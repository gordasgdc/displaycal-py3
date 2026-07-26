"""Tests for the Qt display-uniformity measurement grid window (issue #947).

Drives ``UniformityWindow`` headless via the shared offscreen ``QApplication``
and checks that it builds the ``rows x cols`` swatch grid, drives each swatch
through its 4 brightness-level readings (mirroring the wx
``DisplayUniformityFrame``), marks a finished swatch with a checkmark, restarts
the same swatch in "continuous" mode, and surfaces the keys to send to
``spotread`` / a full worker abort on ``send_requested`` / ``abort_requested``.
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

from DisplayCAL.ui import uniformity_window as uw  # noqa: E402


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
    """A fresh 2x2 uniformity grid window."""
    win = uw.UniformityWindow(rows=2, cols=2)
    yield win
    win.close()


def _sent(window):
    """Collect the keys emitted on ``send_requested`` for a window."""
    keys = []
    window.send_requested.connect(keys.append)
    return keys


def _spin(qapp, ms=250):
    """Pump the event loop for ``ms`` milliseconds (lets QTimer.singleShot fire)."""
    from qtpy.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec_()


# --- construction / setup ---------------------------------------------------


def test_construction_builds_grid_and_disables_buttons(window):
    assert window.rows == 2
    assert window.cols == 2
    assert len(window.buttons) == 4
    assert len(window.panels) == 4
    assert len(window.labels) == 4
    assert all(not button.isEnabled() for button in window.buttons)


def test_construction_defaults_to_config_rows_cols(qapp):
    setcfg("uniformity.rows", 3)
    setcfg("uniformity.cols", 7)
    win = uw.UniformityWindow()
    try:
        assert win.rows == 3
        assert win.cols == 7
    finally:
        win.close()


def test_reset_reenables_record_icon_and_clears_results(window):
    window._enable_buttons()
    window._start_measure(0)
    window.reset()
    assert window.results == {}
    assert window.is_measuring is False
    assert window.buttons[0].isVisible() is False  # not shown (window never shown)
    assert all(not button.isEnabled() for button in window.buttons)


# --- measurement flow --------------------------------------------------------


def test_start_measure_hides_clicked_button_and_sends_after_delay(window, qapp):
    window._enable_buttons()
    keys = _sent(window)
    window.buttons[0].click()
    assert window.index == 0
    assert window.is_measuring is True
    assert window.results == {0: []}
    assert window.buttons[0].isHidden() is True
    assert all(not b.isEnabled() for b in window.buttons)
    _spin(qapp)
    assert keys == [" "]


def test_parse_txt_accumulates_result_and_advances_brightness_levels(window, qapp):
    window._enable_buttons()
    window._start_measure(0)
    keys = _sent(window)
    window.parse_txt(
        "Result is XYZ: 95.000000 100.000000 105.000000, "
        "D50 Lab: 100.000000 0.000000 0.000000\n"
        "Closest Daylight temperature = 6500K (Delta E 1.0)"
    )
    # "Daylight" -> "CDT" (the wx code keys on the matched locus *name*'s
    # first letter, not the ``loci`` dict key it was looked up from).
    assert window.results[0] == [
        {"XYZ": [95.0, 100.0, 105.0], "CDT": 6500}
    ]
    window.parse_txt("key to take a reading\n")
    # Still mid-ramp (1 of 4 levels read): re-sends for the next level. The
    # first " " is _start_measure's own initial send; the second is the
    # advance triggered by this "key to take a reading" line.
    assert window.is_measuring is True
    _spin(qapp)
    assert keys == [" ", " "]


def test_swatch_finishes_after_four_brightness_levels(window, qapp, monkeypatch):
    # Skip the save-report prompt: not all 4 swatches are measured here.
    window._enable_buttons()
    window._start_measure(0)
    for _ in range(4):
        window.parse_txt("Result is XYZ: 50.000000 50.000000 50.000000, D50 Lab: 1 1 1")
        window.parse_txt("key to take a reading\n")
    assert len(window.results[0]) == 4
    assert window.is_measuring is False
    assert window.buttons[0].isEnabled() is True
    assert not window.buttons[0].icon().isNull()
    assert all(b.isEnabled() for b in window.buttons)


def test_all_swatches_finished_prompts_save_dialog(window, monkeypatch):
    from qtpy.QtWidgets import QFileDialog

    prompted = []
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: prompted.append(True) or ("", "")),
    )
    window._enable_buttons()
    for index in range(4):
        window._start_measure(index)
        for _ in range(4):
            window.parse_txt(
                "Result is XYZ: 50.000000 50.000000 50.000000, D50 Lab: 1 1 1"
            )
            window.parse_txt("key to take a reading\n")
    assert prompted == [True]


def test_continuous_mode_restarts_same_swatch(window):
    setcfg("uniformity.measure.continuous", 1)
    try:
        window._enable_buttons()
        window._start_measure(0)
        for _ in range(4):
            window.parse_txt(
                "Result is XYZ: 50.000000 50.000000 50.000000, D50 Lab: 1 1 1"
            )
            window.parse_txt("key to take a reading\n")
        # Restarted on the same swatch instead of stopping.
        assert window.index == 0
        assert window.is_measuring is True
        assert window.results[0] == []
    finally:
        setcfg("uniformity.measure.continuous", 0)


def test_spot_read_failed_suppresses_advance(window):
    window._enable_buttons()
    window._start_measure(0)
    window.parse_txt("Spot read failed\n")
    window.parse_txt("key to take a reading\n")
    # last_error is set, so the "key to take a reading" branch is skipped.
    assert window.results[0] == []
    assert window.is_measuring is True


# --- keyboard ----------------------------------------------------------------


def _key_event(key, text=""):
    from qtpy.QtCore import QEvent, Qt
    from qtpy.QtGui import QKeyEvent

    return QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, text)


def test_escape_key_emits_abort_requested(window, qapp):
    from qtpy.QtCore import Qt

    aborted = []
    window.abort_requested.connect(lambda: aborted.append(True))
    qapp.sendEvent(window, _key_event(Qt.Key.Key_Escape))
    assert aborted == [True]


def test_q_key_emits_abort_requested(window, qapp):
    from qtpy.QtCore import Qt

    aborted = []
    window.abort_requested.connect(lambda: aborted.append(True))
    qapp.sendEvent(window, _key_event(Qt.Key.Key_Q, "Q"))
    assert aborted == [True]


def test_any_key_triggers_measurement_of_focused_swatch(window, qapp):
    from qtpy.QtCore import Qt

    window._enable_buttons()
    window.index = 1
    qapp.sendEvent(window, _key_event(Qt.Key.Key_A, "a"))
    assert window.index == 1
    assert window.is_measuring is True
    assert window.results == {1: []}


def test_key_press_ignored_while_measuring(window, qapp):
    from qtpy.QtCore import Qt

    window._enable_buttons()
    window._start_measure(0)
    qapp.sendEvent(window, _key_event(Qt.Key.Key_A, "a"))
    # Buttons are disabled mid-measurement, so a bare keypress must not
    # restart a different swatch.
    assert window.index == 0


# --- focus tracking ------------------------------------------------------


def test_button_focus_updates_tracked_index(window):
    window._enable_buttons()
    window.buttons[2].setFocus()
    window._on_button_focus(2)
    assert window.index == 2


# --- geometry ------------------------------------------------------------


def test_target_screen_falls_back_to_primary_when_no_match(window, monkeypatch):
    monkeypatch.setattr(uw, "get_argyll_display_number", lambda geometry: None)
    from qtpy.QtGui import QGuiApplication

    screen = window._target_screen()
    assert screen is QGuiApplication.primaryScreen()


def test_place_records_target_geometry(window, monkeypatch):
    from qtpy.QtGui import QGuiApplication

    monkeypatch.setattr(
        uw, "get_argyll_display_number", lambda geometry: 0
    )
    window.place()
    screen = QGuiApplication.primaryScreen()
    geo = screen.geometry()
    assert window._geometry == (geo.x(), geo.y(), geo.width(), geo.height())
