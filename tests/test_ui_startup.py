"""Tests for the Qt splash screen ``DisplayCAL.ui.startup`` (Stage 6).

``welcome_message`` / ``should_enumerate_ports`` are pure marshalling helpers
lifted out of ``display_cal.StartupFrame``, tested without a display.
``StartupController`` is exercised headless via the shared offscreen
``QApplication``, with a fake worker so no Argyll / hardware is needed. See
``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 6).
"""

import os
import time

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL import config  # noqa: E402
from DisplayCAL.config import setcfg  # noqa: E402
from DisplayCAL.ui import startup  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _init_config():
    config.initcfg()
    yield


def _spin_until(qapp, predicate, timeout_s=3.0):
    """Pump the event loop until ``predicate`` is true or the timeout elapses."""
    deadline = time.time() + timeout_s
    while not predicate() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    return predicate()


class _FakeWorker:
    def __init__(self, exception=None):
        self._exception = exception
        self.displays = []
        self.instruments = []
        self.abort_calls = 0
        self.enumerate_calls = []

    def enumerate_displays_and_ports(self, enumerate_ports=True, silent=False):
        self.enumerate_calls.append((enumerate_ports, silent))
        if self._exception is not None:
            raise self._exception
        self.displays = ["Fake @ 0, 0, 1x1 [PRIMARY]"]
        self.instruments = ["Fake Meter"]

    def abort_subprocess(self, confirm=False):
        self.abort_calls += 1


# --- pure helpers ------------------------------------------------------------


def test_welcome_message_differs_first_run_vs_returning(monkeypatch):
    monkeypatch.setattr(startup, "hascfg", lambda *a, **k: False)
    first_run = startup.welcome_message()
    monkeypatch.setattr(startup, "hascfg", lambda *a, **k: True)
    returning = startup.welcome_message()
    assert first_run and returning
    assert first_run != returning


def test_should_enumerate_ports_when_no_instruments_configured():
    setcfg("instruments", [])
    setcfg("enumerate_ports.auto", 0)
    assert startup.should_enumerate_ports()


def test_should_enumerate_ports_skips_when_forced_off(monkeypatch):
    monkeypatch.setattr(startup, "FORCE_SKIP_INITIAL_INSTRUMENT_DETECTION", True)
    setcfg("instruments", [])
    assert not startup.should_enumerate_ports()


def test_should_enumerate_ports_respects_single_known_instrument():
    setcfg("instruments", ["Known Meter"])
    setcfg("enumerate_ports.auto", 0)
    assert not startup.should_enumerate_ports()


# --- StartupController ---------------------------------------------------


def test_splash_pixmap_loads_asset(qapp):
    pixmap = startup.splash_pixmap()
    assert not pixmap.isNull()


def test_controller_enumerates_and_calls_ready(qapp, monkeypatch):
    monkeypatch.setattr(startup.StartupController, "_min_show_ms", 0)
    worker = _FakeWorker()
    ready = []
    controller = startup.StartupController(ready.append, worker=worker)
    try:
        controller.start()
        assert _spin_until(qapp, lambda: ready)
        assert ready == [worker]
        assert worker.displays == ["Fake @ 0, 0, 1x1 [PRIMARY]"]
    finally:
        controller.splash.close()


def test_controller_still_calls_ready_on_enumeration_error(qapp, monkeypatch):
    monkeypatch.setattr(startup.StartupController, "_min_show_ms", 0)
    worker = _FakeWorker(exception=RuntimeError("boom"))
    ready = []
    controller = startup.StartupController(ready.append, worker=worker)
    try:
        controller.start()
        assert _spin_until(qapp, lambda: ready)
        assert ready == [worker]
    finally:
        controller.splash.close()


def test_controller_respects_minimum_show_duration(qapp, monkeypatch):
    monkeypatch.setattr(startup.StartupController, "_min_show_ms", 300)
    worker = _FakeWorker()
    ready = []
    controller = startup.StartupController(ready.append, worker=worker)
    try:
        controller.start()
        # Enumeration itself is near-instant; readiness must still wait for
        # the minimum splash duration.
        start = time.monotonic()
        assert _spin_until(qapp, lambda: ready)
        elapsed_ms = (time.monotonic() - start) * 1000
        assert elapsed_ms >= 250  # a little slack below the 300ms floor
    finally:
        controller.splash.close()


def test_controller_shows_welcome_message(qapp):
    worker = _FakeWorker()
    controller = startup.StartupController(lambda w: None, worker=worker)
    try:
        assert controller.splash.pixmap().isNull() is False
    finally:
        controller.splash.close()
