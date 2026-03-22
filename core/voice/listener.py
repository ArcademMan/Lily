import threading
import time

import numpy as np
import sounddevice as sd

from core.signal import Signal
from core.voice.transcriber import transcribe


class ListenWorker:
    """Records audio while running, then transcribes."""

    SAMPLE_RATE = 16000
    def __init__(self, model, mic_device=None, model_size: str = "base"):
        self.status_changed = Signal()
        self.transcription_ready = Signal()
        self.error = Signal()
        self.finished = Signal()
        self.model = model
        self.mic_device = mic_device
        self.model_size = model_size
        self._running = True
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        if self.model is None:
            self.error.emit("Modello Whisper non caricato.")
            self.finished.emit()
            return

        self.status_changed.emit("listening")
        try:
            audio = self._record()
            if audio is None or len(audio) < self.SAMPLE_RATE * 0.3:
                self.error.emit("Nessun audio rilevato.")
                return

            self.status_changed.emit("processing")
            text = transcribe(self.model, audio, self.model_size)
            if text:
                self.transcription_ready.emit(text)
            else:
                self.error.emit("Nessun testo riconosciuto.")
        except Exception as e:
            self.error.emit(f"Errore: {e}")
        finally:
            self.status_changed.emit("idle")
            self.finished.emit()

    def _record(self) -> np.ndarray | None:
        import queue
        audio_queue = queue.Queue()
        device = self.mic_device if self.mic_device is not None else None

        def callback(indata, frames, time_info, status):
            if status:
                print(f"[Mic] Status: {status}")
            audio_queue.put(indata[:, 0].copy())

        try:
            with sd.InputStream(samplerate=self.SAMPLE_RATE, channels=1,
                                dtype="float32", device=device,
                                blocksize=1600, callback=callback):
                print("[Mic] Registrazione iniziata...")
                while self._running:
                    time.sleep(0.05)
        except Exception as e:
            self.error.emit(f"Errore microfono: {e}")
            return None

        chunks = []
        while not audio_queue.empty():
            chunks.append(audio_queue.get())

        if not chunks:
            return None
        audio = np.concatenate(chunks)
        duration = len(audio) / self.SAMPLE_RATE
        print(f"[Mic] Registrazione finita. Durata: {duration:.1f}s")
        return audio

    def stop(self):
        self._running = False

    def isRunning(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


def get_mic_devices() -> list[dict]:
    devices = sd.query_devices()
    return [
        {"index": i, "name": d["name"]}
        for i, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]
