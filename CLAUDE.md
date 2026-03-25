# Lily - Assistente Vocale

## Regole generali

- Ogni volta che finisci un messaggio o una task, scrivi `LILY_DONE` alla fine.

## TODO — Bug e criticita

### Sicurezza

- [x] **Command injection in `run_command.py`** — `_is_safe_command()` aggirabile: `get-date; rm -rf C:\Users` passa perche `startsWith("get-")` e true, e i pattern bloccati usano path Unix (`/`) non Windows (`C:\`). In agent mode il LLM genera la query, rischio concreto. Fix: splittare il comando su `;`, `&&`, `||`, `|` e validare ogni segmento indipendentemente. Aggiungere pattern Windows ai blocchi (`del`, `rmdir`, `format`, path con `C:\`).

- [x] **PowerShell injection in `program.py`** — `_try_launch_uwp()` inietta `query` direttamente nella stringa PowerShell senza escaping. In agent mode il LLM costruisce la query e puo iniettare codice arbitrario (`*" }}; Start-Process calc.exe; $x = "`). Fix: usare `-replace` o passare il parametro via variabile d'ambiente / argomento separato.

### Crash e corruzione dati

- [x] **Conferma vocale rotta con provider cloud** — `confirmation.py:87` hardcoda `config.ollama_model` nella chiamata `provider.chat()`. Se il provider attivo e Anthropic/OpenAI/Gemini, passa un nome modello Ollama all'API cloud → HTTP 400 → conferma fallisce silenziosamente → azione sempre annullata senza spiegazione. Fix: usare `_get_model(config)` dal brain.

- [x] **GDI handle leak in `screenshot.py`** — `capture_window()` acquisisce 3 handle GDI (`GetWindowDC`, `CreateCompatibleDC`, `CreateCompatibleBitmap`) rilasciate solo a fine funzione. Se `PrintWindow`/`GetDIBits`/`QImage` lanciano eccezione, il blocco `except` ritorna `None` senza rilasciarle. Con `screen_read` frequenti si esaurisce il quota GDI (10.000/processo) → glitch grafici o crash. Fix: try/finally che rilascia tutte le handle acquisite.

- [x] **Clipboard bloccato system-wide** — `clipboard.py` path ctypes: `OpenClipboard(0)` seguito da operazioni senza try/finally. Se `GlobalAlloc`/`GlobalLock`/`wcscpy_s` lancia eccezione, `CloseClipboard()` non viene mai chiamato. Windows permette un solo processo alla volta sul clipboard → resta bloccato system-wide fino al kill del processo. Fix: wrappare tutto in try/finally con `CloseClipboard()`.

- [ ] **QThread segfault in `chat_page.py`** — `_ChatWorker` (QThread): il riferimento Python viene droppato (`self._worker = None`) in `_on_chat_response` mentre il thread C++ potrebbe ancora essere attivo. PySide6 puo fare segfault se il wrapper Python viene garbage-collected prima che il QThread C++ finisca il cleanup. Fix: chiamare `self._worker.wait()` prima di droppare il riferimento, o usare `deleteLater()`.

- [ ] **TOCTOU in `memory.py` e `notes.py`** — `add_memory_entry()` fa `load()` (con lock), rilascia, poi `save()` (con lock). Due thread concorrenti leggono lo stesso vecchio contenuto → uno sovrascrive l'aggiunta dell'altro, perdendo un entry. Stessa race di `config.py` (gia nota) ma qui non documentata. Fix: singolo lock che copre load+modifica+save, oppure scrittura atomica con `.tmp` + `os.replace()`.

- [ ] **`LogCapture` incompleto** — `log_capture.py`: mancano `__getattr__`, `fileno()`, `isatty()`, `encoding`, `errors`. Librerie che interrogano `sys.stderr` (sounddevice, faster-whisper, pygame) crashano con `AttributeError`. Fix: aggiungere `__getattr__` che delega all'oggetto originale, come gia fatto in `_LogTee`.

### Race condition

- [ ] **`_busy` bool senza lock in `assistant.py`** — `_start_listening()`: il check `if self._busy` e l'assegnazione `self._busy = True` sono due operazioni separate nel callback hotkey. Key bounce → due pipeline parallele → due risposte TTS sovrapposte. Fix: usare `threading.Lock` o `threading.Event` per `_busy`.

- [ ] **`sys.stdout` swap non thread-safe** — `assistant.py:_process()`: sostituisce `sys.stdout` con `_LogTee` in un daemon thread. Se voce e chat sono attivi simultaneamente, due thread swappano `sys.stdout` concorrentemente → log persi o corrotti. Fix: usare un lock dedicato per lo swap, o passare il tee come argomento invece di modificare lo stato globale.

- [ ] **`_last_context` globale non protetto** — `core/actions/base.py`: dict globale condiviso tra thread. `clear()` + `update()` non sono atomici. Due comandi in rapida successione possono lasciare il dict in stato parziale. Fix: aggiungere `threading.Lock`.

- [x] **`_active_proc` registrato dopo lo spawn** — `run_command.py`: il processo viene creato con `Popen()`, poi registrato in `_active_proc` sotto lock. Se `kill_active()` viene chiamato tra spawn e registrazione, il processo non viene terminato e gira fino al timeout (30s). Fix: lock acquisito prima di `Popen()`.

- [ ] **Singleton `_TimerNotifier` non thread-safe** — `timer_action.py`: classic check-then-act su `_instance is None`. Due timer che scadono simultaneamente possono creare due istanze → notifiche perse. Fix: usare un `threading.Lock` nel classmethod `instance()`.

- [ ] **`TokenTracker._load()` senza lock** — `token_tracker.py`: `_load()` chiamata dal `__new__` senza `self._lock`. Se due thread chiamano `TokenTracker()` simultaneamente, entrambi entrano in `__new__`, passano il check `_instance is None`, e scrivono su `self._data` concorrentemente. Fix: lock nel `__new__` o usare un module-level lock per la costruzione del singleton.

### Deadlock

- [ ] **`Signal._lock` non rientrante** — `signal.py`: usa `threading.Lock` (non `RLock`). Se un callback chiamato da `emit()` invoca `disconnect()` sullo stesso segnale → deadlock. Fix: usare `RLock`, oppure deferire le disconnect a dopo l'iterazione.

- [ ] **Stop durante conferma vocale** — `assistant.py`: `_stop_listening` resetta `_busy=False` mentre `wait_for_confirmation` e ancora bloccato su `record_until_silence` (timeout 7s). L'hotkey successivo apre un secondo stream audio → conflitto driver audio o silenzio. Dopo il timeout la vecchia pipeline continua con `confirmed=False`. Fix: segnalare a `wait_for_confirmation` di abortire (via Event), e non resettare `_busy` finche il thread non e effettivamente terminato.

---

## TODO — Migliorie codebase

### Medi (qualita / UX)

- [ ] **System prompt troppo lungo** — `prompts.py`: 124 righe con esempi ridondanti. Ogni `classify_intent` consuma ~300 token solo di prompt. Condensare gli esempi, auto-generare la lista intent dal registry delle azioni.

- [ ] **search_terms non normalizzati** — `brain.py`: il LLM puo restituire termini duplicati con case diverso. Fix: `terms = list({t.strip().lower() for t in terms})`.

- [ ] **Nessuna cache sui risultati di ricerca** — `search.py`: "apri Chrome" due volte → ricerca Everything rifatta da zero. Fix: `functools.lru_cache` con TTL 30s.

- [ ] **pick_best_result sempre via LLM** — `brain.py`: anche con match quasi perfetto (query "Chrome", risultato `chrome.exe`), chiama il LLM. Fix: fuzzy match locale (`difflib.SequenceMatcher`) per casi ovvi, LLM solo per ambigui.

- [ ] **Config non atomica** — `config.py`: crash durante `json.dump()` → file vuoto/corrotto. Fix: scrivere su `.tmp` + `os.replace()`.

- [ ] **Log page accumula tutto in memoria** — `log_page.py`: lista `_lines` cresce senza limiti. Fix: cap a ~5000 righe.

- [ ] **Dashboard refresh eccessivo** — `dashboard_page.py`: si aggiorna ogni 3s anche senza cambiamenti. Fix: aggiornare solo su segnale dal core.

- [ ] **print() ovunque invece di logging** — tutto il codebase. Fix: `logging.getLogger(__name__)` con livelli.

- [ ] **CUDA DLL path manipulation ripetuta** — `transcriber.py`: aggiunge directory CUDA al PATH e chiama `os.add_dll_directory()` ad ogni reload. Fix: farlo una sola volta all'avvio.

- [ ] **screen_read usa sempre il modello Ollama** — `screen_read.py`: hardcoda `config.ollama_model` anche se il provider attivo e un altro. Fix: usare il provider e modello configurati.

### Architetturali (refactor futuro)

- [ ] **State machine esplicita** — `assistant.py`: stato tracciato con due bool (`_busy`, `_processing`). Fix: Enum esplicito (IDLE → RECORDING → PROCESSING → EXECUTING → IDLE).

- [ ] **Auto-discovery delle azioni** — `core/actions/__init__.py`: aggiungere azione richiede 3 passi manuali. Fix: decoratore `@register_action("program")`.

- [ ] **Sync automatica prompt-azioni** — `prompts.py`: lista intent scritta a mano, puo andare fuori sync. Fix: generarla dal registry.

- [ ] **ThreadPoolExecutor** — tutto il codebase: daemon thread singoli che perdono eccezioni. Fix: `ThreadPoolExecutor` con `future.result()`.

- [ ] **TTS asyncio persistente** — `tts.py`: crea/distrugge event loop ad ogni `speak()`. Fix: loop persistente su thread dedicato.

- [ ] **Escaping query PowerShell** — `program.py`: query inserita senza escaping nella stringa PowerShell. Fix: sanitizzare input.
