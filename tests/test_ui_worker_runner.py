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

    def _init_run_state(self, **kwargs):
        # Stand-in for Worker._init_run_state: record what a real worker
        # would set so tests can assert on it, without pulling in the real
        # Worker's full per-run state reset.
        self.interactive_frame = kwargs.get("interactive_frame", "")
        self.pauseable = kwargs.get("pauseable", False)
        self.cancelable = kwargs.get("cancelable", True)
        self.paused = False
        self.subprocess_abort = False
        self.thread_abort = False
        self.abort_requested = False
        self.finished = False
        self.starttime = time.time()


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


# --- PasswordPromptAdapter (Worker.authenticate() elevated install) --------


def test_password_prompt_adapter_same_thread_shows_directly(qapp):
    # Called on the GUI thread (unusual), the dialog is shown directly.
    adapter = wr.PasswordPromptAdapter()
    adapter._ask = lambda request: "hunter2"
    assert adapter("Enter password:") == "hunter2"


def test_password_prompt_adapter_blocks_caller_until_gui_answers(qapp):
    # A password requested from a worker thread is shown on the GUI thread and
    # blocks the caller until the GUI answers; the request carries the message.
    adapter = wr.PasswordPromptAdapter()
    seen = {}

    def fake_ask(request):
        seen["msg"] = request.msg
        return "s3cr3t"

    adapter._ask = fake_ask
    results = []
    thread = wr._ProducerThread(lambda: adapter("Enter your password:"))
    thread.finished_with_result.connect(results.append)
    try:
        thread.start()
        assert _spin_until(qapp, lambda: results)
        assert results == ["s3cr3t"]
        assert seen["msg"] == "Enter your password:"
    finally:
        thread.wait()


def test_password_prompt_adapter_returns_none_on_cancel(qapp):
    adapter = wr.PasswordPromptAdapter()
    adapter._ask = lambda request: None
    results = []
    thread = wr._ProducerThread(lambda: adapter("x"))
    thread.finished_with_result.connect(results.append)
    try:
        thread.start()
        assert _spin_until(qapp, lambda: results)
        assert results == [None]
    finally:
        thread.wait()


def test_password_prompt_adapter_dialog_round_trip_accept(qapp):
    # Exercise the real _ask() dialog construction (no mocked _ask): type a
    # password and accept via the line edit's returnPressed -> accept().
    from qtpy.QtCore import QTimer
    from qtpy.QtWidgets import QApplication, QDialog, QLineEdit

    adapter = wr.PasswordPromptAdapter()

    def fill_and_accept():
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                line_edit = widget.findChild(QLineEdit)
                line_edit.setText("typed-pwd")
                line_edit.returnPressed.emit()
                return

    QTimer.singleShot(0, fill_and_accept)
    assert adapter("Enter password:") == "typed-pwd"


def test_password_prompt_adapter_dialog_round_trip_cancel(qapp):
    from qtpy.QtCore import QTimer
    from qtpy.QtWidgets import QApplication, QDialog

    adapter = wr.PasswordPromptAdapter()

    def reject_dialog():
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                widget.reject()
                return

    QTimer.singleShot(0, reject_dialog)
    assert adapter("Enter password:") is None


# --- interactive calibration driver (5c-iii) -------------------------------

from threading import Event  # noqa: E402

from qtpy.QtCore import QObject, Signal  # noqa: E402


class _FakeAdjustmentWindow(QObject):
    """Stand-in for the Qt ``DisplayAdjustmentWindow`` the driver marshals to."""

    send_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.parsed = []
        self.pulses = []
        self.title = ""
        self.reset_calls = 0
        self.shown = False
        self.is_measuring = False

    def parse_output(self, txt):
        self.parsed.append(txt)

    def pulse(self, msg=""):
        self.pulses.append(msg)

    def setWindowTitle(self, title):  # noqa: N802 - Qt name the terminal calls
        self.title = title

    def reset(self):
        self.reset_calls += 1

    def place(self):
        pass

    def show(self):
        self.shown = True

    def raise_(self):
        pass

    def hide(self):
        self.shown = False

    def isVisible(self):  # noqa: N802 - Qt name the terminal probes
        return self.shown

    def isActiveWindow(self):  # noqa: N802 - Qt name the terminal probes
        return False


class FakeCalibrateWorker:
    """Minimal worker exposing what ``AdjustmentController`` touches."""

    def __init__(self, result=True, block=None):
        self.sent = []
        self.terminal = None
        self.progress_wnd = None
        self.thread = None
        self._result = result
        self._block = block

    def calibrate(self, remove=True):
        # Emit a chunk so the terminal marshalling is exercised end to end.
        self.terminal.write("Patch 1 of 10")
        if self._block is not None:
            self._block.wait()
        return self._result

    def safe_send(self, data):
        self.sent.append(data)
        return True

    def log(self, *args, **kwargs):
        pass

    def _init_run_state(self, **kwargs):
        # Stand-in for Worker._init_run_state (see FakeWorker's copy).
        self.interactive_frame = kwargs.get("interactive_frame", "")
        self.pauseable = kwargs.get("pauseable", False)
        self.cancelable = kwargs.get("cancelable", True)
        self.paused = False
        self.subprocess_abort = False
        self.thread_abort = False
        self.abort_requested = False
        self.finished = False
        self.starttime = time.time()


def test_producer_thread_is_alive_reflects_running(qapp):
    block = Event()
    thread = wr._ProducerThread(block.wait)
    assert thread.is_alive() is False
    try:
        thread.start()
        assert _spin_until(qapp, thread.is_alive)
    finally:
        block.set()
        thread.wait()
    assert thread.is_alive() is False


def test_adjustment_terminal_write_marshals_to_window(qapp):
    window = _FakeAdjustmentWindow()
    terminal = wr._AdjustmentTerminal(window)
    # Same-thread emit delivers directly.
    terminal.write("hello")
    assert window.parsed == ["hello"]
    # Empty writes are dropped.
    terminal.write("")
    assert window.parsed == ["hello"]


def test_adjustment_terminal_pulse_returns_flags(qapp):
    window = _FakeAdjustmentWindow()
    terminal = wr._AdjustmentTerminal(window)
    keep_going, skip = terminal.Pulse("please wait")
    assert (keep_going, skip) == (True, False)
    assert window.pulses == ["please wait"]
    terminal.keepGoing = False
    assert terminal.Pulse()[0] is False


def test_adjustment_terminal_confirm_same_thread_shows_directly(qapp):
    window = _FakeAdjustmentWindow()
    terminal = wr._AdjustmentTerminal(window)
    terminal._ask = lambda request: True
    assert terminal.confirm("place instrument", "OK", "Cancel") is True


def test_adjustment_controller_forwards_send_to_worker(qapp):
    window = _FakeAdjustmentWindow()
    worker = FakeCalibrateWorker()
    ctrl = wr.AdjustmentController(worker, window)
    assert ctrl is not None
    window.send_requested.emit("2")
    assert worker.sent == ["2"]


def test_adjustment_controller_sets_interactive_state(qapp):
    window = _FakeAdjustmentWindow()
    block = Event()
    worker = FakeCalibrateWorker(block=block)
    ctrl = wr.AdjustmentController(worker, window)
    try:
        ctrl.run(remove=True)
        assert worker.interactive is True
        assert worker.interactive_frame == "adjust"
        assert worker.progress_wnd is not None
        assert worker.thread is ctrl._thread
        assert window.reset_calls == 1
        assert window.shown is True
    finally:
        block.set()
        assert _spin_until(qapp, lambda: ctrl.is_running is False)


def test_adjustment_controller_run_calls_consumer_and_cleans_up(qapp):
    window = _FakeAdjustmentWindow()
    worker = FakeCalibrateWorker(result=True)
    ctrl = wr.AdjustmentController(worker, window)
    got = []
    ctrl.run(got.append, remove=True)
    assert _spin_until(qapp, lambda: got)
    assert got == [True]
    # The streamed chunk reached the window on the GUI thread.
    assert window.parsed == ["Patch 1 of 10"]
    assert worker.progress_wnd is None
    assert worker.terminal is None
    assert worker.thread is None
    assert window.shown is False
    assert ctrl.is_running is False


def test_adjustment_controller_ignores_second_run_while_running(qapp):
    window = _FakeAdjustmentWindow()
    block = Event()
    worker = FakeCalibrateWorker(block=block)
    ctrl = wr.AdjustmentController(worker, window)
    try:
        ctrl.run(remove=True)
        first_thread = ctrl._thread
        ctrl.run(remove=True)  # ignored while running
        assert ctrl._thread is first_thread
    finally:
        block.set()
        assert _spin_until(qapp, lambda: ctrl.is_running is False)
