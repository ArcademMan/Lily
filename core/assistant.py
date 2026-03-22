import threading
import time as _time

from config import Config
from core.signal import Signal
from core.voice.hotkey import HotkeyManager
from core.voice.listener import ListenWorker
from core.voice.transcriber import WhisperLoader, transcribe
from core.llm.brain import classify_intent
from core.actions import execute_action
from core.voice.tts import TTSEngine
from core.llm.conversation import ConversationMemory

# Intent che richiedono conferma vocale prima dell'esecuzione
DANGEROUS_INTENTS = {"close_program"}
# Intent + parameter che richiedono conferma
DANGEROUS_PARAMS = {("window", "close_all"), ("window", "close_explorer")}

# Timeout in secondi per la conferma
CONFIRM_TIMEOUT = 7



class Assistant:
    """Coordinates the voice pipeline: hold hotkey to record, release to process."""
    state_changed = Signal()
    result_ready = Signal()   # command, result
    notify = Signal()         # notification message

    def __init__(self, config: Config):
        self.config = config
        self._whisper_model = None
        self._listen_worker: ListenWorker | None = None
        self._busy = False
        self._processing = False

        # Memoria conversazionale globale
        self._memory = ConversationMemory(
            max_exchanges=getattr(config, "chat_max_history", 5)
        )

        # TTS
        self.tts = TTSEngine(voice=config.tts_voice, enabled=config.tts_enabled)

        # Hotkey
        self._hotkey = HotkeyManager()
        self._hotkey.pressed.connect(self._start_listening)
        self._hotkey.released.connect(self._stop_listening)

        # Load whisper model in background
        self.state_changed.emit("loading")
        self._loader = WhisperLoader(config.whisper_model)
        self._loader.finished.connect(self._on_model_loaded)
        self._loader.start()

    def _on_model_loaded(self, success: bool, message: str):
        if success:
            self._whisper_model = self._loader.model
            self._hotkey.register(self.config.hotkey)
            self.state_changed.emit("idle")
        else:
            self.notify.emit(message)

    def _start_listening(self):
        if self._busy:
            return
        self._busy = True

        self._listen_worker = ListenWorker(
            self._whisper_model, self.config.mic_device,
            self.config.whisper_model,
        )
        self._listen_worker.status_changed.connect(self.state_changed.emit)
        self._listen_worker.transcription_ready.connect(self._on_transcription)
        self._listen_worker.error.connect(self._on_error)
        self._listen_worker.finished.connect(self._on_worker_finished)
        self._listen_worker.start()

    def _stop_listening(self):
        if self._listen_worker and self._listen_worker.isRunning():
            print("[Hotkey] Stop registrazione")
            self._listen_worker.stop()
        else:
            print("[Hotkey] Stop ignorato (worker non attivo)")

    def _on_transcription(self, text: str):
        self._processing = True
        print(f"[Whisper] Trascrizione: {text}")
        self.state_changed.emit("processing")
        threading.Thread(target=self._process, args=(text,), daemon=True).start()

    @staticmethod
    def _check_dictation(text: str):
        """Controlla se il testo è un comando di dettatura. Ritorna (is_dictation, initial_text)."""
        lower = text.lower().strip().rstrip(".")
        # Keyword matching: se contiene varianti di "dettatura"
        dictation_keywords = ("dettatura", "dittatura", "dettaura", "detta tura")
        for kw in dictation_keywords:
            if kw in lower:
                return True, ""
        # Comandi espliciti
        if lower in ("inizia a dettare", "scrivi quello che dico", "dettami"):
            return True, ""
        # "scrivi [testo]" → digita il testo, MA NON se è "scrivi su/nel/sul/in" (quello è type_in)
        type_in_prefixes = ("scrivi su ", "scrivi nel ", "scrivi sul ", "scrivi in ", "scrivi nella ",
                            "scrivi a ", "scrivi al ")
        if any(lower.startswith(p) for p in type_in_prefixes):
            return False, ""
        for prefix in ("scrivi ", "scrivi, ", "scrivi. "):
            if lower.startswith(prefix):
                return True, text[len(prefix):].strip()
        return False, ""

    def _process(self, text: str):
        t0 = _time.perf_counter()

        # Fast path: dettatura senza passare dall'LLM
        is_dictation, initial_text = self._check_dictation(text)
        if is_dictation:
            print(f"[Dettatura] Rilevato comando dettatura (fast path)")
            self.result_ready.emit(text, "Dettatura attivata.")
            self._play_beep()
            try:
                self._run_dictation(initial_text=initial_text)
            finally:
                self._processing = False
                self._busy = False
            return

        provider = self.config.provider
        model = self.config.anthropic_model if provider == "anthropic" else self.config.ollama_model
        print(f"[LLM] Invio a {model} ({provider})...")
        try:
            # Passa la history per contesto conversazionale
            history = self._memory.get_messages()
            intent = classify_intent(text, self.config, history=history)
            intent["_original_text"] = text
            print(f"[LLM] Tempo risposta: {_time.perf_counter() - t0:.2f}s")
            print(f"[LLM] Risposta: {intent}")

            intent_type = intent.get("intent", "unknown")

            # Dettatura classificata dall'LLM (fallback)
            if intent_type == "dictation":
                initial_text = intent.get("query", "").strip()
                self.result_ready.emit(text, "Dettatura attivata.")
                self._play_beep()
                self._run_dictation(initial_text=initial_text)
                return

            # Dettatura mirata su finestra: "invia su WhatsApp" senza testo
            if intent_type == "type_in" and intent.get("parameter", "").strip().lower() == "dictate":
                target_window = intent.get("query", "")
                self.result_ready.emit(text, f"Parla, invio su {target_window} quando hai finito.")
                self._play_beep()
                self._run_dictation_to_window(intent)
                return

            # Conferma vocale per azioni pericolose
            param = intent.get("parameter", "").strip().lower()
            is_dangerous = (intent_type in DANGEROUS_INTENTS or
                          (intent_type, param) in DANGEROUS_PARAMS)
            if is_dangerous:
                query = intent.get("query", "")
                confirm_msg = self._get_confirm_message(intent_type, query, param)
                print(f"[Sicurezza] Richiesta conferma: {confirm_msg}")
                self.result_ready.emit(text, f"⚠ {confirm_msg}")
                self.tts.speak(confirm_msg)

                # Aspetta che il TTS finisca
                _time.sleep(0.5)
                while self.tts._speaking:
                    _time.sleep(0.1)

                confirmed = self._wait_for_confirmation()
                if not confirmed:
                    cancel_msg = "Azione annullata."
                    print(f"[Sicurezza] {cancel_msg}")
                    self.result_ready.emit(text, cancel_msg)
                    self.tts.speak(cancel_msg)
                    return

                print("[Sicurezza] Confermato!")

            result = execute_action(intent, self.config, memory=self._memory)
            print(f"[Azione] {result}")
            self.result_ready.emit(text, result)
            self.tts.speak(result)

            # Salva nella memoria conversazionale
            self._memory.add_user(text)
            self._memory.add_assistant(result)
        except Exception as e:
            print(f"[Errore] {e}")
            self.result_ready.emit(text, f"Errore: {e}")
        finally:
            self._processing = False
            self._busy = False

    @staticmethod
    def _play_beep(freq: int = 800, duration: int = 150):
        """Suono breve di notifica tramite pygame."""
        try:
            import pygame
            import numpy as np

            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=1)

            sample_rate = 44100
            n_samples = int(sample_rate * duration / 1000)
            t = np.linspace(0, duration / 1000, n_samples, dtype=np.float32)
            # Genera onda sinusoidale con fade in/out
            wave = np.sin(2 * np.pi * freq * t)
            fade = min(n_samples // 10, 500)
            wave[:fade] *= np.linspace(0, 1, fade)
            wave[-fade:] *= np.linspace(1, 0, fade)
            # Converti a int16
            audio = (wave * 16000).astype(np.int16)
            sound = pygame.mixer.Sound(buffer=audio.tobytes())
            sound.play()
            pygame.time.wait(duration + 50)
        except Exception as e:
            print(f"[Beep] Errore: {e}")

    @staticmethod
    def _get_confirm_message(intent_type: str, query: str, parameter: str = "") -> str:
        """Genera il messaggio di conferma in base al tipo di azione."""
        if intent_type == "close_program":
            return f"Vuoi che chiuda {query}?" if query else "Vuoi che chiuda il programma?"
        if intent_type == "window":
            if parameter == "close_all":
                return "Vuoi che chiuda tutte le finestre?"
            if parameter == "close_explorer":
                return "Vuoi che chiuda tutte le cartelle aperte?"
        return f"Confermi l'azione?"

    def _wait_for_confirmation(self) -> bool:
        """Ascolta per conferma vocale senza hotkey. Ritorna True se confermato, False altrimenti."""
        import numpy as np
        import sounddevice as sd
        import queue as _queue

        print(f"[Sicurezza] In attesa di conferma ({CONFIRM_TIMEOUT}s)...")
        self.state_changed.emit("confirming")

        audio_q = _queue.Queue()
        device = self.config.mic_device if self.config.mic_device is not None else None
        SAMPLE_RATE = 16000

        def callback(indata, frames, time_info, status):
            audio_q.put(indata[:, 0].copy())

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1,
                dtype="float32", device=device,
                blocksize=1600, callback=callback,
            )
            stream.start()
        except Exception as e:
            print(f"[Sicurezza] Errore mic: {e}")
            return False

        all_chunks = []
        try:
            start_time = _time.time()
            has_speech = False
            silence_start = None
            SILENCE_THRESHOLD = 0.012
            SILENCE_DURATION = 1.2

            while _time.time() - start_time < CONFIRM_TIMEOUT:
                _time.sleep(0.05)

                # Raccogli nuovi chunk e salva per trascrizione
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

                if energy > SILENCE_THRESHOLD:
                    has_speech = True
                    silence_start = None
                elif has_speech:
                    if silence_start is None:
                        silence_start = _time.time()
                    elif _time.time() - silence_start >= SILENCE_DURATION:
                        print("[Sicurezza] Fine risposta rilevata.")
                        break

            if not has_speech:
                print("[Sicurezza] Timeout, nessuna risposta.")
                return False

        finally:
            stream.stop()
            stream.close()

        # Aggiungi eventuali chunk rimasti
        try:
            while True:
                all_chunks.append(audio_q.get_nowait())
        except _queue.Empty:
            pass

        chunks = all_chunks

        if not chunks:
            return False

        audio = np.concatenate(chunks)
        duration = len(audio) / SAMPLE_RATE
        print(f"[Sicurezza] Audio conferma: {duration:.1f}s")

        if duration < 0.2:
            return False

        response = transcribe(self._whisper_model, audio, self.config.whisper_model)
        print(f"[Sicurezza] Risposta: '{response}'")

        if not response:
            return False

        # Chiedi all'LLM di interpretare la risposta
        return self._llm_confirm(response)

    def _llm_confirm(self, response: str) -> bool:
        """Usa l'LLM per capire se la risposta è una conferma o un rifiuto."""
        from core.llm import get_provider
        from core.llm.brain import _strip_think_tags, _parse_json

        provider = get_provider(self.config)
        thinking = getattr(self.config, "thinking_enabled", False)

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
                model=self.config.ollama_model,
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

        # Default: annulla per sicurezza
        return False

    def _run_dictation(self, initial_text: str = ""):
        """Modalità dettatura: registra a segmenti e digita il testo al cursore."""
        import numpy as np
        import sounddevice as sd
        import queue as _queue
        import keyboard

        SAMPLE_RATE = 16000
        SPEECH_THRESHOLD = 0.008
        SEGMENT_SILENCE = getattr(self.config, "dictation_silence_duration", 3.5)
        silence_timeout = getattr(self.config, "dictation_silence_timeout", 8)

        device = self.config.mic_device if self.config.mic_device is not None else None
        audio_q = _queue.Queue()

        def callback(indata, frames, time_info, status):
            audio_q.put(indata[:, 0].copy())

        self.state_changed.emit("dictation")
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
            self.result_ready.emit("", f"Errore microfono: {e}")
            return

        segments_written = 0

        # Digita subito il testo iniziale (es. "scrivi ciao" → digita "ciao")
        if initial_text:
            print(f"[Dettatura] Testo iniziale: {initial_text}")
            keyboard.write(initial_text)
            segments_written += 1
            self.result_ready.emit("Dettatura", initial_text)

        last_speech_time = _time.time()

        try:
            while True:
                # Fase 1: aspetta che l'utente inizi a parlare
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

                # Fase 2: registra finché parla, stop su silenzio
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

                    if silence_start and _time.time() - silence_start >= SEGMENT_SILENCE:
                        break

                # Fase 3: trascrivi e digita
                if not segment_chunks:
                    continue

                audio = np.concatenate(segment_chunks)
                duration = len(audio) / SAMPLE_RATE
                if duration < 0.3:
                    continue

                print(f"[Dettatura] Segmento: {duration:.1f}s, trascrivo...")
                text = transcribe(self._whisper_model, audio, self.config.whisper_model)

                if text:
                    print(f"[Dettatura] Testo: {text}")
                    if segments_written > 0:
                        keyboard.write(" ")
                    keyboard.write(text)
                    segments_written += 1
                    self.result_ready.emit("Dettatura", text)

        except StopIteration:
            pass
        except Exception as e:
            print(f"[Dettatura] Errore: {e}")
        finally:
            stream.stop()
            stream.close()
            self._play_beep(freq=400, duration=200)
            end_msg = f"Dettatura terminata. {segments_written} segmenti trascritti."
            print(f"[Dettatura] {end_msg}")
            self.result_ready.emit("", end_msg)
            self.state_changed.emit("idle")

    def _run_dictation_to_window(self, intent: dict):
        """Dettatura mirata: ascolta, trascrive tutto, poi incolla e invia sulla finestra target."""
        import numpy as np
        import sounddevice as sd
        import queue as _queue

        SAMPLE_RATE = 16000
        SPEECH_THRESHOLD = 0.008
        SILENCE_DURATION = getattr(self.config, "dictation_silence_duration", 3.5)
        TIMEOUT = getattr(self.config, "dictation_max_duration", 60)

        device = self.config.mic_device if self.config.mic_device is not None else None
        audio_q = _queue.Queue()

        def callback(indata, frames, time_info, status):
            audio_q.put(indata[:, 0].copy())

        self.state_changed.emit("dictation")
        query = intent.get("query", "")
        search_terms = intent.get("search_terms", [])
        print(f"[Dettatura→Finestra] Ascolto per {query}...")

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1,
                dtype="float32", device=device,
                blocksize=1600, callback=callback,
            )
            stream.start()
        except Exception as e:
            print(f"[Dettatura→Finestra] Errore mic: {e}")
            self.result_ready.emit("", f"Errore microfono: {e}")
            return

        # Registra tutto l'audio finché l'utente non smette di parlare
        all_chunks = []
        has_speech = False
        silence_start = None
        start_time = _time.time()

        try:
            while _time.time() - start_time < TIMEOUT:
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

                if energy > SPEECH_THRESHOLD:
                    has_speech = True
                    silence_start = None
                elif has_speech:
                    if silence_start is None:
                        silence_start = _time.time()
                    elif _time.time() - silence_start >= SILENCE_DURATION:
                        print("[Dettatura→Finestra] Fine parlato.")
                        break

        finally:
            stream.stop()
            stream.close()

        if not has_speech or not all_chunks:
            self._play_beep(freq=400, duration=200)
            self.result_ready.emit("", "Nessun audio rilevato.")
            self.state_changed.emit("idle")
            return

        # Trascrivi
        audio = np.concatenate(all_chunks)
        duration = len(audio) / SAMPLE_RATE
        print(f"[Dettatura→Finestra] Audio: {duration:.1f}s, trascrivo...")

        dictated_text = transcribe(self._whisper_model, audio, self.config.whisper_model)
        if not dictated_text:
            self._play_beep(freq=400, duration=200)
            self.result_ready.emit("", "Non ho capito cosa hai detto.")
            self.state_changed.emit("idle")
            return

        print(f"[Dettatura→Finestra] Testo: {dictated_text}")

        # Scrivi e invia sulla finestra target
        from core.actions.type_action import _find_window, _clipboard_paste

        candidates = [query] + search_terms
        words = query.split()
        if len(words) > 1:
            for i in range(len(words)):
                sub = " ".join(words[i:])
                if sub not in candidates:
                    candidates.append(sub)

        import ctypes
        user32 = ctypes.windll.user32
        import keyboard as kb

        hwnd = None
        for term in candidates:
            hwnd = _find_window(term)
            if hwnd:
                break

        if hwnd is None:
            self._play_beep(freq=400, duration=200)
            self.result_ready.emit("", f"Non trovo la finestra {query}.")
            self.state_changed.emit("idle")
            return

        # Salva focus, switch, incolla, invio, ripristina
        prev_hwnd = user32.GetForegroundWindow()
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        _time.sleep(0.15)

        _clipboard_paste(dictated_text)
        _time.sleep(0.05)
        kb.send("enter")
        _time.sleep(0.1)

        if prev_hwnd and prev_hwnd != hwnd:
            user32.SetForegroundWindow(prev_hwnd)

        self._play_beep(freq=400, duration=200)
        self.result_ready.emit(dictated_text, f"Inviato su {query}.")
        self.tts.speak(f"Inviato su {query}.")
        self.state_changed.emit("idle")

    def _on_worker_finished(self):
        print(f"[Worker] Finito. processing={self._processing}")
        if not self._processing:
            self._busy = False

    def _on_error(self, message: str):
        print(f"[Errore] {message}")
        self.state_changed.emit("idle")
        self._busy = False
        self.notify.emit(message)

    def update_hotkey(self):
        self._hotkey.register(self.config.hotkey)
