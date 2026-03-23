import json
import requests

from core.llm.base_provider import LLMProvider, retry_on_transient

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model

    def check(self) -> bool:
        return bool(self.api_key)

    def get_models(self) -> list[str]:
        return [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
        ]

    def chat(self, model: str, messages: list[dict], format_json: bool = False,
             temperature: float = 0.0, num_predict: int = 128, timeout: int = 60, **kwargs) -> str:
        use_model = model or self.model
        url = f"{GEMINI_API_BASE}/{use_model}:generateContent"

        # Convert messages: extract system instruction, build contents
        system_text = ""
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                # Gemini uses "user" and "model" (not "assistant")
                role = "model" if msg["role"] == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        if not contents:
            contents = [{"role": "user", "parts": [{"text": "classify"}]}]

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": num_predict,
            },
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}
        if format_json:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        def _do_request():
            resp = requests.post(
                url,
                headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
                json=payload,
                timeout=timeout,
            )
            if resp.status_code != 200:
                print(f"[Gemini] Errore {resp.status_code}: {resp.text}")
            resp.raise_for_status()
            return resp.json()

        data = retry_on_transient(_do_request)

        # Track token usage
        from core.llm.token_tracker import TokenTracker
        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)
        TokenTracker().track(use_model, prompt_tokens, completion_tokens)
        print(f"[Tokens] prompt={prompt_tokens} completion={completion_tokens} totale={prompt_tokens + completion_tokens}")

        # Extract text from response
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            texts = [p["text"] for p in parts if "text" in p]
            return " ".join(texts).strip()
        return ""
