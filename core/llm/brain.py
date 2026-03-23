"""Intent classification, chat response, result picking, and retry term suggestion."""

import json
import re

from core.llm import get_provider
from core.llm.prompts import (
    SYSTEM_PROMPT_OLLAMA, SYSTEM_PROMPT_CLAUDE,
    PICK_PROMPT_OLLAMA, PICK_PROMPT_CLAUDE,
    RETRY_PROMPT, CHAT_SYSTEM_PROMPT, CHAIN_PROMPT,
    _get_lily_paths_block,
)


_lily_paths_block = _get_lily_paths_block()


def _get_prompts(config):
    provider = getattr(config, "provider", "ollama")
    if provider in ("anthropic", "openai", "gemini"):
        return SYSTEM_PROMPT_CLAUDE + _lily_paths_block, PICK_PROMPT_CLAUDE
    return SYSTEM_PROMPT_OLLAMA + _lily_paths_block, PICK_PROMPT_OLLAMA


def _strip_think_tags(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _parse_json(text: str) -> dict | None:
    start = text.find("{")
    end = text.find("}", start)
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def _apply_thinking(prompt: str, config) -> str:
    """Append /no_think to prompt if thinking is disabled."""
    thinking = getattr(config, "thinking_enabled", False)
    if not thinking:
        return prompt + "\n/no_think"
    return prompt


def classify_intent(text: str, config, history: list[dict] = None) -> dict:
    fallback = {"intent": "unknown", "query": "", "parameter": "", "search_terms": []}
    system_prompt, _ = _get_prompts(config)
    thinking = getattr(config, "thinking_enabled", False)
    system_prompt = _apply_thinking(system_prompt, config)
    num_predict = getattr(config, "num_predict", 128)
    if thinking:
        num_predict = max(num_predict, 512)
    provider = get_provider(config)
    try:
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": text})

        raw = provider.chat(
            model=config.ollama_model,
            messages=messages,
            format_json=True,
            num_predict=num_predict,
            thinking=thinking,
        )
        raw = _strip_think_tags(raw)
        print(f"[LLM] Risposta raw: {raw}")

        result = _parse_json(raw)
        if not result or "intent" not in result:
            return fallback

        result.setdefault("query", "")
        result.setdefault("parameter", "")
        result.setdefault("search_terms", [])
        return result
    except Exception as e:
        print(f"[LLM] Errore: {e}")
        return fallback


def generate_chat_response(text: str, history: list[dict], config) -> str:
    """Genera una risposta conversazionale usando l'LLM con lo storico della chat."""
    provider = get_provider(config)
    chat_num_predict = getattr(config, "chat_num_predict", 384)
    thinking = getattr(config, "thinking_enabled", False)

    system_prompt = CHAT_SYSTEM_PROMPT + _lily_paths_block
    if not thinking:
        system_prompt = _apply_thinking(system_prompt, config)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": text})

    try:
        raw = provider.chat(
            model=config.ollama_model,
            messages=messages,
            format_json=False,
            temperature=0.7,
            num_predict=chat_num_predict,
            timeout=30,
            thinking=thinking,
        )
        raw = _strip_think_tags(raw)
        return raw.strip() if raw.strip() else "Scusa, non sono riuscita a formulare una risposta."
    except Exception as e:
        print(f"[LLM] Chat errore: {e}")
        return "Mi dispiace, ho avuto un problema nel rispondere."


def decompose_chain(text: str, config) -> list[dict]:
    """Decompone un comando multiplo in una lista di intent singoli."""
    provider = get_provider(config)
    thinking = getattr(config, "thinking_enabled", False)
    prompt = CHAIN_PROMPT
    if not thinking:
        prompt = _apply_thinking(prompt, config)

    try:
        raw = provider.chat(
            model=config.ollama_model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            format_json=False,
            num_predict=getattr(config, "chat_num_predict", 384),
            timeout=30,
            thinking=thinking,
        )
        raw = _strip_think_tags(raw)
        print(f"[LLM] Chain raw: {raw}")

        # Parse JSON array
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1:
            return []
        arr = json.loads(raw[start:end + 1])
        if isinstance(arr, list):
            return arr
    except Exception as e:
        print(f"[LLM] Chain errore: {e}")
    return []


def pick_best_result(user_query: str, results: list[str], config,
                     intent_type: str = "", intent_query: str = "") -> int:
    if not results:
        return -1
    if len(results) == 1:
        pass

    thinking = getattr(config, "thinking_enabled", False)
    is_cloud = getattr(config, "provider", "ollama") in ("anthropic", "openai", "gemini")
    max_results = getattr(config, "anthropic_max_results", 10)
    capped = results[:max_results] if is_cloud else results
    _, pick_template = _get_prompts(config)
    provider = get_provider(config)

    def _short(path: str) -> str:
        if not is_cloud:
            return path
        parts = path.replace("\\", "/").split("/")
        if len(parts) <= 4:
            return "/".join(parts)
        return parts[0] + "/.../" + "/".join(parts[-3:])

    numbered = "\n".join(f"{i}: {_short(r)}" for i, r in enumerate(capped))
    prompt = pick_template.format(
        user_query=user_query, results=numbered,
        intent_type=intent_type or "unknown",
        intent_query=intent_query or user_query,
    )
    prompt = _apply_thinking(prompt, config)

    try:
        raw = provider.chat(
            model=config.ollama_model,
            messages=[{"role": "user", "content": prompt}],
            format_json=True,
            num_predict=max(32, getattr(config, "num_predict", 128) // 4),
            timeout=30,
            thinking=thinking,
            num_ctx=16384,
        )
        raw = _strip_think_tags(raw)
        print(f"[LLM] Pick raw: {raw}")

        data = _parse_json(raw)
        if not data:
            return 0
        idx = data.get("pick", 0)
        if idx < 0:
            return -1
        return idx if idx < len(capped) else 0
    except Exception as e:
        print(f"[LLM] Pick errore: {e}")
        return 0


def suggest_retry_terms(query: str, search_terms: list[str],
                        user_query: str, config) -> list[str]:
    """Ask LLM for alternative search terms when nothing was found."""
    thinking = getattr(config, "thinking_enabled", False)
    provider = get_provider(config)
    prompt = RETRY_PROMPT.format(
        query=query, search_terms=search_terms, user_query=user_query,
    )
    prompt = _apply_thinking(prompt, config)

    try:
        print(f"[LLM] Nessun risultato, chiedo termini alternativi...")
        raw = provider.chat(
            model=config.ollama_model,
            messages=[{"role": "user", "content": prompt}],
            format_json=True,
            num_predict=64,
            timeout=15,
            thinking=thinking,
        )
        raw = _strip_think_tags(raw)
        print(f"[LLM] Retry raw: {raw}")

        data = _parse_json(raw)
        if data and "search_terms" in data:
            return [t for t in data["search_terms"] if t and t not in search_terms]
    except Exception as e:
        print(f"[LLM] Retry errore: {e}")
    return []
