"""Prompt templates — thin wrappers around i18n locale strings."""

from core.i18n import t_prompt


def get_classify_prompt(provider_type: str) -> str:
    key = "classify_ollama" if provider_type == "ollama" else "classify_cloud"
    return t_prompt(key)


def get_pick_prompt(provider_type: str) -> str:
    key = "pick_ollama" if provider_type == "ollama" else "pick_cloud"
    return t_prompt(key)


def get_retry_prompt() -> str:
    return t_prompt("retry_prompt")


def get_chain_prompt() -> str:
    return t_prompt("chain_prompt")


def get_chat_system_prompt() -> str:
    return t_prompt("chat_system")


def get_screen_read_prompt() -> str:
    return t_prompt("screen_read_prompt")
