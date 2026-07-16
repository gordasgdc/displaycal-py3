"""Tests for the Qt untethered-measurement navigation window (issue #841).

Drives ``UntetheredWindow`` headless via the shared offscreen ``QApplication``
and checks that it builds the per-patch grid from a CGATS test chart, renders
the RGB patch / measured Lab swatches, requires two settled ``spotread``
readings before committing a patch (mirroring the wx ``UntetheredFrame``'s
delta-based confirmation), auto-advances through unmeasured patches, and
surfaces the keys to send to ``spotread`` on ``send_requested`` /
``abort_requested``.
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

from DisplayCAL.cgats import CGATS  # noqa: E402
from DisplayCAL.ui import untethered_window as uw  # noqa: E402

_TI1 = b"""CTI1

NUMBER_OF_FIELDS 6
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 2
BEGIN_DATA
1 0.000000 0.000000 0.000000 0 0 0
2 100.000000 100.000000 100.000000 0 0 0
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
    """A fresh untethered window."""
    win = uw.UntetheredWindow()
    yield win
    win.close()


@pytest.fixture
def cgats(tmp_path):
    """A minimal two-patch CGATS test chart (black, then white)."""
    path = tmp_path / "test.ti1"
    path.write_bytes(_TI1)
    return CGATS(str(path))


def _sent(window):
    """Collect the keys emitted on ``send_requested`` for a window."""
    keys = []
    window.send_requested.connect(keys.append)
    return keys


# --- construction / setup ---------------------------------------------------


def test_starts_with_no_rows_and_disabled_buttons(window):
    assert window.grid.rowCount() == 0
    assert window.measure_btn.isEnabled() is False
    assert window.finish_btn.isEnabled() is False


def test_reset_restores_auto_checkbox_from_config(window):
    setcfg("untethered.measure.auto", 0)
    window.reset()
    assert window.auto_cb.isChecked() is False
    setcfg("untethered.measure.auto", 1)
    window.reset()
    assert window.auto_cb.isChecked() is True


# --- grid population / rendering -------------------------------------------


def test_first_chunk_populates_grid_from_cgats(window, cgats):
    window.set_cgats(cgats)
    window.parse_txt("Connecting to the instrument\n")
    assert window.grid.rowCount() == 2
    assert window.grid.item(0, 0).text() == "0"  # R
    assert window.grid.item(1, 0).text() == "255"  # R of the white patch (100% -> 255)
    assert window.index == 0
    assert window.index_max == 1


def test_write_without_cgats_is_a_noop(window):
    # Chunks can arrive before Worker.set_terminal_cgats attaches the chart;
    # must not crash.
    window.write("Connecting to the instrument\n")
    assert window.grid.rowCount() == 0


def test_connecting_message_pulses_rgb_label(window, cgats):
    window.set_cgats(cgats)
    window.parse_txt("Connecting to the instrument\n")
    assert window.label_rgb.text() == lang.getstr("instrument.initializing")


def test_ready_for_reading_shows_rgb_patch_after_delay(window, cgats, qapp):
    setcfg("untethered.measure.manual.delay", 0)
    window.set_cgats(cgats)
    window.parse_txt("key to take a reading\n")
    from qtpy.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(50, loop.quit)
    loop.exec_()
    assert window.label_rgb.text() == "RGB 0 0 0"
    assert window.measure_btn.isEnabled() is True


# --- measurement / commit logic ---------------------------------------------


def test_manual_click_primes_measure_count_and_sends_space(window, cgats):
    window.set_cgats(cgats)
    window.parse_txt("key to take a reading\n")
    window._enable_buttons()
    keys = _sent(window)
    window._measure_btn_handler()
    assert window.is_measuring is True
    assert window.measure_count == 1
    from qtpy.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(300, loop.quit)
    loop.exec_()
    assert keys == [" "]


def test_single_close_reading_commits_after_manual_click(window, cgats):
    # A manual click pre-loads measure_count=1, so one settled reading
    # (delta far enough from the initial (-1,-1,-1) sentinel) commits it.
    window.set_cgats(cgats)
    window.parse_txt("key to take a reading\n")
    window._measure_btn_handler()
    window.parse_txt(
        "Result is XYZ: 0.000010 0.000010 0.000010, "
        "D50 Lab: 0.000000 0.000000 0.000000\n"
    )
    assert window.measured == [0]
    assert window.index == 1  # auto-advanced to the next patch


def test_auto_advance_requires_two_settled_readings(window, cgats):
    # Auto-triggered measurements (not primed by a manual click) need two
    # consecutive close-enough readings before committing.
    setcfg("untethered.measure.auto", 1)
    window.set_cgats(cgats)
    window.parse_txt("key to take a reading\n")
    window._measure_btn_handler()
    window.parse_txt(
        "Result is XYZ: 0.000010 0.000010 0.000010, "
        "D50 Lab: 0.000000 0.000000 0.000000\n"
    )
    window.parse_txt("key to take a reading\n")  # auto-triggers the 2nd patch
    window.parse_txt(
        "Result is XYZ: 95.0 100.0 105.0, D50 Lab: 100.0 0.0 0.0\n"
    )
    assert window.measured == [0]  # not yet committed: only one reading so far
    window.parse_txt(
        "Result is XYZ: 95.05 100.0 105.05, D50 Lab: 100.0 0.0 0.0\n"
    )
    assert window.measured == [0, 1]
    assert window.finished is True
    assert window.finish_btn.isEnabled() is True


def test_committed_patch_fills_lab_columns(window, cgats):
    window.set_cgats(cgats)
    window.parse_txt("key to take a reading\n")
    window._measure_btn_handler()
    window.parse_txt(
        "Result is XYZ: 0.000010 0.000010 0.000010, "
        "D50 Lab: 0.000000 0.000000 0.000000\n"
    )
    assert window.grid.item(0, 5).text() == "0.00"  # L*
    assert window.grid.item(0, 6).text() == "0.00"  # a*
    assert window.grid.item(0, 7).text() == "-0.00"  # b*


def test_white_patch_sets_luminance_keyword(window, cgats):
    window.set_cgats(cgats)
    window.parse_txt("key to take a reading\n")
    window._measure_btn_handler()
    window.parse_txt(
        "Result is XYZ: 0.000010 0.000010 0.000010, "
        "D50 Lab: 0.000000 0.000000 0.000000\n"
    )
    window.parse_txt("key to take a reading\n")
    window._measure_btn_handler()
    window.parse_txt("Result is XYZ: 95.0 100.0 105.0, D50 Lab: 100.0 0.0 0.0\n")
    assert cgats[0].queryv1("LUMINANCE_XYZ_CDM2") is not None


# --- navigation --------------------------------------------------------------


def test_next_and_back_buttons_navigate(window, cgats):
    window.set_cgats(cgats)
    window.parse_txt("Connecting to the instrument\n")  # populates the grid
    window._navigate_to(0)
    window._next_btn_handler()
    assert window.index == 1
    window._back_btn_handler()
    assert window.index == 0


def test_cell_click_navigates_when_not_measuring(window, cgats):
    window.set_cgats(cgats)
    window.parse_txt("Connecting to the instrument\n")
    window.is_measuring = False
    window._on_cell_clicked(1, 0)
    assert window.index == 1


def test_cell_click_ignored_while_measuring(window, cgats):
    window.set_cgats(cgats)
    window.parse_txt("Connecting to the instrument\n")
    window._navigate_to(0)
    window.is_measuring = True
    window._on_cell_clicked(1, 0)
    assert window.index == 0


# --- finish ------------------------------------------------------------------


def test_finish_writes_cti3_and_sends_q_twice(window, cgats, qapp):
    from qtpy.QtCore import QEventLoop, QTimer

    def pump(ms):
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec_()

    window.set_cgats(cgats)
    window.parse_txt("key to take a reading\n")
    window._measure_btn_handler()
    window.parse_txt(
        "Result is XYZ: 0.000010 0.000010 0.000010, "
        "D50 Lab: 0.000000 0.000000 0.000000\n"
    )
    # Let the manual click's delayed "measure" keystroke (see UntetheredWindow
    # ._measure) land before observing the finish button's own keystrokes.
    pump(300)
    keys = _sent(window)
    window._finish_btn_handler()
    assert window.finish_btn.isEnabled() is False
    assert cgats[0].type == b"CTI3"
    pump(700)
    assert keys == ["Q", "Q"]


# --- keyboard ----------------------------------------------------------------


def test_escape_key_emits_abort_requested(window):
    from qtpy.QtCore import Qt
    from qtpy.QtGui import QKeyEvent

    aborts = []
    window.abort_requested.connect(lambda: aborts.append(True))
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
    )
    window.keyPressEvent(event)
    assert aborts == [True]


def test_q_key_emits_abort_requested(window):
    from qtpy.QtCore import Qt
    from qtpy.QtGui import QKeyEvent

    aborts = []
    window.abort_requested.connect(lambda: aborts.append(True))
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Q, Qt.KeyboardModifier.NoModifier, "Q"
    )
    window.keyPressEvent(event)
    assert aborts == [True]


def test_close_emits_closing(window):
    closings = []
    window.closing.connect(lambda: closings.append(True))
    window.close()
    assert closings == [True]
