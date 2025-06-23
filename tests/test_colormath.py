import pytest

from DisplayCAL.colormath import (
    CAT_MATRICES,
    get_cat_matrix,
    get_standard_illuminant,
    Matrix3x3,
    smooth_avg_old,
    smooth_avg,
    RGB2XYZ,
)
from tests.data.display_data import DisplayData


def test_smooth_avg_1():
    """testing if the smooth_avg function is working properly"""
    test_values = DisplayData.values_to_smooth
    expected_result = DisplayData.expected_smooth_values
    passes = 1
    window = None
    protect = None
    result = smooth_avg(test_values, passes, window, protect)
    assert result == pytest.approx(expected_result)


def test_smooth_avg_is_matching_old_implementation_1():
    """testing if the ``smooth_avg`` function is matching ``smooth_avg_old``"""
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
    """testing if the ``smooth_avg`` function is matching ``smooth_avg_old``"""
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
    """testing if the ``smooth_avg`` function is matching ``smooth_avg_old``"""
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
