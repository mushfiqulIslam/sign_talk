"""Small Google AI Studio client (Gemini and hosted Gemma). The key never appears in errors or logs."""
import json
import urllib.error
import urllib.request
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"  # sign_talk/.env
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class MissingKey(Exception):
    pass


class GeminiError(Exception):
    pass


def load_key(env_path: Path = ENV_PATH) -> str:
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            name, sep, value = line.strip().partition("=")
            if sep and name.strip() == "GEMMA_API_KEY" and value.strip().strip("'\""):
                return value.strip().strip("'\"")
    raise MissingKey("GEMMA_API_KEY missing in sign_talk/.env")


def generate(model: str, prompt: str, key: str, max_tokens: int = 4096, timeout: int = 150) -> str:
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2},
    }
    req = urllib.request.Request(
        URL.format(model=model),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read()[:300].decode("utf-8", "replace").replace(key, "***")
        raise GeminiError(f"{model}: HTTP {e.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise GeminiError(f"{model}: network error: {getattr(e, 'reason', e)}") from None
    parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
