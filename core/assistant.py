import sys
import threading
import time as _time

import keyboard

from config import Config
from core.i18n import t, t_set, t_list
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
    countdown = Signal()      # remaining seconds (int), -1 = hide
    pick_request = Signal()   # results_with_meta, suggested_index
    pick_done = Signal()      # chiudi overlay

    def __init__(self, config: Config):
        self.config = config
        self._whisper_model = None
        self._listen_worker: ListenWorker | None = None
        self._busy = False
        self._busy_lock = threading.Lock()
        self._processing = False
        self._last_command_log: list[str] = []
        self._pick_event = threading.Event()
        self._pick_choice: int = -1
        self._last_action_ctx: dict = {}
        self._last_mode: str = ""  # "classify", "agent", "classify+agent"
        self._agent_stop = threading.Event()
        self._stdout_lock = threading.Lock()

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

        # Collega terminal watcher al TTS e notifiche
        from core.terminal_watcher import TerminalWatcher
        watcher = TerminalWatcher.instance()
        watcher.on_confirm.connect(lambda tab, line: (
            self.tts.speak(t("watcher_confirm", tab=tab)),
            self.notify.emit(f"[{tab}] {line}"),
        ))
        watcher.on_done.connect(lambda tab: (
            self.tts.speak(t("watcher_done", tab=tab)),
            self.notify.emit(t("watcher_done", tab=tab)),
        ))
        watcher.on_error.connect(lambda tab, line: (
            self.tts.speak(t("watcher_error", tab=tab)),
            self.notify.emit(f"[{tab}] {line}"),
        ))

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
            self._hotkey.register(self.config.hotkey, suppress=getattr(self.config, "hotkey_suppress", False))
            self.state_changed.emit("idle")
        else:
            self.notify.emit(message)

    def _start_listening(self):
        with self._busy_lock:
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
        elif self._processing:
            print("[Hotkey] Stop agent/processing")
            self._agent_stop.set()
            self.tts.stop()
            # Killa eventuali processi shell in corso
            from core.actions.run_command import RunCommandAction
            RunCommandAction.kill_active()
            self._processing = False
            self._busy = False
            self.state_changed.emit("idle")
            self.detail.emit("")
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
        for kw in t_set("dictation_keywords"):
            if kw in lower:
                return True, ""
        if lower in t_set("dictation_phrases"):
            return True, ""
        if any(lower.startswith(p) for p in t_list("dictation_prefixes")):
            return False, ""
        for prefix in ("scrivi ", "scrivi, ", "scrivi. "):
            if lower.startswith(prefix):
                return True, text[len(prefix):].strip()
        return False, ""

    def _check_stop(self, text: str) -> bool:
        """Controlla se è un comando di stop. Ferma TTS immediatamente."""
        import re
        lower = re.sub(r'[,\.!\?]', '', text.lower().strip())
        lower = re.sub(r'\s+', ' ', lower).strip()
        # Rimuovi "lily" dal prefisso per il matching
        clean = lower.removeprefix("lily ").strip()
        if lower in t_set("stop_words") or clean in t_set("stop_words"):
            print("[Stop] Comando stop rilevato")
            self.tts.stop()
            self.result_ready.emit(text, "")
            return True
        if lower in t_set("restart_words") or clean in t_set("restart_words"):
            print("[Restart] Comando riavvio rilevato")
            self.result_ready.emit(text, t("restarting"))
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
        t0 = _time.perf_counter()

        with self._stdout_lock:
            old_stdout = sys.stdout
            sys.stdout = _LogTee(old_stdout, capture_buf)

        try:
            self._process_inner(text, t0)
        finally:
            with self._stdout_lock:
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
            if initial_text:
                # "scrivi, blablabla" -> scrivi il testo e basta, no dettatura
                print(f"[Dettatura] Fast write: {initial_text}")
                keyboard.write(initial_text)
                play_beep()
                self.result_ready.emit("Scrivi", initial_text)
                self._processing = False
                self._busy = False
                self.state_changed.emit("idle")
                return
            print("[Dettatura] Rilevato comando dettatura (fast path)")
            self.result_ready.emit(text, t("dictation_activated"))
            play_beep()
            try:
                run_dictation(
                    self._whisper_model, self.config,
                    self.state_changed, self.result_ready, play_beep,
                    countdown=self.countdown,
                )
            finally:
                self._processing = False
                self._busy = False
            return

        # Agent mode: se abilitato, salta il classify e vai diretto all'agent
        if self.config.agent_enabled:
            self._last_mode = "agent"
            self._agent_stop.clear()
            self._run_agent_mode(text)
            return

        self._last_mode = "classify"
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

            # Classify & Agent: se il classify dice "agent" o "chain", delega all'agent loop
            if intent_type in ("agent", "chain") and self.config.classify_agent_enabled:
                self._last_mode = "classify+agent"
                self._agent_stop.clear()
                self._run_agent_mode(text)
                return

            # intent=agent senza agent attivo -> tratta come chat
            if intent_type == "agent":
                intent["intent"] = "chat"
                intent["query"] = text
                intent_type = "chat"

            # Copia ultimo log nella clipboard
            if intent_type == "copy_log":
                self._handle_copy_log(text)
                return

            # Catena di comandi
            if intent_type == "chain":
                self.detail.emit("Decomposizione comandi...")
                steps = decompose_chain(text, self.config)
                if not steps:
                    if self.config.agent_enabled:
                        self._run_agent_mode(text)
                        return
                    self.result_ready.emit(text, t("chain_decompose_fail"))
                    return

                print(f"[Chain] {len(steps)} passaggi")
                results = []
                for i, step in enumerate(steps):
                    step_intent = step.get("intent", "unknown")

                    # Wait step
                    if step_intent == "wait":
                        secs = float(step.get("parameter", "1"))
                        print(f"[Chain] Attesa {secs}s...")
                        self.detail.emit(t("chain_wait", secs=secs))
                        _time.sleep(secs)
                        continue

                    step["_original_text"] = text
                    self.detail.emit(f"Passo {i + 1}/{len(steps)}: {step_intent}")
                    print(f"[Chain] Passo {i + 1}: {step}")

                    result = execute_action(step, self.config, memory=self._memory, pick_callback=self.request_user_pick)
                    results.append(result)
                    print(f"[Chain] → {result}")

                final = ". ".join(results)
                self.detail.emit("")
                self.result_ready.emit(text, final)
                self.tts.speak(t("chain_done"))
                self._memory.add_user(text)
                self._memory.add_assistant(final)
                return

            # Dettatura classificata dall'LLM (fallback)
            if intent_type == "dictation":
                initial_text = intent.get("query", "").strip()
                self.result_ready.emit(text, t("dictation_activated"))
                play_beep()
                run_dictation(
                    self._whisper_model, self.config,
                    self.state_changed, self.result_ready, play_beep,
                    countdown=self.countdown,
                    initial_text=initial_text,
                )
                return

            # Dettatura mirata su finestra
            if intent_type == "type_in" and intent.get("parameter", "").strip().lower() == "dictate":
                target_window = intent.get("query", "")
                self.result_ready.emit(text, t("dictation_speak_prompt", target=target_window))
                play_beep()
                run_dictation_to_window(
                    self._whisper_model, self.config,
                    self.state_changed, self.result_ready, play_beep,
                    self.tts, intent,
                    countdown=self.countdown,
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
                    cancel_msg = t("action_cancelled")
                    print(f"[Sicurezza] {cancel_msg}")
                    self.result_ready.emit(text, cancel_msg)
                    self.tts.speak(cancel_msg)
                    return

                print("[Sicurezza] Confermato!")
                self._last_mode = "classify+confi"

            self.detail.emit(f"Esecuzione {intent_type}...")
            from core.llm.brain import _pick_used
            _pick_used.flag = False
            result = execute_action(intent, self.config, memory=self._memory, pick_callback=self.request_user_pick, last_action_ctx=self._last_action_ctx)
            if getattr(_pick_used, "flag", False):
                self._last_mode += "+pick"
            self.detail.emit("")
            print(f"[Azione] {result}")

            # Fallback: se l'azione fallisce e classify_agent è attivo, rilancia all'agent
            if self.config.classify_agent_enabled and result and any(
                kw in result.lower() for kw in ("non trovato", "non riuscit", "errore", "nessun risultato")
            ):
                self._last_mode = "classify+agent"
                print(f"[Fallback] Azione fallita, rilancio all'agent: {result}")
                self._agent_stop.clear()
                self._run_agent_mode(text)
                return

            self.result_ready.emit(text, result)

            # Aggiorna TTS live se i settings sono cambiati
            if intent_type == "self_config":
                self.tts.enabled = self.config.tts_enabled
                self.tts.voice = self.config.tts_voice

            self.tts.speak(result)

            self._memory.add_user(text)
            # Arricchisci la memoria con dettagli azione (path, ecc.)
            from core.actions.base import get_action_context
            ctx = get_action_context()
            if ctx:
                self._last_action_ctx = ctx
                memory_text = f"{result} [action: {ctx}]"
            else:
                memory_text = result
            self._memory.add_assistant(memory_text)
        except Exception as e:
            print(f"[Errore] {e}")
            self.result_ready.emit(text, t("error_generic", e=e))
        finally:
            self._processing = False
            self._busy = False
            self.state_changed.emit("idle")

    def _handle_copy_log(self, text: str):
        """Copia l'ultimo log del comando nella clipboard."""
        try:
            if not self._last_command_log:
                msg = t("copy_log_empty")
                self.result_ready.emit(text, msg)
                self.tts.speak(msg)
                return

            log_text = "\n".join(self._last_command_log)
            copy_to_clipboard(log_text)
            n_lines = len(self._last_command_log)
            msg = t("copy_log_done", count=n_lines)
            print(f"[CopyLog] Copiato {n_lines} righe nella clipboard")
            self.result_ready.emit(text, msg)
            self.tts.speak(msg)
        finally:
            self._processing = False
            self._busy = False
            self.state_changed.emit("idle")

    def _confirm_command(self, cmd: str) -> bool:
        """Conferma vocale per comandi shell pericolosi."""
        from core.voice.confirmation import wait_for_confirmation
        from core.i18n import t as _t

        # Mostra il comando tecnico in chat, ma parla solo un messaggio breve
        print(f"[Agent] Conferma comando: {cmd}")
        self.result_ready.emit("", f"⚠ {_t('cmd_confirm_ask', cmd=cmd)}")
        self.tts.speak(_t("cmd_confirm_short"))
        self.tts._done_event.wait(timeout=15)

        play_beep()
        return wait_for_confirmation(
            self._whisper_model, self.config, self.state_changed,
        )

    def _run_agent_mode(self, text: str):
        """Esegue la richiesta in modalita' agent loop."""
        from core.llm.agent import run_agent

        print(f"[Agent] Avvio agent mode per: {text}")
        self.detail.emit("Modalita' agente...")

        def _execute(intent_dict):
            return execute_action(
                intent_dict, self.config,
                memory=self._memory,
                pick_callback=self.request_user_pick,
                confirm_callback=self._confirm_command,
            )

        try:
            result, tool_log = run_agent(
                request=text,
                config=self.config,
                memory=self._memory,
                execute_fn=_execute,
                detail_fn=self.detail.emit,
                confirm_fn=self._confirm_command,
                stop_event=self._agent_stop,
            )
        except Exception as e:
            print(f"[Agent] Errore: {e}")
            result = t("error_generic", e=e)
            tool_log = []

        self.detail.emit("")
        print(f"[Agent] Risultato: {result}")
        self.result_ready.emit(text, result)
        self.tts.speak(result)

        self._memory.add_user(text)
        # Salva risposta + contesto tool nella memory per continuita'
        if tool_log:
            context = " | ".join(tool_log)
            self._memory.add_assistant(f"{result} [tools: {context}]")
        else:
            self._memory.add_assistant(result)

        self._processing = False
        self._busy = False
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

    def process_text_chat(self, text: str) -> str:
        """Pipeline completa per testo dalla chat (senza voce/dettatura/conferma vocale).
        Restituisce il risultato come stringa."""
        from core.llm.brain import classify_intent, decompose_chain
        from core.actions import execute_action

        try:
            # Agent mode: se abilitato, salta il classify
            if self.config.agent_enabled:
                self._last_mode = "agent"
                from core.llm.agent import run_agent
                result, tool_log = run_agent(
                    request=text, config=self.config, memory=self._memory,
                    execute_fn=lambda d: execute_action(d, self.config, memory=self._memory,
                                                        pick_callback=self.request_user_pick,
                                                        confirm_callback=self._confirm_command),
                )
                self._memory.add_user(text)
                if tool_log:
                    self._memory.add_assistant(f"{result} [tools: {' | '.join(tool_log)}]")
                else:
                    self._memory.add_assistant(result)
                return result

            self._last_mode = "classify"
            history = self._memory.get_messages()
            intent = classify_intent(text, self.config, history=history)
            intent["_original_text"] = text
            intent_type = intent.get("intent", "unknown")
            print(f"[Chat] Intent: {intent}")

            # Classify & Agent: se il classify dice "agent" o "chain", delega all'agent loop
            if intent_type in ("agent", "chain") and self.config.classify_agent_enabled:
                self._last_mode = "classify+agent"
                from core.llm.agent import run_agent
                result, tool_log = run_agent(
                    request=text, config=self.config, memory=self._memory,
                    execute_fn=lambda d: execute_action(d, self.config, memory=self._memory,
                                                        pick_callback=self.request_user_pick,
                                                        confirm_callback=self._confirm_command),
                )
                self._memory.add_user(text)
                if tool_log:
                    self._memory.add_assistant(f"{result} [tools: {' | '.join(tool_log)}]")
                else:
                    self._memory.add_assistant(result)
                return result

            # intent=agent senza agent attivo -> tratta come chat
            if intent_type == "agent":
                intent["intent"] = "chat"
                intent["query"] = text
                intent_type = "chat"

            # Intent che non hanno senso da chat testuale
            if intent_type in ("dictation",):
                return t("dictation_voice_only")

            if intent_type == "type_in" and intent.get("parameter", "").strip().lower() == "dictate":
                return t("dictation_window_voice_only")

            # Catena di comandi
            if intent_type == "chain":
                steps = decompose_chain(text, self.config)
                if not steps:
                    if self.config.agent_enabled:
                        from core.llm.agent import run_agent
                        result, tool_log = run_agent(
                            request=text, config=self.config, memory=self._memory,
                            execute_fn=lambda d: execute_action(d, self.config, memory=self._memory, pick_callback=self.request_user_pick),
                        )
                        self._memory.add_user(text)
                        if tool_log:
                            self._memory.add_assistant(f"{result} [tools: {' | '.join(tool_log)}]")
                        else:
                            self._memory.add_assistant(result)
                        return result
                    return t("chain_decompose_fail")

                results = []
                for i, step in enumerate(steps):
                    step_intent = step.get("intent", "unknown")
                    if step_intent == "wait":
                        secs = float(step.get("parameter", "1"))
                        _time.sleep(secs)
                        continue
                    step["_original_text"] = text
                    result = execute_action(step, self.config, memory=self._memory, pick_callback=self.request_user_pick)
                    results.append(result)

                final = ". ".join(results)
                self._memory.add_user(text)
                self._memory.add_assistant(final)
                return final

            # Copia log
            if intent_type == "copy_log":
                if not self._last_command_log:
                    return t("copy_log_empty")
                from core.utils.clipboard import copy_to_clipboard
                log_text = "\n".join(self._last_command_log)
                copy_to_clipboard(log_text)
                return t("copy_log_done", count=len(self._last_command_log))

            # Esecuzione azione (include chat, open_program, ecc.)
            result = execute_action(intent, self.config, memory=self._memory, pick_callback=self.request_user_pick, last_action_ctx=self._last_action_ctx)
            print(f"[Chat] Risultato: {result}")

            # Fallback: se l'azione fallisce e classify_agent è attivo, rilancia all'agent
            if self.config.classify_agent_enabled and result and any(
                kw in result.lower() for kw in ("non trovato", "non riuscit", "errore", "nessun risultato")
            ):
                self._last_mode = "classify+agent"
                print(f"[Fallback] Azione fallita, rilancio all'agent: {result}")
                from core.llm.agent import run_agent
                result, tool_log = run_agent(
                    request=text, config=self.config, memory=self._memory,
                    execute_fn=lambda d: execute_action(d, self.config, memory=self._memory,
                                                        pick_callback=self.request_user_pick,
                                                        confirm_callback=self._confirm_command),
                )
                self._memory.add_user(text)
                if tool_log:
                    self._memory.add_assistant(f"{result} [tools: {' | '.join(tool_log)}]")
                else:
                    self._memory.add_assistant(result)
                return result

            # Aggiorna TTS se self_config
            if intent_type == "self_config":
                self.tts.enabled = self.config.tts_enabled
                self.tts.voice = self.config.tts_voice

            self._memory.add_user(text)
            from core.actions.base import get_action_context
            ctx = get_action_context()
            if ctx:
                self._memory.add_assistant(f"{result} [action: {ctx}]")
            else:
                self._memory.add_assistant(result)
            return result

        except Exception as e:
            print(f"[Chat] Errore: {e}")
            return t("error_generic", e=e)

    def request_user_pick(self, results: list[str], suggested: int = 0) -> int:
        """Mostra l'overlay con i risultati e aspetta la scelta dell'utente.
        Ritorna l'indice scelto o -1 se annullato/timeout."""
        from core.search import get_path_metadata
        results_with_meta = [(r, get_path_metadata(r)) for r in results]

        self._pick_event.clear()
        self._pick_choice = -1
        self.detail.emit("Quale intendevi?")
        self.tts.speak(t("pick_ask", count=len(results)))
        self.pick_request.emit(results_with_meta, suggested)

        # Ascolta voce in parallelo (si ferma quando pick_event è settato)
        n_results = len(results)
        threading.Thread(
            target=self._listen_for_pick, args=(n_results,), daemon=True
        ).start()

        # Aspetta la scelta (max 30 secondi) — click o voce
        picked = self._pick_event.wait(timeout=30)
        self.detail.emit("")
        self.pick_done.emit()  # Chiudi overlay

        if not picked or self._pick_choice == -1:
            self.tts.speak(t("pick_timeout"))
            return -1

        if self._pick_choice == -2:
            self.tts.speak(t("pick_cancelled"))
            return -2

        return self._pick_choice

    def _listen_for_pick(self, n_results: int):
        """Ascolta la voce dell'utente per scegliere un risultato tramite ordinale."""
        from core.utils.audio import record_until_silence, SAMPLE_RATE
        from core.voice.transcriber import transcribe

        try:
            # Aspetta che il TTS finisca prima di ascoltare
            print("[Pick] Aspetto fine TTS...")
            self.tts._done_event.wait(timeout=10)
            _time.sleep(0.5)

            if self._pick_event.is_set():
                return

            print("[Pick] Inizio ascolto vocale...")
            self.state_changed.emit("listening")
            play_beep()  # Beep per segnalare che sta ascoltando
            device = self.config.mic_device if self.config.mic_device is not None else None
            audio = record_until_silence(
                device=device, timeout=20,
                silence_duration=1.5,
                speech_threshold=0.008,
            )

            if self._pick_event.is_set():
                return

            if audio is None:
                print("[Pick] Nessun audio rilevato")
                self.state_changed.emit("idle")
                return

            duration = len(audio) / SAMPLE_RATE
            print(f"[Pick] Audio ricevuto: {duration:.1f}s")

            if duration < 0.3:
                print("[Pick] Audio troppo corto")
                self.state_changed.emit("idle")
                return

            self.state_changed.emit("transcribing")
            response = transcribe(self._whisper_model, audio, self.config.whisper_model)
            print(f"[Pick] Trascrizione: '{response}'")

            if self._pick_event.is_set():
                return

            if not response or not response.strip():
                print("[Pick] Trascrizione vuota")
                self.state_changed.emit("idle")
                return

            idx = self._parse_ordinal(response, n_results)
            if idx == -2:
                print(f"[Pick] Annullato via voce: '{response}'")
                self._pick_choice = -2
                self._pick_event.set()
            elif idx is not None:
                print(f"[Pick] Scelto via voce: indice {idx}")
                self._pick_choice = idx
                self._pick_event.set()
            else:
                print(f"[Pick] Non ho capito la scelta da: '{response}'")
                self.tts.speak(t("pick_not_understood"))
        except Exception as e:
            print(f"[Pick] Errore ascolto: {e}")
        finally:
            self.state_changed.emit("idle")

    @staticmethod
    def _parse_ordinal(text: str, max_n: int) -> int | None:
        """Parsa ordinali italiani/inglesi e numeri dal testo. Ritorna indice 0-based o None."""
        import re
        text = text.lower().strip().rstrip(".")

        # Annullamento — controllare PRIMA dei cardinali ("nessuno" contiene "uno")
        cancel_words = {"annulla", "nessuno", "niente", "cancel", "none", "skip", "lascia", "no"}
        if any(re.search(rf'\b{w}\b', text) for w in cancel_words):
            return -2

        # Ordinali italiani/inglesi
        ordinals = {
            "primo": 1, "prima": 1, "secondo": 2, "seconda": 2,
            "terzo": 3, "terza": 3, "quarto": 4, "quarta": 4,
            "quinto": 5, "quinta": 5, "sesto": 6, "sesta": 6,
            "settimo": 7, "settima": 7, "ottavo": 8, "ottava": 8,
            "nono": 9, "nona": 9, "decimo": 10, "decima": 10,
            "first": 1, "second": 2, "third": 3, "fourth": 4,
            "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
            "ninth": 9, "tenth": 10,
        }
        for word, num in ordinals.items():
            if re.search(rf'\b{word}\b', text) and num <= max_n:
                return num - 1

        # Cardinali italiani/inglesi
        cardinals = {
            "uno": 1, "due": 2, "tre": 3, "quattro": 4, "cinque": 5,
            "sei": 6, "sette": 7, "otto": 8, "nove": 9, "dieci": 10,
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }
        for word, num in cardinals.items():
            if re.search(rf'\b{word}\b', text) and num <= max_n:
                return num - 1

        # Numero diretto: "3", "il 5"
        match = re.search(r'\b(\d+)\b', text)
        if match:
            num = int(match.group(1))
            if 1 <= num <= max_n:
                return num - 1

        return None

    def on_pick_choice(self, index: int):
        """Callback dalla UI quando l'utente sceglie un risultato."""
        self._pick_choice = index
        self._pick_event.set()

    def apply_config(self):
        """Applica le modifiche alla configurazione. Chiamato da SettingsPage dopo save."""
        self.tts.enabled = self.config.tts_enabled
        self.tts.voice = self.config.tts_voice
        self._memory.max_exchanges = getattr(self.config, "chat_max_history", 5)

    def update_hotkey(self):
        self._hotkey.register(self.config.hotkey, suppress=getattr(self.config, "hotkey_suppress", False))
