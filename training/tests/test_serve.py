from fastapi.testclient import TestClient

from serve import make_app

BANK = {"HELSINKI": {"video": "https://x/h.mp4", "base": "HELSINKI"}}


def client(answer="HELSINKI KEKSITTY", fail=False):
    def translate(text, lang):
        if fail:
            raise RuntimeError("gpu fell over")
        return answer
    return TestClient(make_app(translate, BANK, key="secret"))


def test_signs_checked_against_signbank():
    r = client().post("/signs", json={"text": "Helsinki", "lang": "fi"}, headers={"x-api-key": "secret"})
    assert r.status_code == 200
    body = r.json()
    assert body["signs"] == ["HELSINKI"] and body["videos"] == ["https://x/h.mp4"] and body["dropped"] == ["KEKSITTY"]
    assert isinstance(body["ms"], int)


def test_wrong_key_rejected():
    r = client().post("/signs", json={"text": "x", "lang": "fi"}, headers={"x-api-key": "nope"})
    assert r.status_code == 401


def test_bad_language_rejected():
    r = client().post("/signs", json={"text": "x", "lang": "de"}, headers={"x-api-key": "secret"})
    assert r.status_code == 422


def test_model_failure_gives_empty_signs_not_crash():
    r = client(fail=True).post("/signs", json={"text": "x", "lang": "fi"}, headers={"x-api-key": "secret"})
    assert r.status_code == 503


def test_health_needs_no_key():
    assert client().get("/health").json() == {"ok": True}


def test_sentence_video_link_and_file(tmp_path):
    (tmp_path / "sentences").mkdir()
    (tmp_path / "sentences" / "0123456789abcdef.mp4").write_bytes(b"mp4data")
    app = make_app(lambda t, l: "HELSINKI", BANK, key="secret",
                   video_builder=lambda urls: "0123456789abcdef.mp4", video_dir=tmp_path / "sentences")
    c = TestClient(app)
    body = c.post("/signs", json={"text": "x", "lang": "fi"}, headers={"x-api-key": "secret"}).json()
    assert body["video"] == "/v/0123456789abcdef.mp4"
    r = c.get("/v/0123456789abcdef.mp4")
    assert r.status_code == 200 and r.content == b"mp4data" and r.headers["content-type"] == "video/mp4"


def test_video_failure_still_returns_signs(tmp_path):
    def broken(urls):
        raise RuntimeError("ffmpeg died")
    c = TestClient(make_app(lambda t, l: "HELSINKI", BANK, key="secret", video_builder=broken, video_dir=tmp_path))
    body = c.post("/signs", json={"text": "x", "lang": "fi"}, headers={"x-api-key": "secret"}).json()
    assert body["signs"] == ["HELSINKI"] and body["video"] is None


def test_video_path_cannot_escape(tmp_path):
    c = TestClient(make_app(lambda t, l: "", BANK, key="secret", video_builder=lambda u: None, video_dir=tmp_path))
    assert c.get("/v/..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert c.get("/v/nothere.mp4").status_code == 404
