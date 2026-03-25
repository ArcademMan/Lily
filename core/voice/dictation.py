"""Modalità dettatura: registra a segmenti e digita il testo."""

import queue as _queue
import threading as _threading
import time as _time

import numpy as np
import sounddevice as sd
import keyboard

from core.i18n import t
from core.voice.transcriber import transcribe
from core.utils.audio import SAMPLE_RATE, play_beep

SPEECH_THRESHOLD = 0.005
MIN_SPEECH_DURATION = 0.3


def run_dictation(whisper_model, config, state_changed, result_ready, play_beep,
                  countdown=None, initial_text: str = ""):
    """Dettatura a chunk: il mic non si ferma mai, la trascrizione avviene in parallelo."""
    chunk_silence = config.dictation_silence_duration
    end_silence = config.dictation_silence_timeout
    max_duration = config.dictation_max_duration
    device = config.mic_device if config.mic_device is not None else None
    model_size = config.whisper_model

    audio_q = _queue.Queue()
    transcribe_q = _queue.Queue()
    written_any = [False]

    def callback(indata, frames, time_info, status):
        audio_q.put(indata[:, 0].copy())

    # --- Worker thread: trascrive chunk dalla coda e digita ---
    def transcribe_worker():
        while True:
            item = transcribe_q.get()
            if item is None:
                break
            audio_data = item
            duration = len(audio_data) / SAMPLE_RATE
            if duration < MIN_SPEECH_DURATION:
                continue
            print(f"[Dettatura] Trascrivo chunk di {duration:.1f}s...")
            text = transcribe(whisper_model, audio_data, model_size)
            if text:
                print(f"[Dettatura] Chunk: {text}")
                if written_any[0] or initial_text:
                    keyboard.write(" ")
                keyboard.write(text)
                written_any[0] = True
                result_ready.emit("Dettatura", text)

    worker = _threading.Thread(target=transcribe_worker, daemon=True)
    worker.start()

    state_changed.emit("dictation")
    print(f"[Dettatura] Avviata (chunk={chunk_silence}s, stop={end_silence}s, max={max_duration}s)")

    try:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1,
            dtype="float32", device=device,
            blocksize=1600, callback=callback,
        )
        stream.start()
    except Exception as e:
        print(f"[Dettatura] Errore mic: {e}")
        transcribe_q.put(None)
        result_ready.emit("", t("mic_error", e=e))
        return

    if initial_text:
        print(f"[Dettatura] Testo iniziale: {initial_text}")
        keyboard.write(initial_text)
        written_any[0] = True
        result_ready.emit("Dettatura", initial_text)

    current_chunks = []
    last_speech_time = _time.time()
    has_speech = False
    chunk_has_speech = False
    start_time = _time.time()
    last_countdown_val = -1
    chunk_count = 0

    try:
        while True:
            _time.sleep(0.05)

            while not audio_q.empty():
                chunk = audio_q.get()
                current_chunks.append(chunk)
                energy = float(np.sqrt(np.mean(chunk ** 2)))
                if energy > SPEECH_THRESHOLD:
                    has_speech = True
                    chunk_has_speech = True
                    last_speech_time = _time.time()

            silence_elapsed = _time.time() - last_speech_time
            total_elapsed = _time.time() - start_time

            # Countdown verso fine dettatura
            remaining = int(end_silence - silence_elapsed)
            if countdown and has_speech and remaining <= end_silence:
                if remaining != last_countdown_val:
                    last_countdown_val = remaining
                    countdown.emit(max(remaining, 0))

            # Silenzio breve dopo parlato -> taglia chunk e manda in coda
            if chunk_has_speech and silence_elapsed >= chunk_silence and current_chunks:
                audio = np.concatenate(current_chunks)
                transcribe_q.put(audio)
                chunk_count += 1
                print(f"[Dettatura] Chunk #{chunk_count} inviato ({len(audio)/SAMPLE_RATE:.1f}s)")
                current_chunks = []
                chunk_has_speech = False

            # Silenzio lungo -> fine dettatura
            if silence_elapsed >= end_silence and has_speech:
                print(f"[Dettatura] Auto-stop: {end_silence}s senza parlato.")
                break

            # Timeout durata massima
            if total_elapsed >= max_duration:
                print(f"[Dettatura] Max durata raggiunta ({max_duration}s).")
                break

    except Exception as e:
        print(f"[Dettatura] Errore: {e}")
    finally:
        stream.stop()
        stream.close()
        if countdown:
            countdown.emit(-1)

    # Flush ultimo chunk se c'e parlato rimasto
    if chunk_has_speech and current_chunks:
        audio = np.concatenate(current_chunks)
        transcribe_q.put(audio)
        chunk_count += 1
        print(f"[Dettatura] Ultimo chunk #{chunk_count} inviato ({len(audio)/SAMPLE_RATE:.1f}s)")

    # Segnala al worker di terminare e aspetta che finisca
    transcribe_q.put(None)
    worker.join(timeout=30)

    play_beep(freq=400, duration=200)
    end_msg = t("dictation_ended", count=chunk_count)
    print(f"[Dettatura] {end_msg} ({chunk_count} chunk trascritti)")
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
