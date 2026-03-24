"""Controllo multimedia: play/pausa, traccia successiva/precedente, volume app."""

import ctypes
from core.actions.base import Action
from core.i18n import t

# Virtual key codes per i tasti multimediali di Windows
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002


def _press_media_key(vk_code: int):
    """Simula la pressione di un tasto multimediale."""
    ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY, 0)
    ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)


class MediaAction(Action):
    TOOL_SCHEMA = {
        "name": "media",
        "description": "Controlla la riproduzione multimediale: play/pausa, traccia successiva/precedente, stop",
        "parameters": {
            "type": "object",
            "properties": {
                "parameter": {"type": "string", "enum": ["play_pause", "next", "previous", "stop"]}
            },
            "required": ["parameter"]
        }
    }

    def execute(self, intent: dict, config, **kwargs) -> str:
        parameter = intent.get("parameter", "").strip().lower()

        if parameter in ("play", "pause", "play_pause"):
            _press_media_key(VK_MEDIA_PLAY_PAUSE)
            return t("media_play_pause")

        elif parameter in ("next", "skip", "avanti"):
            _press_media_key(VK_MEDIA_NEXT_TRACK)
            return t("media_next")

        elif parameter in ("previous", "prev", "indietro"):
            _press_media_key(VK_MEDIA_PREV_TRACK)
            return t("media_previous")

        elif parameter == "stop":
            _press_media_key(VK_MEDIA_STOP)
            return t("media_stop")

        return t("media_unknown")
