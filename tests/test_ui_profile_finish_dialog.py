"""Tests for the Qt post-calibration/profiling completion dialog.

Drives ``DisplayCAL.ui.profile_finish_dialog.ProfileFinishDialog`` headless via
the shared offscreen ``QApplication`` fixture, the same pattern as
``tests/test_ui_profile_install_window.py``.
"""

import os

import pytest

from DisplayCAL import config
from DisplayCAL.worker import Worker

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL.ui import profile_finish_dialog as pfd  # noqa: E402


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


@pytest.fixture
def worker():
    return Worker()


@pytest.fixture
def fixed_scope_options(monkeypatch):
    """Force a deterministic, non-empty scope choice regardless of the host."""
    monkeypatch.setattr(pfd.pi, "resolve_install_scope_options", lambda **kw: ["u", "l"])


def _make_dialog(qapp, worker, **overrides):
    kwargs = {
        "parent": None,
        "message": "Install profile Foo on display Bar?",
        "cinfo": [],
        "vinfo": [],
        "ok_label": "Install",
        "cancel_label": "Do not install",
        "installable": True,
        "preview_enabled": False,
        "show_profile_info_checked": False,
        "worker": worker,
    }
    kwargs.update(overrides)
    return pfd.ProfileFinishDialog(**kwargs)


# --- modality -----------------------------------------------------------------


def test_dialog_is_window_modal_not_application_modal(qapp, worker):
    """Must not block the separate ProfileInfoWindow the checkbox can open.

    ``exec()`` implicitly makes a QDialog application-modal unless a weaker
    modality was set beforehand -- application-modal blocks input to every
    other top-level window in the app, including the non-modal
    ``ProfileInfoWindow`` the "Show Profile Information" checkbox opens via
    ``main_window.py``'s ``_toggle_profile_info_window``. Window-modal only
    blocks the dialog's own parent window chain, leaving that window usable.
    """
    from qtpy.QtCore import Qt

    dialog = _make_dialog(qapp, worker)
    assert dialog.windowModality() == Qt.WindowModal


# --- gamut grid --------------------------------------------------------------


def test_gamut_grid_omitted_when_no_data(qapp, worker):
    dialog = _make_dialog(qapp, worker)
    try:
        # No cinfo/vinfo -> no bold "gamut.coverage"/"gamut.volume" labels.
        labels = dialog.findChildren(pfd.QLabel)
        texts = [label.text() for label in labels]
        assert not any("Coverage" in t or "coverage" in t for t in texts)
    finally:
        dialog.deleteLater()


def test_gamut_grid_shows_only_populated_columns(qapp, worker):
    dialog = _make_dialog(qapp, worker, cinfo=["99.9% sRGB"], vinfo=[])
    try:
        labels = [label.text() for label in dialog.findChildren(pfd.QLabel)]
        assert any("99.9% sRGB" in t for t in labels)
    finally:
        dialog.deleteLater()


def test_gamut_grid_shows_both_columns(qapp, worker):
    dialog = _make_dialog(
        qapp, worker, cinfo=["99.9% sRGB"], vinfo=["87.3% sRGB"]
    )
    try:
        labels = [label.text() for label in dialog.findChildren(pfd.QLabel)]
        assert any("99.9% sRGB" in t for t in labels)
        assert any("87.3% sRGB" in t for t in labels)
    finally:
        dialog.deleteLater()


# --- preview / show-profile-info checkboxes ----------------------------------


def test_preview_checkbox_hidden_when_disabled(qapp, worker):
    dialog = _make_dialog(qapp, worker, preview_enabled=False)
    try:
        assert dialog.preview_check is None
    finally:
        dialog.deleteLater()


def test_preview_checkbox_defaults_checked_when_enabled(qapp, worker):
    dialog = _make_dialog(qapp, worker, preview_enabled=True)
    try:
        assert dialog.preview_check is not None
        assert dialog.preview_check.isChecked()
    finally:
        dialog.deleteLater()


def test_preview_toggled_signal_emits_new_state(qapp, worker):
    dialog = _make_dialog(qapp, worker, preview_enabled=True)
    try:
        seen = []
        dialog.preview_toggled.connect(seen.append)
        dialog.preview_check.setChecked(False)
        assert seen == [False]
    finally:
        dialog.deleteLater()


def test_show_profile_info_checkbox_reflects_initial_state(qapp, worker):
    dialog = _make_dialog(qapp, worker, show_profile_info_checked=True)
    try:
        assert dialog.show_profile_info_check.isChecked()
    finally:
        dialog.deleteLater()


def test_show_profile_info_toggled_signal_emits_new_state(qapp, worker):
    dialog = _make_dialog(qapp, worker, show_profile_info_checked=False)
    try:
        seen = []
        dialog.show_profile_info_toggled.connect(seen.append)
        dialog.show_profile_info_check.setChecked(True)
        assert seen == [True]
    finally:
        dialog.deleteLater()


# --- installable: load-on-login / install scope ------------------------------


def test_non_installable_hides_login_and_scope_controls(qapp, worker):
    dialog = _make_dialog(qapp, worker, installable=False)
    try:
        assert dialog.load_on_login_check is None
        assert dialog._scope_buttons == {}
    finally:
        dialog.deleteLater()


def test_installable_shows_load_on_login_checkbox(qapp, worker):
    dialog = _make_dialog(qapp, worker, installable=True)
    try:
        assert dialog.load_on_login_check is not None
    finally:
        dialog.deleteLater()


def test_no_scope_options_forces_user_scope(qapp, worker, monkeypatch):
    monkeypatch.setattr(pfd.pi, "resolve_install_scope_options", lambda **kw: [])
    dialog = _make_dialog(qapp, worker, installable=True)
    try:
        assert dialog._scope_buttons == {}
        assert config.getcfg("profile.install_scope") == "u"
    finally:
        dialog.deleteLater()


def test_scope_buttons_built_from_resolved_options(
    qapp, worker, fixed_scope_options
):
    config.setcfg("profile.install_scope", "u")
    dialog = _make_dialog(qapp, worker, installable=True)
    try:
        assert set(dialog._scope_buttons) == {"u", "l"}
        assert dialog._scope_buttons["u"].isChecked()
        assert dialog.install_scope == "u"
    finally:
        dialog.deleteLater()


def test_selecting_scope_button_persists_config(
    qapp, worker, fixed_scope_options
):
    config.setcfg("profile.install_scope", "u")
    dialog = _make_dialog(qapp, worker, installable=True)
    try:
        dialog._scope_buttons["l"].setChecked(True)
        assert config.getcfg("profile.install_scope") == "l"
        assert dialog.install_scope == "l"
    finally:
        dialog.deleteLater()


def test_load_on_login_checkbox_persists_config(qapp, worker):
    dialog = _make_dialog(qapp, worker, installable=True)
    try:
        dialog.load_on_login_check.setChecked(True)
        assert config.getcfg("profile.load_on_login") == 1
        assert dialog.load_on_login_checked is True

        dialog.load_on_login_check.setChecked(False)
        assert config.getcfg("profile.load_on_login") == 0
        assert dialog.load_on_login_checked is False
    finally:
        dialog.deleteLater()


# --- buttons -------------------------------------------------------------


def test_ok_button_accepts_dialog(qapp, worker):
    dialog = _make_dialog(qapp, worker, ok_label="Install profile")
    try:
        buttons = [b for b in dialog.findChildren(pfd.QPushButton)]
        ok_button = next(b for b in buttons if b.text() == "Install profile")
        results = []
        dialog.accepted.connect(lambda: results.append(True))
        ok_button.click()
        assert results == [True]
    finally:
        dialog.deleteLater()


def test_cancel_button_rejects_dialog(qapp, worker):
    dialog = _make_dialog(qapp, worker, cancel_label="Do not install")
    try:
        buttons = [b for b in dialog.findChildren(pfd.QPushButton)]
        cancel_button = next(b for b in buttons if b.text() == "Do not install")
        results = []
        dialog.rejected.connect(lambda: results.append(True))
        cancel_button.click()
        assert results == [True]
    finally:
        dialog.deleteLater()
