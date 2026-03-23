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
