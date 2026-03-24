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

# Pricing per million tokens (default, sovrascritto da pricing.json)
PRICING_FILE = os.path.join(_DATA_DIR, "pricing.json")
_DEFAULT_PRICING_TABLE = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-6-20250514": {"input": 3.00, "output": 15.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-5.4-nano": {"input": 0.20, "output": 1.25},
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
}
DEFAULT_PRICING = {"input": 0.0, "output": 0.0}  # Ollama = gratis


def _load_pricing() -> dict:
    """Carica pricing da file JSON; se non esiste lo crea con i default."""
    if os.path.exists(PRICING_FILE):
        try:
            with open(PRICING_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            # Merge: i default colmano modelli mancanti nel file
            merged = dict(_DEFAULT_PRICING_TABLE)
            merged.update(loaded)
            return merged
        except Exception as e:
            print(f"[TokenTracker] Errore lettura pricing.json: {e}")
    # Crea il file con i default
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(PRICING_FILE, "w", encoding="utf-8") as f:
            json.dump(_DEFAULT_PRICING_TABLE, f, indent=2)
    except Exception:
        pass
    return dict(_DEFAULT_PRICING_TABLE)


PRICING = _load_pricing()


def _calc_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    p = PRICING.get(model, DEFAULT_PRICING)
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def _cost_from_models(models: dict) -> float:
    """Calcola il costo dai token suddivisi per modello."""
    total = 0.0
    for model, tokens in models.items():
        total += _calc_cost(tokens.get("input", 0), tokens.get("output", 0), model)
    return total


def _cost_from_sessions(sessions: list) -> float:
    """Calcola il costo totale da tutte le sessioni giornaliere."""
    total = 0.0
    for s in sessions:
        if "models" in s:
            total += _cost_from_models(s["models"])
    return total


def _sum_from_models(models: dict) -> tuple[int, int, int]:
    """Somma input, output, requests dai modelli di una sessione."""
    ti = sum(m.get("input", 0) for m in models.values())
    to = sum(m.get("output", 0) for m in models.values())
    reqs = sum(m.get("requests", 0) for m in models.values())
    return ti, to, reqs


def _sum_from_sessions(sessions: list) -> tuple[int, int]:
    """Somma input/output token da tutte le sessioni."""
    ti = to = 0
    for s in sessions:
        si, so, _ = _sum_from_models(s.get("models", {}))
        ti += si
        to += so
    return ti, to


def _empty_provider():
    return {"sessions": []}


class TokenTracker:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lock = threading.Lock()
            cls._instance._data = {
                "ollama": _empty_provider(),
                "anthropic": _empty_provider(),
                "openai": _empty_provider(),
                "gemini": _empty_provider(),
            }
            cls._instance._session = {
                "ollama": {"models": {}},
                "anthropic": {"models": {}},
                "openai": {"models": {}},
                "gemini": {"models": {}},
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

                import re
                raw = re.sub(r',\s*([}\]])', r'\1', raw)

                loaded = json.loads(raw)

                # Migra dal vecchio formato (flat) al nuovo (per provider)
                if "ollama" not in loaded and "anthropic" not in loaded:
                    self._data["anthropic"] = {
                        "sessions": loaded.get("sessions", []),
                    }
                    self._save()
                else:
                    for provider in ("ollama", "anthropic", "openai", "gemini"):
                        if provider in loaded:
                            self._data[provider] = {
                                "sessions": loaded[provider].get("sessions", []),
                            }
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
        if model.startswith("claude"):
            return "anthropic"
        if model.startswith("gpt"):
            return "openai"
        if model.startswith("gemini"):
            return "gemini"
        return "ollama"

    def track(self, model: str, input_tokens: int, output_tokens: int):
        provider = self._provider_key(model)

        with self._lock:
            # Session in-memory
            s = self._session[provider]
            m = s["models"].setdefault(model, {"input": 0, "output": 0, "requests": 0})
            m["input"] += input_tokens
            m["output"] += output_tokens
            m["requests"] += 1

            # Daily session — tutto dentro models
            p = self._data[provider]
            today = date.today().isoformat()
            sessions = p["sessions"]
            if sessions and sessions[-1].get("date") == today:
                day = sessions[-1]
            else:
                day = {"date": today, "models": {}}
                sessions.append(day)
            md = day["models"].setdefault(model, {"input": 0, "output": 0, "requests": 0})
            md["input"] += input_tokens
            md["output"] += output_tokens
            md["requests"] += 1

        self._save()

    def session_totals(self) -> tuple[int, int]:
        """Ritorna (total_input, total_output) sommati su tutti i provider della sessione."""
        with self._lock:
            ti = to = 0
            for s in self._session.values():
                for m in s.get("models", {}).values():
                    ti += m.get("input", 0)
                    to += m.get("output", 0)
            return ti, to

    def get_session(self, provider: str) -> dict:
        with self._lock:
            s = self._session.get(provider, {"models": {}})
            models = s.get("models", {})
            ti, to, reqs = _sum_from_models(models)
            return {
                "input": ti,
                "output": to,
                "requests": reqs,
                "cost": _cost_from_models(models),
            }

    def get_totals(self, provider: str) -> dict:
        with self._lock:
            sessions = self._data.get(provider, _empty_provider())["sessions"]
            ti, to = _sum_from_sessions(sessions)
            return {
                "total_input": ti,
                "total_output": to,
                "total_cost": _cost_from_sessions(sessions),
            }

    def get_sessions(self, provider: str) -> list[dict]:
        with self._lock:
            return list(self._data.get(provider, _empty_provider())["sessions"])

    # Backward compat properties (usano anthropic come default)
    @property
    def session_input(self) -> int:
        return self.get_session("anthropic")["input"]

    @property
    def session_output(self) -> int:
        return self.get_session("anthropic")["output"]

    @property
    def session_cost(self) -> float:
        return self.get_session("anthropic")["cost"]

    @property
    def total_input(self) -> int:
        return self.get_totals("anthropic")["total_input"]

    @property
    def total_output(self) -> int:
        return self.get_totals("anthropic")["total_output"]

    @property
    def total_cost(self) -> float:
        return self.get_totals("anthropic")["total_cost"]

    @property
    def sessions(self) -> list[dict]:
        return self.get_sessions("anthropic")
