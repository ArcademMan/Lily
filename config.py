import json
import os

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULTS = {
    "hotkey": "ctrl+shift+space",
    "provider": "ollama",
    "ollama_model": "qwen3b",
    "anthropic_api_key": "",
    "anthropic_model": "claude-haiku-4-5-20251001",
    "es_path": "es.exe",
    "mic_device": None,
    "whisper_model": "medium",
    "thinking_enabled": False,
    "num_predict": 128,
    "tts_enabled": True,
    "tts_voice": "Isabella",
    "chat_max_history": 5,
    "chat_num_predict": 384,
    "dictation_silence_timeout": 8,
    "tesseract_path": "tesseract",
    "dictation_silence_duration": 3.5,
    "dictation_max_duration": 60,
}


class Config:
    def __init__(self):
        self._data: dict = {}
        self.load()

    def load(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        # Fill missing keys with defaults
        for key, value in DEFAULTS.items():
            self._data.setdefault(key, value)

    def save(self):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(f"No setting '{name}'")

    def __setattr__(self, name, value):
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self._data[name] = value

    def to_dict(self) -> dict:
        return dict(self._data)
