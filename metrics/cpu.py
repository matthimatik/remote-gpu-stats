from .metric import Metric

class CPUMetric(Metric):
    identifier = "cpu"
    command = "mpstat 1 1 | awk '/Average:/ {print 100 - $NF}'"
    columns = ["CPU (%)"]

    def parse(self, raw_output: str) -> dict:
        try:
            val = int(raw_output.strip().splitlines()[-1])
            return {"cpu": val}
        except Exception:
            return {"cpu": None, "error": "parse"}
