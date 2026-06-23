"""Gamut-view colorspace configurations.

Replaces the giant ``if/elif self.colorspace == ...`` ladder in
``wx_profile_info.GamutCanvas.DrawCanvas`` with a data-driven registry. Each
entry knows how to label its axes, its default 2D view range, and how to turn a
linear XYZ triplet into 2D coordinates for that colorspace. Outline curves (the
spectral locus / optimal-colour boundary) are produced separately so they can be
toggled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from DisplayCAL import colormath


@dataclass(frozen=True)
class GamutColorspace:
    """View configuration for one gamut projection.

    Attributes:
        label_x: X-axis label.
        label_y: Y-axis label.
        view: Default ``(min_x, min_y, max_x, max_y)`` range.
        step: Axis tick spacing.
        convert: ``f(X, Y, Z) -> (x, y)`` projecting linear XYZ to 2D.
    """

    label_x: str
    label_y: str
    view: tuple[float, float, float, float]
    step: float
    convert: Callable[[float, float, float], tuple[float, float]]


def _scaled(func: Callable, drop_first: bool = True) -> Callable:
    """Wrap a colormath XYZ->… function, scaling XYZ by 100 first.

    Many colormath conversions expect XYZ in the 0..100 range and return a
    leading lightness component we don't plot.

    Args:
        func: A ``colormath.XYZ2*`` callable.
        drop_first: Drop the leading (lightness) component of the result.

    Returns:
        ``f(X, Y, Z) -> (x, y)``.
    """

    def convert(x: float, y: float, z: float) -> tuple[float, float]:
        out = func(x * 100, y * 100, z * 100)
        return tuple(out[1:] if drop_first else out)[:2]

    return convert


#: Registry of supported gamut projections, keyed by colorspace name.
COLORSPACES: dict[str, GamutColorspace] = {
    "a*b*": GamutColorspace(
        "a*", "b*", (-150.0, -150.0, 150.0, 150.0), 50, _scaled(colormath.XYZ2Lab)
    ),
    "Lpt": GamutColorspace(
        "p", "t", (-150.0, -150.0, 150.0, 150.0), 50, _scaled(colormath.XYZ2Lpt)
    ),
    "xy": GamutColorspace(
        "x",
        "y",
        (-0.05, -0.05, 0.75, 0.85),
        0.1,
        lambda x, y, z: tuple(colormath.XYZ2xyY(x, y, z)[:2]),
    ),
    "u'v'": GamutColorspace(
        "u'",
        "v'",
        (-0.025, -0.025, 0.625, 0.6),
        0.1,
        lambda x, y, z: tuple(colormath.XYZ2Lu_v_(x, y, z)[1:]),
    ),
    "u*v*": GamutColorspace(
        "u*", "v*", (-150.0, -150.0, 150.0, 150.0), 50, _scaled(colormath.XYZ2Luv)
    ),
    "DIN99": GamutColorspace(
        "a99", "b99", (-50.0, -50.0, 50.0, 50.0), 25, _scaled(colormath.XYZ2DIN99)
    ),
    "DIN99b": GamutColorspace(
        "a99b", "b99b", (-65.0, -65.0, 65.0, 65.0), 25, _scaled(colormath.XYZ2DIN99b)
    ),
    "DIN99c": GamutColorspace(
        "a99c", "b99c", (-65.0, -65.0, 65.0, 65.0), 25, _scaled(colormath.XYZ2DIN99c)
    ),
    "DIN99d": GamutColorspace(
        "a99d", "b99d", (-65.0, -65.0, 65.0, 65.0), 25, _scaled(colormath.XYZ2DIN99d)
    ),
    "ICtCp": GamutColorspace(
        "Ct",
        "Cp",
        (-0.5, -0.4, 0.4, 0.5),
        0.1,
        lambda x, y, z: tuple(colormath.XYZ2ICtCp(x, y, z, clamp=False)[1:]),
    ),
    "IPT": GamutColorspace(
        "P",
        "T",
        (-1.0, -1.0, 1.0, 1.0),
        0.25,
        lambda x, y, z: tuple(colormath.XYZ2IPT(x, y, z)[1:]),
    ),
}


def outline_curves(colorspace: str) -> list[list[tuple[float, float]]]:
    """Return boundary polyline(s) for ``colorspace`` (empty if none).

    These are the spectral-locus / optimal-colour boundaries drawn behind the
    profile gamut. Mirrors the outline branches of the original ``DrawCanvas``.

    Args:
        colorspace: A key of :data:`COLORSPACES`.

    Returns:
        A list of point sequences; each is drawn as one connected curve.
    """
    cfg = COLORSPACES[colorspace]
    xy = colormath.cie1931_2_xy
    if colorspace == "xy":
        return [[*xy, xy[0]]]
    if colorspace == "u'v'":
        uv = [tuple(colormath.xyY2Lu_v_(x, y, 100)[1:]) for x, y in xy]
        return [[*uv, uv[0]]]
    if colorspace == "a*b*":
        return [[tuple(lab[1:]) for lab in colormath.OPTIMAL_COLORS_LAB]]
    if colorspace.startswith("DIN99"):
        return [
            [
                cfg.convert(*colormath.Lab2XYZ(L, a, b))
                for L, a, b in colormath.OPTIMAL_COLORS_LAB
            ]
        ]
    return []
