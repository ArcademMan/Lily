"""Gestione finestre: chiudi cartelle, minimizza, ripristina, snap, sposta monitor."""

import ctypes
import ctypes.wintypes

import keyboard as kb

from core.actions.base import Action
from core.i18n import t
from core.utils.win32 import get_windows, find_window

user32 = ctypes.windll.user32

WM_CLOSE = 0x0010
SW_RESTORE = 9
SW_MINIMIZE = 6
SW_SHOW = 5
MONITOR_DEFAULTTONEAREST = 0x00000002


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", _RECT),
                ("rcWork", _RECT), ("dwFlags", ctypes.c_ulong)]



def _get_monitors() -> list[_RECT]:
    """Restituisce le aree di lavoro di tutti i monitor."""
    monitors = []

    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        user32.GetMonitorInfoW(hMonitor, ctypes.byref(info))
        monitors.append(info.rcWork)
        return True

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong,
        ctypes.POINTER(_RECT), ctypes.c_double
    )
    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(callback), 0)
    return monitors


class WindowAction(Action):
    TOOL_SCHEMA = {
        "name": "window",
        "description": "Gestisci finestre: chiudi cartelle, minimizza, snap, sposta monitor, ripristina, nudge",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Nome del programma (per snap/move/minimize/restore/nudge)"},
                "parameter": {"type": "string", "description": "close_explorer/minimize_all/show_desktop/snap_left/snap_right/move_monitor/restore/minimize/close_all/nudge_DIRECTION_PIXELS (es. nudge_left_175, nudge_up_200, default 50px)"}
            },
            "required": ["parameter"]
        }
    }

    def execute(self, intent: dict, config, **kwargs) -> str:
        parameter = intent.get("parameter", "").strip().lower()
        query = intent.get("query", "").strip()
        terms = intent.get("search_terms", [])

        if parameter == "close_explorer":
            return self._close_explorer()
        elif parameter in ("minimize_all", "show_desktop"):
            kb.send("win+d")
            return t("window_all_minimized")
        elif parameter == "snap_left":
            return self._snap(query, "left", terms)
        elif parameter == "snap_right":
            return self._snap(query, "right", terms)
        elif parameter == "move_monitor":
            return self._move_to_other_monitor(query, terms)
        elif parameter == "restore":
            return self._restore(query, terms)
        elif parameter == "minimize":
            return self._minimize(query, terms)
        elif parameter == "close_all":
            return self._close_all()
        elif parameter.startswith("nudge_"):
            return self._nudge(query, parameter, terms)

        return t("window_unknown_command")

    def _close_explorer(self) -> str:
        closed = 0
        for w in get_windows():
            if w["class"] == "CabinetWClass":
                user32.PostMessageW(w["hwnd"], WM_CLOSE, 0, 0)
                closed += 1
        if closed == 0:
            return t("window_no_folders")
        return t("window_folders_closed_many", count=closed) if closed > 1 else t("window_folders_closed_one")

    def _snap(self, query: str, direction: str, terms: list[str] = None) -> str:
        if not query:
            return t("window_no_query")

        target = find_window(query, search_terms=terms)
        if not target:
            return t("window_not_found", query=query)

        hwnd = target["hwnd"]
        user32.SetForegroundWindow(hwnd)
        user32.ShowWindow(hwnd, SW_RESTORE)

        # Usa il monitor dove si trova la finestra
        hMonitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        user32.GetMonitorInfoW(hMonitor, ctypes.byref(info))
        work = info.rcWork

        mon_w = work.right - work.left
        mon_h = work.bottom - work.top

        if direction == "left":
            x, y, w, h = work.left, work.top, mon_w // 2, mon_h
        else:
            x, y, w, h = work.left + mon_w // 2, work.top, mon_w // 2, mon_h

        user32.MoveWindow(hwnd, x, y, w, h, True)
        lato = t("window_snap_left") if direction == "left" else t("window_snap_right")
        return t("window_snapped", side=lato)

    def _move_to_other_monitor(self, query: str, terms: list[str] = None) -> str:
        if not query:
            return t("window_no_query")

        target = find_window(query, include_minimized=True, search_terms=terms)
        if not target:
            return t("window_not_found", query=query)

        monitors = _get_monitors()
        if len(monitors) < 2:
            return t("window_single_monitor")

        hwnd = target["hwnd"]
        user32.ShowWindow(hwnd, SW_RESTORE)

        # Trova su quale monitor è la finestra
        rect = _RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        win_cx = (rect.left + rect.right) // 2
        win_cy = (rect.top + rect.bottom) // 2

        current_idx = 0
        for i, mon in enumerate(monitors):
            if mon.left <= win_cx <= mon.right and mon.top <= win_cy <= mon.bottom:
                current_idx = i
                break

        # Sposta sul prossimo monitor
        next_idx = (current_idx + 1) % len(monitors)
        next_mon = monitors[next_idx]

        # Mantieni le stesse dimensioni relative
        win_w = rect.right - rect.left
        win_h = rect.bottom - rect.top
        new_x = next_mon.left + (next_mon.right - next_mon.left - win_w) // 2
        new_y = next_mon.top + (next_mon.bottom - next_mon.top - win_h) // 2

        user32.MoveWindow(hwnd, new_x, new_y, win_w, win_h, True)
        user32.SetForegroundWindow(hwnd)
        return t("window_moved_monitor")

    def _restore(self, query: str, terms: list[str] = None) -> str:
        if not query:
            return t("window_no_restore_query")

        target = find_window(query, include_minimized=True, search_terms=terms)
        if not target:
            return t("window_not_found", query=query)

        hwnd = target["hwnd"]
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        return t("window_restored", name=query)

    def _minimize(self, query: str, terms: list[str] = None) -> str:
        if not query:
            return t("window_no_minimize_query")

        target = find_window(query, search_terms=terms)
        if not target:
            return t("window_not_found", query=query)

        user32.ShowWindow(target["hwnd"], SW_MINIMIZE)
        return t("window_minimized", query=query)

    def _nudge(self, query: str, parameter: str, terms: list[str] = None) -> str:
        if not query:
            return t("window_no_nudge_query")

        target = find_window(query, search_terms=terms)
        if not target:
            return t("window_not_found", query=query)

        hwnd = target["hwnd"]
        rect = _RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        x = rect.left
        y = rect.top
        w = rect.right - rect.left
        h = rect.bottom - rect.top

        # Estrai pixels dal parameter (es. "nudge_down_100" → 100px)
        parts = parameter.split("_")
        # Default 50px
        pixels = 50
        for p in parts:
            if p.isdigit():
                pixels = int(p)

        direction = parameter.replace("nudge_", "").rstrip("_0123456789")

        if direction == "up":
            y -= pixels
        elif direction == "down":
            y += pixels
        elif direction == "left":
            x -= pixels
        elif direction == "right":
            x += pixels

        user32.MoveWindow(hwnd, x, y, w, h, True)
        return t("window_nudged", pixels=pixels)

    def _close_all(self) -> str:
        skip_classes = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW"}
        closed = 0
        for w in get_windows():
            if w["class"] in skip_classes:
                continue
            if "lily" in w["title"].lower():
                continue
            user32.PostMessageW(w["hwnd"], WM_CLOSE, 0, 0)
            closed += 1
        if closed == 0:
            return t("window_no_close_target")
        return t("window_closed_many", count=closed)
