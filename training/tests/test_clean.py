import pytest

from finsl.clean import base_name, clean_sign, clean_signs


@pytest.mark.parametrize(
    "raw,clean",
    [
        ("OS:", None), ("OS:hän", None), ("ZZZ", None), ("KÄMMEN-YLÖS_ele", None),
        ("METELI@sbb", "METELI"), ("KAKSI_num@sbb", "KAKSI"), ("KAKSI_num", "KAKSI"),
        ("n-o-j-a_sa", "FS:noja"), ("n-o-j-a", "FS:noja"),
        ("PIENI(L_alas)", "PIENI(L_alas)"), ("RIITA(2T)", "RIITA(2T)"), ("", None),
        ("JUNA-ASEMA", "JUNA-ASEMA"), ("f", "FS:f"),
    ],
)
def test_clean_sign(raw, clean):
    assert clean_sign(raw) == clean


def test_clean_signs_drops_and_keeps_order():
    assert clean_signs(["OS:", "MIES", "ZZZ", "ISTUA"]) == ["MIES", "ISTUA"]


def test_base_name():
    assert base_name("PIENI(L_alas)") == "PIENI"
    assert base_name("FS:noja") == "FS:noja"
