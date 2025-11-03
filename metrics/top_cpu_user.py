from metrics.metric import Metric

class TopCpuUserMetric(Metric):
    identifier = "top_cpu_user"
    command = "ps -eo user,pcpu --no-headers | awk '{cpu[$1]+=$2} END {for (u in cpu) print u, cpu[u]}' | sort -k2 -nr | head -1 | awk '{print $1}'"
    
    def parse(self, raw_output: str) -> dict:
        try:
            user = raw_output.strip()
            return {"top_cpu_user": user}
        except Exception:
            return {"top_cpu_user": None, "error": "parse"}
