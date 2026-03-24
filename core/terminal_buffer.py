"""Buffer condiviso per l'output del terminale integrato.

L'UI (PtyBridge) scrive qui, le azioni in core/ leggono da qui.
Evita dipendenze core → ui.
"""

import re
import threading
from collections import deque

# Regex per rimuovere sequenze ANSI escape (colori, cursore, ecc.)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b\[[\d;]*[Hf]")

_lock = threading.Lock()
_lines: deque[str] = deque(maxlen=500)


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def append(raw_output: str) -> None:
    """Aggiunge output PTY al buffer, ripulito dai codici ANSI."""
    clean = _strip_ansi(raw_output)
    if not clean.strip():
        return
    with _lock:
        # Splitta per righe e aggiungi
        for line in clean.splitlines():
            _lines.append(line)


def get_text(max_lines: int = 100) -> str:
    """Ritorna le ultime N righe del terminale come testo."""
    with _lock:
        recent = list(_lines)[-max_lines:]
    return "\n".join(recent)


def get_line_count() -> int:
    with _lock:
        return len(_lines)


def clear() -> None:
    with _lock:
        _lines.clear()
