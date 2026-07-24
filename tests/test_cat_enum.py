import sys
from enum import Enum

import pytest

from DisplayCAL.colorspace_to_vrml import CAT


@pytest.mark.parametrize(
    "cat",
    [
        CAT.Bradford,
        CAT.BS,
        CAT.BS_PC,
        CAT.CAT02,
        CAT.CAT02BS,
        CAT.CAT97s,
        CAT.CIE2012_2,
        CAT.CMCCAT2000,
        CAT.HPE_D65,
        CAT.HPE_E,
        CAT.IPT,
        CAT.Sharp,
        CAT.XYZ_Scaling,
    ],
)
def test_it_is_an_enum(cat):
    """CAT is an Enum."""
    assert isinstance(cat, Enum)


@pytest.mark.parametrize(
    "cat,expected_value",
    [
        [CAT.Bradford, "Bradford"],
        [CAT.BS, "BS"],
        [CAT.BS_PC, "BS-PC"],
        [CAT.CAT02, "CAT02"],
        [CAT.CAT02BS, "CAT02BS"],
        [CAT.CAT97s, "CAT97s"],
        [CAT.CIE2012_2, "CIE2012_2"],
        [CAT.CMCCAT2000, "CMCCAT2000"],
        [CAT.HPE_D65, "HPE D65"],
        [CAT.HPE_E, "HPE E"],
        [CAT.IPT, "IPT"],
        [CAT.Sharp, "Sharp"],
        [CAT.XYZ_Scaling, "XYZ scaling"],
    ],
)
def test_enum_values(cat, expected_value):
    """Test enum values."""
    assert cat.value == expected_value


@pytest.mark.parametrize(
    "cat,expected_name",
    [
        [CAT.Bradford, "Bradford"],
        [CAT.BS, "BS"],
        [CAT.BS_PC, "BS_PC"],
        [CAT.CAT02, "CAT02"],
        [CAT.CAT02BS, "CAT02BS"],
        [CAT.CAT97s, "CAT97s"],
        [CAT.CIE2012_2, "CIE2012_2"],
        [CAT.CMCCAT2000, "CMCCAT2000"],
        [CAT.HPE_D65, "HPE_D65"],
        [CAT.HPE_E, "HPE_E"],
        [CAT.IPT, "IPT"],
        [CAT.Sharp, "Sharp"],
        [CAT.XYZ_Scaling, "XYZ_Scaling"],
    ],
)
def test_enum_names(cat, expected_name):
    """Test enum names."""
    assert cat.name == expected_name


@pytest.mark.parametrize(
    "cat,expected_value",
    [
        [CAT.Bradford, "Bradford"],
        [CAT.BS, "BS"],
        [CAT.BS_PC, "BS-PC"],
        [CAT.CAT02, "CAT02"],
        [CAT.CAT02BS, "CAT02BS"],
        [CAT.CAT97s, "CAT97s"],
        [CAT.CIE2012_2, "CIE2012_2"],
        [CAT.CMCCAT2000, "CMCCAT2000"],
        [CAT.HPE_D65, "HPE D65"],
        [CAT.HPE_E, "HPE E"],
        [CAT.IPT, "IPT"],
        [CAT.Sharp, "Sharp"],
        [CAT.XYZ_Scaling, "XYZ scaling"],
    ],
)
def test_enum_as_str(cat, expected_value):
    """Test enum names."""
    assert str(cat) == expected_value


def test_to_cat_cat_is_skipped():
    """CAT.to_cat() cat is skipped."""
    with pytest.raises(TypeError) as cm:
        _ = CAT.to_cat()

    py_error_message = {
        9: "to_cat() missing 1 required positional argument: 'cat'",
    }.get(
        sys.version_info.minor,
        "CAT.to_cat() missing 1 required positional argument: 'cat'",
    )
    assert str(cm.value) == py_error_message


def test_to_cat_cat_is_none():
    """CAT.to_cat() cat is None."""
    with pytest.raises(TypeError) as cm:
        _ = CAT.to_cat(None)
    assert str(cm.value) == (
        "cat should be a CAT enum value or one of ['BS', 'BS-PC', 'BS_PC', "
        "'Bradford', 'CAT02', 'CAT02BS', 'CAT97s', 'CIE2012_2', 'CMCCAT2000', "
        "'HPE D65', 'HPE E', 'HPE_D65', 'HPE_E', 'IPT', 'Sharp', "
        "'XYZ scaling', 'XYZ_Scaling'], not NoneType: 'None'"
    )


def test_to_cat_cat_is_not_a_str():
    """CAT.to_cat() cat is not a str."""
    with pytest.raises(TypeError) as cm:
        _ = CAT.to_cat(12334.123)

    assert str(cm.value) == (
        "cat should be a CAT enum value or one of ['BS', 'BS-PC', 'BS_PC', "
        "'Bradford', 'CAT02', 'CAT02BS', 'CAT97s', 'CIE2012_2', 'CMCCAT2000', "
        "'HPE D65', 'HPE E', 'HPE_D65', 'HPE_E', 'IPT', 'Sharp', "
        "'XYZ scaling', 'XYZ_Scaling'], not float: '12334.123'"
    )


def test_to_cat_cat_is_not_a_valid_str():
    """CAT.to_cat() cat is not a valid str."""
    with pytest.raises(ValueError) as cm:
        _ = CAT.to_cat("not a valid value")

    assert str(cm.value) == (
        "cat should be a CAT enum value or one of ['BS', 'BS-PC', 'BS_PC', "
        "'Bradford', 'CAT02', 'CAT02BS', 'CAT97s', 'CIE2012_2', 'CMCCAT2000', "
        "'HPE D65', 'HPE E', 'HPE_D65', 'HPE_E', 'IPT', 'Sharp', "
        "'XYZ scaling', 'XYZ_Scaling'], not 'not a valid value'"
    )


@pytest.mark.parametrize(
    "cat_name,cat",
    [
        # Bradford
        ["Bradford", CAT.Bradford],
        ["bradford", CAT.Bradford],
        ["BRADFORD", CAT.Bradford],
        ["BrAdFoRd", CAT.Bradford],
        ["bRaDfOrD", CAT.Bradford],
        # BS
        ["BS", CAT.BS],
        ["bs", CAT.BS],
        ["Bs", CAT.BS],
        ["bS", CAT.BS],
        # BS_PC
        ["BS_PC", CAT.BS_PC],
        ["bs_pc", CAT.BS_PC],
        ["Bs_Pc", CAT.BS_PC],
        ["bS_pC", CAT.BS_PC],
        ["BS-PC", CAT.BS_PC],
        ["bs-pc", CAT.BS_PC],
        ["Bs-Pc", CAT.BS_PC],
        ["bS-pC", CAT.BS_PC],
        # CAT02
        ["CAT02", CAT.CAT02],
        ["cat02", CAT.CAT02],
        ["CaT02", CAT.CAT02],
        ["cAt02", CAT.CAT02],
        # CAT02BS
        ["CAT02BS", CAT.CAT02BS],
        ["cat02bs", CAT.CAT02BS],
        ["CaT02bS", CAT.CAT02BS],
        ["cAt02Bs", CAT.CAT02BS],
        # CAT97s
        ["CAT97s", CAT.CAT97s],
        ["CAT97S", CAT.CAT97s],
        ["cat97s", CAT.CAT97s],
        ["cAt97s", CAT.CAT97s],
        ["CaT97S", CAT.CAT97s],
        # CIE2012_2
        ["CIE2012_2", CAT.CIE2012_2],
        ["cie2012_2", CAT.CIE2012_2],
        ["CiE2012_2", CAT.CIE2012_2],
        ["cIe2012_2", CAT.CIE2012_2],
        # CMCCAT2000
        ["CMCCAT2000", CAT.CMCCAT2000],
        ["cmccat2000", CAT.CMCCAT2000],
        ["CmCcAt2000", CAT.CMCCAT2000],
        ["cMcCaT2000", CAT.CMCCAT2000],
        # HPE_D65
        ["HPE_D65", CAT.HPE_D65],
        ["hpe_d65", CAT.HPE_D65],
        ["hPe_D65", CAT.HPE_D65],
        ["HpE_d65", CAT.HPE_D65],
        ["HPE D65", CAT.HPE_D65],
        ["hpe d65", CAT.HPE_D65],
        ["hPe D65", CAT.HPE_D65],
        ["HpE d65", CAT.HPE_D65],
        # HPE_E
        ["HPE_E", CAT.HPE_E],
        ["hpe_e", CAT.HPE_E],
        ["hPe_E", CAT.HPE_E],
        ["HpE_e", CAT.HPE_E],
        ["HPE E", CAT.HPE_E],
        ["hpe e", CAT.HPE_E],
        ["hPe E", CAT.HPE_E],
        ["HpE e", CAT.HPE_E],
        # IPT
        ["IPT", CAT.IPT],
        ["ipt", CAT.IPT],
        ["IpT", CAT.IPT],
        ["iPt", CAT.IPT],
        # Sharp
        ["Sharp", CAT.Sharp],
        ["SHARP", CAT.Sharp],
        ["sharp", CAT.Sharp],
        ["ShArP", CAT.Sharp],
        ["sHaRp", CAT.Sharp],
        # XYZ
        ["XYZ_SCALING", CAT.XYZ_Scaling],
        ["xyz_scaling", CAT.XYZ_Scaling],
        ["Xyz Scaling", CAT.XYZ_Scaling],
        ["xyz scaling", CAT.XYZ_Scaling],
        ["XYZ SCALING", CAT.XYZ_Scaling],
        ["xYz sCaLiNg", CAT.XYZ_Scaling],
        ["XyZ ScAlInG", CAT.XYZ_Scaling],
    ],
)
def test_schedule_cat_to_cat_is_working_properly(cat_name, cat):
    """CAT can parse schedule cat names."""
    assert CAT.to_cat(cat_name) == cat
