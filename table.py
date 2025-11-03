import re
from rich import box
from rich.table import Table


def make_table(results: dict) -> Table:
    table = Table(
        title="Cluster Overview",
        box=box.MINIMAL_DOUBLE_HEAD,
        header_style="bold magenta",
    )
    table.add_column("Host", style="bold cyan")
    table.add_column("Users", justify="right")
    table.add_column("CPU (%)", justify="right")
    table.add_column("RAM (GB)", justify="right")
    table.add_column("GPU Util (%)", justify="right")
    table.add_column("VRAM (GB)", justify="right")
    table.add_column("Home Disk (%)", justify="right")
    table.add_column("Current Load", justify="right", style="bold")
    table.add_column("Top CPU User", justify="left")

    # --- sort numerically by host number if present ---
    def host_key(item):
        host, _ = item
        match = re.search(r"\d+", host)
        return int(match.group()) if match else float("inf")

    for host, data in sorted(results.items(), key=host_key):
        cpu = data["cpu"]
        ram_used, ram_total = data["ram_used"], data["ram_total"]
        ram_ratio = ram_used / ram_total * 100 if ram_total else 0
        users = data["users"]
        top_cpu_user = data.get("top_cpu_user", "N/A")

        gpus = data.get("gpus", [])
        if gpus:
            avg_gpu = sum(g["util"] for g in gpus) / len(gpus)
            vram_used = sum(g["vram_used"] for g in gpus)
            vram_total = sum(g["vram_total"] for g in gpus)
            vram_ratio = vram_used / vram_total * 100 if vram_total else 0
        else:
            avg_gpu = 0
            vram_used = vram_total = vram_ratio = 0

        disk = data["disk_usage"]
        load = (cpu + ram_ratio + avg_gpu) / 3

        def colorize(val: float, low=40, mid=70):
            if val < low:
                return "green"
            elif val < mid:
                return "yellow"
            return "red"

        cpu_color = colorize(cpu)
        ram_color = colorize(ram_ratio)
        vram_color = colorize(vram_ratio)
        gpu_color = colorize(avg_gpu)
        disk_color = colorize(disk)
        load_color = colorize(load)

        table.add_row(
            host,
            str(users),
            f"[{cpu_color}]{cpu:.0f}[/]",
            f"[{ram_color}]{ram_used:.0f}/{ram_total:.0f}[/]",
            f"[{gpu_color}]{avg_gpu:.0f}[/]",
            f"[{vram_color}]{vram_used:.1f}/{vram_total:.0f}[/]",
            f"[{disk_color}]{disk}[/]",
            f"[{load_color}]{load:.0f}[/]",
            f"[bold]{top_cpu_user}[/bold]",
        )

    return table
