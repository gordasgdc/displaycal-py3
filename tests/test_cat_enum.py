from enum import Enum
import sys

import pytest

from DisplayCAL.colorspace_to_vrml import CAT

@pytest.mark.parametrize(
    "cat",
    [
        CAT.Bradford,
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
        [CAT.XYZ_Scaling, "XYZ Scaling"],
    ],
)
def test_enum_values(cat, expected_value):
    """Test enum values."""
    assert cat.value == expected_value


@pytest.mark.parametrize(
    "cat,expected_name",
    [
        [CAT.Bradford, "Bradford"],
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
        [CAT.XYZ_Scaling, "XYZ Scaling"],
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
        10: "CAT.to_cat() missing 1 required positional argument: 'cat'",
        11: "CAT.to_cat() missing 1 required positional argument: 'cat'",
        12: "CAT.to_cat() missing 1 required positional argument: 'cat'",
        13: "CAT.to_cat() missing 1 required positional argument: 'cat'",
    }[sys.version_info.minor]
    assert str(cm.value) == py_error_message


def test_to_cat_cat_is_none():
    """CAT.to_cat() cat is None."""
    with pytest.raises(TypeError) as cm:
        _ = CAT.to_cat(None)
    assert str(cm.value) == (
        "cat should be a CAT enum value or one of ['Bradford', 'XYZ Scaling', "
        "'XYZ_Scaling'], not NoneType: 'None'"
    )


def test_to_cat_cat_is_not_a_str():
    """CAT.to_cat() cat is not a str."""
    with pytest.raises(TypeError) as cm:
        _ = CAT.to_cat(12334.123)

    assert str(cm.value) == (
        "cat should be a CAT enum value or one of ['Bradford', 'XYZ Scaling', "
        "'XYZ_Scaling'], not float: '12334.123'"
    )


def test_to_cat_cat_is_not_a_valid_str():
    """CAT.to_cat() cat is not a valid str."""
    with pytest.raises(ValueError) as cm:
        _ = CAT.to_cat("not a valid value")

    assert str(cm.value) == (
        "cat should be a CAT enum value or one of ['Bradford', 'XYZ_Scaling', "
        "'Bradford', 'XYZ Scaling'], not 'not a valid value'"
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
        # XYZ Scaling
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
