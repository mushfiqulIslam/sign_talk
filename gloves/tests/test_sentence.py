import sentence


def test_words_for_each_sign_in_both_languages():
    assert sentence.WORDS["study"] == ("opiskella", "study")
    assert set(sentence.WORDS) == {"me", "name", "address", "study", "university", "Aalto", "nice", "meet", "good", "day"}


def test_fallback_without_key_joins_the_words(monkeypatch):
    monkeypatch.setattr(sentence, "_api_key", lambda: None)
    s = sentence.make(["me", "study", "Aalto", "university"])
    assert s == {"fi": "Minä opiskella Aalto yliopisto.", "en": "Me study Aalto university.", "by": "words"}


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
