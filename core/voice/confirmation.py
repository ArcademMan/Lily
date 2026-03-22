"""Gestione conferma vocale per azioni pericolose."""

import numpy as np

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

    response = transcribe(whisper_model, audio, config.whisper_model)
    print(f"[Sicurezza] Risposta: '{response}'")

    if not response:
        return False

    return _llm_confirm(response, config)


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
        return f"Vuoi che chiuda {query}?" if query else "Vuoi che chiuda il programma?"
    if intent_type == "window":
        if parameter == "close_all":
            return "Vuoi che chiuda tutte le finestre?"
        if parameter == "close_explorer":
            return "Vuoi che chiuda tutte le cartelle aperte?"
    if intent_type == "notes" and parameter == "svuota":
        return "Vuoi cancellare tutte le note?"
    return "Confermi l'azione?"
