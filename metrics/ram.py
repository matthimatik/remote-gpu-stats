from .metric import Metric

class RAMMetric(Metric):
    identifier = "ram"
    command = "free -m | awk '/Mem:/ {print $3, $2}'"

    def parse(self, raw_output: str) -> dict:
        try:
            used, total = map(int, raw_output.strip().split())
            return {"ram_used": int(used / 1024), "ram_total": total / 1024}
        except Exception:
            return {"ram_used": 0, "ram_total": 0, "error": "parse"}
