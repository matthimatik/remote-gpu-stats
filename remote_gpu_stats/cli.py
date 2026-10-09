import argparse
import getpass
import os

from rich import box
from rich.console import Console
from rich.table import Table

from remote_gpu_stats.history import list_snapshots, load_snapshot, save_snapshot
from remote_gpu_stats.host_discovery import build_discovery_command
from remote_gpu_stats.metrics_collector import MetricsCollector
from remote_gpu_stats.table import make_table


TOP_LEVEL_DOMAIN = "uni-hamburg.de"
INFORMATIK_DOMAIN = f"informatik.{TOP_LEVEL_DOMAIN}"

# IDX = [3, 4, 5, 7, 8, 18, 20, 21, 22, 23, 24, 25, 26, 27, 28, 30, 31, 32, 34, 35]
IDX = [i for i in range(1, 36)]  # all cvpcs

BLADES = [f"ccblade{i}" for i in range(1, 9)]      # general hosts
CVGPUS = [f"cvgpu{i}" for i in range(1, 3)]        # computer vision dpt.
EXTRA_HOSTS = ["kogspc17"]

HOSTS = [f"cvpc{i}" for i in IDX] + EXTRA_HOSTS + BLADES + CVGPUS
# HOSTS = [f"cvpc{i}" for i in range(20, 25)]  # Test with a subset
# HOSTS = [f"cvpc{i}" for i in range(9, 10)]   # Test with a single host

HOSTS = [h + "." + INFORMATIK_DOMAIN for h in HOSTS]

# DNS ranges probed for hosts beyond the static list on every run (unless
# disabled). Generous upper bounds so newly-added machines are not missed;
# only hosts that resolve are queried.
DISCOVERY_PREFIXES = {"ccblade": 50, "cvpc": 50, "cvgpu": 10, "kogspc": 20}

GATEWAY_HOST = f"rzssh1.{INFORMATIK_DOMAIN}"

PASSWORD_ENV = "REMOTE_GPU_STATS_PASSWORD"


def cli():
    parser = argparse.ArgumentParser(
        description="Collect and display system metrics from remote hosts."
    )
    parser.add_argument(
        "username", type=str, nargs="?", help="SSH username for the remote hosts "
        "(required unless viewing history)",
    )
    parser.add_argument(
        "--use-default-key",
        action="store_true",
        help="Opt in to SSH key authentication using ~/.ssh/id_ed25519 "
             "(or ~/.ssh/id_rsa) instead of a password. Key auth is not "
             "used unless this flag is given. Fails loudly if the key "
             "cannot authenticate.",
    )
    parser.add_argument(
        "--no-discover",
        action="store_true",
        help="Skip DNS host discovery through the gateway and query only "
             "the static host list.",
    )
    history_group = parser.add_mutually_exclusive_group()
    history_group.add_argument(
        "--history",
        action="store_true",
        help="List saved runs from previous executions instead of "
             "collecting fresh metrics. No cluster access needed.",
    )
    history_group.add_argument(
        "--show",
        type=int,
        metavar="N",
        help="Re-display saved run N (1 = most recent) instead of "
             "collecting fresh metrics.",
    )
    history_group.add_argument(
        "--latest",
        action="store_true",
        help="Re-display the most recent saved run (same as --show 1).",
    )
    args = parser.parse_args()

    viewing = args.history or args.show is not None or args.latest
    if viewing and (args.username or args.use_default_key or args.no_discover):
        parser.error(
            "history flags cannot be combined with username or collection "
            "flags (--use-default-key, --no-discover)"
        )
    if not viewing and not args.username:
        parser.error("username is required unless --history/--show/--latest is given")
    if args.show is not None and args.show < 1:
        parser.error("--show must be >= 1 (1 = most recent run)")
    return args


def show_history(console: Console, args):
    snapshots = list_snapshots()
    no_runs_message = (
        "No saved runs yet. Collect once with "
        "[bold]remote-gpu-stats <username>[/bold] to create one."
    )

    if args.history:
        if not snapshots:
            console.print(no_runs_message)
            return
        table = Table(
            title="Previous Runs",
            box=box.MINIMAL_DOUBLE_HEAD,
            header_style="bold magenta",
        )
        table.add_column("#", justify="right")
        table.add_column("Saved")
        table.add_column("Age", justify="right")
        table.add_column("Hosts", justify="right")
        table.add_column("Username")
        for i, s in enumerate(snapshots, start=1):
            saved = (
                s["saved_at"].strftime("%Y-%m-%d %H:%M:%S")
                if s["saved_at"]
                else "?"
            )
            table.add_row(str(i), saved, s["age"], str(s["host_count"]), s["username"])
        console.print(table)
        console.print(
            "[dim]View a run with --show <N> (1 = most recent) or --latest[/dim]"
        )
        return

    if not snapshots:
        console.print(no_runs_message)
        raise SystemExit(1)

    index = 1 if args.latest else args.show
    if index > len(snapshots):
        console.print(
            f"Only {len(snapshots)} saved run(s) available; "
            f"--show {index} is out of range."
        )
        raise SystemExit(1)

    snapshot = snapshots[index - 1]
    try:
        envelope = load_snapshot(snapshot["path"])
    except (OSError, ValueError, KeyError) as e:
        console.print(f"Could not load snapshot: {e}")
        raise SystemExit(1)

    if snapshot["saved_at"]:
        title = (
            "Cluster Overview \u2014 saved "
            f"{snapshot['saved_at'].strftime('%Y-%m-%d %H:%M:%S')} "
            f"({snapshot['age']})"
        )
    else:
        title = "Cluster Overview \u2014 saved run"
    console.print(make_table(envelope["results"], title=title))


def resolve_default_key() -> str:
    ssh_dir = os.path.join(os.path.expanduser("~"), ".ssh")
    for name in ("id_ed25519", "id_rsa"):
        path = os.path.join(ssh_dir, name)
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        f"No default SSH key found in {ssh_dir}. Generate one with "
        "`ssh-keygen` and install the public key on each host with "
        "`ssh-copy-id`."
    )


def password_from_env_file() -> str | None:
    """Read PASSWORD_ENV from a .env file in the project root, if present."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.normpath(env_path)
    if not os.path.isfile(env_path):
        return None
    try:
        with open(env_path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() == PASSWORD_ENV:
                    return value.strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def resolve_password() -> str:
    password = os.environ.get(PASSWORD_ENV)
    if not password:
        password = password_from_env_file()
    if not password:
        password = getpass.getpass("SSH password: ")
    return password


def main():
    args = cli()
    console = Console()

    if args.history or args.show is not None or args.latest:
        show_history(console, args)
        return

    password = None
    key_filename = None
    if args.use_default_key:
        key_filename = resolve_default_key()
        console.print(f"[bold]Using SSH key: {key_filename}[/bold]\n")
    else:
        password = resolve_password()

    discovery_command = None
    if not args.no_discover:
        discovery_command = build_discovery_command(DISCOVERY_PREFIXES, INFORMATIK_DOMAIN)
        console.print("[bold]Discovering additional hosts via DNS...[/bold]\n")

    metrics_collector = MetricsCollector(
        user_name=args.username,
        password=password,
        key_filename=key_filename,
        gateway_host=GATEWAY_HOST,
        hosts=HOSTS,
        discovery_command=discovery_command,
    )
    console.print(f"[bold]Collecting system info from {len(HOSTS)} hosts...[/bold]\n")
    results = metrics_collector.collect_metrics()

    # pprint(results)
    console.print(make_table(results))
    if save_snapshot(results, args.username):
        console.print(
            "\n[dim]Snapshot saved \u2014 browse past runs with "
            "--history or --show 1[/dim]"
        )

if __name__ == "__main__":
    main()
