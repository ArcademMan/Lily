# Lily - Assistente Vocale

## Regole generali

- Ogni volta che finisci un messaggio o una task, scrivi `LILY_DONE` alla fine.

## TODO — Bug e criticita

### Crash e corruzione dati

- [x] ~~**`run_agent` tuple unpacking errato in `assistant.py`**~~ — fixato: `result, tool_log = run_agent(...)`.

- [x] ~~**`_save_notes()` non atomica in `notes.py`**~~ — fixato: `.tmp` + `os.replace()`.

- [x] ~~**`os.execv` su Windows in `settings_page.py`**~~ — funziona, testato 1000+ volte.

### Deadlock / Concorrenza

- [ ] **Stop durante conferma vocale** — `assistant.py`: `_stop_listening` resetta `_busy=False` mentre `wait_for_confirmation` e ancora bloccato su `record_until_silence` (timeout 7s). L'hotkey successivo apre un secondo stream audio → conflitto driver audio o silenzio. Dopo il timeout la vecchia pipeline continua con `confirmed=False`. Fix: segnalare a `wait_for_confirmation` di abortire (via Event), e non resettare `_busy` finche il thread non e effettivamente terminato.

### UI

- [x] **PTY reader busy loop in `terminal_page.py`** — `_read_loop()`: se `self._pty.read()` ritorna stringa vuota (EOF/processo morto), il loop continua senza sleep → 100% CPU. Fix: `if not data: break` per uscire su EOF.

- [ ] **Download thread multipli in `model_download.py`** — `showEvent()` spawna un daemon thread senza salvare riferimento. Se il dialog viene mostrato piu volte, thread multipli scaricano lo stesso modello concorrentemente → corruzione directory. Fix: salvare riferimento e verificare `is_alive()` prima di spawnare.

---

## TODO — Migliorie codebase

### Medi (qualita / UX)

- [ ] **System prompt troppo lungo** — `prompts.py`: 124 righe con esempi ridondanti. Ogni `classify_intent` consuma ~300 token solo di prompt. Condensare gli esempi, auto-generare la lista intent dal registry delle azioni.

- [ ] **search_terms non normalizzati** — `brain.py`: il LLM puo restituire termini duplicati con case diverso. Fix: `terms = list({t.strip().lower() for t in terms})`.

- [ ] **Nessuna cache sui risultati di ricerca** — `search.py`: "apri Chrome" due volte → ricerca Everything rifatta da zero. Fix: `functools.lru_cache` con TTL 30s.

- [ ] **pick_best_result sempre via LLM** — `brain.py`: anche con match quasi perfetto (query "Chrome", risultato `chrome.exe`), chiama il LLM. Fix: fuzzy match locale (`difflib.SequenceMatcher`) per casi ovvi, LLM solo per ambigui.

- [x] ~~**Config non atomica**~~ — fixato: `_save_json()` usa `.tmp` + `os.replace()`.

- [ ] **Log page accumula tutto in memoria** — `log_page.py`: lista `_lines` cresce senza limiti. Fix: cap a ~5000 righe.

- [ ] **Dashboard refresh eccessivo** — `dashboard_page.py`: si aggiorna ogni 3s anche senza cambiamenti. Fix: aggiornare solo su segnale dal core.

- [ ] **print() ovunque invece di logging** — tutto il codebase. Fix: `logging.getLogger(__name__)` con livelli.

- [ ] **CUDA DLL path manipulation ripetuta** — `transcriber.py`: aggiunge directory CUDA al PATH e chiama `os.add_dll_directory()` ad ogni reload. Fix: farlo una sola volta all'avvio.

- [x] ~~**screen_read usa sempre il modello Ollama**~~ — fixato: usa `_get_model(config)` che rispetta il provider attivo.

### Architetturali (refactor futuro)

- [ ] **State machine esplicita** — `assistant.py`: stato tracciato con due bool (`_busy`, `_processing`). Fix: Enum esplicito (IDLE → RECORDING → PROCESSING → EXECUTING → IDLE).

- [ ] **Auto-discovery delle azioni** — `core/actions/__init__.py`: aggiungere azione richiede 3 passi manuali. Fix: decoratore `@register_action("program")`.

- [ ] **Sync automatica prompt-azioni** — `prompts.py`: lista intent scritta a mano, puo andare fuori sync. Fix: generarla dal registry.

- [ ] **ThreadPoolExecutor** — tutto il codebase: daemon thread singoli che perdono eccezioni. Fix: `ThreadPoolExecutor` con `future.result()`.

- [ ] **TTS asyncio persistente** — `tts.py`: crea/distrugge event loop ad ogni `speak()`. Fix: loop persistente su thread dedicato.

