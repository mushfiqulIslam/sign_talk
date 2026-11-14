"""Signs -> a natural Finnish and English sentence (Gemini), or the plain words if that fails."""
import json
import os
import re
import urllib.request
from pathlib import Path

# glove sign -> (Finnish word, English word)
WORDS = {
    "me": ("minä", "me"), "name": ("nimi", "name"), "address": ("osoite", "address"),
    "study": ("opiskella", "study"), "university": ("yliopisto", "university"), "Aalto": ("Aalto", "Aalto"),
    "nice": ("mukava", "nice"), "meet": ("tavata", "meet"), "good": ("hyvä", "good"), "day": ("päivä", "day"),
}
# Natural sentences for the demo phrases, used when there is no Gemini key (e.g. a shared bundle).
PHRASES = {
    ("me", "study", "Aalto", "university"): ("Opiskelen Aalto-yliopistossa.", "I study at Aalto University."),
    ("me", "study", "university"): ("Opiskelen yliopistossa.", "I study at the university."),
    ("me", "study"): ("Opiskelen.", "I am a student."),
    ("nice", "meet"): ("Hauska tavata.", "Nice to meet you."),
    ("good", "day"): ("Hyvää päivää!", "Good day!"),
    ("me", "name"): ("Nimeni on…", "My name is…"),
    ("me", "address"): ("Osoitteeni on…", "My address is…"),
    ("Aalto", "university"): ("Aalto-yliopisto.", "Aalto University."),
}
MODEL = "gemini-flash-latest"
PROMPT = """A person signed these Finnish Sign Language signs, in this order: {signs}
(word meanings: {glosses}).
Write what they most likely meant as one short, natural spoken sentence, in Finnish and in English.
Keep the meaning; add only the small words a sentence needs. Answer only JSON: {{"fi": "...", "en": "..."}}"""


def _api_key() -> str | None:
    if os.environ.get("GEMMA_API_KEY"):
        return os.environ["GEMMA_API_KEY"]
    for env in (Path.cwd() / ".env", Path.cwd().parent / ".env", Path.home() / ".signtalk" / ".env"):
        if env.is_file():
            for line in env.read_text().splitlines():
                if line.startswith("GEMMA_API_KEY="):
                    return line.split("=", 1)[1].strip() or None
    return None


def _ask_gemini(prompt: str, key: str) -> str:
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "thinkingConfig": {"thinkingBudget": 0}}}
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=8) as r:
        data = json.load(r)
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _plain(signs: list[str]) -> dict:
    fi = " ".join(WORDS.get(s, (s, s))[0] for s in signs)
    en = " ".join(WORDS.get(s, (s, s))[1] for s in signs)
    return {"fi": fi[:1].upper() + fi[1:] + ".", "en": en[:1].upper() + en[1:] + ".", "by": "words"}


def make(signs: list[str]) -> dict:
    """{"fi", "en", "by"}: by = "gemini" or "words" (fallback)."""
    key = _api_key()
    if not key:
        known = PHRASES.get(tuple(signs))
        return {"fi": known[0], "en": known[1], "by": "phrasebook"} if known else _plain(signs)
    glosses = ", ".join(f"{s} = {WORDS.get(s, (s, s))[0]} / {WORDS.get(s, (s, s))[1]}" for s in signs)
    try:
        text = _ask_gemini(PROMPT.format(signs=" ".join(s.upper() for s in signs), glosses=glosses), key)
        found = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        if found.get("fi") and found.get("en"):
            return {"fi": found["fi"].strip(), "en": found["en"].strip(), "by": "gemini"}
    except Exception as e:  # noqa: BLE001 - never block the conversation on the model
        print(f"sentence model failed ({type(e).__name__}); using plain words")
    return _plain(signs)
