"""Tests for the Qt progress dialog ``DisplayCAL.ui.progress_dialog`` (Stage 5).

These cover the toolkit-neutral time maths directly (no display) and drive the
dialog itself headless via the shared offscreen ``QApplication`` fixture. See
``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 5 -- worker execution layer).
"""

import os

import pytest

from DisplayCAL import config

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

# Skip the whole module cleanly if Qt is unavailable in the environment.
pytest.importorskip("qtpy")

from DisplayCAL.ui import progress_dialog as pd  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _init_config():
    """Initialise config (default values) before each test."""
    config.initcfg()
    yield


# --- pure time maths -------------------------------------------------------


def test_format_elapsed_formats_hms():
    assert pd.format_elapsed(0) == "00:00:00"
    assert pd.format_elapsed(61) == "00:01:01"
    assert pd.format_elapsed(3661) == "01:01:01"


def test_format_elapsed_clamps_negative():
    assert pd.format_elapsed(-5) == "00:00:00"


def test_estimate_remaining_linear_extrapolation():
    # 10 s for 25 of 100 units -> 30 s for the remaining 75.
    assert pd.estimate_remaining(10.0, 25.0, 100.0) == pytest.approx(30.0)


@pytest.mark.parametrize(
    "elapsed,progress,maximum",
    [
        (0.0, 25.0, 100.0),  # no elapsed time yet
        (10.0, 0.0, 100.0),  # no progress yet
        (10.0, 100.0, 100.0),  # already complete
        (10.0, 25.0, 0.0),  # no maximum
    ],
)
def test_estimate_remaining_returns_none_without_enough_info(
    elapsed, progress, maximum
):
    assert pd.estimate_remaining(elapsed, progress, maximum) is None


# --- dialog behaviour ------------------------------------------------------


def test_starts_indeterminate(qapp):
    dlg = pd.ProgressDialog()
    try:
        # Indeterminate gauges report a (0, 0) range.
        assert dlg._gauge.minimum() == 0
        assert dlg._gauge.maximum() == 0
        assert dlg.keep_going is True
        assert dlg.paused is False
    finally:
        dlg.deleteLater()


def test_set_progress_switches_to_determinate(qapp):
    dlg = pd.ProgressDialog(maximum=100)
    try:
        dlg.set_progress(40)
        assert dlg._gauge.maximum() == 100
        assert dlg._gauge.value() == 40
        # Clamped to the maximum.
        dlg.set_progress(999)
        assert dlg._gauge.value() == 100
    finally:
        dlg.deleteLater()


def test_pulse_returns_to_indeterminate(qapp):
    dlg = pd.ProgressDialog(maximum=100)
    try:
        dlg.set_progress(40)
        assert dlg._gauge.maximum() == 100
        dlg.pulse("measuring")
        assert dlg._gauge.maximum() == 0
        assert dlg._message.text() == "measuring"
    finally:
        dlg.deleteLater()


def test_cancel_button_emits_and_stops_keep_going(qapp):
    dlg = pd.ProgressDialog(cancelable=True)
    seen = []
    dlg.cancelled.connect(lambda: seen.append(True))
    try:
        dlg.cancel_button.click()
        assert seen == [True]
        assert dlg.keep_going is False
        assert dlg.cancel_button.isEnabled() is False
    finally:
        dlg.deleteLater()


def test_pause_button_toggles_and_emits(qapp):
    dlg = pd.ProgressDialog(pauseable=True)
    states = []
    dlg.pause_toggled.connect(states.append)
    try:
        assert dlg.pause_button.isVisible() is False  # not shown until exec
        dlg.pause_button.click()
        assert dlg.paused is True
        assert states == [True]
        dlg.pause_button.click()
        assert dlg.paused is False
        assert states == [True, False]
    finally:
        dlg.deleteLater()


def test_no_cancel_button_when_not_cancelable(qapp):
    dlg = pd.ProgressDialog(cancelable=False)
    try:
        assert dlg.cancel_button is None
    finally:
        dlg.deleteLater()


def test_mark_finished_completes_and_disables(qapp):
    dlg = pd.ProgressDialog(maximum=100, pauseable=True, cancelable=True)
    try:
        dlg.mark_finished("done")
        assert dlg._gauge.value() == 100
        assert dlg._message.text() == "done"
        assert dlg.pause_button.isEnabled() is False
        assert dlg.cancel_button.isEnabled() is False
    finally:
        dlg.deleteLater()


def test_reset_returns_to_indeterminate(qapp):
    dlg = pd.ProgressDialog(maximum=100)
    try:
        dlg.set_progress(50)
        dlg.reset()
        assert dlg._gauge.maximum() == 0
        assert dlg._message  # message untouched by reset
    finally:
        dlg.deleteLater()


def test_moveEvent_persists_position(qapp):
    dlg = pd.ProgressDialog()
    try:
        dlg.show()
        dlg.move(123, 45)
        qapp.processEvents()
        assert config.getcfg("position.progress.x", False) == 123
        assert config.getcfg("position.progress.y", False) == 45
    finally:
        dlg.close()
        dlg.deleteLater()


def test_no_remaining_label_when_disabled(qapp):
    dlg = pd.ProgressDialog(show_remaining_time=False)
    try:
        assert dlg._remaining_label is None
        # Updating times must not raise without a remaining label.
        dlg.set_progress(10)
        dlg._update_times()
    finally:
        dlg.deleteLater()
