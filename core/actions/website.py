import urllib.parse
import webbrowser

from core.actions.base import Action
from core.i18n import t

# Domini di motori di ricerca — se la query è uno di questi, usa search_terms come ricerca
SEARCH_ENGINES = {"google", "google.com", "www.google.com", "bing", "bing.com", "duckduckgo"}


class OpenWebsiteAction(Action):
    TOOL_SCHEMA = {
        "name": "open_website",
        "description": "Apri un sito web o cerca su Google",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "URL, dominio, o testo da cercare su Google"}
            },
            "required": ["query"]
        }
    }

    def execute(self, intent: dict, config, **kwargs) -> str:
        query = intent.get("query", "").strip()
        search_terms = intent.get("search_terms", [])

        if not query and not search_terms:
            return t("website_none_specified")

        # Se la query è un motore di ricerca e ci sono search_terms, fai una ricerca
        query_clean = query.lower().replace("https://", "").replace("http://", "").rstrip("/")
        if query_clean in SEARCH_ENGINES and search_terms:
            search_query = search_terms[0]
            url = f"https://www.google.com/search?q={urllib.parse.quote(search_query)}"
            webbrowser.open(url)
            return t("website_searched", query=search_query)

        if not query:
            query = search_terms[0] if search_terms else ""

        if not query:
            return t("website_none_specified")

        # Se è un URL/dominio, apri direttamente
        if query.startswith("http") or "." in query:
            url = query if query.startswith("http") else f"https://{query}"
        else:
            # Nessun URL riconosciuto → cerca su Google
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"

        webbrowser.open(url)
        if "google.com/search" in url:
            return t("website_searched", query=query)
        domain = url.split("//")[-1].split("/")[0].split("?")[0]
        return t("website_opened", domain=domain)
