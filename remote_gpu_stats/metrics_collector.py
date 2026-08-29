import threading

from fabric import Connection, SerialGroup, Result, Config
from fabric.exceptions import GroupException
from paramiko import SSHConfig
from remote_gpu_stats.metrics import GPUMetric, RAMMetric, CPUMetric, UserMetric, DiskUsageMetric, Metric, TopCpuUserMetric, NumCpuCoresMetric



class MetricsCollector:
    # TODO: gateway and pool should be passed to constructor
    
    METRICS: list[Metric] = [CPUMetric(), UserMetric(), DiskUsageMetric(), GPUMetric(), RAMMetric(), TopCpuUserMetric(), NumCpuCoresMetric()]

    def __init__(
        self,
        user_name: str,
        gateway_host: str,
        hosts: list[str],
        password: str | None = None,
        key_filename: str | None = None,
        overall_timeout: float = 120.0,
    ):
        if not password and not key_filename:
            raise ValueError("Either a password or key_filename must be provided")
        self.user_name = user_name
        self.password = password
        self.key_filename = key_filename
        self.gateway_host = gateway_host
        self.hosts = hosts
        self.overall_timeout = overall_timeout

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
        # session limit (OpenSSH MaxSessions defaults to 10); a watchdog
        # bounds the whole run because an unreachable host can block its
        # gateway channel-open for a long time irrespective of the
        # socket/auth timeouts below.
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

        def _run() -> None:
            nonlocal results
            try:
                results = pool.run(cmd, hide=True, timeout=10)
            except GroupException as exc:
                results = exc.result
                for conn, result in results.failed.items():
                    print(f"Host {conn} failed: {result}")

        runner = threading.Thread(target=_run, daemon=True)
        runner.start()
        runner.join(self.overall_timeout)
        if runner.is_alive():
            print(
                f"Collection exceeded {self.overall_timeout}s, "
                "aborting remaining hosts"
            )
            gateway.close()  # force stuck channel opens / commands to fail
            pool.close()
            runner.join(10)

        if not results:
            return {}
        return self._parse_output(results.succeeded)

    def _build_remote_command(self, metrics: list[Metric]) -> str:
        cmd = ""
        for metric in metrics:
            cmd += f"""echo "{metric.identifier}:$({metric.command})"\n"""
        return cmd

    def _parse_output(self, results: dict[Connection, Result]) -> dict:
        all_data = {}

        for connection, result in results.items():
            data = {}
            lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            for line in lines:
                for metric in self.METRICS:
                    if line.startswith(metric.identifier + ":"):
                        parsed = metric.parse(line[len(metric.identifier) + 1 :].strip())
                        data.update(parsed)
                        break
            all_data[connection.host.split(".")[0]] = data
            
        return all_data
