from . import Metric


class UserMetric(Metric):
    identifier = "users"
    command = "who | wc -l"

    def parse(self, raw_output: str) -> dict:
        try:
            val = int(raw_output.strip())
            return {"users": val}
        except Exception:
            return {"users": 0, "error": "parse"}
