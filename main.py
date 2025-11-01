import getpass
import random
import re
import time

from rich.console import Console

from display_cluster_overview import make_table
from jump_host import JumpHost, connect

console = Console()

HOSTS = [f"cvpc{i}" for i in range(20, 31)]
# HOSTS = [f"cvpc{i}" for i in range(1, 36)] + ["kogspc17"]

def get_remote_status(jump: JumpHost, host: str, password: str):
    try:
        chan = jump.get_channel(host)
    except Exception as e:
        return host, f"error: {type(e).__name__}: {e}"
    ssh = None
    try:
        ssh = connect(
            channel=chan,
            target_host=host,
            username="8hirsch",
            password=password,
        )

        REMOTE_CMD = r"""
        echo "USERS:$(who | wc -l)"
        echo "CPU:$(top -bn1 | awk '/Cpu/ {print 100 - $8}')"
        echo "RAM:$(free -m | awk '/Mem:/ {print $3, $2}')"
        nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total \
          --format=csv,noheader,nounits 2>/dev/null || echo "no_gpu"
        echo "DISK:$(df -h /export | awk 'NR==2 {print $5, $2, $3}')"
        """

        stdin, stdout, stderr = ssh.exec_command(REMOTE_CMD, timeout=8)
        out = stdout.read().decode().strip()
        return host, out
    except Exception as e:
        return host, f"error: {type(e).__name__}: {e}"
    finally:
        if ssh:
            ssh.close()
        chan.close()


def parse_output(out: str):
    data = {"gpus": []}
    lines = [l.strip() for l in out.splitlines() if l.strip()]

    for line in lines:
        if line.startswith("USERS:"):
            data["users"] = int(line.split(":")[1])
        elif line.startswith("CPU:"):
            data["cpu"] = float(line.split(":")[1])
        elif line.startswith("RAM:"):
            parts = line.split(":")[1].split()
            data["ram_used"] = int(parts[0]) / 1024
            data["ram_total"] = int(parts[1]) / 1024
        elif line.startswith("DISK:"):
            parts = line.split(":")[1].split()
            data["disk_usage"] = {
                "percent": parts[0],
                "size": parts[1],
                "used": parts[2],
            }
        elif "no_gpu" in line:
            data["gpus"] = []
        elif re.match(r"^\d+,", line):  # GPU info line
            idx, name, util, mem_used, mem_total = [p.strip() for p in line.split(",")]
            data["gpus"].append(
                {
                    "idx": int(idx),
                    "name": name,
                    "util": float(util),
                    "vram_used": float(mem_used) / 1024,
                    "vram_total": float(mem_total) / 1024,
                }
            )

    return data



def collect_all():
    results = {}
    total = len(HOSTS)

    jump_host = "rzssh1.informatik.uni-hamburg.de"
    user_name = "8hirsch"
    password = getpass.getpass("SSH password: ")

    for h in HOSTS:
        with JumpHost(jump_host, user_name, password) as jump:
            time.sleep(random.uniform(0.3, 1.0))
            host, data = get_remote_status(jump, h, password)
            results[host] = parse_output(data)
            console.print(f"[cyan]Progress:[/cyan] {len(results)}/{total}")
    return results

def main():
    console.print("[bold]Collecting system info...[/bold]\n")
    results = collect_all()
    print(results)
    console.print(make_table(results))


if __name__ == "__main__":
    main()
