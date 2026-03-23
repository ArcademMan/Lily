import json
import os
import shutil
import threading

# ── Paths ────────────────────────────────────────────────────────────────────
_APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
LILY_DIR = os.path.join(_APPDATA, "AmMstools", "Lily")
SETTINGS_DIR = os.path.join(LILY_DIR, "settings")
MODELS_DIR = os.path.join(LILY_DIR, "models")
USER_SETTINGS_FILE = os.path.join(SETTINGS_DIR, "user_settings.json")
LILY_SETTINGS_FILE = os.path.join(SETTINGS_DIR, "lily_settings.json")

# Vecchio path per migrazione automatica
_OLD_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

# ── Defaults ─────────────────────────────────────────────────────────────────
# Settings che solo l'utente può modificare (provider, API key, modelli)
USER_DEFAULTS = {
    "provider": "ollama",
    "ollama_model": "qwen3b",
    "anthropic_api_key": "",
    "anthropic_model": "claude-haiku-4-5-20251001",
    "anthropic_max_results": 10,
    "openai_api_key": "",
    "openai_model": "gpt-4o-mini",
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "mic_device": None,
    "whisper_model": "medium",
    "whisper_device": "cuda",
    "setup_done": False,
}

# Settings che Lily può auto-modificare (hotkey, paths, TTS, tuning)
LILY_DEFAULTS = {
    "hotkey": "ctrl+shift+space",
    "es_path": "es.exe",
    "tesseract_path": "tesseract",
    "thinking_enabled": False,
    "num_predict": 128,
    "tts_enabled": True,
    "tts_voice": "Isabella",
    "chat_max_history": 5,
    "chat_num_predict": 384,
    "dictation_silence_timeout": 8,
    "dictation_silence_duration": 3.5,
    "dictation_max_duration": 60,
    "overlay_enabled": True,
}

ALL_DEFAULTS = {**USER_DEFAULTS, **LILY_DEFAULTS}


def _load_json(path: str) -> dict:
    """Carica un file JSON, ritorna {} se non esiste o è corrotto."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"[Config] Warning: {path} non è JSON valido, uso defaults")
        return {}
    except Exception as e:
        print(f"[Config] Warning: impossibile leggere {path}: {e}")
        return {}


def _save_json(path: str, data: dict):
    """Salva un dict come JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class Config:
    def __init__(self):
        self._user_data: dict = {}
        self._lily_data: dict = {}
        super().__setattr__("_lock", threading.RLock())
        self._migrate_old_settings()
        self.load()

    def _migrate_old_settings(self):
        """Migra dal vecchio settings.json unico ai nuovi file separati."""
        if not os.path.exists(_OLD_SETTINGS_FILE):
            return
        if os.path.exists(USER_SETTINGS_FILE) or os.path.exists(LILY_SETTINGS_FILE):
            return  # Già migrato

        print(f"[Config] Migrazione da {_OLD_SETTINGS_FILE}...")
        old_data = _load_json(_OLD_SETTINGS_FILE)
        if not old_data:
            return

        os.makedirs(SETTINGS_DIR, exist_ok=True)

        user_data = {k: old_data[k] for k in USER_DEFAULTS if k in old_data}
        lily_data = {k: old_data[k] for k in LILY_DEFAULTS if k in old_data}

        _save_json(USER_SETTINGS_FILE, user_data)
        _save_json(LILY_SETTINGS_FILE, lily_data)

        # Rinomina il vecchio file per non rimigrare
        backup = _OLD_SETTINGS_FILE + ".bak"
        try:
            shutil.move(_OLD_SETTINGS_FILE, backup)
            print(f"[Config] Migrazione completata. Vecchio file spostato in {backup}")
        except Exception:
            print("[Config] Migrazione completata. Vecchio file non spostato.")

    def load(self):
        self._user_data = _load_json(USER_SETTINGS_FILE)
        self._lily_data = _load_json(LILY_SETTINGS_FILE)

        # Fill defaults
        for key, value in USER_DEFAULTS.items():
            self._user_data.setdefault(key, value)
        for key, value in LILY_DEFAULTS.items():
            self._lily_data.setdefault(key, value)

    def save(self):
        """Salva entrambi i file."""
        with self._lock:
            os.makedirs(SETTINGS_DIR, exist_ok=True)
            _save_json(USER_SETTINGS_FILE, self._user_data)
            _save_json(LILY_SETTINGS_FILE, self._lily_data)

    def save_lily(self):
        """Salva solo le impostazioni di Lily (per auto-configurazione)."""
        with self._lock:
            os.makedirs(SETTINGS_DIR, exist_ok=True)
            _save_json(LILY_SETTINGS_FILE, self._lily_data)

    def is_lily_setting(self, name: str) -> bool:
        """Ritorna True se il setting è modificabile da Lily."""
        return name in LILY_DEFAULTS

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        with self._lock:
            if name in self._lily_data:
                return self._lily_data[name]
            if name in self._user_data:
                return self._user_data[name]
            raise AttributeError(f"No setting '{name}'")

    def __setattr__(self, name, value):
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            with self._lock:
                if name in LILY_DEFAULTS:
                    self._lily_data[name] = value
                else:
                    self._user_data[name] = value

    def to_dict(self) -> dict:
        with self._lock:
            return {**self._user_data, **self._lily_data}
