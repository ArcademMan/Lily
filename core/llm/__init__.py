from core.llm.base_provider import LLMProvider
from core.llm.ollama_provider import OllamaProvider
from core.llm.anthropic_provider import AnthropicProvider


def get_provider(config) -> LLMProvider:
    provider_type = getattr(config, "provider", "ollama")
    if provider_type == "anthropic":
        return AnthropicProvider(config.anthropic_api_key, config.anthropic_model)
    return OllamaProvider()
