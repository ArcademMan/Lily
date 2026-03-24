"""Azione memoria: salva/leggi/cancella preferenze persistenti."""

from core.actions.base import Action
from core.i18n import t
from core.memory import add_memory_entry, remove_memory_entry, load_memory, save_memory


class MemoryAction(Action):
    def execute(self, intent: dict, config, **kwargs) -> str:
        param = intent.get("parameter", "").strip().lower()
        query = intent.get("query", "").strip()

        # "leggi la memoria" / "cosa ricordi?"
        if param in ("read", "leggi"):
            content = load_memory()
            if not content:
                return t("memory_empty")
            return t("memory_content", content=content)

        # "svuota la memoria" / "cancella tutta la memoria"
        if param in ("clear", "svuota"):
            save_memory("")
            return t("memory_cleared")

        # "dimentica X" / "rimuovi dalla memoria X"
        if param in ("forget", "dimentica", "rimuovi"):
            if not query:
                return t("memory_forget_no_query")
            if remove_memory_entry(query):
                return t("memory_forgotten", query=query)
            return t("memory_not_found", query=query)

        # "mettilo in memoria" / "salvalo" — usa il contesto dell'ultima azione
        if param in ("save_last", "salva_ultimo"):
            ctx = kwargs.get("_last_action_context", {})
            if not ctx:
                return t("memory_no_context")
            entry = _format_context(ctx, query)
            add_memory_entry(entry)
            return t("memory_saved", entry=entry)

        # Default: salva testo libero come preferenza
        if query:
            add_memory_entry(query)
            return t("memory_saved", entry=query)

        return t("memory_no_query")


def _format_context(ctx: dict, user_note: str = "") -> str:
    """Formatta il contesto azione in modo minimale per la memoria."""
    action_type = ctx.get("type", "")
    query = ctx.get("query", ctx.get("name", ""))
    path = ctx.get("path", "")

    if action_type in ("program", "folder", "search_files"):
        return f"{query} = {path}"
    if action_type == "close_program":
        return f"{query} = {ctx.get('process', '')}"
    return f"{query} = {path}" if path else query
