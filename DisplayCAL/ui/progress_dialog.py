"""Native Qt progress dialog for long-running worker operations.

Qt successor to the essential, worker-facing behaviour of
:class:`DisplayCAL.wx_windows.ProgressDialog` (see
``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``, Stage 5 -- the worker execution
layer). The wx dialog is ~840 lines because it also carries the *fancy*
presentation: an animated throbber (``AnimatedBitmap`` / ``get_bitmaps``),
looping sound effects (``audio.Sound``), a gradient ``BetterPyGauge`` and
Windows taskbar-progress integration. None of that is load-bearing, so this port
drops it, matching the simplifications the other ported tools made.

What is preserved is the contract the flow actually depends on:

* an indeterminate (``pulse``) and a determinate (``set_progress``) mode,
* elapsed-time and estimated-remaining-time read-outs,
* optional cancel and pause controls, surfaced as Qt signals so the driver (a
  later sub-slice) can stop / pause the worker,
* ``keep_going`` state the driver polls, mirroring wx ``Pulse`` returning
  ``(keepGoing, skip)``,
* position persistence to the shared ``position.progress.*`` config keys, so the
  Qt and wx dialogs stay interchangeable.

The elapsed / remaining maths is factored into the pure module-level
:func:`format_elapsed` and :func:`estimate_remaining` so it is unit-testable
without a display or a ``QApplication``.
"""

from __future__ import annotations

from time import gmtime, strftime, time
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, QTimer, Signal
from qtpy.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.meta import NAME as APPNAME

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent, QMoveEvent
    from qtpy.QtWidgets import QWidget

# Placeholder shown for elapsed / remaining time before an estimate exists,
# matching the wx dialog's ``REMAINING_TIME_LABEL``.
TIME_UNKNOWN = "--:--:--"


# --- pure time maths -------------------------------------------------------


def format_elapsed(seconds: float) -> str:
    """Format a duration in seconds as ``HH:MM:SS``.

    Args:
        seconds (float): The duration in seconds. Negative values are clamped
            to zero.

    Returns:
        str: The duration formatted as ``HH:MM:SS``.
    """
    seconds = max(seconds, 0)
    return strftime("%H:%M:%S", gmtime(seconds))


def estimate_remaining(
    elapsed: float, progress: float, maximum: float
) -> float | None:
    """Estimate the remaining seconds from elapsed time and progress.

    Linear extrapolation from the work done so far, matching the wx dialog's
    ``(t - time2) / value * (range - value)`` estimate.

    Args:
        elapsed (float): Seconds elapsed since progress began advancing.
        progress (float): Current progress value (in ``maximum`` units).
        maximum (float): The progress value that represents completion.

    Returns:
        float | None: The estimated remaining seconds, or ``None`` when there
        is not yet enough information (no elapsed time or no progress).
    """
    if elapsed <= 0 or progress <= 0 or maximum <= 0 or progress >= maximum:
        return None
    remaining = elapsed / progress * (maximum - progress)
    if remaining < 0:
        return None
    return remaining


class ProgressDialog(QDialog):
    """A Qt progress dialog for worker operations.

    Args:
        parent (QWidget | None): Optional parent widget.
        title (str): Window title. Defaults to the application name.
        message (str): Initial status message.
        maximum (int): The progress value that represents completion.
        cancelable (bool): Show a Cancel button that emits :attr:`cancelled`.
        pauseable (bool): Show a Pause/Continue button that emits
            :attr:`pause_toggled`.
        show_remaining_time (bool): Show the estimated-remaining-time read-out.
    """

    #: Emitted when the user asks to cancel the operation.
    cancelled = Signal()
    #: Emitted with the new paused state when the user toggles pause.
    pause_toggled = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = APPNAME,
        message: str = "",
        maximum: int = 100,
        *,
        cancelable: bool = True,
        pauseable: bool = False,
        show_remaining_time: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("progressdialog")
        self.setWindowTitle(title)
        # Keep the dialog non-modal; the driver disables the owner window.
        self.setModal(False)

        self._maximum = maximum
        self._progress = 0.0
        self._indeterminate = True
        self._paused = False
        self._keep_going = True
        self.skip = False
        self._start_time = time()
        # When determinate progress first advanced, for the remaining estimate.
        self._progress_start_time: float | None = None
        self._show_remaining_time = show_remaining_time

        layout = QVBoxLayout(self)

        self._message = QLabel(message or lang.getstr("please_wait"))
        self._message.setWordWrap(True)
        self._message.setMinimumWidth(400)
        self._message.setMinimumHeight(64)
        self._message.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        layout.addWidget(self._message)

        self._gauge = QProgressBar()
        self._gauge.setTextVisible(False)
        self._gauge.setRange(0, 0)  # indeterminate until set_progress()
        layout.addWidget(self._gauge)

        time_row = QHBoxLayout()
        self._elapsed_label = QLabel(f"{lang.getstr('elapsed_time')} {TIME_UNKNOWN}")
        time_row.addWidget(self._elapsed_label)
        if show_remaining_time:
            self._remaining_label = QLabel(
                f"{lang.getstr('remaining_time')} {TIME_UNKNOWN}"
            )
            time_row.addStretch(1)
            time_row.addWidget(self._remaining_label)
        else:
            self._remaining_label = None
        layout.addLayout(time_row)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.pause_button = QPushButton(lang.getstr("pause"))
        self.pause_button.setVisible(pauseable)
        self.pause_button.clicked.connect(self._on_pause_clicked)
        button_row.addWidget(self.pause_button)
        if cancelable:
            self.cancel_button: QPushButton | None = QPushButton(lang.getstr("cancel"))
            self.cancel_button.clicked.connect(self._on_cancel_clicked)
            button_row.addWidget(self.cancel_button)
        else:
            self.cancel_button = None
        layout.addLayout(button_row)

        # One-second clock driving the elapsed / remaining read-outs.
        self._clock = QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._update_times)

        self.reset()

    # -- worker-facing state ------------------------------------------------

    @property
    def keep_going(self) -> bool:
        """Whether the operation should continue (False once cancelled)."""
        return self._keep_going

    @property
    def paused(self) -> bool:
        """Whether the operation is currently paused."""
        return self._paused

    def reset(self) -> None:
        """Reset progress and the elapsed / remaining read-outs."""
        self._progress = 0.0
        self._indeterminate = True
        self._progress_start_time = None
        self._start_time = time()
        self._gauge.setRange(0, 0)
        self._elapsed_label.setText(
            f"{lang.getstr('elapsed_time')} {format_elapsed(0)}"
        )
        if self._remaining_label is not None:
            self._remaining_label.setText(
                f"{lang.getstr('remaining_time')} {TIME_UNKNOWN}"
            )

    def set_message(self, message: str) -> None:
        """Set the status message.

        Args:
            message (str): The new status message.
        """
        if message and message != self._message.text():
            self._message.setText(message)

    def pulse(self, message: str | None = None) -> bool:
        """Switch to the indeterminate (pulsing) mode.

        Args:
            message (str | None): Optional status message to show.

        Returns:
            bool: The current :attr:`keep_going` state, mirroring wx ``Pulse``.
        """
        if message:
            self.set_message(message)
        if not self._indeterminate:
            self._indeterminate = True
            self._gauge.setRange(0, 0)
            if self._remaining_label is not None:
                self._remaining_label.setText(
                    f"{lang.getstr('remaining_time')} {TIME_UNKNOWN}"
                )
        return self._keep_going

    def set_progress(self, value: float, message: str | None = None) -> bool:
        """Set the determinate progress value.

        Args:
            value (float): The new progress value, in ``maximum`` units.
            message (str | None): Optional status message to show.

        Returns:
            bool: The current :attr:`keep_going` state.
        """
        if message:
            self.set_message(message)
        value = max(0.0, min(float(value), float(self._maximum)))
        if self._indeterminate:
            self._indeterminate = False
            self._gauge.setRange(0, self._maximum)
        if value > 0 and self._progress_start_time is None:
            self._progress_start_time = time()
        self._progress = value
        self._gauge.setValue(round(value))
        return self._keep_going

    def mark_finished(self, message: str | None = None) -> None:
        """Complete the progress bar and stop the clock.

        Args:
            message (str | None): Optional final status message.
        """
        self.set_progress(self._maximum, message)
        self.stop_clock()
        self.pause_button.setEnabled(False)
        if self.cancel_button is not None:
            self.cancel_button.setEnabled(False)

    # -- pause / cancel -----------------------------------------------------

    def set_paused(self, paused: bool) -> None:
        """Set the paused state and update the pause button label.

        Args:
            paused (bool): The new paused state.
        """
        if paused == self._paused:
            return
        self._paused = paused
        self.pause_button.setText(
            lang.getstr("continue") if paused else lang.getstr("pause")
        )
        # Restart the remaining-time baseline after a pause, as wx does.
        if not paused:
            self._progress_start_time = None
        self.pause_toggled.emit(paused)

    def _on_pause_clicked(self) -> None:
        """Toggle the paused state from the Pause/Continue button."""
        self.set_paused(not self._paused)

    def _on_cancel_clicked(self) -> None:
        """Request cancellation from the Cancel button."""
        self._keep_going = False
        if self.cancel_button is not None:
            self.cancel_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.set_message(lang.getstr("please_wait"))
        self.cancelled.emit()

    # -- clock --------------------------------------------------------------

    def start_clock(self) -> None:
        """Start the one-second elapsed / remaining clock."""
        if not self._clock.isActive():
            self._clock.start()

    def stop_clock(self) -> None:
        """Stop the elapsed / remaining clock."""
        self._clock.stop()

    def _update_times(self) -> None:
        """Refresh the elapsed and estimated-remaining read-outs."""
        elapsed = time() - self._start_time
        self._elapsed_label.setText(
            f"{lang.getstr('elapsed_time')} {format_elapsed(elapsed)}"
        )
        if self._remaining_label is None or self._indeterminate or self._paused:
            return
        if self._progress_start_time is None:
            return
        remaining = estimate_remaining(
            time() - self._progress_start_time, self._progress, self._maximum
        )
        if remaining is not None:
            self._remaining_label.setText(
                f"{lang.getstr('remaining_time')} {format_elapsed(remaining)}"
            )

    # -- geometry -----------------------------------------------------------

    def place(self) -> None:
        """Position the dialog: centred on the parent, else last saved spot."""
        parent = self.parent()
        if parent is not None and parent.isVisible():
            geo = parent.frameGeometry()
            self.move(geo.center() - self.rect().center())
            return
        x = config.getcfg("position.progress.x", False)
        y = config.getcfg("position.progress.y", False)
        if x is not None and y is not None:
            self.move(int(x), int(y))

    def moveEvent(self, event: QMoveEvent) -> None:  # noqa: N802
        """Persist the dialog position to the shared config keys.

        Args:
            event (QMoveEvent): The Qt move event.
        """
        if self.isVisible():
            pos = self.pos()
            config.setcfg("position.progress.x", pos.x())
            config.setcfg("position.progress.y", pos.y())
        super().moveEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Stop the clock when the dialog closes.

        Args:
            event (QCloseEvent): The Qt close event.
        """
        self.stop_clock()
        super().closeEvent(event)
