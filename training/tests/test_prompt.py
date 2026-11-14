from finsl.prompt import build_prompt, parse_signs


def test_parse_plain():
    assert parse_signs("JUNA-ASEMA HELSINKI LAITURI NELJÄ") == ["JUNA-ASEMA", "HELSINKI", "LAITURI", "NELJÄ"]


def test_parse_noise():  # RF4
    assert parse_signs("Here are the signs: juna-asema, HELSINKI.\n") == ["JUNA-ASEMA", "HELSINKI"]


def test_parse_drops_thinking():  # RF4
    assert parse_signs("<thought>hmm</thought>MIES ISTUA") == ["MIES", "ISTUA"]


def test_parse_keeps_fingerspelling_and_variants():
    assert parse_signs("FS:mika MIES PIENI(L_alas)") == ["FS:mika", "MIES", "PIENI(L_alas)"]


def test_parse_empty():
    assert parse_signs("") == []


def test_prompt_has_lang_and_text():
    p = build_prompt("The train leaves.", "en")
    assert "Language: en" in p and "Sentence: The train leaves." in p
