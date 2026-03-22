REPORT ARCHITETTURALE — Lily Voice Assistant

  Data: 2026-03-22
  Stato attuale del codebase: ~3.400 righe Python, 34 file

  ---
  1. GOD-CLASSES

  1.1 core/assistant.py — 652 righe, classe Assistant (CRITICO)

  10 responsabilità distinte in una classe:

  ┌───────────────────────┬─────────────┬─────────────────────────────────────────────────┐
  │    Responsabilità     │    Righe    │                    Dettaglio                    │
  ├───────────────────────┼─────────────┼─────────────────────────────────────────────────┤
  │                       │ 46-48,      │                                                 │
  │ Hotkey management     │ 64-84,      │ Register/listen/update hotkey                   │
  │                       │ 650-652     │                                                 │
  ├───────────────────────┼─────────────┼─────────────────────────────────────────────────┤
  │ Whisper model loading │ 50-62       │ Background loader + callback                    │
  ├───────────────────────┼─────────────┼─────────────────────────────────────────────────┤
  │ Audio recording       │ 64-84       │ Start/stop ListenWorker                         │
  │ coordination          │             │                                                 │
  ├───────────────────────┼─────────────┼─────────────────────────────────────────────────┤
  │ Intent classification │ 114-198     │ _process() — pipeline principale                │
  │  orchestration        │             │                                                 │
  ├───────────────────────┼─────────────┼─────────────────────────────────────────────────┤
  │ Conferma vocale       │ 238-375     │ _wait_for_confirmation() + _llm_confirm() —     │
  │ azioni pericolose     │             │ apre mic, registra, trascrive, interroga LLM    │
  ├───────────────────────┼─────────────┼─────────────────────────────────────────────────┤
  │ Dettatura a segmenti  │ 377-498     │ _run_dictation() — loop audio con VAD,          │
  │                       │             │ trascrive, digita via keyboard                  │
  ├───────────────────────┼─────────────┼─────────────────────────────────────────────────┤
  │ Dettatura verso       │ 500-637     │ _run_dictation_to_window() — registra tutto,    │
  │ finestra              │             │ trascrive, incolla+invio su finestra target     │
  ├───────────────────────┼─────────────┼─────────────────────────────────────────────────┤
  │ Beep sonoro           │ 200-224     │ _play_beep() — genera onda sinusoidale con      │
  │                       │             │ numpy/pygame                                    │
  ├───────────────────────┼─────────────┼─────────────────────────────────────────────────┤
  │ TTS management        │ 43          │ Crea e gestisce TTSEngine                       │
  ├───────────────────────┼─────────────┼─────────────────────────────────────────────────┤
  │ Conversation memory   │ 37-40,      │ Gestisce ConversationMemory                     │
  │                       │ 190-192     │                                                 │
  └───────────────────────┴─────────────┴─────────────────────────────────────────────────┘

  Problemi specifici:
  - _wait_for_confirmation() (righe 238-335): 98 righe che aprono un InputStream, fanno VAD
  con energy detection, registrano, trascrivono, e interpretano — è un mini-pipeline completo
  dentro un metodo
  - _run_dictation() (righe 377-498): 122 righe — un'altra pipeline audio indipendente con
  loop a 3 fasi
  - _run_dictation_to_window() (righe 500-637): 138 righe — duplica la logica audio di
  _wait_for_confirmation(), poi importa direttamente da type_action.py (riga 593: from
  core.actions.type_action import _find_window, _clipboard_paste)
  - Import interni a runtime: import numpy, import sounddevice, import pygame, import
  keyboard, import ctypes — tutti importati dentro i metodi

  Refactor proposto — spezzare in 3 moduli:

  core/assistant.py          (~200 righe) — Coordinatore: hotkey, pipeline, memory
  core/voice/confirmation.py (~140 righe) — ConfirmationManager: mic → VAD → trascr → LLM
  core/voice/dictation.py    (~180 righe) — DictationEngine: dettatura segmenti +
  dettatura-a-finestra

  ---
  1.2 core/llm/brain.py — 378 righe (ALTO)

  4 responsabilità distinte:

  ┌────────────────────┬─────────┬────────────────────────────────────────────────────────┐
  │   Responsabilità   │  Righe  │                       Dettaglio                        │
  ├────────────────────┼─────────┼────────────────────────────────────────────────────────┤
  │ Prompt templates   │         │ SYSTEM_PROMPT_OLLAMA (105 righe),                      │
  │ (6 costanti)       │ 6-192   │ SYSTEM_PROMPT_CLAUDE, PICK_PROMPT_OLLAMA,              │
  │                    │         │ PICK_PROMPT_CLAUDE, RETRY_PROMPT, CHAT_SYSTEM_PROMPT   │
  ├────────────────────┼─────────┼────────────────────────────────────────────────────────┤
  │ Intent             │ 223-260 │ classify_intent()                                      │
  │ classification     │         │                                                        │
  ├────────────────────┼─────────┼────────────────────────────────────────────────────────┤
  │ Chat response      │ 263-291 │ generate_chat_response()                               │
  ├────────────────────┼─────────┼────────────────────────────────────────────────────────┤
  │ Result picking +   │ 294-377 │ pick_best_result(), suggest_retry_terms()              │
  │ retry              │         │                                                        │
  └────────────────────┴─────────┴────────────────────────────────────────────────────────┘

  Problemi specifici:
  - I prompt occupano 192/378 righe (51% del file) — sono dati, non logica
  - 4 funzioni utility private (_strip_think_tags, _parse_json, _get_prompts, _apply_thinking)
   usate anche da altri file via import diretto (es. screen_read.py riga 195: from
  core.llm.brain import _strip_think_tags, CHAT_SYSTEM_PROMPT, _apply_thinking)
  - _parse_json() (righe 204-212) trova solo il PRIMO } — fallisce con JSON annidati ({"pick":
   -1} ok, ma {"data": {"x": 1}} tronca)

  Refactor proposto:

  core/llm/prompts.py  (~200 righe) — Tutte le costanti prompt
  core/llm/brain.py    (~120 righe) — classify_intent(), generate_chat_response()
  core/llm/picker.py   (~60 righe)  — pick_best_result(), suggest_retry_terms()

  ---
  2. CODICE DUPLICATO

  2.1 _find_window() — 3 implementazioni diverse

  ┌──────────────────┬───────┬────────────────────────────┬─────────────┬─────────────────┐
  │       File       │ Riga  │           Firma            │  Include    │     Cerca       │
  │                  │       │                            │ minimized?  │ sottostringhe?  │
  ├──────────────────┼───────┼────────────────────────────┼─────────────┼─────────────────┤
  │                  │       │ _find_window(query,        │             │                 │
  │ window_action.py │ 66-86 │ include_minimized,         │ Parametro   │ Sì              │
  │                  │       │ search_terms) → dict|None  │             │                 │
  ├──────────────────┼───────┼────────────────────────────┼─────────────┼─────────────────┤
  │ type_action.py   │ 15-36 │ _find_window(query) →      │ Sì          │ No              │
  │                  │       │ int|None                   │ (IsIconic)  │                 │
  ├──────────────────┼───────┼────────────────────────────┼─────────────┼─────────────────┤
  │ screen_read.py   │ 20-52 │ _find_window(query,        │ No (solo    │ Sì              │
  │                  │       │ search_terms) → int|None   │ visible)    │                 │
  └──────────────────┴───────┴────────────────────────────┴─────────────┴─────────────────┘

  Le 3 versioni hanno API diverse e comportamenti diversi. Tutte usano lo stesso pattern
  EnumWindows + callback + ctypes.

  Refactor proposto:

  Creare core/utils/win32.py con una sola implementazione:

  def find_window(query: str, search_terms: list[str] = None,
                  include_minimized: bool = False) -> dict | None:
      """Trova finestra per titolo. Ritorna {"hwnd": int, "title": str, ...} o None."""

  Usata da window_action.py, type_action.py, screen_read.py, e assistant.py (riga 608-611).

  ---
  2.2 Pattern audio duplicato

  _wait_for_confirmation() (assistant.py:238-335) e _run_dictation_to_window()
  (assistant.py:500-637) condividono la stessa struttura:

  1. Apri InputStream(samplerate=16000, channels=1, blocksize=1600)
  2. Loop: raccogli chunk da queue, calcola energy
  3. Rileva speech/silence con threshold
  4. Stop su silence_duration o timeout
  5. Concatena chunks, trascrivi con Whisper

  Potrebbe essere estratto in una utility record_until_silence() in core/voice/.

  ---
  3. PROBLEMI DI STABILITÀ

  3.1 config.py — Nessun thread-safety (CRITICO)

  File: config.py:28-57

  Config._data è un dict Python accessibile da 6+ thread senza lock:
  - UI thread: SettingsPage._save() scrive su _data (righe 340-358) e chiama config.save()
  (riga 358)
  - Worker thread: Assistant._process() legge self.config.provider, self.config.ollama_model,
  ecc. (righe 130-131)
  - Confirmation thread: _wait_for_confirmation() legge self.config.mic_device (riga 248)
  - Dictation thread: _run_dictation() legge config (riga 386-389)
  - Background thread: SettingsPage._check_ollama_status() (riga 275)
  - Background thread: DashboardPage._check_services() (riga 205)

  Race condition: se SettingsPage salva mentre Assistant legge, possibile KeyError o dati
  inconsistenti.

  Fix: Aggiungere threading.RLock() a Config con lock su __getattr__, __setattr__, save(),
  load().

  ---
  3.2 config.py — Nessun error handling su load (MEDIO)

  File: config.py:33-36

  def load(self):
      if os.path.exists(SETTINGS_FILE):
          with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
              self._data = json.load(f)  # ← JSONDecodeError se corrotto

  Se settings.json è corrotto, json.load() lancia JSONDecodeError e l'app crasha all'avvio.

  Fix: wrap in try/except, fallback a DEFAULTS.

  ---
  3.3 StateIndicator — Timer 60 FPS mai fermato (ALTO)

  File: ui/widgets/state_indicator.py:52-55

  self._timer = QTimer(self)
  self._timer.timeout.connect(self.update)
  self._timer.start(16)  # ~60 fps

  Il timer gira SEMPRE, anche quando il widget è nascosto (es. l'utente è sulla pagina
  Settings). Spreca CPU e batteria.

  Fix: Fermare in hideEvent(), ripartire in showEvent(). Oppure self.update() nei property
  setter e rimuovere il timer.

  ---
  3.4 DashboardPage — Timer mai fermato + accesso privato (ALTO)

  File: ui/pages/dashboard_page.py:164-166

  self._timer = QTimer(self)
  self._timer.timeout.connect(self.refresh)
  self._timer.start(5000)

  Gira ogni 5 secondi per tutta la vita dell'app, anche quando il Dashboard non è visibile.

  File: ui/pages/dashboard_page.py:177

  sessions = t._data.get("sessions", [])

  Accede direttamente al membro privato _data di TokenTracker senza lock. TokenTracker.track()
   potrebbe star scrivendo _data da un altro thread nello stesso momento.

  Fix:
  1. Fermare timer quando non visibile
  2. Aggiungere a TokenTracker un getter pubblico:
  @property
  def sessions(self) -> list[dict]:
      return list(self._data.get("sessions", []))

  ---
  3.5 SettingsPage — Accoppiamento diretto a Assistant (MEDIO)

  File: ui/pages/settings_page.py:361-368

  self._assistant.tts.enabled = self._config.tts_enabled
  self._assistant.tts.voice = self._config.tts_voice
  self._assistant._memory.max_exchanges = self._config.chat_max_history
  if self._config.hotkey != old_hotkey:
      self._assistant.update_hotkey()

  La UI accede direttamente a assistant.tts, assistant._memory (membro privato!), e chiama
  assistant.update_hotkey(). Questo crea tight coupling UI→Core.

  Fix: L'Assistant dovrebbe esporre un metodo apply_config() che aggiorna tutto internamente,
  oppure usare segnali.

  ---
  3.6 Thread daemon senza timeout (MEDIO)

  File: ui/pages/settings_page.py:272-280, 290-302

  def _check():
      from core.llm.ollama_provider import OllamaProvider
      ok = OllamaProvider().check()  # ← timeout 3s (ok)

  Il check Ollama ha timeout 3s (ok). Ma se il widget viene distrutto prima che il thread
  finisca, il segnale _ollama_status_ready.emit() va a un oggetto morto → possibile crash.

  ---
  3.7 _parse_json non gestisce JSON annidati (BASSO)

  File: core/llm/brain.py:204-212

  def _parse_json(text: str) -> dict | None:
      start = text.find("{")
      end = text.find("}", start)  # ← trova il PRIMO }, non l'ultimo matching

  Con input {"data": {"x": 1}}, end punta al primo } e il parse fallisce. Per ora non è un
  problema perché tutti i JSON attesi sono flat, ma è fragile.

  ---
  4. PROBLEMI DI PERFORMANCE

  4.1 Import pesanti a runtime

  File: core/assistant.py

  Ogni chiamata a _play_beep(), _wait_for_confirmation(), _run_dictation(),
  _run_dictation_to_window() fa import numpy, import sounddevice, import pygame, import
  keyboard a runtime. Sono import veloci dopo il primo (cached), ma è un pattern inusuale che
  rende il codice meno leggibile.

  Suggerimento: Spostare gli import a livello di modulo nei file estratti
  (ConfirmationManager, DictationEngine).

  4.2 LogPage._filter() — O(n) full re-render

  File: ui/pages/log_page.py (non letto ma confermato dall'analisi precedente)

  Ogni keystroke nella search bar cancella tutto il testo e ri-appende tutte le righe
  filtrate. Con 5000 righe è lento.

  ---
  5. MAPPA DIPENDENZE

  main.py → ui/app.py
    ├── config.py (Config)
    ├── core/assistant.py (Assistant)
    │   ├── core/voice/hotkey.py (HotkeyManager)
    │   ├── core/voice/listener.py (ListenWorker)
    │   ├── core/voice/transcriber.py (WhisperLoader, transcribe)
    │   ├── core/voice/tts.py (TTSEngine)
    │   ├── core/llm/brain.py (classify_intent)
    │   ├── core/llm/conversation.py (ConversationMemory)
    │   ├── core/actions/__init__.py (execute_action)
    │   │   ├── core/actions/program.py → core/search.py, core/llm/brain.py
    │   │   ├── core/actions/folder.py → core/search.py, core/llm/brain.py
    │   │   ├── core/actions/type_action.py [_find_window DUPLICATA]
    │   │   ├── core/actions/window_action.py [_find_window DUPLICATA]
    │   │   ├── core/actions/screen_read.py [_find_window DUPLICATA] → core/llm/brain.py
    │   │   ├── core/actions/close_program.py → core/llm/brain.py
    │   │   └── ... (altri actions senza dipendenze complesse)
    │   └── [runtime] core/actions/type_action.py (_find_window, _clipboard_paste) ← riga 593
    ├── ui/bridge.py (SignalBridge)
    ├── ui/main_window.py (MainWindow)
    │   ├── ui/pages/voice_page.py
    │   ├── ui/pages/settings_page.py → assistant.tts, assistant._memory [ACCOPPIAMENTO]
    │   ├── ui/pages/dashboard_page.py → TokenTracker._data [ACCESSO PRIVATO]
    │   └── ui/pages/log_page.py
    └── ui/tray.py (TrayManager)

  ---
  6. PIANO DI REFACTORING RACCOMANDATO

  Fase 1 — Stabilità (non cambia architettura, zero rischio di regression)

  ┌─────────────────────────────┬─────────────────────────────────┬──────────────────────┐
  │            Task             │              File               │       Impatto        │
  ├─────────────────────────────┼─────────────────────────────────┼──────────────────────┤
  │ Aggiungere RLock a Config   │ config.py                       │ Previene race        │
  │                             │                                 │ condition            │
  ├─────────────────────────────┼─────────────────────────────────┼──────────────────────┤
  │ Try/except su Config.load() │ config.py:33-36                 │ Previene crash su    │
  │                             │                                 │ JSON corrotto        │
  ├─────────────────────────────┼─────────────────────────────────┼──────────────────────┤
  │ Fermare timer su hide       │ state_indicator.py,             │ Riduce CPU           │
  │                             │ dashboard_page.py               │                      │
  ├─────────────────────────────┼─────────────────────────────────┼──────────────────────┤
  │ Getter pubblico sessions su │ token_tracker.py                │ Elimina accesso      │
  │  TokenTracker               │                                 │ privato              │
  ├─────────────────────────────┼─────────────────────────────────┼──────────────────────┤
  │ Usare getter in             │ dashboard_page.py:177,189       │ Thread safety        │
  │ DashboardPage               │                                 │                      │
  └─────────────────────────────┴─────────────────────────────────┴──────────────────────┘

  Fase 2 — Eliminare duplicazioni (rischio basso)

  ┌────────────────────────────────────────────────────┬─────────┬───────────────────────┐
  │                        Task                        │  File   │        Impatto        │
  ├────────────────────────────────────────────────────┼─────────┼───────────────────────┤
  │ Creare core/utils/win32.py con find_window()       │ nuovo   │ Elimina 3x            │
  │ unificata                                          │ file    │ _find_window          │
  ├────────────────────────────────────────────────────┼─────────┼───────────────────────┤
  │ Aggiornare window_action.py, type_action.py,       │ 4 file  │ Import da             │
  │ screen_read.py, assistant.py                       │         │ core/utils/win32      │
  └────────────────────────────────────────────────────┴─────────┴───────────────────────┘

  Fase 3 — Spezzare god-classes (rischio medio, alta resa)

  ┌───────────────────────────┬──────────────────────────────────────┬────────────────────┐
  │           Task            │            File da/verso             │      Impatto       │
  ├───────────────────────────┼──────────────────────────────────────┼────────────────────┤
  │ Estrarre                  │ assistant.py →                       │ -140 righe da      │
  │ ConfirmationManager       │ core/voice/confirmation.py           │ assistant          │
  ├───────────────────────────┼──────────────────────────────────────┼────────────────────┤
  │ Estrarre DictationEngine  │ assistant.py →                       │ -180 righe da      │
  │                           │ core/voice/dictation.py              │ assistant          │
  ├───────────────────────────┼──────────────────────────────────────┼────────────────────┤
  │ Estrarre prompt in        │ brain.py → core/llm/prompts.py       │ -192 righe da      │
  │ prompts.py                │                                      │ brain              │
  ├───────────────────────────┼──────────────────────────────────────┼────────────────────┤
  │ Estrarre picker.py        │ brain.py → core/llm/picker.py        │ -80 righe da brain │
  └───────────────────────────┴──────────────────────────────────────┴────────────────────┘

  Fase 4 — Disaccoppiamento UI↔Core (rischio medio)

  ┌─────────────────────────────────────┬────────────────────────┬───────────────────────┐
  │                Task                 │          File          │        Impatto        │
  ├─────────────────────────────────────┼────────────────────────┼───────────────────────┤
  │ Assistant.apply_config() metodo     │ assistant.py,          │ Elimina accoppiamento │
  │                                     │ settings_page.py       │  diretto              │
  ├─────────────────────────────────────┼────────────────────────┼───────────────────────┤
  │ Rendere _strip_think_tags,          │ brain.py               │ API pulita per        │
  │ _parse_json pubbliche               │                        │ screen_read.py        │
  └─────────────────────────────────────┴────────────────────────┴───────────────────────┘

  ---
  7. FILE PER FILE — STATO ATTUALE

  ┌───────────────────────────────┬───────┬─────────────┬─────────────────────────────────┐
  │             File              │ Righe │    Stato    │              Note               │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ core/assistant.py             │ 652   │ GOD-CLASS   │ 10 responsabilità, da spezzare  │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ core/llm/brain.py             │ 378   │ TROPPO      │ 51% prompt, da separare         │
  │                               │       │ GRANDE      │                                 │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ core/actions/window_action.py │ 295   │ OK-ish      │ Tante sub-ops ma coerenti       │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ ui/pages/settings_page.py     │ 373   │ TROPPO      │ Form gigante + accoppiamento    │
  │                               │       │ GRANDE      │                                 │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ core/actions/screen_read.py   │ 224   │ OK          │ _find_window duplicata          │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ ui/pages/dashboard_page.py    │ 221   │ MEDIO       │ Timer leak + accesso _data      │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ ui/style.py                   │ 206   │ OK          │ Stylesheet lungo ma coerente    │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ core/search.py                │ 188   │ OK          │ Funzioni pure, ben strutturato  │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ core/actions/type_action.py   │ 173   │ MEDIO       │ _find_window duplicata          │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ core/voice/tts.py             │ 154   │ OK          │ Responsabilità singola          │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ ui/main_window.py             │ 151   │ OK          │ Clean                           │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ ui/widgets/state_indicator.py │ 147   │ MEDIO       │ Timer 60fps leak                │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ core/actions/close_program.py │ 127   │ OK          │ —                               │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ core/voice/listener.py        │ 101   │ OK          │ —                               │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ core/llm/token_tracker.py     │ 97    │ MEDIO       │ Nessun lock, _data              │
  │                               │       │             │ pubblicamente usato             │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ core/voice/transcriber.py     │ 90    │ OK          │ —                               │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ core/voice/hotkey.py          │ 83    │ OK          │ —                               │
  ├───────────────────────────────┼───────┼─────────────┼─────────────────────────────────┤
  │ config.py                     │ 61    │ INSTABILE   │ No thread-safety, no error      │
  │                               │       │             │ handling                        │
  └───────────────────────────────┴───────┴─────────────┴─────────────────────────────────┘