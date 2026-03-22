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

## TODO — Feature e miglioramenti

### P0 — Priorità critica

- [x] **Text-to-Speech**: Edge TTS come default con fallback Piper TTS (locale). Voce configurabile nei settings (`tts_voice`, `tts_enabled`). Modello Piper italiano (Paola) in `models/tts/`.
- [x] **Modalità conversazione**: Intent `chat` aggiunto con `CHAT_SYSTEM_PROMPT`. (in corso da altro agent)

### P1 — Priorità alta

- [x] **Modalità dettatura**: Intent `dictation` implementato. Trascrive a segmenti e digita al cursore via `keyboard.write()`. Auto-stop dopo silenzio prolungato. Beep sonoro di attivazione (800Hz) e disattivazione (400Hz).
- [x] **Controllo multimedia**: Action `media` con tasti multimediali Windows (play/pausa, next, previous, stop). Funziona con qualsiasi player.
- [x] **Memoria conversazionale**: `ConversationMemory` globale in Assistant, condivisa tra classify_intent (contesto follow-up) e ChatAction (continuità chat). L'LLM vede i comandi precedenti.
- [x] **Lista comandi in chat**: Lily sa elencare i propri comandi disponibili quando l'utente chiede "cosa puoi fare?".
- [x] **Scrivi su finestra**: Action `type_in` — "vai sul terminale e scrivi X e invia". Trova finestra per nome, porta in focus, digita testo, opzionalmente preme Enter.
- [ ] **Overlay disambiguazione**: Finestrella trasparente in alto a sinistra che mostra le opzioni quando Lily è indecisa (file, cartelle, finestre). L'utente risponde a voce "il primo", "il secondo", ecc.
- [x] **Nudge finestre**: Spostamento fine in pixel — "sposta Discord più in basso", "sposta Chrome 100 pixel a destra". Default 50px, "molto" = 200px, o pixel esatti.

### P2 — Priorità media

- [ ] **Macro / automazioni personalizzate**: File JSON con comandi composti (es. "buongiorno" → apre Outlook + Slack + Google News). Un solo comando vocale esegue più azioni in sequenza.
- [ ] **Note rapide**: Nuova action `note` — "segna: comprare il latte" salva in `notes.md` con timestamp. "Leggi le note di oggi" le legge via TTS.
- [ ] **Meteo**: Nuova action `weather` con API Open-Meteo (gratis, no API key). "Che tempo fa?" / "Pioverà domani?" con città configurabile.
- [ ] **Budget alert per token**: Soglia di spesa giornaliera/mensile configurabile con notifica. Fallback automatico a Ollama quando il budget è esaurito.

### P3 — Priorità bassa

- [x] **Gestione finestre**: Action `window_management` con win32gui — sposta, minimizza, massimizza, mostra desktop.
- [ ] **Clipboard manager**: Nuova action `clipboard` — "leggi la clipboard", "cerca la clipboard online", copia screenshot in clipboard.
- [ ] **Controllo luminosità**: Nuova action `brightness` via `screen_brightness_control` — "luminosità al 50%", "abbassa la luminosità".
- [ ] **Supporto multi-lingua**: Auto-detect lingua nel transcriber, prompt multilingua, setting per lingua preferita con opzione "auto".

### Miglioramenti a feature esistenti

- [x] **Correzione nomi da Whisper**: Prompt Ollama migliorato con lista errori comuni (Eldering→Elden Ring, Little Company→Lethal Company, ecc.). Initial prompt Whisper con nomi programmi/giochi.
- [x] **Parametri Whisper per modello**: beam_size, VAD, initial_prompt variano in base al modello (tiny→large-v3).
- [x] **Ricerca intelligente**: Retry con LLM se nessun risultato, expand_search_terms (varianti con/senza spazi), fuzzy search per parole singole.
- [x] **Pick con contesto**: Il pick riceve intent completo + testo originale, rispetta esclusioni utente ("non su D:"), valida anche risultati singoli.
- [x] **Messaggi parlabili**: Tutti i messaggi di ritorno in italiano e senza path (solo nomi puliti per il TTS).
- [x] **Junk filter migliorato**: Filtrati Recent, artbook, soundtrack, debug tool, uninstall.
- [x] **Supporto qwen3 thinking**: Flag `think: false` inviato a Ollama quando thinking è disabilitato.
- [x] **Conferma vocale per azioni pericolose**: close_program richiede conferma vocale (TTS chiede, mic ascolta, Whisper trascrive, LLM interpreta). Timeout 7s → annulla. Set `DANGEROUS_INTENTS` espandibile.
- [x] **Caps Lock come hotkey**: Supporto alias tasti localizzati (bloc maius/caps lock). Toggle caps forzato a OFF dopo rilascio.
- [x] **Chiusura programmi gentile**: WM_CLOSE via `win32gui` con timeout 3s, poi fallback a `taskkill /F`.
- [ ] **Filtro allucinazioni Whisper dinamico**: Spostare la lista in un JSON editabile. Auto-learning: se l'LLM non classifica l'intent, aggiungere la trascrizione alla lista.
- [x] **Stato Ollama in UI**: Indicatore "Connesso"/"Non connesso" nella pagina settings, visibile solo quando provider è Ollama.
