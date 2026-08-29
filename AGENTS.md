# AGENTS.md

CLI that SSHs into the Uni Hamburg informatik GPU cluster and prints a rich table of per-host metrics. Managed with `uv`; Python 3.10.

## Commands

- Run locally: `uv run remote-gpu-stats <username>` (needs an `informatik.uni-hamburg.de` account; there is no way to run or verify this without live cluster access)
- Publish to PyPI: `uv version --bump <patch|minor|major>` -> `uv build` -> `uv publish`
- No tests, linter, or typecheck are configured (no test deps, no `[tool.*]` sections in `pyproject.toml`). Verification is a manual run against the cluster.

## Auth

- Password default: prompted, or `REMOTE_GPU_STATS_PASSWORD` env var, or a root `.env` file (gitignored) with that key.
- SSH keys are opt-in only via `--use-default-key` (`~/.ssh/id_ed25519` / `id_rsa`). Never assume a key will be used.

## Architecture

- `cli.py` is the entrypoint and holds hardcoded cluster topology: `GATEWAY_HOST` (`rzssh1...`) and the `HOSTS`/`IDX` lists. Changing which hosts are queried means editing these constants.
- `metrics_collector.py` runs one shell command built from all metrics per host, serially, through a `SerialGroup` behind the gateway. The serially-query (not parallel) + watchdog design is intentional: the gateway enforces a per-connection session limit. Don't "optimize" it to parallel.
- `~/.ssh/config` is deliberately disabled (empty `SSHConfig`) so user HostName transforms don't rewrite the FQDN hosts; keep it that way.
- Each `metrics/*.py` defines a `Metric` subclass with `identifier` (a `name:`-prefixed shell echo line), a `command`, and a `parse()`. Adding a metric requires registering it in **two** places: `metrics/__init__.py` imports and the `METRICS` list in `MetricsCollector`. `parse()` returns values keyed by string; errors are folded into the dict (e.g. `{"error": "parse"}`), exceptions are not thrown.
- `table.py` consumes the parsed dict and expects specific keys (`cpu`, `ram_used`, `ram_total`, `users`, `top_cpu_user`, `num_cpu_cores`, `gpus`, `disk_usage`); keep the metric keys in sync with it.

## Style

- Dependencies: `fabric` (SSH), `rich` (tables). Prefer these; don't pull in new SSH/UI libs without a reason.
- `.python-version` pins 3.10 via uv.

## Other

Be careful with being too aggressive with the cluster; it is rate limited and can block your IP/user if you hammer it too much. 