"""Text-to-Speech engine: Edge TTS (online) con fallback Piper (offline)."""

import asyncio
import io
import os
import threading
import wave

from core.signal import Signal


EDGE_VOICES = {
    "Isabella": "it-IT-IsabellaNeural",
    "Diego": "it-IT-DiegoNeural",
    "Elsa": "it-IT-ElsaNeural",
}

MODELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "models", "tts",
)

PIPER_VOICES = {
    "Paola": "it_IT-paola-medium",
}

DEFAULT_VOICE = "Isabella"


class TTSEngine:
    """Sintetizza testo in voce. Edge TTS online, fallback Piper locale."""

    finished = Signal()

    def __init__(self, voice: str = DEFAULT_VOICE, enabled: bool = True):
        self._voice = voice
        self._enabled = enabled
        self._speaking = False
        self._lock = threading.Lock()
        self._piper = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @property
    def voice(self) -> str:
        return self._voice

    @voice.setter
    def voice(self, value: str):
        self._voice = value
        self._piper = None

    def speak(self, text: str):
        """Avvia la sintesi vocale in un thread separato."""
        if not self._enabled or not text or not text.strip():
            return
        with self._lock:
            if self._speaking:
                return
            self._speaking = True
        threading.Thread(target=self._run, args=(text,), daemon=True).start()

    def _run(self, text: str):
        try:
            self._speak_edge(text)
        except Exception as e:
            print(f"[TTS] Edge TTS fallito: {e}, provo Piper...")
            try:
                self._speak_piper(text)
            except Exception as e2:
                print(f"[TTS] Anche Piper fallito: {e2}")
        finally:
            with self._lock:
                self._speaking = False
            self.finished.emit()

    def _speak_edge(self, text: str):
        import edge_tts

        voice_id = EDGE_VOICES.get(self._voice, EDGE_VOICES[DEFAULT_VOICE])

        async def _generate():
            communicate = edge_tts.Communicate(text, voice_id)
            audio_data = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.write(chunk["data"])
            return audio_data.getvalue()

        loop = asyncio.new_event_loop()
        try:
            audio_bytes = loop.run_until_complete(_generate())
        finally:
            loop.close()

        if not audio_bytes:
            raise RuntimeError("Nessun audio generato da Edge TTS")

        self._play_audio(audio_bytes)

    def _get_piper(self):
        """Lazy-load del modello Piper."""
        if self._piper is not None:
            return self._piper

        from piper import PiperVoice

        voice_name = list(PIPER_VOICES.values())[0]
        model_path = os.path.join(MODELS_DIR, f"{voice_name}.onnx")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Modello Piper non trovato: {model_path}")

        print(f"[TTS] Caricamento modello Piper: {voice_name}")
        self._piper = PiperVoice.load(model_path)
        return self._piper

    def _speak_piper(self, text: str):
        piper = self._get_piper()

        audio_buffer = io.BytesIO()
        with wave.open(audio_buffer, "wb") as wav:
            piper.synthesize_wav(text, wav)

        audio_bytes = audio_buffer.getvalue()
        if not audio_bytes:
            raise RuntimeError("Nessun audio generato da Piper")

        self._play_audio(audio_bytes)

    @staticmethod
    def _play_audio(audio_bytes: bytes):
        """Riproduce audio in memoria tramite pygame."""
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            sound = pygame.mixer.Sound(io.BytesIO(audio_bytes))
            sound.play()
            while pygame.mixer.get_busy():
                pygame.time.wait(50)
        except Exception as e:
            print(f"[TTS] Errore riproduzione: {e}")

    @staticmethod
    def available_voices() -> list[str]:
        return list(EDGE_VOICES.keys())
