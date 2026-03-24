"""Gestione conferma vocale per azioni pericolose."""

import numpy as np

from core.i18n import t, t_set
from core.utils.audio import record_until_silence, SAMPLE_RATE
from core.voice.transcriber import transcribe

CONFIRM_TIMEOUT = 7
SILENCE_THRESHOLD = 0.012
SILENCE_DURATION = 1.2


def wait_for_confirmation(whisper_model, config, state_changed) -> bool:
    """Ascolta per conferma vocale senza hotkey. Ritorna True se confermato."""
    print(f"[Sicurezza] In attesa di conferma ({CONFIRM_TIMEOUT}s)...")
    state_changed.emit("confirming")

    device = config.mic_device if config.mic_device is not None else None
    audio = record_until_silence(
        device=device, timeout=CONFIRM_TIMEOUT,
        silence_duration=SILENCE_DURATION,
        speech_threshold=SILENCE_THRESHOLD,
    )

    if audio is None:
        print("[Sicurezza] Timeout, nessuna risposta.")
        return False

    duration = len(audio) / SAMPLE_RATE
    print(f"[Sicurezza] Audio conferma: {duration:.1f}s")

    if duration < 0.2:
        return False

    state_changed.emit("transcribing")
    response = transcribe(whisper_model, audio, config.whisper_model)
    print(f"[Sicurezza] Risposta: '{response}'")

    if not response:
        return False

    # Fast keyword matching first, LLM fallback only if ambiguous
    keyword_result = _keyword_confirm(response)
    if keyword_result is not None:
        print(f"[Sicurezza] Conferma via keyword: {keyword_result}")
        return keyword_result

    return _llm_confirm(response, config)


def _keyword_confirm(response: str) -> bool | None:
    """Fast yes/no detection via keywords. Returns None if ambiguous."""
    text = response.strip().lower()
    # Check exact match or phrase match
    for kw in t_set("yes_keywords"):
        if kw in text:
            return True
    for kw in t_set("no_keywords"):
        if kw in text:
            return False
    return None  # ambiguous — fall back to LLM


def _llm_confirm(response: str, config) -> bool:
    """Usa l'LLM per capire se la risposta è una conferma o un rifiuto."""
    from core.llm import get_provider
    from core.llm.brain import _strip_think_tags, _parse_json

    provider = get_provider(config)
    thinking = getattr(config, "thinking_enabled", False)

    prompt = f"""The user was asked to confirm a dangerous action. They replied: "{response}"

Did they confirm (yes) or deny (no)? Reply ONLY with JSON:
{{"confirm": true}} or {{"confirm": false}}

Examples of YES: "sì", "ok", "vai", "fallo", "certo", "procedi", "confermo", "sì chiudi"
Examples of NO: "no", "annulla", "stop", "lascia stare", "non farlo", "aspetta"
If unclear, default to false (safer)."""

    if not thinking:
        prompt += "\n/no_think"

    try:
        raw = provider.chat(
            model=config.ollama_model,
            messages=[{"role": "user", "content": prompt}],
            format_json=True,
            num_predict=16,
            timeout=10,
            thinking=thinking,
        )
        raw = _strip_think_tags(raw)
        print(f"[Sicurezza] LLM conferma raw: {raw}")
        data = _parse_json(raw)
        if data and "confirm" in data:
            return bool(data["confirm"])
    except Exception as e:
        print(f"[Sicurezza] Errore LLM conferma: {e}")

    return False


def get_confirm_message(intent_type: str, query: str, parameter: str = "") -> str:
    """Genera il messaggio di conferma in base al tipo di azione."""
    if intent_type == "close_program":
        return t("confirm_close_query", query=query) if query else t("confirm_close_generic")
    if intent_type == "window":
        if parameter == "close_all":
            return t("confirm_close_all_windows")
        if parameter == "close_explorer":
            return t("confirm_close_all_folders")
    if intent_type == "notes" and parameter == "svuota":
        return t("confirm_delete_all_notes")
    return t("confirm_generic")
