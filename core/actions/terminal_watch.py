"""Attiva/disattiva il monitoring passivo di un tab del terminale."""

from core.actions.base import Action
from core.i18n import t
from core import terminal_buffer
from core.terminal_watcher import TerminalWatcher


class TerminalWatchAction(Action):
    TOOL_SCHEMA = {
        "name": "terminal_watch",
        "description": "Attiva o disattiva il monitoring di un tab del terminale. Lily avvisera' quando il processo chiede conferma, finisce, o ha errori",
        "parameters": {
            "type": "object",
            "properties": {
                "parameter": {"type": "string", "enum": ["start", "stop"], "description": "start=attiva, stop=disattiva"},
                "tab": {"type": "string", "description": "Nome del tab da monitorare (opzionale, default=attivo)"}
            },
            "required": ["parameter"]
        }
    }

    def execute(self, intent: dict, config, **kwargs) -> str:
        action = intent.get("parameter", "").strip().lower()
        tab_request = intent.get("tab", "").strip()

        # Risolvi tab
        tab_id = self._resolve_tab(tab_request)
        if not tab_id:
            tab_id = terminal_buffer.get_active_tab()
        if not tab_id:
            return t("terminal_watch_no_tab")

        watcher = TerminalWatcher.instance()
        tab_label = terminal_buffer.get_label(tab_id)

        if action == "stop":
            watcher.unwatch(tab_id)
            return t("terminal_watch_stopped", tab=tab_label)

        # Default: start
        watcher.watch(tab_id)
        return t("terminal_watch_started", tab=tab_label)

    @staticmethod
    def _resolve_tab(tab_request: str) -> str | None:
        if not tab_request:
            return None
        tabs = terminal_buffer.list_tabs()
        tab_lower = tab_request.lower()
        for tab in tabs:
            if tab_lower in tab["label"].lower() or tab["id"] == tab_request:
                return tab["id"]
        return None
