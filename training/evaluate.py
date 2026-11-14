"""predictions.jsonl -> Markdown results table in $FINSL_DATA/results/NAME.md"""
import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

from finsl.metrics import chrf, coverage, sign_prf

DEFAULT_DATA = Path(__file__).resolve().parent.parent.parent / "finsl-data"


def table(rows: list[dict], bank: dict, name: str) -> str:
    groups = defaultdict(list)
    for r in rows:
        groups[(r["source"], r["lang"])].append(r)
        groups[("all", "all")].append(r)
    lines = [f"### {name}", "", "| Source | Input | Rows | Precision | Recall | F1 | chrF | In Signbank |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for (source, lang), items in sorted(groups.items(), key=lambda kv: (kv[0][0] == "all", kv[0])):
        prf = [sign_prf(r["signs_pred"], r["signs_ref"]) for r in items]
        mean = lambda xs: sum(xs) / len(xs)
        lines.append(
            f"| {source} | {lang} | {len(items)} | {mean([x[0] for x in prf]):.2f} | {mean([x[1] for x in prf]):.2f} "
            f"| {mean([x[2] for x in prf]):.2f} | {mean([chrf(' '.join(r['signs_pred']), ' '.join(r['signs_ref'])) for r in items]):.1f} "
            f"| {mean([coverage(r['signs_pred'], bank) for r in items]):.0%} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", type=Path, required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--data", type=Path, default=Path(os.environ.get("FINSL_DATA", DEFAULT_DATA)))
    a = ap.parse_args()
    rows = [json.loads(l) for l in a.pred.open(encoding="utf-8")]
    bank = json.loads((a.data / "signbank.json").read_text(encoding="utf-8"))
    out = a.data / "results" / f"{a.name}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = table(rows, bank, a.name)
    out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
