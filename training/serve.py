"""Live sign finder API, run on the GPU machine next to the fine-tuned model.

  SIGN_API_KEY=... FINSL_ADAPTER=~/finsl-gemma4-e2b FINSL_BANK=~/finsl-data/signbank.json \
      .venv/bin/uvicorn serve:app --host 0.0.0.0 --port 8000

POST /signs {"text": "...", "lang": "fi"|"en"} with header x-api-key -> {"signs", "videos", "dropped", "ms"}
"""
import hmac
import json
import os
import re
import threading
import time
from typing import Callable, Literal

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from finsl.prompt import parse_signs
from finsl.signbank import check_signs


class SignRequest(BaseModel):
    text: str = Field(max_length=500)
    lang: Literal["fi", "en"]


def make_app(translate: Callable[[str, str], str], bank: dict, key: str,
             video_builder: Callable[[list[str]], str | None] | None = None, video_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="FinSL sign finder")
    lock = threading.Lock()  # one GPU, one sentence at a time

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/signs")
    def signs(req: SignRequest, x_api_key: str = Header(default="")) -> dict:
        if not hmac.compare_digest(x_api_key, key):
            raise HTTPException(401, "bad key")
        started = time.time()
        try:
            with lock:
                answer = translate(req.text, req.lang)
        except Exception as e:  # noqa: BLE001 - the app falls back to captions only
            raise HTTPException(503, f"model error: {type(e).__name__}") from None
        result = check_signs(parse_signs(answer), bank)
        video = None
        if video_builder:
            try:
                name = video_builder([v for v in result["videos"] if v])
                video = f"/v/{name}" if name else None
            except Exception as e:  # noqa: BLE001 - signs still go out; the app falls back to single clips
                print(f"video build failed: {e}")
        return {**result, "video": video, "ms": int((time.time() - started) * 1000)}

    @app.get("/v/{name}")
    def sentence_video(name: str):
        """Joined sentence videos; names are unguessable hashes, so no key (the lens can't send one)."""
        if not video_dir or not re.fullmatch(r"[0-9a-f]{16}\.mp4", name) or not (video_dir / name).is_file():
            raise HTTPException(404)
        return FileResponse(video_dir / name, media_type="video/mp4")

    return app


def _gpu_app() -> FastAPI:
    import gpu_train

    tok, model = gpu_train._load(os.path.expanduser(os.environ["FINSL_ADAPTER"]))
    bank = json.load(open(os.path.expanduser(os.environ["FINSL_BANK"]), encoding="utf-8"))
    import sentence_video

    cache = Path(os.path.expanduser(os.environ.get("FINSL_VIDEO_CACHE", "~/video-cache")))
    return make_app(lambda text, lang: gpu_train._generate(tok, model, [(text, lang)])[0], bank, os.environ["SIGN_API_KEY"],
                    video_builder=lambda urls: sentence_video.build(urls, cache), video_dir=cache / "sentences")


app = _gpu_app() if os.environ.get("FINSL_ADAPTER") else None
