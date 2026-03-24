import os

from core.actions.base import Action, set_action_context
from core.i18n import t
from core.llm.brain import pick_best_result, suggest_retry_terms
from core.search import search_everything, expand_search_terms, _split_search_words


class SearchFilesAction(Action):
    def execute(self, intent: dict, config, pick_callback=None, **kwargs) -> str:
        query = intent.get("query", "").strip()
        if not query:
            return t("search_no_query")

        search_terms = intent.get("search_terms", [])
        if query not in search_terms:
            search_terms.insert(0, query)

        # Keep original query terms separate for fallback (before LLM terms pollute)
        original_terms = [query] if query else []
        search_terms = expand_search_terms(search_terms)
        all_results = self._search(search_terms, config)

        # Fuzzy fallback: split only original query, not LLM-generated terms
        if not all_results:
            words = _split_search_words(original_terms)
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
            return t("search_not_found", query=query)

        user_request = intent.get("_original_text", query)
        idx, confident = pick_best_result(
            user_request, all_results, config,
            intent_type=intent.get("intent", ""),
            intent_query=query,
        )
        if not confident and pick_callback and len(all_results) > 1:
            print(f"[Pick] LLM non sicuro, chiedo all'utente ({len(all_results)} risultati)")
            user_choice = pick_callback(all_results, idx)
            if user_choice == -2:
                return t("search_cancelled")
            elif user_choice >= 0:
                idx = user_choice
            elif user_choice == -1:
                idx = 0

        if idx < 0:
            idx = 0

        target = all_results[idx]
        folder = os.path.dirname(target)
        print(f"[Azione] Scelto risultato {idx}: {target}")
        os.startfile(folder)
        file_name = os.path.basename(target)
        set_action_context(type="search_files", name=file_name, path=target, folder=folder, query=query)
        return t("search_found", name=file_name)

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
