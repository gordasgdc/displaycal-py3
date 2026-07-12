"""Qt application object for DisplayCAL.

Successor to :class:`DisplayCAL.wx_windows.BaseApp`. It keeps the parts of the
wx app that are genuinely useful and binding-agnostic:

* LIFO exit handlers that run *before* the event loop tears down, so cleanup
  still happens on OS logout/shutdown (wx needed elaborate session-end plumbing
  for this; Qt gives us ``aboutToQuit``).
* ``sys.argv`` file handling and macOS "open file(s) with app" support, routed
  to the top window's :class:`~DisplayCAL.ui.file_drop.FileDropTarget`.
* A SIGINT handler so Ctrl+C closes the app cleanly from a terminal (Qt's event
  loop otherwise swallows Python signals until the next UI event).
"""

from __future__ import annotations

import os
import signal
import sys
import traceback
from typing import Callable, ClassVar

from qtpy.QtCore import QEvent, QTimer
from qtpy.QtWidgets import QApplication

from DisplayCAL.config import PYNAME


class Application(QApplication):
    """DisplayCAL's ``QApplication`` with shared lifecycle helpers.

    Args:
        argv (list[str] | None): Command-line arguments; defaults to
            ``sys.argv``.
        install_sigint (bool): Install a SIGINT handler so Ctrl+C quits cleanly.
    """

    _exithandlers: ClassVar[list[tuple[Callable, tuple, dict]]] = []

    def __init__(
        self, argv: list[str] | None = None, install_sigint: bool = True
    ) -> None:
        super().__init__(argv if argv is not None else sys.argv)
        self.setApplicationName(PYNAME)
        # Install the DisplayCAL palette/font (wx-style, keyed on OS theme).
        from DisplayCAL.ui.theme import apply_theme

        apply_theme(self)
        #: The primary window; set by the tool/frame that owns the app.
        self.top_window = None
        self.aboutToQuit.connect(self._run_exitfuncs)

        # Re-theme live when the OS switches light/dark mode. Qt does not do
        # this on its own -- apply_theme() only ran once, above -- and wx's
        # MainFrame never had to handle it either (it read
        # wx.SystemSettings.GetColour() fresh on every paint). colorScheme()/
        # colorSchemeChanged only exist from Qt 6.5, hence the guard;
        # older Qt just keeps the palette it launched with.
        color_scheme_changed = getattr(self.styleHints(), "colorSchemeChanged", None)
        if color_scheme_changed is not None:
            color_scheme_changed.connect(self._on_color_scheme_changed)

    def _on_color_scheme_changed(self, _scheme: object) -> None:
        """Reapply the theme when the OS light/dark preference changes.

        Args:
            _scheme (Qt.ColorScheme): The new scheme (unused; :func:`apply_theme`
                re-detects it via :func:`~DisplayCAL.ui.theme.is_dark`).
        """
        from DisplayCAL.ui.theme import apply_theme

        apply_theme(self)

        if install_sigint:
            signal.signal(signal.SIGINT, self._signal_handler)
            # Give the Python interpreter a chance to run its signal handlers;
            # without periodic re-entry Qt's C++ loop never yields to Python.
            self._signal_timer = QTimer(self)
            self._signal_timer.timeout.connect(lambda: None)
            self._signal_timer.start(100)

    # -- exit handlers ------------------------------------------------------

    @classmethod
    def register_exitfunc(cls, func: Callable, *args, **kwargs) -> None:
        """Register ``func`` to run on quit (LIFO order).

        Args:
            func (Callable): The callable to run at exit.
            *args: Positional arguments passed to ``func``.
            **kwargs: Keyword arguments passed to ``func``.
        """
        cls._exithandlers.append((func, args, kwargs))

    @classmethod
    def _run_exitfuncs(cls) -> None:
        """Run registered exit handlers, last registered first."""
        while cls._exithandlers:
            func, args, kwargs = cls._exithandlers.pop()
            try:
                func(*args, **kwargs)
            except Exception:  # noqa: BLE001  (mirror wx behaviour: never abort cleanup)
                print("Error in Application exit handler:")
                print(traceback.format_exc())

    # -- file opening -------------------------------------------------------

    def _deliver_paths(self, paths: list[str]) -> None:
        """Hand dropped/opened ``paths`` to the top window's drop target.

        Args:
            paths (list[str]): File paths to deliver to the top window.
        """
        target = getattr(self.top_window, "droptarget", None)
        if target is not None and paths:
            target.drop_files(paths)

    def process_argv(self, count: int = 0) -> list[str] | None:
        """Open any file paths passed on the command line.

        Args:
            count (int): Stop after this many files (0 = all).

        Returns:
            list[str] | None: The list of opened paths, or ``None`` if there
            were none.
        """
        paths: list[str] = []
        for arg in sys.argv[1:]:
            if os.path.isfile(arg):
                paths.append(str(arg))
                if len(paths) == count:
                    break
        if paths:
            self._deliver_paths(paths)
            return paths
        return None

    def event(self, event: QEvent) -> bool:
        """Handle macOS "open file/URL with this app" events.

        Args:
            event (QEvent): The Qt event to handle.

        Returns:
            bool: True if a file-open event was handled, otherwise the result of
            the base-class handler.
        """
        if event.type() == QEvent.FileOpen:
            path = event.file() or event.url().toLocalFile()
            if path:
                self._deliver_paths([path])
                return True
        return super().event(event)

    # -- signals ------------------------------------------------------------

    def _signal_handler(self, signum: int, frame: object) -> None:
        """Quit the application cleanly on SIGINT.

        Args:
            signum (int): The signal number received.
            frame (object): The current stack frame (unused).
        """
        if signum == signal.SIGINT:
            print("Received SIGINT")
            self.quit()
