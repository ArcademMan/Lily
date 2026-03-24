import os

from core.actions.base import Action, set_action_context
from core.i18n import t
from core.llm.brain import pick_best_result, suggest_retry_terms
from core.search import search_everything, expand_search_terms


class OpenFolderAction(Action):
    TOOL_SCHEMA = {
        "name": "open_folder",
        "description": "Cerca e apri una cartella sul PC. query = soggetto principale (es. 'Lethal Company' non 'Video')",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Soggetto principale della cartella (es. 'Lethal Company')"},
                "search_terms": {"type": "array", "items": {"type": "string"}, "description": "Nomi alternativi"},
                "parameter": {"type": "string", "description": "Path esatto se gia' noto (opzionale)"}
            },
            "required": ["query"]
        }
    }

    def execute(self, intent: dict, config, pick_callback=None, **kwargs) -> str:
        # Direct path: if parameter contains a valid folder path, open it directly
        direct_path = intent.get("parameter", "").strip()
        if direct_path and os.path.isdir(direct_path):
            os.startfile(direct_path)
            return t("folder_opened_direct", name=os.path.basename(direct_path))

        query = intent.get("query", "").strip()
        if not query:
            return t("folder_none_specified")

        # Check memoria persistente
        from core.memory import find_memory_path
        saved_path = find_memory_path(query)
        if saved_path and os.path.isdir(saved_path):
            print(f"[Memory] Trovato in memoria: {query} -> {saved_path}")
            os.startfile(saved_path)
            folder_name = os.path.basename(saved_path)
            set_action_context(type="folder", name=folder_name, path=saved_path, query=query)
            return t("folder_opened", name=folder_name)

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
            return t("folder_not_found", query=query)

        user_request = intent.get("_original_text", query)
        idx, confident = pick_best_result(
            user_request, all_results, config,
            intent_type=intent.get("intent", ""),
            intent_query=query,
        )
        # Se l'LLM non è sicuro e abbiamo un callback, chiedi all'utente
        if not confident and pick_callback and len(all_results) > 1:
            print(f"[Pick] LLM non sicuro, chiedo all'utente ({len(all_results)} risultati)")
            user_choice = pick_callback(all_results, idx)
            if user_choice == -2:
                return t("pick_cancelled_action")
            elif user_choice >= 0:
                idx = user_choice
            elif user_choice == -1:
                return t("folder_found_no_match", query=query)

        if idx < 0:
            return t("folder_found_no_match", query=query)
        folder = all_results[idx]
        print(f"[Azione] Scelto risultato {idx}: {folder}")
        os.startfile(folder)
        folder_name = os.path.basename(folder)
        set_action_context(type="folder", name=folder_name, path=folder, query=query)
        return t("folder_opened", name=folder_name)

    def _search(self, search_terms: list[str], config) -> list[str]:
        is_cloud = getattr(config, "provider", "ollama") in ("anthropic", "openai", "gemini")
        max_n = getattr(config, "anthropic_max_results", 10) if is_cloud else 50
        all_results = []
        seen = set()

        # Pass 1: exact folder name match (regex case-insensitive)
        import re
        for term in search_terms:
            escaped = re.escape(term)
            regex = f"^(?i){escaped}$"
            for r in search_everything(config.es_path, regex, ["-ad", "-regex"]):
                if r not in seen:
                    all_results.append(r)
                    seen.add(r)

        # Pass 2: substring fallback if no exact matches
        if not all_results:
            for term in search_terms:
                for r in search_everything(config.es_path, term, ["-ad", "-n", str(max_n)]):
                    if r not in seen:
                        all_results.append(r)
                        seen.add(r)

        return all_results
