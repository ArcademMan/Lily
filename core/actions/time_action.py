from datetime import datetime

from core.actions.base import Action


class TimeAction(Action):
    def execute(self, intent: dict, config) -> str:
        now = datetime.now()
        return f"Sono le {now.strftime('%H:%M')} di {now.strftime('%A %d %B %Y')}."
