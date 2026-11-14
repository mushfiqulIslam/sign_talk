import pytest

from finsl.metrics import chrf, coverage, sign_prf


def test_prf_perfect():
    assert sign_prf(["A", "B"], ["A", "B"]) == (1.0, 1.0, 1.0)


def test_prf_partial():
    p, r, f = sign_prf(["A", "C"], ["A", "B", "B"])
    assert (p, round(r, 3)) == (0.5, 0.333)
    assert f == pytest.approx(0.4)


def test_prf_empty_pred():
    assert sign_prf([], ["A"]) == (0.0, 0.0, 0.0)


def test_prf_compares_base_names():
    assert sign_prf(["PIENI"], ["PIENI(L_alas)"]) == (1.0, 1.0, 1.0)


def test_chrf_identical():
    assert chrf("MIES ISTUA", "MIES ISTUA") == pytest.approx(100.0)


def test_chrf_disjoint_and_empty():
    assert chrf("XYZ", "MIES") == 0.0
    assert chrf("", "MIES") == 0.0


def test_chrf_partial_between():
    assert 0 < chrf("MIES ISTU", "MIES ISTUA") < 100


def test_coverage():
    assert coverage(["MIES", "KEKSITTY", "FS:abc"], {"MIES": {}}) == pytest.approx(2 / 3)
    assert coverage([], {}) == 0.0
