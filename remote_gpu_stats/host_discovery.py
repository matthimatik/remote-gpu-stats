def build_discovery_command(prefixes: dict[str, int], domain: str) -> str:
    """Build one shell command that echoes every ``<prefix><i>.<domain>``
    host that resolves via the gateway's DNS.

    ``prefixes`` maps a host prefix to the highest index to probe (1..max).
    Lookups are run with capped parallelism (``xargs -P 8``) so probing
    ~130 names takes only a couple of seconds, and each prefix pipeline is
    a separate ``;``-joined statement so one failing prefix (missing ``seq``
    etc.) does not kill the rest. ``getent`` is libc-based and always
    present on the gateway, unlike ``host``/``nslookup``.
    """
    parts = []
    for prefix, max_index in prefixes.items():
        parts.append(
            f"seq 1 {max_index} | xargs -I{{}} -P 8 sh -c "
            f"'getent hosts {prefix}{{}}.{domain} >/dev/null 2>&1 && echo {prefix}{{}}'"
        )
    # xargs exits non-zero when any getent lookup fails; force exit 0 so
    # fabric returns the stdout instead of raising on the exit code.
    return " ; ".join(parts) + " ; true"


def parse_discovery_output(stdout: str) -> list[str]:
    """Read short hostnames (one per line) from discovery output.

    Deduplicates while preserving order so the result is deterministic.
    """
    seen: set[str] = set()
    hosts: list[str] = []
    for line in stdout.splitlines():
        name = line.strip()
        if name and name not in seen:
            seen.add(name)
            hosts.append(name)
    return hosts