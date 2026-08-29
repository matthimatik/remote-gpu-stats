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
    table.add_column("CPU Cores", justify="right")
    table.add_column("RAM (GB)", justify="right")
    table.add_column("GPU Util (%)", justify="right")
    table.add_column("VRAM (GB)", justify="right")
    table.add_column("GPU Model", justify="left")
    table.add_column("Home Disk (%)", justify="right")
    table.add_column("Current Load", justify="right", style="bold")
    table.add_column("Top CPU User", justify="left")

    def host_key(item):
        host, _ = item
        match = re.search(r"\d+", host)
        return int(match.group()) if match else float("inf")

    def colorize(val: float, low=40, mid=70):
        if val < low:
            return "green"
        elif val < mid:
            return "yellow"
        return "red"

    def fmt_gpu(g: dict) -> str:
        idx = g.get("idx")
        return f"#{idx}" if isinstance(idx, int) else "GPU"

    for host, data in sorted(results.items(), key=host_key):
        cpu = data["cpu"]
        ram_used, ram_total = data["ram_used"], data["ram_total"]
        ram_ratio = ram_used / ram_total * 100 if ram_total else 0
        users = data["users"]
        top_cpu_user = data.get("top_cpu_user", "N/A")

        num_cpu_cores = data.get("num_cpu_cores", "—")

        gpus = sorted(data.get("gpus", []), key=lambda g: g.get("idx", -1))
        if gpus:
            avg_gpu = sum(g["util"] for g in gpus) / len(gpus)
            gpu_util_cell = "\n".join(
                f"[{colorize(g['util'])}]{fmt_gpu(g)} {g['util']:.0f}%[/]"
                for g in gpus
            )
            vram_cell = "\n".join(
                f"[{colorize(g['vram_used'] / g['vram_total'] * 100)}]"
                f"{g['vram_used']:.1f}/{g['vram_total']:.0f}[/]"
                if g["vram_total"]
                else f"{g['vram_used']:.1f}/-"
                for g in gpus
            )
            gpu_names = "\n".join(fmt_gpu(g) + " " + g["name"] for g in gpus)
        else:
            avg_gpu = 0
            gpu_util_cell = "-"
            vram_cell = "-"
            gpu_names = "-"

        disk = data["disk_usage"]
        load = (cpu + ram_ratio + avg_gpu) / 3

        cpu_color = colorize(cpu)
        ram_color = colorize(ram_ratio)
        disk_color = colorize(disk)
        load_color = colorize(load)

        table.add_row(
            host,
            str(users),
            f"[{cpu_color}]{cpu:.0f}[/]",
            str(num_cpu_cores),
            f"[{ram_color}]{ram_used:.0f}/{ram_total:.0f}[/]",
            gpu_util_cell,
            vram_cell,
            gpu_names,
            f"[{disk_color}]{disk}[/]",
            f"[{load_color}]{load:.0f}[/]",
            f"[bold]{top_cpu_user}[/bold]",
        )

    return table
