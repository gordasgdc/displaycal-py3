"""Headless tests for the Qt measurement-report window.

Exercise ``DisplayCAL.ui.measurement_report.ReportWindow`` under the shared
offscreen ``QApplication``: the config-driven TRC controls, the slider/spin
sync, the fields chooser, and the deferred-action signals. No display, Argyll or
instrument is needed. See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 5+,
measurement-report window).
"""

import os

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL import config  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    config.initcfg()
    lang.init()
    lang.update_defaults()
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp):
    """Create a fresh ReportWindow with config isolated per test.

    Constructing the window and exercising its handlers writes to the global
    ``config.CFG``; snapshot and restore it so these tests don't leak state into
    the rest of the suite (e.g. ``test_worker``).
    """
    from DisplayCAL.ui.measurement_report import ReportWindow

    saved = dict(config.CFG["Default"])
    win = ReportWindow()
    try:
        yield win
    finally:
        win.close()
        config.CFG["Default"] = saved


class TestConstruction:
    def test_expected_controls_exist(self, window):
        for attr in (
            "chart_ctrl",
            "fields_ctrl",
            "chart_btn",
            "chart_patches_amount",
            "simulate_whitepoint_cb",
            "simulate_whitepoint_relative_cb",
            "simulation_profile_cb",
            "simulation_profile_ctrl",
            "use_simulation_profile_as_output_cb",
            "enable_3dlut_cb",
            "apply_none_ctrl",
            "apply_black_offset_ctrl",
            "apply_trc_ctrl",
            "mr_trc_ctrl",
            "mr_trc_gamma_ctrl",
            "mr_trc_gamma_type_ctrl",
            "mr_black_output_offset_ctrl",
            "mr_black_output_offset_intctrl",
            "devlink_profile_cb",
            "devlink_profile_ctrl",
            "output_profile_ctrl",
            "output_profile_current_btn",
            "measurement_report_btn",
        ):
            assert hasattr(window, attr), attr

    def test_fields_chooser_defaults(self, window):
        # Default is populated from the loaded chart (RGB-based reference).
        items = [window.fields_ctrl.itemText(i) for i in range(window.fields_ctrl.count())]
        assert items  # non-empty
        assert all(v in ("CMYK", "LAB", "RGB", "XYZ") for v in items)

    def test_trc_chooser_populated(self, window):
        items = [window.mr_trc_ctrl.itemText(i) for i in range(window.mr_trc_ctrl.count())]
        assert len(items) == 3


class TestTrcControls:
    def test_select_gamma_22_sets_config(self, window):
        window.mr_trc_ctrl.setCurrentIndex(0)
        window.mr_trc_ctrl_handler()
        assert config.getcfg("measurement_report.trc_gamma") == 2.2
        assert config.getcfg("measurement_report.trc_gamma_type") == "b"
        assert config.getcfg("measurement_report.trc_output_offset") == 1.0

    def test_select_bt1886_sets_config(self, window):
        window.mr_trc_ctrl.setCurrentIndex(1)
        window.mr_trc_ctrl_handler()
        assert config.getcfg("measurement_report.trc_gamma") == 2.4
        assert config.getcfg("measurement_report.trc_gamma_type") == "B"
        assert config.getcfg("measurement_report.trc_output_offset") == 0.0

    def test_update_trc_control_reflects_bt1886(self, window):
        config.setcfg("measurement_report.trc_gamma", 2.4)
        config.setcfg("measurement_report.trc_gamma_type", "B")
        config.setcfg("measurement_report.trc_output_offset", 0.0)
        window.mr_update_trc_control()
        assert window.mr_trc_ctrl.currentIndex() == 1

    def test_update_trc_control_reflects_custom(self, window):
        config.setcfg("measurement_report.trc_gamma", 2.6)
        config.setcfg("measurement_report.trc_gamma_type", "B")
        config.setcfg("measurement_report.trc_output_offset", 0.5)
        window.mr_update_trc_control()
        assert window.mr_trc_ctrl.currentIndex() == 2

    def test_gamma_type_handler_sets_config(self, window):
        window.mr_trc_gamma_type_ctrl.setCurrentIndex(0)  # relative -> "b"
        window.mr_trc_gamma_type_ctrl_handler()
        assert config.getcfg("measurement_report.trc_gamma_type") == "b"


class TestBlackOffset:
    def test_slider_syncs_spin_and_config(self, window):
        window.mr_black_output_offset_ctrl.setValue(25)
        assert window.mr_black_output_offset_intctrl.value() == 25
        assert config.getcfg("measurement_report.trc_output_offset") == 0.25

    def test_spin_syncs_slider_and_config(self, window):
        window.mr_black_output_offset_intctrl.setValue(40)
        assert window.mr_black_output_offset_ctrl.value() == 40
        assert config.getcfg("measurement_report.trc_output_offset") == 0.40


class TestFields:
    def test_fields_handler_persists_selection(self, window):
        window.fields_ctrl.clear()
        window.fields_ctrl.addItems(["RGB", "XYZ"])
        window.fields_ctrl.setCurrentIndex(1)
        window.fields_ctrl_handler(None)
        assert config.getcfg("measurement_report.chart.fields") == "XYZ"


class TestSignals:
    def test_measure_button_emits_request(self, window):
        received = []
        window.measure_requested.connect(lambda: received.append(True))
        # The button is disabled until the config is valid; enable it so the
        # click reaches the signal (we are testing the wiring, not enablement).
        window.measurement_report_btn.setEnabled(True)
        window.measurement_report_btn.click()
        assert received == [True]

    def test_chart_button_emits_edit_request(self, window):
        received = []
        window.edit_chart_requested.connect(lambda: received.append(True))
        window.chart_btn.click()
        assert received == [True]
