import json

from finsl.testset import eval_sample


def _write(tmp_path, n):
    d = tmp_path / "dataset"
    d.mkdir()
    rows = []
    for i in range(n):
        base = {"signs": ["A", "B"], "session": "CFINSL2014_013_01", "signer_pair": "013", "split": "test", "source": "corpus"}
        rows += [{**base, "text": f"lause {i}", "lang": "fi"},
                 {**base, "text": f"sentence {i}", "lang": "en", "fi_text": f"lause {i}"}]
    (d / "test.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_sample_pairs_english_with_its_finnish(tmp_path):  # RF3
    _write(tmp_path, 100)
    s = eval_sample(tmp_path)
    fi = {r["text"] for r in s if r["lang"] == "fi" and r["source"] == "corpus"}
    en = {r["fi_text"] for r in s if r["lang"] == "en" and r["source"] == "corpus"}
    assert len(fi) == 72 and en == fi
    assert sum(r["source"] == "station" for r in s) == 6


def test_sample_is_stable(tmp_path):
    _write(tmp_path, 100)
    assert eval_sample(tmp_path) == eval_sample(tmp_path)
