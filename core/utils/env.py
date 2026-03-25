"""Utility per ottenere un environment pulito per processi figli.

Quando l'app gira come exe PyInstaller, PATH viene inquinato con
_internal/ (che contiene DLL CUDA, vcruntime, libcrypto, ecc.).
PowerShell eredita queste DLL e fallisce con 0xc00000142.
clean_env() ricostruisce un PATH di sistema pulito.
"""

import os
import sys
import winreg

_clean_cache: dict | None = None


def _get_system_path() -> str:
    """Legge il PATH di sistema + utente dal registro e espande le variabili."""
    parts = []
    # PATH di sistema
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment") as key:
            val, reg_type = winreg.QueryValueEx(key, "Path")
            if reg_type == winreg.REG_EXPAND_SZ:
                val = winreg.ExpandEnvironmentStrings(val)
            parts.append(val)
    except OSError:
        pass
    # PATH utente
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            val, reg_type = winreg.QueryValueEx(key, "Path")
            if reg_type == winreg.REG_EXPAND_SZ:
                val = winreg.ExpandEnvironmentStrings(val)
            parts.append(val)
    except OSError:
        pass
    return ";".join(parts) if parts else os.environ.get("PATH", "")


def clean_env() -> dict[str, str]:
    """Ritorna una copia di os.environ con il PATH originale di sistema."""
    global _clean_cache
    if _clean_cache is not None:
        return dict(_clean_cache)

    env = os.environ.copy()

    if getattr(sys, "frozen", False):
        env["PATH"] = _get_system_path()

    _clean_cache = env
    return dict(env)
