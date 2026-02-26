from enum import IntEnum
import sys

import pytest

from DisplayCAL.config import BitmapSizeType

@pytest.mark.parametrize(
    "type_",
    [
        BitmapSizeType.HighDPI_Normal,
        BitmapSizeType.HighDPI_4x,
        BitmapSizeType.HighDPI_2x,
        BitmapSizeType.HighDPI_2x_Original,
        BitmapSizeType.Original,
    ],
)
def test_it_is_an_int_enum(type_):
    """BitmapSizeType is an IntEnum."""
    assert isinstance(type_, IntEnum)


@pytest.mark.parametrize(
    "type_,expected_value",
    [
        [BitmapSizeType.HighDPI_Normal, 0],
        [BitmapSizeType.HighDPI_4x, 1],
        [BitmapSizeType.HighDPI_2x, 2],
        [BitmapSizeType.HighDPI_2x_Original, 3],
        [BitmapSizeType.Original, 4],
    ],
)
def test_enum_values(type_, expected_value):
    """Test enum values."""
    assert type_ == expected_value


@pytest.mark.parametrize(
    "type_,expected_value",
    [
        [BitmapSizeType.HighDPI_Normal, "HighDPI_Normal"],
        [BitmapSizeType.HighDPI_4x, "HighDPI_4x"],
        [BitmapSizeType.HighDPI_2x, "HighDPI_2x"],
        [BitmapSizeType.HighDPI_2x_Original, "HighDPI_2x_Original"],
        [BitmapSizeType.Original, "Original"],
    ],
)
def test_enum_names(type_, expected_value):
    """Test enum names."""
    assert str(type_) == expected_value


def test_to_type_type_is_skipped():
    """BitmapSizeType.to_type() type_ is skipped."""
    with pytest.raises(TypeError) as cm:
        _ = BitmapSizeType.to_type()

    py_error_message = {
        8: "to_type() missing 1 required positional argument: 'type_'",
        9: "to_type() missing 1 required positional argument: 'type_'",
    }.get(sys.version_info.minor,
        "BitmapSizeType.to_type() missing 1 required positional argument: 'type_'"
    )
    assert str(cm.value) == py_error_message


def test_to_type_type_is_none():
    """BitmapSizeType.to_type() type_ is None."""
    with pytest.raises(TypeError) as cm:
        _ = BitmapSizeType.to_type(None)
    assert str(cm.value) == (
        "type_ should be a BitmapSizeType enum value or one "
        "of ['HighDPI_Normal', 'HighDPI_4x', 'HighDPI_2x', "
        "'HighDPI_2x_Original', 'Original', 0, 1, 2, 3, 4], "
        "not NoneType: 'None'"
    )


def test_to_type_type_is_not_a_str():
    """BitmapSizeType.to_type() type_ is not an int or str."""
    with pytest.raises(TypeError) as cm:
        _ = BitmapSizeType.to_type(12334.123)

    assert str(cm.value) == (
        "type_ should be a BitmapSizeType enum value or one of "
        "['HighDPI_Normal', 'HighDPI_4x', 'HighDPI_2x', "
        "'HighDPI_2x_Original', 'Original', 0, 1, 2, 3, 4], "
        "not float: '12334.123'"
    )


def test_to_type_type_is_not_a_valid_str():
    """BitmapSizeType.to_type() type_ is not a valid str."""
    with pytest.raises(ValueError) as cm:
        _ = BitmapSizeType.to_type("not a valid value")

    assert str(cm.value) == (
        "type_ should be a BitmapSizeType enum value or one of "
        "['HighDPI_Normal', 'HighDPI_4x', 'HighDPI_2x', "
        "'HighDPI_2x_Original', 'Original', 0, 1, 2, 3, 4], "
        "not 'not a valid value'"
    )


@pytest.mark.parametrize(
    "type__name,type_",
    [
        # HighDPI_Normal
        ["HighDPI_Normal", BitmapSizeType.HighDPI_Normal],
        ["highdpi_normal", BitmapSizeType.HighDPI_Normal],
        ["HIGHDPI_NORMAL", BitmapSizeType.HighDPI_Normal],
        ["HiGhDpI_NoRmAl", BitmapSizeType.HighDPI_Normal],
        ["hIgHdPi_nOrMaL", BitmapSizeType.HighDPI_Normal],
        [0, BitmapSizeType.HighDPI_Normal],
        # HighDPI_4x
        ["HighDPI_4x", BitmapSizeType.HighDPI_4x],
        ["highdpi_4x", BitmapSizeType.HighDPI_4x],
        ["HIGHDPI_4X", BitmapSizeType.HighDPI_4x],
        ["HiGhDpI_4x", BitmapSizeType.HighDPI_4x],
        ["hIgHdPi_4X", BitmapSizeType.HighDPI_4x],
        [1, BitmapSizeType.HighDPI_4x],
        # HighDPI_2x
        ["HighDPI_2x", BitmapSizeType.HighDPI_2x],
        ["highdpi_2x", BitmapSizeType.HighDPI_2x],
        ["HIGHDPI_2X", BitmapSizeType.HighDPI_2x],
        ["HiGhDpI_2x", BitmapSizeType.HighDPI_2x],
        ["hIgHdPi_2X", BitmapSizeType.HighDPI_2x],
        [2, BitmapSizeType.HighDPI_2x],
        # HighDPI_2x_Original
        ["HighDPI_2x_Original", BitmapSizeType.HighDPI_2x_Original],
        ["highdpi_2x_original", BitmapSizeType.HighDPI_2x_Original],
        ["HIGHDPI_2X_ORIGINAL", BitmapSizeType.HighDPI_2x_Original],
        ["HiGhDpI_2x_Original", BitmapSizeType.HighDPI_2x_Original],
        ["hIgHdPi_2X_Original", BitmapSizeType.HighDPI_2x_Original],
        [3, BitmapSizeType.HighDPI_2x_Original],
        # Original
        ["Original", BitmapSizeType.Original],
        ["original", BitmapSizeType.Original],
        ["ORIGINAL", BitmapSizeType.Original],
        ["OrIgInAl", BitmapSizeType.Original],
        ["oRiGiNaL", BitmapSizeType.Original],
        [4, BitmapSizeType.Original],
    ],
)
def test_to_type_is_working_properly(type__name, type_):
    """BitmapSizeType can parse schedule type_ names."""
    assert BitmapSizeType.to_type(type__name) == type_


@pytest.mark.parametrize(
    "value1,value2",
    [
        [BitmapSizeType.HighDPI_Normal + 1, BitmapSizeType.HighDPI_4x],
        [BitmapSizeType.HighDPI_4x + 1, BitmapSizeType.HighDPI_2x],
        [BitmapSizeType.HighDPI_2x + 1, BitmapSizeType.HighDPI_2x_Original],
        [BitmapSizeType.HighDPI_2x_Original + 1, BitmapSizeType.Original],
        [BitmapSizeType.Original + 1, 5], # Beyond the enum range
    ],
)
def test_addition_with_integer_values(value1, value2):
    """BitmapSizeType can be added to integer values."""
    assert value1 == value2


@pytest.mark.parametrize(
    "value1,value2",
    [
        [BitmapSizeType.HighDPI_Normal - 1, -1],
        [BitmapSizeType.HighDPI_4x - 1, BitmapSizeType.HighDPI_Normal],
        [BitmapSizeType.HighDPI_2x - 1, BitmapSizeType.HighDPI_4x],
        [BitmapSizeType.HighDPI_2x_Original - 1, BitmapSizeType.HighDPI_2x],
        [BitmapSizeType.Original - 1, BitmapSizeType.HighDPI_2x_Original],
        [3 - BitmapSizeType.HighDPI_4x, 2],
        [3 - BitmapSizeType.HighDPI_2x, 1],
    ],
)
def test_subtraction_with_integer_values(value1, value2):
    """BitmapSizeType can be subtracted from integer values."""
    assert value1 == value2


@pytest.mark.parametrize(
    "value1,value2",
    [
        [BitmapSizeType.HighDPI_Normal * 2, 0],
        [BitmapSizeType.HighDPI_4x * 2, BitmapSizeType.HighDPI_2x],
        [BitmapSizeType.HighDPI_2x * 2, BitmapSizeType.Original],
        [BitmapSizeType.HighDPI_2x_Original * 2, BitmapSizeType.HighDPI_2x + 4],
        [BitmapSizeType.Original * 2, BitmapSizeType.HighDPI_Normal + 8],
    ],
)
def test_multiplication_with_integer_values(value1, value2):
    """BitmapSizeType can be multiplied by integer values."""
    assert value1 == value2
