from core.actions.folder import OpenFolderAction
from core.actions.program import OpenProgramAction
from core.actions.website import OpenWebsiteAction
from core.actions.volume import VolumeAction
from core.actions.time_action import TimeAction
from core.actions.close_program import CloseProgramAction
from core.actions.search_files import SearchFilesAction
from core.actions.screenshot import ScreenshotAction
from core.actions.timer_action import TimerAction
from core.actions.chat import ChatAction
from core.actions.media import MediaAction
from core.actions.window_action import WindowAction
from core.actions.type_action import TypeInAction
from core.actions.screen_read import ScreenReadAction
from core.actions.self_config import SelfConfigAction
from core.actions.notes import NotesAction
from core.actions.system_info import SystemInfoAction

_ACTIONS = {
    "open_folder": OpenFolderAction(),
    "open_program": OpenProgramAction(),
    "open_website": OpenWebsiteAction(),
    "volume": VolumeAction(),
    "time": TimeAction(),
    "close_program": CloseProgramAction(),
    "search_files": SearchFilesAction(),
    "screenshot": ScreenshotAction(),
    "timer": TimerAction(),
    "chat": ChatAction(),
    "media": MediaAction(),
    "window": WindowAction(),
    "type_in": TypeInAction(),
    "screen_read": ScreenReadAction(),
    "self_config": SelfConfigAction(),
    "notes": NotesAction(),
    "system_info": SystemInfoAction(),
}


def execute_action(intent: dict, config, memory=None) -> str:
    action_type = intent.get("intent", "unknown")
    action = _ACTIONS.get(action_type)
    if action is None:
        return "Non ho capito cosa vuoi fare."
    # Passa la memoria condivisa alla ChatAction
    if action_type == "chat" and memory is not None:
        return action.execute(intent, config, memory=memory)
    return action.execute(intent, config)
