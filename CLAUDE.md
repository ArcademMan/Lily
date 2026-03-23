# Lily - Assistente Vocale

## Panoramica

Assistente vocale in italiano per Windows con pipeline: hotkey → registrazione audio → trascrizione Whisper (GPU) → classificazione intent via LLM (Ollama/Claude) → esecuzione azione. UI in PySide6 con design glassmorphism.

## Struttura progetto

- `core/` — logica principale (assistant, search, signal)
- `core/voice/` — pipeline vocale (listener, transcriber, hotkey)
- `core/llm/` — provider LLM (Ollama, Anthropic, brain, token tracker)
- `core/actions/` — azioni eseguibili (9 tipi: program, folder, website, screenshot, timer, volume, ecc.)
- `ui/` — interfaccia PySide6 (pages, widgets, bridge, tray)
- `config.py` — gestione configurazione
- `main.py` — entry point

## Convenzioni

- Lingua: italiano (Whisper hardcoded `language="it"`)
- Nuove azioni: ereditare da `core/actions/base.py` → registrare in `core/actions/__init__.py` → aggiornare prompt in `core/llm/brain.py`
- Nuovi provider LLM: ereditare da `core/llm/base_provider.py` → aggiungere factory in `core/llm/__init__.py`
- Segnali core→UI: usare `core/signal.py` + `ui/bridge.py`

---

## Feature implementate

- Text-to-Speech (Edge TTS + fallback Piper locale)
- Modalità conversazione (intent `chat` con personalità)
- Modalità dettatura (segmenti + dettatura su finestra target)
- Controllo multimedia (play/pausa, next, previous, stop)
- Memoria conversazionale globale (classify_intent + chat)
- Lista comandi in chat ("cosa puoi fare?")
- Scrivi su finestra ("vai su X e scrivi Y e invia")
- Lettura schermo (screenshot + OCR Tesseract + interpretazione LLM)
- Gestione finestre (snap, sposta monitor, minimizza, ripristina, chiudi cartelle, nudge pixel)
- Conferma vocale per azioni pericolose
- Correzione nomi Whisper + parametri per modello
- Ricerca intelligente (retry LLM, expand terms, fuzzy)
- Pick con contesto (intent completo, esclusioni utente)
- Messaggi parlabili (italiano, nomi puliti)
- Caps Lock come hotkey (alias localizzati)
- Chiusura programmi gentile (WM_CLOSE + fallback taskkill)
- Stato Ollama in UI
- Config thread-safe (RLock) + error handling JSON corrotto
- `find_window` unificata in `core/utils/win32.py`
- Quick notes vocali (salva, leggi, cancella note con timestamp)
- Catena di comandi in linguaggio naturale (decomposizione LLM in sotto-azioni sequenziali)

---

## TODO — Feature da implementare

- [ ] Monitoring passivo / Watchdog — "avvisami quando il download finisce", monitor cartella/processo/CPU
- [ ] Automazione visiva — "quando vedi la scritta X sullo schermo, avvisami" — polling periodico con OCR, notifica vocale. Monitoraggio visivo dello schermo
- [ ] Multi-step visivi — "cerca su Google Immagini un gatto e scarica la prima immagine" — azioni concatenate con feedback visivo (screenshot → OCR → decisione → azione)

---

## TODO — Migliorie codebase

### Critici (stabilità) — COMPLETATI

- [x] **Provider cloud ignorano il parametro model** — `anthropic_provider.py`, `openai_provider.py`, `gemini_provider.py`
  Fix: `use_model = model or self.model` in tutti e tre i provider.

- [x] **JSON parsing fragile in brain.py** — `brain.py:_parse_json()`
  Fix: parser con conteggio depth bilanciato che gestisce `{}` annidati e stringhe con escape.

- [x] **Thread-safety mancante nel listener** — `listener.py`
  Fix: sostituito bool `_running` con `threading.Event` (`_stop_event`).

### Alti (efficienza / robustezza) — COMPLETATI

- [x] **Busy-wait sulla TTS** — `assistant.py` + `tts.py`
  Fix: aggiunto `_done_event` (threading.Event) alla TTS, l'assistant usa `event.wait(timeout=15)` invece del polling loop.

- [x] **Conferma vocale chiama il LLM per un sì/no** — `confirmation.py`
  Fix: aggiunto keyword matching veloce (`_keyword_confirm`) con set YES/NO, fallback LLM solo se ambiguo.

- [x] **Nessun retry sulle chiamate di rete** — tutti i provider LLM
  Fix: `retry_on_transient()` in `base_provider.py` con backoff 0.5s/1s/2s. Retry solo su ConnectionError, Timeout, HTTP 429/5xx.

- [x] **nvidia-smi ogni 5 secondi** — `voice_page.py`
  Fix: intervallo portato a 30 secondi.

- [x] **Memory leak nei timer ricorrenti** — `timer_action.py`
  Fix: aggiunto `cancel_event` (threading.Event) per ogni timer ricorrente, controllato prima di creare il prossimo tick.

- [x] **Conversation memory non thread-safe** — `conversation.py`
  Fix: aggiunto `threading.Lock` su tutte le operazioni di lettura/scrittura di `_history`.

### Medi (qualità / UX)

- [ ] **System prompt troppo lungo** — `prompts.py`
  Il prompt per Ollama è 124 righe con molti esempi ridondanti. Ogni chiamata `classify_intent` consuma ~300 token solo di prompt. Condensare gli esempi, e auto-generare la lista degli intent disponibili dal registry delle azioni così non va aggiornata a mano.

- [ ] **search_terms non normalizzati** — `brain.py`
  Il LLM può restituire termini duplicati con case diverso (es. `["Elden Ring", "elden ring"]`). La ricerca li tratta come distinti e fa lavoro doppio. Fix: `terms = list({t.strip().lower() for t in terms})`.

- [ ] **Nessuna cache sui risultati di ricerca** — `search.py`
  Se l'utente dice "apri Chrome" due volte, la ricerca su Everything viene rifatta da zero ogni volta. Un `functools.lru_cache` con TTL di 30 secondi eliminerebbe ricerche duplicate.

- [ ] **pick_best_result sempre via LLM** — `brain.py`
  Anche quando c'è un match quasi perfetto (es. query "Chrome" e risultato `chrome.exe`), il codice chiama il LLM per scegliere tra i risultati. Un fuzzy match locale (es. `difflib.SequenceMatcher`) potrebbe risolvere i casi ovvi istantaneamente, e chiamare il LLM solo quando ci sono più candidati ambigui.

- [ ] **Config non atomica** — `config.py`
  Se il processo crasha durante `json.dump()`, il file settings può rimanere vuoto o corrotto (il file viene aperto in write mode che lo tronca prima di scrivere). Fix: scrivere su file `.tmp` e poi `os.replace()` che su Windows è atomico.

- [ ] **Log page accumula tutto in memoria** — `log_page.py`
  La lista `_lines` cresce senza limiti. In sessioni lunghe (ore di uso) può arrivare a migliaia di righe. Fix: cap a ~5000 righe, eliminando le più vecchie.

- [ ] **Dashboard refresh eccessivo** — `dashboard_page.py`
  Si aggiorna ogni 3 secondi con un timer, anche se non è cambiato nulla. Ridisegna tutta la UI (layout, chart, righe modelli) inutilmente. Fix: aggiornare solo quando arriva un segnale dal core che indica una nuova chiamata LLM completata.

- [ ] **print() ovunque invece di logging** — tutto il codebase
  Debug, errori e info usano tutti `print()`. Non c'è modo di filtrare per livello, redirectare su file, o disabilitare in produzione. Fix: `logging.getLogger(__name__)` con livelli DEBUG/INFO/WARNING.

- [ ] **CUDA DLL path manipulation ripetuta** — `transcriber.py`
  Ogni volta che il modello Whisper viene caricato, il codice aggiunge directory CUDA al PATH di sistema e chiama `os.add_dll_directory()`. Questo modifica stato globale del processo e il PATH cresce ad ogni reload. Fix: farlo una sola volta all'avvio dell'app.

- [ ] **screen_read usa sempre il modello Ollama** — `screen_read.py`
  La lettura schermo (OCR + interpretazione LLM) usa sempre `config.ollama_model` hardcodato, anche se il provider attivo è Anthropic o OpenAI. Fix: usare il provider e modello configurati dall'utente.

### Architetturali (refactor futuro)

- [ ] **State machine esplicita** — `assistant.py`
  Lo stato è tracciato con due bool (`_busy`, `_processing`) che possono assumere combinazioni incoerenti. Un Enum esplicito (IDLE → RECORDING → PROCESSING → EXECUTING → IDLE) renderebbe le transizioni chiare e prevenibili i bug di stato.

- [ ] **Auto-discovery delle azioni** — `core/actions/__init__.py`
  Aggiungere una nuova azione richiede: creare la classe, registrarla manualmente in `__init__.py`, aggiornare il prompt in `prompts.py`. Un decoratore `@register_action("program")` permetterebbe di fare tutto nel file dell'azione.

- [ ] **Sync automatica prompt ↔ azioni** — `prompts.py`
  La lista degli intent nel system prompt è scritta a mano e può andare fuori sync con le azioni reali. Generarla automaticamente dal registry eliminerebbe il problema.

- [ ] **ThreadPoolExecutor** — tutto il codebase
  Ogni task lancia un daemon thread singolo che, se crasha, perde l'eccezione silenziosamente. Un `ThreadPoolExecutor` gestisce il pool, cattura le eccezioni, e permette di aspettare i risultati con `future.result()`.

- [ ] **TTS asyncio persistente** — `tts.py`
  Ogni chiamata a `speak()` crea un nuovo event loop asyncio (`asyncio.new_event_loop()`), lo usa per una singola generazione Edge TTS, e lo distrugge. Creare/distruggere loop ha overhead. Fix: un singolo loop persistente su un thread dedicato, o semplicemente `asyncio.run()`.

- [ ] **Escaping query PowerShell** — `program.py`
  La funzione `_try_launch_uwp()` inserisce la query direttamente nella stringa PowerShell senza escaping. Il rischio reale è quasi zero (l'input viene dalla voce dell'utente, non da fonti esterne), ma per correttezza andrebbe sanitizzato.
