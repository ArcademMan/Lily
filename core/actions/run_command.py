"""Esecuzione comandi shell con sistema di sicurezza a whitelist."""

import re
import subprocess
import threading

from core.actions.base import Action
from core.i18n import t

# Timeout massimo per qualsiasi comando (secondi)
_CMD_TIMEOUT = 30

# Massimo output restituito all'LLM (caratteri)
_MAX_OUTPUT = 4000

# ── Whitelist: pattern di comandi READ-ONLY che passano senza conferma ──────
# Tutto il resto richiede conferma vocale dall'utente.
_SAFE_PREFIXES = [
    # PowerShell read-only cmdlets
    "get-", "test-", "select-", "where-", "format-", "measure-",
    "convertto-", "convertfrom-", "out-string", "sort-object",
    "group-object", "compare-object", "resolve-path",
    # Info di sistema
    "hostname", "whoami", "systeminfo", "ver",
    # Rete (read-only)
    "ping ", "ping6 ", "tracert ", "nslookup ", "ipconfig",
    "netstat", "arp ", "route print",
    # File system read-only
    "dir ", "dir/", "ls ", "ls/", "type ", "cat ", "more ",
    "find ", "findstr ", "where.exe",
    "tree ",
    "get-content ", "gc ", "get-filehash ",
    "test-path ", "resolve-path ",
    # Processi (solo lettura)
    "tasklist", "wmic process",
    # Git read-only
    "git status", "git log", "git diff", "git branch", "git remote",
    "git show", "git blame",
    # Versioni
    "python --version", "python3 --version", "node --version",
    "npm --version", "java -version", "dotnet --version",
    "winget --version", "ffmpeg -version",
    # Variabili d'ambiente
    "echo %", "echo $",
    "$env:",
]

# Pattern regex per comandi safe (per casi piu' complessi)
_SAFE_PATTERNS = [
    r"^\$\w+\s*=\s*get-",          # $x = Get-Something
    r"^\$\w+\s*=\s*\[",            # $x = [Environment]::GetFolderPath(...)
    r"^get-\w+",                     # Get-Process, Get-ChildItem, ecc.
    r"^\[[\w.]+\]::\w+",            # [System.Environment]::GetEnvironmentVariable
    r"^python\d?\s+-c\s+['\"]",     # python -c "print(...)"  (read-only scripts)
    r"^pip\s+(list|show|freeze)",    # pip list, pip show, pip freeze
]

# ── Blacklist: comandi SEMPRE bloccati anche con conferma ───────────────────
_BLOCKED_PATTERNS = [
    r"format\s+[a-z]:",             # format C:
    r"rm\s+-rf",                    # rm -rf (qualsiasi path)
    r"del\s+/[sfq]",               # del /s /f /q (ricorsivo forzato)
    r"rmdir\s+/[sq]",              # rmdir /s /q
    r"rd\s+/[sq]",                 # rd /s /q (alias di rmdir)
    r"shutdown\s+",                  # shutdown
    r"restart-computer",             # Restart-Computer
    r"stop-computer",                # Stop-Computer
    r"clear-disk",                   # Clear-Disk
    r"initialize-disk",             # Initialize-Disk
    r"remove-partition",            # Remove-Partition
    r"reg\s+delete",                # reg delete (registro)
    r"bcdedit",                     # boot configuration
    r"sfc\s+",                      # system file checker
    r"dism\s+",                     # DISM
    r"cipher\s+/[we]",             # encrypt/wipe
    r"remove-item\s+.*-recurse",   # Remove-Item -Recurse
    r"remove-item\s+[a-z]:\\",     # Remove-Item C:\...
    r"del\s+[a-z]:\\",             # del C:\...
    r"format-volume",               # Format-Volume
    r"clear-recyclebin",            # Clear-RecycleBin
]


def _unwrap_powershell(cmd: str) -> str:
    """Estrae il comando interno da wrapper tipo 'powershell -Command "..."'."""
    m = re.match(
        r'^powershell(?:\.exe)?\s+(?:-\w+\s+)*-Command\s+["\'](.+)["\']$',
        cmd.strip(), re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(1).strip()
    return cmd


def _has_unquoted_separator(cmd: str) -> bool:
    """Controlla se ci sono ; && || fuori da quotes."""
    in_single = False
    in_double = False
    i = 0
    while i < len(cmd):
        c = cmd[i]
        if c == '\\' and i + 1 < len(cmd):
            i += 2
            continue
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if c == ';':
                return True
            if c == '&' and i + 1 < len(cmd) and cmd[i + 1] == '&':
                return True
            if c == '|' and i + 1 < len(cmd) and cmd[i + 1] == '|':
                return True
        i += 1
    return False


def _is_safe_command(cmd: str) -> bool:
    """Controlla se il comando e' read-only e puo' essere eseguito senza conferma."""
    # Unwrap: l'LLM spesso wrappa in powershell -Command "..."
    inner = _unwrap_powershell(cmd)
    cmd_lower = inner.strip().lower()

    # Comandi che wrappano contenuto in quotes (python -c "...;...", pip show "x")
    # non vanno splittati sui ; interni. Controlla se il pattern safe matcha E
    # i separatori sono solo dentro quotes.
    if _is_safe_single(cmd_lower) and not _has_unquoted_separator(cmd_lower):
        return True

    # Splitta su separatori — ogni segmento deve essere safe indipendentemente
    if re.search(r'[;]|&&|\|\|', cmd_lower):
        segments = re.split(r'\s*(?:;|&&|\|\|)\s*', cmd_lower)
        segments = [s.strip() for s in segments if s.strip()]
        return bool(segments) and all(_is_safe_command(seg) for seg in segments)

    # Pipeline: ogni segmento deve essere safe
    if "|" in cmd_lower:
        segments = [s.strip() for s in cmd_lower.split("|")]
        segments = [s for s in segments if s]
        return bool(segments) and all(_is_safe_single(seg) for seg in segments)

    return _is_safe_single(cmd_lower)


def _is_safe_single(cmd_lower: str) -> bool:
    """Controlla se un singolo comando (senza ; o |) e' safe."""
    # Strip parentesi e .Property wrapping: (Get-ChildItem ...).Count → Get-ChildItem ...
    stripped = re.sub(r'^\((.+)\)\.\w+$', r'\1', cmd_lower.strip())
    stripped = stripped.strip().lstrip('(').rstrip(')')

    for check in [cmd_lower, stripped]:
        for prefix in _SAFE_PREFIXES:
            if check.startswith(prefix):
                return True
        for pattern in _SAFE_PATTERNS:
            if re.match(pattern, check):
                return True

    return False


def _is_blocked_command(cmd: str) -> bool:
    """Controlla se il comando e' nella blacklist (sempre bloccato)."""
    cmd_lower = cmd.strip().lower()
    for pattern in _BLOCKED_PATTERNS:
        if re.search(pattern, cmd_lower):
            return True
    return False


class RunCommandAction(Action):
    TOOL_SCHEMA = {
        "name": "run_command",
        "description": "Esegui un comando sul PC. Viene eseguito in PowerShell, non serve wrappare. Comandi read-only passano subito, gli altri chiedono conferma",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Comando PowerShell da eseguire (senza prefisso powershell)"}
            },
            "required": ["command"]
        }
    }

    def execute(self, intent: dict, config, **kwargs) -> str:
        cmd = intent.get("parameter", "").strip() or intent.get("command", "").strip() or intent.get("param", "").strip()
        if not cmd:
            return t("cmd_empty")

        # Blocco assoluto
        if _is_blocked_command(cmd):
            print(f"[Command] BLOCCATO: {cmd}")
            return t("cmd_blocked")

        # Conferma per comandi non-safe
        if not _is_safe_command(cmd):
            confirm_fn = kwargs.get("confirm_callback")
            if confirm_fn:
                print(f"[Command] Richiesta conferma per: {cmd}")
                confirmed = confirm_fn(cmd)
                if not confirmed:
                    return t("cmd_denied")
            else:
                # Nessun callback di conferma disponibile — rifiuta per sicurezza
                print(f"[Command] Nessun confirm_callback, rifiuto: {cmd}")
                return t("cmd_needs_confirm", cmd=cmd)

        return self._run(cmd)

    # Processo attivo — puo' essere killato dall'esterno
    _active_proc: subprocess.Popen | None = None
    _proc_lock = threading.Lock()

    @classmethod
    def kill_active(cls):
        """Killa il processo attivo se presente."""
        with cls._proc_lock:
            if cls._active_proc and cls._active_proc.poll() is None:
                print("[Command] Kill processo attivo")
                cls._active_proc.kill()
                cls._active_proc = None

    def _run(self, cmd: str) -> str:
        """Esegue il comando e ritorna stdout+stderr."""
        print(f"[Command] Esecuzione: {cmd}")
        try:
            inner = _unwrap_powershell(cmd)
            with self._proc_lock:
                from core.utils.env import clean_env
                proc = subprocess.Popen(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", inner],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, creationflags=subprocess.CREATE_NO_WINDOW,
                    env=clean_env(),
                )
                self._active_proc = proc

            try:
                stdout, stderr = proc.communicate(timeout=_CMD_TIMEOUT)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                return t("cmd_timeout", seconds=_CMD_TIMEOUT)
            finally:
                with self._proc_lock:
                    self._active_proc = None

            output = ""
            if stdout and stdout.strip():
                output += stdout.strip()
            if stderr and stderr.strip():
                if output:
                    output += "\n"
                output += f"[STDERR] {stderr.strip()}"

            if not output:
                if proc.returncode == 0:
                    output = t("cmd_success_no_output")
                else:
                    output = t("cmd_error_code", code=proc.returncode)

            if len(output) > _MAX_OUTPUT:
                output = output[:_MAX_OUTPUT] + f"\n... (troncato, {len(output)} chars totali)"

            print(f"[Command] Exit code: {proc.returncode}, output: {len(output)} chars")
            return output

        except Exception as e:
            return t("cmd_error", e=e)
