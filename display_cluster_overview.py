import re
from rich import box
from rich.table import Table


def make_table(results: dict):
    table = Table(
        title="Cluster Overview",
        box=box.MINIMAL_DOUBLE_HEAD,
        header_style="bold magenta",
        row_styles=["none", "dim"],
    )

    table.add_column("Host", style="bold cyan")
    table.add_column("Users", justify="right")
    table.add_column("CPU", justify="right")
    table.add_column("RAM (GB)", justify="right")
    table.add_column("GPU Util", justify="right")
    table.add_column("VRAM (GB)", justify="right")
    table.add_column("/export", justify="right")
    table.add_column("Load", justify="right", style="bold")
    table.add_column("Status", style="dim")

    def sort_key(h):
        try:
            return int(re.sub(r"\D", "", h))
        except Exception:
            return h

    for host in sorted(results.keys(), key=sort_key):
        data = results[host]

        # Handle connection or parse errors
        if "error" in data:
            table.add_row(
                host, "-", "-", "-", "-", "-", "-", "-", f"[red]{data['error']}[/red]"
            )
            continue

        cpu = data.get("cpu", 0)
        ram_used = data.get("ram_used", 0)
        ram_total = data.get("ram_total", 0)
        ram_ratio = (ram_used / ram_total) if ram_total else 0
        users = str(data.get("users", "-"))

        # Disk usage
        disk = data.get("disk_usage", {})
        disk_percent = disk.get("percent", "-")
        disk_str = f"{disk_percent} ({disk.get('used', '-')}/{disk.get('size', '-')})"

        # Compute load score
        if not data["gpus"]:
            load_score = (cpu + ram_ratio * 100) / 2
            color = "green" if load_score < 40 else "yellow" if load_score < 70 else "red"
            table.add_row(
                host,
                users,
                f"{cpu:.0f}%",
                f"{ram_used:.1f}/{ram_total:.0f}",
                "-",
                "-",
                disk_str,
                f"[{color}]{load_score:.0f}[/]",
                "[yellow]No GPU[/yellow]",
            )
            continue

        # GPU stats
        gpu_utils = [float(g["util"]) for g in data["gpus"]]
        avg_gpu = sum(gpu_utils) / len(gpu_utils)
        gpu_util_str = ", ".join([f"{g['util']}%" for g in data["gpus"]])
        vram_str = ", ".join(
            [f"{g['vram_used']:.1f}/{g['vram_total']:.0f}" for g in data["gpus"]]
        )

        load_score = (cpu + ram_ratio * 100 + avg_gpu) / 3
        color = "green" if load_score < 40 else "yellow" if load_score < 70 else "red"

        table.add_row(
            host,
            users,
            f"{cpu:.0f}%",
            f"{ram_used:.1f}/{ram_total:.0f}",
            gpu_util_str,
            vram_str,
            disk_str,
            f"[{color}]{load_score:.0f}[/]",
            "[green]OK[/green]",
        )

    return table
