import io
import json
import urllib.error
import urllib.request

import pytest

from finsl.gemini import GeminiError, MissingKey, generate, load_key
from translate_english import english_row


def test_missing_key(tmp_path):  # RF5
    (tmp_path / ".env").write_text("OTHER=1\n")
    with pytest.raises(MissingKey, match="GEMMA_API_KEY missing"):
        load_key(tmp_path / ".env")


def test_missing_env_file(tmp_path):  # RF5
    with pytest.raises(MissingKey):
        load_key(tmp_path / ".env")


def test_loads_key(tmp_path):
    (tmp_path / ".env").write_text('# comment\nGEMMA_API_KEY="abc123"\n')
    assert load_key(tmp_path / ".env") == "abc123"


def test_error_message_never_contains_key(monkeypatch):  # RF5
    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"error":"bad key"}'))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(GeminiError) as excinfo:
        generate("gemma-4-26b-a4b-it", "hi", key="AIzaSECRET")
    assert "400" in str(excinfo.value) and "AIzaSECRET" not in str(excinfo.value)


def test_generate_returns_answer_without_thoughts(monkeypatch):
    body = {"candidates": [{"content": {"parts": [{"text": "hmm", "thought": True}, {"text": "MIES ISTUA"}]}}]}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout: Resp(json.dumps(body).encode()))
    assert generate("m", "p", key="k") == "MIES ISTUA"


def test_english_row_keeps_split_and_signs():  # RF3
    fi = {"text": "mies istuu.", "lang": "fi", "signs": ["MIES", "ISTUA"], "session": "S",
          "signer_pair": "013", "split": "test", "source": "corpus"}
    en = english_row(fi, "the man sits.")
    assert en["lang"] == "en" and en["text"] == "the man sits."
    assert en["split"] == "test" and en["signs"] == fi["signs"] and en["session"] == "S"
    assert en["fi_text"] == "mies istuu."
