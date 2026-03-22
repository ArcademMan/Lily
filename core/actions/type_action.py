"""Azione type_in: scrive testo su una finestra con switch di focus rapido."""

import time

import ctypes
import ctypes.wintypes
import keyboard as kb

from core.actions.base import Action

user32 = ctypes.windll.user32
SW_RESTORE = 9


def _find_window(query: str) -> int | None:
    """Trova hwnd della finestra il cui titolo contiene la query."""
    result = None
    query_lower = query.lower()

    def callback(hwnd, _):
        nonlocal result
        if user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if query_lower in buf.value.lower():
                    result = hwnd
                    return False
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )
    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return result


class TypeInAction(Action):
    def execute(self, intent: dict, config) -> str:
        query = intent.get("query", "").strip()
        parameter = intent.get("parameter", "").strip()

        if not query:
            return "Non hai specificato su quale finestra andare."

        # Trova la finestra
        search_terms = intent.get("search_terms", [])
        candidates = [query] + search_terms
        words = query.split()
        if len(words) > 1:
            for i in range(len(words)):
                sub = " ".join(words[i:])
                if sub not in candidates:
                    candidates.append(sub)

        hwnd = None
        for term in candidates:
            hwnd = _find_window(term)
            if hwnd:
                break

        if hwnd is None:
            return f"Non trovo la finestra {query}."

        window_name = query

        # Solo focus, senza testo
        if not parameter:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            return f"Sono su {window_name}."

        # Controlla se deve inviare
        send = False
        text = parameter
        for suffix in (" e invia", " e premi invio", " invio", " enter"):
            if text.lower().endswith(suffix):
                text = text[:-len(suffix)].strip()
                send = True
                break

        # Salva finestra attuale
        prev_hwnd = user32.GetForegroundWindow()

        # Switch rapido: focus → scrivi → invio → ripristina
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.15)  # Minimo per il focus

        if text:
            # Usa clipboard per incollare istantaneamente invece di digitare
            _clipboard_paste(text)

        if send:
            time.sleep(0.05)
            kb.send("enter")

        time.sleep(0.1)

        # Ripristina focus alla finestra precedente
        if prev_hwnd and prev_hwnd != hwnd:
            user32.SetForegroundWindow(prev_hwnd)

        if send:
            return f"Scritto e inviato su {window_name}."
        if text:
            return f"Scritto su {window_name}."
        return f"Sono su {window_name}."


def _clipboard_paste(text: str):
    """Copia il testo nella clipboard e incolla con Ctrl+V. Molto più veloce di keyboard.write()."""
    import win32clipboard

    # Salva clipboard attuale
    old_clip = None
    try:
        win32clipboard.OpenClipboard()
        try:
            old_clip = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        except Exception:
            pass
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
    except Exception:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass
        # Fallback: usa ctypes
        _clipboard_paste_ctypes(text)
        kb.send("ctrl+v")
        time.sleep(0.05)
        return

    # Incolla
    kb.send("ctrl+v")
    time.sleep(0.05)

    # Ripristina clipboard precedente
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        if old_clip:
            win32clipboard.SetClipboardText(old_clip, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
    except Exception:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


def _clipboard_paste_ctypes(text: str):
    """Fallback clipboard con ctypes se win32clipboard non è disponibile."""
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard(0)
    user32.EmptyClipboard()

    h = kernel32.GlobalAlloc(GMEM_MOVEABLE, (len(text) + 1) * 2)
    p = kernel32.GlobalLock(h)
    ctypes.cdll.msvcrt.wcscpy_s(ctypes.c_wchar_p(p), len(text) + 1, text)
    kernel32.GlobalUnlock(h)
    user32.SetClipboardData(CF_UNICODETEXT, h)
    user32.CloseClipboard()
