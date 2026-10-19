"""Monitor lookup UI: reachable in guided and advanced mode, honest, never blocking."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("qtpy")
from test_ui_main_window import _init_config, qapp, stub_worker, window  # noqa: E402,F401

from DisplayCAL import display_lookup as dl  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL.ui import display_lookup_dialog as dd  # noqa: E402


@pytest.fixture
def app(qapp, _init_config):  # noqa: F811
    lang.init()
    return qapp


def test_dialog_external_monitor_copies_model_and_opens_the_site(app, monkeypatch):
    urls = []
    monkeypatch.setattr(dd, "open_url", lambda u: urls.append(u) or True)
    dlg = dd.DisplayLookupDialog(entry="BenQ PD3200U @ 1512, 0, 3840x2160", platform="darwin", hw_model="Mac14,9")
    assert "not a built-in Apple screen" in dlg.kind_label.text()
    assert len(dlg.action_buttons) == 1
    dlg.action_buttons[0].click()
    assert urls == [dl.DISPLAYSPECS_HOME]
    assert dd.QApplication.clipboard().text() == "BenQ PD3200U"
    assert "BenQ PD3200U" in dlg.status.text()


def test_dialog_builtin_mac_opens_the_everymac_lookup_by_identifier(app, monkeypatch):
    urls = []
    monkeypatch.setattr(dd, "open_url", lambda u: urls.append(u) or True)
    dlg = dd.DisplayLookupDialog(entry="Mac14,9 @ 0, 0, 1512x982", platform="darwin", hw_model="Mac14,9")
    assert "Mac14,9" in dlg.kind_label.text()
    dlg.action_buttons[0].click()
    assert urls == ["https://everymac.com/ultimate-mac-lookup/?identify=Mac14%2C9"]


def test_user_can_correct_the_model_and_the_clipboard_follows(app, monkeypatch):
    monkeypatch.setattr(dd, "open_url", lambda u: True)
    dlg = dd.DisplayLookupDialog(entry="BenQ PD3200U", platform="linux", hw_model=None)
    dlg.model_edit.setText("BenQ PD3200UE")
    dlg.action_buttons[0].click()
    assert dd.QApplication.clipboard().text() == "BenQ PD3200UE"


def test_failure_to_open_the_browser_is_reported_not_fatal(app, monkeypatch):
    monkeypatch.setattr(dd, "open_url", lambda u: False)
    dlg = dd.DisplayLookupDialog(entry="BenQ PD3200U", platform="linux", hw_model=None)
    dlg.action_buttons[0].click()  # must not raise
    assert dl.DISPLAYSPECS_HOME in dlg.status.text() and "BenQ PD3200U" in dd.QApplication.clipboard().text()


def test_no_model_identified_dialog_still_works_without_a_recommendation(app, monkeypatch):
    monkeypatch.setattr(dd, "open_url", lambda u: True)
    dlg = dd.DisplayLookupDialog(entry="", platform="linux", hw_model=None)
    assert "could not be identified" in dlg.kind_label.text()
    dlg.action_buttons[0].click()
    # no correction wording appears as a recommendation
    text = dlg.findChildren(dd.QLabel)
    assert not any("recommended correction" in lab.text().lower() for lab in text)


def test_dialog_separates_the_four_concepts_and_cautions(app):
    dlg = dd.DisplayLookupDialog(entry="x", platform="linux", hw_model=None)
    text = " ".join(lab.text() for lab in dlg.findChildren(dd.QLabel))
    for key in ("lookup.concept.panel", "lookup.concept.emissive", "lookup.concept.mode", "lookup.concept.correction", "lookup.caution"):
        assert lang.getstr(key)[:25] in text
    assert "LCD PFS Phosphor" in text  # the upstream explanation is kept


@pytest.mark.parametrize("code", ["ro", "en", "es"])
def test_all_lookup_strings_exist_in_every_language(app, code):
    for key in [k for k in lang.LDICT["en"] if k.startswith("lookup.")]:
        assert lang.getstr(key, lcode=code) != key, (code, key)
        assert key in lang.LDICT[code], (code, key)


def test_reachable_in_guided_mode(window):
    g = window._guide
    assert g.lookup_btn.text() == lang.getstr("lookup.link") and g.lookup_btn2.text()
    assert g.lookup_btn.objectName() == "display_lookup_button"


def test_reachable_in_advanced_mode_next_to_the_correction_choice(window):
    assert window.display_lookup_btn.text() == lang.getstr("lookup.link")
    window._focus_correction_choice()
    assert window._panels["display_instrument"] is window.stack.currentWidget()


def test_reachable_in_the_correction_creation_window(window):
    from DisplayCAL.ui.colorimeter_correction_window import CreateCorrectionWindow

    w = CreateCorrectionWindow()
    assert w.display_lookup_btn.text() == lang.getstr("lookup.link")
