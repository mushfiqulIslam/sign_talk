"""Scores for predicted sign lists: precision/recall/F1, chrF, and Signbank coverage."""
from collections import Counter

from finsl.clean import base_name
from finsl.signbank import known


def sign_prf(pred: list[str], ref: list[str]) -> tuple[float, float, float]:
    """Multiset overlap on base names (a sign may repeat)."""
    p, r = Counter(map(base_name, pred)), Counter(map(base_name, ref))
    hit = sum((p & r).values())
    if not hit:
        return 0.0, 0.0, 0.0
    precision, recall = hit / sum(p.values()), hit / sum(r.values())
    return precision, recall, 2 * precision * recall / (precision + recall)


def _ngrams(text: str, n: int) -> Counter:
    s = text.replace(" ", "")
    return Counter(s[i : i + n] for i in range(len(s) - n + 1))


def chrf(pred: str, ref: str, max_n: int = 6, beta: float = 2.0) -> float:
    """Standard chrF (character n-grams 1-6, spaces removed, beta 2), 0-100."""
    precisions, recalls = [], []
    for n in range(1, max_n + 1):
        hyp, tgt = _ngrams(pred, n), _ngrams(ref, n)
        if not hyp or not tgt:
            continue
        hit = sum((hyp & tgt).values())
        precisions.append(hit / sum(hyp.values()))
        recalls.append(hit / sum(tgt.values()))
    if not precisions:
        return 0.0
    p, r = sum(precisions) / len(precisions), sum(recalls) / len(recalls)
    if p + r == 0:
        return 0.0
    return 100 * (1 + beta**2) * p * r / (beta**2 * p + r)


def coverage(pred: list[str], bank: dict) -> float:
    """Share of predicted signs that Signbank has (before the check removes the rest)."""
    return sum(known(s, bank) for s in pred) / len(pred) if pred else 0.0
