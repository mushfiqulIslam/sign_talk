from finsl.split import signer_pair, split_for


def test_signer_pair():
    assert signer_pair("CFINSL2015_028_05") == "028"


def test_fixed_split():
    assert split_for("013") == "test"
    assert split_for("031") == "val"
    assert split_for("011") == "train"
