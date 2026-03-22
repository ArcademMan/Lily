import subprocess

from core.actions.base import Action
from core.llm.brain import pick_best_result


def _list_processes() -> list[dict]:
    """Get running processes with window titles."""
    result = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, timeout=5,
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
    def execute(self, intent: dict, config) -> str:
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
            return "Nessun programma specificato."

        processes = _list_processes()
        # Filter processes matching the query
        query_lower = query.lower()
        search_terms = intent.get("search_terms", [])
        all_terms = [query_lower] + [t.lower() for t in search_terms]

        matches = [p for p in processes if any(t in p.lower() for t in all_terms)]

        if not matches:
            return f"Nessun processo trovato per {query}."

        if len(matches) == 1:
            target = matches[0]
        else:
            user_request = intent.get("_original_text", query)
            idx = pick_best_result(user_request, matches, config)
            if idx < 0:
                return f"Trovati processi ma nessuno corrisponde a {query}."
            target = matches[idx]

        print(f"[Azione] Chiusura: {target}")
        name = target.replace(".exe", "")
        try:
            # Tentativo gentile: WM_CLOSE sulle finestre del processo
            if self._close_gentle(target):
                return f"Chiuso {name}."
            # Fallback: taskkill forzato
            print(f"[Azione] WM_CLOSE fallito, forzo chiusura di {target}")
            subprocess.run(["taskkill", "/F", "/IM", target], capture_output=True, timeout=5)
            return f"Chiuso {name} forzatamente."
        except Exception as e:
            return f"Errore nella chiusura di {target}: {e}"

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
                )
                if process_name.lower() not in check.stdout.lower():
                    return True
                time.sleep(0.3)

            return False
        except ImportError:
            print("[Azione] win32gui non disponibile, skip WM_CLOSE")
            return False
