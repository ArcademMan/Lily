import time
from abc import ABC, abstractmethod

import requests


def retry_on_transient(func, max_retries: int = 3, backoff: tuple = (0.5, 1.0, 2.0)):
    """Retry wrapper for network calls. Only retries on transient errors."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            return func()
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
            if attempt < max_retries - 1:
                wait = backoff[min(attempt, len(backoff) - 1)]
                print(f"[Retry] Tentativo {attempt + 1} fallito, riprovo tra {wait}s...")
                time.sleep(wait)
        except requests.HTTPError as e:
            # Only retry on 429 (rate limit) or 5xx (server error)
            if e.response is not None and (e.response.status_code == 429 or e.response.status_code >= 500):
                last_exc = e
                if attempt < max_retries - 1:
                    wait = backoff[min(attempt, len(backoff) - 1)]
                    print(f"[Retry] HTTP {e.response.status_code}, riprovo tra {wait}s...")
                    time.sleep(wait)
            else:
                raise
    raise last_exc


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, model: str, messages: list[dict], format_json: bool = False,
             temperature: float = 0.0, num_predict: int = 128, timeout: int = 60,
             **kwargs) -> str:
        pass

    @abstractmethod
    def check(self) -> bool:
        pass

    @abstractmethod
    def get_models(self) -> list[str]:
        pass
