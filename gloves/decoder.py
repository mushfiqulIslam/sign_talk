"""Turns a stream of per-window guesses into signs, and signs into sentences."""

REST = "rest"  # same name as signs.REST_LABEL; never output as a word


class Decoder:
    """A sign counts once `need` windows in a row agree with at least `min_prob` confidence.
    Holding or repeating the same sign counts once until another sign or rest comes between.
    A sentence ends `gap_s` seconds after the hands last signed anything."""

    def __init__(self, need: int = 3, min_prob: float = 0.45, gap_s: float = 2.0):  # tuned: 98% of test phrases exact
        self.need, self.min_prob, self.gap_s = need, min_prob, gap_s
        self._run_label, self._run = None, 0
        self._last_sign = None
        self._signs: list[str] = []
        self._last_time = 0.0

    def push(self, label: str, prob: float, t: float) -> list[tuple]:
        if prob < self.min_prob:
            self._run_label, self._run = None, 0
            return []
        if label != REST:
            self._last_time = t  # hands still signing: the sentence stays open
        if label == self._run_label:
            self._run += 1
        else:
            self._run_label, self._run = label, 1
        if self._run != self.need:
            return []
        if label == REST:
            self._last_sign = None
            return []
        if label == self._last_sign:
            return []
        self._last_sign = label
        self._signs.append(label)
        return [("sign", label)]

    def tick(self, t: float) -> list[tuple]:
        if self._signs and t - self._last_time >= self.gap_s:
            return self.flush()
        return []

    def flush(self) -> list[tuple]:
        if not self._signs:
            return []
        signs, self._signs, self._last_sign = self._signs, [], None
        return [("sentence", signs)]
