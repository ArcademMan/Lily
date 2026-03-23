from core.llm.base_provider import LLMProvider
from core.llm.ollama_provider import OllamaProvider
from core.llm.anthropic_provider import AnthropicProvider
from core.llm.openai_provider import OpenAIProvider
from core.llm.gemini_provider import GeminiProvider


def get_provider(config) -> LLMProvider:
    provider_type = getattr(config, "provider", "ollama")
    if provider_type == "anthropic":
        return AnthropicProvider(config.anthropic_api_key, config.anthropic_model)
    if provider_type == "openai":
        return OpenAIProvider(config.openai_api_key, config.openai_model)
    if provider_type == "gemini":
        return GeminiProvider(config.gemini_api_key, config.gemini_model)
    return OllamaProvider()
