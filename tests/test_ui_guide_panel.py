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
    assert not guide.model_box.isHidden()
    items = [guide.model_combo.itemText(i) for i in range(guide.model_combo.count())]
    assert any("Calibrite" in t for t in items) and len(items) >= 6
    assert guide.model_combo.currentIndex() == 0  # nothing is preselected
    assert "guide.s1" not in guide.model_hint.text()  # translated, not a raw key


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
    for item in guide._prep.items:
        if item.required:
            guide.prepare._boxes[item.key].setChecked(True)
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
    for item in guide._prep.items:
        if item.required:
            guide.prepare._boxes[item.key].setChecked(True)
    guide._next()
    assert guide._step == 3
    assert guide.start_btn.isEnabled()
    guide.start_btn.click()
    assert started == [1]
    # the run can be cancelled: the last step opens only once a profile exists
    assert guide._step == 3
    guide.on_profile_built()
    assert guide._step == 4


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
    assert guide.model_box.isHidden()


def test_finish_page_without_profile_says_so(guide):
    guide.refresh()
    assert guide.profile_state.text()
    assert "guide." not in guide.profile_state.text()


def test_rescan_is_asynchronous_and_single_flight(window, monkeypatch):
    import threading
    import time

    started = []
    gate = threading.Event()

    def slow(self, *a, **k):
        started.append(1)
        gate.wait(5)
        self.displays = ["D1"]
        self.instruments = ["ColorHug2"]

    monkeypatch.setattr(type(window.worker), "enumerate_displays_and_ports", slow)
    window.detect_displays_and_ports_btn_handler()
    assert window._busy
    # A second request while one runs must not start another scan.
    window.detect_displays_and_ports_btn_handler()
    window.detect_displays_and_ports_btn_handler()
    assert not window.detect_displays_and_ports_btn.isEnabled()
    gate.set()
    deadline = time.time() + 5
    while window._busy and time.time() < deadline:
        window.window().repaint()
        from qtpy.QtWidgets import QApplication

        QApplication.processEvents()
        time.sleep(0.01)
    assert not window._busy
    assert started == [1]
    assert window.display_ctrl.count() == 1
    assert window.detect_displays_and_ports_btn.isEnabled()


def _confirm_everything(guide, window, monkeypatch, goal="photo"):
    monkeypatch.setattr(window, "_load_calibration_file", lambda *a, **k: None)
    guide._next()
    guide.goal_buttons[goal].setChecked(True)
    guide._next()


def test_nothing_in_preparation_is_ticked_for_the_user(guide, window, monkeypatch):
    _confirm_everything(guide, window, monkeypatch)
    assert all(not cb.isChecked() for cb in guide.prepare._boxes.values())
    assert not guide._prep.complete
    assert guide.start_btn.isEnabled() is False


def test_ready_message_claims_only_what_is_demonstrated(guide):
    text = guide.action_label.text()
    assert "Continue with your goal and the preparation" in text
    assert "everything" not in text.lower()


def test_model_choice_drives_the_placement_steps_without_touching_measurement(
    guide, window
):
    window.comport_ctrl.setCurrentIndex(0)  # i1 DisplayPro family
    guide.refresh()
    mode_before = window.measurement_mode_ctrl.currentIndex()
    cfg_before = window.get_measurement_mode()
    assert not guide.prepare.player._steps == []
    assert "diffuser" not in guide.prepare.player._steps
    idx = guide.model_combo.findData("Calibrite ColorChecker Display / Pro / Plus")
    guide.model_combo.setCurrentIndex(idx)
    assert "diffuser" in guide.prepare.player._steps
    assert "tilt" not in guide.prepare.player._steps
    assert window.measurement_mode_ctrl.currentIndex() == mode_before
    assert window.get_measurement_mode() == cfg_before


def test_start_summary_lists_evidence_kinds(guide, window, monkeypatch):
    _confirm_everything(guide, window, monkeypatch)
    for cb in guide.prepare._boxes.values():
        cb.setChecked(True)
    guide._next()
    text = " ".join(
        guide.summary_lay.itemAt(i).widget().text()
        for i in range(guide.summary_lay.count())
    )
    assert "detected by the system" in text
    assert "not verified" in text  # model of the shared identifier is unconfirmed
    assert "confirmed by you" in text


def test_stop_motion_before_start(guide, window, monkeypatch):
    started = []
    monkeypatch.setattr(window, "guided_primary_action", lambda: lambda: started.append(1))
    _confirm_everything(guide, window, monkeypatch)
    for cb in guide.prepare._boxes.values():
        cb.setChecked(True)
    guide._next()
    guide.prepare.player.autoplay_once()
    guide.start_btn.click()
    assert started == [1]
    assert not guide.prepare.player.is_playing()
