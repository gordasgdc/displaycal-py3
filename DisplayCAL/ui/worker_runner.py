"""Qt worker execution layer (Stage 5, worker execution).

Home of the Qt-side driver that runs :class:`DisplayCAL.worker.Worker`
operations for the Qt main window, replacing the wx-event-loop-bound
``Worker.start()`` path (``delayedresult`` threading, ``wx.CallAfter``, the wx
``ProgressDialog`` and its ``wx.Timer``-driven ``progress_handler``). See
``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 5).

This first piece is the toolkit-neutral progress parser lifted out of
``Worker.progress_handler`` (worker.py:15022). The wx handler cannot be reused
under Qt because it is interleaved with ``wx.GetApp()`` / ``wx.CallAfter`` /
``DisplayAdjustmentFrame`` calls that require a running wx app; only the
numeric percentage extraction is toolkit-neutral, and that is what the Qt
progress poll needs. Keeping it here as a pure function makes it unit-testable
without a display and lets the wx handler delegate to it later.
"""

from __future__ import annotations

import contextlib
import re
from threading import Event
from time import time
from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import QObject, QThread, QTimer, Signal

from DisplayCAL import localization as lang
from DisplayCAL.argyll import get_argyll_utilname
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui import message_box
from DisplayCAL.ui.progress_dialog import ProgressDialog

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

    from DisplayCAL.worker import Worker

# How often (ms) the GUI-thread poll reads the worker output buffers. Matches
# the ~75 ms cadence of the wx ProgressDialog timer that drove progress_handler.
POLL_INTERVAL_MS = 75

# Argyll warnings look like ``dispread: Warning - ...``; they must not be parsed
# as progress and are stripped before matching, matching the wx handler.
_WARNING_RE = re.compile(r"\D+: Warning -.*")
_PERCENT_RE = re.compile(r"\s*\d+%\s*(?:[^=]+)?$")
_PATCH_RE = re.compile(r"Patch \d+ of \d+", re.IGNORECASE)
_ADDED_RE = re.compile(r"Added \d+/\d+", re.IGNORECASE)
_ITERATION_RE = re.compile(r"It (\d+):")

# targen refines over at most this many iterations.
_TARGEN_ITERATIONS = 20.0


def _resolve_progress_type(worker: Worker, pauseable: bool) -> int:  # noqa: FBT001
    """Pick the throbber animation type, mirroring wx ``Worker.set_progress_type``.

    Args:
        worker (Worker): The worker whose current command / interactive state
            decides the type.
        pauseable (bool): Whether the run is pauseable (implies a measurement,
            same shortcut wx takes).

    Returns:
        int: 0 (processing), 1 (measuring) or 2 (generating test patches),
        forwarded to
        :meth:`DisplayCAL.ui.progress_dialog.ProgressDialog.set_progress_type`.
    """
    if pauseable or getattr(worker, "interactive_frame", "") in (
        "ambient",
        "luminance",
    ):
        return 1
    if getattr(worker, "cmdname", None) == get_argyll_utilname("targen"):
        return 2
    return 0


def parse_progress(msg: str, lastmsg: str) -> tuple[float | None, str]:
    """Extract a completion percentage from Argyll command output.

    Toolkit-neutral port of the parsing in ``Worker.progress_handler``. Handles
    the four shapes Argyll emits:

    * ``NN%`` download / colprof progress,
    * ``Patch N of M`` dispcal / dispread measurement progress,
    * ``Added N/M`` targen patch generation,
    * ``It N:`` targen optimisation iterations (which also clears ``lastmsg``).

    Args:
        msg (str): The recent accumulated output (``Worker.recent``).
        lastmsg (str): The most recent single line (``Worker.lastmsg``).

    Returns:
        tuple[float | None, str]: The percentage in ``0..100`` (or ``None`` when
        no progress could be parsed) and the possibly-cleared ``lastmsg``.
    """
    msg = _WARNING_RE.sub("", msg)
    lastmsg = _WARNING_RE.sub("", lastmsg).strip()
    percentage: float | None = None
    # Filter for '=' (via the regex) so a 1% reading during calibration-check
    # measurements doesn't get treated as command progress.
    if _PERCENT_RE.match(lastmsg):
        with contextlib.suppress(ValueError):
            percentage = int(lastmsg.split("%")[0])
    elif _PATCH_RE.match(lastmsg):
        components = lastmsg.split()
        with contextlib.suppress(ValueError, IndexError):
            start = float(components[1])
            end = float(components[3])
            percentage = max(start - 1, 0) / end * 100
    elif _ADDED_RE.match(lastmsg):
        components = lastmsg.lower().replace("added ", "").split("/")
        with contextlib.suppress(ValueError, IndexError):
            start = float(components[0])
            end = float(components[1])
            percentage = start / end * 100
    else:
        iteration = _ITERATION_RE.search(msg)
        if iteration:
            with contextlib.suppress(ValueError):
                start = float(iteration.groups()[0])
                percentage = min(start, _TARGEN_ITERATIONS) / _TARGEN_ITERATIONS * 100
                lastmsg = ""
    if percentage is not None:
        percentage = max(min(percentage, 100), 0)
    return percentage, lastmsg


class _ConfirmRequest:
    """A pending confirmation, handed from the worker thread to the GUI thread.

    The worker thread fills in the prompt fields and blocks on :attr:`event`;
    the GUI thread shows the dialog, writes :attr:`result` and sets the event,
    releasing the worker thread. This is how the Qt adapter reproduces the
    blocking ``ConfirmDialog.ShowModal()`` the worker previously called inline
    (see ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``, Stage 5, sub-slice 5b-iii).
    """

    __slots__ = ("cancel", "event", "icon", "msg", "ok", "result")

    def __init__(self, msg: str, ok: str, cancel: str, icon: str) -> None:
        self.msg = msg
        self.ok = ok
        self.cancel = cancel
        self.icon = icon
        self.result = False
        self.event = Event()


class _Confirm3Request:
    """A pending three-button confirmation, handed worker thread to GUI thread.

    Mirrors :class:`_ConfirmRequest`, but for the one wx ``ConfirmDialog``
    usage with an ``alt`` third button
    (``Worker.detected_levels_issue_confirm``): retry / fix via calibration /
    cancel.
    """

    __slots__ = ("alt", "cancel", "event", "icon", "msg", "result", "retry")

    def __init__(self, msg: str, retry: str, alt: str, cancel: str, icon: str) -> None:
        self.msg = msg
        self.retry = retry
        self.alt = alt
        self.cancel = cancel
        self.icon = icon
        self.result = "cancel"
        self.event = Event()


class _PasswordRequest:
    """A pending sudo password prompt, handed from the worker thread to the GUI thread.

    Mirrors :class:`_ConfirmRequest`, but the GUI thread hands back an entered
    password (or ``None`` on cancel) instead of a yes/no answer.
    """

    __slots__ = ("event", "msg", "result")

    def __init__(self, msg: str) -> None:
        self.msg = msg
        self.result: str | None = None
        self.event = Event()


class PasswordPromptAdapter(QObject):
    """Thread-safe stand-in for the wx sudo-password ``ConfirmDialog``.

    ``Sudo.authenticate`` (``DisplayCAL/worker.py``) calls this in place of
    building its wx password dialog inline when ``Worker.password_prompt`` is
    set, reproducing the blocking ``ShowModal()`` round-trip: the request is
    marshalled to the GUI thread (which owns the dialog) and the calling
    thread blocks until the user answers. Assign an instance to
    ``Worker.password_prompt`` in any Qt window that offers an elevated
    (root) install scope (``InstallProfileWindow``,
    ``colorimeter_correction_io.ImportController``).

    Args:
        parent (QWidget | None): Parent window for the password dialog.
    """

    _requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._parent = parent
        self._requested.connect(self._on_requested)

    def __call__(self, msg: str) -> str | None:
        """Prompt for a password and block the calling thread for the answer.

        Args:
            msg (str): The prompt message (may include a previous-attempt
                error, matching ``Sudo.authenticate``'s in-place message
                update on a rejected password).

        Returns:
            str | None: The entered password, or None if the user cancelled.
        """
        request = _PasswordRequest(msg)
        if QThread.currentThread() is self.thread():
            # Already on the GUI thread (unusual): show directly, no blocking.
            return self._ask(request)
        self._requested.emit(request)
        request.event.wait()
        return request.result

    def _on_requested(self, request: _PasswordRequest) -> None:
        """Show the password dialog on the GUI thread and release the caller."""
        try:
            request.result = self._ask(request)
        finally:
            request.event.set()

    def _ask(self, request: _PasswordRequest) -> str | None:
        """Show the actual Qt password dialog (GUI thread).

        Split out as the single toolkit touch-point so tests can drive the
        blocking round-trip without a real modal event loop.
        """
        from qtpy.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QLabel,
            QLineEdit,
            QVBoxLayout,
        )

        dialog = QDialog(self._parent)
        dialog.setWindowTitle(APPNAME)
        layout = QVBoxLayout(dialog)
        label = QLabel(request.msg)
        label.setWordWrap(True)
        layout.addWidget(label)
        line_edit = QLineEdit()
        line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        line_edit.returnPressed.connect(dialog.accept)
        layout.addWidget(line_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        line_edit.setFocus()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return line_edit.text()
        return None


class _ProducerThread(QThread):
    """Run a worker producer off the GUI thread.

    The producer (e.g. ``Worker.measure``) blocks while Argyll runs; running it
    on a ``QThread`` keeps the GUI responsive. Its return value -- ``True`` /
    ``False`` or an ``Exception`` instance, following the worker contract -- is
    delivered back on the GUI thread via :attr:`finished_with_result`. Any raised
    exception is caught and delivered the same way, mirroring the wx
    ``Producer`` wrapper.
    """

    #: Emitted with the producer's result (bool or Exception) when it finishes.
    finished_with_result = Signal(object)

    def __init__(
        self,
        producer: Callable,
        wargs: tuple = (),
        wkwargs: dict | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._producer = producer
        self._wargs = wargs
        self._wkwargs = wkwargs or {}
        #: The worker probes ``self.thread.name`` in ``quit_terminate_cmd``; give
        #: the QThread the ``threading.Thread``-style attributes it expects when
        #: it is installed as ``worker.thread`` (interactive calibration).
        self.name = "qt-worker-producer"

    def is_alive(self) -> bool:
        """``threading.Thread``-style alias the worker uses via ``worker.thread``.

        ``Worker.exec_cmd`` gates adding the interactive terminal / output
        buffers to the log stream on ``self.thread.is_alive()``, so a QThread
        standing in for ``worker.thread`` must answer to that name.
        """
        return self.isRunning()

    def run(self) -> None:
        """Run the producer and emit its result."""
        try:
            result = self._producer(*self._wargs, **self._wkwargs)
        except Exception as exception:  # noqa: BLE001 - surfaced as the result
            result = exception
        self.finished_with_result.emit(result)


class _AnimBmpProxy:
    """Thread-safe stand-in for ``ProgressDialog.animbmp.frame`` assignment.

    ``Worker.audio_visual_feedback`` (``DisplayCAL/worker.py``) is
    toolkit-neutral and, when there is no wx ``App`` running, is called
    directly on the measurement thread (see ``FilteredStream._write``). On
    every "Patch N of M" line it does ``self.progress_wnd.animbmp.frame = 0``
    to replay the shutter's open/close blink -- but a real ``AnimatedBitmap``
    is a ``QWidget`` and can't be touched off the GUI thread. This proxy
    stands in for ``progress_wnd.animbmp`` and re-emits that assignment as a
    queued signal instead.
    """

    def __init__(self, adapter: ProgressAdapter) -> None:
        self._adapter = adapter

    @property
    def frame(self) -> int:
        """Unused by the worker (write-only from its side); always 0."""
        return 0

    @frame.setter
    def frame(self, value: int) -> None:
        self._adapter._patch_read.emit(value)  # noqa: SLF001 - cooperating class


class ProgressAdapter(QObject):
    """Thread-safe stand-in for the wx ``progress_wnd`` the worker drives.

    The worker calls progress methods on ``self.progress_wnd`` directly from the
    measurement thread. Touching a ``QWidget`` from a non-GUI thread is unsafe,
    so this adapter takes those calls, returns the ``(keepGoing, skip)`` tuple
    synchronously from plain flags (safe to read from any thread), and marshals
    the actual GUI update onto the GUI thread through queued signals. The
    adapter must be created on the GUI thread so its signal deliveries queue.

    It also duck-types the ``animbmp`` / ``sound_on_off_btn`` attributes
    ``Worker.audio_visual_feedback`` probes via ``hasattr`` to decide whether
    to replay the shutter blink and play the (toolkit-neutral)
    ``commit_sound`` / ``measurement_sound`` on each patch read -- without
    them, that method silently no-ops for the Qt dialog.

    Only the surface the non-interactive measurement path touches is
    implemented; the mid-measurement instrument prompts (``self.dlg = ...``) are
    sub-slice 5b-iii.

    Args:
        dialog (ProgressDialog): The Qt progress dialog to drive.
        parent (QObject | None): Optional Qt parent.
    """

    _message = Signal(str)
    _progress = Signal(float, str)
    _title = Signal(str)
    _confirm_requested = Signal(object)
    _confirm3_requested = Signal(object)
    _patch_read = Signal(int)

    def __init__(self, dialog: ProgressDialog, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._dialog = dialog
        # Flags the worker thread reads/writes; plain attributes are fine.
        self.keepGoing = True  # noqa: N815 - mirrors the wx attribute name
        self.skip = False
        self.paused = False
        self.original_msg = ""
        self.progress_type = 0
        self.dlg = None
        # Duck-typed for Worker.audio_visual_feedback's hasattr() checks; see
        # _AnimBmpProxy and _on_patch_read.
        self.animbmp = _AnimBmpProxy(self)
        self.sound_on_off_btn = True
        self._message.connect(self._apply_message)
        self._progress.connect(self._apply_progress)
        self._title.connect(self._apply_title)
        # Queued so a confirm requested from the worker thread is shown on the
        # GUI thread; the worker thread blocks until the request is answered.
        self._confirm_requested.connect(self._on_confirm_requested)
        self._confirm3_requested.connect(self._on_confirm3_requested)
        self._patch_read.connect(self._on_patch_read)

    # -- wx progress_wnd interface (may run on the worker thread) -----------

    def Pulse(self, msg: str | None = None) -> tuple[bool, bool]:  # noqa: N802
        """Show an indeterminate update.

        Args:
            msg (str | None): Optional message.

        Returns:
            tuple[bool, bool]: ``(keepGoing, skip)``.
        """
        if msg:
            self._message.emit(msg)
        return self.keepGoing, self.skip

    UpdatePulse = Pulse

    def UpdateProgress(  # noqa: N802
        self, value: float, msg: str | None = None
    ) -> tuple[bool, bool]:
        """Show a determinate update.

        Args:
            value (float): Progress value.
            msg (str | None): Optional message.

        Returns:
            tuple[bool, bool]: ``(keepGoing, skip)``.
        """
        self._progress.emit(float(value), msg or "")
        return self.keepGoing, self.skip

    def SetTitle(self, title: str) -> None:  # noqa: N802
        """Set the dialog title (marshalled to the GUI thread)."""
        self._title.emit(title)

    def Resume(self) -> None:  # noqa: N802
        """Resume after a pause (clears the abort flag)."""
        self.keepGoing = True

    def reset(self) -> None:
        """Reset progress (no-op flag reset; the controller resets the dialog)."""
        self.keepGoing = True

    def confirm(  # noqa: PLR0913
        self,
        msg: str,
        ok: str,
        cancel: str,
        icon: str = "dialog-information",
    ) -> bool:
        """Show a modal confirmation and block the worker thread for the answer.

        Called from the worker thread in place of the wx
        ``ConfirmDialog.ShowModal()`` the worker used to run inline. The request
        is marshalled to the GUI thread (which owns the dialog) and this call
        blocks until the user answers, mirroring the modal wx behaviour.

        Args:
            msg (str): The message to show.
            ok (str): The confirm (accept) button label.
            cancel (str): The cancel (reject) button label.
            icon (str): The icon name, ``"dialog-warning"`` for a warning else
                an information icon.

        Returns:
            bool: True if the user confirmed, False if they cancelled.
        """
        request = _ConfirmRequest(msg, ok, cancel, icon)
        if QThread.currentThread() is self.thread():
            # Already on the GUI thread (unusual): show directly, no blocking.
            return self._ask(request)
        self._confirm_requested.emit(request)
        request.event.wait()
        return request.result

    def _on_confirm_requested(self, request: _ConfirmRequest) -> None:
        """Show the confirm dialog on the GUI thread and release the worker."""
        try:
            request.result = self._ask(request)
        finally:
            request.event.set()

    def _ask(self, request: _ConfirmRequest) -> bool:
        """Show the actual Qt confirm dialog (GUI thread).

        Split out as the single toolkit touch-point so tests can drive the
        blocking round-trip without a real modal event loop.
        """
        from qtpy.QtWidgets import QMessageBox

        box = QMessageBox(self._dialog)
        box.setIcon(
            QMessageBox.Icon.Warning
            if request.icon == "dialog-warning"
            else QMessageBox.Icon.Information
        )
        box.setText(request.msg)
        ok_button = box.addButton(request.ok, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(request.cancel, QMessageBox.ButtonRole.RejectRole)
        message_box.exec_box(box)
        return box.clickedButton() is ok_button

    def confirm3(  # noqa: PLR0913
        self,
        msg: str,
        retry: str,
        alt: str,
        cancel: str,
        icon: str = "dialog-warning",
    ) -> str:
        """Show a modal three-button confirmation, blocking the worker thread.

        Services ``Worker.detected_levels_issue_confirm`` in place of the wx
        ``ConfirmDialog(ok=retry, alt=alt)`` it built inline.

        Args:
            msg (str): The message to show.
            retry (str): The "retry" (primary) button label.
            alt (str): The alternate-action button label.
            cancel (str): The cancel button label.
            icon (str): The icon name, ``"dialog-warning"`` for a warning else
                an information icon.

        Returns:
            str: ``"retry"``, ``"alt"``, or ``"cancel"``.
        """
        request = _Confirm3Request(msg, retry, alt, cancel, icon)
        if QThread.currentThread() is self.thread():
            return self._ask3(request)
        self._confirm3_requested.emit(request)
        request.event.wait()
        return request.result

    def _on_confirm3_requested(self, request: _Confirm3Request) -> None:
        """Show the three-button dialog on the GUI thread and release the worker."""
        try:
            request.result = self._ask3(request)
        finally:
            request.event.set()

    def _ask3(self, request: _Confirm3Request) -> str:
        """Show the actual Qt three-button dialog (GUI thread)."""
        from qtpy.QtWidgets import QMessageBox

        box = QMessageBox(self._dialog)
        box.setIcon(
            QMessageBox.Icon.Warning
            if request.icon == "dialog-warning"
            else QMessageBox.Icon.Information
        )
        box.setText(request.msg)
        retry_button = box.addButton(request.retry, QMessageBox.ButtonRole.AcceptRole)
        alt_button = box.addButton(request.alt, QMessageBox.ButtonRole.ActionRole)
        box.addButton(request.cancel, QMessageBox.ButtonRole.RejectRole)
        message_box.exec_box(box)
        clicked = box.clickedButton()
        if clicked is retry_button:
            return "retry"
        if clicked is alt_button:
            return "alt"
        return "cancel"

    # The worker probes these for visibility / layout; they are not meaningful
    # for the adapter, so they are safe no-ops / simple answers.
    def Show(self, show: bool = True) -> None:  # noqa: N802, FBT001, FBT002
        """No-op: the controller owns dialog visibility."""

    def Hide(self) -> None:  # noqa: N802
        """No-op: the controller owns dialog visibility."""

    def Layout(self) -> None:  # noqa: N802
        """No-op: Qt lays out automatically."""

    def start_timer(self, ms: int = 75) -> None:
        """No-op: the controller owns the poll timer."""

    def stop_timer(self, immediate: bool = True) -> None:  # noqa: FBT001, FBT002
        """No-op: the controller owns the poll timer."""

    def IsShownOnScreen(self) -> bool:  # noqa: N802
        """Report whether the dialog is visible."""
        return bool(self._dialog.isVisible())

    def IsShown(self) -> bool:  # noqa: N802
        """Report whether the dialog is visible."""
        return bool(self._dialog.isVisible())

    def IsActive(self) -> bool:  # noqa: N802
        """Report whether the dialog is the active window."""
        return bool(self._dialog.isActiveWindow())

    def Raise(self) -> None:  # noqa: N802
        """No-op: raising is handled by the controller if needed."""

    # -- GUI-thread slots ---------------------------------------------------

    def _apply_message(self, msg: str) -> None:
        """Apply a pulsed message on the GUI thread."""
        self._dialog.pulse(msg)

    def _apply_progress(self, value: float, msg: str) -> None:
        """Apply a determinate update on the GUI thread."""
        self._dialog.set_progress(value, msg or None)

    def _apply_title(self, title: str) -> None:
        """Apply a title change on the GUI thread."""
        self._dialog.setWindowTitle(title)

    def _on_patch_read(self, value: int) -> None:  # noqa: ARG002 - wx sets 0 only
        """Replay the shutter blink on the GUI thread (see _AnimBmpProxy)."""
        self._dialog.on_patch_read()


class WorkerRunController(QObject):
    """Drive a :class:`DisplayCAL.worker.Worker` operation under Qt.

    The Qt replacement for ``Worker.start()``'s non-interactive path: it runs a
    producer on a :class:`_ProducerThread`, shows the Qt
    :class:`~DisplayCAL.ui.progress_dialog.ProgressDialog`, polls the worker's
    output buffers on the GUI thread (via :func:`parse_progress`) to advance the
    bar, and calls the consumer on the GUI thread when the producer finishes.
    The interactive-calibration path (``DisplayAdjustmentFrame``) is sub-slice
    5c.

    Args:
        worker (Worker): The worker whose producer will run.
        dialog (ProgressDialog): The progress dialog to drive.
        parent (QObject | None): Optional Qt parent.
    """

    #: Emitted with the producer's result after the consumer has run.
    finished = Signal(object)

    def __init__(
        self, worker: Worker, dialog: ProgressDialog, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._dialog = dialog
        self._adapter: ProgressAdapter | None = None
        self._thread: _ProducerThread | None = None
        self._consumer: Callable | None = None
        self._pauseable = False
        self._poll = QTimer(self)
        self._poll.setInterval(POLL_INTERVAL_MS)
        self._poll.timeout.connect(self._on_poll)
        dialog.cancelled.connect(self._on_cancel)
        dialog.pause_toggled.connect(self._on_pause)

    @property
    def is_running(self) -> bool:
        """Whether a producer thread is currently running."""
        return self._thread is not None and self._thread.isRunning()

    def run(
        self,
        producer: Callable,
        consumer: Callable | None = None,
        *,
        wargs: tuple = (),
        wkwargs: dict | None = None,
        progress_title: str = APPNAME,
        progress_msg: str = "",
        pauseable: bool = True,
        cancelable: bool = True,
        interactive_frame: str = "",
    ) -> None:
        """Start a worker producer with the progress dialog.

        Args:
            producer (Callable): The worker method to run off the GUI thread
                (e.g. ``worker.measure``).
            consumer (Callable | None): Called on the GUI thread with the
                producer result when it finishes.
            wargs (tuple): Positional arguments for the producer.
            wkwargs (dict | None): Keyword arguments for the producer.
            progress_title (str): Progress dialog title.
            progress_msg (str): Initial progress message.
            pauseable (bool): Whether the operation can be paused.
            cancelable (bool): Whether the operation can be cancelled.
            interactive_frame (str): Passed through to
                ``Worker._init_run_state``. ``"ambient"`` or ``"luminance"``
                makes a single-shot ``spotread`` run auto-answer its "hit a
                key to read" prompt (see ``Worker.check_is_single_measurement``
                / ``do_single_measurement``) instead of blocking forever on a
                keystroke this headless run can never send.
        """
        if self.is_running:
            return
        self._prepare_worker(
            pauseable=pauseable,
            cancelable=cancelable,
            interactive_frame=interactive_frame,
        )
        self._adapter = ProgressAdapter(self._dialog)
        self._worker.progress_wnd = self._adapter
        self._consumer = consumer
        self._pauseable = pauseable

        self._dialog.reset()
        self._dialog.setWindowTitle(progress_title)
        self._dialog.set_message(progress_msg or lang.getstr("please_wait"))
        self._dialog.pause_button.setVisible(pauseable)
        # Prime the throbber type synchronously (no fade delay) before
        # start_clock() below plays it; only later mid-run switches (in
        # _on_poll) go through the fade transition.
        self._dialog.progress_type = _resolve_progress_type(self._worker, pauseable)
        self._dialog.place()
        self._dialog.show()
        self._dialog.start_clock()

        self._thread = _ProducerThread(producer, wargs, wkwargs or {}, parent=self)
        # exec_cmd() only wires the subprocess output into worker.recent/
        # lastmsg/self (and thus into parse(), which answers Argyll's
        # mid-measurement "hit a key to continue" prompts via safe_send())
        # when hasattr(worker, "thread") and worker.thread.is_alive() - so
        # this has to stand in for worker.thread here exactly like
        # AdjustmentController does for the interactive path.
        self._worker.thread = self._thread
        self._thread.finished_with_result.connect(self._on_finished)
        self._poll.start()
        self._thread.start()

    def _prepare_worker(
        self, *, pauseable: bool, cancelable: bool, interactive_frame: str = ""
    ) -> None:
        """Initialise the worker state ``Worker.start()`` would set."""
        worker = self._worker
        worker.interactive = False
        worker._init_run_state(
            interactive_frame=interactive_frame,
            pauseable=pauseable,
            cancelable=cancelable,
        )

    def _on_poll(self) -> None:
        """Read the worker buffers and advance the dialog (GUI thread)."""
        from DisplayCAL.worker import FilteredStream

        self._dialog.set_progress_type(
            _resolve_progress_type(self._worker, self._pauseable)
        )
        # Mirrors the wx ``progress_handler``'s per-tick ``self.pause_continue()``
        # call: this is what actually reads the dialog's pause button state and
        # sends the Argyll pause/continue keystroke. Without it, toggling
        # "Pause" only updates the dialog UI and never reaches the subprocess.
        self._worker.pause_continue()
        try:
            msg = self._worker.recent.read(FilteredStream.triggers)
            lastmsg = self._worker.lastmsg.read(FilteredStream.triggers).strip()
        except Exception:  # noqa: BLE001 - buffers may be mid-write; skip a tick
            return
        percentage, lastmsg = parse_progress(msg, lastmsg)
        if percentage is not None:
            text = "\n".join(part for part in (msg, lastmsg) if part).strip()
            self._dialog.set_progress(percentage, text or None)
        else:
            text = (msg or lastmsg).strip()
            if text:
                self._dialog.pulse(text)

    def _on_finished(self, result: object) -> None:
        """Handle producer completion on the GUI thread."""
        self._poll.stop()
        self._dialog.stop_clock()
        self._dialog.hide()
        self._worker.progress_wnd = None
        if self._thread is not None:
            # run() has returned by the time this queued slot fires; wait()
            # returns immediately and avoids a "destroyed while running" warning.
            self._thread.wait()
        self._worker.thread = None
        consumer = self._consumer
        self._consumer = None
        self._adapter = None
        self._thread = None
        if consumer is not None:
            consumer(result)
        self.finished.emit(result)

    def _on_cancel(self) -> None:
        """Ask the worker to abort when the user cancels."""
        if self._adapter is not None:
            self._adapter.keepGoing = False
        with contextlib.suppress(Exception):
            self._worker.abort_subprocess(False)

    def _on_pause(self, paused: bool) -> None:  # noqa: FBT001
        """Reflect the dialog pause state so ``Worker.pause_continue`` sees it."""
        if self._adapter is not None:
            self._adapter.paused = paused


class _AdjustmentTerminal(QObject):
    """Thread-safe ``terminal`` + ``progress_wnd`` for the Qt adjustment window.

    The interactive calibration path is different from the non-interactive one:
    ``dispcal`` streams interactive text that the worker writes straight to
    ``worker.terminal`` (via a ``FilteredStream``) from the producer thread, and
    the worker also touches ``worker.progress_wnd`` (status pulses, the
    instrument-placement confirmations, the ``keepGoing`` abort flag) from that
    same thread. Both roles are the one wx ``DisplayAdjustmentFrame``; under Qt
    the ``DisplayAdjustmentWindow`` widget must only be touched on the GUI
    thread, so this proxy stands in for both and marshals every call onto the
    GUI thread through queued signals. It must be created on the GUI thread so
    those deliveries queue.

    Args:
        window: The ``DisplayAdjustmentWindow`` to drive.
        parent (QObject | None): Optional Qt parent.
    """

    _write = Signal(str)
    _pulse = Signal(str)
    _title = Signal(str)
    _reset = Signal()
    _show = Signal()
    _confirm_requested = Signal(object)
    _confirm3_requested = Signal(object)

    def __init__(self, window: object, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window = window
        # Flags the worker thread reads/writes; plain attributes are fine.
        self.keepGoing = True  # noqa: N815 - mirrors the wx attribute name
        self.skip = False
        self.paused = False
        self.dlg = None
        self.original_msg = ""
        self.progress_type = 1
        self._write.connect(window.parse_output)
        self._pulse.connect(window.pulse)
        self._title.connect(window.setWindowTitle)
        self._reset.connect(window.reset)
        self._show.connect(self._on_show)
        self._confirm_requested.connect(self._on_confirm_requested)
        self._confirm3_requested.connect(self._on_confirm3_requested)

    # -- FilteredStream terminal (worker thread) ----------------------------

    def write(self, txt: str) -> None:
        """Render a ``dispcal`` chunk on the GUI thread (worker thread call)."""
        if txt:
            self._write.emit(txt)

    # -- wx progress_wnd interface (worker thread) --------------------------

    @property
    def is_measuring(self) -> bool:
        """Whether the window is mid-measurement (read by the worker)."""
        return bool(getattr(self._window, "is_measuring", False))

    def Pulse(self, msg: str | None = None) -> tuple[bool, bool]:  # noqa: N802
        """Show an indeterminate status update.

        Args:
            msg (str | None): Optional status message.

        Returns:
            tuple[bool, bool]: ``(keepGoing, skip)``.
        """
        if msg:
            self._pulse.emit(str(msg))
        return self.keepGoing, self.skip

    UpdatePulse = Pulse

    def UpdateProgress(  # noqa: N802
        self, value: float, msg: str | None = None
    ) -> tuple[bool, bool]:
        """Show a determinate update (rendered as a status pulse here).

        Args:
            value (float): Progress value (the adjustment window has no overall
                bar, so only the message is shown).
            msg (str | None): Optional status message.

        Returns:
            tuple[bool, bool]: ``(keepGoing, skip)``.
        """
        if msg:
            self._pulse.emit(str(msg))
        return self.keepGoing, self.skip

    def SetTitle(self, title: str) -> None:  # noqa: N802
        """Set the window title (marshalled to the GUI thread)."""
        self._title.emit(str(title))

    def Resume(self) -> None:  # noqa: N802
        """Resume after a pause (clears the abort flag)."""
        self.keepGoing = True

    def reset(self) -> None:
        """Reset the window to its pre-adjustment state (GUI thread)."""
        self.keepGoing = True
        self._reset.emit()

    def confirm(
        self,
        msg: str,
        ok: str,
        cancel: str,
        icon: str = "dialog-information",
    ) -> bool:
        """Show a modal confirmation and block the worker thread for the answer.

        Services ``Worker._prompt_confirm`` for the mid-measurement instrument
        prompts, mirroring :meth:`ProgressAdapter.confirm`.

        Args:
            msg (str): The message to show.
            ok (str): The confirm (accept) button label.
            cancel (str): The cancel (reject) button label.
            icon (str): The icon name (``"dialog-warning"`` for a warning).

        Returns:
            bool: True if the user confirmed, False if they cancelled.
        """
        request = _ConfirmRequest(msg, ok, cancel, icon)
        if QThread.currentThread() is self.thread():
            return self._ask(request)
        self._confirm_requested.emit(request)
        request.event.wait()
        return request.result

    def _on_confirm_requested(self, request: _ConfirmRequest) -> None:
        """Show the confirm dialog on the GUI thread and release the worker."""
        try:
            request.result = self._ask(request)
        finally:
            request.event.set()

    def _ask(self, request: _ConfirmRequest) -> bool:
        """Show the actual Qt confirm dialog, parented to the window."""
        from qtpy.QtWidgets import QMessageBox

        box = QMessageBox(self._window)
        box.setIcon(
            QMessageBox.Icon.Warning
            if request.icon == "dialog-warning"
            else QMessageBox.Icon.Information
        )
        box.setText(request.msg)
        ok_button = box.addButton(request.ok, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(request.cancel, QMessageBox.ButtonRole.RejectRole)
        message_box.exec_box(box)
        return box.clickedButton() is ok_button

    def confirm3(  # noqa: PLR0913
        self,
        msg: str,
        retry: str,
        alt: str,
        cancel: str,
        icon: str = "dialog-warning",
    ) -> str:
        """Show a modal three-button confirmation, blocking the worker thread.

        Services ``Worker.detected_levels_issue_confirm``, mirroring
        :meth:`ProgressAdapter.confirm3`.

        Args:
            msg (str): The message to show.
            retry (str): The "retry" (primary) button label.
            alt (str): The alternate-action button label.
            cancel (str): The cancel button label.
            icon (str): The icon name, ``"dialog-warning"`` for a warning else
                an information icon.

        Returns:
            str: ``"retry"``, ``"alt"``, or ``"cancel"``.
        """
        request = _Confirm3Request(msg, retry, alt, cancel, icon)
        if QThread.currentThread() is self.thread():
            return self._ask3(request)
        self._confirm3_requested.emit(request)
        request.event.wait()
        return request.result

    def _on_confirm3_requested(self, request: _Confirm3Request) -> None:
        """Show the three-button dialog on the GUI thread and release the worker."""
        try:
            request.result = self._ask3(request)
        finally:
            request.event.set()

    def _ask3(self, request: _Confirm3Request) -> str:
        """Show the actual Qt three-button dialog, parented to the window."""
        from qtpy.QtWidgets import QMessageBox

        box = QMessageBox(self._window)
        box.setIcon(
            QMessageBox.Icon.Warning
            if request.icon == "dialog-warning"
            else QMessageBox.Icon.Information
        )
        box.setText(request.msg)
        retry_button = box.addButton(request.retry, QMessageBox.ButtonRole.AcceptRole)
        alt_button = box.addButton(request.alt, QMessageBox.ButtonRole.ActionRole)
        box.addButton(request.cancel, QMessageBox.ButtonRole.RejectRole)
        message_box.exec_box(box)
        clicked = box.clickedButton()
        if clicked is retry_button:
            return "retry"
        if clicked is alt_button:
            return "alt"
        return "cancel"

    def _on_show(self) -> None:
        """Show / raise the window on the GUI thread."""
        self._window.place()
        self._window.show()
        self._window.raise_()

    # The worker probes these for visibility / layout; safe no-ops / answers.
    def Show(self, show: bool = True) -> None:  # noqa: N802, FBT001, FBT002
        """Show the window (marshalled to the GUI thread)."""
        if show:
            self._show.emit()

    def Hide(self) -> None:  # noqa: N802
        """No-op: the controller hides the window on completion."""

    def Layout(self) -> None:  # noqa: N802
        """No-op: Qt lays out automatically."""

    def start_timer(self, ms: int = 50) -> None:
        """No-op: the terminal is fed by the worker's output stream directly."""

    def stop_timer(self, immediate: bool = True) -> None:  # noqa: FBT001, FBT002
        """No-op: there is no poll timer for the interactive path."""

    def IsShownOnScreen(self) -> bool:  # noqa: N802
        """Report whether the window is visible."""
        return bool(self._window.isVisible())

    def IsShown(self) -> bool:  # noqa: N802
        """Report whether the window is visible."""
        return bool(self._window.isVisible())

    def IsActive(self) -> bool:  # noqa: N802
        """Report whether the window is the active window."""
        return bool(self._window.isActiveWindow())

    def Raise(self) -> None:  # noqa: N802
        """No-op: raising is handled on show."""


class AdjustmentController(QObject):
    """Drive an interactive ``Worker.calibrate`` under Qt.

    The interactive counterpart to :class:`WorkerRunController`: it runs the
    ``dispcal`` calibration producer on a :class:`_ProducerThread` with the Qt
    :class:`~DisplayCAL.ui.display_adjustment_window.DisplayAdjustmentWindow` as
    the worker's ``terminal`` / ``progress_wnd`` (through the thread-safe
    :class:`_AdjustmentTerminal`), and wires the window's ``send_requested``
    keys back to ``worker.safe_send``. This is the Qt replacement for the
    ``interactive_frame="adjust"`` branch of ``Worker.start()``.

    Args:
        worker (Worker): The worker whose ``calibrate`` producer will run.
        window: The ``DisplayAdjustmentWindow`` to drive.
        parent (QObject | None): Optional Qt parent.
    """

    #: Emitted with the producer's result after the consumer has run.
    finished = Signal(object)

    def __init__(
        self, worker: Worker, window: object, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._window = window
        self._terminal: _AdjustmentTerminal | None = None
        self._thread: _ProducerThread | None = None
        self._consumer: Callable | None = None
        self._progress_dialog: ProgressDialog | None = None
        self._adapter: ProgressAdapter | None = None
        self._swapped = False
        self._start_time = 0.0
        self._poll = QTimer(self)
        self._poll.setInterval(POLL_INTERVAL_MS)
        self._poll.timeout.connect(self._on_poll)
        window.send_requested.connect(self._on_send)
        window.closing.connect(self._on_window_closing)

    @property
    def is_running(self) -> bool:
        """Whether a calibration producer thread is currently running."""
        return self._thread is not None and self._thread.isRunning()

    def run(self, consumer: Callable | None = None, *, remove: bool = True) -> None:
        """Start the interactive calibration.

        Args:
            consumer (Callable | None): Called on the GUI thread with the
                producer result when calibration finishes.
            remove (bool): Passed through to ``Worker.calibrate`` (whether to
                remove the generated calibration files after processing).
        """
        if self.is_running:
            return
        self._prepare_worker()
        self._terminal = _AdjustmentTerminal(self._window)
        self._worker.terminal = self._terminal
        self._worker.progress_wnd = self._terminal
        self._consumer = consumer
        self._swapped = False
        self._start_time = time()

        self._window.reset()
        self._window.place()
        self._window.show()

        self._thread = _ProducerThread(
            self._worker.calibrate, wkwargs={"remove": remove}, parent=self
        )
        # The producer thread stands in for ``worker.thread`` so ``exec_cmd``
        # attaches the interactive terminal to the output stream.
        self._worker.thread = self._thread
        self._thread.finished_with_result.connect(self._on_finished)
        self._poll.start()
        self._thread.start()

    def _prepare_worker(self) -> None:
        """Set the interactive worker state ``Worker.start()`` would set."""
        worker = self._worker
        worker.interactive = True
        worker._init_run_state(
            interactive_frame="adjust", pauseable=True, cancelable=True
        )

    def _on_send(self, key: str) -> None:
        """Forward a key requested by the window to the ``dispcal`` subprocess."""
        with contextlib.suppress(Exception):
            self._worker.safe_send(key)

    def _on_poll(self) -> None:
        """Advance progress, swapping to a plain progress dialog once due.

        Toolkit-neutral port of the ``wx.CallAfter(self.swap_progress_wnds)``
        branch of ``Worker.progress_handler`` (worker.py): once ``dispcal``
        moves past keyboard interaction into unattended measurement (a
        percentage appears, the interactive window isn't mid-measurement, and
        a few seconds have passed since the run started), keyboard prompts are
        no longer needed. wx swaps the interactive frame for a progress
        dialog there; that branch never fires here because it depends on a
        running wx event loop pumping ``wx.CallAfter``, so without this poll
        the adjustment window would neither hide nor hand off to a progress
        dialog once "Continue calibration" moves past the interactive step.
        """
        from DisplayCAL.worker import FilteredStream

        # See WorkerRunController._on_poll: this is what actually applies the
        # dialog's pause button state to the running subprocess. A no-op
        # before dispcal reaches unattended measurement (worker.pauseable_now
        # is still False), so it's safe to call on every tick.
        self._worker.pause_continue()
        try:
            msg = self._worker.recent.read(FilteredStream.triggers)
            lastmsg = self._worker.lastmsg.read(FilteredStream.triggers).strip()
        except Exception:  # noqa: BLE001 - buffers may be mid-write; skip a tick
            return
        percentage, lastmsg = parse_progress(msg, lastmsg)
        if not self._swapped:
            if (
                percentage is not None
                and time() > self._start_time + 3
                and not getattr(self._window, "is_measuring", False)
            ):
                self._swap_to_progress_dialog()
            return
        if percentage is not None:
            text = "\n".join(part for part in (msg, lastmsg) if part).strip()
            self._progress_dialog.set_progress(percentage, text or None)
        else:
            text = (msg or lastmsg).strip()
            if text:
                self._progress_dialog.pulse(text)

    def _swap_to_progress_dialog(self) -> None:
        """Hide the adjustment window and switch to a plain progress dialog."""
        self._swapped = True
        if self._progress_dialog is None:
            self._progress_dialog = ProgressDialog(self.parent(), pauseable=True)
        dialog = self._progress_dialog
        self._adapter = ProgressAdapter(dialog)
        self._worker.progress_wnd = self._adapter
        dialog.cancelled.connect(self._on_cancel)
        dialog.pause_toggled.connect(self._on_pause)
        dialog.reset()
        dialog.setWindowTitle(lang.getstr("calibration"))
        dialog.pause_button.setVisible(True)
        # Always a measurement from here on (dispcal patch reads).
        dialog.progress_type = 1
        dialog.place()
        dialog.show()
        dialog.start_clock()
        self._window.hide()

    def _on_cancel(self) -> None:
        """Ask the worker to abort when the user cancels the progress dialog."""
        if self._adapter is not None:
            self._adapter.keepGoing = False
        with contextlib.suppress(Exception):
            self._worker.abort_subprocess(False)

    def _on_pause(self, paused: bool) -> None:  # noqa: FBT001
        """Reflect the dialog pause state so ``Worker.pause_continue`` sees it."""
        if self._adapter is not None:
            self._adapter.paused = paused

    def _on_window_closing(self) -> None:
        """Abort a still-running interactive ``dispcal`` when the window closes.

        Closing the window (whether idle at the menu or mid-measurement)
        otherwise leaves the producer thread blocked on the subprocess forever:
        nothing is left to answer its prompts, so the process -- and its
        on-screen patch window -- stays up and the main window never comes
        back. Mirrors :meth:`WorkerRunController._on_cancel`.
        """
        if not self.is_running:
            return
        if self._terminal is not None:
            self._terminal.keepGoing = False
        with contextlib.suppress(Exception):
            self._worker.abort_subprocess(False)

    def _on_finished(self, result: object) -> None:
        """Handle calibration completion on the GUI thread."""
        self._poll.stop()
        if self._swapped and self._progress_dialog is not None:
            self._progress_dialog.stop_clock()
            self._progress_dialog.hide()
            with contextlib.suppress(TypeError):
                self._progress_dialog.cancelled.disconnect(self._on_cancel)
            with contextlib.suppress(TypeError):
                self._progress_dialog.pause_toggled.disconnect(self._on_pause)
        self._window.hide()
        self._worker.progress_wnd = None
        self._worker.terminal = None
        if self._thread is not None:
            # run() has returned by the time this queued slot fires; wait()
            # returns immediately and avoids a "destroyed while running" warning.
            self._thread.wait()
        self._worker.thread = None
        consumer = self._consumer
        self._consumer = None
        self._terminal = None
        self._thread = None
        self._adapter = None
        self._swapped = False
        if consumer is not None:
            consumer(result)
        self.finished.emit(result)


class _UntetheredTerminal(QObject):
    """Thread-safe ``terminal`` + ``progress_wnd`` for the Qt untethered window.

    Mirrors :class:`_AdjustmentTerminal`, but for the "Untethered" pseudo-display
    measurement path (issue #841): ``Worker.measure`` / ``Worker.measure_ti1``
    run ``spotread`` interactively, streaming a per-patch prompt to
    ``worker.terminal`` and touching ``worker.progress_wnd`` (status pulses,
    the instrument-placement confirmation) from the producer thread. Both
    roles are the one wx ``UntetheredFrame``; under Qt the
    :class:`~DisplayCAL.ui.untethered_window.UntetheredWindow` widget must only
    be touched on the GUI thread, so this proxy stands in for both and
    marshals every call onto the GUI thread through queued signals. It must be
    created on the GUI thread so those deliveries queue.

    Also carries :attr:`is_untethered_terminal`, the duck-typed marker
    ``Worker.instrument_place_on_screen``, ``Worker.audio_visual_feedback`` and
    ``Worker.prepare_dispread`` check instead of
    ``isinstance(..., UntetheredFrame)``, since this proxy is not (and cannot
    be, with no running wx ``App``) a real instance of the wx class.

    Args:
        window: The ``UntetheredWindow`` to drive.
        parent (QObject | None): Optional Qt parent.
    """

    _write = Signal(str)
    _pulse = Signal(str)
    _cgats = Signal(object)
    _reset = Signal()
    _show = Signal()
    _confirm_requested = Signal(object)
    _confirm3_requested = Signal(object)

    #: Duck-typed marker; see the class docstring.
    is_untethered_terminal = True

    def __init__(self, window: object, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window = window
        # Flags the worker thread reads/writes; plain attributes are fine.
        self.keepGoing = True  # noqa: N815 - mirrors the wx attribute name
        self.skip = False
        self.paused = False
        self.dlg = None
        self._write.connect(window.parse_txt)
        self._pulse.connect(window.pulse)
        self._cgats.connect(window.set_cgats)
        self._reset.connect(window.reset)
        self._show.connect(self._on_show)
        self._confirm_requested.connect(self._on_confirm_requested)
        self._confirm3_requested.connect(self._on_confirm3_requested)

    # -- FilteredStream terminal (worker thread) ----------------------------

    def write(self, txt: str) -> None:
        """Render a ``spotread`` chunk on the GUI thread (worker thread call)."""
        if txt:
            self._write.emit(txt)

    @property
    def cgats(self) -> object:
        """The CGATS test chart being measured.

        Set (from the worker thread) by ``Worker.set_terminal_cgats``, which
        is what actually populates the window's per-patch grid.
        """
        return getattr(self._window, "cgats", None)

    @cgats.setter
    def cgats(self, value: object) -> None:
        self._cgats.emit(value)

    # -- wx progress_wnd interface (worker thread) --------------------------

    @property
    def is_measuring(self) -> bool:
        """Whether the window is mid-measurement (read by the worker)."""
        return bool(getattr(self._window, "is_measuring", False))

    def Pulse(self, msg: str | None = None) -> tuple[bool, bool]:  # noqa: N802
        """Show an indeterminate status update.

        Args:
            msg (str | None): Optional status message.

        Returns:
            tuple[bool, bool]: ``(keepGoing, skip)``.
        """
        if msg:
            self._pulse.emit(str(msg))
        return self.keepGoing, self.skip

    UpdatePulse = Pulse

    def UpdateProgress(  # noqa: N802
        self, value: float, msg: str | None = None
    ) -> tuple[bool, bool]:
        """Show a determinate update (rendered as a status pulse here).

        Args:
            value (float): Progress value (unused; the untethered window has
                no overall bar, only the per-patch grid).
            msg (str | None): Optional status message.

        Returns:
            tuple[bool, bool]: ``(keepGoing, skip)``.
        """
        if msg:
            self._pulse.emit(str(msg))
        return self.keepGoing, self.skip

    def Resume(self) -> None:  # noqa: N802
        """Resume after a pause (clears the abort flag)."""
        self.keepGoing = True

    def reset(self) -> None:
        """Reset the window to its pre-measurement state (GUI thread)."""
        self.keepGoing = True
        self._reset.emit()

    def confirm(
        self,
        msg: str,
        ok: str,
        cancel: str,
        icon: str = "dialog-information",
    ) -> bool:
        """Show a modal confirmation and block the worker thread for the answer.

        Services ``Worker._prompt_confirm`` (e.g. the instrument on-screen
        placement prompt), mirroring :meth:`ProgressAdapter.confirm`.

        Args:
            msg (str): The message to show.
            ok (str): The confirm (accept) button label.
            cancel (str): The cancel (reject) button label.
            icon (str): The icon name (``"dialog-warning"`` for a warning).

        Returns:
            bool: True if the user confirmed, False if they cancelled.
        """
        request = _ConfirmRequest(msg, ok, cancel, icon)
        if QThread.currentThread() is self.thread():
            return self._ask(request)
        self._confirm_requested.emit(request)
        request.event.wait()
        return request.result

    def _on_confirm_requested(self, request: _ConfirmRequest) -> None:
        """Show the confirm dialog on the GUI thread and release the worker."""
        try:
            request.result = self._ask(request)
        finally:
            request.event.set()

    def _ask(self, request: _ConfirmRequest) -> bool:
        """Show the actual Qt confirm dialog, parented to the window."""
        from qtpy.QtWidgets import QMessageBox

        box = QMessageBox(self._window)
        box.setIcon(
            QMessageBox.Icon.Warning
            if request.icon == "dialog-warning"
            else QMessageBox.Icon.Information
        )
        box.setText(request.msg)
        ok_button = box.addButton(request.ok, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(request.cancel, QMessageBox.ButtonRole.RejectRole)
        message_box.exec_box(box)
        return box.clickedButton() is ok_button

    def confirm3(  # noqa: PLR0913
        self,
        msg: str,
        retry: str,
        alt: str,
        cancel: str,
        icon: str = "dialog-warning",
    ) -> str:
        """Show a modal three-button confirmation, blocking the worker thread.

        Mirrors :meth:`ProgressAdapter.confirm3`.

        Args:
            msg (str): The message to show.
            retry (str): The "retry" (primary) button label.
            alt (str): The alternate-action button label.
            cancel (str): The cancel button label.
            icon (str): The icon name, ``"dialog-warning"`` for a warning else
                an information icon.

        Returns:
            str: ``"retry"``, ``"alt"``, or ``"cancel"``.
        """
        request = _Confirm3Request(msg, retry, alt, cancel, icon)
        if QThread.currentThread() is self.thread():
            return self._ask3(request)
        self._confirm3_requested.emit(request)
        request.event.wait()
        return request.result

    def _on_confirm3_requested(self, request: _Confirm3Request) -> None:
        """Show the three-button dialog on the GUI thread and release the worker."""
        try:
            request.result = self._ask3(request)
        finally:
            request.event.set()

    def _ask3(self, request: _Confirm3Request) -> str:
        """Show the actual Qt three-button dialog, parented to the window."""
        from qtpy.QtWidgets import QMessageBox

        box = QMessageBox(self._window)
        box.setIcon(
            QMessageBox.Icon.Warning
            if request.icon == "dialog-warning"
            else QMessageBox.Icon.Information
        )
        box.setText(request.msg)
        retry_button = box.addButton(request.retry, QMessageBox.ButtonRole.AcceptRole)
        alt_button = box.addButton(request.alt, QMessageBox.ButtonRole.ActionRole)
        box.addButton(request.cancel, QMessageBox.ButtonRole.RejectRole)
        message_box.exec_box(box)
        clicked = box.clickedButton()
        if clicked is retry_button:
            return "retry"
        if clicked is alt_button:
            return "alt"
        return "cancel"

    def _on_show(self) -> None:
        """Show / raise the window on the GUI thread."""
        self._window.place()
        self._window.show()
        self._window.raise_()

    # The worker probes these for visibility / layout; safe no-ops / answers.
    def Show(self, show: bool = True) -> None:  # noqa: N802, FBT001, FBT002
        """Show the window (marshalled to the GUI thread)."""
        if show:
            self._show.emit()

    def Hide(self) -> None:  # noqa: N802
        """No-op: the controller hides the window on completion."""

    def Layout(self) -> None:  # noqa: N802
        """No-op: Qt lays out automatically."""

    def start_timer(self, ms: int = 50) -> None:
        """No-op: the window is fed by the worker's output stream directly."""

    def stop_timer(self, immediate: bool = True) -> None:  # noqa: FBT001, FBT002
        """No-op: there is no poll timer for the interactive path."""

    def IsShownOnScreen(self) -> bool:  # noqa: N802
        """Report whether the window is visible."""
        return bool(self._window.isVisible())

    def IsShown(self) -> bool:  # noqa: N802
        """Report whether the window is visible."""
        return bool(self._window.isVisible())

    def IsActive(self) -> bool:  # noqa: N802
        """Report whether the window is the active window."""
        return bool(self._window.isActiveWindow())

    def Raise(self) -> None:  # noqa: N802
        """No-op: raising is handled on show."""


class UntetheredController(QObject):
    """Drive an interactive untethered measurement (``spotread``) under Qt.

    The untethered counterpart to :class:`AdjustmentController`: it runs the
    given measurement producer (``worker.measure`` or ``worker.measure_ti1``,
    both of which run ``spotread`` interactively when the configured display is
    "Untethered" -- see ``config.is_untethered_display``) on a
    :class:`_ProducerThread` with the Qt
    :class:`~DisplayCAL.ui.untethered_window.UntetheredWindow` as the worker's
    ``terminal`` / ``progress_wnd`` (through the thread-safe
    :class:`_UntetheredTerminal`), and wires the window's ``send_requested``
    keys back to ``worker.safe_send`` and its ``abort_requested`` to
    ``worker.abort_subprocess``. This is the Qt replacement for the
    ``interactive_frame="untethered"`` branch of ``Worker.start()``.

    Args:
        worker (Worker): The worker whose measurement producer will run.
        window: The ``UntetheredWindow`` to drive.
        parent (QObject | None): Optional Qt parent.
    """

    #: Emitted with the producer's result after the consumer has run.
    finished = Signal(object)

    def __init__(
        self, worker: Worker, window: object, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._window = window
        self._terminal: _UntetheredTerminal | None = None
        self._thread: _ProducerThread | None = None
        self._consumer: Callable | None = None
        window.send_requested.connect(self._on_send)
        window.abort_requested.connect(self._on_abort_requested)
        window.closing.connect(self._on_window_closing)

    @property
    def is_running(self) -> bool:
        """Whether a measurement producer thread is currently running."""
        return self._thread is not None and self._thread.isRunning()

    def run(
        self,
        producer: Callable,
        consumer: Callable | None = None,
        *,
        wargs: tuple = (),
        wkwargs: dict | None = None,
    ) -> None:
        """Start the interactive untethered measurement.

        Args:
            producer (Callable): The worker measurement method to run off the
                GUI thread (``worker.measure`` or ``worker.measure_ti1``).
            consumer (Callable | None): Called on the GUI thread with the
                producer result when the measurement finishes.
            wargs (tuple): Positional arguments for the producer.
            wkwargs (dict | None): Keyword arguments for the producer.
        """
        if self.is_running:
            return
        self._prepare_worker()
        self._terminal = _UntetheredTerminal(self._window)
        self._worker.terminal = self._terminal
        self._worker.progress_wnd = self._terminal
        self._consumer = consumer

        self._window.reset()
        self._window.place()
        self._window.show()

        self._thread = _ProducerThread(producer, wargs, wkwargs or {}, parent=self)
        # exec_cmd() only wires the interactive terminal into the output
        # stream (and thus into parse(), which answers spotread's per-patch
        # prompts) when hasattr(worker, "thread") and worker.thread.is_alive()
        # - so this has to stand in for worker.thread here exactly like
        # AdjustmentController does for the interactive calibration path.
        self._worker.thread = self._thread
        self._thread.finished_with_result.connect(self._on_finished)
        self._thread.start()

    def _prepare_worker(self) -> None:
        """Set the interactive worker state ``Worker.start()`` would set."""
        worker = self._worker
        worker.interactive = True
        worker._init_run_state(
            interactive_frame="untethered", pauseable=False, cancelable=True
        )

    def _on_send(self, key: str) -> None:
        """Forward a key requested by the window to the ``spotread`` subprocess."""
        with contextlib.suppress(Exception):
            self._worker.safe_send(key)

    def _on_abort_requested(self) -> None:
        """Abort the running ``spotread`` (the window's Escape/"Q" key binding)."""
        with contextlib.suppress(Exception):
            self._worker.abort_subprocess()

    def _on_window_closing(self) -> None:
        """Abort a still-running ``spotread`` when the window closes.

        Closing the window otherwise leaves the producer thread blocked on
        the subprocess forever: nothing is left to answer its prompts, so the
        process stays up and the main window never comes back. Mirrors
        :meth:`AdjustmentController._on_window_closing`.
        """
        if not self.is_running:
            return
        if self._terminal is not None:
            self._terminal.keepGoing = False
        with contextlib.suppress(Exception):
            self._worker.abort_subprocess(False)

    def _on_finished(self, result: object) -> None:
        """Handle measurement completion on the GUI thread."""
        self._window.hide()
        self._worker.progress_wnd = None
        self._worker.terminal = None
        if self._thread is not None:
            # run() has returned by the time this queued slot fires; wait()
            # returns immediately and avoids a "destroyed while running" warning.
            self._thread.wait()
        self._worker.thread = None
        consumer = self._consumer
        self._consumer = None
        self._terminal = None
        self._thread = None
        if consumer is not None:
            consumer(result)
        self.finished.emit(result)


class _UniformityTerminal(QObject):
    """Thread-safe ``terminal`` + ``progress_wnd`` for the Qt uniformity grid.

    Mirrors :class:`_UntetheredTerminal`, but for the display-uniformity
    measurement grid (issue #947): ``Worker.measure_uniformity_producer`` runs
    ``spotread`` interactively, streaming a per-swatch, per-brightness-level
    prompt to ``worker.terminal`` and touching ``worker.progress_wnd`` (the
    instrument-placement confirmation) from the producer thread. Both roles
    are the one wx ``DisplayUniformityFrame``; under Qt the
    :class:`~DisplayCAL.ui.uniformity_window.UniformityWindow` widget must
    only be touched on the GUI thread, so this proxy stands in for both and
    marshals every call onto the GUI thread through queued signals. It must
    be created on the GUI thread so those deliveries queue.

    Also carries :attr:`is_uniformity_terminal`, the duck-typed marker
    ``Worker.instrument_place_on_screen`` and ``Worker.audio_visual_feedback``
    check instead of ``isinstance(..., DisplayUniformityFrame)``, since this
    proxy is not (and cannot be, with no running wx ``App``) a real instance
    of the wx class.

    Args:
        window: The ``UniformityWindow`` to drive.
        parent (QObject | None): Optional Qt parent.
    """

    _write = Signal(str)
    _reset = Signal()
    _show = Signal()
    _confirm_requested = Signal(object)
    _confirm3_requested = Signal(object)

    #: Duck-typed marker; see the class docstring.
    is_uniformity_terminal = True

    def __init__(self, window: object, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window = window
        # Flags the worker thread reads/writes; plain attributes are fine.
        self.keepGoing = True  # noqa: N815 - mirrors the wx attribute name
        self.skip = False
        self.dlg = None
        self._write.connect(window.parse_txt)
        self._reset.connect(window.reset)
        self._show.connect(self._on_show)
        self._confirm_requested.connect(self._on_confirm_requested)
        self._confirm3_requested.connect(self._on_confirm3_requested)

    # -- FilteredStream terminal (worker thread) ----------------------------

    def write(self, txt: str) -> None:
        """Render a ``spotread`` chunk on the GUI thread (worker thread call)."""
        if txt:
            self._write.emit(txt)

    # -- wx progress_wnd interface (worker thread) --------------------------

    @property
    def is_measuring(self) -> bool:
        """Whether the window is mid-measurement (read by the worker)."""
        return bool(getattr(self._window, "is_measuring", False))

    def Pulse(self, msg: str | None = None) -> tuple[bool, bool]:  # noqa: N802, ARG002
        """Report the keep-going state (the wx frame's ``Pulse`` never shows
        the message either -- see ``DisplayUniformityFrame.Pulse``).

        Returns:
            tuple[bool, bool]: ``(keepGoing, skip)``.
        """
        return self.keepGoing, self.skip

    UpdatePulse = Pulse

    def UpdateProgress(  # noqa: N802
        self, value: float, msg: str | None = None  # noqa: ARG002
    ) -> tuple[bool, bool]:
        """Report the keep-going state (no visible progress in the grid).

        Returns:
            tuple[bool, bool]: ``(keepGoing, skip)``.
        """
        return self.keepGoing, self.skip

    def Resume(self) -> None:  # noqa: N802
        """Resume after a pause (clears the abort flag)."""
        self.keepGoing = True

    def reset(self) -> None:
        """Reset the window to its pre-measurement state (GUI thread)."""
        self.keepGoing = True
        self._reset.emit()

    def confirm(
        self,
        msg: str,
        ok: str,
        cancel: str,
        icon: str = "dialog-information",
    ) -> bool:
        """Show a modal confirmation and block the worker thread for the answer.

        Services ``Worker._prompt_confirm`` (e.g. the instrument on-screen
        placement prompt), mirroring :meth:`ProgressAdapter.confirm`.

        Args:
            msg (str): The message to show.
            ok (str): The confirm (accept) button label.
            cancel (str): The cancel (reject) button label.
            icon (str): The icon name (``"dialog-warning"`` for a warning).

        Returns:
            bool: True if the user confirmed, False if they cancelled.
        """
        request = _ConfirmRequest(msg, ok, cancel, icon)
        if QThread.currentThread() is self.thread():
            return self._ask(request)
        self._confirm_requested.emit(request)
        request.event.wait()
        return request.result

    def _on_confirm_requested(self, request: _ConfirmRequest) -> None:
        """Show the confirm dialog on the GUI thread and release the worker."""
        try:
            request.result = self._ask(request)
        finally:
            request.event.set()

    def _ask(self, request: _ConfirmRequest) -> bool:
        """Show the actual Qt confirm dialog, parented to the window."""
        from qtpy.QtWidgets import QMessageBox

        box = QMessageBox(self._window)
        box.setIcon(
            QMessageBox.Icon.Warning
            if request.icon == "dialog-warning"
            else QMessageBox.Icon.Information
        )
        box.setText(request.msg)
        ok_button = box.addButton(request.ok, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(request.cancel, QMessageBox.ButtonRole.RejectRole)
        message_box.exec_box(box)
        return box.clickedButton() is ok_button

    def confirm3(  # noqa: PLR0913
        self,
        msg: str,
        retry: str,
        alt: str,
        cancel: str,
        icon: str = "dialog-warning",
    ) -> str:
        """Show a modal three-button confirmation, blocking the worker thread.

        Mirrors :meth:`ProgressAdapter.confirm3`.

        Args:
            msg (str): The message to show.
            retry (str): The "retry" (primary) button label.
            alt (str): The alternate-action button label.
            cancel (str): The cancel button label.
            icon (str): The icon name, ``"dialog-warning"`` for a warning else
                an information icon.

        Returns:
            str: ``"retry"``, ``"alt"``, or ``"cancel"``.
        """
        request = _Confirm3Request(msg, retry, alt, cancel, icon)
        if QThread.currentThread() is self.thread():
            return self._ask3(request)
        self._confirm3_requested.emit(request)
        request.event.wait()
        return request.result

    def _on_confirm3_requested(self, request: _Confirm3Request) -> None:
        """Show the three-button dialog on the GUI thread and release the worker."""
        try:
            request.result = self._ask3(request)
        finally:
            request.event.set()

    def _ask3(self, request: _Confirm3Request) -> str:
        """Show the actual Qt three-button dialog, parented to the window."""
        from qtpy.QtWidgets import QMessageBox

        box = QMessageBox(self._window)
        box.setIcon(
            QMessageBox.Icon.Warning
            if request.icon == "dialog-warning"
            else QMessageBox.Icon.Information
        )
        box.setText(request.msg)
        retry_button = box.addButton(request.retry, QMessageBox.ButtonRole.AcceptRole)
        alt_button = box.addButton(request.alt, QMessageBox.ButtonRole.ActionRole)
        box.addButton(request.cancel, QMessageBox.ButtonRole.RejectRole)
        message_box.exec_box(box)
        clicked = box.clickedButton()
        if clicked is retry_button:
            return "retry"
        if clicked is alt_button:
            return "alt"
        return "cancel"

    def _on_show(self) -> None:
        """Show / raise the window on the GUI thread.

        Deliberately a plain ``show()``, not ``showFullScreen()``: see
        ``UniformityWindow.place()`` for why.
        """
        self._window.place()
        self._window.show()
        self._window.raise_()

    # The worker probes these for visibility / layout; safe no-ops / answers.
    def Show(self, show: bool = True) -> None:  # noqa: N802, FBT001, FBT002
        """Show the window (marshalled to the GUI thread)."""
        if show:
            self._show.emit()

    def Hide(self) -> None:  # noqa: N802
        """No-op: the controller hides the window on completion."""

    def Layout(self) -> None:  # noqa: N802
        """No-op: Qt lays out automatically."""

    def start_timer(self, ms: int = 50) -> None:
        """No-op: the window is fed by the worker's output stream directly."""

    def stop_timer(self, immediate: bool = True) -> None:  # noqa: FBT001, FBT002
        """No-op: there is no poll timer for the interactive path."""

    def IsShownOnScreen(self) -> bool:  # noqa: N802
        """Report whether the window is visible."""
        return bool(self._window.isVisible())

    def IsShown(self) -> bool:  # noqa: N802
        """Report whether the window is visible."""
        return bool(self._window.isVisible())

    def IsActive(self) -> bool:  # noqa: N802
        """Report whether the window is the active window."""
        return bool(self._window.isActiveWindow())

    def Raise(self) -> None:  # noqa: N802
        """No-op: raising is handled on show."""


class UniformityController(QObject):
    """Drive an interactive display-uniformity measurement under Qt.

    The uniformity counterpart to :class:`UntetheredController`: it runs
    ``worker.measure_uniformity_producer`` (``spotread``) on a
    :class:`_ProducerThread` with the Qt
    :class:`~DisplayCAL.ui.uniformity_window.UniformityWindow` as the worker's
    ``terminal`` / ``progress_wnd`` (through the thread-safe
    :class:`_UniformityTerminal`), and wires the window's ``send_requested``
    keys back to ``worker.safe_send`` and its ``abort_requested`` to
    ``worker.abort_subprocess``. This is the Qt replacement for the
    ``interactive_frame="uniformity"`` branch of ``Worker.start()``.

    Args:
        worker (Worker): The worker whose measurement producer will run.
        window: The ``UniformityWindow`` to drive.
        parent (QObject | None): Optional Qt parent.
    """

    #: Emitted with the producer's result after the consumer has run.
    finished = Signal(object)

    def __init__(
        self, worker: Worker, window: object, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._window = window
        self._terminal: _UniformityTerminal | None = None
        self._thread: _ProducerThread | None = None
        self._consumer: Callable | None = None
        self._waiting_for_instrument = False
        window.send_requested.connect(self._on_send)
        window.abort_requested.connect(self._on_abort_requested)
        window.closing.connect(self._on_window_closing)

    @property
    def is_running(self) -> bool:
        """Whether a measurement producer thread is currently running."""
        return self._thread is not None and self._thread.isRunning()

    def run(
        self,
        producer: Callable,
        consumer: Callable | None = None,
        *,
        wargs: tuple = (),
        wkwargs: dict | None = None,
    ) -> None:
        """Start the interactive uniformity measurement.

        Args:
            producer (Callable): The worker measurement method to run off the
                GUI thread (``worker.measure_uniformity_producer``).
            consumer (Callable | None): Called on the GUI thread with the
                producer result when the measurement finishes.
            wargs (tuple): Positional arguments for the producer.
            wkwargs (dict | None): Keyword arguments for the producer.
        """
        if self.is_running:
            return
        self._prepare_worker()
        self._terminal = _UniformityTerminal(self._window)
        self._worker.terminal = self._terminal
        self._worker.progress_wnd = self._terminal
        self._consumer = consumer
        self._waiting_for_instrument = False

        self._window.reset()
        self._window.place()
        # Deliberately a plain show(), not showFullScreen(): see
        # UniformityWindow.place() for why.
        self._window.show()

        self._thread = _ProducerThread(producer, wargs, wkwargs or {}, parent=self)
        # exec_cmd() only wires the interactive terminal into the output
        # stream (and thus into parse(), which answers spotread's per-swatch
        # prompts) when hasattr(worker, "thread") and worker.thread.is_alive()
        # - so this has to stand in for worker.thread here exactly like
        # UntetheredController does for its interactive path.
        self._worker.thread = self._thread
        self._thread.finished_with_result.connect(self._on_finished)
        self._thread.start()

    def _prepare_worker(self) -> None:
        """Set the interactive worker state ``Worker.start()`` would set."""
        worker = self._worker
        worker.interactive = True
        worker._init_run_state(  # noqa: SLF001 - cooperating class
            interactive_frame="uniformity", pauseable=False, cancelable=True
        )

    def _on_send(self, key: str) -> None:
        """Forward a key requested by the window to the ``spotread`` subprocess.

        Port of ``DisplayUniformityFrame.safe_send``: waits for
        ``worker.instrument_on_screen`` (set once the instrument-placement
        prompt is confirmed) before actually forwarding, retrying every
        200 ms in the meantime, since the grid's very first swatch click can
        race that confirmation.
        """
        worker = self._worker
        if not (getattr(worker, "subprocess", None) and not worker.subprocess_abort):
            return
        if not worker.instrument_on_screen:
            self._waiting_for_instrument = True
            QTimer.singleShot(200, lambda: self._on_send(key))
            return
        self._waiting_for_instrument = False
        with contextlib.suppress(Exception):
            worker.safe_send(key)

    def _on_abort_requested(self) -> None:
        """Abort the running ``spotread`` (the window's Escape/"Q" key binding)."""
        with contextlib.suppress(Exception):
            self._worker.abort_subprocess()

    def _on_window_closing(self) -> None:
        """Abort a still-running ``spotread`` when the window closes.

        Closing the window otherwise leaves the producer thread blocked on
        the subprocess forever: nothing is left to answer its prompts, so the
        process stays up and the main window never comes back. Mirrors
        :meth:`UntetheredController._on_window_closing`.
        """
        if not self.is_running:
            return
        if self._terminal is not None:
            self._terminal.keepGoing = False
        with contextlib.suppress(Exception):
            self._worker.abort_subprocess(False)

    def _on_finished(self, result: object) -> None:
        """Handle measurement completion on the GUI thread."""
        self._window.hide()
        self._worker.progress_wnd = None
        self._worker.terminal = None
        if self._thread is not None:
            # run() has returned by the time this queued slot fires; wait()
            # returns immediately and avoids a "destroyed while running" warning.
            self._thread.wait()
        self._worker.thread = None
        consumer = self._consumer
        self._consumer = None
        self._terminal = None
        self._thread = None
        if consumer is not None:
            consumer(result)
        self.finished.emit(result)
