import threading

import numpy as np

from core.i18n import t, t_list
from core.signal import Signal


def _model_settings() -> dict:
    base = t("whisper_initial_prompt_base")
    extended = t("whisper_initial_prompt_extended")
    return {
        "tiny":     (1, False, base),
        "base":     (1, False, base),
        "small":    (3, False, base),
        "medium":   (3, True,  extended),
        "large-v3": (5, True,  extended),
    }


class WhisperLoader:
    """Loads the faster-whisper model in background."""

    def __init__(self, model_size: str = "base", device: str = "cuda"):
        self.finished = Signal()
        self.model_size = model_size
        self.device = device
        self.model = None

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            import os, sys
            # Add local CUDA DLLs to PATH (only needed for GPU)
            if self.device == "cuda":
                if getattr(sys, 'frozen', False):
                    base = os.path.dirname(sys.executable)
                else:
                    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                lib_dir = os.path.join(base, "lib")
                if os.path.exists(lib_dir):
                    os.add_dll_directory(lib_dir)
                    os.environ["PATH"] = lib_dir + ";" + os.environ.get("PATH", "")
            from faster_whisper import WhisperModel
            from config import MODELS_DIR
            # Load model from local Lily models directory
            model_path = os.path.join(MODELS_DIR, f"faster-whisper-{self.model_size}")
            if not os.path.isdir(model_path):
                model_path = self.model_size  # fallback to HF download
            compute = "float16" if self.device == "cuda" else "int8"
            self.model = WhisperModel(model_path, device=self.device, compute_type=compute)
            label = "GPU" if self.device == "cuda" else "CPU"
            self.finished.emit(True, t("whisper_loaded", label=label))
        except Exception as e:
            self.finished.emit(False, t("whisper_load_error", e=e))


def transcribe(model, audio: np.ndarray, model_size: str = "base") -> str:
    import time as _time
    t0 = _time.perf_counter()
    print("[Whisper] Trascrizione in corso...")

    settings = _model_settings()
    beam_size, vad_filter, initial_prompt = settings.get(
        model_size, settings["base"]
    )

    kwargs = dict(
        language=t("whisper_language"),
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

    if any(h in result.lower() for h in t_list("hallucination_words")):
        print("[Whisper] Filtrato: allucinazione rilevata")
        return ""
    return result
