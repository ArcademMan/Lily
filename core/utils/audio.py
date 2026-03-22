"""Utility audio condivise: beep e registrazione con silence detection."""

import queue as _queue
import time as _time

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
BLOCKSIZE = 1600


def play_beep(freq: int = 800, duration: int = 150):
    """Suono breve di notifica tramite pygame."""
    try:
        import pygame

        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=1)

        sample_rate = 44100
        n_samples = int(sample_rate * duration / 1000)
        t = np.linspace(0, duration / 1000, n_samples, dtype=np.float32)
        wave = np.sin(2 * np.pi * freq * t)
        fade = min(n_samples // 10, 500)
        wave[:fade] *= np.linspace(0, 1, fade)
        wave[-fade:] *= np.linspace(1, 0, fade)
        audio = (wave * 16000).astype(np.int16)
        sound = pygame.mixer.Sound(buffer=audio.tobytes())
        sound.play()
        pygame.time.wait(duration + 50)
    except Exception as e:
        print(f"[Beep] Errore: {e}")


def record_until_silence(device=None, timeout: float = 60,
                         silence_duration: float = 1.2,
                         speech_threshold: float = 0.012) -> np.ndarray | None:
    """Registra audio dal microfono finché non rileva silenzio dopo speech.

    Returns numpy array of audio or None if no speech detected.
    """
    audio_q = _queue.Queue()

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
        print(f"[Audio] Errore mic: {e}")
        return None

    all_chunks = []
    try:
        start_time = _time.time()
        has_speech = False
        silence_start = None

        while _time.time() - start_time < timeout:
            _time.sleep(0.05)

            got_new = False
            try:
                while True:
                    chunk = audio_q.get_nowait()
                    all_chunks.append(chunk)
                    got_new = True
            except _queue.Empty:
                pass

            if not got_new:
                continue

            energy = float(np.sqrt(np.mean(all_chunks[-1] ** 2)))

            if energy > speech_threshold:
                has_speech = True
                silence_start = None
            elif has_speech:
                if silence_start is None:
                    silence_start = _time.time()
                elif _time.time() - silence_start >= silence_duration:
                    break

        if not has_speech:
            return None

    finally:
        stream.stop()
        stream.close()

    # Drain remaining chunks
    try:
        while True:
            all_chunks.append(audio_q.get_nowait())
    except _queue.Empty:
        pass

    if not all_chunks:
        return None

    return np.concatenate(all_chunks)
