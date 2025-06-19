from enum import Enum
import sys

import pytest

from DisplayCAL.colorspace_to_vrml import ColorSpace

@pytest.mark.parametrize(
    "colorspace",
    [
        ColorSpace.DIN99,
        ColorSpace.DIN99b,
        ColorSpace.DIN99c,
        ColorSpace.DIN99d,
        ColorSpace.HSI,
        ColorSpace.HSL,
        ColorSpace.HSV,
        ColorSpace.ICtCp,
        ColorSpace.IPT,
        ColorSpace.Lab,
        ColorSpace.LCHab,
        ColorSpace.LCHuv,
        ColorSpace.Lpt,
        ColorSpace.LuvPrime,
        ColorSpace.Luv,
        ColorSpace.RGB,
        ColorSpace.xyY,
    ],
)
def test_it_is_an_enum(colorspace):
    """ColorSpace is an Enum."""
    assert isinstance(colorspace, Enum)


@pytest.mark.parametrize(
    "colorspace,expected_value",
    [
        [ColorSpace.DIN99, "DIN99"],
        [ColorSpace.DIN99b, "DIN99b"],
        [ColorSpace.DIN99c, "DIN99c"],
        [ColorSpace.DIN99d, "DIN99d"],
        [ColorSpace.HSI, "HSI"],
        [ColorSpace.HSL, "HSL"],
        [ColorSpace.HSV, "HSV"],
        [ColorSpace.ICtCp, "ICtCp"],
        [ColorSpace.IPT, "IPT"],
        [ColorSpace.Lab, "Lab"],
        [ColorSpace.LCHab, "LCH(ab)"],
        [ColorSpace.LCHuv, "LCH(uv)"],
        [ColorSpace.Lpt, "Lpt"],
        [ColorSpace.LuvPrime, "Lu'v'"],
        [ColorSpace.Luv, "Luv"],
        [ColorSpace.RGB, "RGB"],
        [ColorSpace.xyY, "xyY"],
    ],
)
def test_enum_values(colorspace, expected_value):
    """Test enum values."""
    assert colorspace.value == expected_value


@pytest.mark.parametrize(
    "colorspace,expected_value",
    [
        [ColorSpace.DIN99, "DIN99"],
        [ColorSpace.DIN99b, "DIN99b"],
        [ColorSpace.DIN99c, "DIN99c"],
        [ColorSpace.DIN99d, "DIN99d"],
        [ColorSpace.HSI, "HSI"],
        [ColorSpace.HSL, "HSL"],
        [ColorSpace.HSV, "HSV"],
        [ColorSpace.ICtCp, "ICtCp"],
        [ColorSpace.IPT, "IPT"],
        [ColorSpace.Lab, "Lab"],
        [ColorSpace.LCHab, "LCH(ab)"],
        [ColorSpace.LCHuv, "LCH(uv)"],
        [ColorSpace.LCHab, "LCHab"],
        [ColorSpace.LCHuv, "LCHuv"],
        [ColorSpace.Lpt, "Lpt"],
        [ColorSpace.LuvPrime, "Lu'v'"],
        [ColorSpace.LuvPrime, "LuvPrime"],
        [ColorSpace.Luv, "Luv"],
        [ColorSpace.RGB, "RGB"],
        [ColorSpace.xyY, "xyY"],
    ],
)
def test_str_comparison(colorspace, expected_value):
    """Test str comparison."""
    assert colorspace == expected_value


@pytest.mark.parametrize(
    "colorspace,expected_name",
    [
        [ColorSpace.DIN99, "DIN99"],
        [ColorSpace.DIN99b, "DIN99b"],
        [ColorSpace.DIN99c, "DIN99c"],
        [ColorSpace.DIN99d, "DIN99d"],
        [ColorSpace.HSI, "HSI"],
        [ColorSpace.HSL, "HSL"],
        [ColorSpace.HSV, "HSV"],
        [ColorSpace.ICtCp, "ICtCp"],
        [ColorSpace.IPT, "IPT"],
        [ColorSpace.Lab, "Lab"],
        [ColorSpace.LCHab, "LCHab"],
        [ColorSpace.LCHuv, "LCHuv"],
        [ColorSpace.Lpt, "Lpt"],
        [ColorSpace.LuvPrime, "LuvPrime"],
        [ColorSpace.Luv, "Luv"],
        [ColorSpace.RGB, "RGB"],
        [ColorSpace.xyY, "xyY"],
    ],
)
def test_enum_names(colorspace, expected_name):
    """Test enum names."""
    assert colorspace.name == expected_name


@pytest.mark.parametrize(
    "colorspace,expected_value",
    [
        [ColorSpace.DIN99, "DIN99"],
        [ColorSpace.DIN99b, "DIN99b"],
        [ColorSpace.DIN99c, "DIN99c"],
        [ColorSpace.DIN99d, "DIN99d"],
        [ColorSpace.HSI, "HSI"],
        [ColorSpace.HSL, "HSL"],
        [ColorSpace.HSV, "HSV"],
        [ColorSpace.ICtCp, "ICtCp"],
        [ColorSpace.IPT, "IPT"],
        [ColorSpace.Lab, "Lab"],
        [ColorSpace.LCHab, "LCH(ab)"],
        [ColorSpace.LCHuv, "LCH(uv)"],
        [ColorSpace.Lpt, "Lpt"],
        [ColorSpace.LuvPrime, "Lu'v'"],
        [ColorSpace.Luv, "Luv"],
        [ColorSpace.RGB, "RGB"],
        [ColorSpace.xyY, "xyY"],
    ],
)
def test_enum_as_str(colorspace, expected_value):
    """Test enum names."""
    assert str(colorspace) == expected_value


def test_to_colorspace_colorspace_is_skipped():
    """ColorSpace.to_colorspace() colorspace is skipped."""
    with pytest.raises(TypeError) as cm:
        _ = ColorSpace.to_colorspace()

    py_error_message = {
        9: "to_colorspace() missing 1 required positional argument: 'colorspace'",
        10: "ColorSpace.to_colorspace() missing 1 required positional argument: 'colorspace'",
        11: "ColorSpace.to_colorspace() missing 1 required positional argument: 'colorspace'",
        12: "ColorSpace.to_colorspace() missing 1 required positional argument: 'colorspace'",
        13: "ColorSpace.to_colorspace() missing 1 required positional argument: 'colorspace'",
    }[sys.version_info.minor]
    assert str(cm.value) == py_error_message


def test_to_colorspace_colorspace_is_none():
    """ColorSpace.to_colorspace() colorspace is None."""
    with pytest.raises(TypeError) as cm:
        _ = ColorSpace.to_colorspace(None)
    assert str(cm.value) == (
        "colorspace should be a ColorSpace enum value or one of ['DIN99', "
        "'DIN99b', 'DIN99c', 'DIN99d', 'HSI', 'HSL', 'HSV', 'ICtCp', 'IPT', "
        "'LCH(ab)', 'LCH(uv)', 'LCHab', 'LCHuv', 'Lab', 'Lpt', \"Lu'v'\", "
        "'Luv', 'LuvPrime', 'RGB', 'xyY'], not NoneType: 'None'"
    )


def test_to_colorspace_colorspace_is_not_a_str():
    """ColorSpace.to_colorspace() colorspace is not a str."""
    with pytest.raises(TypeError) as cm:
        _ = ColorSpace.to_colorspace(12334.123)

    assert str(cm.value) == (
        "colorspace should be a ColorSpace enum value or one of ['DIN99', "
        "'DIN99b', 'DIN99c', 'DIN99d', 'HSI', 'HSL', 'HSV', 'ICtCp', 'IPT', "
        "'LCH(ab)', 'LCH(uv)', 'LCHab', 'LCHuv', 'Lab', 'Lpt', \"Lu'v'\", "
        "'Luv', 'LuvPrime', 'RGB', 'xyY'], not float: '12334.123'"
    )


def test_to_colorspace_colorspace_is_not_a_valid_str():
    """ColorSpace.to_colorspace() colorspace is not a valid str."""
    with pytest.raises(ValueError) as cm:
        _ = ColorSpace.to_colorspace("not a valid value")

    assert str(cm.value) == (
        "colorspace should be a ColorSpace enum value or one of ['DIN99', "
        "'DIN99b', 'DIN99c', 'DIN99d', 'HSI', 'HSL', 'HSV', 'ICtCp', 'IPT', "
        "'LCH(ab)', 'LCH(uv)', 'LCHab', 'LCHuv', 'Lab', 'Lpt', \"Lu'v'\", "
        "'Luv', 'LuvPrime', 'RGB', 'xyY'], not 'not a valid value'"
    )


@pytest.mark.parametrize(
    "colorspace_name,colorspace",
    [
        # DIN99
        ["DIN99", ColorSpace.DIN99],
        ["din99", ColorSpace.DIN99],
        ["DiN99", ColorSpace.DIN99],
        ["dIn99", ColorSpace.DIN99],
        # DIN99b
        ["DIN99b", ColorSpace.DIN99b],
        ["din99b", ColorSpace.DIN99b],
        ["DIN99B", ColorSpace.DIN99b],
        ["DiN99b", ColorSpace.DIN99b],
        ["dIn99B", ColorSpace.DIN99b],
        # DIN99c
        ["DIN99c", ColorSpace.DIN99c],
        ["din99c", ColorSpace.DIN99c],
        ["DIN99C", ColorSpace.DIN99c],
        ["DiN99c", ColorSpace.DIN99c],
        ["dIn99C", ColorSpace.DIN99c],
        # DIN99d
        ["DIN99d", ColorSpace.DIN99d],
        ["din99d", ColorSpace.DIN99d],
        ["DIN99D", ColorSpace.DIN99d],
        ["DIN99d", ColorSpace.DIN99d],
        ["dIN99d", ColorSpace.DIN99d],
        # HSI
        ["HSI", ColorSpace.HSI],
        ["hsi", ColorSpace.HSI],
        ["HsI", ColorSpace.HSI],
        ["hSi", ColorSpace.HSI],
        # HSL
        ["HSL", ColorSpace.HSL],
        ["hsl", ColorSpace.HSL],
        ["HsL", ColorSpace.HSL],
        ["hSl", ColorSpace.HSL],
        # HSV
        ["HSV", ColorSpace.HSV],
        ["hsv", ColorSpace.HSV],
        ["HsV", ColorSpace.HSV],
        ["hSv", ColorSpace.HSV],
        # ICtCp
        ["ICtCp", ColorSpace.ICtCp],
        ["ictcp", ColorSpace.ICtCp],
        ["ICtCP", ColorSpace.ICtCp],
        ["IcTcp", ColorSpace.ICtCp],
        ["iCtCp", ColorSpace.ICtCp],
        # IPT
        ["IPT", ColorSpace.IPT],
        ["ipt", ColorSpace.IPT],
        ["IpT", ColorSpace.IPT],
        ["iPt", ColorSpace.IPT],
        # Lab
        ["Lab", ColorSpace.Lab],
        ["lab", ColorSpace.Lab],
        ["LaB", ColorSpace.Lab],
        ["lAB", ColorSpace.Lab],
        # LCHab
        ["LCHab", ColorSpace.LCHab],
        ["lchab", ColorSpace.LCHab],
        ["Lchab", ColorSpace.LCHab],
        ["lChAb", ColorSpace.LCHab],
        ["LCH(ab)", ColorSpace.LCHab],
        ["lch(ab)", ColorSpace.LCHab],
        ["Lch(ab)", ColorSpace.LCHab],
        ["lCh(Ab)", ColorSpace.LCHab],
        # LCHuv
        ["LCHuv", ColorSpace.LCHuv],
        ["lchuv", ColorSpace.LCHuv],
        ["Lchuv", ColorSpace.LCHuv],
        ["lChUv", ColorSpace.LCHuv],
        ["LCH(uv)", ColorSpace.LCHuv],
        ["lch(uv)", ColorSpace.LCHuv],
        ["Lch(uv)", ColorSpace.LCHuv],
        ["lCh(Uv)", ColorSpace.LCHuv],
        # Lpt
        ["Lpt", ColorSpace.Lpt],
        ["lpt", ColorSpace.Lpt],
        ["LpT", ColorSpace.Lpt],
        ["lPt", ColorSpace.Lpt],
        # LuvPrime
        ["LuvPrime", ColorSpace.LuvPrime],
        ["luvprime", ColorSpace.LuvPrime],
        ["LuvPrime", ColorSpace.LuvPrime],
        ["lUvPrime", ColorSpace.LuvPrime],
        ["Lu'v'", ColorSpace.LuvPrime],
        ["lu'v'", ColorSpace.LuvPrime],
        ["Lu'V'", ColorSpace.LuvPrime],
        ["lU'v'", ColorSpace.LuvPrime],
        # Luv
        ["Luv", ColorSpace.Luv],
        ["luv", ColorSpace.Luv],
        ["LuV", ColorSpace.Luv],
        ["lUv", ColorSpace.Luv],
        # RGB
        ["RGB", ColorSpace.RGB],
        ["rgb", ColorSpace.RGB],
        ["RgB", ColorSpace.RGB],
        ["rGb", ColorSpace.RGB],
        # xyY
        ["xyY", ColorSpace.xyY],
        ["xyy", ColorSpace.xyY],
        ["XyY", ColorSpace.xyY],
        ["xYy", ColorSpace.xyY],
    ],
)
def test_schedule_colorspace_to_colorspace_is_working_properly(colorspace_name, colorspace):
    """ColorSpace can parse schedule colorspace names."""
    assert ColorSpace.to_colorspace(colorspace_name) == colorspace
