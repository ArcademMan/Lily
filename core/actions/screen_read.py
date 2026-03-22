"""Cattura una finestra o porzione di schermo, OCR con Tesseract, e legge/interpreta il contenuto."""

import os

from core.actions.base import Action
from core.llm.brain import generate_chat_response
from core.utils.win32 import find_window_hwnd
from core.utils.screenshot import capture_window
from core.utils.ocr import ocr_image


class ScreenReadAction(Action):
    def execute(self, intent: dict, config) -> str:
        query = intent.get("query", "").strip()
        parameter = intent.get("parameter", "").strip()
        search_terms = intent.get("search_terms", [])
        original_text = intent.get("_original_text", "")

        if not query:
            return "Non hai specificato quale finestra leggere."

        # Trova la finestra
        hwnd = find_window_hwnd(query, search_terms=search_terms)
        if hwnd is None:
            return f"Non trovo la finestra {query}."

        # Cattura screenshot
        print(f"[ScreenRead] Cattura finestra: {query}")
        image_path = capture_window(hwnd)
        if image_path is None:
            return "Errore nella cattura dello schermo."

        try:
            # OCR
            tesseract_path = getattr(config, "tesseract_path", "tesseract")
            print(f"[ScreenRead] OCR in corso...")
            ocr_text = ocr_image(image_path, tesseract_path)

            if not ocr_text:
                return f"Non riesco a leggere il testo sulla finestra {query}."

            print(f"[ScreenRead] Testo OCR ({len(ocr_text)} chars): {ocr_text[:200]}...")

            # Usa l'LLM per interpretare/riassumere quello che ha letto
            # in base a cosa l'utente ha chiesto
            prompt = f"""L'utente ha chiesto: "{original_text}"

Ho catturato lo schermo della finestra "{query}" e questo è il testo OCR (potrebbe essere impreciso):
---
{ocr_text[:2000]}
---

REGOLE:
- Rispondi SOLO alla domanda dell'utente, in massimo 1-2 frasi
- NON ripetere il testo OCR, riassumi e interpreta
- Se chiede "ultimo messaggio" o "chi ha scritto", cerca nomi di persone e messaggi nel testo
- Il testo verrà letto ad alta voce, sii breve e chiaro"""

            from core.llm import get_provider
            from core.llm.brain import _strip_think_tags, _apply_thinking
            from core.llm.prompts import CHAT_SYSTEM_PROMPT

            provider = get_provider(config)
            thinking = getattr(config, "thinking_enabled", False)
            system_prompt = CHAT_SYSTEM_PROMPT
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
            return response if response else f"Ho letto il testo ma non riesco a rispondere."

        finally:
            # Pulisci il file temporaneo
            try:
                os.unlink(image_path)
            except Exception:
                pass
