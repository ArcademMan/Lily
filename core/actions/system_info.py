import psutil

from core.actions.base import Action


class SystemInfoAction(Action):
    """Reports system resource usage: CPU, RAM, disk, top processes."""

    def execute(self, intent: dict, config) -> str:
        query = intent.get("query", "").strip().lower()
        parameter = intent.get("parameter", "").strip().lower()

        if "process" in query or "pesant" in query or "pesano" in query:
            return self._top_processes(parameter)
        if "disco" in query or "disk" in query or "spazio" in query:
            return self._disk_usage()
        if "cpu" in query:
            return self._cpu_info()
        if "ram" in query or "memoria" in query:
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

        parts = [
            f"CPU al {cpu}%",
            f"RAM {ram_used:.1f} su {ram_total:.1f} giga, al {mem.percent}%",
            f"Disco C {disk_free:.0f} giga liberi su {disk_total:.0f}",
        ]

        # Top 3 processi per RAM
        top = self._get_top_processes(3, "memory")
        if top:
            nomi = ", ".join(f"{name} ({mem_mb:.0f} mega)" for name, mem_mb, _ in top)
            parts.append(f"Processi più pesanti: {nomi}")

        return ". ".join(parts) + "."

    def _cpu_info(self) -> str:
        cpu_total = psutil.cpu_percent(interval=1)
        per_core = psutil.cpu_percent(interval=0.5, percpu=True)
        cores = len(per_core)
        max_core = max(per_core)

        top = self._get_top_processes(3, "cpu")
        result = f"CPU al {cpu_total}% complessivo, {cores} core, picco singolo core al {max_core}%."

        if top:
            nomi = ", ".join(f"{name} ({cpu:.0f}%)" for name, _, cpu in top)
            result += f" Processi più attivi: {nomi}."

        return result

    def _ram_info(self) -> str:
        mem = psutil.virtual_memory()
        used = mem.used / (1024 ** 3)
        total = mem.total / (1024 ** 3)
        available = mem.available / (1024 ** 3)

        top = self._get_top_processes(5, "memory")
        result = f"RAM al {mem.percent}%: {used:.1f} giga usati su {total:.1f}, {available:.1f} giga disponibili."

        if top:
            nomi = ", ".join(f"{name} ({mem_mb:.0f} mega)" for name, mem_mb, _ in top)
            result += f" Più pesanti: {nomi}."

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
                parts.append(
                    f"Disco {part.mountpoint.rstrip(chr(92))} "
                    f"{free:.0f} giga liberi su {total:.0f}, al {usage.percent}%"
                )
            except (PermissionError, OSError):
                continue

        return ". ".join(parts) + "." if parts else "Non riesco a leggere i dischi."

    def _top_processes(self, sort_by: str = "") -> str:
        key = "cpu" if "cpu" in sort_by else "memory"
        top = self._get_top_processes(5, key)

        if not top:
            return "Non riesco a leggere i processi."

        label = "CPU" if key == "cpu" else "RAM"
        lines = []
        for name, mem_mb, cpu_pct in top:
            if key == "cpu":
                lines.append(f"{name}: CPU {cpu_pct:.0f}%, RAM {mem_mb:.0f} mega")
            else:
                lines.append(f"{name}: {mem_mb:.0f} mega di RAM, CPU {cpu_pct:.0f}%")

        intro = f"Top 5 processi per {label}"
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
