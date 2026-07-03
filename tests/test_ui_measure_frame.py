"""Tests for the toolkit-neutral geometry maths in ``DisplayCAL.ui.measure_frame``.

These cover the relative<->pixel conversions extracted from the wx
``MeasureFrame`` (``place_n_zoom`` / ``get_dimensions`` / ``get_default_size``).
They need no display or ``QApplication`` — the functions are pure and take the
display geometry as plain tuples (see ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``,
Stage 1).
"""

import pytest

from DisplayCAL.ui.measure_frame import (
    compute_dimensions,
    compute_frame_geometry,
    default_measureframe_size,
)

# A typical 1920x1080 display with a 40px-high panel/taskbar reserved.
DISPLAY = (0, 0, 1920, 1080)
CLIENT = (0, 0, 1920, 1040)
DEFAULT_SIZE = 300.0


def test_default_measureframe_size_uses_larger_axis():
    """The 100 mm patch uses the axis with the highest pixel density."""
    # 1920 / 510 mm ~= 3.76 px/mm is the denser axis here.
    result = default_measureframe_size((1920, 1080), (510.0, 287.0))
    assert result == round(100.0 * 1920 / 510.0)


def test_compute_frame_geometry_centered():
    """A centred unit-scale patch lands centred at the default pixel size."""
    side, pos, scale = compute_frame_geometry(
        0.5, 0.5, 1.0, DISPLAY, CLIENT, DEFAULT_SIZE, 120, 25
    )
    assert side == 300
    # (1920 - 300) * 0.5 = 810 ; (1080 - 300) * 0.5 - 25 titlebar = 365
    assert pos == (810, 365)
    assert scale == 1.0


def test_compute_frame_geometry_clamps_to_min_size():
    """A tiny scale is floored to the control-fitting minimum square."""
    side, _pos, _scale = compute_frame_geometry(
        0.5, 0.5, 0.1, DISPLAY, CLIENT, DEFAULT_SIZE, 150, 0
    )
    assert side == 150


def test_compute_frame_geometry_fullscreen_forces_scale_50():
    """A patch as large as the display reports Argyll's maximum scale of 50."""
    _side, _pos, scale = compute_frame_geometry(
        0.5, 0.5, 50.0, DISPLAY, CLIENT, DEFAULT_SIZE, 120, 25
    )
    assert scale == 50


def test_compute_frame_geometry_position_never_below_client_origin():
    """The top-left is clamped to the usable client origin."""
    client = (0, 50, 1920, 990)
    _side, pos, _scale = compute_frame_geometry(
        0.0, 0.0, 1.0, DISPLAY, client, DEFAULT_SIZE, 120, 25
    )
    assert pos[0] >= client[0]
    assert pos[1] >= client[1]


def test_compute_dimensions_roundtrips_center():
    """A centred pixel geometry maps back to ``0.5,0.5,scale``."""
    side, pos, _scale = compute_frame_geometry(
        0.5, 0.5, 1.0, DISPLAY, CLIENT, DEFAULT_SIZE, 120, 25
    )
    dims = compute_dimensions((side, side), pos, DISPLAY, CLIENT, DEFAULT_SIZE, 25)
    assert dims == "0.5,0.5,1.0"


@pytest.mark.parametrize("x,y,scale", [(0.5, 0.5, 1.0), (0.25, 0.75, 2.0), (0.0, 0.0, 1.5)])
def test_place_then_dimensions_roundtrip(x, y, scale):
    """Placing then reading back reproduces the original coordinates."""
    side, pos, saved_scale = compute_frame_geometry(
        x, y, scale, DISPLAY, CLIENT, DEFAULT_SIZE, 120, 25
    )
    dims = compute_dimensions((side, side), pos, DISPLAY, CLIENT, DEFAULT_SIZE, 25)
    got_x, got_y, got_scale = (float(v) for v in dims.split(","))
    assert got_x == pytest.approx(x, abs=1e-3)
    assert got_y == pytest.approx(y, abs=1e-3)
    assert got_scale == pytest.approx(saved_scale, abs=1e-3)


def test_compute_dimensions_detects_fullscreen():
    """A near-display-sized patch is reported as fullscreen (scale 50, centred)."""
    dims = compute_dimensions(
        (1920, 1040), (0, 0), DISPLAY, CLIENT, DEFAULT_SIZE, 25
    )
    assert dims == "0.5,0.5,50.0"
