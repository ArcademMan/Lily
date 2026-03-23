import os

from core.actions.base import Action
from core.llm.brain import pick_best_result, suggest_retry_terms
from core.search import search_everything, expand_search_terms, _split_search_words


class SearchFilesAction(Action):
    def execute(self, intent: dict, config) -> str:
        query = intent.get("query", "").strip()
        if not query:
            return "Nessun termine di ricerca specificato."

        search_terms = intent.get("search_terms", [])
        if query not in search_terms:
            search_terms.insert(0, query)

        search_terms = expand_search_terms(search_terms)
        all_results = self._search(search_terms, config)

        # Fuzzy fallback: search by individual words
        if not all_results:
            words = _split_search_words(search_terms)
            if words:
                print(f"[Ricerca] Nessun risultato esatto, provo con parole singole: {words}")
                all_results = self._search(words, config)

        # Retry: if nothing found, ask LLM for alternative terms
        if not all_results:
            user_request = intent.get("_original_text", query)
            retry_terms = suggest_retry_terms(query, search_terms, user_request, config)
            if retry_terms:
                print(f"[Ricerca] Retry con termini: {retry_terms}")
                all_results = self._search(retry_terms, config)

        if not all_results:
            return f"Nessun file trovato per '{query}'."

        user_request = intent.get("_original_text", query)
        idx = pick_best_result(
            user_request, all_results, config,
            intent_type=intent.get("intent", ""),
            intent_query=query,
        )
        if idx < 0:
            idx = 0  # For files, still open something useful

        target = all_results[idx]
        folder = os.path.dirname(target)
        print(f"[Azione] Scelto risultato {idx}: {target}")
        os.startfile(folder)
        file_name = os.path.basename(target)
        return f"Trovato {file_name}."

    def _search(self, search_terms: list[str], config) -> list[str]:
        is_cloud = getattr(config, "provider", "ollama") in ("anthropic", "openai", "gemini")
        args = ["-a-d"]
        if is_cloud:
            max_n = getattr(config, "anthropic_max_results", 10)
            args.extend(["-n", str(max_n)])
        all_results = []
        seen = set()
        for term in search_terms:
            for r in search_everything(config.es_path, term, args):
                if r not in seen:
                    all_results.append(r)
                    seen.add(r)
        return all_results
