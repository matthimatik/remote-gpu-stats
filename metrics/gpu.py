from .metric import Metric

class GPUMetric(Metric):
    identifier = "gpu"
    command = (
        "nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total "
        "--format=csv,noheader,nounits 2>/dev/null || echo 'no_gpu'"
    )

    def parse(self, raw_output: str) -> dict:
        gpus = []
        for line in raw_output.strip().splitlines():
            if "no_gpu" in line:
                return {"gpus": []}
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                idx, util, mem_used, mem_total = parts
                gpus.append({
                    "idx": idx,
                    "util": float(util),
                    "vram_used": float(mem_used) / 1024,
                    "vram_total": float(mem_total) / 1024
                })
        return {"gpus": gpus}
