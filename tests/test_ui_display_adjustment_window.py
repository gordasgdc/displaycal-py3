"""Tests for the Qt interactive-adjustment window ``display_adjustment_window``.

The toolkit-neutral parsing is covered by ``test_ui_display_adjustment``; these
drive the widget itself headless via the shared offscreen ``QApplication`` and
check that it builds the five pages, applies the mode-dependent page enabling,
renders parsed readings onto the right page, tracks the measuring / menu phase,
and surfaces the key strings to send to ``dispcal`` on ``send_requested``.
See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 5, sub-slice 5c-ii).
"""

import os

import pytest

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import setcfg

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL.ui import display_adjustment_window as daw  # noqa: E402

# Real dispcal samples, shared with test_ui_display_adjustment.
from tests.test_ui_display_adjustment import (  # noqa: E402
    BLACK_POINT_CONVERGED,
    CHECK_ALL,
    MENU,
    WHITE_POINT,
)


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _init():
    """Config + localization must be live for the localized read-out labels."""
    config.initcfg()
    lang.init()
    yield


@pytest.fixture
def window(qapp):
    """A fresh adjustment window (LCD mode by default)."""
    setcfg("measurement_mode", "l")
    win = daw.DisplayAdjustmentWindow()
    yield win
    win.close()


def _sent(window):
    """Collect the keys emitted on ``send_requested`` for a window."""
    keys = []
    window.send_requested.connect(keys.append)
    return keys


# --- construction ----------------------------------------------------------


def test_builds_five_pages(window):
    ctrltypes = [page.ctrltype for page in window.pages]
    assert ctrltypes == [
        "black_level",
        "rgb_gain",
        "luminance",
        "rgb_offset",
        "check_all",
    ]


def test_rgb_page_has_rgbl_gauges(window):
    rgb_page = window.pages[1]
    assert set(rgb_page.gauges) == {"R", "G", "B", "L"}
    assert set(rgb_page.labels) == {"rgb", "luminance"}


def test_check_all_page_has_four_labels_no_gauges(window):
    check = window.pages[4]
    assert check.gauges == {}
    assert set(check.labels) == {
        "luminance",
        "black_level",
        "white_point",
        "black_point",
    }


# --- mode-dependent setup --------------------------------------------------


def test_lcd_disables_black_pages_and_selects_white_point(window):
    assert window.disabled_pages == [0, 3]
    assert window.current_page().ctrltype == "rgb_gain"
    assert window._selector_buttons[0].isHidden()
    assert window._selector_buttons[3].isHidden()
    assert not window._selector_buttons[1].isHidden()


def test_crt_without_black_luminance_disables_page_0(qapp, monkeypatch):
    # ``calibration.black_luminance`` is clamped to a tiny positive float by
    # config, so simulate the "as measured" (falsy) case at the getcfg seam.
    real = daw.getcfg
    monkeypatch.setattr(
        daw,
        "getcfg",
        lambda name, *a, **k: (
            "c"
            if name == "measurement_mode"
            else 0
            if name == "calibration.black_luminance"
            else real(name, *a, **k)
        ),
    )
    win = daw.DisplayAdjustmentWindow()
    try:
        assert win.disabled_pages == [0]
        assert win.current_page().ctrltype == "rgb_gain"
    finally:
        win.close()


def test_crt_with_black_luminance_selects_page_0(qapp):
    setcfg("measurement_mode", "c")
    setcfg("calibration.black_luminance", 1.0)
    win = daw.DisplayAdjustmentWindow()
    try:
        assert win.disabled_pages == []
        assert win.current_page().ctrltype == "black_level"
    finally:
        win.close()


def test_calibration_button_label_tracks_trc(qapp):
    setcfg("measurement_mode", "l")
    setcfg("trc", "")
    setcfg("calibration.continue_next", 0)
    win = daw.DisplayAdjustmentWindow()
    try:
        assert win.calibration_btn.text() == lang.getstr("finish")
    finally:
        win.close()


# --- rendering -------------------------------------------------------------


def test_white_point_readings_update_rgb_page(window):
    # LCD default selects the white-point (rgb_gain) page.
    window.parse_output(WHITE_POINT)
    page = window.current_page()
    assert page.gauges["R"].value() == 55
    assert page.gauges["G"].value() == 40
    assert page.gauges["B"].value() == 55
    rgb_label, rgb_check = page.labels["rgb"]
    assert lang.getstr("current") in rgb_label.text()
    # DE 4.8 -> out of tolerance, no checkmark. ``isHidden`` reflects the
    # explicit shown/hidden flag without needing a shown ancestor.
    assert rgb_check.isHidden() is True


def test_converged_reading_shows_checkmark(window):
    window.set_selection(1)
    # Reuse the black-point-converged sample but on the rgb page context.
    window.current_page().context.ctrltype = "rgb_gain"
    window.parse_output(BLACK_POINT_CONVERGED)
    _label, check = window.current_page().labels["rgb"]
    assert check.isHidden() is False


def test_measuring_phase_sets_stop_button(window):
    window.parse_output(WHITE_POINT)  # contains "initial measurements"
    assert window.is_measuring is True
    assert window.adjustment_btn.text() == lang.getstr(
        "calibration.interactive_display_adjustment.stop"
    )


def test_menu_phase_enables_buttons_and_clears_measuring(window):
    window.parse_output(WHITE_POINT)  # -> measuring
    window.parse_output(MENU)  # -> back to menu
    assert window.is_measuring is False
    assert window.calibration_btn.isEnabled()
    assert window.adjustment_btn.isEnabled()


def test_check_all_renders_every_metric(qapp):
    setcfg("measurement_mode", "l")
    win = daw.DisplayAdjustmentWindow()
    try:
        win.set_selection(4)
        win.parse_output(CHECK_ALL)
        page = win.current_page()
        assert lang.getstr("current") in page.labels["luminance"][0].text()
        assert lang.getstr("current") in page.labels["black_point"][0].text()
    finally:
        win.close()


def test_reset_zeroes_gauges_and_hides_checkmarks(window):
    window.parse_output(WHITE_POINT)
    window.reset()
    page = window.current_page()
    assert page.gauges["R"].value() == 0
    assert all(check.isHidden() for _l, check in page.labels.values())


# --- worker-key actions ----------------------------------------------------


def test_start_sends_selected_page_key(window):
    keys = _sent(window)
    window.set_selection(1)  # rgb_gain -> argyll key "2"
    window.start_interactive_adjustment()
    assert keys == ["2"]


def test_start_while_measuring_aborts(window):
    keys = _sent(window)
    window.is_measuring = True
    window.start_interactive_adjustment()
    assert keys == [" "]


def test_continue_to_calibration_sends_7_with_trc(window):
    setcfg("trc", "2.2")
    keys = _sent(window)
    window.continue_to_calibration()
    assert keys == ["7"]


def test_continue_to_calibration_sends_8_without_trc(window):
    setcfg("trc", "")
    keys = _sent(window)
    window.continue_to_calibration()
    assert keys == ["8"]


def test_space_key_starts_adjustment(window):
    from qtpy.QtCore import Qt
    from qtpy.QtGui import QKeyEvent

    keys = _sent(window)
    window.set_selection(1)
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier, " ")
    window.keyPressEvent(event)
    assert keys == ["2"]


def test_digit_key_selects_page_and_starts(window):
    from qtpy.QtCore import Qt
    from qtpy.QtGui import QKeyEvent

    keys = _sent(window)
    # "3" -> page index 2 (luminance), not disabled in LCD mode.
    event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_3, Qt.KeyboardModifier.NoModifier, "3")
    window.keyPressEvent(event)
    assert window.current_page().ctrltype == "luminance"
    assert keys == ["3"]
