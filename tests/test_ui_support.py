"""Voluntary support and feedback UI."""

import hashlib
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")
pytest.importorskip("qtpy")

from test_ui_main_window import _init_config, qapp, stub_worker, window  # noqa: E402,F401

from DisplayCAL import config, support  # noqa: E402
from DisplayCAL.config import getcfg, setcfg  # noqa: E402
from DisplayCAL.ui import support_dialog as sd  # noqa: E402

HERE = os.path.dirname(os.path.dirname(__file__))


@pytest.fixture
def opened(monkeypatch):
    urls = []
    monkeypatch.setattr(sd, "open_url", lambda u: urls.append(u) or True)
    monkeypatch.setattr(config, "writecfg", lambda *a, **k: None)
    return urls


def test_github_logo_files_are_the_official_unaltered_ones():
    expected = {
        "github-invertocat-black.svg": "693d7abe6f899646cc2e96856723b45e95f71885a54910b2749f6decdf7e1ee1",
        "github-invertocat-white.svg": "ccd84c89b1056345608fc3489357f8acc7397e49a3cdc2d418b6c8016911d47b",
    }
    for name, digest in expected.items():
        path = os.path.join(HERE, "DisplayCAL", "theme", "brands", name)
        with open(path, "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == digest


def test_star_opens_only_the_repository_page(qapp, opened):
    actions = sd.SupportActions()
    assert not actions.star_btn.icon().isNull()
    assert actions.star_btn.text() and actions.star_btn.accessibleName()
    actions.star_btn.click()
    assert opened == [support.REPO_URL]


def test_feedback_never_includes_diagnostic_unless_ticked(qapp, opened, tmp_path):
    log = tmp_path / "l.log"
    log.write_text("secret line a@b.com\n", encoding="utf-8")
    dlg = sd.FeedbackDialog(log_path=str(log))
    assert dlg.diag_cb.isChecked() is False
    dlg.description.setPlainText("It stopped")
    dlg._open()
    assert "Version" in opened[0] and "Platform" in opened[0]
    assert "Diagnostic" not in opened[0]
    dlg2 = sd.FeedbackDialog(log_path=str(log))
    dlg2.description.setPlainText("It stopped")
    dlg2.diag_cb.setChecked(True)
    assert (
        "a%40b.com" not in "".join(dlg2.diagnostic_text())
        and "a@b.com" not in dlg2.diagnostic_text()
    )
    dlg2._open()
    assert "Diagnostic" in opened[-1]


def test_dialog_shows_version_and_platform_before_sending(qapp):
    dlg = sd.FeedbackDialog()
    text = dlg.info.text()
    assert support.app_version_line() in text and support.platform_line() in text


def test_invite_close_and_never(qapp, opened):
    setcfg("support.invite", 1)
    setcfg("support.dismissed_version", "")
    v = "1.0"
    assert sd.invite_allowed(v)
    inv = sd.SupportInvite(v)
    inv.close_btn.click()
    assert getcfg("support.dismissed_version") == v
    assert not sd.invite_allowed(v)
    assert sd.invite_allowed("2.0")  # only silenced for this version
    inv2 = sd.SupportInvite("2.0")
    inv2.never_btn.click()
    assert getcfg("support.invite") == 0
    assert not sd.invite_allowed("9.9")
    setcfg("support.invite", 1)
    setcfg("support.dismissed_version", "")


def test_help_menu_offers_both_actions(window):
    titles = [a.text() for a in window._help_menu.actions()]
    assert "Give a star on GitHub" in titles and "Send feedback" in titles


def test_no_invitation_before_a_finished_flow(window):
    guide = window._guide
    setcfg("support.invite", 1)
    guide.refresh()
    assert guide.invite.isHidden()
    window.last_profile_check = type(
        "C", (), {"verified": False, "message_key": "guide.verify.mismatch"}
    )()
    guide.refresh()
    assert guide.invite.isHidden()  # not after a failed/unverified install
    window.last_profile_check = type(
        "C", (), {"verified": True, "message_key": "guide.verify.match"}
    )()
    guide.refresh()
    assert not guide.invite.isHidden()
    window.last_profile_check = None


def test_about_has_support_with_separate_credits(qapp):
    from DisplayCAL.ui.about_window import AboutWindow

    w = AboutWindow(None)
    actions = w.findChildren(sd.SupportActions)
    assert actions
    credits = actions[0].credits.text()
    assert support.UPSTREAM_URL in credits and support.ORIGINAL_URL in credits
    assert support.ARGYLL_URL in credits
