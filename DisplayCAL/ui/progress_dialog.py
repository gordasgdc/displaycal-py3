"""Native Qt progress dialog for long-running worker operations.

Qt successor to :class:`DisplayCAL.wx_windows.ProgressDialog` (see
``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``, Stage 5 -- the worker execution
layer). It reproduces the wx dialog's "fancy" presentation -- the dark
theme, the animated shutter/patch throbber (:mod:`.progress_widgets`,
porting wx ``AnimatedBitmap`` / ``get_bitmaps``) and the thin
colour-cycling gauge (porting wx ``BetterPyGauge``) -- since those are the
visible chrome users compare against the wx dialog. Looping sound effects
(``audio.Sound``) and Windows taskbar-progress integration are not visual
and remain out of scope.

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

from qtpy.QtCore import QSize, Qt, QTimer, Signal
from qtpy.QtGui import QFontMetrics, QIcon
from qtpy.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui.progress_widgets import (
    AnimatedBitmap,
    GradientGauge,
    get_progress_bitmaps,
)

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent, QMoveEvent
    from qtpy.QtWidgets import QWidget

# Placeholder shown for elapsed / remaining time before an estimate exists,
# matching the wx dialog's ``REMAINING_TIME_LABEL``.
TIME_UNKNOWN = "--:--:--"

# Dark theme, lifted from DisplayCAL.wx_windows.ProgressDialog.__init__
# (self.BackgroundColour = "#141414" / self.ForegroundColour = "#FFFFFF").
_STYLESHEET = """
QDialog#progressdialog {
    background-color: #141414;
}
QDialog#progressdialog QLabel {
    color: #FFFFFF;
    background: transparent;
}
QDialog#progressdialog QPushButton {
    color: #FFFFFF;
    background-color: #222222;
    border: none;
    border-radius: 3px;
    padding: 5px 14px;
}
QDialog#progressdialog QPushButton:hover {
    background-color: #333333;
}
QDialog#progressdialog QPushButton:pressed {
    background-color: #111111;
}
QDialog#progressdialog QPushButton:disabled {
    color: #777777;
    background-color: #1a1a1a;
}
QDialog#progressdialog QPushButton#soundButton {
    padding: 0px;
}
"""

# Fade timing for switching between animation/sound "progress types", keyed
# by the type being faded *out* of. Matches
# DisplayCAL.wx_windows.ProgressDialog.set_progress_type.
_FADE_DELAY_MS = {0: 4000, 1: 500, 2: 2000}


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
        self.setStyleSheet(_STYLESHEET)

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
        # 0 = processing, 1 = measuring, 2 = generating test patches; drives
        # which throbber animation plays. Matches wx ``progress_type``.
        self.progress_type = 0

        outer = QHBoxLayout(self)
        self.animbmp = AnimatedBitmap(self)
        outer.addWidget(self.animbmp, 0, Qt.AlignmentFlag.AlignVCenter)

        layout = QVBoxLayout()
        outer.addLayout(layout, 1)

        self._message = QLabel(message or lang.getstr("please_wait"))
        self._message.setWordWrap(True)
        self._message.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        # Reserve space for 4 lines of ~80 characters, matching wx's own
        # sizing trick (``self.msg.Label = "\n".join(["E" * 80] * 4)``) so
        # the dialog doesn't start out narrower than the wx one.
        metrics = QFontMetrics(self._message.font())
        self._message.setMinimumSize(
            metrics.horizontalAdvance("E" * 80), metrics.height() * 4
        )
        layout.addWidget(self._message)

        self._gauge = GradientGauge()
        layout.addWidget(self._gauge)

        # Two label+value rows in a grid, matching the wx dialog's
        # ``wx.FlexGridSizer(0, 2, 0, margin)`` (stacked, not side by side).
        time_grid = QGridLayout()
        time_grid.setColumnStretch(1, 1)
        time_grid.addWidget(QLabel(lang.getstr("elapsed_time")), 0, 0)
        self._elapsed_label = QLabel(TIME_UNKNOWN)
        time_grid.addWidget(self._elapsed_label, 0, 1, Qt.AlignmentFlag.AlignLeft)
        if show_remaining_time:
            time_grid.addWidget(QLabel(lang.getstr("remaining_time")), 1, 0)
            self._remaining_label = QLabel(TIME_UNKNOWN)
            time_grid.addWidget(
                self._remaining_label, 1, 1, Qt.AlignmentFlag.AlignLeft
            )
        else:
            self._remaining_label = None
        layout.addLayout(time_grid)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.sound_on_off_btn = QPushButton()
        self.sound_on_off_btn.setObjectName("soundButton")
        self.sound_on_off_btn.setIcon(self._sound_icon())
        self.sound_on_off_btn.setIconSize(QSize(16, 16))
        self.sound_on_off_btn.setFixedSize(28, 28)
        self.sound_on_off_btn.clicked.connect(self._on_sound_toggle)
        button_row.addWidget(self.sound_on_off_btn)
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
        self._elapsed_label.setText(format_elapsed(0))
        if self._remaining_label is not None:
            self._remaining_label.setText(TIME_UNKNOWN)

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
                self._remaining_label.setText(TIME_UNKNOWN)
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

    # -- sound ----------------------------------------------------------------

    def _sound_icon(self) -> QIcon:
        """The speaker icon matching the current ``measurement.play_sound`` state."""
        name = (
            "sound_volume_full"
            if config.getcfg("measurement.play_sound")
            else "sound_off"
        )
        path = config.get_data_path(f"theme/icons/16x16/{name}.png")
        return QIcon(path) if path else QIcon()

    def _on_sound_toggle(self) -> None:
        """Toggle ``measurement.play_sound``, mirroring wx ``play_sound_handler``.

        This only flips the shared config flag and the button icon: the
        actual per-patch ``commit_sound`` / ``measurement_sound`` playback
        lives in the toolkit-neutral ``Worker.audio_visual_feedback``
        (``DisplayCAL/worker.py``), which reads this same config value fresh
        on every patch read.
        """
        config.setcfg(
            "measurement.play_sound",
            int(not config.getcfg("measurement.play_sound")),
        )
        self.sound_on_off_btn.setIcon(self._sound_icon())

    # -- clock --------------------------------------------------------------

    def start_clock(self) -> None:
        """Start the one-second elapsed / remaining clock and the throbber."""
        if not self._clock.isActive():
            self._clock.start()
        self.anim_fadein()

    def stop_clock(self) -> None:
        """Stop the elapsed / remaining clock and the throbber."""
        self._clock.stop()
        self.animbmp.stop()

    # -- throbber animation ---------------------------------------------------

    def anim_fadein(self) -> None:
        """(Re)start the throbber animation for the current progress type.

        Ports wx ``ProgressDialog.anim_fadein``: each progress type loops a
        different frame range of its animation (see :mod:`.progress_widgets`).
        """
        bitmaps = get_progress_bitmaps(self.progress_type)
        if self.progress_type == 1:
            frame_range, loop = (0, 9), False  # Measuring: shutter open/close.
        elif self.progress_type == 2:
            frame_range, loop = (27, 36), True  # Generating test patches.
        else:
            frame_range, loop = (60, 68), True  # Processing (no assets; blank).
        self.animbmp.set_bitmaps(bitmaps, range_=frame_range, loop=loop)
        if self.progress_type == 1:
            self.animbmp.frame = 4
        QTimer.singleShot(50, self._play_animbmp)

    def _play_animbmp(self) -> None:
        """Start playback if the dialog is still shown (wx ``CallLater`` guard)."""
        if self.isVisible():
            self.animbmp.play(24)

    def anim_fadeout(self) -> None:
        """Let the throbber play out to its last frame instead of looping."""
        self.animbmp.loop = False
        self.animbmp.range = (self.animbmp.range[0], -1)

    def on_patch_read(self) -> None:
        """Replay the shutter's open/close blink for a newly read patch.

        Ports wx's ``Worker.audio_visual_feedback`` resetting
        ``progress_wnd.animbmp.frame = 0`` on every "Patch N of M" line: the
        throbber's 24fps timer keeps running for the whole "measuring" phase
        (``anim_fadein`` never loops it, but never stops it either), so
        resetting the frame index here is what makes it blink once per patch
        instead of only once when measuring starts. See
        :class:`DisplayCAL.ui.worker_runner.ProgressAdapter` for how this
        reaches the GUI thread from the worker thread.
        """
        self.animbmp.frame = 0

    def set_progress_type(self, progress_type: int) -> None:
        """Switch the throbber animation (and eventually sound) type.

        Args:
            progress_type (int): 0 (processing), 1 (measuring) or 2
                (generating test patches).
        """
        if progress_type == self.progress_type:
            return
        delay = _FADE_DELAY_MS.get(self.progress_type, 2000)
        self.anim_fadeout()
        self.progress_type = progress_type

        def _maybe_fade_in() -> None:
            if self.isVisible() and self.progress_type == progress_type:
                self.anim_fadein()

        QTimer.singleShot(delay, _maybe_fade_in)

    def _update_times(self) -> None:
        """Refresh the elapsed and estimated-remaining read-outs."""
        elapsed = time() - self._start_time
        self._elapsed_label.setText(format_elapsed(elapsed))
        if self._remaining_label is None or self._indeterminate or self._paused:
            return
        if self._progress_start_time is None:
            return
        remaining = estimate_remaining(
            time() - self._progress_start_time, self._progress, self._maximum
        )
        if remaining is not None:
            self._remaining_label.setText(format_elapsed(remaining))

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
