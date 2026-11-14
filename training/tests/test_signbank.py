import json
from pathlib import Path

import pytest

from finsl.signbank import Entry, known, parse_dictionary_page

HERE = Path(__file__).parent
FIXTURE = (HERE / "fixtures" / "signbank_page.html").read_text()
BANK = HERE.parent.parent.parent / "finsl-data" / "signbank.json"


def test_parse_page():
    entries = parse_dictionary_page(FIXTURE)
    assert entries[0] == Entry(
        sign="JUNA-ASEMA", gloss_id=111,
        video_url="https://a3s.fi/signbank_data/media/glossvideo/JU/JUNA-ASEMA-111_vid1.mp4",
        words=["rautatieasema", "asema"],
    )


def test_entry_without_video():
    assert parse_dictionary_page(FIXTURE)[1].video_url is None


def test_known_by_exact_or_base():
    bank = {"PIENI": {"video": None, "base": "PIENI"}}
    assert known("PIENI(L_alas)", bank) and known("PIENI", bank)
    assert not known("ISO", bank)


def test_fingerspelling_is_always_known():
    assert known("FS:noja", {})


@pytest.mark.skipif(not BANK.exists(), reason="run build_signbank.py first")
def test_station_examples_use_only_known_signs():
    bank = json.loads(BANK.read_text())
    rows = [json.loads(l) for l in (HERE.parent / "station_examples.jsonl").open(encoding="utf-8")]
    assert len(rows) == 40
    unknown = {s for r in rows for s in r["signs"] if not known(s, bank)}
    assert not unknown, unknown


def test_bank_keys_match_cleaned_corpus_names():
    from finsl.signbank import make_bank
    bank = make_bank([Entry("NELJÄ_num", 1, "https://x/4.mp4"), Entry("PIENI(L_alas)", 2, None),
                      Entry("KÄSI-YLÖS_ele", 3, None)])
    assert known("NELJÄ", bank) and bank["NELJÄ"]["video"] == "https://x/4.mp4"
    assert known("PIENI", bank)
    assert "KÄSI-YLÖS_ele" not in bank  # gestures are not signs
