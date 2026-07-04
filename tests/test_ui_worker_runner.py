"""Tests for the Qt worker execution layer ``DisplayCAL.ui.worker_runner``.

``parse_progress`` (extracted from ``Worker.progress_handler``) is a pure
function tested without a display. The ``_ProducerThread`` / ``ProgressAdapter``
/ ``WorkerRunController`` driver is exercised headless via the shared offscreen
``QApplication``, with a fake worker so no Argyll / hardware is needed. See
``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 5, sub-slices 5b-i / 5b-ii).
"""

import os
import time

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

from DisplayCAL.ui.worker_runner import parse_progress  # noqa: E402


def test_percent_download_progress():
    pct, lastmsg = parse_progress("", "42%")
    assert pct == 42
    assert lastmsg == "42%"


def test_percent_ignores_equals_calibration_check():
    # The '=' guard stops a calibration-check "1%" reading being treated as
    # command progress.
    pct, _ = parse_progress("", "1% = something")
    assert pct is None


def test_patch_of_progress():
    # Patch 26 of 100 -> (26 - 1) / 100 * 100 = 25.0
    pct, _ = parse_progress("", "Patch 26 of 100")
    assert pct == pytest.approx(25.0)


def test_patch_of_progress_first_patch_floors_at_zero():
    # Patch 1 of 50 -> max(1 - 1, 0) / 50 = 0.0
    pct, _ = parse_progress("", "Patch 1 of 50")
    assert pct == pytest.approx(0.0)


def test_added_targen_progress():
    # Added 30/120 -> 25%
    pct, _ = parse_progress("", "Added 30/120")
    assert pct == pytest.approx(25.0)


def test_iteration_targen_progress_clears_lastmsg():
    # It 5: ... -> min(5, 20) / 20 * 100 = 25%, and lastmsg is cleared.
    pct, lastmsg = parse_progress("It 5: refining", "some stale line")
    assert pct == pytest.approx(25.0)
    assert lastmsg == ""


def test_iteration_caps_at_twenty():
    pct, _ = parse_progress("It 40: refining", "")
    assert pct == pytest.approx(100.0)


def test_warnings_are_stripped_not_parsed():
    # A warning line must not be parsed as progress.
    pct, lastmsg = parse_progress("", "dispread: Warning - something 50%")
    assert pct is None
    assert "Warning" not in lastmsg


def test_no_match_returns_none():
    pct, lastmsg = parse_progress("just some text", "nothing numeric here")
    assert pct is None
    assert lastmsg == "nothing numeric here"


def test_percentage_is_clamped():
    pct, _ = parse_progress("", "150%")
    assert pct == 100


# --- driver / adapter / controller (headless Qt) ---------------------------

pytest.importorskip("qtpy")

from DisplayCAL.ui import progress_dialog as pd  # noqa: E402
from DisplayCAL.ui import worker_runner as wr  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


class _FakeBuffer:
    """Stand-in for a worker ``FilteredStream`` output buffer."""

    def __init__(self):
        self._text = ""

    def set(self, text):
        self._text = text

    def read(self, triggers=None):
        return self._text


class FakeWorker:
    """Minimal worker exposing what ``WorkerRunController`` touches."""

    def __init__(self):
        self.recent = _FakeBuffer()
        self.lastmsg = _FakeBuffer()
        self.progress_wnd = None
        self.abort_calls = []

    def abort_subprocess(self, confirm=False):
        self.abort_calls.append(confirm)


def _spin_until(qapp, predicate, timeout_s=3.0):
    """Pump the event loop until ``predicate`` is true or the timeout elapses."""
    deadline = time.time() + timeout_s
    while not predicate() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    return predicate()


def test_producer_thread_emits_result(qapp):
    thread = wr._ProducerThread(lambda: 42)
    results = []
    thread.finished_with_result.connect(results.append)
    thread.start()
    assert _spin_until(qapp, lambda: results)
    assert results == [42]
    thread.wait()


def test_producer_thread_emits_exception_as_result(qapp):
    boom = ValueError("boom")

    def producer():
        raise boom

    thread = wr._ProducerThread(producer)
    results = []
    thread.finished_with_result.connect(results.append)
    thread.start()
    assert _spin_until(qapp, lambda: results)
    assert results == [boom]
    thread.wait()


def test_adapter_pulse_returns_flags_and_updates_dialog(qapp):
    dlg = pd.ProgressDialog()
    adapter = wr.ProgressAdapter(dlg)
    try:
        # Same-thread emit delivers directly, so the dialog updates in place.
        keep_going, skip = adapter.Pulse("measuring")
        assert (keep_going, skip) == (True, False)
        assert dlg._message.text() == "measuring"
        # Cancelling flips the flag the worker thread reads.
        adapter.keepGoing = False
        assert adapter.Pulse()[0] is False
    finally:
        dlg.deleteLater()


def test_adapter_update_progress_sets_determinate_value(qapp):
    dlg = pd.ProgressDialog(maximum=100)
    adapter = wr.ProgressAdapter(dlg)
    try:
        adapter.UpdateProgress(60, "almost")
        assert dlg._gauge.value() == 60
        assert dlg._gauge.maximum() == 100
    finally:
        dlg.deleteLater()


def test_controller_poll_advances_dialog(qapp):
    dlg = pd.ProgressDialog(maximum=100)
    worker = FakeWorker()
    ctrl = wr.WorkerRunController(worker, dlg)
    try:
        worker.recent.set("")
        worker.lastmsg.set("Patch 26 of 100")
        ctrl._on_poll()
        assert dlg._gauge.value() == 25
    finally:
        dlg.deleteLater()


def test_controller_run_calls_consumer_and_cleans_up(qapp):
    dlg = pd.ProgressDialog()
    worker = FakeWorker()
    ctrl = wr.WorkerRunController(worker, dlg)
    got = []
    try:
        ctrl.run(lambda: True, got.append, progress_msg="Measuring")
        # The adapter is installed while running.
        assert worker.progress_wnd is not None
        assert _spin_until(qapp, lambda: got)
        assert got == [True]
        assert worker.progress_wnd is None
        assert dlg.isVisible() is False
        assert ctrl.is_running is False
    finally:
        dlg.deleteLater()


def test_controller_run_ignores_second_start_while_running(qapp):
    dlg = pd.ProgressDialog()
    worker = FakeWorker()
    ctrl = wr.WorkerRunController(worker, dlg)
    release = []
    calls = []

    def slow():
        calls.append(1)
        while not release:
            time.sleep(0.005)
        return True

    try:
        ctrl.run(slow)
        # Second call while running is a no-op.
        ctrl.run(lambda: calls.append(2))
        release.append(True)
        assert _spin_until(qapp, lambda: ctrl.is_running is False)
        assert calls == [1]
    finally:
        release.append(True)
        dlg.deleteLater()


def test_controller_cancel_aborts_worker(qapp):
    dlg = pd.ProgressDialog(cancelable=True)
    worker = FakeWorker()
    ctrl = wr.WorkerRunController(worker, dlg)
    try:
        # Simulate an in-flight run so the adapter is present.
        ctrl._adapter = wr.ProgressAdapter(dlg)
        dlg.cancel_button.click()
        assert ctrl._adapter.keepGoing is False
        assert worker.abort_calls == [False]
    finally:
        dlg.deleteLater()


def test_controller_pause_reflects_to_adapter(qapp):
    dlg = pd.ProgressDialog(pauseable=True)
    worker = FakeWorker()
    ctrl = wr.WorkerRunController(worker, dlg)
    try:
        ctrl._adapter = wr.ProgressAdapter(dlg)
        dlg.pause_button.click()
        assert ctrl._adapter.paused is True
    finally:
        dlg.deleteLater()


def test_adapter_confirm_same_thread_shows_directly(qapp):
    # Called on the GUI thread (unusual), confirm() shows directly, no blocking.
    dlg = pd.ProgressDialog()
    adapter = wr.ProgressAdapter(dlg)
    adapter._ask = lambda request: True
    try:
        assert adapter.confirm("hi", "OK", "Cancel") is True
    finally:
        dlg.deleteLater()


def test_adapter_confirm_blocks_worker_until_gui_answers(qapp):
    # A confirm requested from the worker thread is shown on the GUI thread and
    # blocks the worker until the GUI answers; the request carries the prompt.
    dlg = pd.ProgressDialog()
    adapter = wr.ProgressAdapter(dlg)
    seen = {}

    def fake_ask(request):
        seen["msg"] = request.msg
        seen["ok"] = request.ok
        seen["cancel"] = request.cancel
        seen["icon"] = request.icon
        return True

    adapter._ask = fake_ask
    results = []
    thread = wr._ProducerThread(
        lambda: adapter.confirm("place it", "OK", "Cancel", "dialog-warning")
    )
    thread.finished_with_result.connect(results.append)
    try:
        thread.start()
        assert _spin_until(qapp, lambda: results)
        assert results == [True]
        assert seen["msg"] == "place it"
        assert seen["ok"] == "OK"
        assert seen["cancel"] == "Cancel"
        assert seen["icon"] == "dialog-warning"
    finally:
        thread.wait()
        dlg.deleteLater()


def test_adapter_confirm_returns_false_on_cancel(qapp):
    dlg = pd.ProgressDialog()
    adapter = wr.ProgressAdapter(dlg)
    adapter._ask = lambda request: False
    results = []
    thread = wr._ProducerThread(lambda: adapter.confirm("x", "OK", "No"))
    thread.finished_with_result.connect(results.append)
    try:
        thread.start()
        assert _spin_until(qapp, lambda: results)
        assert results == [False]
    finally:
        thread.wait()
        dlg.deleteLater()
