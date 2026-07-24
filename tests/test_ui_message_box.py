"""Tests for the macOS-safe ``QMessageBox`` wrappers ``DisplayCAL.ui.message_box``.

See the module docstring for why these wrappers exist: on macOS, Qt renders
``QMessageBox``'s static convenience methods (and any manually constructed
instance) through a native ``NSAlert``-backed style that drops the window
title, bleeds the parent window through translucent corners, and shows the
app's dock icon instead of a warning/question/critical/info glyph. These
tests exercise the ``AA_DontUseNativeDialogs`` toggle in isolation (mocking
``QMessageBox`` itself so no real dialog ever shows) rather than the visual
outcome, which was verified live instead (see the ``7-move-the-ui-to-qt``
punch list).
"""

import os

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from qtpy.QtCore import Qt  # noqa: E402
from qtpy.QtWidgets import QApplication, QMessageBox  # noqa: E402

from DisplayCAL.ui import message_box  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _reset_attribute(qapp):
    """Ensure the attribute starts and ends unset, regardless of test outcome."""
    QApplication.setAttribute(Qt.AA_DontUseNativeDialogs, False)
    yield
    QApplication.setAttribute(Qt.AA_DontUseNativeDialogs, False)


@pytest.mark.parametrize("name", ["warning", "question", "critical", "information"])
def test_wrapper_forwards_to_qmessagebox(qapp, monkeypatch, name):
    calls = []

    def fake(*args, **kwargs):
        calls.append(QApplication.testAttribute(Qt.AA_DontUseNativeDialogs))
        return QMessageBox.Yes

    monkeypatch.setattr(QMessageBox, name, staticmethod(fake))
    monkeypatch.setattr("sys.platform", "darwin")

    result = getattr(message_box, name)(None, "title", "text")

    assert result == QMessageBox.Yes
    # The attribute was set while QMessageBox's own method ran...
    assert calls == [True]
    # ...and cleared again once the wrapper returned.
    assert QApplication.testAttribute(Qt.AA_DontUseNativeDialogs) is False


def test_wrapper_is_a_noop_toggle_outside_macos(qapp, monkeypatch):
    calls = []

    def fake(*args, **kwargs):
        calls.append(QApplication.testAttribute(Qt.AA_DontUseNativeDialogs))
        return QMessageBox.Ok

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(fake))
    monkeypatch.setattr("sys.platform", "win32")

    message_box.warning(None, "title", "text")

    # Never toggled on a platform where QMessageBox isn't natively re-skinned.
    assert calls == [False]


def test_exec_box_prefers_exec__alias(qapp, monkeypatch):
    """A fake with both ``exec`` and ``exec_`` should use ``exec_``.

    Several existing tests monkeypatch only ``QMessageBox.exec_`` on the real
    class, leaving the real (native) ``exec`` untouched -- preferring ``exec``
    would silently skip the patched hook and pop a real, hanging modal
    dialog.
    """
    calls = []

    class _Box:
        def exec(self):
            calls.append("exec")
            return 1

        def exec_(self):
            calls.append("exec_")
            return 2

    monkeypatch.setattr("sys.platform", "darwin")
    result = message_box.exec_box(_Box())

    assert calls == ["exec_"]
    assert result == 2


def test_exec_box_falls_back_to_exec(qapp, monkeypatch):
    calls = []

    class _Box:
        def exec(self):
            calls.append("exec")
            return 1

    monkeypatch.setattr("sys.platform", "darwin")
    result = message_box.exec_box(_Box())

    assert calls == ["exec"]
    assert result == 1
