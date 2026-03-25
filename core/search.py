import os
import subprocess
from pathlib import Path


def check_everything(es_path: str) -> bool:
    try:
        result = subprocess.run(
            [es_path, "-get-everything-version"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0 and len(result.stdout.strip()) > 0
    except Exception:
        return False


JUNK_PATTERNS = [
    "\\cache\\", "\\temp\\", "\\tmp\\", "\\.cache\\",
    "\\.git\\", "\\node_modules\\",
    "\\__pycache__\\", "\\.venv\\", "\\site-packages\\",
    "\\recent\\", "\\artbook", "\\soundtrack",
    "\\debug tool", "\\uninstall",
]


def _is_junk_path(path: str) -> bool:
    lower = path.lower().replace("/", "\\")
    return any(p in lower for p in JUNK_PATTERNS)


def search_everything(es_path: str, query: str, extra_args: list[str] | None = None) -> list[str]:
    cmd = [es_path]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(query)
    try:
        print(f"[Everything] Comando: {cmd}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.stderr.strip():
            print(f"[Everything] Stderr: {result.stderr[:200]}")
        lines = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        return [l for l in lines if not _is_junk_path(l)]
    except Exception:
        return []


def search_start_menu(terms: list[str]) -> list[str]:
    results = []
    seen = set()
    terms_lower = [t.lower() for t in terms]

    dirs = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    for sm_dir in dirs:
        if sm_dir.exists():
            for lnk in sm_dir.rglob("*.lnk"):
                name = lnk.stem.lower()
                if any(t in name for t in terms_lower) and str(lnk) not in seen:
                    results.append(str(lnk))
                    seen.add(str(lnk))
    return results


def search_desktop(terms: list[str]) -> list[str]:
    results = []
    seen = set()
    terms_lower = [t.lower() for t in terms]

    dirs = [
        Path.home() / "Desktop",
        Path(os.environ.get("PUBLIC", "C:/Users/Public")) / "Desktop",
    ]
    for desk_dir in dirs:
        if desk_dir.exists():
            for lnk in desk_dir.glob("*.lnk"):
                name = lnk.stem.lower()
                if any(t in name for t in terms_lower) and str(lnk) not in seen:
                    results.append(str(lnk))
                    seen.add(str(lnk))
    return results


def search_registry(terms: list[str]) -> list[str]:
    results = []
    terms_lower = [t.lower() for t in terms]
    try:
        import winreg
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    if any(t in subkey_name.lower() for t in terms_lower):
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            exe_path = winreg.QueryValue(subkey, None)
                            if exe_path:
                                results.append(exe_path)
                    i += 1
                except OSError:
                    break
    except Exception:
        pass
    return results


def _italian_number_variants(word: str) -> list[str]:
    """Generate Italian singular/plural variants for a word.
    E.g. 'tappetini' -> ['tappetino'], 'gatto' -> ['gatti'], 'funghi' -> ['fungo']."""
    variants = []
    w = word.lower()
    # Plural -> Singular (most specific first)
    if w.endswith("ini"):       # tappetini -> tappetino
        variants.append(word[:-1] + "o")
    elif w.endswith("oni"):     # bottoni -> bottone
        variants.append(word[:-1] + "e")
    elif w.endswith("etti"):    # biglietti -> biglietto
        variants.append(word[:-1] + "o")
    elif w.endswith("elli"):    # cappelli -> cappello
        variants.append(word[:-1] + "o")
    elif w.endswith("chi"):     # fiaschi -> fiasco
        variants.append(word[:-3] + "co")
    elif w.endswith("ghi"):     # funghi -> fungo
        variants.append(word[:-3] + "go")
    elif w.endswith("i") and len(w) > 2:  # gatti -> gatto
        variants.append(word[:-1] + "o")
    # -e plural -> -a singular (case -> casa)
    if w.endswith("e") and len(w) > 2:
        variants.append(word[:-1] + "a")
    # Singular -> Plural
    if w.endswith("ino"):       # tappetino -> tappetini
        variants.append(word[:-1] + "i")
    elif w.endswith("one"):     # bottone -> bottoni
        variants.append(word[:-1] + "i")
    elif w.endswith("etto"):    # biglietto -> biglietti
        variants.append(word[:-1] + "i")
    elif w.endswith("ello"):    # cappello -> cappelli
        variants.append(word[:-1] + "i")
    elif w.endswith("co"):      # fiasco -> fiaschi
        variants.append(word[:-2] + "chi")
    elif w.endswith("go"):      # fungo -> funghi
        variants.append(word[:-2] + "ghi")
    elif w.endswith("o") and len(w) > 2:  # gatto -> gatti
        variants.append(word[:-1] + "i")
    elif w.endswith("a") and len(w) > 2:  # casa -> case
        variants.append(word[:-1] + "e")
    return variants


def expand_search_terms(terms: list[str]) -> list[str]:
    """Add variants with different separators and Italian singular/plural to search terms.
    E.g. ['Animus Template'] -> ['Animus Template', 'AnimusTemplate', 'animus_template', 'Animus-Template']
    E.g. ['AnimusTemplate'] -> ['AnimusTemplate', 'Animus Template']"""
    import re
    expanded = list(terms)
    seen = set(t.lower() for t in terms)

    def _add(variant):
        if variant and variant.lower() not in seen:
            expanded.append(variant)
            seen.add(variant.lower())

    for t in terms:
        # "Animus Template" -> "AnimusTemplate"
        _add(t.replace(" ", ""))
        # "Animus Template" -> "animus_template"
        _add(t.replace(" ", "_").lower())
        # "Animus Template" -> "Animus-Template"
        _add(t.replace(" ", "-"))
        # "AnimusTemplate" -> "Animus Template" (CamelCase split)
        spaced = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', t)
        _add(spaced)
        # "animus_template" -> "animus template"
        _add(t.replace("_", " "))
        # "animus-template" -> "animus template"
        _add(t.replace("-", " "))
        # Italian singular/plural variants
        # Strip extension first, generate variants, re-add extension
        base, ext = (t.rsplit(".", 1) if "." in t else (t, ""))
        for word in base.replace("_", " ").replace("-", " ").split():
            for variant in _italian_number_variants(word):
                # Replace the word in the original term
                _add(base.replace(word, variant) + ("." + ext if ext else ""))
                _add(variant + ("." + ext if ext else ""))
                _add(variant)
    return expanded


def _split_search_words(terms: list[str]) -> list[str]:
    """Split multi-word terms into individual words for fuzzy matching.
    E.g. ['Elden Ring'] -> ['Elden', 'Ring'] (words >= 3 chars)."""
    words = set()
    for term in terms:
        for word in term.replace("_", " ").replace("-", " ").split():
            if len(word) >= 3:
                words.add(word)
    return list(words)


def find_program(search_terms: list[str], es_path: str) -> list[str]:
    """Aggregate program search across all sources."""
    seen = set()
    results = []

    def _add(items):
        for item in items:
            if item not in seen:
                results.append(item)
                seen.add(item)

    _add(search_start_menu(search_terms))
    _add(search_desktop(search_terms))
    _add(search_registry(search_terms))

    # Everything search — exact terms
    for term in search_terms:
        if len(results) >= 15:
            break
        for ext in ["lnk", "exe"]:
            _add(search_everything(es_path, term, ["-a-d", "-n", "5", f"ext:{ext}"]))

    # Fuzzy fallback: if no results, search by individual words
    if not results:
        words = _split_search_words(search_terms)
        print(f"[Ricerca] Nessun risultato esatto, provo fuzzy con parole: {words}")
        _add(search_start_menu(words))
        _add(search_desktop(words))
        for word in words:
            if len(results) >= 15:
                break
            for ext in ["lnk", "exe"]:
                _add(search_everything(es_path, word, ["-a-d", "-n", "5", f"ext:{ext}"]))

    print(f"[Ricerca] Trovati {len(results)} risultati per {search_terms}")
    for i, r in enumerate(results):
        print(f"  {i}: {r}")
    return results


def get_path_metadata(path: str) -> str:
    """Genera una descrizione compatta del contenuto di un path per il pick LLM.
    Per cartelle: numero file, tipi principali, dimensione, ultima modifica.
    Per file: dimensione, estensione, ultima modifica."""
    try:
        p = Path(path)
        if not p.exists():
            return ""

        if p.is_dir():
            files = []
            dirs = []
            try:
                entries = list(p.iterdir())
                files = [e for e in entries if e.is_file()]
                dirs = [e for e in entries if e.is_dir()]
            except PermissionError:
                return "[access denied]"

            if not files and not dirs:
                return "[empty]"

            if not files:
                dir_names = ", ".join(d.name for d in dirs[:5])
                return f"[{len(dirs)} subdirs: {dir_names}]"

            # Conta per estensione
            ext_count = {}
            total_size = 0
            for f in files:
                ext = f.suffix.lower().lstrip(".") or "no_ext"
                ext_count[ext] = ext_count.get(ext, 0) + 1
                try:
                    total_size += f.stat().st_size
                except Exception:
                    pass

            # Top 3 estensioni
            top_exts = sorted(ext_count.items(), key=lambda x: -x[1])[:3]
            ext_str = ",".join(f"{n} {e}" for e, n in top_exts)

            # Dimensione leggibile
            if total_size < 1024:
                size_str = f"{total_size}B"
            elif total_size < 1024 * 1024:
                size_str = f"{total_size // 1024}KB"
            elif total_size < 1024 * 1024 * 1024:
                size_str = f"{total_size // (1024 * 1024)}MB"
            else:
                size_str = f"{total_size / (1024 ** 3):.1f}GB"

            # Ultima modifica
            try:
                mtime = max(f.stat().st_mtime for f in files)
                from datetime import datetime
                mod_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
            except Exception:
                mod_str = "?"

            return f"[{len(files)} files: {ext_str} | {size_str} | {mod_str}]"

        else:
            # File singolo
            try:
                size = p.stat().st_size
                if size < 1024:
                    size_str = f"{size}B"
                elif size < 1024 * 1024:
                    size_str = f"{size // 1024}KB"
                else:
                    size_str = f"{size // (1024 * 1024)}MB"

                from datetime import datetime
                mod_str = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
                return f"[{p.suffix} | {size_str} | {mod_str}]"
            except Exception:
                return ""

    except Exception:
        return ""
