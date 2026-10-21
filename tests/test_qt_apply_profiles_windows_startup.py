"""Tests for the Windows start-up of the Qt apply-profiles loader.

The wx loader prepares the GDI gamma-ramp API in ``setup_taskbar_icon`` before
its display monitoring thread starts. The inherited code that applies the
calibration curves (``self.gdi32.SetDeviceGammaRamp``) depends on it, so the Qt
``_setup_ui`` has to prepare it as well, or the monitoring thread dies with
``AttributeError: 'QtProfileLoader' object has no attribute 'gdi32'`` the first
time it tries to apply a profile.
"""

import ctypes
import os
import types
from unittest import mock

import pytest

from DisplayCAL import config

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL.ui.tools import apply_profiles  # noqa: E402
from DisplayCAL.ui.tools.apply_profiles import QtProfileLoader  # noqa: E402


@pytest.fixture(autouse=True)
def _init_config():
    config.initcfg()
    yield


class _FakeGdi32:
    """Stands in for ``ctypes.windll.gdi32``."""

    def __init__(self):
        self.GetDeviceGammaRamp = types.SimpleNamespace(restype=None)
        self.SetDeviceGammaRamp = types.SimpleNamespace(restype=None)


class _RecordingThread:
    """Records the loader state at the moment the monitoring thread starts."""

    owner = None
    gdi32_when_started = "not started"

    def __init__(self, target=None, name=None):
        pass

    def start(self):
        _RecordingThread.gdi32_when_started = getattr(
            _RecordingThread.owner, "gdi32", "missing"
        )


def _windows_loader(monkeypatch, windll):
    """Build a loader and run its Windows ``_setup_ui`` against ``windll``."""
    monkeypatch.setattr(apply_profiles.sys, "platform", "win32")
    monkeypatch.setattr(
        apply_profiles.QSystemTrayIcon,
        "isSystemTrayAvailable",
        staticmethod(lambda: False),
    )
    monkeypatch.setattr(apply_profiles, "_ScriptingHost", lambda pl: mock.Mock())
    monkeypatch.setattr(apply_profiles.threading, "Thread", _RecordingThread)
    monkeypatch.setattr(ctypes, "windll", windll, raising=False)
    pl = QtProfileLoader.__new__(QtProfileLoader)
    pl._skip = False
    _RecordingThread.owner = pl
    _RecordingThread.gdi32_when_started = "not started"
    pl._setup_ui()
    return pl


def test_windows_setup_prepares_gdi32_before_monitoring_starts(qapp, monkeypatch):
    gdi32 = _FakeGdi32()

    pl = _windows_loader(monkeypatch, types.SimpleNamespace(gdi32=gdi32))

    assert pl.gdi32 is gdi32
    assert _RecordingThread.gdi32_when_started is gdi32
    assert gdi32.GetDeviceGammaRamp.restype is ctypes.c_bool
    assert gdi32.SetDeviceGammaRamp.restype is ctypes.c_bool


def test_windows_setup_without_gdi32_still_starts_monitoring(qapp, monkeypatch):
    pl = _windows_loader(monkeypatch, types.SimpleNamespace())

    assert pl.gdi32 is None
    assert _RecordingThread.gdi32_when_started is None


def test_window_enumeration_for_the_monitoring_thread_never_touches_qt_widgets(
    qapp, monkeypatch
):
    """``_check_keep_running`` runs on the monitoring thread.

    Qt widgets must only be touched on the GUI thread; calling
    ``QApplication.topLevelWidgets`` from the monitoring thread while the tray
    menu is rebuilt there made the loader exit when the menu was opened.
    """
    import threading

    pl = QtProfileLoader.__new__(QtProfileLoader)
    pl._refresh_own_windows()
    calls = []

    class _StubApp:
        @staticmethod
        def instance():
            return _StubApp

        @staticmethod
        def topLevelWidgets():
            calls.append(threading.current_thread())
            return []

    monkeypatch.setattr(apply_profiles, "QApplication", _StubApp)
    result = []

    worker = threading.Thread(
        target=lambda: result.append(pl._enumerate_own_top_level_windows())
    )
    worker.start()
    worker.join()

    assert calls == []
    assert isinstance(result[0], list)


def test_refresh_keeps_only_real_windows(qapp):
    from qtpy.QtWidgets import QDialog, QMenu, QWidget

    pl = QtProfileLoader.__new__(QtProfileLoader)
    window, dialog, menu = QWidget(), QDialog(), QMenu()
    try:
        pl._refresh_own_windows()
        windows = pl._enumerate_own_top_level_windows()
        assert window in windows
        assert dialog not in windows
        assert menu not in windows
    finally:
        for widget in (window, dialog, menu):
            widget.deleteLater()
        qapp.processEvents()
