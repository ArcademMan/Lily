# Lily — Assistente Vocale AI per Windows

Assistente vocale in italiano per Windows con classificazione intent via LLM ed esecuzione automatica di azioni. Pipeline: hotkey → registrazione audio → trascrizione Whisper (GPU) → classificazione intent → esecuzione azione.

## Caratteristiche

- **Pipeline vocale completa** — Premi Caps Lock, parla, rilascia. Lily trascrive, capisce e agisce.
- **17 azioni disponibili** — Apri programmi, cartelle, siti web, controlla volume e multimedia, gestisci finestre, imposta timer, prendi screenshot, leggi lo schermo (OCR), detta testo, prendi appunti vocali e altro.
- **Catena di comandi** — Comandi complessi in linguaggio naturale vengono decomposti in sotto-azioni sequenziali.
- **Multi-provider LLM** — Ollama (locale, default), Anthropic Claude, OpenAI, Google Gemini.
- **Trascrizione GPU** — Faster-Whisper con CUDA per trascrizione rapida e accurata.
- **Text-to-Speech** — Edge TTS (cloud) con fallback Piper (offline).
- **Conversazione** — Memoria conversazionale per dialoghi multi-turno.
- **UI glassmorphism** — Interfaccia moderna in PySide6 con effetto vetro e blur nativo Windows.

## Requisiti

- Windows 10/11
- Python 3.10+
- GPU NVIDIA con CUDA (consigliato, non obbligatorio)
- [Ollama](https://ollama.com/) (se si usa il provider locale)

## Installazione

```bash
git clone https://github.com/tu-utente/Lily.git
cd Lily
pip install -r requirements.txt
```

### Dipendenze principali

| Pacchetto | Uso |
|---|---|
| PySide6 | Interfaccia grafica |
| faster-whisper | Trascrizione speech-to-text |
| sounddevice | Cattura audio microfono |
| keyboard | Hotkey globali |
| requests | Comunicazione con Ollama/API |
| edge-tts | Text-to-speech cloud |
| pillow | Screenshot e immagini |
| pytesseract | OCR per lettura schermo |

Provider LLM opzionali: `anthropic`, `openai`, `google-generativeai`

## Avvio

```bash
python main.py
```

Al primo avvio verrà mostrato un wizard di configurazione per selezionare microfono, modello Whisper e provider LLM.

## Utilizzo

1. **Premi Caps Lock** (o l'hotkey configurata) per iniziare a registrare
2. **Parla** il tuo comando in italiano
3. **Rilascia** il tasto — Lily trascrive, classifica l'intent e esegue l'azione

### Esempi di comandi

| Comando | Azione |
|---|---|
| "Apri Chrome" | Lancia Google Chrome |
| "Alza il volume" | Aumenta il volume di sistema |
| "Che ore sono?" | Dice l'ora corrente |
| "Metti in pausa la musica" | Pausa riproduzione multimediale |
| "Fai uno screenshot" | Cattura schermo negli appunti |
| "Cosa c'è sullo schermo?" | Screenshot + OCR + interpretazione LLM |
| "Scrivi 'ciao' su Notepad e invia" | Apre Notepad e digita il testo |
| "Sposta Chrome a destra" | Snap della finestra a metà schermo |
| "Timer 5 minuti" | Imposta un timer con notifica |
| "Ricordami di bere ogni 30 minuti" | Reminder ricorrente |
| "Salva nota: comprare il latte" | Salva un appunto vocale |
| "Come funziona il codice su schermo?" | Legge e spiega il contenuto visibile |

## Azioni disponibili

| Intent | Descrizione |
|---|---|
| `open_program` | Avvia programmi, giochi, app UWP |
| `open_folder` | Apre cartelle e directory |
| `open_website` | Apre URL o cerca su Google |
| `close_program` | Chiude programmi (graceful + fallback) |
| `search_files` | Cerca file per nome |
| `screenshot` | Cattura screenshot |
| `screen_read` | Screenshot + OCR + interpretazione LLM |
| `volume` | Controlla volume di sistema |
| `media` | Play/pausa/next/stop multimedia |
| `type_in` | Digita testo in una finestra target |
| `window` | Snap, sposta, minimizza, ripristina finestre |
| `timer` | Timer, sveglie, promemoria ricorrenti |
| `time` | Ora e data corrente |
| `chat` | Conversazione libera |
| `notes` | Appunti vocali rapidi |
| `self_config` | Modifica impostazioni di Lily |
| `system_info` | Info su CPU, RAM, disco, processi |

## Provider LLM

| Provider | Tipo | Configurazione |
|---|---|---|
| **Ollama** | Locale | Installa Ollama, scarica un modello (es. `llama3`) |
| **Anthropic** | Cloud | API key Anthropic |
| **OpenAI** | Cloud | API key OpenAI |
| **Gemini** | Cloud | API key Google AI |

Il provider si configura dalla pagina LLM nell'interfaccia.

## Struttura progetto

```
Lily/
├── main.py                 # Entry point
├── config.py               # Configurazione thread-safe
├── core/
│   ├── assistant.py        # Coordinatore principale
│   ├── search.py           # Ricerca programmi
│   ├── signal.py           # Sistema segnali thread-safe
│   ├── actions/            # 17 azioni eseguibili
│   ├── llm/                # Provider LLM e classificazione intent
│   │   ├── brain.py        # Classificazione intent e chat
│   │   ├── prompts.py      # Prompt di sistema
│   │   └── ...provider.py  # Provider (Ollama, Anthropic, OpenAI, Gemini)
│   ├── voice/              # Pipeline vocale
│   │   ├── hotkey.py       # Gestione hotkey
│   │   ├── listener.py     # Registrazione audio
│   │   ├── transcriber.py  # Trascrizione Whisper
│   │   ├── tts.py          # Text-to-speech
│   │   └── dictation.py    # Modalità dettatura
│   └── utils/              # Utility (Win32, OCR, clipboard)
└── ui/                     # Interfaccia PySide6
    ├── app.py              # Inizializzazione app
    ├── main_window.py      # Finestra principale frameless
    ├── bridge.py           # Bridge segnali core → Qt
    ├── style.py            # Stylesheet glassmorphism
    └── pages/              # Pagine (Dashboard, LLM, Voice, Settings, Log)
```

## Estendere Lily

### Aggiungere una nuova azione

1. Crea un file in `core/actions/` ereditando da `Action` (`core/actions/base.py`)
2. Registra l'azione in `core/actions/__init__.py`
3. Aggiorna il prompt di classificazione in `core/llm/brain.py`

### Aggiungere un nuovo provider LLM

1. Crea un provider ereditando da `LLMProvider` (`core/llm/base_provider.py`)
2. Aggiungi la factory in `core/llm/__init__.py`

## Licenza

Questo progetto è per uso personale.
