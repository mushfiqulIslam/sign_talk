"""The one prompt format, shared by training, evaluation and the live endpoint."""
import re

INSTRUCTION = (
    "Translate the sentence into Finnish Sign Language (FinSL) sign names, in signing order.\n"
    "Answer with sign names only, in capitals, separated by spaces. Spell names as FS:name."
)

_THOUGHT = re.compile(r"<(thought|think)>.*?</\1>", re.S | re.I)
_TOKEN = re.compile(r"^(FS:[a-zåäö0-9]+|[A-ZÅÄÖ0-9][A-ZÅÄÖ0-9\-]*(\([^)\s]*\))?)$")


def build_prompt(text: str, lang: str) -> str:
    return f"{INSTRUCTION}\nLanguage: {lang}\nSentence: {text}"


def _normalise(token: str) -> str:
    token = token.strip(".,;!?\"'")
    if token[:3].upper() == "FS:":
        return "FS:" + token[3:].lower()
    head, paren, tail = token.partition("(")
    return head.upper() + paren + tail


def parse_signs(output: str) -> list[str]:
    """Model answer -> sign names, ignoring thinking text and any lead-in like 'Here are the signs:'."""
    text = _THOUGHT.sub(" ", output)
    signs = []
    for line in text.splitlines():
        if ":" in line:  # drop a lead-in, but keep FS:name tokens
            lead, _, rest = line.rpartition(": ")
            if lead and not lead.strip().upper().startswith("FS"):
                line = rest
        for raw in re.split(r"[\s,]+", line):
            token = _normalise(raw) if raw else ""
            if token and _TOKEN.match(token):
                signs.append(token)
    return signs
