"""Utility clipboard: copia e incolla testo via Win32."""

import time
import ctypes
import ctypes.wintypes

import keyboard as kb

user32 = ctypes.windll.user32


def clipboard_paste(text: str):
    """Copia il testo nella clipboard e incolla con Ctrl+V."""
    try:
        import win32clipboard

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
            _clipboard_paste_ctypes(text)
            kb.send("ctrl+v")
            time.sleep(0.05)
            return

        kb.send("ctrl+v")
        time.sleep(0.05)

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

    except ImportError:
        _clipboard_paste_ctypes(text)
        kb.send("ctrl+v")
        time.sleep(0.05)


def copy_to_clipboard(text: str):
    """Copia testo nella clipboard SENZA incollare."""
    try:
        import win32clipboard
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return
        except Exception:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
    except ImportError:
        pass

    # Fallback ctypes
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard(0)
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, (len(text) + 1) * 2)
        p = kernel32.GlobalLock(h)
        ctypes.cdll.msvcrt.wcscpy_s(ctypes.c_wchar_p(p), len(text) + 1, text)
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_UNICODETEXT, h)
    finally:
        user32.CloseClipboard()


def _clipboard_paste_ctypes(text: str):
    """Fallback clipboard con ctypes."""
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard(0)
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, (len(text) + 1) * 2)
        p = kernel32.GlobalLock(h)
        ctypes.cdll.msvcrt.wcscpy_s(ctypes.c_wchar_p(p), len(text) + 1, text)
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_UNICODETEXT, h)
    finally:
        user32.CloseClipboard()
