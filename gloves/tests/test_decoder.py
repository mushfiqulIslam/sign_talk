from decoder import Decoder


def feed(d, labels, start=0.0, step=0.25, prob=0.9):
    out = []
    for i, label in enumerate(labels):
        out += d.push(label, prob, start + i * step)
    return out


def test_sign_needs_several_agreeing_windows():
    d = Decoder(need=3)
    assert feed(d, ["me", "me"]) == []
    assert d.push("me", 0.9, 0.5) == [("sign", "me")]


def test_same_sign_held_is_emitted_once():
    d = Decoder(need=3)
    assert feed(d, ["me"] * 20) == [("sign", "me")]


def test_low_confidence_windows_do_not_count():
    d = Decoder(need=3, min_prob=0.7)
    assert feed(d, ["me"] * 5, prob=0.5) == []


def test_rest_class_is_never_a_sign_but_allows_repeat():
    d = Decoder(need=2)
    events = feed(d, ["me", "me", "rest", "rest", "me", "me"])
    assert events == [("sign", "me"), ("sign", "me")]


def test_sentence_ends_after_a_quiet_gap():
    d = Decoder(need=2, gap_s=2.0)
    feed(d, ["me", "me", "study", "study"])
    assert d.tick(1.0) == []
    assert d.tick(3.0) == [("sentence", ["me", "study"])]
    assert d.tick(9.0) == []  # nothing new


def test_flush_ends_the_sentence():
    d = Decoder(need=2)
    feed(d, ["good", "good", "day", "day"])
    assert d.flush() == [("sentence", ["good", "day"])]
    assert d.flush() == []


def test_holding_a_sign_keeps_the_sentence_open():
    d = Decoder(need=2, gap_s=2.0)
    feed(d, ["me"] * 12)  # me held for 3 s
    assert d.tick(3.5) == []  # only 0.75 s since the hands last signed
    assert d.tick(5.0) == [("sentence", ["me"])]
