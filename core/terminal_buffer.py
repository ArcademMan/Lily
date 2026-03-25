"""Buffer condiviso per l'output del terminale integrato.

L'UI (PtyBridge) scrive qui, le azioni in core/ leggono da qui.
Evita dipendenze core → ui. Supporta buffer multipli per tab.
"""

import re
import threading
from collections import deque

# Regex per rimuovere sequenze ANSI escape (colori, cursore, ecc.)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b\[[\d;]*[Hf]")

_lock = threading.Lock()
_buffers: dict[str, deque[str]] = {}
_labels: dict[str, str] = {}  # tab_id -> label (es. "PS 1", "Claude Code")
_writers: dict[str, callable] = {}  # tab_id -> write function (from PtyBridge)
_active_tab: str | None = None
_MAX_LINES = 500


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _get_buf(tab_id: str) -> deque[str]:
    if tab_id not in _buffers:
        _buffers[tab_id] = deque(maxlen=_MAX_LINES)
    return _buffers[tab_id]


def append(raw_output: str, tab_id: str = None) -> None:
    """Aggiunge output PTY al buffer, ripulito dai codici ANSI."""
    clean = _strip_ansi(raw_output)
    if not clean.strip():
        return
    tid = tab_id or _active_tab or "_default"
    with _lock:
        buf = _get_buf(tid)
        for line in clean.splitlines():
            buf.append(line)


def get_text(tab_id: str = None, max_lines: int = 100) -> str:
    """Ritorna le ultime N righe di un tab. Se tab_id=None, usa il tab attivo."""
    tid = tab_id or _active_tab or "_default"
    with _lock:
        buf = _buffers.get(tid)
        if not buf:
            return ""
        recent = list(buf)[-max_lines:]
    return "\n".join(recent)


def get_line_count(tab_id: str = None) -> int:
    tid = tab_id or _active_tab or "_default"
    with _lock:
        buf = _buffers.get(tid)
        return len(buf) if buf else 0


def clear(tab_id: str = None) -> None:
    tid = tab_id or _active_tab or "_default"
    with _lock:
        if tid in _buffers:
            _buffers[tid].clear()


def remove_tab(tab_id: str) -> None:
    """Rimuove un buffer tab."""
    with _lock:
        _buffers.pop(tab_id, None)
        _labels.pop(tab_id, None)
        _writers.pop(tab_id, None)


def register_writer(tab_id: str, write_fn: callable) -> None:
    """Registra la funzione di scrittura PTY per un tab."""
    with _lock:
        _writers[tab_id] = write_fn


def write(text: str, tab_id: str = None, press_enter: bool = True) -> bool:
    """Scrive testo nel PTY di un tab. Ritorna True se riuscito."""
    tid = tab_id or _active_tab
    if not tid:
        return False
    with _lock:
        fn = _writers.get(tid)
    if not fn:
        return False
    try:
        fn(text + ("\r" if press_enter else ""))
        return True
    except Exception:
        return False


def set_active(tab_id: str) -> None:
    """Setta il tab attivo."""
    global _active_tab
    _active_tab = tab_id


def set_label(tab_id: str, label: str) -> None:
    """Associa un nome leggibile a un tab."""
    with _lock:
        _labels[tab_id] = label


def get_label(tab_id: str) -> str:
    with _lock:
        return _labels.get(tab_id, tab_id)


def get_active_tab() -> str | None:
    return _active_tab


def list_tabs() -> list[dict]:
    """Ritorna info su tutti i tab: id, label, line_count."""
    with _lock:
        return [
            {"id": tid, "label": _labels.get(tid, tid), "lines": len(buf)}
            for tid, buf in _buffers.items()
        ]
