from . import Metric


class GPUMetric(Metric):
    identifier = "gpu"
    command = (
        "nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total "
        "--format=csv,noheader,nounits 2>/dev/null || echo 'no_gpu'"
    )

    def parse(self, raw_output: str) -> dict:
        gpus = []
        for line in raw_output.strip().splitlines():
            if "no_gpu" in line:
                return {"gpus": []}
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                idx, name, util, mem_used, mem_total = parts
                gpus.append({
                    "idx": int(idx),
                    "name": name,
                    "util": float(util) if util != "[N/A]" else 0.0,
                    "vram_used": float(mem_used) / 1024,
                    "vram_total": float(mem_total) / 1024
                })
        return {"gpus": gpus}
