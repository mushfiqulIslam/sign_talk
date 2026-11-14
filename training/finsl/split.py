"""Split by signer pair, so test signers are never seen in training."""
from typing import Literal

TEST = {"013", "028"}
VAL = {"017", "031"}


def signer_pair(session: str) -> str:
    """CFINSL2014_011_03 -> 011 (the pair of signers recorded together)."""
    return session.split("_")[1]


def split_for(pair: str) -> Literal["train", "val", "test"]:
    return "test" if pair in TEST else "val" if pair in VAL else "train"
