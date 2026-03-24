"""Legge il contenuto del terminale integrato e lo interpreta via LLM."""

from core.actions.base import Action
from core.i18n import t, t_prompt
from core import terminal_buffer


class TerminalReadAction(Action):
    TOOL_SCHEMA = {
        "name": "terminal_read",
        "description": "Leggi l'output del terminale integrato di Lily e interpreta il contenuto",
        "parameters": {
            "type": "object",
            "properties": {
                "parameter": {"type": "string", "description": "Cosa cercare nell'output (opzionale)"}
            },
            "required": []
        }
    }

    def execute(self, intent: dict, config, **kwargs) -> str:
        parameter = intent.get("parameter", "").strip()
        original_text = intent.get("_original_text", "")

        text = terminal_buffer.get_text(max_lines=80)
        if not text.strip():
            return t("terminal_read_empty")

        # Costruisci prompt per l'LLM
        prompt = t_prompt("terminal_read_prompt",
                          terminal_text=text[-3000:],
                          user_request=original_text or parameter)

        from core.llm import get_provider
        from core.llm.brain import _strip_think_tags, _apply_thinking, _get_model
        from core.llm.prompts import get_chat_system_prompt

        provider = get_provider(config)
        model = _get_model(config)
        thinking = getattr(config, "thinking_enabled", False)
        system_prompt = get_chat_system_prompt()
        if not thinking:
            system_prompt = _apply_thinking(system_prompt, config)

        try:
            raw = provider.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                format_json=False,
                temperature=0.5,
                num_predict=getattr(config, "chat_num_predict", 384),
                timeout=30,
                thinking=thinking,
            )
            response = _strip_think_tags(raw).strip()
            return response if response else t("terminal_read_llm_error")
        except Exception as e:
            print(f"[TerminalRead] Errore LLM: {e}")
            return t("terminal_read_llm_error")
