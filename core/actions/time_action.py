from datetime import datetime

from core.actions.base import Action
from core.i18n import t


class TimeAction(Action):
    TOOL_SCHEMA = {
        "name": "time",
        "description": "Restituisce ora e data corrente",
        "parameters": {"type": "object", "properties": {}}
    }

    def execute(self, intent: dict, config, **kwargs) -> str:
        now = datetime.now()
        return t("time_response", time=now.strftime('%H:%M'), date=now.strftime('%A %d %B %Y'))
