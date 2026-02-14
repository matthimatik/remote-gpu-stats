from . import Metric


class NumCpuCoresMetric(Metric):
    identifier = "num_cpu_cores"
    command = "nproc"

    def parse(self, raw_output: str) -> dict:
        """Parse the output of the nproc command to get the number of CPU cores."""
        num_cores = int(raw_output.strip())
        return {"num_cpu_cores": num_cores}