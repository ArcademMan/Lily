import subprocess

from core.actions.base import Action, set_action_context
from core.i18n import t
from core.llm.brain import pick_best_result


def _list_processes() -> list[dict]:
    """Get running processes with window titles."""
    result = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, timeout=5,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    processes = []
    seen = set()
    for line in result.stdout.strip().splitlines():
        parts = line.strip('"').split('","')
        if len(parts) >= 2:
            name = parts[0]
            if name.lower() not in seen and name.lower().endswith(".exe"):
                processes.append(name)
                seen.add(name.lower())
    return processes


class CloseProgramAction(Action):
    TOOL_SCHEMA = {
        "name": "close_program",
        "description": "Chiudi un programma in esecuzione",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Nome del programma da chiudere"},
                "search_terms": {"type": "array", "items": {"type": "string"}, "description": "Nomi alternativi"}
            },
            "required": ["query"]
        }
    }

    def execute(self, intent: dict, config, pick_callback=None, **kwargs) -> str:
        query = intent.get("query", "").strip()
        # Some models put the program name in parameter instead of query
        if not query:
            query = intent.get("parameter", "").strip()
        # Last resort: extract from original text (remove common verbs)
        if not query:
            original = intent.get("_original_text", "").strip()
            for word in ["chiudi", "termina", "stoppa", "esci da", "close", "quit", "kill"]:
                original = original.lower().replace(word, "")
            query = original.strip().strip(".")
        if not query:
            return t("close_none_specified")

        processes = _list_processes()
        # Filter processes matching the query
        query_lower = query.lower()
        search_terms = intent.get("search_terms", [])
        all_terms = [query_lower] + [t.lower() for t in search_terms]

        matches = [p for p in processes if any(t in p.lower() for t in all_terms)]

        if not matches:
            return t("close_not_found", query=query)

        if len(matches) == 1:
            target = matches[0]
        else:
            user_request = intent.get("_original_text", query)
            idx, confident = pick_best_result(user_request, matches, config)

            if not confident and pick_callback and len(matches) > 1:
                print(f"[Pick] LLM non sicuro, chiedo all'utente ({len(matches)} risultati)")
                user_choice = pick_callback(matches, idx)
                if user_choice == -2:
                    return t("pick_cancelled_action")
                elif user_choice >= 0:
                    idx = user_choice
                elif user_choice == -1:
                    return t("close_found_no_match", query=query)

            if idx < 0:
                return t("close_found_no_match", query=query)
            target = matches[idx]

        print(f"[Azione] Chiusura: {target}")
        name = target.replace(".exe", "")
        set_action_context(type="close_program", name=name, process=target, query=query)
        try:
            # Tentativo gentile: WM_CLOSE sulle finestre del processo
            if self._close_gentle(target):
                return t("close_success", name=name)
            # Fallback: taskkill forzato
            print(f"[Azione] WM_CLOSE fallito, forzo chiusura di {target}")
            subprocess.run(["taskkill", "/F", "/IM", target], capture_output=True, timeout=5,
                           creationflags=subprocess.CREATE_NO_WINDOW)
            return t("close_forced", name=name)
        except Exception as e:
            return t("close_error", target=target, e=e)

    @staticmethod
    def _close_gentle(process_name: str, timeout: float = 3.0) -> bool:
        """Chiude un processo inviando WM_CLOSE alle sue finestre. Ritorna True se il processo termina."""
        import time
        try:
            import win32gui
            import win32con
            import win32process

            # Trova tutti i PID del processo
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            pids = set()
            for line in result.stdout.strip().splitlines():
                parts = line.strip('"').split('","')
                if len(parts) >= 2:
                    try:
                        pids.add(int(parts[1]))
                    except ValueError:
                        pass

            if not pids:
                return False

            # Invia WM_CLOSE a tutte le finestre di quei PID
            def enum_callback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid in pids:
                        try:
                            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                            print(f"[Azione] WM_CLOSE inviato a hwnd={hwnd} (pid={pid})")
                        except Exception:
                            pass

            win32gui.EnumWindows(enum_callback, None)

            # Aspetta che il processo termini
            deadline = time.time() + timeout
            while time.time() < deadline:
                check = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
                    capture_output=True, text=True, timeout=3,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if process_name.lower() not in check.stdout.lower():
                    return True
                time.sleep(0.3)

            return False
        except ImportError:
            print("[Azione] win32gui non disponibile, skip WM_CLOSE")
            return False
