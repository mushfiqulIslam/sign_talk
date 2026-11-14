"""The fixed evaluation sample, shared by every model so the scores compare fairly."""
import json
import random
from pathlib import Path

STATION = Path(__file__).resolve().parent.parent / "station_examples.jsonl"
SAMPLE_PER_LANG = 72
SEED = 2026


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open(encoding="utf-8")]


def rows_for(split: str, data: Path, generated: bool = True) -> list[dict]:
    """Corpus rows + hand-written station rows, plus template station rows for training."""
    from finsl.station_gen import generate

    extra = generate() if split == "train" and generated else []
    return load(data / "dataset" / f"{split}.jsonl") + [r for r in load(STATION) if r["split"] == split] + extra


def eval_sample(data: Path) -> list[dict]:
    """All station test rows, plus SAMPLE_PER_LANG corpus sentences in Finnish and the same ones in English."""
    test = rows_for("test", data)
    fi = [r for r in test if r["source"] == "corpus" and r["lang"] == "fi"]
    chosen_fi = random.Random(SEED).sample(fi, min(SAMPLE_PER_LANG, len(fi)))
    keys = {(r["session"], r["text"]) for r in chosen_fi}
    en = [r for r in test if r["source"] == "corpus" and r["lang"] == "en" and (r["session"], r.get("fi_text")) in keys]
    return [r for r in test if r["source"] == "station"] + chosen_fi + en
