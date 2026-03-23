import requests

from core.llm.base_provider import LLMProvider, retry_on_transient

OLLAMA_BASE = "http://localhost:11434"


class OllamaProvider(LLMProvider):
    def check(self) -> bool:
        try:
            r = requests.get(OLLAMA_BASE, timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def get_models(self) -> list[str]:
        try:
            r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
            r.raise_for_status()
            data = r.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def chat(self, model: str, messages: list[dict], format_json: bool = False,
             temperature: float = 0.0, num_predict: int = 128, timeout: int = 60,
             thinking: bool = False, num_ctx: int = 8192) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": num_predict},
        }
        if format_json:
            payload["format"] = "json"
        # Disable thinking for models that support it (e.g. qwen3)
        # when not explicitly enabled — prevents wasting tokens on <think> blocks
        if not thinking:
            payload["think"] = False
        payload["options"]["num_ctx"] = num_ctx
        def _do_request():
            resp = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()

        data = retry_on_transient(_do_request)

        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        print(f"[Tokens] prompt={prompt_tokens} completion={completion_tokens} totale={prompt_tokens + completion_tokens}")

        from core.llm.token_tracker import TokenTracker
        TokenTracker().track(model, prompt_tokens, completion_tokens)

        return data.get("message", {}).get("content", "").strip()
