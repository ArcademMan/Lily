import os

from core.actions.base import Action
from core.llm.brain import pick_best_result, suggest_retry_terms
from core.search import search_everything, expand_search_terms


class OpenFolderAction(Action):
    def execute(self, intent: dict, config) -> str:
        query = intent.get("query", "").strip()
        if not query:
            return "Nessun nome cartella specificato."

        search_terms = intent.get("search_terms", [])
        if query not in search_terms:
            search_terms.insert(0, query)
        search_terms = expand_search_terms(search_terms)

        all_results = self._search(search_terms, config.es_path)

        # Retry: if nothing found, ask LLM for alternative terms
        if not all_results:
            user_request = intent.get("_original_text", query)
            retry_terms = suggest_retry_terms(query, search_terms, user_request, config)
            if retry_terms:
                print(f"[Ricerca] Retry con termini: {retry_terms}")
                all_results = self._search(retry_terms, config.es_path)

        if not all_results:
            return f"Nessuna cartella trovata per '{query}'."

        user_request = intent.get("_original_text", query)
        idx = pick_best_result(
            user_request, all_results, config,
            intent_type=intent.get("intent", ""),
            intent_query=query,
        )
        if idx < 0:
            return f"Trovate cartelle ma nessuna corrisponde a '{query}'."
        folder = all_results[idx]
        print(f"[Azione] Scelto risultato {idx}: {folder}")
        os.startfile(folder)
        folder_name = os.path.basename(folder)
        return f"Aperta cartella {folder_name}."

    def _search(self, search_terms: list[str], es_path: str) -> list[str]:
        all_results = []
        seen = set()
        for term in search_terms:
            for r in search_everything(es_path, term, ["-ad", "-n", "10"]):
                if r not in seen:
                    all_results.append(r)
                    seen.add(r)
        return all_results
