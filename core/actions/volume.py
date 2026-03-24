from ctypes import cast, POINTER

from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

from core.actions.base import Action
from core.i18n import t

VOLUME_STEP = 0.1


def _get_volume_interface():
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


class VolumeAction(Action):
    def execute(self, intent: dict, config, **kwargs) -> str:
        parameter = intent.get("parameter", "").strip()
        try:
            vol = _get_volume_interface()
            if parameter == "up":
                current = vol.GetMasterVolumeLevelScalar()
                new = min(1.0, current + VOLUME_STEP)
                vol.SetMasterVolumeLevelScalar(new, None)
                return t("volume_level", level=int(new * 100))
            elif parameter == "down":
                current = vol.GetMasterVolumeLevelScalar()
                new = max(0.0, current - VOLUME_STEP)
                vol.SetMasterVolumeLevelScalar(new, None)
                return t("volume_level", level=int(new * 100))
            elif parameter == "mute":
                muted = vol.GetMute()
                vol.SetMute(not muted, None)
                return t("volume_unmuted") if muted else t("volume_muted")
            else:
                return t("volume_unknown_param", parameter=parameter)
        except Exception as e:
            return t("volume_error", e=e)
