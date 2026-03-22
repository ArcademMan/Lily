"""Azione chat: risponde a domande generiche e conversazione."""

from core.actions.base import Action
from core.llm.brain import generate_chat_response


class ChatAction(Action):
    def execute(self, intent: dict, config, memory=None) -> str:
        user_text = intent.get("_original_text", "") or intent.get("query", "")
        if not user_text:
            return "Non ho capito la domanda."

        history = memory.get_messages() if memory else []
        response = generate_chat_response(user_text, history, config)

        return response
