import getpass
import os
import platform
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich import box
from rich.console import Console
from rich.table import Table
import pexpect

console = Console()

HOSTS = [f"cvpc{i}" for i in range(1, 36)] + ["kogspc17"]

REMOTE_CMD = r"""
CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print 100 - $8}')
RAM_USED=$(free -m | awk '/Mem:/ {print $3}')
RAM_TOTAL=$(free -m | awk '/Mem:/ {print $2}')
echo "CPU:$CPU RAM:${RAM_USED}/${RAM_TOTAL}MB"
nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total \
  --format=csv,noheader,nounits 2>/dev/null || echo "no_gpu"
"""

IS_WINDOWS = platform.system().lower().startswith("win")
HOSTNAME = (
    os.getenv("COMPUTERNAME", "").lower()
    if IS_WINDOWS
    else os.uname().nodename.lower()
)
ON_GATEWAY = "rzssh1" in HOSTNAME

console.print(f"[bold]Running on {HOSTNAME}[/bold]")
console.print(f"Detected: {'Windows' if IS_WINDOWS else 'Linux/macOS'}")
console.print(f"Gateway mode: {'direct' if ON_GATEWAY else 'proxy-jump'}\n")

# Always ask for the password once at startup.
PASSWORD = getpass.getpass("SSH password for all hosts: ")


def build_ssh_cmd(host: str) -> str:
    """Return full SSH command string (not list, since we use pexpect)."""
    parts = ["ssh", "-q", "-o", "StrictHostKeyChecking=no"]
    if not ON_GATEWAY:
        parts += ["-J", "rzssh1"]
        if not IS_WINDOWS:
            parts += [
                "-o",
                "ControlMaster=auto",
                "-o",
                "ControlPersist=10m",
                "-o",
                "ControlPath=~/.ssh/cm-%r@%h:%p",
            ]
    parts += [host, REMOTE_CMD]
    return " ".join(parts)


def run_ssh_with_password(host: str) -> str:
    """Runs SSH with password prompt handling."""
    ssh_cmd = build_ssh_cmd(host)
    child = pexpect.spawn(ssh_cmd, encoding="utf-8", timeout=10)

    while True:
        idx = child.expect(
            [
                pexpect.EOF,
                pexpect.TIMEOUT,
                "[Pp]assword:",
                "Permission denied",
                "Could not resolve hostname",
            ],
            timeout=20,
        )

        if idx == 0:
            return child.before.strip()
        elif idx == 1:
            raise TimeoutError("Timeout")
        elif idx == 2:
            child.sendline(PASSWORD)
        elif idx == 3:
            raise PermissionError("Permission denied (wrong password)")
        elif idx == 4:
            raise ConnectionError("Unknown host")


def get_remote_status(host):
    console.log(f"Fetching {host}...")
    time.sleep(random.uniform(0.3, 1.0))
    try:
        output = run_ssh_with_password(host)
        console.log(f"Fetched {host}")
        return host, parse_output(output)
    except Exception as e:
        console.log(f"[red]{host}: {e}[/red]")
        return host, {"error": str(e)}


def parse_output(out: str):
    lines = out.strip().splitlines()
    if not lines:
        return {"error": "empty output"}
    match = re.search(r"CPU:(\S+)\s+RAM:(\d+)/(\d+)MB", lines[0])
    if not match:
        return {"error": f"parse error: {lines[0]}"}
    cpu = float(match.group(1))
    ram_used = int(match.group(2)) / 1024
    ram_total = int(match.group(3)) / 1024
    gpus = []
    for g in lines[1:]:
        if "no_gpu" in g:
            return {"cpu": cpu, "ram_used": ram_used, "ram_total": ram_total, "gpus": []}
        parts = [x.strip() for x in g.split(",")]
        if len(parts) >= 5:
            gpus.append(
                {
                    "idx": parts[0],
                    "name": parts[1],
                    "util": parts[2],
                    "vram_used": float(parts[3]) / 1024,
                    "vram_total": float(parts[4]) / 1024,
                }
            )
    return {"cpu": cpu, "ram_used": ram_used, "ram_total": ram_total, "gpus": gpus}


def collect_all():
    results = {}
    total = len(HOSTS)
    max_workers = 5 if not IS_WINDOWS else 3
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(get_remote_status, h): h for h in HOSTS}
        for f in as_completed(futures):
            host, data = f.result()
            results[host] = data
            console.print(f"[cyan]Progress:[/cyan] {len(results)}/{tota
