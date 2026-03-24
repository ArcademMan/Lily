"""Utilità Win32 condivise per la gestione delle finestre."""

import ctypes
import ctypes.wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def get_windows(include_minimized: bool = False) -> list[dict]:
    """Enumera finestre con titolo. Se include_minimized, include anche quelle minimizzate."""
    windows = []

    def callback(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True

        visible = user32.IsWindowVisible(hwnd)
        minimized = user32.IsIconic(hwnd)

        if not visible and not minimized:
            return True
        if minimized and not include_minimized:
            return True

        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buf, 256)

        # Recupera nome processo (exe) tramite PID
        exe = ""
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value:
            handle = kernel32.OpenProcess(
                _PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
            )
            if handle:
                exe_buf = ctypes.create_unicode_buffer(260)
                exe_size = ctypes.wintypes.DWORD(260)
                if kernel32.QueryFullProcessImageNameW(
                    handle, 0, exe_buf, ctypes.byref(exe_size)
                ):
                    exe = exe_buf.value.rsplit("\\", 1)[-1]
                kernel32.CloseHandle(handle)

        windows.append({
            "hwnd": hwnd,
            "title": buf.value,
            "class": cls_buf.value,
            "minimized": bool(minimized),
            "exe": exe,
        })
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )
    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return windows


def find_window(query: str, search_terms: list[str] = None,
                include_minimized: bool = False) -> dict | None:
    """Trova una finestra il cui titolo contiene la query o uno dei search_terms.

    Ritorna dict con hwnd, title, class, minimized oppure None.
    """
    candidates = [query]
    if search_terms:
        candidates.extend(search_terms)
    # Aggiungi sottostringhe
    words = query.split()
    if len(words) > 1:
        for i in range(len(words)):
            sub = " ".join(words[i:])
            if sub not in candidates:
                candidates.append(sub)

    windows = get_windows(include_minimized=include_minimized)

    # Prima priorità: match per titolo finestra
    for term in candidates:
        term_lower = term.lower()
        for w in windows:
            if term_lower in w["title"].lower():
                return w

    # Fallback: match per nome processo (senza .exe)
    for term in candidates:
        term_lower = term.lower()
        for w in windows:
            exe_stem = w.get("exe", "").lower().removesuffix(".exe")
            if exe_stem and term_lower in exe_stem:
                return w

    return None


def find_window_hwnd(query: str, search_terms: list[str] = None,
                     include_minimized: bool = True) -> int | None:
    """Trova l'hwnd di una finestra. Convenience wrapper attorno a find_window.

    Di default include anche le finestre minimizzate (compatibilità con type_action).
    """
    result = find_window(query, search_terms=search_terms,
                         include_minimized=include_minimized)
    return result["hwnd"] if result else None
