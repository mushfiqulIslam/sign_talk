"""One small video per sentence for the lens: Signbank clips shrunk to 352x198, sped up, joined.

The lens plays one video at a time and loads each one before playing, so one short file per
sentence plays without gaps. Clips and sentences are cached on disk (CC BY-NC-SA material:
never committed, deleted with the machine).
"""
import hashlib
import shutil
import subprocess
import urllib.request
from pathlib import Path

WIDTH, HEIGHT = 352, 198  # fits Meta's lens limit: <= 400 px a side, <= 70,000 pixels
SPEED = 1.25


def _key(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def _download(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "finsl-hackathon"})
    with urllib.request.urlopen(req, timeout=30) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def _ffmpeg(*args: str) -> None:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", *args]
    if subprocess.run(cmd, capture_output=True).returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {args[-1]}")


def _small_clip(url: str, cache: Path) -> Path:
    """Download and shrink one Signbank clip, once."""
    out = cache / "clips" / f"{_key(url)}.mp4"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_suffix(".raw")
    _download(url, raw)
    _ffmpeg("-i", str(raw), "-an",
            "-vf", f"setpts=PTS/{SPEED},scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
                   f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps=25,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", str(out))
    raw.unlink(missing_ok=True)
    return out


def build(urls: list[str], cache: Path) -> str | None:
    """Returns the file name of the joined sentence video under cache/sentences, or None."""
    if not urls:
        return None
    name = f"{_key('|'.join(urls))}.mp4"
    out = cache / "sentences" / name
    if out.exists():
        return name
    out.parent.mkdir(parents=True, exist_ok=True)
    clips = [_small_clip(u, cache) for u in urls]
    listing = out.with_suffix(".txt")
    listing.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    # all clips share size, rate and codec, so they join without re-encoding
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(out))
    listing.unlink(missing_ok=True)
    return name
