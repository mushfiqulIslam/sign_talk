"""Finnish Signbank dictionary pages -> sign name, video URL and Finnish words."""
import re
from dataclasses import dataclass, field

from finsl.clean import base_name

_ENTRY = re.compile(r'href="/dictionary/gloss/(\d+)"[^>]*>\s*<h3[^>]*gloss-idgloss[^>]*>([^<]+)</h3>')
_VIDEO = re.compile(r'<source src="(https://[^"]+\.mp4)"')
_WORDS = re.compile(r'class="gloss-keywords">([^<]*)<')


@dataclass
class Entry:
    sign: str
    gloss_id: int
    video_url: str | None
    words: list[str] = field(default_factory=list)


def parse_dictionary_page(html: str) -> list[Entry]:
    matches = list(_ENTRY.finditer(html))
    entries = []
    for i, m in enumerate(matches):
        chunk = html[m.end() : matches[i + 1].start() if i + 1 < len(matches) else len(html)]
        video = _VIDEO.search(chunk)
        words = _WORDS.search(chunk)
        entries.append(Entry(
            sign=m.group(2).strip(), gloss_id=int(m.group(1)),
            video_url=video.group(1) if video else None,
            words=[w.strip() for w in words.group(1).split(",") if w.strip()] if words else [],
        ))
    return entries


def known(sign: str, bank: dict) -> bool:
    """A sign may be shown only if Signbank has it (exact or base name). Fingerspelling always works."""
    return sign.startswith("FS:") or sign in bank or base_name(sign) in bank


def make_bank(entries: list[Entry]) -> dict[str, dict]:
    """Keyed by the same cleaned names the corpus uses (NELJÄ_num -> NELJÄ), plus base names."""
    from finsl.clean import clean_sign

    bank: dict[str, dict] = {}
    for e in entries:
        name = clean_sign(e.sign)
        if name and name not in bank:
            bank[name] = {"video": e.video_url, "base": base_name(name), "words": e.words, "id": e.gloss_id,
                          "signbank_name": e.sign}
    for v in list(bank.values()):
        bank.setdefault(v["base"], v)
    return bank


def check_signs(signs: list[str], bank: dict) -> dict:
    """Keep only signs Signbank has (spec anti-goal: never show an invented sign), with their video links."""
    kept, videos, dropped = [], [], []
    for s in signs:
        if s.startswith("FS:"):
            kept.append(s)
            videos.append(None)
        elif known(s, bank):
            kept.append(s)
            videos.append((bank.get(s) or bank[base_name(s)])["video"])
        else:
            dropped.append(s)
    return {"signs": kept, "videos": videos, "dropped": dropped}
