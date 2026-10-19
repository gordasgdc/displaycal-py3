"""Tests for the guided calibration panel (offscreen Qt, stubbed worker)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")
pytest.importorskip("qtpy")

# Reuse the stubbed-worker window fixtures of the main-window tests.
from test_ui_main_window import _init_config, qapp, stub_worker, window  # noqa: E402,F401

from DisplayCAL import guide_model as gm  # noqa: E402
from DisplayCAL.ui import guide_panel  # noqa: E402


@pytest.fixture
def guide(window, monkeypatch):
    monkeypatch.setattr(guide_panel, "check_argyll_bin", lambda *a, **k: True)
    window._guide.refresh()
    return window._guide


def test_guide_is_first_and_default_tab(window):
    assert next(iter(window._tab_buttons)) == "guide"
    assert window.stack.currentWidget() is window._panels["guide"]


def test_action_bar_hidden_on_guide_and_shown_elsewhere(window):
    window._select_tab("guide")
    assert window._button_bar_widget.isHidden()
    window._select_tab("calibration")
    assert not window._button_bar_widget.isHidden()


def test_advanced_tabs_all_still_reachable(window):
    for key in ("display_instrument", "calibration", "profiling", "verification"):
        window._select_tab(key)
        assert window.stack.currentWidget() is window._panels[key]


def test_mirrors_follow_the_window_selectors(guide, window):
    assert guide.monitor_combo.count() == window.display_ctrl.count() == 2
    assert guide.instrument_combo.count() == window.comport_ctrl.count() == 2
    guide.instrument_combo.setCurrentIndex(1)
    assert window.comport_ctrl.currentIndex() == 1


def test_ready_state_with_devices(guide):
    assert guide._readiness().ok
    assert guide.next_btn.isEnabled()


def test_not_ready_without_instrument_explains_and_blocks(guide, window):
    window.worker.instruments = []
    guide.refresh()
    assert not guide._readiness().ok
    assert not guide.next_btn.isEnabled()
    assert guide.gate_label.text()
    assert not guide.start_btn.isEnabled()


def test_not_ready_without_argyll(guide, monkeypatch):
    monkeypatch.setattr(guide_panel, "check_argyll_bin", lambda *a, **k: False)
    guide.refresh()
    assert guide._readiness().status == gm.NO_ARGYLL


def test_shared_identifier_asks_user_to_confirm_model(guide, window):
    window.comport_ctrl.setCurrentIndex(0)  # i1 DisplayPro, ColorMunki Display
    guide.refresh()
    assert len(guide.candidates_group.buttons()) >= 4
    assert "Calibrite" in " ".join(b.text() for b in guide.candidates_group.buttons())
    assert "guide.s1" not in guide.ident_info.text()  # translated, not a raw key


def test_cannot_skip_ahead_before_requirements(guide):
    guide.go(2)  # not reached yet
    assert guide._step == 0
    guide._next()
    assert guide._step == 1
    assert not guide.next_btn.isEnabled()  # no goal chosen


def test_choosing_a_goal_loads_its_preset(guide, window, monkeypatch):
    calls = []
    monkeypatch.setattr(
        window, "_load_calibration_file", lambda path, silent=False: calls.append(path)
    )
    guide._next()
    guide.goal_buttons["photo"].setChecked(True)
    assert calls and calls[0].endswith("photo.icc")
    assert guide._goal == "photo"
    assert guide.next_btn.isEnabled()


def test_preparation_gates_progress(guide, monkeypatch, window):
    monkeypatch.setattr(window, "_load_calibration_file", lambda *a, **k: None)
    guide._next()
    guide.goal_buttons["video"].setChecked(True)
    guide._next()
    assert guide._step == 2
    assert not guide.next_btn.isEnabled()
    for item in gm.PREPARATION:
        if item.required:
            guide.prep_boxes[item.key].setChecked(True)
    assert guide.next_btn.isEnabled()


def test_start_button_requires_everything_then_runs_primary_action(
    guide, monkeypatch, window
):
    monkeypatch.setattr(window, "_load_calibration_file", lambda *a, **k: None)
    started = []
    monkeypatch.setattr(
        window, "guided_primary_action", lambda: lambda: started.append(1)
    )
    guide._next()
    guide.goal_buttons["office_web"].setChecked(True)
    guide._next()
    for item in gm.PREPARATION:
        if item.required:
            guide.prep_boxes[item.key].setChecked(True)
    guide._next()
    assert guide._step == 3
    assert guide.start_btn.isEnabled()
    guide.start_btn.click()
    assert started == [1]


def test_primary_action_matches_action_bar_rule(window):
    handler = window.guided_primary_action()
    assert handler in (
        window.calibrate_and_profile_btn_handler,
        window.calibrate_btn_handler,
        window.profile_btn_handler,
    )


def test_unknown_instrument_is_not_guessed(guide, window):
    window.worker.instruments = ["Totally New Meter"]
    window.update_comports()
    guide.refresh()
    assert "Totally New Meter" in guide.ident_title.text()
    assert guide.candidates_group.buttons() == []


def test_finish_page_without_profile_says_so(guide):
    guide.refresh()
    assert guide.profile_state.text()
    assert "guide." not in guide.profile_state.text()
