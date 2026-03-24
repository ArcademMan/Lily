"""Cattura una finestra o porzione di schermo, OCR con Tesseract, e legge/interpreta il contenuto."""

import os

from core.actions.base import Action
from core.i18n import t, t_prompt
from core.llm.brain import generate_chat_response
from core.utils.win32 import find_window_hwnd
from core.utils.screenshot import capture_window
from core.utils.ocr import ocr_image


class ScreenReadAction(Action):
    def execute(self, intent: dict, config, **kwargs) -> str:
        query = intent.get("query", "").strip()
        parameter = intent.get("parameter", "").strip()
        search_terms = intent.get("search_terms", [])
        original_text = intent.get("_original_text", "")

        if not query:
            return t("screen_read_no_window")

        # Trova la finestra
        hwnd = find_window_hwnd(query, search_terms=search_terms)
        if hwnd is None:
            return t("screen_read_window_not_found", query=query)

        # Cattura screenshot
        print(f"[ScreenRead] Cattura finestra: {query}")
        image_path = capture_window(hwnd)
        if image_path is None:
            return t("screen_read_capture_error")

        try:
            # OCR
            tesseract_path = getattr(config, "tesseract_path", "tesseract")
            print(f"[ScreenRead] OCR in corso...")
            ocr_text = ocr_image(image_path, tesseract_path)

            if not ocr_text:
                return t("screen_read_ocr_empty", query=query)

            print(f"[ScreenRead] Testo OCR ({len(ocr_text)} chars): {ocr_text[:200]}...")

            # Usa l'LLM per interpretare/riassumere quello che ha letto
            # in base a cosa l'utente ha chiesto
            prompt = t_prompt("screen_read_prompt", window=query,
                              ocr_text=ocr_text[:2000], user_request=original_text)

            from core.llm import get_provider
            from core.llm.brain import _strip_think_tags, _apply_thinking
            from core.llm.prompts import get_chat_system_prompt

            provider = get_provider(config)
            thinking = getattr(config, "thinking_enabled", False)
            system_prompt = get_chat_system_prompt()
            if not thinking:
                system_prompt = _apply_thinking(system_prompt, config)

            raw = provider.chat(
                model=config.ollama_model,
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
            return response if response else t("screen_read_llm_error")

        finally:
            # Pulisci il file temporaneo
            try:
                os.unlink(image_path)
            except Exception:
                pass
