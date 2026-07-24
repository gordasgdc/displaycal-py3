"""macOS-safe wrappers around :class:`QMessageBox`.

On macOS, Qt renders ``QMessageBox.warning``/``question``/``critical``/
``information`` (and any manually constructed ``QMessageBox``) through a
native ``NSAlert``-backed style: no window title text, a translucent
vibrancy background that bleeds the parent window behind it, and the app's
own dock icon in place of a distinct warning/question/critical/info glyph
(confirmed live -- a real warning-triangle icon only appears once native
rendering is disabled). wx's ``ConfirmDialog`` equivalents are plain,
custom-drawn windows with a full title bar and a real icon, so this native
re-skin is a wx/Qt parity gap that hits every message dialog in the app, not
just one call site.

Toggling ``Qt.AA_DontUseNativeDialogs`` around a single, synchronous
``exec()`` call switches Qt to its own built-in rendering (real title bar,
real icon, opaque background) for that dialog only: the attribute is read
fresh by Qt at ``exec()`` time rather than cached at startup, so scoping the
toggle this tightly leaves every other native dialog alone. That matters
because the same attribute, if set app-wide, also disables native
``QFileDialog``/``QColorDialog``/``QFontDialog`` -- confirmed live: it
replaces the native Finder-integrated Open panel with Qt's plain fallback
file browser (no sidebar, no Quick Look, no search). Not needed on
Windows/Linux, where ``QMessageBox`` was never natively re-skinned to begin
with, so the toggle is a no-op there.
"""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Iterator

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QMessageBox


@contextlib.contextmanager
def _non_native() -> Iterator[None]:
    if sys.platform != "darwin":
        yield
        return
    QApplication.setAttribute(Qt.AA_DontUseNativeDialogs, True)
    try:
        yield
    finally:
        QApplication.setAttribute(Qt.AA_DontUseNativeDialogs, False)


def warning(*args, **kwargs):
    """Wrap :meth:`QMessageBox.warning` (see module docstring)."""
    with _non_native():
        return QMessageBox.warning(*args, **kwargs)


def question(*args, **kwargs):
    """Wrap :meth:`QMessageBox.question` (see module docstring)."""
    with _non_native():
        return QMessageBox.question(*args, **kwargs)


def critical(*args, **kwargs):
    """Wrap :meth:`QMessageBox.critical` (see module docstring)."""
    with _non_native():
        return QMessageBox.critical(*args, **kwargs)


def information(*args, **kwargs):
    """Wrap :meth:`QMessageBox.information` (see module docstring)."""
    with _non_native():
        return QMessageBox.information(*args, **kwargs)


def exec_box(box: QMessageBox):
    """Run a manually constructed ``QMessageBox`` (see module docstring).

    Prefers the ``exec_()`` alias, falling back to ``exec()``: several tests
    substitute a lightweight fake in place of the real ``QMessageBox`` that
    only implements one or the other, and some monkeypatch ``exec_``
    specifically on the real class -- checking ``exec`` first would find the
    real (unpatched) method and silently skip the patched one, popping a
    real modal dialog that hangs the test run.
    """
    method = getattr(box, "exec_", None) or box.exec
    with _non_native():
        return method()
