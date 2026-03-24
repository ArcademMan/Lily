"""Azione type_in: scrive testo su una finestra con switch di focus rapido."""

import time

import ctypes
import ctypes.wintypes
import keyboard as kb

from core.actions.base import Action
from core.i18n import t
from core.utils.win32 import find_window_hwnd
from core.utils.clipboard import clipboard_paste

user32 = ctypes.windll.user32
SW_RESTORE = 9


class TypeInAction(Action):
    def execute(self, intent: dict, config, **kwargs) -> str:
        query = intent.get("query", "").strip()
        parameter = intent.get("parameter", "").strip()

        if not query:
            return t("type_no_window")

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
            hwnd = find_window_hwnd(term)
            if hwnd:
                break

        if hwnd is None:
            return t("type_window_not_found", query=query)

        window_name = query

        # Solo focus, senza testo
        if not parameter:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            return t("type_focused", name=window_name)

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
            clipboard_paste(text)

        if send:
            time.sleep(0.2)
            kb.send("enter")

        time.sleep(0.2)

        # Ripristina focus alla finestra precedente
        if prev_hwnd and prev_hwnd != hwnd:
            user32.SetForegroundWindow(prev_hwnd)

        if send:
            return t("type_sent", name=window_name)
        if text:
            return t("type_written", name=window_name)
        return t("type_focused", name=window_name)
