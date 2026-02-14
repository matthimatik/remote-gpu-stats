from .metric import Metric

class DiskUsageMetric(Metric):
    identifier = "disk_usage"
    command = "df -h /export | awk 'NR==2 {print $5, $2, $3}'"

    def parse(self, raw_output: str) -> dict:
        try:
            usage_percent = raw_output.strip().split()[0]
            usage_value = int(usage_percent.rstrip('%'))
            return {"disk_usage": usage_value}
        except Exception:
            return {"disk_usage": None, "error": "parse"}
