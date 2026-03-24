import psutil

from core.actions.base import Action
from core.i18n import t, t_list


class SystemInfoAction(Action):
    """Reports system resource usage: CPU, RAM, disk, top processes."""

    TOOL_SCHEMA = {
        "name": "system_info",
        "description": "Info sulle risorse di sistema: CPU, RAM, disco, processi pesanti",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Cosa controllare: cpu, ram, disco, processi. Vuoto=panoramica"}
            }
        }
    }

    def execute(self, intent: dict, config, **kwargs) -> str:
        query = intent.get("query", "").strip().lower()
        parameter = intent.get("parameter", "").strip().lower()

        heavy_kw = t_list("sysinfo_heavy_keywords")
        disk_kw = t_list("sysinfo_disk_keywords")
        ram_kw = t_list("sysinfo_ram_keywords")

        if "process" in query or any(kw in query for kw in heavy_kw):
            return self._top_processes(parameter)
        if any(kw in query for kw in disk_kw):
            return self._disk_usage()
        if "cpu" in query:
            return self._cpu_info()
        if any(kw in query for kw in ram_kw):
            return self._ram_info()

        # Default: panoramica completa
        return self._overview()

    def _overview(self) -> str:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")

        ram_used = mem.used / (1024 ** 3)
        ram_total = mem.total / (1024 ** 3)
        disk_free = disk.free / (1024 ** 3)
        disk_total = disk.total / (1024 ** 3)

        overview = t("sysinfo_overview", cpu=cpu, ram_used=ram_used, ram_total=ram_total,
                      ram_pct=mem.percent, disk_free=disk_free, disk_total=disk_total)

        # Top 3 processi per RAM
        top = self._get_top_processes(3, "memory")
        if top:
            nomi = ", ".join(f"{name} ({mem_mb:.0f} MB)" for name, mem_mb, _ in top)
            overview += " " + t("sysinfo_heavy_procs", names=nomi)

        return overview

    def _cpu_info(self) -> str:
        cpu_total = psutil.cpu_percent(interval=1)
        per_core = psutil.cpu_percent(interval=0.5, percpu=True)
        cores = len(per_core)
        max_core = max(per_core)

        top = self._get_top_processes(3, "cpu")
        result = t("sysinfo_cpu_detail", cpu=cpu_total, cores=cores, max_core=max_core)

        if top:
            nomi = ", ".join(f"{name} ({cpu:.0f}%)" for name, _, cpu in top)
            result += " " + t("sysinfo_cpu_procs", names=nomi)

        return result

    def _ram_info(self) -> str:
        mem = psutil.virtual_memory()
        used = mem.used / (1024 ** 3)
        total = mem.total / (1024 ** 3)
        available = mem.available / (1024 ** 3)

        top = self._get_top_processes(5, "memory")
        result = t("sysinfo_ram_detail", pct=mem.percent, used=used, total=total, available=available)

        if top:
            nomi = ", ".join(f"{name} ({mem_mb:.0f} MB)" for name, mem_mb, _ in top)
            result += " " + t("sysinfo_ram_procs", names=nomi)

        return result

    def _disk_usage(self) -> str:
        parts = []
        for part in psutil.disk_partitions():
            if "fixed" not in part.opts and "rw" not in part.opts:
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                free = usage.free / (1024 ** 3)
                total = usage.total / (1024 ** 3)
                parts.append(t("sysinfo_disk_line",
                               mount=part.mountpoint.rstrip(chr(92)),
                               free=free, total=total, pct=usage.percent))
            except (PermissionError, OSError):
                continue

        return " ".join(parts) if parts else t("sysinfo_disk_error")

    def _top_processes(self, sort_by: str = "") -> str:
        key = "cpu" if "cpu" in sort_by else "memory"
        top = self._get_top_processes(5, key)

        if not top:
            return t("sysinfo_proc_error")

        label = "CPU" if key == "cpu" else "RAM"
        lines = []
        for name, mem_mb, cpu_pct in top:
            if key == "cpu":
                lines.append(f"{name}: CPU {cpu_pct:.0f}%, RAM {mem_mb:.0f} MB")
            else:
                lines.append(f"{name}: {mem_mb:.0f} MB RAM, CPU {cpu_pct:.0f}%")

        intro = t("sysinfo_top_procs", label=label)
        return f"{intro}: " + ", ".join(lines) + "."

    @staticmethod
    def _get_top_processes(n: int, sort_by: str = "memory"):
        """Returns list of (name, memory_mb, cpu_percent) tuples."""
        procs = []
        for p in psutil.process_iter(["name", "memory_info", "cpu_percent"]):
            try:
                info = p.info
                name = info["name"] or "?"
                mem_mb = (info["memory_info"].rss / (1024 ** 2)) if info["memory_info"] else 0
                cpu = info["cpu_percent"] or 0
                procs.append((name, mem_mb, cpu))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Raggruppa per nome (somma risorse)
        grouped: dict[str, list[float]] = {}
        for name, mem_mb, cpu in procs:
            if name not in grouped:
                grouped[name] = [0.0, 0.0]
            grouped[name][0] += mem_mb
            grouped[name][1] += cpu

        items = [(name, vals[0], vals[1]) for name, vals in grouped.items()]

        if sort_by == "cpu":
            items.sort(key=lambda x: x[2], reverse=True)
        else:
            items.sort(key=lambda x: x[1], reverse=True)

        return items[:n]
