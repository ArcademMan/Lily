import json
import requests

from core.llm.base_provider import LLMProvider, retry_on_transient

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model

    def check(self) -> bool:
        return bool(self.api_key)

    def get_models(self) -> list[str]:
        return [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-5.4-nano",
            "gpt-5.4-mini",
        ]

    def chat(self, model: str, messages: list[dict], format_json: bool = False,
             temperature: float = 0.0, num_predict: int = 128, timeout: int = 60, **kwargs) -> str:
        use_model = model or self.model

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": use_model,
            "max_completion_tokens": num_predict,
            "temperature": temperature,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
        }
        if format_json:
            payload["response_format"] = {"type": "json_object"}

        def _do_request():
            resp = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=timeout)
            if resp.status_code != 200:
                print(f"[OpenAI] Errore {resp.status_code}: {resp.text}")
            resp.raise_for_status()
            return resp.json()

        data = retry_on_transient(_do_request)

        # Track token usage
        from core.llm.token_tracker import TokenTracker
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        TokenTracker().track(use_model, prompt_tokens, completion_tokens)
        print(f"[Tokens] prompt={prompt_tokens} completion={completion_tokens} totale={prompt_tokens + completion_tokens}")

        # Extract text from response
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "").strip()
        return ""
