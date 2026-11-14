"""Add an English row for every Finnish row (same signs, same split), translated by Gemini, cached."""
import argparse
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from finsl.gemini import GeminiError, generate, load_key

DEFAULT_DATA = Path(__file__).resolve().parent.parent.parent / "finsl-data"
MODEL = "gemini-flash-latest"
BATCH = 25
INSTRUCTION = (
    "Translate each Finnish sentence to natural English. Words in brackets are implied; "
    "keep the meaning, drop the brackets. Answer as a numbered list, same numbering, nothing else."
)


def english_row(fi_row: dict, english: str) -> dict:
    return {**fi_row, "text": english, "lang": "en", "fi_text": fi_row["text"]}


def _translate(batch: list[str], key: str) -> list[str | None]:
    prompt = INSTRUCTION + "\n\n" + "\n".join(f"{i + 1}. {t}" for i, t in enumerate(batch))
    answer = generate(MODEL, prompt, key, max_tokens=8192, timeout=150)
    found = {}
    for line in answer.splitlines():
        m = re.match(r"\s*(\d+)[.)]\s*(.+)", line)
        if m:
            found[int(m.group(1))] = m.group(2).strip()
    return [found.get(i + 1) for i in range(len(batch))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path(os.environ.get("FINSL_DATA", DEFAULT_DATA)))
    data = ap.parse_args().data
    key = load_key()
    cache_path = data / "cache" / "english.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache: dict[str, str] = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    for split in ("train", "val", "test"):
        path = data / "dataset" / f"{split}.jsonl"
        rows = [json.loads(l) for l in path.open(encoding="utf-8")]
        fi_rows = [r for r in rows if r["lang"] == "fi"]
        todo = sorted({r["text"] for r in fi_rows} - cache.keys())
        batches = [todo[i : i + BATCH] for i in range(0, len(todo), BATCH)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(_translate, b, key): b for b in batches}
            for n, fut in enumerate(as_completed(futures), 1):
                try:
                    for fi, en in zip(futures[fut], fut.result()):
                        if en:
                            cache[fi] = en
                except GeminiError as e:
                    print(f"  a batch failed: {e}")
                cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0))
                print(f"{split}: batch {n}/{len(batches)}", flush=True)
        out = fi_rows + [english_row(r, cache[r["text"]]) for r in fi_rows if r["text"] in cache]
        with path.open("w", encoding="utf-8") as f:
            for r in out:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{split}: {len(fi_rows)} fi + {len(out) - len(fi_rows)} en rows")


if __name__ == "__main__":
    main()
