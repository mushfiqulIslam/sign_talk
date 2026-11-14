"""No-training baseline: hosted Gemma 4 with the 8 closest training examples in the prompt."""
import argparse
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from finsl.gemini import GeminiError, generate, load_key
from finsl.prompt import build_prompt, parse_signs
from finsl.testset import eval_sample, rows_for

DEFAULT_DATA = Path(__file__).resolve().parent.parent.parent / "finsl-data"
MODEL = "gemma-4-26b-a4b-it"
SHOTS = 8


def _words(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def few_shot_prompt(row: dict, pool: list[dict]) -> str:
    """Examples from training rows in the same language that share the most words."""
    w = _words(row["text"])
    same_lang = [r for r in pool if r["lang"] == row["lang"]]
    best = sorted(same_lang, key=lambda r: -len(w & _words(r["text"])))[:SHOTS]
    examples = "\n\n".join(f"{build_prompt(r['text'], r['lang'])}\nSigns: {' '.join(r['signs'])}" for r in best)
    return f"Examples:\n\n{examples}\n\nNow the real one.\n{build_prompt(row['text'], row['lang'])}\nSigns:"


def predict_row(row: dict, pool: list[dict], key: str) -> dict:
    prompt = few_shot_prompt(row, pool)
    started = time.time()
    answer = ""
    for attempt in range(2):
        try:
            answer = generate(MODEL, prompt, key, max_tokens=16384, timeout=400)  # it thinks ~4k+ tokens first
            break
        except GeminiError as e:
            print(f"  retry ({e})"[:200], flush=True)
    return {"text": row["text"], "lang": row["lang"], "source": row["source"], "signs_ref": row["signs"],
            "signs_pred": parse_signs(answer), "raw": answer[:500], "seconds": round(time.time() - started, 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path(os.environ.get("FINSL_DATA", DEFAULT_DATA)))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--fill-empty", action="store_true", help="redo only rows whose answer was empty")
    a = ap.parse_args()
    key = load_key()
    pool = rows_for("train", a.data)
    rows = eval_sample(a.data)[: a.limit]
    out = a.data / "predictions" / ("baseline_gemma4" + (f"_limit{a.limit}" if a.limit else "") + ".jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {}
    if a.fill_empty and out.exists():
        done = {(r["text"], r["lang"]): r for r in map(json.loads, out.open(encoding="utf-8")) if r["signs_pred"]}
    todo = [r for r in rows if (r["text"], r["lang"]) not in done]
    print(f"{len(done)} kept, {len(todo)} to predict")
    with ThreadPoolExecutor(a.workers) as pool_ex, out.open("w", encoding="utf-8") as f:
        for r in done.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        for i, result in enumerate(pool_ex.map(lambda r: predict_row(r, pool, key), todo), 1):
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
            f.flush()
            print(f"{i}/{len(todo)} {result['seconds']}s {' '.join(result['signs_pred'])[:80]}", flush=True)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
