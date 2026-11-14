"""Turn raw CFinSL sign annotations into clean sign names (spec: Data preparation, cleaning rules)."""
import re

_FINGERSPELL = re.compile(r"^((?:[a-zåäö]-)*[a-zåäö])(?:_[a-z]+)?$")
_TRAILING_CODE = re.compile(r"_[a-zåäö]+$")  # _num, _sa, _kvkt … after the name, outside brackets
_VARIANT = re.compile(r"\(.*\)$")


def clean_sign(raw: str) -> str | None:
    """Clean one annotation; None means drop it (pointing, unclear, gesture, code only)."""
    s = raw.strip()
    if not s or s.startswith(("OS:", "OS(", "_", "@")) or s == "ZZZ" or s.endswith(":"):
        return None
    if "_ele" in s:  # a gesture, not a sign
        return None
    s = s.split("@", 1)[0]
    m = _FINGERSPELL.match(s)
    if m:
        return "FS:" + m.group(1).replace("-", "")
    if not s.endswith(")"):
        s = _TRAILING_CODE.sub("", s)
    return s or None


def clean_signs(raw: list[str]) -> list[str]:
    return [c for c in map(clean_sign, raw) if c]


def base_name(sign: str) -> str:
    """PIENI(L_alas) -> PIENI, used for Signbank lookup and scoring."""
    return _VARIANT.sub("", sign) or sign
