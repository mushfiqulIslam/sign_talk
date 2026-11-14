"""Made-up station announcements from templates, using only signs that exist in Signbank.

They teach the model numbers, places and vehicles, which the story corpus barely has.
Not checked by a FinSL signer; training split only.
"""
import json
import random
from pathlib import Path

STATION = Path(__file__).resolve().parent.parent / "station_examples.jsonl"

# sign, Finnish "to" (illative), Finnish "from" (elative), English
CITIES = [
    ("HELSINKI", "Helsinkiin", "Helsingistä", "Helsinki"), ("TAMPERE", "Tampereelle", "Tampereelta", "Tampere"),
    ("TURKU", "Turkuun", "Turusta", "Turku"), ("OULU", "Ouluun", "Oulusta", "Oulu"),
    ("KUOPIO", "Kuopioon", "Kuopiosta", "Kuopio"), ("JYVÄSKYLÄ", "Jyväskylään", "Jyväskylästä", "Jyväskylä"),
    ("LAHTI", "Lahteen", "Lahdesta", "Lahti"), ("VAASA", "Vaasaan", "Vaasasta", "Vaasa"),
    ("PORI", "Poriin", "Porista", "Pori"), ("JOENSUU", "Joensuuhun", "Joensuusta", "Joensuu"),
    ("KOUVOLA", "Kouvolaan", "Kouvolasta", "Kouvola"), ("SEINÄJOKI", "Seinäjoelle", "Seinäjoelta", "Seinäjoki"),
    ("MIKKELI", "Mikkeliin", "Mikkelistä", "Mikkeli"), ("VANTAA", "Vantaalle", "Vantaalta", "Vantaa"),
]
# sign, Finnish, English: long-distance vehicles go to cities, local ones don't
LONG = [("MATKUSTAA-JUNALLA", "juna", "train"), ("BUSSI", "bussi", "bus")]
LOCAL = [("METRO", "metro", "metro"), ("RAITIOVAUNU", "raitiovaunu", "tram")]
NUMBERS = {1: ("YKSI", "yksi", "one"), 2: ("KAKSI", "kaksi", "two"), 3: ("KOLME", "kolme", "three"),
           4: ("NELJÄ", "neljä", "four"), 5: ("VIISI", "viisi", "five"), 6: ("KUUSI", "kuusi", "six"),
           7: ("SEITSEMÄN", "seitsemän", "seven"), 8: ("KAHDEKSAN", "kahdeksan", "eight"),
           9: ("YHDEKSÄN", "yhdeksän", "nine"), 10: ("KYMMENEN", "kymmenen", "ten"),
           15: ("VIISITOISTA", "viisitoista", "fifteen"), 20: ("KAKSIKYMMENTÄ", "kaksikymmentä", "twenty")}
PLATFORMS = list(range(1, 11))
MINUTES = [2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20]


def _num(rng: random.Random, n: int) -> tuple[str, str, str]:
    """Speech-to-text writes numbers as words or digits; teach both."""
    sign, fi, en = NUMBERS[n]
    return (sign, str(n), str(n)) if rng.random() < 0.5 else (sign, fi, en)


def _one(rng: random.Random) -> tuple[str, str, list[str]]:
    kind = rng.randrange(7)
    if kind >= 5:  # local vehicles, no city
        vs, vf, ve = rng.choice(LOCAL)
        if kind == 5:
            ns, nf, ne = _num(rng, rng.choice(MINUTES))
            return f"{vf.capitalize()} on myöhässä {nf} minuuttia.", f"The {ve} is {ne} minutes late.", [vs, "YLI:kello", ns, "MINUUTTI"]
        ns, nf, ne = _num(rng, rng.choice(PLATFORMS))
        return f"{vf.capitalize()} lähtee laiturilta {nf}.", f"The {ve} leaves from platform {ne}.", [vs, "LÄHTEÄ", "LAITURI", ns]
    vs, vf, ve = rng.choice(LONG)
    cs, c_to, c_from, ce = rng.choice(CITIES)
    V = vf.capitalize()
    if kind == 0:
        ns, nf, ne = _num(rng, rng.choice(PLATFORMS))
        return f"{V} {c_to} lähtee laiturilta {nf}.", f"The {ve} to {ce} leaves from platform {ne}.", [vs, cs, "LÄHTEÄ", "LAITURI", ns]
    if kind == 1:
        ns, nf, ne = _num(rng, rng.choice(MINUTES))
        return f"{V} {c_to} on myöhässä {nf} minuuttia.", f"The {ve} to {ce} is {ne} minutes late.", [vs, cs, "YLI:kello", ns, "MINUUTTI"]
    if kind == 2:
        ns, nf, ne = _num(rng, rng.choice(PLATFORMS))
        return f"{V} {c_from} saapuu laiturille {nf}.", f"The {ve} from {ce} arrives at platform {ne}.", [vs, cs, "SAAPUA", "LAITURI", ns]
    if kind == 3:
        return f"Seuraava {vf} {c_to} lähtee kohta.", f"The next {ve} to {ce} leaves soon.", ["SEURAAVA", vs, cs, "LÄHTEÄ", "KOHTA"]
    ns, nf, ne = _num(rng, rng.choice(PLATFORMS))
    return (f"Laituri on muuttunut: {vf} {c_to} lähtee laiturilta {nf}.",
            f"Platform change: the {ve} to {ce} leaves from platform {ne}.",
            ["LAITURI", "MUUTTAA", vs, cs, "LÄHTEÄ", "LAITURI", ns])


def generate(n: int = 600, seed: int = 2026) -> list[dict]:
    """n distinct sentences, each in Finnish and English, never copying a hand-written val/test sentence."""
    held_out = {r["text"] for r in map(json.loads, STATION.open(encoding="utf-8")) if r["split"] != "train"}
    rng, seen, rows = random.Random(seed), set(), []
    attempts = 0
    while len(seen) < n and attempts < n * 50:
        attempts += 1
        fi, en, signs = _one(rng)
        if fi in seen or fi in held_out or en in held_out:
            continue
        seen.add(fi)
        base = {"signs": signs, "session": f"station-gen-{len(seen):04d}", "signer_pair": "station-gen",
                "split": "train", "source": "station-generated"}
        rows += [{**base, "text": fi, "lang": "fi"}, {**base, "text": en, "lang": "en", "fi_text": fi}]
    return rows
