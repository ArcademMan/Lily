"""Modalità dettatura: registra a segmenti e digita il testo."""

import queue as _queue
import time as _time

import numpy as np
import sounddevice as sd
import keyboard

from core.voice.transcriber import transcribe
from core.utils.audio import record_until_silence, SAMPLE_RATE, play_beep

SPEECH_THRESHOLD = 0.008


def run_dictation(whisper_model, config, state_changed, result_ready, play_beep,
                  initial_text: str = ""):
    """Dettatura a segmenti: registra, trascrive e digita al cursore."""
    segment_silence = getattr(config, "dictation_silence_duration", 3.5)
    silence_timeout = getattr(config, "dictation_silence_timeout", 8)
    device = config.mic_device if config.mic_device is not None else None
    audio_q = _queue.Queue()

    def callback(indata, frames, time_info, status):
        audio_q.put(indata[:, 0].copy())

    state_changed.emit("dictation")
    print(f"[Dettatura] Avviata. Auto-stop dopo {silence_timeout}s di silenzio.")

    try:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1,
            dtype="float32", device=device,
            blocksize=1600, callback=callback,
        )
        stream.start()
    except Exception as e:
        print(f"[Dettatura] Errore mic: {e}")
        result_ready.emit("", f"Errore microfono: {e}")
        return

    segments_written = 0

    if initial_text:
        print(f"[Dettatura] Testo iniziale: {initial_text}")
        keyboard.write(initial_text)
        segments_written += 1
        result_ready.emit("Dettatura", initial_text)

    last_speech_time = _time.time()

    try:
        while True:
            # Fase 1: aspetta parlato
            has_speech = False
            while not has_speech:
                _time.sleep(0.05)
                if _time.time() - last_speech_time > silence_timeout:
                    print(f"[Dettatura] Auto-stop: {silence_timeout}s senza parlato.")
                    raise StopIteration

                latest = None
                while not audio_q.empty():
                    latest = audio_q.get()
                if latest is not None:
                    energy = float(np.sqrt(np.mean(latest ** 2)))
                    if energy > SPEECH_THRESHOLD:
                        has_speech = True
                        last_speech_time = _time.time()

            # Fase 2: registra segmento
            print("[Dettatura] Parlato rilevato, registro segmento...")
            segment_chunks = []
            while not audio_q.empty():
                segment_chunks.append(audio_q.get())

            silence_start = None
            while True:
                _time.sleep(0.03)
                got_chunk = False
                while not audio_q.empty():
                    chunk = audio_q.get()
                    segment_chunks.append(chunk)
                    got_chunk = True
                    energy = float(np.sqrt(np.mean(chunk ** 2)))
                    if energy > SPEECH_THRESHOLD:
                        silence_start = None
                        last_speech_time = _time.time()
                    elif silence_start is None:
                        silence_start = _time.time()

                if not got_chunk and silence_start is None:
                    silence_start = _time.time()

                if silence_start and _time.time() - silence_start >= segment_silence:
                    break

            # Fase 3: trascrivi e digita
            if not segment_chunks:
                continue

            audio = np.concatenate(segment_chunks)
            duration = len(audio) / SAMPLE_RATE
            if duration < 0.3:
                continue

            print(f"[Dettatura] Segmento: {duration:.1f}s, trascrivo...")
            text = transcribe(whisper_model, audio, config.whisper_model)

            if text:
                print(f"[Dettatura] Testo: {text}")
                if segments_written > 0:
                    keyboard.write(" ")
                keyboard.write(text)
                segments_written += 1
                result_ready.emit("Dettatura", text)

    except StopIteration:
        pass
    except Exception as e:
        print(f"[Dettatura] Errore: {e}")
    finally:
        stream.stop()
        stream.close()
        play_beep(freq=400, duration=200)
        end_msg = f"Dettatura terminata. {segments_written} segmenti trascritti."
        print(f"[Dettatura] {end_msg}")
        result_ready.emit("", end_msg)
        state_changed.emit("idle")


def run_dictation_to_window(whisper_model, config, state_changed, result_ready,
                            play_beep, tts, intent: dict):
    """Dettatura mirata: ascolta, trascrive, poi incolla e invia sulla finestra target."""
    import ctypes
    import keyboard as kb
    from core.utils.win32 import find_window_hwnd
    from core.utils.clipboard import clipboard_paste

    silence_duration = getattr(config, "dictation_silence_duration", 3.5)
    timeout = getattr(config, "dictation_max_duration", 60)
    device = config.mic_device if config.mic_device is not None else None
    user32 = ctypes.windll.user32

    state_changed.emit("dictation")
    query = intent.get("query", "")
    search_terms = intent.get("search_terms", [])
    print(f"[Dettatura→Finestra] Ascolto per {query}...")

    audio = record_until_silence(
        device=device, timeout=timeout,
        silence_duration=silence_duration,
        speech_threshold=SPEECH_THRESHOLD,
    )

    if audio is None:
        play_beep(freq=400, duration=200)
        result_ready.emit("", "Nessun audio rilevato.")
        state_changed.emit("idle")
        return

    # Trascrivi
    duration = len(audio) / SAMPLE_RATE
    print(f"[Dettatura→Finestra] Audio: {duration:.1f}s, trascrivo...")

    dictated_text = transcribe(whisper_model, audio, config.whisper_model)
    if not dictated_text:
        play_beep(freq=400, duration=200)
        result_ready.emit("", "Non ho capito cosa hai detto.")
        state_changed.emit("idle")
        return

    print(f"[Dettatura→Finestra] Testo: {dictated_text}")

    # Trova finestra e invia
    hwnd = find_window_hwnd(query, search_terms=search_terms)
    if hwnd is None:
        play_beep(freq=400, duration=200)
        result_ready.emit("", f"Non trovo la finestra {query}.")
        state_changed.emit("idle")
        return

    # Focus, incolla, invio, ripristina
    prev_hwnd = user32.GetForegroundWindow()
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    _time.sleep(0.15)

    clipboard_paste(dictated_text)
    _time.sleep(0.2)
    kb.send("enter")
    _time.sleep(0.2)

    if prev_hwnd and prev_hwnd != hwnd:
        user32.SetForegroundWindow(prev_hwnd)

    play_beep(freq=400, duration=200)
    result_ready.emit(dictated_text, f"Inviato su {query}.")
    tts.speak(f"Inviato su {query}.")
    state_changed.emit("idle")
