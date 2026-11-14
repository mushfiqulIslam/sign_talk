"""Modal wrapper around gpu_train.py (same training as on Verda): fine-tune Gemma 4 E2B (LoRA) on FinSL sign names, predict the test sample, and serve it live.

  uv run modal volume put finsl-data ../../finsl-data/dataset /dataset     # once, after build + translate
  uv run modal run modal_app.py::train --limit 64 --max-steps 5            # smoke test
  uv run modal run modal_app.py::train                                     # full run
  uv run modal run modal_app.py::predict_local                             # fine-tuned -> predictions/finetuned_e2b.jsonl
  uv run modal run modal_app.py::predict_local --no-adapter                # untrained   -> predictions/base_e2b.jsonl
  uv run modal deploy modal_app.py                                         # live endpoint for the backend
"""
import json
import os
import time
from pathlib import Path

import modal

ADAPTER_DIR = "/models/finsl-gemma4-e2b"
GPU = os.environ.get("FINSL_GPU", "A10G")  # L40S needs a payment method on the account
HERE = Path(__file__).resolve().parent

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install("torch==2.15.0", "transformers==5.23.0", "peft==0.21.3", "accelerate", "fastapi[standard]")
    .env({"HF_HOME": "/hf-cache", "TOKENIZERS_PARALLELISM": "false"})
    .add_local_file(HERE / "station_examples.jsonl", "/root/station_examples.jsonl")
    .add_local_python_source("finsl", "gpu_train")
)
app = modal.App("finsl-signs", image=image)
data_vol = modal.Volume.from_name("finsl-data", create_if_missing=True)
models_vol = modal.Volume.from_name("finsl-models", create_if_missing=True)
hf_vol = modal.Volume.from_name("hf-cache", create_if_missing=True)
VOLUMES = {"/data": data_vol, "/models": models_vol, "/hf-cache": hf_vol}

@app.function(gpu=GPU, volumes=VOLUMES, timeout=2 * 60 * 60)
def train(limit: int | None = None, max_steps: int | None = None) -> dict:
    import gpu_train

    log = gpu_train.train(Path("/data"), ADAPTER_DIR, limit, max_steps)
    models_vol.commit()
    return log


@app.function(gpu=GPU, volumes=VOLUMES, timeout=60 * 60)
def predict(adapter: bool = True) -> list[dict]:
    import gpu_train

    return gpu_train.predict(Path("/data"), ADAPTER_DIR if adapter else None)


@app.local_entrypoint()
def predict_local(adapter: bool = True):
    data = HERE.parent.parent / "finsl-data"
    out = data / "predictions" / ("finetuned_e2b.jsonl" if adapter else "base_e2b.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = predict.remote(adapter)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"wrote {len(rows)} rows to {out}")


@app.cls(gpu=GPU, volumes=VOLUMES, scaledown_window=300, min_containers=0)
class SignFinder:
    @modal.enter()
    def load(self):
        import gpu_train

        self.gpu_train = gpu_train
        self.tok, self.model = gpu_train._load(ADAPTER_DIR)

    @modal.fastapi_endpoint(method="POST")
    def signs(self, body: dict) -> dict:
        from finsl.prompt import parse_signs

        started = time.time()
        answer = self.gpu_train._generate(self.tok, self.model, [(str(body.get("text", ""))[:500], body.get("lang", "fi"))])[0]
        return {"signs": parse_signs(answer), "ms": int((time.time() - started) * 1000)}
