import argparse
import getpass

from rich.console import Console

from remote_gpu_stats.metrics_collector import MetricsCollector
from remote_gpu_stats.table import make_table


TOP_LEVEL_DOMAIN = "uni-hamburg.de"
INFORMATIK_DOMAIN = f"informatik.{TOP_LEVEL_DOMAIN}"

IDX = [3, 4, 5, 7, 8, 18, 20, 21, 22, 23, 24, 25, 26, 27, 28, 30, 31, 32, 34, 35]
# IDX = [i for i in range(1, 36)]  # all cvpcs

GATEWAY_HOST = f"rzssh1.{INFORMATIK_DOMAIN}"
# HOSTS = [f"cvpc{i}" for i in range(20, 25)]
# HOSTS = [f"cvpc{i}" for i in range(1, 36)] + [f"kogspc17"]
HOSTS = [f"cvpc{i}" for i in IDX] + [f"kogspc17"]
# HOSTS = [f"cvpc{i}" for i in range(9, 10)]  # Test with a single host

HOSTS = [h + "." + INFORMATIK_DOMAIN for h in HOSTS]


def cli():
    parser = argparse.ArgumentParser(
        description="Collect and display system metrics from remote hosts."
    )
    parser.add_argument(
        "username", type=str, help="SSH username for remote hosts",
    )
    return parser.parse_args()

def main():
    args = cli()
    console = Console()

    password = getpass.getpass("SSH password: ")
    metrics_collector = MetricsCollector(
        user_name=args.username, 
        password=password,
        gateway_host=GATEWAY_HOST,
        hosts=HOSTS,
    )
    console.print(f"[bold]Collecting system info from {len(HOSTS)} hosts...[/bold]\n")
    results = metrics_collector.collect_metrics()

    # pprint(results)
    console.print(make_table(results))

if __name__ == "__main__":
    main()
