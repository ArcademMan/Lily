import json
import os
from datetime import date

USAGE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "usage.json")

# Haiku 4.5 pricing per million tokens
PRICING = {
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    "claude-sonnet-4-6-20250514": {"input": 3.00, "output": 15.00},
}
DEFAULT_PRICING = {"input": 0.80, "output": 4.00}


class TokenTracker:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data = {"total_input": 0, "total_output": 0, "total_cost": 0.0, "sessions": []}
            cls._instance._session_input = 0
            cls._instance._session_output = 0
            cls._instance._session_cost = 0.0
            cls._instance._load()
        return cls._instance

    def _load(self):
        if os.path.exists(USAGE_FILE):
            try:
                with open(USAGE_FILE, "r") as f:
                    self._data = json.load(f)
            except Exception:
                pass

    def _save(self):
        try:
            with open(USAGE_FILE, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception:
            pass

    def track(self, model: str, input_tokens: int, output_tokens: int):
        pricing = PRICING.get(model, DEFAULT_PRICING)
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

        self._session_input += input_tokens
        self._session_output += output_tokens
        self._session_cost += cost

        self._data["total_input"] = self._data.get("total_input", 0) + input_tokens
        self._data["total_output"] = self._data.get("total_output", 0) + output_tokens
        self._data["total_cost"] = round(self._data.get("total_cost", 0.0) + cost, 6)

        # Daily tracking
        today = date.today().isoformat()
        sessions = self._data.get("sessions", [])
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
        self._data["sessions"] = sessions
        self._save()

    @property
    def session_input(self) -> int:
        return self._session_input

    @property
    def session_output(self) -> int:
        return self._session_output

    @property
    def session_cost(self) -> float:
        return self._session_cost

    @property
    def total_input(self) -> int:
        return self._data.get("total_input", 0)

    @property
    def total_output(self) -> int:
        return self._data.get("total_output", 0)

    @property
    def total_cost(self) -> float:
        return self._data.get("total_cost", 0.0)
