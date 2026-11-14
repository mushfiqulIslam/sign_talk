from pathlib import Path

import sentence_video as sv


def fake_tools(monkeypatch, calls):
    def fake_download(url, dest):
        dest.write_bytes(b"raw " + url.encode())

    def fake_run(cmd, **kw):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b"mp4")  # ffmpeg's last argument is the output file

        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(sv, "_download", fake_download)
    monkeypatch.setattr(sv.subprocess, "run", fake_run)


def test_joins_clips_into_one_named_file(tmp_path, monkeypatch):
    calls = []
    fake_tools(monkeypatch, calls)
    name = sv.build(["https://x/a.mp4", "https://x/b.mp4"], tmp_path)
    assert name.endswith(".mp4") and (tmp_path / "sentences" / name).exists()
    shrink = [c for c in calls if any("scale=352:198" in a for a in c)]
    assert len(shrink) == 2  # each clip shrunk to the lens size once


def test_same_signs_same_file_and_cached(tmp_path, monkeypatch):
    calls = []
    fake_tools(monkeypatch, calls)
    a = sv.build(["https://x/a.mp4", "https://x/b.mp4"], tmp_path)
    n = len(calls)
    b = sv.build(["https://x/a.mp4", "https://x/b.mp4"], tmp_path)
    assert a == b and len(calls) == n  # nothing rebuilt


def test_shared_clip_shrunk_once(tmp_path, monkeypatch):
    calls = []
    fake_tools(monkeypatch, calls)
    sv.build(["https://x/a.mp4", "https://x/b.mp4"], tmp_path)
    sv.build(["https://x/a.mp4", "https://x/c.mp4"], tmp_path)
    shrink = [c for c in calls if any("scale=352:198" in a for a in c)]
    assert len(shrink) == 3


def test_no_clips_no_video(tmp_path):
    assert sv.build([], tmp_path) is None
