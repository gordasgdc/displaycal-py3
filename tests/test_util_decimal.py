"""Tests for DisplayCAL.util_decimal module."""

# Standard library imports
import decimal


# Third-party Imports
import pytest

# Local Imports
from DisplayCAL.util_decimal import float2dec, stripzeros


@pytest.mark.parametrize(
    "input_value,expected",
    [
        (1.5, decimal.Decimal("1.5")),
        (1.9999999999, decimal.Decimal("2")),
        (1.0000000000, decimal.Decimal("1")),
        (5.0, decimal.Decimal("5")),
        (-3.5, decimal.Decimal("-3.5")),
        (-1.9999999999, decimal.Decimal("-1")),
        (1.123456789, decimal.Decimal("1.123456789")),
    ]
)
def test_float2dec(input_value, expected):
    """Test conversion of a simple float."""
    assert float2dec(input_value) == expected


@pytest.mark.parametrize(
    "input_value,digits,expected",
    [
        (1.999, 3, decimal.Decimal("2")),
        (1.000, 3, decimal.Decimal("1")),
        (1.99, 2, decimal.Decimal("2")),
    ]
)
def test_float2dec_with_custom_digits(input_value, digits, expected):
    """Test with custom digit precision."""
    assert float2dec(input_value, digits=digits) == expected


@pytest.mark.parametrize(
    "input_value,expected", [
        (1.0, decimal.Decimal("1")),
        (1.234567890, decimal.Decimal("1.23456789")),
        ("1.2000", decimal.Decimal("1.2")),
        ("1.234", decimal.Decimal("1.234")),
        (decimal.Decimal("1.5000"), decimal.Decimal("1.5")),
        (5.0, decimal.Decimal("5")),
        ("123", decimal.Decimal("123")),
        (-3.5000, decimal.Decimal("-3.5")),
        (0.0001, decimal.Decimal("0.0001")),
        (0.0, decimal.Decimal("0")),
        (42, decimal.Decimal("42")),
        ("1.23e-4", decimal.Decimal("0.000123")),

    ]
)
def test_stripzeros(input_value, expected):
    """Test stripping trailing zeros from float."""
    assert stripzeros(input_value) == expected


def test_stripzeros_invalid_string():
    """Test with invalid string that cannot be converted."""
    result = stripzeros("invalid")
    assert result == "invalid"