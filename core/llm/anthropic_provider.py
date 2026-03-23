import json
import requests

from core.llm.base_provider import LLMProvider, retry_on_transient

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001"):
        self.api_key = api_key
        self.model = model

    def check(self) -> bool:
        return bool(self.api_key)

    def get_models(self) -> list[str]:
        return [
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-6-20250514",
        ]

    def chat(self, model: str, messages: list[dict], format_json: bool = False,
             temperature: float = 0.0, num_predict: int = 128, timeout: int = 60, **kwargs) -> str:
        use_model = model or self.model

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        # Convert messages: extract system message, keep the rest
        system_text = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                user_messages.append({"role": msg["role"], "content": msg["content"]})

        # Ensure at least one user message
        if not user_messages:
            user_messages = [{"role": "user", "content": "classify"}]

        payload = {
            "model": use_model,
            "max_tokens": num_predict,
            "temperature": temperature,
            "messages": user_messages,
        }
        if system_text:
            payload["system"] = system_text

        def _do_request():
            resp = requests.post(ANTHROPIC_API_URL, headers=headers, json=payload, timeout=timeout)
            if resp.status_code != 200:
                print(f"[Anthropic] Errore {resp.status_code}: {resp.text}")
            resp.raise_for_status()
            return resp.json()

        data = retry_on_transient(_do_request)

        # Track token usage
        from core.llm.token_tracker import TokenTracker
        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)
        TokenTracker().track(use_model, prompt_tokens, completion_tokens)
        print(f"[Tokens] prompt={prompt_tokens} completion={completion_tokens} totale={prompt_tokens + completion_tokens}")

        # Extract text from content blocks
        content = data.get("content", [])
        texts = [block["text"] for block in content if block.get("type") == "text"]
        return " ".join(texts).strip()
