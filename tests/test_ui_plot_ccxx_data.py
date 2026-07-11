"""Tests for the toolkit-neutral CCMX/CCSS plot data-prep backend.

Exercises ``DisplayCAL.ui.plot.ccxx_data.compute_ccxx_plot_data`` against a
minimal CCMX (matrix) fixture and the repo's bundled CCSS (spectral) fixture,
plus the small standalone helpers (``nicenum``, ``comparison_gamut_triangle``).
No Qt import is needed; this module is pure Python + Argyll (for the CCSS
``spec2cie`` conversion). See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``
(``CCXXPlot`` visualization).
"""

import os

import pytest

from DisplayCAL import config
from DisplayCAL.cgats import CGATS
from DisplayCAL.ui.plot.ccxx_data import (
    COMPARISON_GAMUTS,
    comparison_gamut_triangle,
    compute_ccxx_plot_data,
    nicenum,
)
from DisplayCAL.worker import Worker

#: A minimal, fully-parseable CCMX correction (identity-like 3x3 matrix).
CCMX_TEXT = (
    "CCMX\n\n"
    'DESCRIPTOR "Colorimeter Correction Matrix"\n'
    'ORIGINATOR "Argyll CCMX"\n'
    'CREATED "Thu Apr 19 13:24:37 2012"\n'
    'DISPLAY "Test LCD"\n'
    'REFERENCE "i1 Pro"\n'
    'REFERENCE_OBSERVER "1931_2"\n'
    'FIT_METHOD "xy"\n'
    'FIT_AVG_DE00 "0.1234"\n'
    'FIT_MAX_DE00 "0.5678"\n'
    'COLOR_REP "XYZ"\n\n'
    "NUMBER_OF_FIELDS 3\n"
    "BEGIN_DATA_FORMAT\n"
    "XYZ_X XYZ_Y XYZ_Z\n"
    "END_DATA_FORMAT\n\n"
    "NUMBER_OF_SETS 3\n"
    "BEGIN_DATA\n"
    "1.02 0.01 0.02\n"
    "0.01 0.99 0.03\n"
    "0.02 0.02 1.01\n"
    "END_DATA\n"
)

CCSS_PATH = os.path.join(
    os.path.dirname(__file__),
    "data",
    "icc",
    "Dell, DELL UP2516D (i1 Pro 2) 08.2020.ccss",
)


class TestNicenum:
    def test_rounds_to_nearest_nice_number(self):
        assert nicenum(4.2, do_round=True) == 5.0
        assert nicenum(0.0042, do_round=True) == pytest.approx(0.005)

    def test_rounds_up_when_not_rounding(self):
        assert nicenum(4.2, do_round=False) == 5.0
        assert nicenum(1.2, do_round=False) == 2.0


class TestComparisonGamutTriangle:
    def test_returns_closed_triangle_for_each_registered_gamut(self):
        for rgb_space, _dash in COMPARISON_GAMUTS:
            triangle = comparison_gamut_triangle(rgb_space)
            assert len(triangle) == 4
            assert triangle[0] == triangle[-1]


class TestComputeCcxxPlotDataCcmx:
    @pytest.fixture
    def cgats(self, tmp_path):
        path = tmp_path / "test.ccmx"
        path.write_text(CCMX_TEXT)
        return CGATS(str(path))

    def test_detects_ccmx(self, cgats):
        data = compute_ccxx_plot_data(cgats)
        assert data.is_ccss is False

    def test_title_uses_matrix_descriptor(self, cgats):
        data = compute_ccxx_plot_data(cgats)
        assert "Colorimeter Correction Matrix" in data.title

    def test_x_label_includes_matrix_reference_and_fit_stats(self, cgats):
        data = compute_ccxx_plot_data(cgats)
        assert "1.020000" in data.x_label
        assert "i1 Pro" in data.x_label
        assert "0.1234" in data.x_label
        assert "0.5678" in data.x_label

    def test_flower_plot_has_seven_positions_times_two_markers(self, cgats):
        data = compute_ccxx_plot_data(cgats)
        assert len(data.curves) == 14
        assert all(curve.marker == "s" for curve in data.curves)
        assert all(len(curve.points) == 1 for curve in data.curves)

    def test_all_flower_points_have_resolved_colors(self, cgats):
        data = compute_ccxx_plot_data(cgats)
        assert len(data.points) == 14
        for point in data.points:
            assert len(point.xyz) == 3
            assert all(0 <= c <= 255 for c in point.color)

    def test_axis_ranges_cover_flower_extents(self, cgats):
        data = compute_ccxx_plot_data(cgats)
        x0, x1 = data.axis_x
        y0, y1 = data.axis_y
        assert x0 <= 0 and x1 >= 100
        assert y0 <= 0 and y1 >= 100


class TestComputeCcxxPlotDataCcss:
    @pytest.fixture
    def cgats(self):
        # dry_run can leak True from an unrelated test sharing this xdist
        # worker process (pre-existing pollution, see
        # qt-test-suite-order-dependent-flakes); force it off so spec2cie
        # actually runs.
        config.setcfg("dry_run", 0)
        return CGATS(CCSS_PATH)

    def test_detects_ccss(self, cgats):
        data = compute_ccxx_plot_data(cgats, Worker())
        assert data.is_ccss is True

    def test_title_uses_spectral_descriptor(self, cgats):
        data = compute_ccxx_plot_data(cgats, Worker())
        # "spectral"'s translated form can be capitalized ("Spectral") once
        # some other test in the same xdist worker has called lang.init();
        # match case-insensitively rather than depending on init order.
        assert data.title.lower().startswith("spectral: ")
        assert "Dell, DELL UP2516D" in data.title

    def test_x_label_reports_reference_and_band_spacing(self, cgats):
        data = compute_ccxx_plot_data(cgats, Worker())
        assert "nm" in data.x_label

    def test_one_curve_per_patch(self, cgats):
        data = compute_ccxx_plot_data(cgats, Worker())
        # One spectral power-distribution curve per DATA row (patch), each
        # resampled to 1nm steps across the reported spectral range.
        assert len(data.curves) == len(data.points) > 0
        x_min, x_max = data.axis_x
        for curve in data.curves:
            assert curve.marker is None
            assert len(curve.points) > 1
            for x, _y in curve.points:
                assert x_min <= x <= x_max
