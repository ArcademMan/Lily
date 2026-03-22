"""Cattura una finestra o porzione di schermo, OCR con Tesseract, e legge/interpreta il contenuto."""

import ctypes
import ctypes.wintypes
import subprocess
import tempfile
import os

from core.actions.base import Action
from core.llm.brain import generate_chat_response

user32 = ctypes.windll.user32


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def _find_window(query: str, search_terms: list[str] = None) -> int | None:
    """Trova hwnd della finestra il cui titolo contiene la query."""
    candidates = [query]
    if search_terms:
        candidates.extend(search_terms)
    words = query.split()
    if len(words) > 1:
        for i in range(len(words)):
            sub = " ".join(words[i:])
            if sub not in candidates:
                candidates.append(sub)

    result = None

    def callback(hwnd, _):
        nonlocal result
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title_lower = buf.value.lower()
                for term in candidates:
                    if term.lower() in title_lower:
                        result = hwnd
                        return False
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
    )
    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return result


def _capture_window(hwnd: int) -> str | None:
    """Cattura screenshot della finestra specifica usando PrintWindow (funziona anche se coperta)."""
    try:
        import ctypes.wintypes

        gdi32 = ctypes.windll.gdi32

        rect = _RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top

        if w <= 0 or h <= 0:
            return None

        # Crea un DC compatibile e un bitmap per la cattura
        hwnd_dc = user32.GetWindowDC(hwnd)
        mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
        bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
        gdi32.SelectObject(mem_dc, bitmap)

        # PrintWindow cattura la finestra anche se coperta
        # Flag 2 = PW_RENDERFULLCONTENT (cattura anche contenuti DX/GL)
        user32.PrintWindow(hwnd, mem_dc, 2)

        # Converti a QPixmap e salva
        from PySide6.QtGui import QImage, QPixmap
        from PySide6.QtWidgets import QApplication

        # Leggi i pixel dal bitmap
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32),
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h  # Top-down
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0  # BI_RGB

        buffer = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mem_dc, bitmap, 0, h, buffer, ctypes.byref(bmi), 0)

        # Cleanup GDI
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(hwnd, hwnd_dc)

        # Crea QImage da buffer (BGRA → salva come PNG)
        img = QImage(buffer, w, h, w * 4, QImage.Format.Format_ARGB32)

        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp_path = tmp.name
        tmp.close()
        img.save(tmp_path, "PNG")
        return tmp_path

    except Exception as e:
        print(f"[ScreenRead] Errore cattura: {e}")
        return None


def _ocr_image(image_path: str, tesseract_path: str, lang: str = "eng") -> str:
    """Esegue OCR su un'immagine con Tesseract."""
    try:
        result = subprocess.run(
            [tesseract_path, image_path, "stdout", "-l", lang, "--psm", "6"],
            capture_output=True, text=True, timeout=15,
        )
        text = result.stdout.strip()
        if result.stderr.strip():
            # Filtra i warning comuni di Tesseract
            for line in result.stderr.strip().splitlines():
                if "warning" not in line.lower() and "estimating" not in line.lower():
                    print(f"[OCR] {line}")
        return text
    except FileNotFoundError:
        print(f"[OCR] Tesseract non trovato: {tesseract_path}")
        return ""
    except Exception as e:
        print(f"[OCR] Errore: {e}")
        return ""


class ScreenReadAction(Action):
    def execute(self, intent: dict, config) -> str:
        query = intent.get("query", "").strip()
        parameter = intent.get("parameter", "").strip()
        search_terms = intent.get("search_terms", [])
        original_text = intent.get("_original_text", "")

        if not query:
            return "Non hai specificato quale finestra leggere."

        # Trova la finestra
        hwnd = _find_window(query, search_terms)
        if hwnd is None:
            return f"Non trovo la finestra {query}."

        # Cattura screenshot
        print(f"[ScreenRead] Cattura finestra: {query}")
        image_path = _capture_window(hwnd)
        if image_path is None:
            return "Errore nella cattura dello schermo."

        try:
            # OCR
            tesseract_path = getattr(config, "tesseract_path", "tesseract")
            print(f"[ScreenRead] OCR in corso...")
            ocr_text = _ocr_image(image_path, tesseract_path)

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
            from core.llm.brain import _strip_think_tags, CHAT_SYSTEM_PROMPT, _apply_thinking

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
