import pytest

from DisplayCAL.colormath import Matrix3x3


def test_matrix3x3_does_not_initialize_as_identity_matrix():
    """Matrix3x3 without any args will not be an identity matrix.

    TODO: This is for future.
    """
    assert Matrix3x3() != Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]])


@pytest.mark.parametrize(
    "matrix1, matrix2, expected",
    [
        # True cases
        [
            Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
            Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
            True,
        ],
        [
            Matrix3x3([[1, 2, 3], [4, 5, 6], [7, 8, 9]]),
            Matrix3x3([[1, 2, 3], [4, 5, 6], [7, 8, 9]]),
            True,
        ],
        [
            Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
            [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            True,
        ],
        [
            Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
            ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
            True,
        ],
        # False cases
        [
            Matrix3x3([[0, 0, 0], [0, 0, 0], [0, 0, 0]]),
            Matrix3x3([[1, 2, 3], [4, 5, 6], [7, 8, 9]]),
            False,
        ],
        [
            Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
            Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 2]]),
            False,
        ],
        [
            Matrix3x3([[0, 0, 0], [0, 0, 0], [0, 0, 0]]),
            [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
            False,
        ],
        [
            Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
            [[1, 0, 0], [0, 1, 0], [0, 0, 2]],
            False,
        ],
        [
            Matrix3x3([[0, 0, 0], [0, 0, 0], [0, 0, 0]]),
            ((1, 2, 3), (4, 5, 6), (7, 8, 9)),
            False,
        ],
        [
            Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
            ((1, 0, 0), (0, 1, 0), (0, 0, 2)),
            False,
        ],
        # Other types
        [Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]]), "not a matrix", False],
        [Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]]), None, False],
        [Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]]), 42, False],
    ],
)
def test_matrix3x3_equality(matrix1, matrix2, expected):
    """Matrix3x3 equality."""
    assert (matrix1 == matrix2) is expected


def test_matrix3x3_is_hashable():
    """Matrix3x3 is hashable."""
    assert hash(Matrix3x3([[1, 0, 0], [0, 1, 0], [0, 0, 1]]))
