"""Wake word detection using energy monitoring + Whisper."""

import os
import queue
import re
import threading
import time

import numpy as np
import sounddevice as sd

from core.signal import Signal
from core.utils.audio import SAMPLE_RATE, BLOCKSIZE

_SPEECH_THRESHOLD = 0.012  # Stessa soglia di record_until_silence


class WakeWordListener:
    """Listens for a wake word using energy detection + Whisper.

    Flow:
    1. Monitor audio energy (quasi zero CPU)
    2. When voice detected, record until silence
    3. Transcribe with existing Whisper model
    4. If transcription starts with wake word -> emit signal
    """

    detected = Signal()  # ()

    def __init__(self, wake_word: str = "lily", mic_device=None,
                 whisper_model=None, on_status=None):
        self._wake_word = wake_word.lower().strip()
        self._mic_device = mic_device
        self._whisper_model = whisper_model
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._paused = False
        self._on_status = on_status or (lambda msg: None)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        if not self._whisper_model:
            print("[WakeWord] Nessun modello Whisper, wake word disabilitato")
            return
        self._stop.clear()
        self._paused = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self):
        device = self._mic_device if self._mic_device is not None else None
        self._on_status(f"[WakeWord] In ascolto per '{self._wake_word}'")
        print(f"[WakeWord] In ascolto per '{self._wake_word}'...")

        audio_q = queue.Queue()

        def callback(indata, frames, time_info, status):
            audio_q.put(indata[:, 0].copy())

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1,
                dtype="float32", device=device,
                blocksize=BLOCKSIZE, callback=callback,
            )
            stream.start()
        except Exception as e:
            print(f"[WakeWord] Errore apertura mic: {e}")
            return

        try:
            while not self._stop.is_set():
                if self._paused:
                    while not audio_q.empty():
                        try: audio_q.get_nowait()
                        except queue.Empty: break
                    self._stop.wait(0.1)
                    continue

                try:
                    chunk = audio_q.get(timeout=0.2)
                except queue.Empty:
                    continue

                energy = float(np.sqrt(np.mean(chunk ** 2)))
                if energy < _SPEECH_THRESHOLD:
                    continue

                print(f"[WakeWord] Voce rilevata (energy={energy:.4f})")

                audio = self._record_until_silence(audio_q, chunk)
                if audio is None:
                    continue

                duration = len(audio) / SAMPLE_RATE
                print(f"[WakeWord] Registrato {duration:.1f}s, trascrivo...")

                text = self._transcribe(audio)
                if not text:
                    print("[WakeWord] Trascrizione vuota")
                    continue

                print(f"[WakeWord] Trascrizione: '{text}'")

                if self._is_wake_word(text):
                    print("[WakeWord] MATCH! Attivo.")
                    self.detected.emit()
                    # Aspetta che la pausa venga attivata dal callback
                    while self._paused and not self._stop.is_set():
                        while not audio_q.empty():
                            try: audio_q.get_nowait()
                            except queue.Empty: break
                        self._stop.wait(0.1)
                    continue
                else:
                    print(f"[WakeWord] No match (cercavo '{self._wake_word}')")

        except Exception as e:
            if not self._stop.is_set():
                print(f"[WakeWord] Errore: {e}")
        finally:
            stream.stop()
            stream.close()

    def _record_until_silence(self, audio_q, initial_chunk: np.ndarray) -> np.ndarray | None:
        """Registra fino al silenzio. Stessi parametri di core.utils.audio."""
        chunks = [initial_chunk]
        silence_start = None
        start = time.perf_counter()

        while not self._stop.is_set() and not self._paused:
            if time.perf_counter() - start > 4.0:
                break

            try:
                chunk = audio_q.get(timeout=0.2)
            except queue.Empty:
                continue
            chunks.append(chunk)

            energy = float(np.sqrt(np.mean(chunk ** 2)))

            if energy >= _SPEECH_THRESHOLD:
                silence_start = None
            else:
                if silence_start is None:
                    silence_start = time.perf_counter()
                elif time.perf_counter() - silence_start >= 0.8:
                    break

        audio = np.concatenate(chunks)
        if len(audio) < SAMPLE_RATE * 0.3:
            print("[WakeWord] Audio troppo corto, ignoro")
            return None
        return audio

    def _transcribe(self, audio: np.ndarray) -> str:
        try:
            segments, _ = self._whisper_model.transcribe(
                audio,
                language="en",
                beam_size=1,
                vad_filter=False,
            )
            texts = [seg.text.strip() for seg in segments if seg.text.strip()]
            return " ".join(texts)
        except Exception:
            return ""

    def _is_wake_word(self, text: str) -> bool:
        """Match fuzzy per il wake word."""
        clean = re.sub(r'[^\w\s]', '', text.lower().strip())
        # Match esatto col wake word completo
        if clean.startswith(self._wake_word):
            return True
        # Senza spazi (es. "heylily")
        compact = clean.replace(" ", "")
        wake_compact = self._wake_word.replace(" ", "")
        if compact.startswith(wake_compact):
            return True
        # Match con ogni parola del wake word (es. "lily" matcha "hey lily")
        wake_words = self._wake_word.split()
        for word in wake_words:
            if clean == word or clean.startswith(word + " "):
                return True
        return False
