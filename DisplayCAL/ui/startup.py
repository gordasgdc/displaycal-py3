"""Qt port of the splash screen (``display_cal.StartupFrame``, Stage 6).

The wx ``StartupFrame`` shows an animated splash screen while
:meth:`~DisplayCAL.worker.Worker.enumerate_displays_and_ports` runs on a
background thread (via ``delayedresult``), then builds ``MainFrame`` around
the now-populated worker. This module is the Qt equivalent:
:class:`StartupController` shows a :class:`QSplashScreen` and drives it with
:class:`_SplashAnimator` (the icon-reveal / version-number-fade animation,
composed frame by frame onto the splash pixmap) while :class:`_EnumerateThread`
runs the same enumeration on a background ``QThread``. The two run
concurrently rather than the wx serial animation-then-enumerate order; the
populated :class:`~DisplayCAL.worker.Worker` is handed to a callback (see
:func:`main`) once *both* finish, so the splash is never up for less time than
the animation takes even when enumeration is near-instant.

**Dropped versus the wx splash** (Qt natively supports translucent PNG
windows, so none of this is needed): the desktop screenshot grabbed from
behind the shaped window (``grab_image`` / the macOS ``screencapture`` and
Wayland ``gnome-screenshot``/``spectacle`` paths and their gamma-correction),
and reapplying the base bitmap's alpha channel / blurring after each zoom
frame (Qt's ``QImage`` keeps alpha through scaling natively; the blur radius
in the wx version was sub-pixel anyway).

**Deferred to later integration** (Pile 2 dialogs not yet ported): the
update-check prompt and the instrument-setup/donation nag that wx runs after
the main window appears.
"""

from __future__ import annotations

import sys
import traceback
from typing import Callable

from qtpy.QtCore import QObject, QRect, Qt, QThread, QTimer, Signal
from qtpy.QtGui import QColor, QPainter, QPixmap
from qtpy.QtWidgets import QSplashScreen

from DisplayCAL import audio, colormath, config
from DisplayCAL import localization as lang
from DisplayCAL.config import getcfg, hascfg
from DisplayCAL.options import FORCE_SKIP_INITIAL_INSTRUMENT_DETECTION
from DisplayCAL.worker import Worker

#: Fade steps for the version-number overlay (``StartupFrame``'s
#: ``splash_version_anim``): builds to full opacity, then settles slightly.
_VERSION_ALPHAS = (0, 0.2, 0.4, 0.6, 0.8, 1, 0.95, 0.9, 0.85, 0.8, 0.75)

#: Interval between icon-reveal / version-fade frames (``1000 / 30`` fps).
_FRAME_INTERVAL_MS = round(1000 / 30.0)


def splash_pixmap() -> QPixmap:
    """Return the configured splash image as a ``QPixmap``.

    Mirrors ``StartupFrame``'s ``splash.simple`` config switch between the
    plain and illustrated splash images.

    Returns:
        QPixmap: The splash bitmap, or a null pixmap if the asset is missing.
    """
    name = "theme/splash-simple.png" if getcfg("splash.simple") else "theme/splash.png"
    path = config.get_data_path(name)
    return QPixmap(path) if path else QPixmap()


def welcome_message() -> str:
    """Return the initial splash status message.

    Mirrors ``StartupFrame.__init__``'s welcome-back-vs-first-run text.

    Returns:
        str: The localized two-line startup message.
    """
    return "\n".join(
        [
            lang.getstr("welcome_back" if hascfg("recent_cals") else "welcome"),
            lang.getstr("startup"),
        ]
    )


def should_enumerate_ports() -> bool:
    """Return whether instrument (comport) enumeration should run.

    Mirrors the ``enumerate_ports`` kwarg ``StartupFrame.startup`` passes to
    ``enumerate_displays_and_ports``: skipped only when explicitly forced off,
    otherwise run whenever auto-enumeration is configured or the instrument
    list is empty or ambiguous (more than one candidate).

    Returns:
        bool: True if port enumeration should run.
    """
    if FORCE_SKIP_INITIAL_INSTRUMENT_DETECTION:
        return False
    inst_count = len(getcfg("instruments"))
    return bool(getcfg("enumerate_ports.auto") or not inst_count or inst_count > 1)


def load_anim_frames() -> list[QPixmap]:
    """Load the icon-reveal animation frames (``theme/splash_anim_unpremultiplied``).

    Returns:
        list[QPixmap]: The frames in playback order (empty if missing).
    """
    paths = config.get_data_path("theme/splash_anim", r"\.png$") or []
    frames = []
    for path in paths:
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            frames.append(pixmap)
    return frames


def load_version_frames() -> list[QPixmap]:
    """Build the fading-in version-number overlay frames.

    Mirrors ``StartupFrame.__init__``'s ``splash_version_anim``: the same
    ``theme/splash_version`` bitmap rendered at each of :data:`_VERSION_ALPHAS`.

    Returns:
        list[QPixmap]: The alpha-faded frames (empty if the asset is missing).
    """
    path = config.get_data_path("theme/splash_version.png")
    base = QPixmap(path) if path else QPixmap()
    if base.isNull():
        return []
    frames = []
    for alpha in _VERSION_ALPHAS:
        frame = QPixmap(base.size())
        frame.fill(Qt.transparent)
        painter = QPainter(frame)
        painter.setOpacity(alpha)
        painter.drawPixmap(0, 0, base)
        painter.end()
        frames.append(frame)
    return frames


def zoom_scales() -> list[float]:
    """Return the "zoom in" scale-per-frame curve (``splash.zoom`` option).

    Mirrors ``StartupFrame.__init__``'s ``zoom_scales`` (a 15-step ease-out
    curve via :func:`~DisplayCAL.colormath.special_pow`, then a small 1.02
    overshoot settling back to 1.0), minus the wx ``minv`` floor (at most a
    sub-pixel offset for realistic splash sizes, so dropping it is invisible).

    Returns:
        list[float]: Scale factors, one per zoom frame, ending at ``1.0``.
    """
    numframes = 15
    scales = [
        colormath.special_pow(0.35 + x / (numframes - 1.0) * 0.65, -2084)
        for x in range(numframes)
    ]
    scales.append(1.02)
    scales.append(1.0)
    return scales


def play_startup_sound() -> None:
    """Play the startup sound if ``startup_sound.enable`` is set.

    Mirrors ``StartupFrame.__init__``'s startup-sound block verbatim (needs a
    stereo file).
    """
    if not getcfg("startup_sound.enable"):
        return
    audio.safe_init()
    if audio._LIB:  # noqa: SLF001  (module-level state, no public accessor)
        print(lang.getstr("audio.lib", f"{audio._LIB} {audio._LIB_VERSION}"))  # noqa: SLF001
    path = config.get_data_path("theme/intro_new.wav")
    if not path:
        return
    sound = audio.Sound(path)
    sound.volume = 0.8
    sound.safe_play()


class _EnumerateThread(QThread):
    """Run :meth:`Worker.enumerate_displays_and_ports` off the GUI thread.

    Args:
        worker (Worker): The worker to enumerate on.
        enumerate_ports (bool): Whether to also enumerate instrument ports.
        parent (QObject | None): Optional Qt parent.
    """

    #: Emitted with ``None`` on success or the caught ``Exception`` on failure.
    done = Signal(object)

    def __init__(
        self, worker: Worker, enumerate_ports: bool, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._enumerate_ports = enumerate_ports

    def run(self) -> None:
        """Run the enumeration and emit the result."""
        try:
            self._worker.enumerate_displays_and_ports(
                enumerate_ports=self._enumerate_ports, silent=True
            )
        except Exception as exception:  # noqa: BLE001  (reported on GUI thread)
            self.done.emit(exception)
        else:
            self.done.emit(None)


def _draw_embossed_message(painter: QPainter, w: int, h: int, message: str) -> None:
    """Draw the status message with wx's raised/embossed text style.

    Mirrors ``StartupFrame.Draw``'s three-pass label draw (a dark shadow,
    then black, then light gray drawn last on top): wx never actually shows
    solid black text, the topmost and most visible layer is light gray, with
    a subtle dark bevel underneath it for contrast against both the lighter
    and darker regions of the splash image.

    Args:
        painter (QPainter): The active painter to draw into.
        w (int): The splash pixmap width.
        h (int): The splash pixmap height.
        message (str): The (possibly multi-line) status message.
    """
    rect = QRect(0, round(h * 0.75), w, 40)
    align = int(Qt.AlignHCenter | Qt.AlignTop)
    for color, dy in (("#101010", 2), ("#000000", 1), ("#CCCCCC", 0)):
        painter.setPen(QColor(color))
        painter.drawText(rect.translated(0, dy), align, message)


class _SplashAnimator(QObject):
    """Drive the splash-screen icon-reveal / version-fade animation.

    Qt port of ``StartupFrame.startup``/``Draw``: each tick composes the base
    splash bitmap, the current icon-reveal frame and (once the icon has fully
    revealed) the fading-in version-number overlay onto one ``QPixmap`` and
    pushes it to the ``QSplashScreen`` via ``setPixmap`` (which clears any
    current message, so the status message is re-applied every frame).

    Args:
        splash (QSplashScreen): The splash screen to animate.
        message (str): The status message to keep showing during playback.
    """

    def __init__(self, splash: QSplashScreen, message: str) -> None:
        super().__init__()
        self._splash = splash
        self._message = message
        self._base = splash_pixmap()
        self._anim_frames = load_anim_frames()
        self._version_frames = load_version_frames()
        self._zoom_scales = zoom_scales() if getcfg("splash.zoom") else []
        self._frame = 0
        self._total = (
            len(self._zoom_scales) + len(self._anim_frames) + len(self._version_frames)
        )
        self._on_finished: Callable[[], None] | None = None

    def start(self, on_finished: Callable[[], None]) -> None:
        """Start playback, calling ``on_finished`` once all frames are shown.

        Args:
            on_finished (Callable[[], None]): Called on the GUI thread when
                the animation completes (immediately if there is nothing to
                animate, e.g. the splash asset is missing).
        """
        self._on_finished = on_finished
        if self._base.isNull() or self._total == 0:
            on_finished()
            return
        self._advance()

    def _advance(self) -> None:
        self._render_frame(self._frame)
        self._frame += 1
        if self._frame >= self._total:
            self._on_finished()
            return
        interval = 1 if self._frame < len(self._zoom_scales) else _FRAME_INTERVAL_MS
        QTimer.singleShot(interval, self._advance)

    def _render_frame(self, index: int) -> None:
        w, h = self._base.width(), self._base.height()
        composite = QPixmap(self._base.size())
        composite.fill(Qt.transparent)
        painter = QPainter(composite)
        painter.drawPixmap(0, 0, self._base)
        if index < len(self._zoom_scales):
            if self._anim_frames:
                painter.drawPixmap(0, 0, self._anim_frames[0])
            _draw_embossed_message(painter, w, h, self._message)
            painter.end()
            scale = self._zoom_scales[index]
            scaled = composite.scaled(
                max(1, round(w * scale)),
                max(1, round(h * scale)),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            frame_pixmap = QPixmap(composite.size())
            frame_pixmap.fill(Qt.transparent)
            zoom_painter = QPainter(frame_pixmap)
            zoom_painter.drawPixmap(
                round(w / 2 - scaled.width() / 2),
                round(h / 2 - scaled.height() / 2),
                scaled,
            )
            zoom_painter.end()
        else:
            if self._anim_frames:
                anim_index = min(
                    index - len(self._zoom_scales), len(self._anim_frames) - 1
                )
                painter.drawPixmap(0, 0, self._anim_frames[anim_index])
            version_index = index - len(self._zoom_scales) - len(self._anim_frames)
            if 0 <= version_index < len(self._version_frames):
                painter.drawPixmap(0, 0, self._version_frames[version_index])
            _draw_embossed_message(painter, w, h, self._message)
            painter.end()
            frame_pixmap = composite
        self._splash.setPixmap(frame_pixmap)


class StartupController(QObject):
    """Show the animated splash screen while enumerating displays/instruments.

    Args:
        on_ready (Callable[[Worker], None]): Called on the GUI thread once
            both enumeration and the splash animation finish (matching the wx
            behaviour of always proceeding to the main window, regardless of
            whether enumeration raised). Receives the now-populated worker.
        worker (Worker | None): The worker to enumerate on; a fresh one is
            created if not given.
    """

    #: Kill the enumeration subprocess if it hangs this long (matches wx's
    #: ``wx.CallLater(20000, self.worker.abort_subprocess)``).
    _timeout_ms = 20000

    #: Extra time to hold the splash up once animation + enumeration finish.
    _hold_ms = 1000

    def __init__(
        self,
        on_ready: Callable[[Worker], None],
        worker: Worker | None = None,
    ) -> None:
        super().__init__()
        self.worker = worker if worker is not None else Worker()
        self._on_ready = on_ready
        self.splash = QSplashScreen(
            splash_pixmap(), Qt.WindowStaysOnTopHint | Qt.SplashScreen
        )
        # Requires the splash/anim/version PNGs to carry a correctly
        # premultiplied alpha channel (no baked-in matte on the antialiased
        # edges); otherwise the edge pixels' matte color shows through as a
        # fringe against the real desktop.
        self.splash.setAttribute(Qt.WA_TranslucentBackground)
        self._animator = _SplashAnimator(self.splash, welcome_message())
        self._thread: _EnumerateThread | None = None
        self._enum_done = False
        self._enum_error: Exception | None = None
        self._anim_done = False
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self.worker.abort_subprocess)

    def start(self) -> None:
        """Show the splash screen and start the animation + enumeration."""
        self.splash.show()
        self.splash.raise_()
        self.splash.activateWindow()
        play_startup_sound()
        self._timeout_timer.start(self._timeout_ms)
        self._thread = _EnumerateThread(self.worker, should_enumerate_ports(), self)
        self._thread.done.connect(self._on_enum_done)
        self._thread.start()
        self._animator.start(self._on_anim_done)

    def _on_enum_done(self, error: Exception | None) -> None:
        self._timeout_timer.stop()
        self._enum_done = True
        self._enum_error = error
        self._maybe_finish()

    def _on_anim_done(self) -> None:
        self._anim_done = True
        self._maybe_finish()

    def _maybe_finish(self) -> None:
        if not (self._enum_done and self._anim_done):
            return
        if self._enum_error is not None:
            traceback.print_exception(
                type(self._enum_error), self._enum_error, self._enum_error.__traceback__
            )
        QTimer.singleShot(self._hold_ms, lambda: self._on_ready(self.worker))


def main() -> int:
    """Run the Qt application: splash screen, then the main window.

    Returns:
        int: The Qt application exit code.
    """
    config.initcfg()
    lang.init()
    lang.update_defaults()

    from DisplayCAL.ui.application import Application
    from DisplayCAL.ui.main_window import MainWindow

    app = Application(sys.argv)

    def _on_ready(worker: Worker) -> None:
        window = MainWindow(worker=worker)
        app.top_window = window
        window.show()
        window.listen()
        app.process_argv()
        controller.splash.finish(window)

    controller = StartupController(_on_ready)
    app.top_window = controller.splash
    controller.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
