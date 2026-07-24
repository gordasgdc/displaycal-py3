"""Tests for the Qt fix-profile-associations dialog (issue #889).

Drives ``DisplayCAL.ui.tools.fix_profile_associations.FixProfileAssociationsDialog``
headless via the shared offscreen ``QApplication`` fixture, the same pattern
as ``tests/test_ui_profile_associations.py``. The dialog's real data comes
from ``ProfileLoader.devices2profiles``, itself only ever populated by the
win32-only ``ProfileLoader._set_display_profiles``, so these tests drive the
dialog against a stub loader instead of the real (Windows-only) enumeration.
"""

import os

import pytest

from DisplayCAL import config

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL.ui.tools import fix_profile_associations as fpa  # noqa: E402


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


class _StubPL:
    """Minimal stand-in for ``QtProfileLoader`` (avoids spawning a real tray)."""

    def __init__(self, devices2profiles=None):
        self.devices2profiles = devices2profiles or {}
        self.set_display_profiles_calls = 0

    def _set_display_profiles(self, dry_run=False):
        self.set_display_profiles_calls += 1

    def get_title(self):
        return "DisplayCAL Apply Profiles"


def _make_dialog(qapp, pl=None):
    return fpa.FixProfileAssociationsDialog(pl or _StubPL())


def test_construct_with_no_devices(qapp):
    dialog = _make_dialog(qapp)
    try:
        assert dialog.table.rowCount() == 0
        assert dialog.windowTitle() == "DisplayCAL Apply Profiles"
    finally:
        dialog.close()


def test_construct_calls_set_display_profiles_dry_run(qapp):
    pl = _StubPL()
    dialog = _make_dialog(qapp, pl=pl)
    try:
        assert pl.set_display_profiles_calls == 1
    finally:
        dialog.close()


def test_table_populated_from_devices2profiles(qapp):
    devices2profiles = {
        "dev1": (("Display 1", b"edid1"), None, "unassigned"),
        "dev2": (("[PRIMARY]Display 2", b"edid2"), None, "Some Profile"),
    }
    dialog = _make_dialog(qapp, pl=_StubPL(devices2profiles))
    try:
        assert dialog.table.rowCount() == 2
        assert dialog.table.item(0, 0).text() == "Display 1"
        assert dialog.table.item(0, 1).text() == "unassigned"
        assert "[PRIMARY]" not in dialog.table.item(1, 0).text()
        assert "Display 2" in dialog.table.item(1, 0).text()
        assert dialog.table.item(1, 1).text() == "Some Profile"
    finally:
        dialog.close()


def test_update_refreshes_table_and_re_queries_loader(qapp):
    pl = _StubPL({"dev1": (("Display 1", b"edid1"), None, "unassigned")})
    dialog = _make_dialog(qapp, pl=pl)
    try:
        pl.devices2profiles = {
            "dev1": (("Display 1", b"edid1"), None, "unassigned"),
            "dev2": (("Display 2", b"edid2"), None, "unassigned"),
        }
        dialog.update()
        assert pl.set_display_profiles_calls == 2
        assert dialog.table.rowCount() == 2
    finally:
        dialog.close()


def test_close_stops_refresh_timer(qapp):
    dialog = _make_dialog(qapp)
    assert dialog._refresh_timer.isActive()
    dialog.close()
    assert not dialog._refresh_timer.isActive()


def test_ok_cancel_buttons_present(qapp):
    from qtpy.QtWidgets import QDialogButtonBox

    from DisplayCAL import localization as lang

    dialog = _make_dialog(qapp)
    try:
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons is not None
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        assert ok_button.text().replace("&", "") == lang.getstr(
            "profile_loader.fix_profile_associations"
        )
        assert cancel_button.text().replace("&", "") == lang.getstr("cancel")
    finally:
        dialog.close()
