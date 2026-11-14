"""Training examples: the shared prompt, and the sign names as the answer."""
from finsl.prompt import build_prompt


def example(row: dict) -> dict:
    return {"prompt": build_prompt(row["text"], row["lang"]), "answer": " ".join(row["signs"])}
