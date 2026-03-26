"""Scrive testo nel terminale integrato di Lily."""

from core.actions.base import Action
from core.i18n import t
from core import terminal_buffer


class TerminalWriteAction(Action):
    TOOL_SCHEMA = {
        "name": "terminal_write",
        "description": "Scrivi testo/comando nel terminale integrato di Lily. Utile per interagire con processi in esecuzione (es. Claude Code)",
        "parameters": {
            "type": "object",
            "properties": {
                "parameter": {"type": "string", "description": "Testo da scrivere nel terminale"},
                "tab": {"type": "string", "description": "Nome del tab (opzionale, default=attivo)"},
                "enter": {"type": "boolean", "description": "Premi invio dopo il testo (default=true)"}
            },
            "required": ["parameter"]
        }
    }

    def execute(self, intent: dict, config, **kwargs) -> str:
        text = intent.get("parameter", "").strip()
        if not text:
            return t("terminal_write_empty")

        tab_request = intent.get("tab", "").strip()
        press_enter = intent.get("enter", True)

        # Risolvi tab
        tab_id = None
        if tab_request:
            tabs = terminal_buffer.list_tabs()
            tab_lower = tab_request.lower()
            for tab in tabs:
                if tab_lower in tab["label"].lower() or tab["id"] == tab_request:
                    tab_id = tab["id"]
                    break

        ok = terminal_buffer.write(text, tab_id=tab_id, press_enter=press_enter)
        if not ok:
            return t("terminal_write_no_session")

        tab_label = terminal_buffer.get_label(tab_id) if tab_id else "attivo"
        return t("terminal_write_ok", tab=tab_label)
