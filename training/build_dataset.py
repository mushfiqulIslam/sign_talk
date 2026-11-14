"""CFinSL annotation files -> $FINSL_DATA/dataset/{train,val,test}.jsonl (Finnish rows)."""
import argparse
import json
import os
from collections import Counter
from pathlib import Path

from finsl.clean import clean_signs
from finsl.eaf import read_pairs
from finsl.split import signer_pair, split_for

DEFAULT_DATA = Path(__file__).resolve().parent.parent.parent / "finsl-data"
MIN_SIGNS = 2


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path(os.environ.get("FINSL_DATA", DEFAULT_DATA)))
    data = ap.parse_args().data
    out_dir = data / "dataset"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    skipped = Counter()
    for path in sorted(data.glob("elicit*/**/*.eaf")):
        session = path.stem
        pair = signer_pair(session)
        for p in read_pairs(path):
            signs = clean_signs(p.signs)
            if len(signs) < MIN_SIGNS:
                skipped["fewer than 2 signs after cleaning"] += 1
                continue
            split = split_for(pair)
            rows[split].append({
                "text": p.text, "lang": "fi", "signs": signs, "session": session,
                "signer_pair": pair, "split": split, "source": "corpus",
            })
    for split, items in rows.items():
        with open(out_dir / f"{split}.jsonl", "w", encoding="utf-8") as f:
            for r in items:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    total = sum(map(len, rows.values()))
    for split, items in rows.items():
        print(f"{split}: {len(items)} rows ({len(items) / max(total, 1):.0%})")
    print(f"skipped: {dict(skipped)}")


if __name__ == "__main__":
    main()
