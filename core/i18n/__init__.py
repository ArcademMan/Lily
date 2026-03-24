"""Localization module for Lily. Provides t(), t_set(), t_prompt() accessors."""

import importlib

_locales: dict[str, dict] = {}
_current: dict = {}
_current_lang: str = "it"


def set_locale(lang: str):
    """Set the active locale (e.g. 'it', 'en')."""
    global _current, _current_lang
    if lang not in _locales:
        mod = importlib.import_module(f"core.i18n.{lang}")
        _locales[lang] = mod.STRINGS
    _current = _locales[lang]
    _current_lang = lang


def get_locale() -> str:
    """Return current locale code."""
    return _current_lang


def t(key: str, **kwargs) -> str:
    """Get translated string, with optional .format() placeholders."""
    val = _current.get(key, f"[missing:{key}]")
    if isinstance(val, str) and kwargs:
        return val.format(**kwargs)
    return val


def t_set(key: str) -> set:
    """Get a set of keywords (e.g. yes/no words, stop words)."""
    return _current.get(key, set())


def t_list(key: str) -> list:
    """Get a list value (e.g. months, hallucination words)."""
    return _current.get(key, [])


def t_dict(key: str) -> dict:
    """Get a dict value (e.g. TTS voices, setting aliases)."""
    return _current.get(key, {})


def t_prompt(key: str, **kwargs) -> str:
    """Get a prompt template. If the value is callable, call it with kwargs."""
    val = _current.get(key, f"[missing prompt:{key}]")
    if callable(val):
        return val(**kwargs)
    if isinstance(val, str) and kwargs:
        return val.format(**kwargs)
    return val


# Auto-init with Italian
set_locale("it")
