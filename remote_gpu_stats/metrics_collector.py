import threading

from fabric import Connection, SerialGroup, Result, Config
from paramiko import SSHConfig
from remote_gpu_stats.metrics import GPUMetric, RAMMetric, CPUMetric, UserMetric, DiskUsageMetric, Metric, TopCpuUserMetric, NumCpuCoresMetric



class MetricsCollector:
    # TODO: gateway and pool should be passed to constructor
    
    METRICS: list[Metric] = [CPUMetric(), UserMetric(), DiskUsageMetric(), GPUMetric(), RAMMetric(), TopCpuUserMetric(), NumCpuCoresMetric()]
    # A host that has not produced an answer within this many seconds is
    # declared unreachable and skipped so the run is not blocked for the
    # minutes a gateway channel-open toward a dead host can take.
    PER_HOST_TIMEOUT = 5.0

    def __init__(
        self,
        user_name: str,
        gateway_host: str,
        hosts: list[str],
        password: str | None = None,
        key_filename: str | None = None,
    ):
        if not password and not key_filename:
            raise ValueError("Either a password or key_filename must be provided")
        self.user_name = user_name
        self.password = password
        self.key_filename = key_filename
        self.gateway_host = gateway_host
        self.hosts = hosts

    def _connect_kwargs(self) -> dict:
        if self.key_filename:
            return {
                "key_filename": self.key_filename,
                "timeout": 3,          # socket connect timeout
                "banner_timeout": 3,   # wait for SSH banner
                "auth_timeout": 3,     # wait for authentication
            }
        return {
            "password": self.password,
            "timeout": 3,          # socket connect timeout
            "banner_timeout": 3,   # wait for SSH banner
            "auth_timeout": 3,     # wait for authentication
        }

    def collect_metrics(self) -> dict:
        connect_kwargs = self._connect_kwargs()
        # Disable loading of ~/.ssh/config so user config rules (e.g. a
        # HostName transform that appends the campus domain) do not rewrite
        # the fully-qualified hostnames we already build here. Hosts are
        # queried serially because the gateway enforces a per-connection
        # session limit (OpenSSH MaxSessions defaults to 10). The local
        # socket/auth/banner timeouts below only bound the direct TCP connect;
        # behind a gateway that connect happens inside the gateway, so an
        # unreachable host can block its channel-open for far longer. Each host
        # therefore runs in its own thread bounded by PER_HOST_TIMEOUT so a
        # dead host is skipped quickly without stalling the whole run.
        config = Config(ssh_config=SSHConfig())

        gateway = Connection(
            self.gateway_host,
            user=self.user_name,
            connect_kwargs=connect_kwargs,
            config=config,
        )

        pool = SerialGroup(
            *self.hosts,
            user=self.user_name,
            connect_kwargs=connect_kwargs,
            gateway=gateway,
            config=config,
        )

        cmd = self._build_remote_command(self.METRICS)

        results: dict[Connection, Result] = {}

        for conn in pool:
            holder: dict = {}

            def _run_one() -> None:
                try:
                    holder["result"] = conn.run(cmd, hide=True, timeout=self.PER_HOST_TIMEOUT)
                except Exception as exc:
                    holder["error"] = exc

            worker = threading.Thread(target=_run_one, daemon=True)
            worker.start()
            worker.join(self.PER_HOST_TIMEOUT)
            if worker.is_alive():
                print(f"Host {conn} did not respond within "
                      f"{self.PER_HOST_TIMEOUT:.0f}s, skipping")
                continue
            if "error" in holder:
                print(f"Host {conn} failed: {holder['error']}")
                continue
            results[conn] = holder["result"]

        if not results:
            return {}
        return self._parse_output(results)

    def _build_remote_command(self, metrics: list[Metric]) -> str:
        cmd = ""
        for metric in metrics:
            cmd += f"""echo "{metric.identifier}:$({metric.command})"\n"""
        return cmd

    def _parse_output(self, results: dict[Connection, Result]) -> dict:
        all_data = {}

        # Split the combined output into per-metric blocks. A block starts at a
        # line prefixed with a metric identifier and extends until the next
        # metric identifier line. Some metric commands emit multiple lines (e.g.
        # nvidia-smi for a host with several GPUs), so every line belonging to a
        # metric must be passed to that metric's parse().
        def _blocks(lines: list[str]):
            current_id = None
            block = []
            for line in lines:
                matched = next(
                    (m.identifier for m in self.METRICS
                     if line.startswith(m.identifier + ":")),
                    None,
                )
                if matched is not None:
                    if current_id is not None:
                        yield current_id, block
                    current_id = matched
                    block = [line[len(matched) + 1:].strip()]
                elif current_id is not None:
                    block.append(line)
            if current_id is not None:
                yield current_id, block

        for connection, result in results.items():
            data = {}
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            for identifier, block in _blocks(lines):
                for metric in self.METRICS:
                    if metric.identifier == identifier:
                        parsed = metric.parse("\n".join(block))
                        data.update(parsed)
                        break
            all_data[connection.host.split(".")[0]] = data

        return all_data
