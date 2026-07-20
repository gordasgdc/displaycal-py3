"""Tests for the Qt profile-associations dialog (issue #888).

Drives ``DisplayCAL.ui.tools.profile_associations.ProfileAssociationsDialog``
headless via the shared offscreen ``QApplication`` fixture, the same pattern
as ``tests/test_ui_profile_finish_dialog.py``.

The dialog's real behaviour (add/remove/set-default/use-my-settings) drives
Windows-only WCS/registry APIs (``_winreg_get_display_profiles`` et al, only
imported under ``sys.platform == "win32"``) against a ``monitors`` list that
in practice is only ever non-empty on Windows (``ProfileLoader.monitors`` is
populated exclusively by the win32-only ``_enumerate_monitors``). These tests
therefore exercise the dialog with an empty ``monitors`` list -- the only
state reachable on non-Windows -- plus the platform-independent scaffolding
(button enable states, the disabled "fix" checkbox, timer teardown).
"""

import os
import sys
import threading

import pytest

from DisplayCAL import config

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL.ui.tools import profile_associations as pa  # noqa: E402


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

    def __init__(self, monitors=()):
        self.monitors = list(monitors)
        self.lock = threading.Lock()
        self._next = False
        self.child_devices_count = {}

    def _can_fix_profile_associations(self):
        return False

    def get_title(self):
        return "DisplayCAL Apply Profiles"

    def elevate(self):
        return False


def _make_dialog(qapp, pl=None):
    return pa.ProfileAssociationsDialog(pl or _StubPL())


def test_construct_with_no_monitors(qapp):
    """No displays enumerated (the only state reachable off Windows)."""
    dialog = _make_dialog(qapp)
    try:
        assert dialog.display_combo.count() == 0
        assert not dialog.display_combo.isEnabled()
        assert not dialog.identify_btn.isEnabled()
        assert not dialog.add_btn.isEnabled()
        assert not dialog.remove_btn.isEnabled()
        assert not dialog.profile_info_btn.isEnabled()
        assert not dialog.set_as_default_btn.isEnabled()
        assert dialog.profiles_table.rowCount() == 0
    finally:
        dialog.close()


def test_fix_profile_associations_checkbox_stays_disabled(qapp):
    """FixProfileAssociationsDialog isn't ported yet (#889) -- keep it inert."""
    dialog = _make_dialog(qapp)
    try:
        assert not dialog.fix_profile_associations_cb.isEnabled()
        assert dialog.fix_profile_associations_cb.toolTip() == (
            pa._FIX_ASSOCIATIONS_TOOLTIP
        )
    finally:
        dialog.close()


def test_win32_only_widgets_gated_by_platform(qapp):
    dialog = _make_dialog(qapp)
    try:
        if sys.platform == "win32":
            assert dialog.use_my_settings_cb is not None
            assert dialog.warn_icon is not None
            assert dialog.warn_label is not None
        else:
            assert dialog.use_my_settings_cb is None
            assert dialog.warn_icon is None
            assert dialog.warn_label is None
    finally:
        dialog.close()


def test_close_stops_refresh_timer(qapp):
    dialog = _make_dialog(qapp)
    assert dialog.update_profiles_timer.isActive()
    dialog.close()
    assert not dialog.update_profiles_timer.isActive()


def test_identify_displays_with_no_monitors_is_a_noop(qapp):
    dialog = _make_dialog(qapp)
    try:
        dialog.identify_displays()
        assert dialog._identification_overlays == {}
    finally:
        dialog.close()


def test_add_remove_set_default_beep_when_nothing_selected(qapp, monkeypatch):
    """With no row selected, the mutating actions must not touch set_profile."""
    dialog = _make_dialog(qapp, pl=_StubPL(monitors=[("Display 1", None, {}, None)]))
    try:
        called = []
        monkeypatch.setattr(dialog, "set_profile", lambda *a, **k: called.append(a))
        dialog.remove_profile()
        dialog.set_as_default()
        assert called == []
    finally:
        dialog.close()
