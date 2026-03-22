"""OCR con Tesseract."""

import subprocess


def ocr_image(image_path: str, tesseract_path: str, lang: str = "eng") -> str:
    """Esegue OCR su un'immagine con Tesseract. Ritorna il testo estratto."""
    try:
        result = subprocess.run(
            [tesseract_path, image_path, "stdout", "-l", lang, "--psm", "6"],
            capture_output=True, text=True, timeout=15,
        )
        text = result.stdout.strip()
        if result.stderr.strip():
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
