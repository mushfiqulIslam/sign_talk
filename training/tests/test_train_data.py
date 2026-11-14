import json

from finsl.train_data import example


def test_example_is_prompt_and_answer():
    row = {"text": "mies istuu.", "lang": "fi", "signs": ["MIES", "ISTUA"]}
    ex = example(row)
    assert ex["answer"] == "MIES ISTUA"
    assert "Sentence: mies istuu." in ex["prompt"] and "Language: fi" in ex["prompt"]
