"""Memoria persistente di Lily: preferenze utente iniettate nel prompt."""

import os
import threading
from datetime import datetime

from config import SETTINGS_DIR

MEMORY_FILE = os.path.join(SETTINGS_DIR, "memory.md")
_lock = threading.Lock()


def _load_unlocked() -> str:
    """Carica memoria senza acquisire il lock (uso interno)."""
    if not os.path.exists(MEMORY_FILE):
        return ""
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        print(f"[Memory] Errore lettura: {e}")
        return ""


def _save_unlocked(content: str):
    """Salva memoria senza acquisire il lock (uso interno)."""
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        tmp = MEMORY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, MEMORY_FILE)
    except Exception as e:
        print(f"[Memory] Errore scrittura: {e}")


def load_memory() -> str:
    """Carica il contenuto della memoria. Ritorna stringa vuota se non esiste."""
    with _lock:
        return _load_unlocked()


def save_memory(content: str):
    """Sovrascrive l'intero contenuto della memoria."""
    with _lock:
        _save_unlocked(content)


def add_memory_entry(entry: str):
    """Aggiunge una riga alla memoria."""
    line = entry.strip()
    with _lock:
        current = _load_unlocked()
        if current:
            new_content = current + "\n" + line
        else:
            new_content = line
        _save_unlocked(new_content)
    print(f"[Memory] Aggiunto: {line}")


def remove_memory_entry(keyword: str) -> bool:
    """Rimuove la prima riga che contiene la keyword. Ritorna True se trovata."""
    with _lock:
        current = _load_unlocked()
        if not current:
            return False
        lines = current.splitlines()
        new_lines = []
        found = False
        for line in lines:
            if not found and keyword.lower() in line.lower():
                found = True
                print(f"[Memory] Rimosso: {line}")
                continue
            new_lines.append(line)
        if found:
            _save_unlocked("\n".join(new_lines))
    return found


def find_memory_path(query: str) -> str | None:
    """Cerca nella memoria un path associato alla query. Formato: 'nome = path'.
    Ritorna il path se trovato, None altrimenti."""
    content = load_memory()
    if not content:
        return None
    query_lower = query.lower().strip()
    for line in content.splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        name_part, path_part = line.split("=", 1)
        if query_lower in name_part.lower().strip():
            path = path_part.strip()
            if path:
                print(f"[Memory] Match: '{query}' -> {path}")
                return path
    return None


def get_memory_for_prompt() -> str:
    """Ritorna la memoria formattata per l'iniezione nel prompt LLM."""
    content = load_memory()
    if not content:
        return ""
    return f"\n\nUSER PREFERENCES (remember these):\n{content}\n"
