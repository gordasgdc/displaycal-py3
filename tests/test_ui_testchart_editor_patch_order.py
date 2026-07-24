"""Tests for the Qt testchart editor's "change patch order" feature (issue #843).

The wx testchart editor (``wx_testchart_editor.tc_sort_handler``) offers 23
sort/reorder modes (gray/white/primary-to-top, hue-space sorts, and
checkerboard interleave patterns) via a combo box + Apply button. None of
this was wired up in the Qt port (``DisplayCAL.ui.tools.testchart_editor``) -
these tests exercise the ported ``tc_sort_handler`` directly against
``TestchartEditorWindow``.
"""

import os

import pytest

from DisplayCAL import config
from DisplayCAL import localization as lang

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL.cgats import (  # noqa: E402
    CGATS,
    sort_by_rec709_luma,
    sort_by_rgb,
    sort_by_rgb_sum,
    stable_sort_by_l,
)
from DisplayCAL.ui.tools import testchart_editor as te  # noqa: E402

# Red, mid-gray, blue and white patches (in that order) so gray/white/primary
# "to-top" sorts have something distinct to reorder.
_TI1 = b"""CTI1

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 4
BEGIN_DATA
1 100.000000 0.000000 0.000000 40 20 2
2 50.000000 50.000000 50.000000 20 20 20
3 0.000000 0.000000 100.000000 10 5 40
4 100.000000 100.000000 100.000000 95 100 108
END_DATA
"""


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _init():
    """Config + localization must be live for the localized read-outs."""
    config.initcfg()
    lang.init()
    yield


@pytest.fixture
def window(qapp):
    """A fresh testchart editor window."""
    win = te.TestchartEditorWindow()
    yield win
    win.close()


@pytest.fixture
def loaded(window, tmp_path):
    """The window with a 4-row chart (red/gray/blue/white) loaded into the grid."""
    path = tmp_path / "test.ti1"
    path.write_bytes(_TI1)
    window.ti1 = CGATS(str(path))
    window._populate_grid()
    window.tc_check()
    return window


def _rgb_rows(window):
    data = window.ti1.queryv1("DATA")
    return [(s.RGB_R, s.RGB_G, s.RGB_B) for s in data.values()]


def test_sort_controls_disabled_without_chart(window):
    assert window.change_patch_order_ctrl.isEnabled() is False
    assert window.change_patch_order_btn.isEnabled() is False


def test_sort_controls_enabled_with_loaded_chart(loaded):
    window = loaded
    assert window.change_patch_order_ctrl.isEnabled() is True
    assert window.change_patch_order_btn.isEnabled() is True


def test_sort_controls_disabled_again_after_clear(loaded):
    window = loaded
    window.tc_clear()
    assert window.change_patch_order_ctrl.isEnabled() is False
    assert window.change_patch_order_btn.isEnabled() is False


def test_sort_combo_has_23_modes(window):
    assert window.change_patch_order_ctrl.count() == 23


def test_sort_handler_is_a_noop_without_a_chart(window):
    # Just needs to not raise.
    window.change_patch_order_ctrl.setCurrentIndex(0)
    window.tc_sort_handler()
    assert window.ti1 is None


def test_sort_handler_gray_to_top_moves_gray_patch_first(loaded):
    window = loaded
    assert _rgb_rows(window)[0] == (100.0, 0.0, 0.0)  # red starts on top
    window.change_patch_order_ctrl.setCurrentIndex(0)  # gray to top
    window.tc_sort_handler()
    rows = _rgb_rows(window)
    assert rows[0][0] == rows[0][1] == rows[0][2]  # a neutral patch is now first
    assert window.ti1.modified is True
    assert window.grid.rowCount() == 4


def test_sort_handler_white_to_top_moves_white_patch_first(loaded):
    window = loaded
    window.change_patch_order_ctrl.setCurrentIndex(1)  # white to top
    window.tc_sort_handler()
    assert _rgb_rows(window)[0] == (100.0, 100.0, 100.0)


@pytest.mark.parametrize(
    "index,method_name",
    [
        (0, "sort_rgb_gray_to_top"),
        (1, "sort_rgb_white_to_top"),
        (8, "sort_by_hsi"),
        (9, "sort_by_hsl"),
        (10, "sort_by_hsv"),
        (11, "sort_by_l"),
        (12, "sort_by_rec709_luma"),
        (13, "sort_by_rgb"),
        (14, "sort_by_rgb_sum"),
        (15, "sort_by_bgr"),
    ],
    ids=[
        "gray_to_top",
        "white_to_top",
        "hsi",
        "hsl",
        "hsv",
        "l",
        "rec709_luma",
        "rgb",
        "rgb_sum",
        "bgr",
    ],
)
def test_sort_handler_dispatches_single_method(loaded, monkeypatch, index, method_name):
    window = loaded
    calls = []
    monkeypatch.setattr(
        CGATS, method_name, lambda self: calls.append(method_name) or True
    )
    window.change_patch_order_ctrl.setCurrentIndex(index)
    window.tc_sort_handler()
    assert calls == [method_name]


@pytest.mark.parametrize(
    "index,expected_kwargs",
    [
        (2, {"red": True}),
        (3, {"green": True}),
        (4, {"blue": True}),
        (5, {"green": True, "blue": True}),
        (6, {"red": True, "blue": True}),
        (7, {"red": True, "green": True}),
    ],
    ids=["red", "green", "blue", "cyan", "magenta", "yellow"],
)
def test_sort_handler_primary_to_top_dispatch(
    loaded, monkeypatch, index, expected_kwargs
):
    window = loaded
    calls = []
    monkeypatch.setattr(
        CGATS,
        "sort_rgb_to_top",
        lambda self, **kwargs: calls.append(kwargs) or True,
    )
    window.change_patch_order_ctrl.setCurrentIndex(index)
    window.tc_sort_handler()
    assert calls == [expected_kwargs]


def test_sort_handler_minimize_display_response_delay_chains_three_sorts(
    loaded, monkeypatch
):
    window = loaded
    calls = []
    for name in ("sort_by_bgr", "sort_rgb_gray_to_top", "sort_rgb_white_to_top"):
        monkeypatch.setattr(
            CGATS, name, lambda self, name=name: calls.append(name) or True
        )
    window.change_patch_order_ctrl.setCurrentIndex(16)
    window.tc_sort_handler()
    assert calls == ["sort_by_bgr", "sort_rgb_gray_to_top", "sort_rgb_white_to_top"]


@pytest.mark.parametrize(
    "index,expected_args,expected_kwargs",
    [
        (17, (None, None), {}),
        (18, (None, None), {"split_grays": True, "shift": True}),
        (19, (), {"sort1": stable_sort_by_l}),
        (20, (sort_by_rec709_luma,), {}),
        (21, (sort_by_rgb_sum,), {}),
        (22, (sort_by_rgb, None), {"split_grays": True, "shift": True}),
    ],
    ids=[
        "interleave",
        "shift_interleave",
        "maximize_lightness_difference",
        "maximize_rec709_luma_difference",
        "maximize_RGB_difference",
        "vary_RGB_difference",
    ],
)
def test_sort_handler_checkerboard_dispatch(
    loaded, monkeypatch, index, expected_args, expected_kwargs
):
    window = loaded
    calls = []
    monkeypatch.setattr(
        CGATS,
        "checkerboard",
        lambda self, *args, **kwargs: calls.append((args, kwargs)) or True,
    )
    window.change_patch_order_ctrl.setCurrentIndex(index)
    window.tc_sort_handler()
    assert calls == [(expected_args, expected_kwargs)]


def test_sort_handler_repopulates_grid_and_enables_save(loaded, monkeypatch):
    window = loaded
    window.ti1.filename = None  # save button gating needs an existing file path
    populate_calls = []
    monkeypatch.setattr(window, "_populate_grid", lambda: populate_calls.append(True))
    window.change_patch_order_ctrl.setCurrentIndex(0)
    window.tc_sort_handler()
    assert populate_calls == [True]
    assert window.ti1.modified is True
