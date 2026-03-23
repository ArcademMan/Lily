<p align="center">
  <img src="./assets/icon.png" alt="Lily" width="180">
</p>

<h1 align="center">Lily</h1>

<p align="center">
  <strong>Assistente vocale AI per Windows</strong><br>
  Hotkey → trascrizione Whisper → classificazione intent LLM → esecuzione azione.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-blue" alt="Platform">
  <img src="https://img.shields.io/badge/python-3.10+-yellow" alt="Python">
  <img src="https://img.shields.io/badge/gui-PySide6-green" alt="GUI">
  <img src="https://img.shields.io/badge/license-GPL--v3-lightgrey" alt="License">
</p>

---

## Features

| Azione | Descrizione |
|--------|-------------|
| **Programmi** | Apri, chiudi, cerca programmi, giochi, app UWP |
| **Cartelle & File** | Apri cartelle, cerca file per nome |
| **Web** | Apri URL o cerca su Google |
| **Volume & Media** | Alza/abbassa volume, play/pausa/next/stop |
| **Screenshot & OCR** | Cattura schermo, leggi e interpreta contenuto visibile |
| **Finestre** | Snap, sposta monitor, minimizza, ripristina, nudge pixel |
| **Dettatura** | Digita testo in una finestra target |
| **Timer & Reminder** | Timer, sveglie, promemoria ricorrenti |
| **Note vocali** | Salva, leggi, cancella appunti rapidi |
| **Chat** | Conversazione libera con memoria multi-turno |
| **Catena comandi** | Comandi complessi decomposti in sotto-azioni sequenziali |
| **Sistema** | Info CPU, RAM, disco, processi, ora/data |

## Requisiti

- Windows 10/11
- Python 3.10+
- GPU NVIDIA con CUDA (consigliato, non obbligatorio)
- [Ollama](https://ollama.com/) (se si usa il provider locale)

## Installazione

### Da sorgente

```bash
git clone https://github.com/arcademman/Lily.git
cd Lily
pip install -r requirements.txt
python main.py
```

### Da release

1. Scarica `Lily-Setup.exe` da [Releases](https://github.com/arcademman/Lily/releases)
2. Esegui l'installer
3. Avvia Lily dal menu Start

> Al primo avvio verrà mostrato un wizard per configurare microfono, modello Whisper e provider LLM.

## Provider LLM

| Provider | Tipo | Configurazione |
|----------|------|----------------|
| **Ollama** | Locale | Installa Ollama, scarica un modello (es. `llama3`) |
| **Anthropic** | Cloud | API key Anthropic |
| **OpenAI** | Cloud | API key OpenAI |
| **Gemini** | Cloud | API key Google AI |

Il provider si configura dalla pagina LLM nell'interfaccia.

## Build

Per compilare come `.exe` standalone:

```bash
pip install pyinstaller
pyinstaller main.spec
```

Per creare l'installer (richiede [Inno Setup](https://jrsoftware.org/isinfo.php)):

```bash
iscc installer.iss
```

## Licenza

[GNU GPL v3](LICENSE)
