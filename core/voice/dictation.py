"""Modalità dettatura: registra a segmenti e digita il testo."""

import queue as _queue
import time as _time

import numpy as np
import sounddevice as sd
import keyboard

from core.i18n import t
from core.voice.transcriber import transcribe
from core.utils.audio import SAMPLE_RATE, play_beep

SPEECH_THRESHOLD = 0.005


def run_dictation(whisper_model, config, state_changed, result_ready, play_beep,
                  countdown=None, initial_text: str = ""):
    """Dettatura continua: registra tutto l'audio, trascrive una volta alla fine."""
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
        result_ready.emit("", t("mic_error", e=e))
        return

    if initial_text:
        print(f"[Dettatura] Testo iniziale: {initial_text}")
        keyboard.write(initial_text)
        result_ready.emit("Dettatura", initial_text)

    all_chunks = []
    last_speech_time = _time.time()
    has_speech = False
    last_countdown_val = -1

    try:
        while True:
            _time.sleep(0.05)

            while not audio_q.empty():
                chunk = audio_q.get()
                all_chunks.append(chunk)
                energy = float(np.sqrt(np.mean(chunk ** 2)))
                if energy > SPEECH_THRESHOLD:
                    has_speech = True
                    last_speech_time = _time.time()

            silence_elapsed = _time.time() - last_speech_time
            remaining = int(silence_timeout - silence_elapsed)
            if countdown and has_speech and remaining <= silence_timeout:
                if remaining != last_countdown_val:
                    last_countdown_val = remaining
                    countdown.emit(max(remaining, 0))

            if silence_elapsed > silence_timeout:
                print(f"[Dettatura] Auto-stop: {silence_timeout}s senza parlato.")
                break

    except Exception as e:
        print(f"[Dettatura] Errore: {e}")
    finally:
        stream.stop()
        stream.close()
        if countdown:
            countdown.emit(-1)

    # Trascrivi tutto in un colpo
    if has_speech and all_chunks:
        audio = np.concatenate(all_chunks)
        duration = len(audio) / SAMPLE_RATE
        if duration >= 0.3:
            state_changed.emit("transcribing")
            print(f"[Dettatura] Audio totale: {duration:.1f}s, trascrivo...")
            text = transcribe(whisper_model, audio, config.whisper_model)
            if text:
                print(f"[Dettatura] Testo: {text}")
                if initial_text:
                    keyboard.write(" ")
                keyboard.write(text)
                result_ready.emit("Dettatura", text)

    play_beep(freq=400, duration=200)
    end_msg = t("dictation_ended", count=1 if has_speech else 0)
    print(f"[Dettatura] {end_msg}")
    result_ready.emit("", end_msg)
    state_changed.emit("idle")


def run_dictation_to_window(whisper_model, config, state_changed, result_ready,
                            play_beep, tts, intent: dict, countdown=None):
    """Dettatura mirata: ascolta a segmenti, trascrive, poi incolla e invia sulla finestra target."""
    import ctypes
    import keyboard as kb
    from core.utils.win32 import find_window_hwnd
    from core.utils.clipboard import clipboard_paste

    silence_timeout = getattr(config, "dictation_silence_timeout", 8)
    device = config.mic_device if config.mic_device is not None else None
    user32 = ctypes.windll.user32

    state_changed.emit("dictation")
    query = intent.get("query", "")
    search_terms = intent.get("search_terms", [])
    print(f"[Dettatura→Finestra] Ascolto per {query}...")

    audio_q = _queue.Queue()

    def callback(indata, frames, time_info, status):
        audio_q.put(indata[:, 0].copy())

    try:
        mic_stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1,
            dtype="float32", device=device,
            blocksize=1600, callback=callback,
        )
        mic_stream.start()
    except Exception as e:
        print(f"[Dettatura→Finestra] Errore mic: {e}")
        play_beep(freq=400, duration=200)
        result_ready.emit("", t("mic_error", e=e))
        state_changed.emit("idle")
        return

    all_chunks = []
    last_speech_time = _time.time()
    has_speech = False
    last_countdown_val = -1

    try:
        while True:
            _time.sleep(0.05)

            while not audio_q.empty():
                chunk = audio_q.get()
                all_chunks.append(chunk)
                energy = float(np.sqrt(np.mean(chunk ** 2)))
                if energy > SPEECH_THRESHOLD:
                    has_speech = True
                    last_speech_time = _time.time()

            silence_elapsed = _time.time() - last_speech_time
            remaining = int(silence_timeout - silence_elapsed)
            if countdown and has_speech and remaining <= silence_timeout:
                if remaining != last_countdown_val:
                    last_countdown_val = remaining
                    countdown.emit(max(remaining, 0))

            if silence_elapsed > silence_timeout:
                print(f"[Dettatura→Finestra] Auto-stop: {silence_timeout}s senza parlato.")
                break

    except Exception as e:
        print(f"[Dettatura→Finestra] Errore: {e}")
    finally:
        mic_stream.stop()
        mic_stream.close()
        if countdown:
            countdown.emit(-1)

    # Trascrivi tutto in un colpo
    dictated_text = ""
    if has_speech and all_chunks:
        audio = np.concatenate(all_chunks)
        duration = len(audio) / SAMPLE_RATE
        if duration >= 0.3:
            state_changed.emit("transcribing")
            print(f"[Dettatura→Finestra] Audio totale: {duration:.1f}s, trascrivo...")
            dictated_text = transcribe(whisper_model, audio, config.whisper_model) or ""
            if dictated_text:
                print(f"[Dettatura→Finestra] Testo: {dictated_text}")
                result_ready.emit("Dettatura", dictated_text)
    if not dictated_text:
        play_beep(freq=400, duration=200)
        result_ready.emit("", t("dictation_no_audio"))
        state_changed.emit("idle")
        return

    print(f"[Dettatura→Finestra] Testo completo: {dictated_text}")

    # Trova finestra e invia
    hwnd = find_window_hwnd(query, search_terms=search_terms)
    if hwnd is None:
        play_beep(freq=400, duration=200)
        result_ready.emit("", t("dictation_window_not_found", query=query))
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
    result_ready.emit(dictated_text, t("dictation_sent", query=query))
    tts.speak(t("dictation_sent", query=query))
    state_changed.emit("idle")
