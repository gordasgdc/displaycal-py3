"""Tests for ``QtProfileLoader._toggle_fix_profile_associations`` (issue #889).

Covers the Qt override that replaces wx's ``FixProfileAssociationsDialog``
with the Qt port (:mod:`DisplayCAL.ui.tools.fix_profile_associations`) while
keeping the confirm/apply logic (setcfg, ``_set_display_profiles``/
``_reset_display_profile_associations``, ``writecfg``) identical to the
inherited wx version. Exercises the real dialog construction (headless, via
the shared offscreen ``QApplication``) but stubs out its modal ``exec()`` so
the test can drive both the accepted and cancelled paths deterministically.
"""

import os
import threading

import pytest

from DisplayCAL import config

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL.ui.tools.apply_profiles import QtProfileLoader  # noqa: E402
from DisplayCAL.ui.tools.profile_associations import _CheckedEvent  # noqa: E402


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


def _make_pl(monkeypatch):
    """Build a ``QtProfileLoader`` without running ``__init__``'s wx/Qt bootstrap."""
    pl = QtProfileLoader.__new__(QtProfileLoader)
    pl.lock = threading.Lock()
    pl.devices2profiles = {}
    pl._manual_restore = False
    calls = {"set": 0, "reset": 0}
    monkeypatch.setattr(pl, "get_title", lambda: "DisplayCAL Apply Profiles")
    monkeypatch.setattr(pl, "writecfg", lambda *a, **k: None)
    monkeypatch.setattr(
        pl,
        "_set_display_profiles",
        lambda dry_run=False: calls.__setitem__("set", calls["set"] + 1),
    )
    monkeypatch.setattr(
        pl,
        "_reset_display_profile_associations",
        lambda: calls.__setitem__("reset", calls["reset"] + 1),
    )
    return pl, calls


def _stub_dialog_result(monkeypatch, result):
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.fix_profile_associations.FixProfileAssociationsDialog.exec",
        lambda self: result,
    )
    monkeypatch.setattr(
        "DisplayCAL.ui.tools.fix_profile_associations.FixProfileAssociationsDialog.close",
        lambda self: None,
    )


def test_toggle_on_accepted_sets_cfg_and_applies(qapp, monkeypatch):
    from qtpy.QtWidgets import QDialog

    pl, calls = _make_pl(monkeypatch)
    _stub_dialog_result(monkeypatch, QDialog.DialogCode.Accepted)

    result = pl._toggle_fix_profile_associations(_CheckedEvent(True))

    assert result is True
    assert config.getcfg("profile_loader.fix_profile_associations") == 1
    # One dry-run call from the confirmation dialog's own refresh, one real
    # call from the actual apply after confirmation.
    assert calls == {"set": 2, "reset": 0}


def test_toggle_on_cancelled_leaves_state_untouched(qapp, monkeypatch):
    from qtpy.QtWidgets import QDialog

    pl, calls = _make_pl(monkeypatch)
    config.setcfg("profile_loader.fix_profile_associations", 0)
    _stub_dialog_result(monkeypatch, QDialog.DialogCode.Rejected)

    result = pl._toggle_fix_profile_associations(_CheckedEvent(True))

    assert result is False
    assert config.getcfg("profile_loader.fix_profile_associations") == 0
    # Only the confirmation dialog's own dry-run refresh, no real apply.
    assert calls == {"set": 1, "reset": 0}


def test_toggle_off_resets_associations_without_showing_dialog(qapp, monkeypatch):
    pl, calls = _make_pl(monkeypatch)

    result = pl._toggle_fix_profile_associations(_CheckedEvent(False))

    assert result is False
    assert config.getcfg("profile_loader.fix_profile_associations") == 0
    assert calls == {"set": 0, "reset": 1}
