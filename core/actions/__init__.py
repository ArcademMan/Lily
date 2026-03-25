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
from core.actions.memory_action import MemoryAction
from core.actions.run_command import RunCommandAction
from core.actions.terminal_read import TerminalReadAction
from core.actions.terminal_write import TerminalWriteAction
from core.actions.terminal_watch import TerminalWatchAction

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
    "save_memory": MemoryAction(),
    "run_command": RunCommandAction(),
    "terminal_read": TerminalReadAction(),
    "terminal_write": TerminalWriteAction(),
    "terminal_watch": TerminalWatchAction(),
}


def get_tool_schemas() -> list[dict]:
    """Collect TOOL_SCHEMA from all actions that define one."""
    return [a.TOOL_SCHEMA for a in _ACTIONS.values() if a.TOOL_SCHEMA]


def execute_action(intent: dict, config, memory=None, pick_callback=None,
                   last_action_ctx: dict = None, confirm_callback=None) -> str:
    action_type = intent.get("intent", "unknown")
    action = _ACTIONS.get(action_type)
    if action is None:
        return "Non ho capito cosa vuoi fare."

    kwargs = {}
    if memory is not None:
        kwargs["memory"] = memory
    if pick_callback is not None:
        kwargs["pick_callback"] = pick_callback
    if last_action_ctx is not None:
        kwargs["_last_action_context"] = last_action_ctx
    if confirm_callback is not None:
        kwargs["confirm_callback"] = confirm_callback

    return action.execute(intent, config, **kwargs)
