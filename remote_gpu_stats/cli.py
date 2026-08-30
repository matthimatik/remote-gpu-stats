import argparse
import getpass
import os

from rich.console import Console

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
        "username", type=str, help="SSH username for the remote hosts",
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
    return parser.parse_args()


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

if __name__ == "__main__":
    main()
