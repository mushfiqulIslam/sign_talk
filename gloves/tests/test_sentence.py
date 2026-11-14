import sentence


def test_words_for_each_sign_in_both_languages():
    assert sentence.WORDS["study"] == ("opiskella", "study")
    assert set(sentence.WORDS) == {"me", "name", "address", "study", "university", "Aalto", "nice", "meet", "good", "day"}


def test_fallback_without_key_joins_the_words(monkeypatch):
    monkeypatch.setattr(sentence, "_api_key", lambda: None)
    s = sentence.make(["good", "study", "day"])  # not in the phrase book
    assert s == {"fi": "Hyvä opiskella päivä.", "en": "Good study day.", "by": "words"}


def test_model_answer_is_used(monkeypatch):
    monkeypatch.setattr(sentence, "_api_key", lambda: "k")
    monkeypatch.setattr(sentence, "_ask_gemini", lambda prompt, key: '{"fi": "Opiskelen Aallossa.", "en": "I study at Aalto."}')
    assert sentence.make(["me", "study", "Aalto"]) == {"fi": "Opiskelen Aallossa.", "en": "I study at Aalto.", "by": "gemini"}


def test_model_failure_falls_back(monkeypatch):
    monkeypatch.setattr(sentence, "_api_key", lambda: "k")
    def boom(prompt, key):
        raise TimeoutError
    monkeypatch.setattr(sentence, "_ask_gemini", boom)
    assert sentence.make(["good", "day"])["by"] == "words"


def test_phrase_book_gives_natural_sentences_without_a_key(monkeypatch):
    monkeypatch.setattr(sentence, "_api_key", lambda: None)
    assert sentence.make(["me", "study", "Aalto", "university"]) == \
        {"fi": "Opiskelen Aalto-yliopistossa.", "en": "I study at Aalto University.", "by": "phrasebook"}
    assert sentence.make(["nice", "meet"])["en"] == "Nice to meet you."
