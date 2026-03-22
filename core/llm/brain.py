import json
import re

from core.llm import get_provider

SYSTEM_PROMPT_OLLAMA = """Classify the user intent from Italian voice input. The text comes from speech-to-text and OFTEN contains errors.
You MUST fix names to their REAL form. Think about what real program, game, or app the user meant.

CRITICAL: The transcription is often wrong! Common examples:
- "Eldering" / "Altering" / "Elder Ring" = "Elden Ring" (game by FromSoftware)
- "Little Company" / "Lysol Company" / "Legal Company" = "Lethal Company"
- "Fortnight" / "Fort Night" = "Fortnite"
- "Maicraft" / "Main Craft" = "Minecraft"
- "Valloran" / "Valorant" = "Valorant"
- "Lega of Legend" = "League of Legends"
- "Fottosciop" / "Foto Shop" = "Photoshop"
- "Primo Pro" = "Premiere Pro"
- "After Effect" = "After Effects"
- "Blender" could be "Blender" (correct)
- "Vi Es Code" / "Visco" = "VS Code" / "Visual Studio Code"
- "Cloud Code" / "Clod Code" = "Claude Code"
- Always think: what REAL software/game sounds like what was transcribed?

Reply with ONLY a JSON object, nothing else.

{"intent": "TYPE", "query": "CORRECTED_NAME", "search_terms": ["alt1", "alt2"], "parameter": "PARAM"}

TYPE must be one of:
- open_folder: user wants to FIND or OPEN A FOLDER/DIRECTORY. Keywords: "cartella", "directory", "dove si trova"
- open_program: user wants to LAUNCH/START a program, app or game. Keywords: "apri", "avvia", "lancia", "esegui"
- close_program: user wants to CLOSE/QUIT a running program. Keywords: "chiudi", "termina", "stoppa", "esci da"
- open_website: user wants to open a website or search online. If user wants to SEARCH something ("cerca su Google X", "cercalo su Google", "me lo cerchi su Google"), query = the search terms, NOT "google.com". If user wants to open a specific site ("apri YouTube"), query = the URL/domain. ANY mention of "Google" + searching = open_website, NEVER search_files.
- search_files: user wants to FIND/SEARCH for a SPECIFIC file by name. Keywords: "cerca file", "trova file", "trovami il file". ONLY when the user mentions a specific filename.
- screenshot: user wants to take a screenshot. Keywords: "screenshot", "schermata", "cattura schermo"
- timer: user wants to set a timer/alarm. parameter = duration (e.g. "5m", "1h", "30s"). Keywords: "timer", "sveglia", "avvisami tra"
- volume: user wants to change SYSTEM volume. parameter = "up", "down", or "mute"
- media: user wants to control music/media playback. parameter = "play_pause", "next", "previous", or "stop". Keywords: "metti play", "pausa", "prossima canzone", "canzone precedente", "stop musica", "riproduci", "metti in pausa"
- window: user wants to manage windows/screens. parameter values:
  "close_explorer" = close all open folders/explorer windows
  "minimize_all" or "show_desktop" = minimize everything / show desktop
  "snap_left" or "snap_right" = move window to left/right half of screen (put program name in query)
  "move_monitor" = move window to the other monitor/screen (put program name in query)
  "minimize" = minimize a specific window (put program name in query)
  "restore" = restore/show a minimized window (put program name in query)
  "close_all" = close all windows
  "nudge_up", "nudge_down", "nudge_left", "nudge_right" = move window slightly in a direction. Append pixel amount: "nudge_down_100" for 100px. Default is 50px. "un po'" = 50, "molto" = 200, or user can specify exact pixels.
  Keywords: "chiudi le cartelle", "minimizza tutto", "mostra desktop", "sposta a sinistra/destra", "sposta sull'altro schermo", "ripristina", "minimizza", "più in alto", "più in basso", "più a sinistra", "più a destra"
- screen_read: user wants to READ/SEE what's on a window or screen. Captures the window and reads the text via OCR. query = window/program name. parameter = what to look for or question about the content. Keywords: "leggi", "cosa c'è scritto", "leggimi", "cosa vedi su", "ultimo messaggio", "cosa dice"
- type_in: user wants to GO TO a specific window and optionally TYPE text there. query = window/program name to focus. parameter = the text to type. If the user wants to SEND/SUBMIT the message, ALWAYS append " e invia" at the END of parameter. Keywords: "vai su", "vai sul", "scrivi su", "scrivi nel", "scrivi a", "digita su", "invia a/su"
  IMPORTANT for type_in: when user says "invia" or "e invia" ANYWHERE in the sentence, put " e invia" at the END of parameter.
  CRITICAL: "invia su X" or "invia a X" at the START of a sentence = ALWAYS type_in, NEVER chat.
  CRITICAL: parameter must contain ALL the text after the app name, VERBATIM. Do NOT summarize, cut, or rephrase. Copy the ENTIRE message exactly as the user said it.
  If user says ONLY "invia su X" or "scrivi su X" WITHOUT specifying what to write, set parameter to "dictate" — the system will activate voice dictation mode for that window.
- time: user asks for current time or date
- dictation: user wants to type text at cursor via voice. Keywords: "modalità dettatura", "dettatura", "scrivi", "dettami". If user says "scrivi [TEXT]", put [TEXT] in query (the part AFTER "scrivi"). If just "modalità dettatura" or "dettatura", query is empty.
- chat: user is asking a QUESTION, wants information, making conversation, or asking something that doesn't fit other intents. Keywords: "cos'è", "chi è", "perché", "come funziona", "dimmi", "racconta", "dove stanno", "dove si trovano", "come faccio". Use this for questions like "dove sono i salvataggi di X?" or "come si installa Y?"
- unknown: ONLY for completely unintelligible or empty input. If the input is a question or conversation, use "chat" instead

IMPORTANT:
- "query" = the CORRECTED real name, NOT the raw transcription. Fix typos and transcription errors!
- "search_terms" = multiple alternative real names, abbreviations, exe names. Include variations to maximize search success.
- "apri X" where X is a program = open_program. "chiudi X" = close_program. open_folder ONLY with "cartella/directory/folder".
- For open_folder: query = the MAIN SUBJECT name only (e.g. "Lethal Company", not "video Lethal Company"). The system will search for all folders matching the name and pick the best one based on context.
- parameter defaults to "" if not needed. search_terms defaults to [] if not needed.

Examples:
- "apri Eldering" -> {"intent": "open_program", "query": "Elden Ring", "search_terms": ["Elden Ring", "ELDEN RING", "eldenring"], "parameter": ""}
- "chiudi Discord" -> {"intent": "close_program", "query": "Discord", "search_terms": ["Discord", "discord.exe"], "parameter": ""}
- "apri Chrome" -> {"intent": "open_program", "query": "Chrome", "search_terms": ["Google Chrome", "chrome.exe"], "parameter": ""}
- "apri Foto Shop" -> {"intent": "open_program", "query": "Photoshop", "search_terms": ["Adobe Photoshop", "Photoshop", "photoshop.exe"], "parameter": ""}
- "apri la cartella video di Elden Ring" -> {"intent": "open_folder", "query": "Elden Ring", "search_terms": ["Elden Ring", "ELDEN RING"], "parameter": ""}
- "apri la cartella documenti" -> {"intent": "open_folder", "query": "Documenti", "search_terms": ["Documents", "Documenti"], "parameter": ""}
- "fai uno screenshot" -> {"intent": "screenshot", "query": "", "search_terms": [], "parameter": ""}
- "metti un timer di 5 minuti" -> {"intent": "timer", "query": "", "search_terms": [], "parameter": "5m"}
- "cos'è la fotosintesi?" -> {"intent": "chat", "query": "cos'è la fotosintesi?", "search_terms": [], "parameter": ""}
- "raccontami una barzelletta" -> {"intent": "chat", "query": "raccontami una barzelletta", "search_terms": [], "parameter": ""}
- "dove stanno i salvataggi di Elden Ring?" -> {"intent": "chat", "query": "dove stanno i salvataggi di Elden Ring?", "search_terms": [], "parameter": ""}
- "trovami il file banane funghi" -> {"intent": "search_files", "query": "banane funghi", "search_terms": ["banane funghi", "bananefunghi"], "parameter": ""}
- "chiudi tutte le cartelle" -> {"intent": "window", "query": "", "search_terms": [], "parameter": "close_explorer"}
- "minimizza tutto" -> {"intent": "window", "query": "", "search_terms": [], "parameter": "minimize_all"}
- "sposta Discord a sinistra" -> {"intent": "window", "query": "Discord", "search_terms": [], "parameter": "snap_left"}
- "mostra il desktop" -> {"intent": "window", "query": "", "search_terms": [], "parameter": "show_desktop"}
- "sposta Chrome sull'altro schermo" -> {"intent": "window", "query": "Chrome", "search_terms": [], "parameter": "move_monitor"}
- "ripristina Discord" -> {"intent": "window", "query": "Discord", "search_terms": [], "parameter": "restore"}
- "minimizza Discord" -> {"intent": "window", "query": "Discord", "search_terms": [], "parameter": "minimize"}
- "sposta Discord più in basso" -> {"intent": "window", "query": "Discord", "search_terms": [], "parameter": "nudge_down"}
- "sposta Chrome 100 pixel a destra" -> {"intent": "window", "query": "Chrome", "search_terms": [], "parameter": "nudge_right_100"}
- "sposta Discord molto più su" -> {"intent": "window", "query": "Discord", "search_terms": [], "parameter": "nudge_up_200"}
- "leggimi l'ultimo messaggio su WhatsApp" -> {"intent": "screen_read", "query": "WhatsApp", "search_terms": [], "parameter": "ultimo messaggio"}
- "cosa c'è scritto su Discord" -> {"intent": "screen_read", "query": "Discord", "search_terms": [], "parameter": ""}
- "cosa vedi sul terminale" -> {"intent": "screen_read", "query": "terminale", "search_terms": [], "parameter": ""}
- "vai sul terminale e scrivi ciao e invia" -> {"intent": "type_in", "query": "terminale", "search_terms": [], "parameter": "ciao e invia"}
- "vai su Sublime" -> {"intent": "type_in", "query": "Sublime", "search_terms": [], "parameter": ""}
- "scrivi su Discord ok perfetto e invia" -> {"intent": "type_in", "query": "Discord", "search_terms": [], "parameter": "ok perfetto e invia"}
- "invia a WhatsApp questo messaggio è da Lily" -> {"intent": "type_in", "query": "WhatsApp", "search_terms": [], "parameter": "questo messaggio è da Lily e invia"}
- "scrivi a WhatsApp ciao e invialo" -> {"intent": "type_in", "query": "WhatsApp", "search_terms": [], "parameter": "ciao e invia"}
- "invia su WhatsApp ciao sto programmando e non posso parlare" -> {"intent": "type_in", "query": "WhatsApp", "search_terms": [], "parameter": "ciao sto programmando e non posso parlare e invia"}
- "invia su WhatsApp" -> {"intent": "type_in", "query": "WhatsApp", "search_terms": [], "parameter": "dictate"}
- "scrivi su Discord" -> {"intent": "type_in", "query": "Discord", "search_terms": [], "parameter": "dictate"}
- "metti pausa" -> {"intent": "media", "query": "", "search_terms": [], "parameter": "play_pause"}
- "prossima canzone" -> {"intent": "media", "query": "", "search_terms": [], "parameter": "next"}
- "canzone precedente" -> {"intent": "media", "query": "", "search_terms": [], "parameter": "previous"}
- "modalità dettatura" -> {"intent": "dictation", "query": "", "search_terms": [], "parameter": ""}
- "scrivi ciao come stai" -> {"intent": "dictation", "query": "ciao come stai", "search_terms": [], "parameter": ""}
- "scrivi quello che dico" -> {"intent": "dictation", "query": "", "search_terms": [], "parameter": ""}"""

SYSTEM_PROMPT_CLAUDE = """Classify Italian voice input. Fix transcription errors, correct names to real form. Reply ONLY with JSON:
{"intent":"TYPE","query":"KEY_TERM","search_terms":["alt1","alt2"],"parameter":"PARAM"}

Intents: open_folder, open_program, close_program, open_website, search_files, screenshot, timer (parameter=duration like "5m"), volume (parameter=up/down/mute), time, dictation ("modalità dettatura"/"dettatura"/"scrivi quello che dico"), chat (general questions/conversation), unknown (ONLY for unintelligible input).
open_folder ONLY with "cartella/directory/folder". close_program for "chiudi/termina". search_files for "cerca/trova file".
query = corrected key term. search_terms = real alternative names. Think about actual PC paths.

Examples:
- "apri la cartella video di Altering" -> {"intent":"open_folder","query":"Elden Ring","search_terms":["Elden Ring","EldenRing"],"parameter":""}
- "chiudi Discord" -> {"intent":"close_program","query":"Discord","search_terms":["Discord","discord.exe"],"parameter":""}
- "cerca i file PSD" -> {"intent":"search_files","query":"*.psd","search_terms":["ext:psd"],"parameter":""}
- "cercalo su Google" -> {"intent":"open_website","query":"(use context from conversation)","search_terms":[],"parameter":""}
- "me lo cerchi su Google" -> {"intent":"open_website","query":"(use context from conversation)","search_terms":[],"parameter":""}
- "fai uno screenshot" -> {"intent":"screenshot","query":"","search_terms":[],"parameter":""}
- "metti un timer di 5 minuti" -> {"intent":"timer","query":"","search_terms":[],"parameter":"5m"}
- "cos'è la fotosintesi?" -> {"intent":"chat","query":"cos'è la fotosintesi?","search_terms":[],"parameter":""}"""

PICK_PROMPT_OLLAMA = """The user said: "{user_query}"
The classified intent was: {intent_type}, looking for: "{intent_query}"

Here are the search results (file/folder paths):
{results}

Pick the BEST matching result for what the user wants. Consider the FULL user request, not just the query name.
For example, if the user asked for "cartella video di X", prefer paths containing "Video" or "video".
Reply with ONLY a JSON object:
{{"pick": INDEX}}
where INDEX is the 0-based index of the best result. If none match, reply {{"pick": -1}}

PRIORITY RULES:
1. Start Menu shortcuts (.lnk in "Start Menu") = BEST for launching programs/games
2. Desktop shortcuts (.lnk on Desktop) = second best
3. Main game/program .exe = OK if no shortcut exists
4. Paths that match the user's CONTEXT (video, documenti, etc.) are preferred
5. AVOID: uninstallers, debug tools, artbooks, soundtracks, DLC extras, updaters, crash reporters, WER/ReportArchive
6. RESPECT user EXCLUSIONS: if user says "not on D:", "non su D", "che non sta in D", EXCLUDE results on that drive. Reply {{"pick": -1}} if all results are excluded."""

PICK_PROMPT_CLAUDE = """User said: "{user_query}"
Intent: {intent_type}, query: "{intent_query}"
Results:
{results}
Pick BEST match considering full user context. Reply ONLY: {{"pick": INDEX}} (0-based, -1 if none match)"""

RETRY_PROMPT = """I searched for "{query}" with terms {search_terms} but found NOTHING on the user's PC.
The user said: "{user_query}"

The name might be wrong due to speech-to-text errors. Suggest alternative search terms.
Reply with ONLY a JSON object:
{{"search_terms": ["term1", "term2", "term3"]}}

Think about:
- The version WITHOUT spaces (e.g. "Animus Template" -> "AnimusTemplate")
- The version WITH spaces if original had none
- Common misspellings or misheard versions of the name
- The actual real name of the program/game/folder
- Shorter or partial versions of the name"""


CHAT_SYSTEM_PROMPT = """Sei Lily, un'assistente vocale italiana. Rispondi in modo naturale, conciso e amichevole.

REGOLE IMPORTANTI:
- Rispondi SEMPRE in italiano
- Sii concisa: le tue risposte verranno lette ad alta voce, quindi evita testi troppo lunghi
- Massimo 2-3 frasi per risposta, a meno che l'utente non chieda spiegazioni dettagliate
- Hai personalità: sei simpatica, disponibile e un po' spiritosa
- Se non sai qualcosa, dillo onestamente
- Non usare markdown, emoji o formattazione speciale (il testo viene letto dal TTS)
- Non usare elenchi puntati o numerati, usa frasi discorsive

COMANDI DISPONIBILI (se l'utente chiede cosa puoi fare, elencali in modo discorsivo):
- Aprire programmi e giochi: "apri Discord", "avvia Photoshop"
- Chiudere programmi: "chiudi Chrome" (chiede conferma prima)
- Aprire cartelle: "apri la cartella video di Elden Ring"
- Cercare file: "trovami il file animus template"
- Aprire siti web: "apri YouTube", "cerca su Google qualcosa"
- Screenshot: "fai uno screenshot"
- Timer: "metti un timer di 5 minuti"
- Volume: "alza il volume", "muta"
- Controllo musica: "metti pausa", "prossima canzone", "canzone precedente"
- Gestione finestre: "chiudi tutte le cartelle", "minimizza tutto", "mostra il desktop", "sposta Discord a sinistra"
- Scrivere su finestre: "vai sul terminale e scrivi ciao e invia", "vai su Discord e scrivi ok perfetto"
- Leggere lo schermo: "leggimi l'ultimo messaggio su WhatsApp", "cosa c'è scritto su Discord", "cosa vedi sul terminale"
- Ora e data: "che ora è?"
- Modalità dettatura: "modalità dettatura" (trascrive e digita al cursore)
- Conversazione: puoi fare domande su qualsiasi cosa"""


def _get_prompts(config):
    if getattr(config, "provider", "ollama") == "anthropic":
        return SYSTEM_PROMPT_CLAUDE, PICK_PROMPT_CLAUDE
    return SYSTEM_PROMPT_OLLAMA, PICK_PROMPT_OLLAMA


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
    # Con thinking attivo, servono più token (thinking usa ~200-300 token)
    if thinking:
        num_predict = max(num_predict, 512)
    provider = get_provider(config)
    try:
        messages = [{"role": "system", "content": system_prompt}]
        # Aggiungi history per contesto (follow-up tra comandi)
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

    system_prompt = CHAT_SYSTEM_PROMPT
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


def pick_best_result(user_query: str, results: list[str], config,
                     intent_type: str = "", intent_query: str = "") -> int:
    if not results:
        return -1
    if len(results) == 1:
        # Still validate single result against user context
        # (e.g. user said "not on D:" but only result is on D:)
        pass

    thinking = getattr(config, "thinking_enabled", False)
    is_cloud = getattr(config, "provider", "ollama") == "anthropic"
    capped = results[:10] if is_cloud else results
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
