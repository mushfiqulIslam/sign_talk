import json
from pathlib import Path

import pytest

from finsl.signbank import known
from finsl.station_gen import generate

BANK = Path(__file__).resolve().parent.parent.parent.parent / "finsl-data" / "signbank.json"
STATION = Path(__file__).resolve().parent.parent / "station_examples.jsonl"


def test_pairs_and_size():
    rows = generate(n=200, seed=1)
    fi = [r for r in rows if r["lang"] == "fi"]
    en = [r for r in rows if r["lang"] == "en"]
    assert len(fi) == len(en) == 200
    assert {r["session"] for r in fi} == {r["session"] for r in en}
    assert all(r["source"] == "station-generated" and r["split"] == "train" for r in rows)


def test_number_seven_is_seitseman():
    rows = generate(n=2000, seed=1)
    sevens = [r for r in rows if r["lang"] == "en" and "platform 7." in r["text"]]
    assert sevens and all("SEITSEMÄN" in r["signs"] for r in sevens)


def test_never_copies_handwritten_val_or_test():
    held = {json.loads(l)["text"] for l in STATION.open(encoding="utf-8") if json.loads(l)["split"] != "train"}
    assert not held & {r["text"] for r in generate(n=2000, seed=1)}


@pytest.mark.skipif(not BANK.exists(), reason="run build_signbank.py first")
def test_only_known_signs():
    bank = json.loads(BANK.read_text())
    assert all(known(s, bank) for r in generate(n=2000, seed=1) for s in r["signs"])
