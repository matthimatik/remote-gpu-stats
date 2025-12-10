from fabric import Connection, SerialGroup, Result
from fabric.exceptions import GroupException 
from metrics import GPUMetric, RAMMetric, CPUMetric, UserMetric, DiskUsageMetric, Metric, TopCpuUserMetric, NumCpuCoresMetric



class MetricsCollector:
    # TODO: gateway and pool should be passed to constructor
    
    METRICS: list[Metric] = [CPUMetric(), UserMetric(), DiskUsageMetric(), GPUMetric(), RAMMetric(), TopCpuUserMetric(), NumCpuCoresMetric()]

    def __init__(
        self,
        user_name: str,
        password: str,
        gateway_host: str,
        hosts: list[str],
    ):
        self.user_name = user_name
        self.password = password
        self.gateway_host = gateway_host
        self.hosts = hosts

    def collect_metrics(self) -> dict:
        gateway = Connection(
            self.gateway_host,
            user=self.user_name,
            connect_kwargs={"password": self.password},
        )

        pool = SerialGroup(
            *self.hosts,
            user=self.user_name,
            connect_kwargs={
                "password": self.password,
                "timeout": 3,          # socket connect timeout
                "banner_timeout": 3,   # wait for SSH banner
                "auth_timeout": 3,     # wait for authentication
            },
            gateway=gateway,
            # connect_timeout=3,
        )

        cmd = self._build_remote_command(self.METRICS)

        try:
            results = pool.run(cmd, hide=True, timeout=10)
        except GroupException as exc:
            results = exc.result
            for conn, result in results.failed.items():
                print(f"Host {conn} failed: {result}")

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
