"""Read CFinSL ELAN (.eaf) files: each Finnish translation with the signs made during it."""
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

SIGNERS = ("1", "2")
TWO_HANDED_MS = 200  # the same sign on both hands, starting this close together, is one sign


@dataclass
class Pair:
    text: str
    signs: list[str]
    signer: str


def _tier(root, ts, name):
    out = []
    for t in root.iter("TIER"):
        if t.get("TIER_ID") != name:
            continue
        for a in t.iter("ALIGNABLE_ANNOTATION"):
            s, e = ts.get(a.get("TIME_SLOT_REF1")), ts.get(a.get("TIME_SLOT_REF2"))
            value = (a.findtext("ANNOTATION_VALUE") or "").strip()
            if s is not None and e is not None and value:
                out.append((s, e, value))
    return out


def read_pairs(path: Path) -> list[Pair]:
    root = ET.parse(path).getroot()
    ts = {
        t.get("TIME_SLOT_ID"): int(t.get("TIME_VALUE"))
        for t in root.iter("TIME_SLOT")
        if t.get("TIME_VALUE") is not None
    }
    pairs = []
    for signer in SIGNERS:
        hands = sorted(_tier(root, ts, f"ID_{signer}_oik") + _tier(root, ts, f"ID_{signer}_vas"))
        for start, end, text in _tier(root, ts, f"Käännös_{signer}"):
            signs: list[tuple[int, str]] = []
            for gs, ge, name in hands:
                if not start <= (gs + ge) / 2 <= end:
                    continue
                if any(n == name and abs(t - gs) < TWO_HANDED_MS for t, n in signs[-2:]):
                    continue
                signs.append((gs, name))
            if signs:
                pairs.append(Pair(text=text, signs=[n for _, n in signs], signer=signer))
    return pairs
