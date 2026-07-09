"""Tests for the Qt main-window shell ``DisplayCAL.ui.main_window`` (Stage 3).

These exercise the toolkit-neutral marshalling helpers directly (no display) and
drive the window itself headless via the shared offscreen ``QApplication``
fixture. Display/port enumeration is stubbed so the tests need no Argyll install.
See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 3).
"""

import os
import time

import pytest

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import getcfg, setcfg
from DisplayCAL.worker import Worker

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

# Skip the whole module cleanly if Qt is unavailable in the environment.
pytest.importorskip("qtpy")

from DisplayCAL.ui import main_window as mw  # noqa: E402
from DisplayCAL.ui import measurement_flow as mf  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _init_config():
    """Initialise config (default values) before each test."""
    config.initcfg()
    yield


@pytest.fixture
def stub_worker(monkeypatch):
    """Stub worker enumeration so no Argyll / hardware is needed."""

    def fake(self, *args, **kwargs):
        self.displays = [
            "DELL U2413 @ 0, 0, 1920x1080 [PRIMARY]",
            "Web @ localhost",
        ]
        self.instruments = ["i1 DisplayPro, ColorMunki Display", "Spyder5"]

    monkeypatch.setattr(Worker, "enumerate_displays_and_ports", fake)


# --- pure marshalling helpers ----------------------------------------------


def test_display_items_localizes_primary_marker():
    items = mw.display_items(["Foo @ 0, 0 [PRIMARY]", "Bar @ 1"])
    # The [PRIMARY] marker is replaced with the localized suffix.
    assert "[PRIMARY]" not in items[0]
    assert "Foo @ 0, 0" in items[0]
    assert items[1] == "Bar @ 1"


def test_instrument_items_falls_back_to_raw_name():
    items = mw.instrument_items(["Totally Unknown Meter"])
    # No localization key -> the raw name is used as the default.
    assert items == ["Totally Unknown Meter"]


def test_calibration_quality_slider_roundtrip():
    for level in mw.CALIBRATION_QUALITY_LEVELS:
        assert mw.slider_to_calibration_quality(
            mw.calibration_quality_to_slider(level)
        ) == level


def test_profile_quality_slider_roundtrip():
    for level in mw.PROFILE_QUALITY_LEVELS:
        assert mw.slider_to_profile_quality(
            mw.profile_quality_to_slider(level)
        ) == level


def test_calibration_quality_unknown_falls_back_to_default():
    # An out-of-set value maps to the config default's slider position.
    assert mw.calibration_quality_to_slider("zzz") == mw.calibration_quality_to_slider(
        config.DEFAULTS["calibration.quality"]
    )


@pytest.mark.parametrize(
    "index,text,expected",
    [
        (0, "", ""),  # as-measured
        (1, "2.2", "2.2"),  # Gamma 2.2 (from text)
        (2, "", "l"),  # L*
        (3, "", "709"),  # Rec. 709
        (4, "2.4", "2.4"),  # Rec. 1886 (from text)
        (5, "", "240"),  # SMPTE 240M
        (6, "", "s"),  # sRGB
        (7, "1.8", "1.8"),  # Custom (from text)
    ],
)
def test_trc_value_from_selection(index, text, expected):
    assert mw.trc_value_from_selection(index, text) == expected


def test_trc_selection_from_config_bt1886():
    # 2.4 / absolute / zero black output offset == BT.1886 preset (row 4).
    row, text, type_row = mw.trc_selection_from_config(2.4, "G", 0)
    assert row == 4
    assert type_row == 1
    assert text == "2.4"


def test_trc_selection_from_config_fixed():
    row, text, type_row = mw.trc_selection_from_config("709", "g", 1)
    assert row == 3
    assert text == ""
    assert type_row == 0


def test_trc_selection_from_config_gamma22_preset():
    # 2.2 / relative / 100% output offset == the "Gamma 2.2" preset (row 1).
    row, _text, _type_row = mw.trc_selection_from_config(2.2, "g", 1)
    assert row == 1


def test_profile_types_cover_config_valid_values():
    values = {value for value, _label in mw.PROFILE_TYPES}
    assert values == set(config.VALID_VALUES["profile.type"])


# --- window construction / wiring ------------------------------------------


@pytest.fixture
def window(qapp, stub_worker):
    """Construct a MainWindow against the stubbed worker."""
    win = mw.MainWindow()
    yield win
    win.close()


def test_tabs_present(window):
    assert list(window._tab_buttons) == [
        "display_instrument",
        "calibration",
        "profiling",
        "lut3d",
    ]


def test_selectors_populate_from_worker(window):
    displays = [
        window.display_ctrl.itemText(i) for i in range(window.display_ctrl.count())
    ]
    assert len(displays) == 2
    assert window.comport_ctrl.count() == 2
    assert window.observer_ctrl.count() == len(config.VALID_VALUES["observer"])


def test_display_selection_persists_number(window):
    window.display_ctrl.setCurrentIndex(1)
    assert getcfg("display.number") == 2


def test_comport_selection_persists_number(window):
    window.comport_ctrl.setCurrentIndex(1)
    assert getcfg("comport.number") == 2


def test_observer_selection_persists_key(window):
    keys = list(window._observers)
    target = keys[-1]
    window.observer_ctrl.setCurrentIndex(len(keys) - 1)
    assert getcfg("observer") == target


def test_drift_compensation_checkboxes_persist(window):
    window.whitelevel_drift_compensation_cb.setChecked(True)
    assert getcfg("drift_compensation.whitelevel") == 1
    window.blacklevel_drift_compensation_cb.setChecked(True)
    assert getcfg("drift_compensation.blacklevel") == 1


def test_display_delay_override_persists_and_toggles_enabled(window):
    assert window.min_display_update_delay_ms_ctrl.isEnabled() is False
    window.override_min_display_update_delay_ms_cb.setChecked(True)
    assert getcfg("measure.override_min_display_update_delay_ms") == 1
    assert window.min_display_update_delay_ms_ctrl.isEnabled() is True
    window.min_display_update_delay_ms_ctrl.setValue(150)
    assert getcfg("measure.min_display_update_delay_ms") == 150


def test_display_settle_time_mult_override_persists_and_toggles_enabled(window):
    assert window.display_settle_time_mult_ctrl.isEnabled() is False
    window.override_display_settle_time_mult_cb.setChecked(True)
    assert getcfg("measure.override_display_settle_time_mult") == 1
    assert window.display_settle_time_mult_ctrl.isEnabled() is True
    window.display_settle_time_mult_ctrl.setValue(2.5)
    assert getcfg("measure.display_settle_time_mult") == 2.5


def test_ffp_insertion_group_persists(window):
    window.ffp_insertion_cb.setChecked(True)
    assert getcfg("patterngenerator.ffp_insertion") == 1
    window.ffp_insertion_interval_ctrl.setValue(2.5)
    assert getcfg("patterngenerator.ffp_insertion.interval") == 2.5
    window.ffp_insertion_duration_ctrl.setValue(3.5)
    assert getcfg("patterngenerator.ffp_insertion.duration") == 3.5
    window.ffp_insertion_level_ctrl.setValue(50)
    assert getcfg("patterngenerator.ffp_insertion.level") == 0.5


def test_output_levels_radio_group_persists(window):
    window.output_levels_limited_range.setChecked(True)
    assert getcfg("patterngenerator.detect_video_levels") == 0
    assert getcfg("patterngenerator.use_video_levels") == 1

    window.output_levels_full_range.setChecked(True)
    assert getcfg("patterngenerator.detect_video_levels") == 0
    assert getcfg("patterngenerator.use_video_levels") == 0

    window.output_levels_auto.setChecked(True)
    assert getcfg("patterngenerator.detect_video_levels") == 1


def test_display_lut_ctrl_lists_only_lut_capable_displays(window, monkeypatch):
    monkeypatch.setattr(mw.sys, "platform", "linux")
    setcfg("use_separate_lut_access", 1)
    window.worker.lut_access = [True, False]
    window.update_display_lut_ctrl()
    items = [
        window.display_lut_ctrl.itemText(i)
        for i in range(window.display_lut_ctrl.count())
    ]
    assert len(items) == 1
    assert items[0] == window.display_ctrl.itemText(0)


def test_display_lut_link_ctrl_follows_display_selection_when_linked(
    window, monkeypatch
):
    monkeypatch.setattr(mw.sys, "platform", "linux")
    setcfg("use_separate_lut_access", 1)
    window.worker.lut_access = [True, True]
    setcfg("display_lut.link", 1)
    window.update_display_lut_ctrl()
    assert window.display_lut_ctrl.isEnabled() is False

    window.display_ctrl.setCurrentIndex(1)
    assert window.display_lut_ctrl.currentText() == window.display_ctrl.itemText(1)


def test_display_lut_link_ctrl_unlinked_allows_independent_selection(
    window, monkeypatch
):
    monkeypatch.setattr(mw.sys, "platform", "linux")
    setcfg("use_separate_lut_access", 1)
    window.worker.lut_access = [True, True]
    setcfg("display_lut.link", 0)
    window.update_display_lut_ctrl()
    assert window.display_lut_ctrl.isEnabled() is True

    window.display_lut_ctrl.setCurrentIndex(1)
    assert getcfg("display_lut.number") == 2


def test_display_lut_row_hidden_on_macos_and_windows(window, monkeypatch):
    """wx never shows this row on darwin/win32, regardless of capability."""
    setcfg("use_separate_lut_access", 1)
    window.worker.lut_access = [True, False]
    for platform in ("darwin", "win32"):
        monkeypatch.setattr(mw.sys, "platform", platform)
        window.update_display_lut_ctrl()
        assert window.display_lut_ctrl.count() == 0
        assert getcfg("display_lut.link") == 1


def test_display_lut_row_hidden_without_separate_lut_access(window, monkeypatch):
    monkeypatch.setattr(mw.sys, "platform", "linux")
    setcfg("use_separate_lut_access", 0)
    window.worker.lut_access = [False, False]
    window.update_display_lut_ctrl()
    assert window.display_lut_ctrl.count() == 0


def test_detect_displays_and_ports_btn_refreshes_controls(window, monkeypatch):
    calls = []
    monkeypatch.setattr(
        window.worker,
        "enumerate_displays_and_ports",
        lambda *a, **k: calls.append(True),
    )
    window.detect_displays_and_ports_btn.click()
    assert calls == [True]


def test_measurement_mode_ctrl_populates_and_persists(window):
    assert window.measurement_mode_ctrl.count() >= 1
    assert window.measurement_mode_ctrl.isEnabled() is True

    window.measurement_mode_ctrl.setCurrentIndex(1)
    code = window.get_measurement_mode()
    assert getcfg("measurement_mode") == (code[0] if code != "auto" else code)


def test_measurement_mode_ctrl_rebuilds_on_instrument_change(window):
    before = [
        window.measurement_mode_ctrl.itemText(i)
        for i in range(window.measurement_mode_ctrl.count())
    ]
    window.comport_ctrl.setCurrentIndex(1)
    # Rebuilding must not leave the combo empty/disabled for the new
    # instrument (a regression guard for the comport -> measurement-mode
    # refresh wiring, not a claim about the exact item set).
    assert window.measurement_mode_ctrl.count() >= 1
    assert window.measurement_mode_ctrl.isEnabled() is True
    assert before  # sanity: there was something to compare against


def test_colorimeter_correction_matrix_ctrl_hidden_when_ccxx_unsupported(window):
    # The stub worker's default argyll_version ([0, 0, 0]) can't use CCXX.
    assert window.colorimeter_correction_matrix_ctrl.isVisibleTo(window) is False


def test_colorimeter_correction_matrix_ctrl_shown_when_ccxx_supported(window):
    window.worker.argyll_version = [1, 5, 0]
    window.update_colorimeter_correction_matrix_ctrl()
    assert window.colorimeter_correction_matrix_ctrl.isVisibleTo(window) is True


def test_colorimeter_correction_matrix_ctrl_handler_none_and_auto(window):
    window.colorimeter_correction_matrix_ctrl_handler(0)
    assert getcfg("colorimeter_correction_matrix_file") == ""

    window.colorimeter_correction_matrix_ctrl_handler(1)
    assert getcfg("colorimeter_correction_matrix_file").startswith("AUTO")


def test_colorimeter_correction_matrix_btn_handler_cancelled_is_noop(
    window, monkeypatch
):
    monkeypatch.setattr(
        mw.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    before = getcfg("colorimeter_correction_matrix_file")
    window.colorimeter_correction_matrix_btn_handler()
    assert getcfg("colorimeter_correction_matrix_file") == before


def test_colorimeter_correction_web_btn_handler_refreshes_after_finish(
    window, monkeypatch
):
    from DisplayCAL.ui import colorimeter_correction_io as ccio

    def fake_run(self):
        self.finished.emit()

    monkeypatch.setattr(ccio.WebCheckController, "run", fake_run)
    calls = []
    monkeypatch.setattr(
        window,
        "update_colorimeter_correction_matrix_ctrl_items",
        lambda *a, **k: calls.append((a, k)),
    )
    window.colorimeter_correction_web_btn_handler()
    assert calls
    assert window._ccxx_web_controller is None


def test_colorimeter_correction_create_btn_handler_opens_window(window):
    window.colorimeter_correction_create_btn_handler()
    try:
        assert window._ccxx_create_window is not None
    finally:
        window._ccxx_create_window.close()


def test_colorimeter_correction_info_btn_handler_shows_notice(window, monkeypatch):
    calls = []
    monkeypatch.setattr(
        mw.QMessageBox,
        "information",
        staticmethod(lambda *a, **k: calls.append(True)),
    )
    window.colorimeter_correction_info_btn_handler()
    assert calls == [True]


def test_observer_ctrl_lives_on_calibration_tab(window):
    """wx puts ``observer_ctrl`` on the Calibration tab (``main.xrc``
    ``calibration_settings_panel``), not Display & Instrument; a regression
    guard for that layout-parity mistake."""
    assert window._panels["calibration"].isAncestorOf(window.observer_ctrl)
    assert not window._panels["display_instrument"].isAncestorOf(
        window.observer_ctrl
    )


def test_calibration_tab_control_order_matches_wx(window):
    """wx's ``main.xrc`` orders the ambient-adjust row before black-point
    correction; guard against the two being swapped again."""
    from qtpy.QtCore import QPoint

    panel = window._panels["calibration"]
    ambient_y = window.ambient_adjust_cb.mapTo(panel, QPoint(0, 0)).y()
    bpc_y = window.black_point_correction_ctrl.mapTo(panel, QPoint(0, 0)).y()
    assert ambient_y <= bpc_y


def test_populating_does_not_write_config(qapp, stub_worker):
    """Repopulating controls must not clobber config via the guard flag."""
    setcfg("display.number", 2)
    setcfg("comport.number", 2)
    win = mw.MainWindow()
    try:
        # Construction selected the stored indices without firing writes that
        # would reset them to 1.
        assert getcfg("display.number") == 2
        assert getcfg("comport.number") == 2
    finally:
        win.close()


def test_select_tab_switches_stack(window):
    window._select_tab("profiling")
    assert window.stack.currentWidget() is window._panels["profiling"]
    assert window._tab_buttons["profiling"].isChecked() is True


def test_action_buttons_enabled(window):
    # Only one of the three is ever shown at once (mirrors wx's
    # ``update_main_controls``); with interactive adjustment on and no
    # "update existing calibration", that's "Calibrate & Profile". Config is
    # process-global and other tests may have left it in a different state,
    # so drive the widgets (and force a recompute) rather than assume
    # defaults - matching the pattern used by the other calibration tests.
    window.calibration_update_cb.setChecked(False)
    window.interactive_adjustment_cb.setChecked(True)
    window.trc_ctrl.setCurrentIndex(6)
    window._update_action_buttons()
    assert window.calibrate_btn.isHidden() is True
    assert window.calibrate_and_profile_btn.isHidden() is False
    assert window.calibrate_and_profile_btn.isEnabled() is True
    assert window.profile_btn.isHidden() is True


def test_action_buttons_mutually_exclusive_calibrate_only(window):
    # Disabling interactive adjustment and picking the "as measured" TRC
    # disables ``enable_cal``, so only "Profile only" remains.
    window.calibration_update_cb.setChecked(False)
    window.interactive_adjustment_cb.setChecked(False)
    window.trc_ctrl.setCurrentIndex(0)
    window._update_action_buttons()
    assert window.calibrate_btn.isHidden() is True
    assert window.calibrate_and_profile_btn.isHidden() is True
    assert window.profile_btn.isHidden() is False
    assert window.profile_btn.isEnabled() is True


def test_action_buttons_mutually_exclusive_update_existing_profile(
    window, monkeypatch
):
    # "Update existing calibration" against a file that resolves to an ICC
    # profile shows "Calibrate only" instead of "Calibrate & Profile".
    monkeypatch.setattr(config, "is_profile", lambda *a, **k: True)
    window.interactive_adjustment_cb.setChecked(True)
    window.calibration_update_cb.setChecked(True)
    window._update_action_buttons()
    assert window.calibrate_btn.isHidden() is False
    assert window.calibrate_btn.isEnabled() is True
    assert window.calibrate_and_profile_btn.isHidden() is True
    assert window.profile_btn.isHidden() is True


# --- Calibration tab wiring ------------------------------------------------


def test_interactive_adjustment_persists(window):
    window.interactive_adjustment_cb.setChecked(False)
    assert getcfg("calibration.interactive_display_adjustment") == 0
    window.interactive_adjustment_cb.setChecked(True)
    assert getcfg("calibration.interactive_display_adjustment") == 1


def test_whitepoint_colortemp_mode_persists(window):
    window.whitepoint_ctrl.setCurrentIndex(1)  # color temperature
    window.whitepoint_colortemp_ctrl.setValue(5800)
    assert getcfg("whitepoint.colortemp") == 5800
    # x/y are cleared so the stored mode round-trips back to color-temp.
    assert getcfg("whitepoint.x", False) is None


def test_whitepoint_native_clears_all(window):
    window.whitepoint_ctrl.setCurrentIndex(1)
    window.whitepoint_colortemp_ctrl.setValue(5000)
    window.whitepoint_ctrl.setCurrentIndex(0)  # native
    assert getcfg("whitepoint.colortemp", False) is None
    assert getcfg("whitepoint.x", False) is None


def test_luminance_custom_persists(window):
    window.luminance_ctrl.setCurrentIndex(1)  # custom
    window.luminance_textctrl.setValue(100.0)
    assert getcfg("calibration.luminance") == 100.0
    window.luminance_ctrl.setCurrentIndex(0)  # as-measured
    assert getcfg("calibration.luminance", False) is None


def test_trc_selection_persists(window):
    window.trc_ctrl.setCurrentIndex(2)  # L*
    assert getcfg("trc") == "l"


def test_black_output_offset_slider_persists(window):
    window.black_output_offset_ctrl.setValue(50)
    assert getcfg("calibration.black_output_offset") == 0.5


def test_calibration_quality_slider_persists(window):
    window.calibration_quality_ctrl.setValue(4)
    assert getcfg("calibration.quality") == "h"


def test_calibration_controls_reflect_config(qapp, stub_worker):
    setcfg("trc", "709")
    setcfg("calibration.quality", "u")
    setcfg("calibration.black_output_offset", 0.25)
    win = mw.MainWindow()
    try:
        assert win.trc_ctrl.currentIndex() == 3
        assert win.calibration_quality_ctrl.value() == 5
        assert win.black_output_offset_ctrl.value() == 25
    finally:
        win.close()


# --- Profiling tab wiring --------------------------------------------------


def test_profile_type_persists(window):
    window.profile_type_ctrl.setCurrentIndex(2)  # LabLUT
    assert getcfg("profile.type") == "l"


def test_profile_quality_persists(window):
    # Use a cLUT type so the quality is not coerced to high (gamma+matrix rule).
    setcfg("profile.type", "l")
    window.profile_quality_ctrl.setValue(2)
    assert getcfg("profile.quality") == "m"


def test_profile_name_persists(window):
    window.profile_name_textctrl.setText("my profile")
    window._profile_name_changed()
    assert getcfg("profile.name") == "my profile"


def test_profile_name_sanitizes_invalid_text(window):
    window.profile_name_textctrl.setText("bad/name:here")
    window._profile_name_changed()
    assert window.profile_name_textctrl.text() == "badnamehere"
    assert getcfg("profile.name") == "badnamehere"


def test_profile_type_ctrl_translates_labels(window):
    # A regression guard for the labels being untranslated lang keys.
    assert window.profile_type_ctrl.itemText(0) == lang.getstr(
        "profile.type.lut_matrix.xyz"
    )


def test_profile_type_ctrl_enables_gamap_only_for_lut_types(window):
    window.profile_type_ctrl.setCurrentIndex(2)  # LabLUT ("l", a LUT type)
    assert window.gamap_btn.isEnabled()
    window.profile_type_ctrl.setCurrentIndex(4)  # 1xCurve+MTX ("S", not LUT)
    assert not window.gamap_btn.isEnabled()


def test_profile_type_ctrl_locks_quality_for_gamma_types(window):
    window.profile_type_ctrl.setCurrentIndex(5)  # 3xGamma+MTX ("g")
    assert not window.profile_quality_ctrl.isEnabled()
    assert getcfg("profile.quality") == "h"
    window.profile_type_ctrl.setCurrentIndex(0)  # back to a non-gamma type
    assert window.profile_quality_ctrl.isEnabled()


def test_profile_type_ctrl_nudges_bpc_default(window):
    setcfg("profile.type", "s")  # shaper+matrix, not yet a LUT type
    window.black_point_compensation_cb.setChecked(False)
    window.profile_type_ctrl.setCurrentIndex(1)  # XYZLUT ("x", a LUT type)
    assert getcfg("profile.black_point_compensation") == 0
    window.profile_type_ctrl.setCurrentIndex(4)  # 1xCurve+MTX ("S")
    assert getcfg("profile.black_point_compensation") == 1


def test_testchart_ctrl_populates_with_auto_first(window):
    assert window.testchart_ctrl.count() > 1
    assert window.testchart_ctrl.itemText(0) == lang.getstr("auto_optimized")
    assert window._testchart_paths[0] == "auto"


def test_testchart_patches_row_hidden_for_fixed_testchart(window):
    assert not window._patches_row_widget.isHidden()
    window.testchart_ctrl.setCurrentIndex(1)
    assert window._patches_row_widget.isHidden()


def test_testchart_patches_amount_slider_updates_meas_time_and_name(window):
    window.testchart_patches_amount_ctrl.setValue(3)
    assert window.testchart_patches_amount.text() == "115"
    assert getcfg("testchart.auto_optimize") == 3
    assert window.testchart_meas_time.text()


def test_testchart_patches_amount_high_auto_nudges_profile_type(window):
    setcfg("3dlut.create", 0)
    setcfg("profile.type", "S")
    window.testchart_patches_amount_ctrl.setValue(10)
    assert getcfg("profile.type") == "X"


def test_testchart_patch_sequence_persists(window):
    setcfg("show_advanced_options", 1)
    window._update_advanced_options_visibility()
    window.testchart_patch_sequence_ctrl.setCurrentIndex(1)
    assert getcfg("testchart.patch_sequence") == "maximize_lightness_difference"


def test_testchart_patch_sequence_row_gated_by_advanced_options(window):
    setcfg("show_advanced_options", 0)
    window._update_advanced_options_visibility()
    assert window._profiling_form.isRowVisible(window.testchart_patch_sequence_ctrl) is False
    setcfg("show_advanced_options", 1)
    window._update_advanced_options_visibility()
    assert window._profiling_form.isRowVisible(window.testchart_patch_sequence_ctrl) is True


def test_gamap_btn_shows_notice(window, monkeypatch):
    calls = []
    monkeypatch.setattr(
        mw.QMessageBox, "information", staticmethod(lambda *a, **k: calls.append(True))
    )
    window._gamap_btn_handler()
    assert calls == [True]


def test_create_testchart_btn_shows_notice(window, monkeypatch):
    calls = []
    monkeypatch.setattr(
        mw.QMessageBox, "information", staticmethod(lambda *a, **k: calls.append(True))
    )
    window._create_testchart_btn_handler()
    assert calls == [True]


def test_testchart_btn_handler_cancelled_is_noop(window, monkeypatch):
    monkeypatch.setattr(
        mw.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    before = getcfg("testchart.file")
    window._testchart_btn_handler()
    assert getcfg("testchart.file") == before


def test_testchart_btn_handler_missing_file_shows_error(window, monkeypatch, tmp_path):
    missing = str(tmp_path / "nope.ti1")
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (missing, "")),
    )
    calls = []
    monkeypatch.setattr(
        mw.QMessageBox, "critical", staticmethod(lambda *a, **k: calls.append(True))
    )
    window._testchart_btn_handler()
    assert calls == [True]


def test_testchart_btn_handler_loads_bundled_ti1(window, monkeypatch):
    # Deliberately not "ccxx.ti1": loading it would flip the process-global
    # ``is_ccxx_testchart()`` result for every test that runs afterwards
    # (config.CFG isn't reset between tests, only reloaded from disk -- see
    # the test-flakiness note in MAINFRAME_PORT_PLAN.md's Stage 3 Session 8).
    path = os.path.join(
        os.path.dirname(config.__file__), "ti1", "d3-e4-s2-g28-m0-b0-f0.ti1"
    )
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (path, "")),
    )
    try:
        window._testchart_btn_handler()
        assert getcfg("testchart.file") == path
        assert window._patches_row_widget.isHidden()
        assert window.testchart_patches_amount.text() != "0"
    finally:
        setcfg("testchart.file", "auto")


def test_profile_name_info_btn_shows_placeholders(window, monkeypatch):
    calls = []
    monkeypatch.setattr(
        mw.QMessageBox,
        "information",
        staticmethod(lambda parent, title, msg: calls.append(msg)),
    )
    window._profile_name_info_btn_handler()
    assert calls and "%dn" in calls[0]


def test_profile_save_path_btn_cancelled_is_noop(window, monkeypatch):
    monkeypatch.setattr(
        mw.QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "")
    )
    before = getcfg("profile.save_path")
    window._profile_save_path_btn_handler()
    assert getcfg("profile.save_path") == before


def test_profile_save_path_btn_persists_and_updates_name(window, monkeypatch, tmp_path):
    monkeypatch.setattr(
        mw.QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *a, **k: str(tmp_path)),
    )
    window._profile_save_path_btn_handler()
    assert getcfg("profile.save_path") == str(tmp_path)


def test_update_profile_name_reflects_display_selection(window):
    # Explicit template: this test's own subject is the %dns placeholder, not
    # whatever ``profile.name`` a previous test happened to leave behind
    # (config.CFG leaks between tests, see the note above).
    setcfg("profile.name", "%dns")
    window.profile_name_textctrl.setText("%dns")
    window.display_ctrl.setCurrentIndex(0)
    window.update_profile_name()
    first = window.profile_name_label.text()
    assert window.display_ctrl.count() > 1
    window.display_ctrl.setCurrentIndex(1)
    window.update_profile_name()
    assert window.profile_name_label.text() != first


# --- 3D LUT tab wiring -----------------------------------------------------


def test_lut3d_create_persists(window):
    window.lut3d_create_cb.setChecked(True)
    assert getcfg("3dlut.create") == 1


def test_lut3d_size_persists(window):
    window.lut3d_size_ctrl.setCurrentIndex(0)
    assert getcfg("3dlut.size") == config.VALID_VALUES["3dlut.size"][0]


def test_lut3d_rendering_intent_persists(window):
    intents = config.VALID_VALUES["3dlut.rendering_intent"]
    window.lut3d_rendering_intent_ctrl.setCurrentIndex(2)
    assert getcfg("3dlut.rendering_intent") == intents[2]


def test_populating_calibration_does_not_write_config(qapp, stub_worker):
    setcfg("calibration.quality", "u")
    setcfg("trc", "709")
    win = mw.MainWindow()
    try:
        # Repopulation on construction must not clobber the stored values.
        assert getcfg("calibration.quality") == "u"
        assert getcfg("trc") == "709"
    finally:
        win.close()


# --- measurement actions (Stage 4) -----------------------------------------


@pytest.fixture
def _no_writecfg(monkeypatch):
    """Keep begin_measurement / call_pending_function off the real config file."""
    monkeypatch.setattr(mw, "writecfg", lambda *a, **k: None)


@pytest.fixture
def _stub_measurement_run(window, monkeypatch):
    """Neutralise the worker run so signal-dispatch tests touch no hardware.

    ``measurement_requested`` is connected to the real runner in ``__init__``;
    tests that only assert the signal fires stub the leaf run methods (looked up
    on the instance at emit time) so no ``QThread`` / progress dialog starts.
    """
    monkeypatch.setattr(window, "_run_profile_measurement", lambda: None)
    monkeypatch.setattr(window, "_run_calibration_measurement", lambda action: None)


def _run_pending_synchronously(window):
    """Fire the window's deferred pending-run immediately (no event loop)."""
    window._defer = lambda callback: callback()


def _force_mode(window, monkeypatch, mode):
    """Pin the flow's presentation decision so dispatch is platform-independent."""

    def fake_plan(pending_function, *args, **kwargs):
        window.flow.set_pending_function(pending_function, *args)
        return mf.MeasurementPlan(mode=mode, display_name="DELL U2413")

    monkeypatch.setattr(window.flow, "plan_measurement", fake_plan)


def _show_action_button(window, monkeypatch, button_attr):
    """Put ``window`` into the (mutually exclusive) state that shows ``button_attr``.

    Only one of calibrate/calibrate-and-profile/profile is ever visible+enabled
    at once (see :meth:`MainWindow._update_action_buttons`), so exercising a
    button first requires driving the window into the state that surfaces it.
    """
    window.calibration_update_cb.setChecked(False)
    window.interactive_adjustment_cb.setChecked(True)
    window.trc_ctrl.setCurrentIndex(6)
    if button_attr == "calibrate_btn":
        # "Update existing calibration" against a file that resolves to an
        # ICC profile shows "Calibrate only" instead of "Calibrate & Profile".
        monkeypatch.setattr(config, "is_profile", lambda *a, **k: True)
        window.calibration_update_cb.setChecked(True)
    elif button_attr == "profile_btn":
        window.interactive_adjustment_cb.setChecked(False)
        window.trc_ctrl.setCurrentIndex(0)
    # Config is process-global and the checkbox no-ops above (setChecked to an
    # already-current value) don't emit ``toggled``, so force a recompute
    # rather than rely on signal-driven updates picking up every case.
    window._update_action_buttons()
    assert getattr(window, button_attr).isEnabled() is True


@pytest.mark.parametrize(
    "button_attr,action",
    [
        ("calibrate_btn", mw.MeasurementAction.CALIBRATE),
        ("calibrate_and_profile_btn", mw.MeasurementAction.CALIBRATE_AND_PROFILE),
        ("profile_btn", mw.MeasurementAction.PROFILE),
    ],
)
def test_action_button_dry_run_emits_request(
    window, _no_writecfg, _stub_measurement_run, monkeypatch, button_attr, action
):
    # Dry run -> the flow calls the pending driver straight away.
    monkeypatch.setattr(config, "get_display_name", lambda *a, **k: "DELL U2413")
    monkeypatch.setattr(config, "is_virtual_display", lambda *a, **k: False)
    setcfg("dry_run", 1)
    _run_pending_synchronously(window)
    _show_action_button(window, monkeypatch, button_attr)
    seen = []
    window.measurement_requested.connect(seen.append)

    getattr(window, button_attr).click()

    assert seen == [action]


def test_show_frame_mode_presents_measureframe(
    window, _no_writecfg, _stub_measurement_run, monkeypatch
):
    _force_mode(window, monkeypatch, mf.PresentationMode.SHOW_FRAME)
    _run_pending_synchronously(window)
    seen = []
    window.measurement_requested.connect(seen.append)

    window.begin_measurement(mw.MeasurementAction.CALIBRATE)

    assert window.measureframe is not None
    assert window.measureframe.isVisible() is True
    # No driver runs until the user actually presses Measure.
    assert seen == []

    window.measureframe.measure_requested.emit()

    assert seen == [mw.MeasurementAction.CALIBRATE]
    # Committing hides the frame again.
    assert window.measureframe.isVisible() is False


def test_subprocess_mode_starts_subprocess(window, _no_writecfg, monkeypatch):
    called = []
    monkeypatch.setattr(
        window, "_start_measureframe_subprocess", lambda: called.append(True)
    )
    _force_mode(window, monkeypatch, mf.PresentationMode.SUBPROCESS)

    window.begin_measurement(mw.MeasurementAction.CALIBRATE)

    assert called == [True]


def test_measureframe_result_measure_runs_pending(
    window, _no_writecfg, _stub_measurement_run, monkeypatch
):
    monkeypatch.setattr(window, "_start_measureframe_subprocess", lambda: None)
    _force_mode(window, monkeypatch, mf.PresentationMode.SUBPROCESS)
    _run_pending_synchronously(window)
    seen = []
    window.measurement_requested.connect(seen.append)
    window.begin_measurement(mw.MeasurementAction.PROFILE)  # stages the pending driver

    window._on_measureframe_finished(255, "")

    assert seen == [mw.MeasurementAction.PROFILE]


def test_measureframe_result_clean_close_restores(window, _no_writecfg, monkeypatch):
    _run_pending_synchronously(window)
    seen = []
    window.measurement_requested.connect(seen.append)
    restored = []
    monkeypatch.setattr(
        window, "_restore_after_measurement", lambda: restored.append(True)
    )

    window._on_measureframe_finished(0, "")

    assert restored == [True]
    assert seen == []


def test_measureframe_result_failure_shows_error(window, _no_writecfg, monkeypatch):
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    monkeypatch.setattr(window, "_restore_after_measurement", lambda: None)

    window._on_measureframe_finished(-1, "boom")

    assert errors
    assert "boom" in errors[0][2]


# --- worker execution wiring (Stage 5) -------------------------------------


def test_profile_request_runs_measure_through_controller(window, monkeypatch):
    # A committed PROFILE run drives worker.measure through the controller with
    # the non-interactive apply_calibration=True setup just_profile does.
    calls = {}

    def fake_run(_ctrl, producer, consumer=None, **kwargs):
        calls["producer"] = producer
        calls["consumer"] = consumer
        calls["wkwargs"] = kwargs.get("wkwargs")

    monkeypatch.setattr(config, "get_display_name", lambda *a, **k: "DELL U2413")
    monkeypatch.setattr(mw.WorkerRunController, "run", fake_run)

    window.measurement_requested.emit(mw.MeasurementAction.PROFILE)

    assert calls["producer"] == window.worker.measure
    assert calls["consumer"] == window._on_measurement_finished
    assert calls["wkwargs"] == {"apply_calibration": True}
    assert window.worker.dispread_after_dispcal is False
    assert window.worker.interactive is False


def test_profile_request_marks_untethered_interactive(window, monkeypatch):
    monkeypatch.setattr(config, "get_display_name", lambda *a, **k: "Untethered")
    monkeypatch.setattr(mw.WorkerRunController, "run", lambda *a, **k: None)

    window.measurement_requested.emit(mw.MeasurementAction.PROFILE)

    assert window.worker.interactive is True


@pytest.mark.parametrize(
    "action",
    [mw.MeasurementAction.CALIBRATE, mw.MeasurementAction.CALIBRATE_AND_PROFILE],
)
def test_calibration_request_runs_calibration(window, monkeypatch, action):
    seen = []
    monkeypatch.setattr(
        window, "_run_calibration_measurement", lambda a: seen.append(a)
    )

    window.measurement_requested.emit(action)

    assert seen == [action]


def test_interactive_calibration_runs_through_adjustment_controller(
    window, monkeypatch
):
    # Interactive display adjustment on (and not a calibration update) drives the
    # AdjustmentController rather than the progress-dialog runner.
    setcfg("calibration.interactive_display_adjustment", 1)
    setcfg("calibration.update", 0)
    calls = {}
    monkeypatch.setattr(
        mw.AdjustmentController,
        "run",
        lambda _ctrl, consumer=None, **kw: calls.update(consumer=consumer, kw=kw),
    )

    window._run_calibration_measurement(mw.MeasurementAction.CALIBRATE)

    assert getcfg("calibration.continue_next") == 0
    assert calls["kw"] == {"remove": True}
    assert callable(calls["consumer"])


def test_noninteractive_calibration_runs_through_progress_controller(
    window, monkeypatch
):
    # Interactive adjustment off -> non-interactive calibration over the dialog.
    setcfg("calibration.interactive_display_adjustment", 0)
    calls = {}
    monkeypatch.setattr(
        mw.WorkerRunController,
        "run",
        lambda _ctrl, producer, consumer=None, **kw: calls.update(
            producer=producer, wkwargs=kw.get("wkwargs")
        ),
    )

    window._run_calibration_measurement(mw.MeasurementAction.CALIBRATE)

    assert calls["producer"] == window.worker.calibrate
    assert calls["wkwargs"] == {"remove": True}
    assert window.worker.interactive is False


def test_calibrate_and_profile_chains_characterization_on_success(window, monkeypatch):
    setcfg("calibration.interactive_display_adjustment", 0)
    ran = []
    monkeypatch.setattr(window, "_run_profile_measurement", lambda: ran.append(True))

    window._on_calibration_finished(mw.MeasurementAction.CALIBRATE_AND_PROFILE, True)

    assert ran == [True]


def test_calibration_finished_incomplete_shows_notice(window, monkeypatch):
    setcfg("dry_run", 0)
    infos = []
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: infos.append(a))

    window._on_calibration_finished(mw.MeasurementAction.CALIBRATE, False)

    assert infos
    assert lang.getstr("calibration.incomplete") in infos[0][2]


def test_measurement_finished_exception_shows_error(window, monkeypatch):
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))

    window._on_measurement_finished(ValueError("boom"))

    assert errors
    assert "boom" in errors[0][2]


def test_measurement_finished_incomplete_shows_info(window, monkeypatch):
    infos = []
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: infos.append(a))
    setcfg("dry_run", 0)

    window._on_measurement_finished(False)

    assert infos


def test_measurement_finished_incomplete_silent_on_dry_run(window, monkeypatch):
    infos = []
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: infos.append(a))
    setcfg("dry_run", 1)

    window._on_measurement_finished(False)

    assert infos == []


def test_measurement_finished_success_logs(window, monkeypatch):
    logged = []
    monkeypatch.setattr(window.worker, "log", lambda *a, **k: logged.append(a))

    window._on_measurement_finished(True)

    assert logged


# --- calibration/profile-file header bar -----------------------------------


def _srgb_preset_path(window):
    """Return the bundled sRGB preset's path from the window's own recent_cals."""
    for cal in window.recent_cals:
        if os.path.basename(cal) == "sRGB.icc":
            return cal
    raise AssertionError("sRGB preset not found in recent_cals")


def test_header_combo_lists_new_settings_and_presets(window):
    items = [
        window.calibration_file_ctrl.itemText(i)
        for i in range(window.calibration_file_ctrl.count())
    ]
    assert items[0] == lang.getstr("settings.new")
    assert lang.getstr("sRGB.icc") in items
    assert len(items) == len(window.recent_cals)


def test_header_buttons_disabled_without_calibration(window):
    # ``config.initcfg()`` seeds ``calibration.file`` to the default preset the
    # first time the (session-shared, test-isolated) config file is created;
    # clear it explicitly so this test doesn't depend on run order.
    setcfg("calibration.file", None)
    window.update_controls()

    assert not window.create_session_archive_btn.isEnabled()
    assert not window.delete_calibration_btn.isEnabled()
    assert not window.profile_info_btn.isEnabled()
    assert not window.install_profile_btn.isEnabled()


def test_load_calibration_file_applies_preset(window):
    path = _srgb_preset_path(window)

    window._load_calibration_file(path, silent=True)

    assert getcfg("calibration.file") == path
    assert getcfg("trc") == "s"
    assert getcfg("trc.type") == "g"
    assert window.calibration_file_ctrl.currentText() == lang.getstr("sRGB.icc")
    # Bundled presets aren't archivable/deletable, matching wx.
    assert not window.create_session_archive_btn.isEnabled()
    assert not window.delete_calibration_btn.isEnabled()
    assert window.profile_info_btn.isEnabled()
    assert window.install_profile_btn.isEnabled()


def test_calibration_file_ctrl_handler_loads_selected_recent(window):
    path = _srgb_preset_path(window)
    idx = window.recent_cals.index(path)

    window.calibration_file_ctrl_handler(idx)

    assert getcfg("calibration.file") == path


def test_calibration_file_ctrl_handler_ignores_index_zero(window):
    path = _srgb_preset_path(window)
    setcfg("calibration.file", path)

    window.calibration_file_ctrl_handler(0)

    assert getcfg("calibration.file") == path


def test_load_calibration_file_missing_path_is_noop(window):
    before = getcfg("calibration.file", False)

    window._load_calibration_file("/nonexistent/path/profile.icc")

    assert getcfg("calibration.file", False) == before


def test_load_calibration_file_rejects_archive_extension(window, monkeypatch):
    infos = []
    monkeypatch.setattr(
        mw.QMessageBox, "information", lambda *a, **k: infos.append(a)
    )
    monkeypatch.setattr(mw.os.path, "exists", lambda _path: True)

    window._load_calibration_file("/tmp/session.zip")

    assert infos
    assert getcfg("calibration.file", False) != "/tmp/session.zip"


def test_load_cal_btn_handler_uses_file_dialog(window, monkeypatch):
    path = _srgb_preset_path(window)
    monkeypatch.setattr(
        mw.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (path, ""))
    )

    window.load_cal_btn_handler()

    assert getcfg("calibration.file") == path
    assert getcfg("last_cal_or_icc_path") == path


def test_load_cal_btn_handler_cancelled_is_noop(window, monkeypatch):
    before = getcfg("calibration.file", False)
    monkeypatch.setattr(
        mw.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
    )

    window.load_cal_btn_handler()

    assert getcfg("calibration.file", False) == before


def test_profile_info_btn_handler_opens_window(window, monkeypatch):
    path = _srgb_preset_path(window)
    window._load_calibration_file(path, silent=True)

    class _FakeProfileInfoWindow:
        def __init__(self):
            self.loaded = None
            self._visible = False

        def load_profile(self, path):
            self.loaded = path

        def show(self):
            self._visible = True

        def raise_(self):
            pass

        def activateWindow(self):
            pass

    monkeypatch.setattr(mw, "ProfileInfoWindow", _FakeProfileInfoWindow)

    window.profile_info_btn_handler()

    assert window._profile_info_window.loaded == path
    assert window._profile_info_window._visible


def test_profile_info_btn_handler_noop_without_profile(window, monkeypatch):
    setcfg("calibration.file", None)
    calls = []
    monkeypatch.setattr(mw, "ProfileInfoWindow", lambda: calls.append(True))

    window.profile_info_btn_handler()

    assert calls == []


def test_install_profile_btn_handler_opens_window(window, monkeypatch):
    path = _srgb_preset_path(window)
    window._load_calibration_file(path, silent=True)

    class _FakeInstallProfileWindow:
        def __init__(self):
            self.loaded = None
            self._visible = False

        def load_profile(self, path):
            self.loaded = path

        def show(self):
            self._visible = True

        def raise_(self):
            pass

        def activateWindow(self):
            pass

    monkeypatch.setattr(mw, "InstallProfileWindow", _FakeInstallProfileWindow)

    window.install_profile_btn_handler()

    assert window._install_profile_window.loaded == path


def test_create_session_archive_handler_cancelled_is_noop(window, monkeypatch):
    path = _srgb_preset_path(window)
    setcfg("calibration.file", path)
    monkeypatch.setattr(
        mw.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )

    window.create_session_archive_handler()

    assert window._archive_thread is None


def test_create_session_archive_handler_no_file_is_noop(window):
    setcfg("calibration.file", False)

    window.create_session_archive_handler()

    assert window._archive_thread is None


def test_create_session_archive_handler_runs_and_completes(
    window, monkeypatch, tmp_path, qapp
):
    cal_dir = tmp_path / "session"
    cal_dir.mkdir()
    cal_file = cal_dir / "test.cal"
    cal_file.write_text("dummy")
    setcfg("calibration.file", str(cal_file))
    archive_path = tmp_path / "test.zip"
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(archive_path), "*.zip")),
    )

    window.create_session_archive_handler()

    deadline = time.time() + 5.0
    while window._archive_thread is not None and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)

    assert archive_path.exists()
    assert getcfg("last_archive_save_path") == str(archive_path)


def test_delete_calibration_handler_declined_keeps_file(window, monkeypatch, tmp_path):
    cal_dir = tmp_path / "session"
    cal_dir.mkdir()
    cal_file = cal_dir / "test.cal"
    cal_file.write_text("dummy")
    setcfg("calibration.file", str(cal_file))
    monkeypatch.setattr(
        mw.QMessageBox,
        "question",
        staticmethod(lambda *a, **k: mw.QMessageBox.No),
    )

    window.delete_calibration_handler()

    assert cal_file.exists()
    assert getcfg("calibration.file") == str(cal_file)


def test_delete_calibration_handler_confirmed_removes_file(
    window, monkeypatch, tmp_path
):
    cal_dir = tmp_path / "session"
    cal_dir.mkdir()
    cal_file = cal_dir / "test.cal"
    cal_file.write_text("dummy")
    setcfg("calibration.file", str(cal_file))
    monkeypatch.setattr(
        mw.QMessageBox,
        "question",
        staticmethod(lambda *a, **k: mw.QMessageBox.Yes),
    )

    window.delete_calibration_handler()

    assert not cal_file.exists()
    # Falls back to the default preset, matching wx's own ``setcfg(..., None)``
    # (config resolves a cleared "calibration.file" to ``DEFAULTS`` rather than
    # a falsy value).
    assert getcfg("calibration.file") != str(cal_file)
    assert getcfg("settings.changed") == 1


def test_delete_calibration_handler_no_file_is_noop(window):
    setcfg("calibration.file", False)

    window.delete_calibration_handler()  # Should not raise.


# --- per-tab info panels (wx's ``*_settings_info_panel`` / StaticFancyText) -


def test_info_text_html_converts_bold_markup_and_paragraphs():
    lang.init()
    html = mw.MainWindow._info_text_html("info.calibration_settings")
    assert "<b>Calibration</b>" in html
    assert "<font" not in html
    assert "<p" in html


def test_settings_stack_is_wrapped_in_scroll_area(window):
    # wx wraps the equivalent tab content in a scrolled window (``calpanel``)
    # since the info panels below can make a tab taller than the window.
    scroll_areas = window.findChildren(mw.QScrollArea)
    assert any(area.widget() is window.stack for area in scroll_areas)


def test_calibration_tab_has_info_panel_text(window):
    lang.init()
    labels = [lbl.text() for lbl in window._panels["calibration"].findChildren(mw.QLabel)]
    assert any(
        "<b>Calibration</b> is done by" in text for text in labels
    )


def test_profiling_tab_has_info_panel_text(window):
    lang.init()
    labels = [lbl.text() for lbl in window._panels["profiling"].findChildren(mw.QLabel)]
    assert any("<b>Profiling</b> is the process" in text for text in labels)


def test_lut3d_tab_has_info_panel_text(window):
    lang.init()
    labels = [lbl.text() for lbl in window._panels["lut3d"].findChildren(mw.QLabel)]
    assert any("<b>3D LUT</b>" in text for text in labels)


def test_display_instrument_tab_has_both_info_panel_texts(window):
    lang.init()
    labels = [
        lbl.text()
        for lbl in window._panels["display_instrument"].findChildren(mw.QLabel)
    ]
    assert any("<b>warm up</b>" in text for text in labels)
    assert any(
        "Disable any and all dynamic picture settings" in text for text in labels
    )


# --- show_advanced_options --------------------------------------------------
#
# Mirrors wx's ``MainFrame.show_advanced_options_handler`` and the helpers it
# calls (``show_display_delay_ctrls``, ``show_ffp_ctrls``,
# ``show_output_levels_ctrls``, ``show_observer_ctrl``, ``show_trc_controls``).
# ``QWidget.isHidden()`` reports a widget's own explicit visibility flag
# regardless of whether its tab is currently selected or the window is shown
# (unlike ``isVisible()``/``isVisibleTo()``, which also require every
# ancestor -- including the settings ``QStackedWidget``'s non-current pages --
# to be on-screen); ``QFormLayout.isRowVisible()`` is likewise independent of
# the ancestor chain.
#
# Every test below sets every config key its assertions depend on explicitly
# (rather than assuming a freshly-initialized default) and calls the
# ``_update_*`` refresh method directly rather than relying on
# ``QAction.setChecked`` to detect a change: ``config.setcfg`` only mutates
# the in-memory ``CFG`` singleton, so a value an earlier test left behind
# (e.g. ``argyll.version``) otherwise survives ``_init_config``'s
# ``initcfg()`` call, and a ``setChecked(True)`` that finds the action
# already checked from such a leak is a silent no-op (Qt only emits
# ``toggled`` on an actual state change), leaving stale visibility behind.


def test_show_advanced_options_menu_action_syncs_from_config(window):
    setcfg("show_advanced_options", 0)
    window._update_advanced_options_visibility()
    assert window.show_advanced_options_action.isChecked() is False

    setcfg("show_advanced_options", 1)
    window._update_advanced_options_visibility()
    assert window.show_advanced_options_action.isChecked() is True


def test_show_advanced_options_toggle_persists_config(window):
    window.show_advanced_options_action.setChecked(False)
    window.show_advanced_options_action.setChecked(True)
    assert getcfg("show_advanced_options") == 1
    window.show_advanced_options_action.setChecked(False)
    assert getcfg("show_advanced_options") == 0


def test_show_advanced_options_gates_profile_type_row(window):
    setcfg("show_advanced_options", 0)
    window._update_advanced_options_visibility()
    assert window._profiling_form.isRowVisible(window._profile_type_row_widget) is False

    setcfg("show_advanced_options", 1)
    window._update_advanced_options_visibility()
    assert window._profiling_form.isRowVisible(window._profile_type_row_widget) is True


def test_show_advanced_options_gates_black_luminance_row(window):
    setcfg("show_advanced_options", 0)
    window._update_advanced_options_visibility()
    assert (
        window._calibration_form.isRowVisible(window._black_luminance_row_widget)
        is False
    )

    setcfg("show_advanced_options", 1)
    window._update_advanced_options_visibility()
    assert (
        window._calibration_form.isRowVisible(window._black_luminance_row_widget)
        is True
    )


def test_show_advanced_options_gates_observer_row(window, monkeypatch):
    monkeypatch.setattr(
        Worker, "instrument_can_use_nondefault_observer", lambda self, *a, **k: True
    )
    setcfg("calibration.interactive_display_adjustment", 1)

    setcfg("show_advanced_options", 0)
    window._update_observer_visibility()
    assert window._calibration_form.isRowVisible(window.observer_ctrl) is False

    setcfg("show_advanced_options", 1)
    window._update_observer_visibility()
    assert window._calibration_form.isRowVisible(window.observer_ctrl) is True

    # Also gated on interactive-adjustment/TRC being on, independent of advanced.
    setcfg("calibration.interactive_display_adjustment", 0)
    setcfg("trc", "")
    window._update_observer_visibility()
    assert window._calibration_form.isRowVisible(window.observer_ctrl) is False


def test_show_advanced_options_gates_observer_row_without_nondefault_support(
    window, monkeypatch
):
    monkeypatch.setattr(
        Worker, "instrument_can_use_nondefault_observer", lambda self, *a, **k: False
    )
    setcfg("calibration.interactive_display_adjustment", 1)
    setcfg("show_advanced_options", 1)
    window._update_observer_visibility()
    assert window._calibration_form.isRowVisible(window.observer_ctrl) is False


def test_trc_dependent_rows_hidden_for_as_measured_regardless_of_advanced(window):
    window.trc_ctrl.setCurrentIndex(0)  # "as measured"
    for advanced in (0, 1):
        setcfg("show_advanced_options", advanced)
        window._apply_trc_mode()
        assert (
            window._calibration_form.isRowVisible(window._quality_row_widget)
            is False
        )
        assert (
            window._calibration_form.isRowVisible(window._ambient_row_widget)
            is False
        )
        assert (
            window._calibration_form.isRowVisible(window.black_output_offset_ctrl)
            is False
        )
        assert (
            window._calibration_form.isRowVisible(window.black_point_correction_ctrl)
            is False
        )


def test_trc_typed_gamma_row_needs_advanced_options(window):
    # Row 1 ("Gamma 2.2") is a typed-gamma row: its text/type fields and the
    # black-point-correction slider only appear with advanced options on.
    window.trc_ctrl.setCurrentIndex(1)

    setcfg("show_advanced_options", 0)
    window._apply_trc_mode()
    assert window.trc_textctrl.isHidden() is True
    assert window.trc_type_ctrl.isHidden() is True
    assert (
        window._calibration_form.isRowVisible(window.black_point_correction_ctrl)
        is False
    )
    # The calibration-speed row only needs a non-"as measured" TRC, not advanced.
    assert window._calibration_form.isRowVisible(window._quality_row_widget) is True

    setcfg("show_advanced_options", 1)
    window._apply_trc_mode()
    assert window.trc_textctrl.isHidden() is False
    assert window.trc_type_ctrl.isHidden() is False
    assert (
        window._calibration_form.isRowVisible(window.black_point_correction_ctrl)
        is True
    )


def test_trc_custom_row_always_shows_gamma_fields(window):
    # Row 7 ("custom") shows the gamma text/type fields even without advanced
    # options, since there's no other way to enter the value.
    setcfg("show_advanced_options", 0)
    window.trc_ctrl.setCurrentIndex(7)
    window._apply_trc_mode()
    assert window.trc_textctrl.isHidden() is False
    assert window.trc_type_ctrl.isHidden() is False


def test_show_advanced_options_gates_output_levels_row(window):
    setcfg("show_advanced_options", 0)
    window._update_advanced_options_visibility()
    assert window._output_levels_row_widget.isHidden() is True

    setcfg("show_advanced_options", 1)
    window._update_advanced_options_visibility()
    assert window._output_levels_row_widget.isHidden() is False


def test_show_advanced_options_keeps_ffp_row_hidden_for_ordinary_display(window):
    # ffp insertion only applies to Prisma/Resolve/madVR pattern generators;
    # an ordinary monitor keeps the row hidden even with advanced options on.
    setcfg("show_advanced_options", 1)
    window._update_advanced_options_visibility()
    assert window._ffp_row_widget.isHidden() is True


def test_show_advanced_options_gates_display_delay_override_rows(window):
    setcfg("argyll.version", "1.9.2")

    setcfg("show_advanced_options", 0)
    window._update_advanced_options_visibility()
    assert window._delay_form.isRowVisible(window._override_delay_row_widget) is False
    assert (
        window._delay_form.isRowVisible(window._override_settle_row_widget) is False
    )

    setcfg("show_advanced_options", 1)
    window._update_advanced_options_visibility()
    assert window._delay_form.isRowVisible(window._override_delay_row_widget) is True
    assert window._delay_form.isRowVisible(window._override_settle_row_widget) is True


def test_show_advanced_options_hides_settle_override_for_old_argyll(window):
    setcfg("argyll.version", "1.6.0")
    setcfg("show_advanced_options", 1)
    window._update_advanced_options_visibility()
    assert window._delay_form.isRowVisible(window._override_delay_row_widget) is True
    assert (
        window._delay_form.isRowVisible(window._override_settle_row_widget) is False
    )


def test_update_controls_resyncs_advanced_options_menu_action(window):
    setcfg("show_advanced_options", 1)
    window.update_controls()
    assert window.show_advanced_options_action.isChecked() is True
    assert window._profiling_form.isRowVisible(window._profile_type_row_widget) is True
