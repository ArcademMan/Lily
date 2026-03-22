import threading

import numpy as np

from core.signal import Signal

HALLUCINATION_FILTER = [
    "sottotitoli", "qtss", "amara.org", "sottotitolato",
    "revisione", "traduzione", "trascrizione", "music", "applausi",
]

INITIAL_PROMPT_BASE = "Apri, avvia, cerca, chiudi, cartella, volume, sito web, programma, gioco, screenshot, timer, scrivi, invia, modalità dettatura, sposta, minimizza."
INITIAL_PROMPT_EXTENDED = (
    INITIAL_PROMPT_BASE + " "
    "Elden Ring, Lethal Company, Minecraft, Fortnite, Valorant, Discord, Photoshop, "
    "Premiere Pro, Visual Studio Code, Blender, Steam, Spotify, Chrome, Firefox, OBS, "
    "Claude, Claude Code, Haiku, WhatsApp, Lily."
)

# Per-model transcription settings: (beam_size, vad_filter, initial_prompt)
MODEL_SETTINGS = {
    "tiny":     (1, False, INITIAL_PROMPT_BASE),
    "base":     (1, False, INITIAL_PROMPT_BASE),
    "small":    (3, False, INITIAL_PROMPT_BASE),
    "medium":   (3, True,  INITIAL_PROMPT_EXTENDED),
    "large-v3": (5, True,  INITIAL_PROMPT_EXTENDED),
}


class WhisperLoader:
    """Loads the faster-whisper model in background."""

    def __init__(self, model_size: str = "base"):
        self.finished = Signal()
        self.model_size = model_size
        self.model = None

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            import os, sys
            # Add local CUDA DLLs to PATH
            if getattr(sys, 'frozen', False):
                base = os.path.dirname(sys.executable)
            else:
                base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            lib_dir = os.path.join(base, "lib")
            if os.path.exists(lib_dir):
                os.add_dll_directory(lib_dir)
                os.environ["PATH"] = lib_dir + ";" + os.environ.get("PATH", "")
            from faster_whisper import WhisperModel
            self.model = WhisperModel(self.model_size, device="cuda", compute_type="float16")
            self.finished.emit(True, "Modello Whisper caricato.")
        except Exception as e:
            self.finished.emit(False, f"Errore caricamento Whisper: {e}")


def transcribe(model, audio: np.ndarray, model_size: str = "base") -> str:
    import time as _time
    t0 = _time.perf_counter()
    print("[Whisper] Trascrizione in corso...")

    beam_size, vad_filter, initial_prompt = MODEL_SETTINGS.get(
        model_size, MODEL_SETTINGS["base"]
    )

    kwargs = dict(
        language="it",
        beam_size=beam_size,
        vad_filter=vad_filter,
        initial_prompt=initial_prompt,
    )
    if vad_filter:
        kwargs["vad_parameters"] = dict(min_silence_duration_ms=300)

    segments, info = model.transcribe(audio, **kwargs)
    texts = [seg.text.strip() for seg in segments if seg.text.strip()]
    result = " ".join(texts)

    print(f"[Whisper] Lingua rilevata: {info.language} (prob: {info.language_probability:.2f})")
    print(f"[Whisper] Segmenti: {len(texts)}, testo: '{result}'")
    print(f"[Whisper] Tempo trascrizione: {_time.perf_counter() - t0:.2f}s")

    if any(h in result.lower() for h in HALLUCINATION_FILTER):
        print("[Whisper] Filtrato: allucinazione rilevata")
        return ""
    return result
