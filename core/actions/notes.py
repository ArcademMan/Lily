"""Quick notes vocali: salva, leggi, cancella note con timestamp."""

import json
import os
import re
import threading
from datetime import datetime, date

from core.actions.base import Action
from core.i18n import t, t_set, t_list
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
    TOOL_SCHEMA = {
        "name": "notes",
        "description": "Gestisci note vocali: salva, leggi, cerca, cancella",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Testo della nota o filtro di ricerca"},
                "parameter": {"type": "string", "description": "Vuoto=salva, 'leggi'=leggi, 'cancella'=cancella, 'svuota'=cancella tutto"}
            }
        }
    }

    _READ_CMDS = {"read", "leggi", "mostra", "lista"}
    _DELETE_CMDS = {"delete", "cancella", "rimuovi", "togli"}
    _CLEAR_CMDS = {"clear", "svuota", "cancella_tutto"}

    @classmethod
    def _is_read(cls, param: str) -> bool:
        return param in cls._READ_CMDS

    @classmethod
    def _is_delete(cls, param: str) -> bool:
        return param in cls._DELETE_CMDS

    @classmethod
    def _is_clear(cls, param: str) -> bool:
        return param in cls._CLEAR_CMDS

    def execute(self, intent: dict, config, **kwargs) -> str:
        parameter = intent.get("parameter", "").strip().lower()
        query = intent.get("query", "").strip()

        if self._is_read(parameter):
            return self._read_notes(query)
        elif self._is_delete(parameter):
            return self._delete_note(query)
        elif self._is_clear(parameter):
            return self._clear_notes()
        else:
            text = query or parameter
            if not text:
                return t("notes_nothing_to_save")
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
        return t("notes_saved", text=text)

    def _read_notes(self, query: str) -> str:
        with _lock:
            notes = _load_notes()
        if not notes:
            return t("notes_empty")

        q = query.lower()

        # ── Filtro posizionale: prima / ultima / ultime N ─────────
        first_kw = t_set("note_first_keywords")
        last_kw = t_set("note_last_keywords")
        if q in first_kw:
            return self._speak_note(notes[0])
        if q in last_kw:
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
                return t("notes_none_for_date", label=self._format_date_label(date_filter))
            return self._speak_notes(matched, len(notes),
                                     intro=t("notes_header_date", label=self._format_date_label(date_filter)))

        # ── Filtro per contenuto ──────────────────────────────────
        if q and q not in ("tutte", "tutto", "tutte le note", ""):
            matched = [n for n in notes if q in n["text"].lower()]
            if not matched:
                return t("notes_none_matching", query=query)
            return self._speak_notes(matched, len(notes),
                                     intro=t("notes_found_one", count=len(matched), query=query) if len(matched) == 1
                                     else t("notes_found_many", count=len(matched), query=query))

        # ── Tutte (ultime 5) ─────────────────────────────────────
        return self._speak_notes(notes[-5:], len(notes))

    def _delete_note(self, query: str) -> str:
        if not query:
            return t("notes_delete_no_query")
        with _lock:
            notes = _load_notes()
            query_lower = query.lower()
            remaining = [n for n in notes if query_lower not in n["text"].lower()]
            removed = len(notes) - len(remaining)
            if removed == 0:
                return t("notes_delete_not_found", query=query)
            _save_notes(remaining)
        if removed == 1:
            return t("notes_deleted_one")
        return t("notes_deleted_many", count=removed)

    def _clear_notes(self) -> str:
        with _lock:
            notes = _load_notes()
            count = len(notes)
            if count == 0:
                return t("notes_empty_to_delete")
            _save_notes([])
        if count == 1:
            return t("notes_deleted_one")
        return t("notes_deleted_all", count=count)

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
            intro = t("notes_count_one", count=total) if total == 1 else t("notes_count_many", count=total)
            if len(notes) < total:
                intro += ". " + t("notes_showing_last", count=len(notes))

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
        today_word = t("today")
        yesterday_word = t("yesterday")
        today_prefix = t("note_today_prefix")
        yesterday_prefix = t("note_yesterday_prefix")
        months_list = t_list("months")

        today = date.today()
        if text in (today_word, today_prefix):
            return today
        if text in (yesterday_word, yesterday_prefix):
            from datetime import timedelta
            return today - timedelta(days=1)
        # "20 marzo", "20/03", "20-03"
        months_pattern = "|".join(months_list)
        m = re.match(r"(\d{1,2})[/\-\s]*(0?[1-9]|1[0-2]|" + months_pattern + r")", text)
        if m:
            day = int(m.group(1))
            month_str = m.group(2)
            months_map = {name: i + 1 for i, name in enumerate(months_list)}
            month = months_map.get(month_str, None) or int(month_str)
            try:
                return date(today.year, month, day)
            except ValueError:
                pass
        return None

    @staticmethod
    def _format_date_label(d: date) -> str:
        today = date.today()
        if d == today:
            return t("today")
        from datetime import timedelta
        if d == today - timedelta(days=1):
            return t("yesterday")
        return d.strftime("%d/%m")

    @staticmethod
    def _format_date(iso_str: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_str)
            now = datetime.now()
            if dt.date() == now.date():
                return t("note_time_today", time=dt.strftime('%H:%M'))
            delta = (now.date() - dt.date()).days
            if delta == 1:
                return t("note_time_yesterday", time=dt.strftime('%H:%M'))
            return t("note_time_other", date=dt.strftime('%d/%m'), time=dt.strftime('%H:%M'))
        except Exception:
            return ""
