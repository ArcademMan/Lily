"""Quick notes vocali: salva, leggi, cancella note con timestamp."""

import json
import os
import re
import threading
from datetime import datetime, date

from core.actions.base import Action
from config import SETTINGS_DIR

_NOTES_FILE = os.path.join(SETTINGS_DIR, "notes.json")
_lock = threading.Lock()


def _load_notes() -> list[dict]:
    if not os.path.exists(_NOTES_FILE):
        return []
    try:
        with open(_NOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return []


def _save_notes(notes: list[dict]):
    os.makedirs(os.path.dirname(_NOTES_FILE), exist_ok=True)
    with open(_NOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)


class NotesAction(Action):
    _READ_CMDS = {"read", "leggi", "mostra", "lista"}
    _DELETE_CMDS = {"delete", "cancella", "rimuovi", "togli"}
    _CLEAR_CMDS = {"clear", "svuota", "cancella_tutto"}

    def execute(self, intent: dict, config) -> str:
        parameter = intent.get("parameter", "").strip().lower()
        query = intent.get("query", "").strip()

        if parameter in self._READ_CMDS:
            return self._read_notes(query)
        elif parameter in self._DELETE_CMDS:
            return self._delete_note(query)
        elif parameter in self._CLEAR_CMDS:
            return self._clear_notes()
        else:
            text = query or parameter
            if not text:
                return "Non ho capito cosa annotare."
            return self._save_note(text)

    def _save_note(self, text: str) -> str:
        with _lock:
            notes = _load_notes()
            notes.append({
                "text": text,
                "created": datetime.now().isoformat(timespec="seconds"),
            })
            _save_notes(notes)
        print(f"[Note] Salvata: {text}")
        return f"Nota salvata: {text}"

    def _read_notes(self, query: str) -> str:
        with _lock:
            notes = _load_notes()
        if not notes:
            return "Non hai nessuna nota."

        q = query.lower()

        # ── Filtro posizionale: prima / ultima / ultime N ─────────
        if q in ("prima", "la prima", "più vecchia"):
            return self._speak_note(notes[0])
        if q in ("ultima", "l'ultima", "più recente"):
            return self._speak_note(notes[-1])

        m = re.match(r"ultim[eai]\s*(\d+)", q)
        if m:
            n = min(int(m.group(1)), len(notes))
            return self._speak_notes(notes[-n:], len(notes))

        # ── Filtro per data: oggi / ieri / data specifica ─────────
        date_filter = self._parse_date_filter(q)
        if date_filter:
            matched = [n for n in notes if self._note_date(n) == date_filter]
            if not matched:
                return f"Nessuna nota per {self._format_date_label(date_filter)}."
            return self._speak_notes(matched, len(notes),
                                     intro=f"Note di {self._format_date_label(date_filter)}")

        # ── Filtro per contenuto ──────────────────────────────────
        if q and q not in ("tutte", "tutto", "tutte le note", ""):
            matched = [n for n in notes if q in n["text"].lower()]
            if not matched:
                return f"Nessuna nota trovata con '{query}'."
            return self._speak_notes(matched, len(notes),
                                     intro=f"Ho trovato {len(matched)} nota" if len(matched) == 1
                                     else f"Ho trovato {len(matched)} note")

        # ── Tutte (ultime 5) ─────────────────────────────────────
        return self._speak_notes(notes[-5:], len(notes))

    def _delete_note(self, query: str) -> str:
        if not query:
            return "Non ho capito quale nota cancellare."
        with _lock:
            notes = _load_notes()
            query_lower = query.lower()
            remaining = [n for n in notes if query_lower not in n["text"].lower()]
            removed = len(notes) - len(remaining)
            if removed == 0:
                return f"Nessuna nota trovata con '{query}'."
            _save_notes(remaining)
        if removed == 1:
            return "Nota cancellata."
        return f"{removed} note cancellate."

    def _clear_notes(self) -> str:
        with _lock:
            notes = _load_notes()
            count = len(notes)
            if count == 0:
                return "Non hai nessuna nota da cancellare."
            _save_notes([])
        if count == 1:
            return "Nota cancellata."
        return f"Tutte le {count} note cancellate."

    # ── Helpers parlabili ─────────────────────────────────────────

    def _speak_note(self, note: dict) -> str:
        when = self._format_date(note["created"])
        return f"{when}: {note['text']}"

    def _speak_notes(self, notes: list[dict], total: int, intro: str = "") -> str:
        parts = []
        for n in notes:
            when = self._format_date(n["created"])
            parts.append(f"{when}, {n['text']}")

        if not intro:
            intro = f"Hai {total} nota" if total == 1 else f"Hai {total} note"
            if len(notes) < total:
                intro += f". Ecco le ultime {len(notes)}"

        return intro + ". " + ". ".join(parts)

    # ── Date helpers ──────────────────────────────────────────────

    @staticmethod
    def _note_date(note: dict) -> date | None:
        try:
            return datetime.fromisoformat(note["created"]).date()
        except Exception:
            return None

    @staticmethod
    def _parse_date_filter(text: str) -> date | None:
        today = date.today()
        if text in ("oggi", "di oggi"):
            return today
        if text in ("ieri", "di ieri"):
            from datetime import timedelta
            return today - timedelta(days=1)
        # "20 marzo", "20/03", "20-03"
        m = re.match(r"(\d{1,2})[/\-\s]*(0?[1-9]|1[0-2]|"
                     r"gennaio|febbraio|marzo|aprile|maggio|giugno|"
                     r"luglio|agosto|settembre|ottobre|novembre|dicembre)", text)
        if m:
            day = int(m.group(1))
            month_str = m.group(2)
            months = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
                      "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
                      "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12}
            month = months.get(month_str, None) or int(month_str)
            try:
                return date(today.year, month, day)
            except ValueError:
                pass
        return None

    @staticmethod
    def _format_date_label(d: date) -> str:
        today = date.today()
        if d == today:
            return "oggi"
        from datetime import timedelta
        if d == today - timedelta(days=1):
            return "ieri"
        return d.strftime("%d/%m")

    @staticmethod
    def _format_date(iso_str: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_str)
            now = datetime.now()
            if dt.date() == now.date():
                return f"oggi alle {dt.strftime('%H:%M')}"
            delta = (now.date() - dt.date()).days
            if delta == 1:
                return f"ieri alle {dt.strftime('%H:%M')}"
            return f"il {dt.strftime('%d/%m')} alle {dt.strftime('%H:%M')}"
        except Exception:
            return ""
