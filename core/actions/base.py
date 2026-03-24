from abc import ABC, abstractmethod

# Contesto dell'ultima azione eseguita — usato per la memoria arricchita
_last_context: dict = {}


def set_action_context(**ctx):
    """Chiamato dalle azioni per salvare dettagli (path, intent, query, ecc.)."""
    _last_context.clear()
    _last_context.update(ctx)


def get_action_context() -> dict:
    """Ritorna il contesto dell'ultima azione e lo resetta."""
    ctx = dict(_last_context)
    _last_context.clear()
    return ctx


class Action(ABC):
    @abstractmethod
    def execute(self, intent: dict, config, **kwargs) -> str:
        pass
