import os
import subprocess

from core.actions.base import Action
from core.llm.brain import pick_best_result, suggest_retry_terms
from core.search import find_program, expand_search_terms


def _try_launch_uwp(query: str) -> str | None:
    """Prova a lanciare un'app UWP tramite il suo AppID."""
    try:
        r = subprocess.run(
            ["powershell", "-c",
             f'Get-StartApps | Where-Object {{ $_.Name -like "*{query}*" }} | Select-Object -First 1 -ExpandProperty AppID'],
            capture_output=True, text=True, timeout=5,
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
    def execute(self, intent: dict, config) -> str:
        query = intent.get("query", "").strip()
        if not query:
            return "Nessun programma specificato."

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
            return f"Nessun programma trovato per '{query}'."

        user_request = intent.get("_original_text", query)
        idx = pick_best_result(
            user_request, results, config,
            intent_type=intent.get("intent", ""),
            intent_query=query,
        )
        if idx < 0:
            return f"Trovati programmi ma nessuno corrisponde a '{query}'."
        target = results[idx]
        print(f"[Azione] Scelto risultato {idx}: {target}")
        try:
            os.startfile(target)
        except PermissionError:
            # App UWP (WindowsApps) — prova via shell:AppsFolder
            print(f"[Azione] Accesso negato, provo come app UWP...")
            app_id = _try_launch_uwp(query)
            if not app_id:
                return f"Non riesco ad aprire {query}, accesso negato."
        name = os.path.splitext(os.path.basename(target))[0]
        return f"Avvio {name}."
