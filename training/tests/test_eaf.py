from pathlib import Path

from finsl.eaf import Pair, read_pairs

FIXTURES = Path(__file__).parent / "fixtures"


def test_reads_translation_with_signs_in_time_order():
    pairs = read_pairs(FIXTURES / "tiny.eaf")
    assert pairs[0] == Pair(text="mies istuu.", signs=["MIES", "ISTUA"], signer="1")


def test_two_handed_sign_counted_once():  # RF2
    assert read_pairs(FIXTURES / "tiny.eaf")[1].signs == ["KAKSI", "POIKA"]


def test_translation_without_signs_is_skipped():  # RF1
    texts = [p.text for p in read_pairs(FIXTURES / "tiny.eaf")]
    assert "ei viittomia." not in texts


def test_missing_tiers_give_no_pairs(tmp_path):  # RF1
    f = tmp_path / "empty.eaf"
    f.write_text("<ANNOTATION_DOCUMENT><TIME_ORDER/></ANNOTATION_DOCUMENT>")
    assert read_pairs(f) == []
