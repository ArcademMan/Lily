import requests
from config import Config

config = Config()
key = config.anthropic_api_key
print(f"Key: {key[:12]}...")

r = requests.post(
    "https://api.anthropic.com/v1/messages",
    headers={
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    },
    json={
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 10,
        "messages": [{"role": "user", "content": "hi"}],
    },
)
print(f"Status: {r.status_code}")
print(f"Response: {r.text}")
