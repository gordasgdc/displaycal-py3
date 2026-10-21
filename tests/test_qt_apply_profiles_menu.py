"""Tests for the Qt apply-profiles tray menu on Windows.

``ApplyProfilesTrayIcon._rebuild_menu`` runs in the tray icon's constructor, so
an action wired to a loader method that does not exist aborts the whole
apply-profiles component at start-up (``AttributeError: 'QtProfileLoader'
object has no attribute 'open_display_settings'``) before the calibration
curves are ever applied. ``open_display_settings`` only ever existed on the wx
``TaskBarIcon``, never on ``ProfileLoader``, and nothing exercised the
Windows-only branch of the menu on another platform. The other tray tests use a
plain ``mock.Mock()`` loader, which answers to any attribute name, so they could
not catch a missing method either.
"""

import ast
import inspect
import os
import sys
import textwrap
from unittest import mock

import pytest

from DisplayCAL import config

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from qtpy.QtWidgets import QMenu  # noqa: E402

from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL import profile_loader  # noqa: E402
from DisplayCAL.ui.tools import apply_profiles  # noqa: E402
from DisplayCAL.ui.tools.apply_profiles import (  # noqa: E402
    ApplyProfilesTrayIcon,
    QtProfileLoader,
)


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _init_config():
    config.initcfg()
    lang.init()
    yield


def _strict_loader():
    """Return a loader double that only accepts attributes the real class has.

    ``create_autospec`` raises ``AttributeError`` for a name that
    ``QtProfileLoader`` (including everything it inherits) does not define,
    exactly like the real object does.
    """
    pl = mock.create_autospec(QtProfileLoader, instance=True)
    # Instance attributes set in ``ProfileLoader.__init__`` are not part of
    # the class, so the autospec does not know them.
    pl._reset_gamma_ramps = False
    pl._is_displaycal_running.return_value = False
    pl._is_other_running.return_value = False
    pl._can_fix_profile_associations.return_value = True
    return pl


def _build_menu(monkeypatch, platform, pl):
    """Run ``_rebuild_menu`` for ``platform`` without a real system tray."""
    monkeypatch.setattr(
        apply_profiles, "calibration_management_isenabled", lambda: False
    )
    tray = ApplyProfilesTrayIcon.__new__(ApplyProfilesTrayIcon)
    tray.pl = pl
    tray._menu = QMenu()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "platform", platform)
        tray._rebuild_menu()
    return tray._menu


def _action(menu, text):
    return next((a for a in menu.actions() if a.text() == text), None)


def test_windows_menu_builds_with_the_real_loader_interface(qapp, monkeypatch):
    pl = _strict_loader()

    menu = _build_menu(monkeypatch, "win32", pl)

    action = _action(menu, lang.getstr("mswin.open_display_settings"))
    assert action is not None


def test_windows_menu_display_settings_action_calls_the_loader(qapp, monkeypatch):
    pl = _strict_loader()
    menu = _build_menu(monkeypatch, "win32", pl)

    _action(menu, lang.getstr("mswin.open_display_settings")).trigger()

    pl.open_display_settings.assert_called_once()


def test_display_settings_action_is_windows_only(qapp, monkeypatch):
    menu = _build_menu(monkeypatch, "darwin", _strict_loader())

    assert _action(menu, lang.getstr("mswin.open_display_settings")) is None


def _self_attributes(tree):
    """Names assigned as ``self.<name>`` anywhere in ``tree``."""
    names = set()
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                names.add(target.attr)
    return names


def test_qt_tray_only_uses_loader_attributes_that_exist():
    """Every ``pl.<name>`` used by the Qt module resolves on the loader.

    Platform independent: it also covers branches that only run on Windows
    (or only off Windows), which a test run on one platform never executes.
    """
    available = set(dir(QtProfileLoader))
    for cls in (profile_loader.ProfileLoader, QtProfileLoader):
        source = textwrap.dedent(inspect.getsource(cls))
        available |= _self_attributes(ast.parse(source))

    module_tree = ast.parse(inspect.getsource(apply_profiles))
    used = {}
    for node in ast.walk(module_tree):
        if not isinstance(node, ast.Attribute):
            continue
        owner = node.value
        is_pl = isinstance(owner, ast.Name) and owner.id == "pl"
        is_self_pl = (
            isinstance(owner, ast.Attribute)
            and owner.attr == "pl"
            and isinstance(owner.value, ast.Name)
            and owner.value.id == "self"
        )
        if is_pl or is_self_pl:
            used.setdefault(node.attr, node.lineno)

    missing = {name: line for name, line in used.items() if name not in available}
    assert not missing, f"Qt tray uses loader attributes that do not exist: {missing}"


class _FakeApp:
    """Stands in for ``QApplication`` inside ``apply_profiles`` only."""

    beeps = 0

    @staticmethod
    def beep():
        _FakeApp.beeps += 1


def test_open_display_settings_launches_the_windows_control_panel_page(monkeypatch):
    pl = QtProfileLoader.__new__(QtProfileLoader)
    popen = mock.Mock()
    monkeypatch.setattr(apply_profiles.subprocess, "Popen", popen)

    pl.open_display_settings()

    popen.assert_called_once()
    assert popen.call_args.args[0] == [
        "control",
        "/name",
        "Microsoft.Display",
        "/page",
        "Settings",
    ]


def test_open_display_settings_failure_beeps_and_does_not_raise(monkeypatch):
    pl = QtProfileLoader.__new__(QtProfileLoader)
    _FakeApp.beeps = 0
    monkeypatch.setattr(apply_profiles, "QApplication", _FakeApp)
    monkeypatch.setattr(
        apply_profiles.subprocess, "Popen", mock.Mock(side_effect=OSError("no control"))
    )

    pl.open_display_settings()

    assert _FakeApp.beeps == 1
