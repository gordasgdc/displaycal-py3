"""Qt port of the splash screen (``display_cal.StartupFrame``, Stage 6).

The wx ``StartupFrame`` shows a splash screen while
:meth:`~DisplayCAL.worker.Worker.enumerate_displays_and_ports` runs on a
background thread (via ``delayedresult``), then builds ``MainFrame`` around
the now-populated worker and fades the splash out. This module is the Qt
equivalent: :class:`StartupController` shows a :class:`QSplashScreen` while
:class:`_EnumerateThread` runs the same enumeration off the GUI thread, then
hands the populated :class:`~DisplayCAL.worker.Worker` to a callback that
builds :class:`~DisplayCAL.ui.main_window.MainWindow` around it (see
:meth:`MainWindow.__init__`'s ``worker`` parameter).

**Dropped versus the wx splash** (Qt natively supports translucent PNG
windows, so none of this is needed): the desktop screenshot grabbed from
behind the shaped window (``grab_image`` / the macOS ``screencapture`` and
Wayland ``gnome-screenshot``/``spectacle`` paths and their gamma-correction),
the zoom-in/fade animation and frame-by-frame version-number fade, and the
startup sound.

**Deferred to later integration** (Pile 2 dialogs not yet ported): the
update-check prompt and the instrument-setup/donation nag that wx runs after
the main window appears.
"""

from __future__ import annotations

import sys
import time
import traceback
from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import QObject, Qt, QThread, QTimer, Signal
from qtpy.QtWidgets import QSplashScreen

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import getcfg, hascfg
from DisplayCAL.options import FORCE_SKIP_INITIAL_INSTRUMENT_DETECTION
from DisplayCAL.worker import Worker

if TYPE_CHECKING:
    from qtpy.QtGui import QPixmap


def splash_pixmap() -> QPixmap:
    """Return the configured splash image as a ``QPixmap``.

    Mirrors ``StartupFrame``'s ``splash.simple`` config switch between the
    plain and illustrated splash images.

    Returns:
        QPixmap: The splash bitmap, or a null pixmap if the asset is missing.
    """
    from qtpy.QtGui import QPixmap

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


class StartupController(QObject):
    """Show the splash screen while enumerating displays and instruments.

    Args:
        on_ready (Callable[[Worker], None]): Called on the GUI thread once
            enumeration finishes, successfully or not (matching the wx
            behaviour of always proceeding to the main window). Receives the
            now-populated worker.
        worker (Worker | None): The worker to enumerate on; a fresh one is
            created if not given.
    """

    #: Kill the enumeration subprocess if it hangs this long (matches wx's
    #: ``wx.CallLater(20000, self.worker.abort_subprocess)``).
    _timeout_ms = 20000

    #: Minimum time the splash stays visible. Real enumeration can finish in
    #: well under a second, and with the wx zoom/fade animation dropped there
    #: is nothing else holding the splash up, so without a floor it can flash
    #: by too fast to read. Roughly matches how long that animation used to
    #: take before ``enumerate_displays_and_ports`` was even started.
    _min_show_ms = 1200

    def __init__(
        self,
        on_ready: Callable[[Worker], None],
        worker: Worker | None = None,
    ) -> None:
        super().__init__()
        self.worker = worker if worker is not None else Worker()
        self._on_ready = on_ready
        self.splash = QSplashScreen(splash_pixmap())
        self.splash.showMessage(
            welcome_message(), int(Qt.AlignHCenter | Qt.AlignBottom), Qt.black
        )
        self._thread: _EnumerateThread | None = None
        self._start_time = 0.0
        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self.worker.abort_subprocess)

    def start(self) -> None:
        """Show the splash screen and start enumeration in the background."""
        self.splash.show()
        self._start_time = time.monotonic()
        self._timeout_timer.start(self._timeout_ms)
        self._thread = _EnumerateThread(self.worker, should_enumerate_ports(), self)
        self._thread.done.connect(self._on_done)
        self._thread.start()

    def _on_done(self, error: Exception | None) -> None:
        self._timeout_timer.stop()
        if error is not None:
            traceback.print_exception(type(error), error, error.__traceback__)
        elapsed_ms = (time.monotonic() - self._start_time) * 1000
        remaining_ms = self._min_show_ms - elapsed_ms
        if remaining_ms > 0:
            QTimer.singleShot(int(remaining_ms), lambda: self._on_ready(self.worker))
        else:
            self._on_ready(self.worker)


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
