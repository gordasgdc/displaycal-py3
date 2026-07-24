import math

import pytest

from DisplayCAL.colormath import (
    LSTAR_K,
    REC709_P,
    RGB2XYZ,
    SMPTE240M_P,
    SRGB_P,
    Matrix3x3,
    get_cat_matrix,
    get_standard_illuminant,
    linmin,
    smooth_avg,
    smooth_avg_old,
    special_pow,
)
from tests.data.display_data import DisplayData


def test_smooth_avg_1():
    """Testing if the smooth_avg function is working properly"""
    test_values = DisplayData.values_to_smooth
    expected_result = DisplayData.expected_smooth_values
    passes = 1
    window = None
    protect = None
    result = smooth_avg(test_values, passes, window, protect)
    assert result == pytest.approx(expected_result)


def test_smooth_avg_is_matching_old_implementation_1():
    """Testing if the ``smooth_avg`` function is matching ``smooth_avg_old``"""
    test_values = DisplayData.values_to_smooth
    expected_result = DisplayData.expected_smooth_values
    passes = 1
    window = None
    protect = None
    result_1 = smooth_avg_old(test_values, passes, window, protect)
    result_2 = smooth_avg(test_values, passes, window, protect)

    assert len(result_1) == len(test_values)
    assert len(result_2) == len(test_values)
    assert result_1 == pytest.approx(result_2)
    assert result_1 == pytest.approx(expected_result)
    assert result_2 == pytest.approx(expected_result)


def test_smooth_avg_is_matching_old_implementation_2():
    """Testing if the ``smooth_avg`` function is matching ``smooth_avg_old``"""
    test_values = DisplayData.values_to_smooth
    passes = 1
    window = tuple([1] * 5)
    window_size = len(window)
    half_window_size = int(window_size / 2)
    protect = None
    result_1 = smooth_avg_old(test_values, passes, window, protect)
    result_2 = smooth_avg(test_values, passes, window, protect)

    assert len(result_1) == len(test_values)
    assert len(result_2) == len(test_values)
    # unfortunately the first value after start and first value after end are not
    # matching, but the rest are perfectly matching
    assert result_1[half_window_size:-half_window_size] == pytest.approx(
        result_2[half_window_size:-half_window_size]
    )


def test_smooth_avg_is_matching_old_implementation_3():
    """Testing if the ``smooth_avg`` function is matching ``smooth_avg_old``"""
    test_values = DisplayData.values_to_smooth
    passes = 1
    window = tuple([1] * 7)
    window_size = len(window)
    half_window_size = int(window_size / 2)
    protect = None
    result_1 = smooth_avg_old(test_values, passes, window, protect)
    result_2 = smooth_avg(test_values, passes, window, protect)

    assert len(result_1) == len(test_values)
    assert len(result_2) == len(test_values)
    # unfortunately the first value after start and first value after end are not
    # matching, but the rest are perfectly matching
    assert result_1[half_window_size:-half_window_size] == pytest.approx(
        result_2[half_window_size:-half_window_size]
    )


def test_smooth_avg_protetced_values_1():
    """Testing ``smooth_avg`` ``protect`` is working as expected."""
    test_values = [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]
    passes = 1
    window = (1, 1, 1)
    protect = [7]
    result = smooth_avg(test_values, passes, window, protect)
    expected_result = [
        0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.3333333333333333,
        1,
        0.3333333333333333,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
    ]
    assert result == expected_result


def test_smooth_avg_protetced_values_2():
    """Testing ``smooth_avg`` ``protect`` is working as expected."""
    test_values = [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0]
    passes = 1
    window = (1, 1, 1)
    protect = [6, 7]
    result = smooth_avg(test_values, passes, window, protect)
    expected_result = [
        0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
        1,
        0.3333333333333333,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
    ]
    assert result == expected_result


@pytest.mark.parametrize(
    "test_value, expected",
    [
        [
            "Bradford",
            Matrix3x3(
                [
                    [0.89510, 0.26640, -0.16140],
                    [-0.75020, 1.71350, 0.03670],
                    [0.03890, -0.06850, 1.02960],
                ]
            ),
        ],
        [
            "CAT02",
            Matrix3x3(
                [
                    [0.7328, 0.4296, -0.1624],
                    [-0.7036, 1.6975, 0.0061],
                    [0.0030, 0.0136, 0.9834],
                ]
            ),
        ],
        [
            "CAT02BS",
            Matrix3x3(
                [
                    [0.7328, 0.4296, -0.1624],
                    [-0.7036, 1.6975, 0.0061],
                    [0.0000, 0.0000, 1.0000],
                ]
            ),
        ],
        [
            "CAT97s",
            Matrix3x3(
                [
                    [0.8562, 0.3372, -0.1934],
                    [-0.8360, 1.8327, 0.0033],
                    [0.0357, -0.0469, 1.0112],
                ]
            ),
        ],
        [
            "CMCCAT2000",
            Matrix3x3(
                [
                    [0.7982, 0.3389, -0.1371],
                    [-0.5918, 1.5512, 0.0406],
                    [0.0008, 0.0239, 0.9753],
                ]
            ),
        ],
        [
            "HPE E",
            Matrix3x3(
                [
                    [0.38971, 0.68898, -0.07868],
                    [-0.22981, 1.18340, 0.04641],
                    [0.00000, 0.00000, 1.00000],
                ]
            ),
        ],
        [
            "Sharp",
            Matrix3x3(
                [
                    [1.2694, -0.0988, -0.1706],
                    [-0.8364, 1.8006, 0.0357],
                    [0.0297, -0.0315, 1.0018],
                ]
            ),
        ],
        [
            "HPE D65",
            Matrix3x3(
                [
                    [0.40024, 0.70760, -0.08081],
                    [-0.22630, 1.16532, 0.04570],
                    [0.00000, 0.00000, 0.91822],
                ]
            ),
        ],
        ["XYZ scaling", Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]])],
        [
            "IPT",
            Matrix3x3(
                [
                    [0.4002, 0.7075, -0.0807],
                    [-0.2280, 1.1500, 0.0612],
                    [0.0000, 0.0000, 0.9184],
                ]
            ),
        ],
        [
            "CIE2012_2",
            Matrix3x3(
                [
                    [0.2052445519046028, 0.8334486497310412, -0.0386932016356441],
                    [-0.4972221301804286, 1.4034846060306130, 0.0937375241498157],
                    [0.0000000000000000, 0.0000000000000000, 1.0000000000000000],
                ]
            ),
        ],
        [
            "BS",
            Matrix3x3(
                [
                    [0.8752, 0.2787, -0.1539],
                    [-0.8904, 1.8709, 0.0195],
                    [-0.0061, 0.0162, 0.9899],
                ]
            ),
        ],
        [
            "BS-PC",
            Matrix3x3(
                [
                    [0.6489, 0.3915, -0.0404],
                    [-0.3775, 1.3055, 0.0720],
                    [-0.0271, 0.0888, 0.9383],
                ]
            ),
        ],
    ],
)
def test_get_cat_matrix_with_str_input(test_value, expected):
    """Testing get_cat_matrix with str input."""
    result = get_cat_matrix(test_value)
    assert result == expected


@pytest.mark.skip(
    reason="TODO: This test is moved from the module, properly implement it."
)
def test_from_module():
    for i in range(4):
        if i == 0:
            wp = "native"
        elif i == 1:
            wp = "D50"
            XYZ = get_standard_illuminant(wp)
        elif i == 2:
            wp = "D65"
            XYZ = get_standard_illuminant(wp)
        elif i == 3:
            XYZ = get_standard_illuminant("D65", ("ASTM E308-01",))
            wp = " ".join([str(v) for v in XYZ])
        print(
            f"RGB and corresponding XYZ (nominal range 0.0 - 1.0) with whitepoint {wp}"
        )
        for name in rgb_spaces:
            spc = rgb_spaces[name]
            if i == 0:
                XYZ = CIEDCCT2XYZ(spc[1])
            spc = spc[0], XYZ, spc[2], spc[3], spc[4]
            print(
                f"{name} 1.0, 1.0, 1.0 = XYZ",
                [str(round(v, 4)) for v in RGB2XYZ(1.0, 1.0, 1.0, spc)],
            )
            print(
                f"{name} 1.0, 0.0, 0.0 = XYZ",
                [str(round(v, 4)) for v in RGB2XYZ(1.0, 0.0, 0.0, spc)],
            )
            print(
                f"{name} 0.0, 1.0, 0.0 = XYZ",
                [str(round(v, 4)) for v in RGB2XYZ(0.0, 1.0, 0.0, spc)],
            )
            print(
                f"{name} 0.0, 0.0, 1.0 = XYZ",
                [str(round(v, 4)) for v in RGB2XYZ(0.0, 0.0, 1.0, spc)],
            )
        print("")


@pytest.mark.parametrize(
    "a, b, expected",
    [
        (2.0, 3.0, 8.0),  # simple power
        (-2.0, 3.0, -8.0),  # negative base, odd exponent
        (2.0, 0.5, math.sqrt(2.0)),  # square root
        (0.0, 2.0, 0.0),  # zero base
        (2.0, 1.0, 2.0),  # identity
    ],
)
def test_special_pow_basic_power(a, b, expected):
    assert special_pow(a, b) == pytest.approx(expected)


def test_special_pow_slope_limit_negative_input():
    """slope_limit should limit the result for negative input."""
    a = -0.5
    b = 2.0
    slope_limit = 0.1
    result = special_pow(a, b, slope_limit)
    assert result == pytest.approx(min(-math.pow(-a, b), a / slope_limit))


def test_special_pow_slope_limit_positive_input():
    """slope_limit should limit the result for positive input."""
    a = 0.05
    b = 2.0
    slope_limit = 0.5
    result = special_pow(a, b, slope_limit)
    assert result == pytest.approx(max(math.pow(a, b), a / slope_limit))


@pytest.mark.parametrize(
    "a, b, expected",
    [
        # sRGB forward (XYZ -> RGB, sRGB TRC)
        (0.002, 1.0 / -2.4, 0.002 * SRGB_P),
        (0.1, 1.0 / -2.4, 1.055 * math.pow(0.1, 1.0 / 2.4) - 0.055),
        # sRGB reverse (RGB -> XYZ, sRGB TRC)
        (0.002, -2.4, 0.002 / SRGB_P),
        (0.1, -2.4, math.pow((0.1 + 0.055) / 1.055, 2.4)),
        # L* forward (XYZ -> RGB, L* TRC)
        (0.005, 1.0 / -3.0, 0.01 * 0.005 * LSTAR_K),
        (0.1, 1.0 / -3.0, 1.16 * math.pow(0.1, 1.0 / 3.0) - 0.16),
        # L* reverse (RGB -> XYZ, L* TRC)
        (0.05, -3.0, 100.0 * 0.05 / LSTAR_K),
        (0.2, -3.0, math.pow((0.2 + 0.16) / 1.16, 3.0)),
        # Rec. 709 forward (XYZ -> RGB, Rec. 709 TRC)
        (0.01, 1.0 / -709, 0.01 * REC709_P),
        (0.2, 1.0 / -709, 1.099 * math.pow(0.2, 0.45) - 0.099),
        # Rec. 709 reverse (RGB -> XYZ, Rec. 709 TRC)
        (0.01, -709, 0.01 / REC709_P),
        (0.2, -709, math.pow((0.2 + 0.099) / 1.099, 1.0 / 0.45)),
        # SMPTE 240M forward (XYZ -> RGB, SMPTE 240M TRC)
        (0.01, 1.0 / -240, 0.01 * SMPTE240M_P),
        (0.2, 1.0 / -240, 1.1115 * math.pow(0.2, 0.45) - 0.1115),
        # SMPTE 240M reverse (RGB -> XYZ, SMPTE 240M TRC)
        (0.01, -240, 0.01 / SMPTE240M_P),
        (0.2, -240, math.pow((0.1115 + 0.2) / 1.1115, 1.0 / 0.45)),
    ],
)
def test_special_pow_transfer_functions(a, b, expected):
    assert special_pow(a, b) == pytest.approx(expected)


def test_special_pow_invalid_gamma():
    with pytest.raises(ValueError):
        special_pow(1.0, -9999)


def quadratic_func(fdata, xt):
    # Simple quadratic: f(x) = (x-3)^2, minimum at x=3
    # xt is a dict or list, use first dimension
    x = xt[0] if isinstance(xt, (list, tuple)) else xt.get(0, 0)
    return (x - 3.0) ** 2


def linear_func(fdata, xt):
    # Linear function: f(x) = 2x + 1, minimum at -infinity
    x = xt[0] if isinstance(xt, (list, tuple)) else xt.get(0, 0)
    return 2 * x + 1


def multi_dim_quadratic(fdata, xt):
    # 2D quadratic: f(x, y) = (x-2)^2 + (y+1)^2, minimum at (2, -1)
    x = xt[0] if isinstance(xt, (list, tuple)) else xt.get(0, 0)
    y = xt[1] if isinstance(xt, (list, tuple)) else xt.get(1, 0)
    return (x - 2.0) ** 2 + (y + 1.0) ** 2


def test_linmin_quadratic_minimization():
    cp = [0.0]
    xi = [1.0]
    di = 1
    ftol = 1e-6
    fdata = None
    result = linmin(cp, xi, di, ftol, quadratic_func, fdata)
    # Minimum should be at x=3, so cp[0] should be close to 3, result close to 0
    assert cp[0] == pytest.approx(3.0, abs=1e-3)
    assert result == pytest.approx(0.0, abs=1e-6)


def test_linmin_linear_function():
    cp = [0.0]
    xi = [1.0]
    di = 1
    ftol = 1e-6
    fdata = None
    result = linmin(cp, xi, di, ftol, linear_func, fdata)
    # For a linear function, linmin should move cp in the negative direction
    # as much as possible, but since the bracket is limited, it should not diverge
    # Just check that the result is less than the starting value
    assert result < linear_func(None, {0: 0.0})


def test_linmin_multidimensional_quadratic():
    cp = [0.0, 0.0]
    xi = [1.0, 1.0]
    di = 2
    ftol = 1e-6
    fdata = None
    result = linmin(cp, xi, di, ftol, multi_dim_quadratic, fdata)
    # The minimum along the direction [1,1] from [0,0] is at t where
    # (t-2)^2 + (t+1)^2 is minimized, i.e., t = 0.5
    # So cp should be [0.5, 0.5]
    assert cp[0] == pytest.approx(0.5, abs=1e-3)
    assert cp[1] == pytest.approx(0.5, abs=1e-3)
    # The function value at this point
    expected = multi_dim_quadratic(None, [0.5, 0.5])
    assert result == pytest.approx(expected, abs=1e-6)


def test_linmin_with_zero_direction():
    cp = [1.0]
    xi = [0.0]
    di = 1
    ftol = 1e-6
    fdata = None
    result = linmin(cp, xi, di, ftol, quadratic_func, fdata)
    # If direction is zero, cp should not change
    assert cp[0] == pytest.approx(1.0)
    # The result should be the function value at cp
    assert result == pytest.approx(quadratic_func(None, {0: 1.0}))


def test_linmin_handles_dict_xt():
    # linmin uses dict for xt if di <= 10, so test that path
    cp = [0.0]
    xi = [1.0]
    di = 1
    ftol = 1e-6
    fdata = None
    result = linmin(cp, xi, di, ftol, quadratic_func, fdata)
    assert cp[0] == pytest.approx(3.0, abs=1e-3)
    assert result == pytest.approx(0.0, abs=1e-6)
