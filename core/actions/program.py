import os
import subprocess

from core.actions.base import Action, set_action_context
from core.i18n import t
from core.llm.brain import pick_best_result, suggest_retry_terms
from core.search import find_program, expand_search_terms


def _sanitize_ps_query(query: str) -> str:
    """Rimuove caratteri pericolosi per interpolazione in PowerShell."""
    # Permetti solo lettere, cifre, spazi, trattini e punti
    import re
    return re.sub(r"[^\w\s\-.]", "", query, flags=re.UNICODE)


def _try_launch_uwp(query: str) -> str | None:
    """Prova a lanciare un'app UWP tramite il suo AppID."""
    safe_query = _sanitize_ps_query(query)
    if not safe_query:
        return None
    try:
        r = subprocess.run(
            ["powershell", "-c",
             f'Get-StartApps | Where-Object {{ $_.Name -like "*{safe_query}*" }} | Select-Object -First 1 -ExpandProperty AppID'],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        app_id = r.stdout.strip()
        if app_id:
            print(f"[Azione] App UWP trovata: {app_id}")
            os.startfile(f"shell:AppsFolder\\{app_id}")
            return app_id
    except Exception as e:
        print(f"[Azione] Errore ricerca UWP: {e}")
    return None


class OpenProgramAction(Action):
    TOOL_SCHEMA = {
        "name": "open_program",
        "description": "Avvia un programma, app o gioco sul PC",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Nome del programma"},
                "search_terms": {"type": "array", "items": {"type": "string"}, "description": "Nomi alternativi"}
            },
            "required": ["query"]
        }
    }

    def execute(self, intent: dict, config, pick_callback=None, **kwargs) -> str:
        query = intent.get("query", "").strip()
        if not query:
            return t("program_none_specified")

        # Check memoria persistente: se c'è un path salvato, usalo direttamente
        from core.memory import find_memory_path
        saved_path = find_memory_path(query)
        if saved_path and os.path.exists(saved_path):
            print(f"[Memory] Trovato in memoria: {query} -> {saved_path}")
            try:
                os.startfile(saved_path)
                name = os.path.splitext(os.path.basename(saved_path))[0]
                set_action_context(type="program", name=name, path=saved_path, query=query)
                return t("program_launched", name=name)
            except Exception:
                print(f"[Memory] Path in memoria non valido, cerco normalmente...")

        search_terms = intent.get("search_terms", [])
        if query not in search_terms:
            search_terms.insert(0, query)
        search_terms = expand_search_terms(search_terms)

        results = find_program(search_terms, config.es_path)

        # Retry: if nothing found, ask LLM for alternative terms
        if not results:
            user_request = intent.get("_original_text", query)
            retry_terms = suggest_retry_terms(query, search_terms, user_request, config)
            if retry_terms:
                print(f"[Ricerca] Retry con termini: {retry_terms}")
                results = find_program(retry_terms, config.es_path)

        if not results:
            return t("program_not_found", query=query)

        user_request = intent.get("_original_text", query)
        idx, confident = pick_best_result(
            user_request, results, config,
            intent_type=intent.get("intent", ""),
            intent_query=query,
        )
        if not confident and pick_callback and len(results) > 1:
            print(f"[Pick] LLM non sicuro, chiedo all'utente ({len(results)} risultati)")
            user_choice = pick_callback(results, idx)
            if user_choice == -2:
                return t("pick_cancelled_action")
            elif user_choice >= 0:
                idx = user_choice
            elif user_choice == -1:
                return t("program_found_no_match", query=query)

        if idx < 0:
            return t("program_found_no_match", query=query)
        target = results[idx]
        print(f"[Azione] Scelto risultato {idx}: {target}")
        try:
            os.startfile(target)
        except PermissionError:
            # App UWP (WindowsApps) — prova via shell:AppsFolder
            print(f"[Azione] Accesso negato, provo come app UWP...")
            app_id = _try_launch_uwp(query)
            if not app_id:
                return t("program_access_denied", query=query)
        name = os.path.splitext(os.path.basename(target))[0]
        set_action_context(type="program", name=name, path=target, query=query)
        return t("program_launched", name=name)
