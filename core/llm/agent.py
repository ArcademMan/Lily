"""Agent loop: LLM chiama tool, osserva risultati, decide il passo successivo."""

import json
import re
from typing import Callable

from core.llm import get_provider
from core.llm.brain import _parse_json, _strip_think_tags, _apply_thinking, _get_model
from core.actions import get_tool_schemas


def _build_tool_descriptions(schemas: list[dict]) -> str:
    """Genera la sezione tool del prompt agent dai TOOL_SCHEMA."""
    lines = []
    for s in schemas:
        name = s["name"]
        desc = s["description"]
        params = s.get("parameters", {}).get("properties", {})
        required = s.get("parameters", {}).get("required", [])

        param_parts = []
        for pname, pinfo in params.items():
            req = " (required)" if pname in required else ""
            pdesc = pinfo.get("description", "")
            if "enum" in pinfo:
                pdesc += f" [{'/'.join(pinfo['enum'])}]"
            param_parts.append(f"  {pname}: {pinfo.get('type', 'string')}{req} - {pdesc}")

        param_block = "\n".join(param_parts) if param_parts else "  (nessun parametro)"
        lines.append(f"- {name}: {desc}\n{param_block}")

    return "\n".join(lines)


def _build_system_prompt(tool_descriptions: str) -> str:
    from config import SETTINGS_DIR, LILY_DIR
    from core.memory import get_memory_for_prompt
    memory_block = get_memory_for_prompt() or ""
    return f"""You are Lily, an autonomous voice assistant for Windows. You have these tools:

{tool_descriptions}

IMPORTANT:
- run_command runs PowerShell. PREFER it for file operations, system queries, and anything not covered by other tools
- To read a file: run_command with Get-Content 'path'. To count files: Get-ChildItem. To check system: Get-Process, ipconfig, etc.
- Write SIMPLE, SHORT commands. If a previous result has a path, use it directly in run_command
- Other tools are shortcuts: volume, media, timer, screenshot. Use them only for those specific actions
RULES:
- ONE tool at a time, then observe the result
- Never ask the user for confirmation. Act, if it fails try differently
- When the user says to write/send to terminal, ONLY write and stop. Do not read or send more commands after
- Always reply in Italian. MAX 1 sentence. No suggestions, no questions, no explanations
- ONE JSON only, nothing else
To call a tool:
{{"tool_call": {{"name": "TOOL_NAME", "arguments": {{"param": "value"}}}}}}
When you have the final answer:
{{"final_answer": "Response in Italian for the user"}}
ALWAYS one of the two. Never both. Never text outside JSON.
final_answer: plain text, no markdown, no asterisks, no formatting. It will be read aloud.
Your settings dir: {SETTINGS_DIR} (files: lily_settings.json)
Your install dir: {LILY_DIR}
{memory_block}"""


def run_agent(
    request: str,
    config,
    memory=None,
    execute_fn: Callable = None,
    detail_fn: Callable = None,
    confirm_fn: Callable = None,
    stop_event=None,
    max_iterations: int = None,
) -> str:
    """Esegue un agent loop: LLM chiama tool, osserva risultati, itera.

    Args:
        request: Testo dell'utente
        config: Config dell'app
        memory: ConversationMemory (opzionale)
        execute_fn: Funzione che esegue un intent dict e ritorna str
        detail_fn: Callback per aggiornamenti UI (opzionale)
        confirm_fn: Callback per conferma comandi pericolosi (cmd: str) -> bool
        max_iterations: Max iterazioni (default da config)

    Returns:
        Risposta finale dell'agente (stringa parlabile)
    """
    if max_iterations is None:
        max_iterations = getattr(config, "agent_max_iterations", 6)

    schemas = get_tool_schemas()
    if not schemas:
        return "Nessun tool disponibile.", []

    tool_names = {s["name"] for s in schemas}
    tool_desc = _build_tool_descriptions(schemas)
    system_prompt = _build_system_prompt(tool_desc)

    thinking = getattr(config, "thinking_enabled", False)
    system_prompt = _apply_thinking(system_prompt, config)

    provider = get_provider(config)
    model = _get_model(config)

    # Costruisci messaggi iniziali
    messages = [{"role": "system", "content": system_prompt}]

    # Aggiungi history dalla conversation memory
    if memory:
        history = memory.get_messages()
        if history:
            messages.extend(history[-6:])  # Ultime 3 coppie

    messages.append({"role": "user", "content": request})

    results_log = []
    last_tool_args = None
    repeat_count = 0

    for i in range(max_iterations):
        if stop_event and stop_event.is_set():
            print("[Agent] Interrotto dall'utente")
            return "Interrotto.", results_log

        if detail_fn and i > 0:
            detail_fn(f"Agente: passo {i + 1}...")

        try:
            raw = provider.chat(
                model=model,
                messages=messages,
                format_json=True,
                num_predict=getattr(config, "chat_num_predict", 384),
                timeout=30,
                thinking=thinking,
            )
        except Exception as e:
            print(f"[Agent] Errore LLM: {e}")
            break

        raw = _strip_think_tags(raw)
        print(f"[Agent] Step {i + 1} raw: {raw[:300]}")

        parsed = _parse_json(raw)
        if not parsed:
            # LLM ha risposto con testo libero, trattalo come final_answer
            clean = raw.strip()
            if clean:
                return clean, results_log
            break

        # Final answer
        if "final_answer" in parsed:
            answer = str(parsed["final_answer"]).strip()
            # Strip markdown che il TTS leggerebbe letteralmente
            answer = re.sub(r'\*+', '', answer)
            answer = re.sub(r'`+', '', answer)
            answer = re.sub(r'#+\s*', '', answer)
            answer = answer.strip()
            if answer:
                return answer, results_log
            break

        # Tool call
        tool_call = parsed.get("tool_call")
        if not tool_call or "name" not in tool_call:
            # Nessun tool call e nessun final_answer — forse l'LLM ha restituito
            # direttamente i parametri di un tool (intent-style)?
            if "intent" in parsed or "name" in parsed:
                tool_call = {"name": parsed.get("name") or parsed.get("intent"),
                             "arguments": parsed}
            else:
                break

        tool_name = tool_call["name"]
        tool_args = tool_call.get("arguments", {})

        # Validazione tool
        if tool_name not in tool_names:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"[Errore] Tool '{tool_name}' non esiste. Tool disponibili: {', '.join(sorted(tool_names))}"})
            continue

        # Anti-loop: se chiama lo stesso tool con gli stessi argomenti
        current_call = (tool_name, json.dumps(tool_args, sort_keys=True))
        if current_call == last_tool_args:
            repeat_count += 1
            if repeat_count >= 2:
                print(f"[Agent] Loop rilevato: {tool_name} chiamato 3 volte con stessi args")
                break
        else:
            repeat_count = 0
            last_tool_args = current_call

        # Costruisci intent dict ed esegui
        intent = {"intent": tool_name}
        intent.update(tool_args)
        intent["_original_text"] = request

        print(f"[Agent] Chiamo tool: {tool_name} args={tool_args}")
        if detail_fn:
            detail_fn(f"Agente: {tool_name}...")

        try:
            result = execute_fn(intent) if execute_fn else f"Tool {tool_name} non disponibile"
        except Exception as e:
            result = f"Errore nell'esecuzione di {tool_name}: {e}"
            print(f"[Agent] Errore exec: {e}")

        if stop_event and stop_event.is_set():
            print("[Agent] Interrotto dall'utente dopo exec")
            return "Interrotto.", results_log

        print(f"[Agent] Risultato: {result[:200]}")
        results_log.append(f"{tool_name}: {result}")

        # Aggiungi alla conversazione
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": f"[Risultato di {tool_name}]: {result}"})

    # Se siamo usciti dal loop senza final_answer, costruisci un riassunto
    if results_log:
        return ". ".join(results_log), results_log
    return "Non sono riuscita a completare la richiesta.", results_log
