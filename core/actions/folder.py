import os

from core.actions.base import Action
from core.llm.brain import pick_best_result, suggest_retry_terms
from core.search import search_everything, expand_search_terms


class OpenFolderAction(Action):
    def execute(self, intent: dict, config) -> str:
        # Direct path: if parameter contains a valid folder path, open it directly
        direct_path = intent.get("parameter", "").strip()
        if direct_path and os.path.isdir(direct_path):
            os.startfile(direct_path)
            return f"Aperta cartella {os.path.basename(direct_path)}."

        query = intent.get("query", "").strip()
        if not query:
            return "Nessun nome cartella specificato."

        search_terms = intent.get("search_terms", [])
        if query not in search_terms:
            search_terms.insert(0, query)
        search_terms = expand_search_terms(search_terms)

        all_results = self._search(search_terms, config)

        # Retry: if nothing found, ask LLM for alternative terms
        if not all_results:
            user_request = intent.get("_original_text", query)
            retry_terms = suggest_retry_terms(query, search_terms, user_request, config)
            if retry_terms:
                print(f"[Ricerca] Retry con termini: {retry_terms}")
                all_results = self._search(retry_terms, config)

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

    def _search(self, search_terms: list[str], config) -> list[str]:
        is_cloud = getattr(config, "provider", "ollama") in ("anthropic", "openai", "gemini")
        max_n = getattr(config, "anthropic_max_results", 10) if is_cloud else 50
        all_results = []
        seen = set()

        # Pass 1: exact folder name match (wfn:)
        for term in search_terms:
            for r in search_everything(config.es_path, f"wfn:{term}", ["-ad"]):
                if r not in seen:
                    all_results.append(r)
                    seen.add(r)

        # Pass 2: substring fallback only if no exact matches
        if not all_results:
            for term in search_terms:
                for r in search_everything(config.es_path, term, ["-ad", "-n", str(max_n)]):
                    if r not in seen:
                        all_results.append(r)
                        seen.add(r)

        return all_results
