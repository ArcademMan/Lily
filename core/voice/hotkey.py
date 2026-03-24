import ctypes
import time

import keyboard
from core.i18n import t_dict
from core.signal import Signal

# Alias per tasti con nomi diversi in base alla lingua di Windows
def _key_aliases() -> dict:
    return t_dict("hotkey_aliases")

_TOGGLE_KEYS = {"caps lock", "capslock"}
VK_CAPITAL = 0x14


class HotkeyManager:
    pressed = Signal()
    released = Signal()

    def __init__(self):
        self._registered = False
        self._hotkey_pressed = False
        self._suppress_caps = False
        self._ignore_until = 0

    def register(self, hotkey: str):
        if self._registered:
            keyboard.unhook_all()
            self._registered = False

        self._hotkey_pressed = False
        self._suppress_caps = hotkey.lower().strip() in _TOGGLE_KEYS

        if self._suppress_caps:
            self._force_caps_off()

        def on_event(event):
            # Ignora eventi sintetici da _force_caps_off
            if time.perf_counter() < self._ignore_until:
                return

            # Costruisci il set di nomi validi per il rilascio
            if "+" in hotkey:
                keys = {k.strip() for k in hotkey.split("+")}
            else:
                keys = {hotkey}
            for alias_key, alias_set in _key_aliases().items():
                if alias_key in keys:
                    keys.update(alias_set)

            if event.event_type == keyboard.KEY_DOWN:
                if keyboard.is_pressed(hotkey) and not self._hotkey_pressed:
                    self._hotkey_pressed = True
                    print("[Hotkey] PREMUTO")
                    self.pressed.emit()
            elif event.event_type == keyboard.KEY_UP:
                if self._hotkey_pressed and event.name in keys:
                    self._hotkey_pressed = False
                    print("[Hotkey] RILASCIATO")
                    self.released.emit()
                    if self._suppress_caps:
                        self._force_caps_off()

        try:
            keyboard.hook(on_event)
            self._registered = True
            if self._suppress_caps:
                print("[Hotkey] Caps Lock usato come hotkey (toggle disabilitato)")
            else:
                print(f"[Hotkey] Registrato: {hotkey}")
        except Exception as e:
            print(f"[Hotkey] Errore registrazione: {e}")

    def _force_caps_off(self):
        """Forza Caps Lock a OFF se è attivo."""
        try:
            if ctypes.windll.user32.GetKeyState(VK_CAPITAL) & 1:
                self._ignore_until = time.perf_counter() + 0.15
                ctypes.windll.user32.keybd_event(VK_CAPITAL, 0x3A, 0, 0)
                ctypes.windll.user32.keybd_event(VK_CAPITAL, 0x3A, 2, 0)
        except Exception:
            pass
