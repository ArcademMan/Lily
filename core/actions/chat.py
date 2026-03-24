"""Azione chat: risponde a domande generiche e conversazione."""

from core.actions.base import Action
from core.i18n import t
from core.llm.brain import generate_chat_response


class ChatAction(Action):
    def execute(self, intent: dict, config, memory=None, **kwargs) -> str:
        user_text = intent.get("_original_text", "") or intent.get("query", "")
        if not user_text:
            return t("chat_error")

        history = memory.get_messages() if memory else []
        response = generate_chat_response(user_text, history, config)

        return response
