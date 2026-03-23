import sys
import threading
import time as _time

from config import Config
from core.signal import Signal
from core.voice.hotkey import HotkeyManager
from core.voice.listener import ListenWorker
from core.voice.transcriber import WhisperLoader
from core.llm.brain import classify_intent, decompose_chain
from core.actions import execute_action
from core.voice.tts import TTSEngine
from core.llm.conversation import ConversationMemory
from core.voice.confirmation import wait_for_confirmation, get_confirm_message
from core.voice.dictation import run_dictation, run_dictation_to_window
from core.utils.audio import play_beep
from core.utils.clipboard import copy_to_clipboard
from core.actions.timer_action import _TimerNotifier

# Intent che richiedono conferma vocale prima dell'esecuzione
DANGEROUS_INTENTS = {"close_program"}
# Intent + parameter che richiedono conferma
DANGEROUS_PARAMS = {("window", "close_all"), ("window", "close_explorer"), ("notes", "svuota")}


class _LogTee:
    """Wraps stdout per catturare le righe di log in un buffer."""

    def __init__(self, original, buffer: list):
        self.original = original
        self.buffer = buffer

    def write(self, text):
        self.original.write(text)
        if text and text.strip():
            self.buffer.append(text.rstrip("\n"))

    def flush(self):
        self.original.flush()

    def __getattr__(self, name):
        return getattr(self.original, name)


class Assistant:
    """Coordinates the voice pipeline: hold hotkey to record, release to process."""
    state_changed = Signal()
    result_ready = Signal()   # command, result
    notify = Signal()         # notification message
    detail = Signal()         # detailed status message

    def __init__(self, config: Config):
        self.config = config
        self._whisper_model = None
        self._listen_worker: ListenWorker | None = None
        self._busy = False
        self._processing = False
        self._last_command_log: list[str] = []

        # Memoria conversazionale globale
        self._memory = ConversationMemory(
            max_exchanges=getattr(config, "chat_max_history", 5)
        )

        # TTS
        self.tts = TTSEngine(voice=config.tts_voice, enabled=config.tts_enabled)

        # Collega timer/reminder al TTS e notifiche
        timer_notifier = _TimerNotifier.instance()
        timer_notifier.speak.connect(lambda msg: self.tts.speak(msg))
        timer_notifier.notify.connect(lambda msg: self.notify.emit(msg))

        # Hotkey
        self._hotkey = HotkeyManager()
        self._hotkey.pressed.connect(self._start_listening)
        self._hotkey.released.connect(self._stop_listening)

        # Load whisper model in background
        self.state_changed.emit("loading")
        self._loader = WhisperLoader(config.whisper_model, config.whisper_device)
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
        dictation_keywords = ("dettatura", "dittatura", "dettaura", "detta tura")
        for kw in dictation_keywords:
            if kw in lower:
                return True, ""
        if lower in ("inizia a dettare", "scrivi quello che dico", "dettami"):
            return True, ""
        type_in_prefixes = ("scrivi su ", "scrivi nel ", "scrivi sul ", "scrivi in ", "scrivi nella ",
                            "scrivi a ", "scrivi al ")
        if any(lower.startswith(p) for p in type_in_prefixes):
            return False, ""
        for prefix in ("scrivi ", "scrivi, ", "scrivi. "):
            if lower.startswith(prefix):
                return True, text[len(prefix):].strip()
        return False, ""

    _STOP_WORDS = {"stop", "lily stop", "fermati", "basta", "zitto", "zitta", "taci"}
    _RESTART_WORDS = {"riavviati", "lily riavviati", "restart", "riavvia lily", "riavvio"}

    def _check_stop(self, text: str) -> bool:
        """Controlla se è un comando di stop. Ferma TTS immediatamente."""
        import re
        lower = re.sub(r'[,\.!\?]', '', text.lower().strip())
        lower = re.sub(r'\s+', ' ', lower).strip()
        # Rimuovi "lily" dal prefisso per il matching
        clean = lower.removeprefix("lily ").strip()
        if lower in self._STOP_WORDS or clean in self._STOP_WORDS:
            print("[Stop] Comando stop rilevato")
            self.tts.stop()
            self.result_ready.emit(text, "")
            return True
        if lower in self._RESTART_WORDS or clean in self._RESTART_WORDS:
            print("[Restart] Comando riavvio rilevato")
            self.result_ready.emit(text, "Mi riavvio...")
            self._request_restart()
            return True
        return False

    def _request_restart(self):
        """Segnala al main loop che deve riavviare."""
        import sys
        import subprocess
        import os

        python = sys.executable
        script = os.path.abspath(sys.argv[0])
        cwd = os.path.dirname(script)
        pid = os.getpid()

        # Lancia wrapper che aspetta la morte del processo e rilancia
        restart_cmd = (
            f'powershell -WindowStyle Hidden -Command "'
            f'Wait-Process -Id {pid} -ErrorAction SilentlyContinue; '
            f'Start-Sleep -Seconds 3; '
            f'Start-Process -FilePath \'{python}\' -ArgumentList \'{script}\' -WorkingDirectory \'{cwd}\'"'
        )
        print(f"[Restart] PID={pid}, lancio wrapper...")
        subprocess.Popen(restart_cmd, shell=True)

        # Emetti segnale — il bridge Qt lo riceve nel main thread e chiude l'app
        self.notify.emit("__RESTART__")

    def _process(self, text: str):
        # Cattura log del comando
        capture_buf: list[str] = []
        old_stdout = sys.stdout
        sys.stdout = _LogTee(old_stdout, capture_buf)

        t0 = _time.perf_counter()

        try:
            self._process_inner(text, t0)
        finally:
            sys.stdout = old_stdout
            # Salva il log solo se non è un copy_log (evita sovrascrittura)
            if capture_buf and not any("copy_log" in line for line in capture_buf[:5]):
                self._last_command_log = list(capture_buf)

    def _process_inner(self, text: str, t0: float):
        # Fast path: stop
        if self._check_stop(text):
            self._processing = False
            self._busy = False
            return

        # Fast path: dettatura senza passare dall'LLM
        is_dictation, initial_text = self._check_dictation(text)
        if is_dictation:
            print("[Dettatura] Rilevato comando dettatura (fast path)")
            self.result_ready.emit(text, "Dettatura attivata.")
            play_beep()
            try:
                run_dictation(
                    self._whisper_model, self.config,
                    self.state_changed, self.result_ready, play_beep,
                    initial_text=initial_text,
                )
            finally:
                self._processing = False
                self._busy = False
            return

        provider = self.config.provider
        model = self.config.anthropic_model if provider == "anthropic" else self.config.ollama_model
        print(f"[LLM] Invio a {model} ({provider})...")
        self.detail.emit("Classificazione intent...")
        try:
            history = self._memory.get_messages()
            intent = classify_intent(text, self.config, history=history)
            intent["_original_text"] = text
            print(f"[LLM] Tempo risposta: {_time.perf_counter() - t0:.2f}s")
            print(f"[LLM] Risposta: {intent}")

            intent_type = intent.get("intent", "unknown")
            query = intent.get("query", "")
            self.detail.emit(f"{intent_type}: {query}" if query else intent_type)

            # Copia ultimo log nella clipboard
            if intent_type == "copy_log":
                self._handle_copy_log(text)
                return

            # Catena di comandi
            if intent_type == "chain":
                self.detail.emit("Decomposizione comandi...")
                steps = decompose_chain(text, self.config)
                if not steps:
                    self.result_ready.emit(text, "Non sono riuscita a scomporre i comandi.")
                    return

                print(f"[Chain] {len(steps)} passaggi")
                results = []
                for i, step in enumerate(steps):
                    step_intent = step.get("intent", "unknown")

                    # Wait step
                    if step_intent == "wait":
                        secs = float(step.get("parameter", "1"))
                        print(f"[Chain] Attesa {secs}s...")
                        self.detail.emit(f"Attesa {secs}s...")
                        _time.sleep(secs)
                        continue

                    step["_original_text"] = text
                    self.detail.emit(f"Passo {i + 1}/{len(steps)}: {step_intent}")
                    print(f"[Chain] Passo {i + 1}: {step}")

                    result = execute_action(step, self.config, memory=self._memory)
                    results.append(result)
                    print(f"[Chain] → {result}")

                final = ". ".join(results)
                self.detail.emit("")
                self.result_ready.emit(text, final)
                self.tts.speak("Fatto, ho eseguito tutti i comandi.")
                self._memory.add_user(text)
                self._memory.add_assistant(final)
                return

            # Dettatura classificata dall'LLM (fallback)
            if intent_type == "dictation":
                initial_text = intent.get("query", "").strip()
                self.result_ready.emit(text, "Dettatura attivata.")
                play_beep()
                run_dictation(
                    self._whisper_model, self.config,
                    self.state_changed, self.result_ready, play_beep,
                    initial_text=initial_text,
                )
                return

            # Dettatura mirata su finestra
            if intent_type == "type_in" and intent.get("parameter", "").strip().lower() == "dictate":
                target_window = intent.get("query", "")
                self.result_ready.emit(text, f"Parla, invio su {target_window} quando hai finito.")
                play_beep()
                run_dictation_to_window(
                    self._whisper_model, self.config,
                    self.state_changed, self.result_ready, play_beep,
                    self.tts, intent,
                )
                return

            # Conferma vocale per azioni pericolose
            param = intent.get("parameter", "").strip().lower()
            is_dangerous = (intent_type in DANGEROUS_INTENTS or
                          (intent_type, param) in DANGEROUS_PARAMS)
            if is_dangerous:
                query = intent.get("query", "")
                confirm_msg = get_confirm_message(intent_type, query, param)
                print(f"[Sicurezza] Richiesta conferma: {confirm_msg}")
                self.result_ready.emit(text, f"⚠ {confirm_msg}")
                self.tts.speak(confirm_msg)

                self.tts._done_event.wait(timeout=15)

                confirmed = wait_for_confirmation(
                    self._whisper_model, self.config, self.state_changed,
                )
                if not confirmed:
                    cancel_msg = "Azione annullata."
                    print(f"[Sicurezza] {cancel_msg}")
                    self.result_ready.emit(text, cancel_msg)
                    self.tts.speak(cancel_msg)
                    return

                print("[Sicurezza] Confermato!")

            self.detail.emit(f"Esecuzione {intent_type}...")
            result = execute_action(intent, self.config, memory=self._memory)
            self.detail.emit("")
            print(f"[Azione] {result}")
            self.result_ready.emit(text, result)

            # Aggiorna TTS live se i settings sono cambiati
            if intent_type == "self_config":
                self.tts.enabled = self.config.tts_enabled
                self.tts.voice = self.config.tts_voice

            self.tts.speak(result)

            self._memory.add_user(text)
            self._memory.add_assistant(result)
        except Exception as e:
            print(f"[Errore] {e}")
            self.result_ready.emit(text, f"Errore: {e}")
        finally:
            self._processing = False
            self._busy = False

    def _handle_copy_log(self, text: str):
        """Copia l'ultimo log del comando nella clipboard."""
        try:
            if not self._last_command_log:
                msg = "Non c'è nessun log da copiare."
                self.result_ready.emit(text, msg)
                self.tts.speak(msg)
                return

            log_text = "\n".join(self._last_command_log)
            copy_to_clipboard(log_text)
            n_lines = len(self._last_command_log)
            msg = f"Log copiato nella clipboard, {n_lines} righe."
            print(f"[CopyLog] Copiato {n_lines} righe nella clipboard")
            self.result_ready.emit(text, msg)
            self.tts.speak(msg)
        finally:
            self._processing = False
            self._busy = False

    def _on_worker_finished(self):
        print(f"[Worker] Finito. processing={self._processing}")
        if not self._processing:
            self._busy = False

    def _on_error(self, message: str):
        print(f"[Errore] {message}")
        self.state_changed.emit("idle")
        self._busy = False
        self.notify.emit(message)

    def process_text_chat(self, text: str) -> str:
        """Pipeline completa per testo dalla chat (senza voce/dettatura/conferma vocale).
        Restituisce il risultato come stringa."""
        from core.llm.brain import classify_intent, decompose_chain
        from core.actions import execute_action

        try:
            history = self._memory.get_messages()
            intent = classify_intent(text, self.config, history=history)
            intent["_original_text"] = text
            intent_type = intent.get("intent", "unknown")
            print(f"[Chat] Intent: {intent}")

            # Intent che non hanno senso da chat testuale
            if intent_type in ("dictation",):
                return "La dettatura funziona solo via voce."

            if intent_type == "type_in" and intent.get("parameter", "").strip().lower() == "dictate":
                return "La dettatura su finestra funziona solo via voce."

            # Catena di comandi
            if intent_type == "chain":
                steps = decompose_chain(text, self.config)
                if not steps:
                    return "Non sono riuscita a scomporre i comandi."

                results = []
                for i, step in enumerate(steps):
                    step_intent = step.get("intent", "unknown")
                    if step_intent == "wait":
                        secs = float(step.get("parameter", "1"))
                        _time.sleep(secs)
                        continue
                    step["_original_text"] = text
                    result = execute_action(step, self.config, memory=self._memory)
                    results.append(result)

                final = ". ".join(results)
                self._memory.add_user(text)
                self._memory.add_assistant(final)
                return final

            # Copia log
            if intent_type == "copy_log":
                if not self._last_command_log:
                    return "Non c'è nessun log da copiare."
                from core.utils.clipboard import copy_to_clipboard
                log_text = "\n".join(self._last_command_log)
                copy_to_clipboard(log_text)
                return f"Log copiato nella clipboard, {len(self._last_command_log)} righe."

            # Esecuzione azione (include chat, open_program, ecc.)
            result = execute_action(intent, self.config, memory=self._memory)
            print(f"[Chat] Risultato: {result}")

            # Aggiorna TTS se self_config
            if intent_type == "self_config":
                self.tts.enabled = self.config.tts_enabled
                self.tts.voice = self.config.tts_voice

            self._memory.add_user(text)
            self._memory.add_assistant(result)
            return result

        except Exception as e:
            print(f"[Chat] Errore: {e}")
            return f"Errore: {e}"

    def apply_config(self):
        """Applica le modifiche alla configurazione. Chiamato da SettingsPage dopo save."""
        self.tts.enabled = self.config.tts_enabled
        self.tts.voice = self.config.tts_voice
        self._memory.max_exchanges = getattr(self.config, "chat_max_history", 5)

    def update_hotkey(self):
        self._hotkey.register(self.config.hotkey)
