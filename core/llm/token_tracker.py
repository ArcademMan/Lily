import json
import os
import threading
from datetime import date

_APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
_DATA_DIR = os.path.join(_APPDATA, "AmMstools", "Lily", "settings")
USAGE_FILE = os.path.join(_DATA_DIR, "usage.json")

_OLD_USAGE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "usage.json"
)

# Pricing per million tokens
PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-6-20250514": {"input": 3.00, "output": 15.00},
}
DEFAULT_PRICING = {"input": 0.0, "output": 0.0}  # Ollama = gratis


def _empty_provider():
    return {"total_input": 0, "total_output": 0, "total_cost": 0.0, "sessions": []}


class TokenTracker:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lock = threading.Lock()
            cls._instance._data = {
                "ollama": _empty_provider(),
                "anthropic": _empty_provider(),
            }
            cls._instance._session = {
                "ollama": {"input": 0, "output": 0, "cost": 0.0},
                "anthropic": {"input": 0, "output": 0, "cost": 0.0},
            }
            cls._instance._load()
        return cls._instance

    def _load(self):
        # Migra dal vecchio path se necessario
        if not os.path.exists(USAGE_FILE) and os.path.exists(_OLD_USAGE_FILE):
            try:
                os.makedirs(_DATA_DIR, exist_ok=True)
                import shutil
                shutil.move(_OLD_USAGE_FILE, USAGE_FILE)
            except Exception:
                pass

        if os.path.exists(USAGE_FILE):
            try:
                with open(USAGE_FILE, "r") as f:
                    raw = f.read()

                # Rimuovi trailing commas (errore comune nell'editing manuale)
                import re
                raw = re.sub(r',\s*([}\]])', r'\1', raw)

                loaded = json.loads(raw)

                # Migra dal vecchio formato (flat) al nuovo (per provider)
                if "ollama" not in loaded and "anthropic" not in loaded:
                    self._data["anthropic"] = {
                        "total_input": loaded.get("total_input", 0),
                        "total_output": loaded.get("total_output", 0),
                        "total_cost": loaded.get("total_cost", 0.0),
                        "sessions": loaded.get("sessions", []),
                    }
                    self._save()
                else:
                    for provider in ("ollama", "anthropic"):
                        if provider in loaded:
                            self._data[provider] = loaded[provider]
            except Exception as e:
                print(f"[TokenTracker] Errore caricamento usage.json: {e}")

    def _save(self):
        with self._lock:
            try:
                os.makedirs(_DATA_DIR, exist_ok=True)
                with open(USAGE_FILE, "w") as f:
                    json.dump(self._data, f, indent=2)
            except Exception:
                pass

    def _provider_key(self, model: str) -> str:
        """Determina il provider dal nome del modello."""
        if model.startswith("claude"):
            return "anthropic"
        return "ollama"

    def track(self, model: str, input_tokens: int, output_tokens: int):
        provider = self._provider_key(model)
        pricing = PRICING.get(model, DEFAULT_PRICING)
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

        with self._lock:
            # Session
            self._session[provider]["input"] += input_tokens
            self._session[provider]["output"] += output_tokens
            self._session[provider]["cost"] += cost

            # Totali
            p = self._data[provider]
            p["total_input"] = p.get("total_input", 0) + input_tokens
            p["total_output"] = p.get("total_output", 0) + output_tokens
            p["total_cost"] = round(p.get("total_cost", 0.0) + cost, 6)

            # Daily
            today = date.today().isoformat()
            sessions = p.get("sessions", [])
            if sessions and sessions[-1].get("date") == today:
                sessions[-1]["input"] = sessions[-1].get("input", 0) + input_tokens
                sessions[-1]["output"] = sessions[-1].get("output", 0) + output_tokens
                sessions[-1]["cost"] = round(sessions[-1].get("cost", 0.0) + cost, 6)
                sessions[-1]["requests"] = sessions[-1].get("requests", 0) + 1
            else:
                sessions.append({
                    "date": today,
                    "input": input_tokens,
                    "output": output_tokens,
                    "cost": round(cost, 6),
                    "requests": 1,
                })
            p["sessions"] = sessions

        self._save()

    def get_session(self, provider: str) -> dict:
        with self._lock:
            s = self._session.get(provider, {"input": 0, "output": 0, "cost": 0.0})
            return dict(s)

    def get_totals(self, provider: str) -> dict:
        with self._lock:
            p = self._data.get(provider, _empty_provider())
            return {
                "total_input": p.get("total_input", 0),
                "total_output": p.get("total_output", 0),
                "total_cost": p.get("total_cost", 0.0),
            }

    def get_sessions(self, provider: str) -> list[dict]:
        with self._lock:
            p = self._data.get(provider, _empty_provider())
            return list(p.get("sessions", []))

    # Backward compat properties (usano anthropic come default)
    @property
    def session_input(self) -> int:
        return self._session["anthropic"]["input"]

    @property
    def session_output(self) -> int:
        return self._session["anthropic"]["output"]

    @property
    def session_cost(self) -> float:
        return self._session["anthropic"]["cost"]

    @property
    def total_input(self) -> int:
        return self._data["anthropic"].get("total_input", 0)

    @property
    def total_output(self) -> int:
        return self._data["anthropic"].get("total_output", 0)

    @property
    def total_cost(self) -> float:
        return self._data["anthropic"].get("total_cost", 0.0)

    @property
    def sessions(self) -> list[dict]:
        return self.get_sessions("anthropic")
