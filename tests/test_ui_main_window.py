"""Tests for the Qt main-window shell ``DisplayCAL.ui.main_window`` (Stage 3).

These exercise the toolkit-neutral marshalling helpers directly (no display) and
drive the window itself headless via the shared offscreen ``QApplication``
fixture. Display/port enumeration is stubbed so the tests need no Argyll install.
See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 3).
"""

import os

import pytest

from DisplayCAL import config
from DisplayCAL.config import getcfg, setcfg
from DisplayCAL.worker import Worker

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

# Skip the whole module cleanly if Qt is unavailable in the environment.
pytest.importorskip("qtpy")

from DisplayCAL.ui import main_window as mw  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _init_config():
    """Initialise config (default values) before each test."""
    config.initcfg()
    yield


@pytest.fixture
def stub_worker(monkeypatch):
    """Stub worker enumeration so no Argyll / hardware is needed."""

    def fake(self, *args, **kwargs):
        self.displays = [
            "DELL U2413 @ 0, 0, 1920x1080 [PRIMARY]",
            "Web @ localhost",
        ]
        self.instruments = ["i1 DisplayPro, ColorMunki Display", "Spyder5"]

    monkeypatch.setattr(Worker, "enumerate_displays_and_ports", fake)


# --- pure marshalling helpers ----------------------------------------------


def test_display_items_localizes_primary_marker():
    items = mw.display_items(["Foo @ 0, 0 [PRIMARY]", "Bar @ 1"])
    # The [PRIMARY] marker is replaced with the localized suffix.
    assert "[PRIMARY]" not in items[0]
    assert "Foo @ 0, 0" in items[0]
    assert items[1] == "Bar @ 1"


def test_instrument_items_falls_back_to_raw_name():
    items = mw.instrument_items(["Totally Unknown Meter"])
    # No localization key -> the raw name is used as the default.
    assert items == ["Totally Unknown Meter"]


# --- window construction / wiring ------------------------------------------


@pytest.fixture
def window(qapp, stub_worker):
    """Construct a MainWindow against the stubbed worker."""
    win = mw.MainWindow()
    yield win
    win.close()


def test_tabs_present(window):
    assert list(window._tab_buttons) == [
        "display_instrument",
        "calibration",
        "profiling",
        "lut3d",
    ]


def test_selectors_populate_from_worker(window):
    displays = [
        window.display_ctrl.itemText(i) for i in range(window.display_ctrl.count())
    ]
    assert len(displays) == 2
    assert window.comport_ctrl.count() == 2
    assert window.observer_ctrl.count() == len(config.VALID_VALUES["observer"])


def test_display_selection_persists_number(window):
    window.display_ctrl.setCurrentIndex(1)
    assert getcfg("display.number") == 2


def test_comport_selection_persists_number(window):
    window.comport_ctrl.setCurrentIndex(1)
    assert getcfg("comport.number") == 2


def test_observer_selection_persists_key(window):
    keys = list(window._observers)
    target = keys[-1]
    window.observer_ctrl.setCurrentIndex(len(keys) - 1)
    assert getcfg("observer") == target


def test_populating_does_not_write_config(qapp, stub_worker):
    """Repopulating controls must not clobber config via the guard flag."""
    setcfg("display.number", 2)
    setcfg("comport.number", 2)
    win = mw.MainWindow()
    try:
        # Construction selected the stored indices without firing writes that
        # would reset them to 1.
        assert getcfg("display.number") == 2
        assert getcfg("comport.number") == 2
    finally:
        win.close()


def test_select_tab_switches_stack(window):
    window._select_tab("profiling")
    assert window.stack.currentWidget() is window._panels["profiling"]
    assert window._tab_buttons["profiling"].isChecked() is True


def test_action_buttons_disabled_until_stage_4(window):
    assert window.calibrate_btn.isEnabled() is False
    assert window.calibrate_and_profile_btn.isEnabled() is False
    assert window.profile_btn.isEnabled() is False
