from pathlib import Path

import qr_page


def test_connect_link_carries_host_port_and_name():
    assert qr_page.connect_link("10.0.0.5", 8765, "Anna's laptop") == \
        "signtalk://connect?host=10.0.0.5&port=8765&name=Anna%27s+laptop"


def test_page_has_a_qr_and_the_address(tmp_path):
    path = qr_page.write_page(tmp_path / "p.html", "10.0.0.5", 8765, "Table 7")
    html = Path(path).read_text(encoding="utf-8")
    assert "<svg" in html and "10.0.0.5" in html and "Table 7" in html


def test_bundled_model_is_used_when_present(tmp_path, monkeypatch):
    import serve

    (tmp_path / "gloves-model.joblib").write_bytes(b"x")
    monkeypatch.setattr(serve, "HERE", tmp_path)
    assert serve.default_model() == tmp_path / "gloves-model.joblib"


def test_bundle_has_everything_to_run(tmp_path):
    import zipfile

    import joblib

    import bundle

    joblib.dump({"labels": ["a"]}, tmp_path / "m.joblib")
    out = bundle.make(tmp_path / "m.joblib", tmp_path / "b.zip")
    names = zipfile.ZipFile(out).namelist()
    for f in ["serve.py", "qr_page.py", "pyproject.toml", "start.bat", "start.sh", "QUICKSTART.txt", "gloves-model.joblib"]:
        assert f"SignTalk-Gloves/{f}" in names
    assert not any(n.endswith(".env") for n in names)
