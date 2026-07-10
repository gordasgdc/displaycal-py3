"""Tests for the Qt main-window shell ``DisplayCAL.ui.main_window`` (Stage 3).

These exercise the toolkit-neutral marshalling helpers directly (no display) and
drive the window itself headless via the shared offscreen ``QApplication``
fixture. Display/port enumeration is stubbed so the tests need no Argyll install.
See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 3).
"""

import os
import shutil
import time
from types import SimpleNamespace

import pytest

from DisplayCAL import config
from DisplayCAL import gamap_settings
from DisplayCAL import localization as lang
from DisplayCAL import lut3d_settings as l3d
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
    """Initialise config (default values) before each test.

    ``initcfg()`` only fills in missing keys -- it does not clear ones a
    prior test already set in the shared in-memory ``config.CFG`` (the
    "config leaks between tests" trap this file's history already warns
    about). ``3dlut.create`` / ``profile.black_point_compensation`` are
    explicitly reset here: either being left ``1`` by an earlier test used
    to be harmless, but now drives ``_check_handler`` into showing a real,
    usually-unmocked ``QMessageBox`` via ``_check_lut3d_bpc`` whenever a
    later test flips either checkbox through the UI -- hanging the whole run
    (the "Qt test modal-hang gotcha").
    """
    config.initcfg()
    setcfg("3dlut.create", 0)
    setcfg("profile.black_point_compensation", 0)
    yield


@pytest.fixture
def srgb_profile_path():
    """Path to a bundled real ``mntr``/``RGB`` profile with a ``vcgt`` tag."""
    return os.path.join(
        os.path.dirname(__file__), "data", "icc", "vcgt_cm_test_cyanish_reddish.icc"
    )


@pytest.fixture
def lut3d_input_profile_path():
    """Path to a second, distinct bundled real ``mntr``/``RGB`` profile."""
    return os.path.join(
        os.path.dirname(__file__), "data", "icc", "vcgt_cm_test_blueish_yellowish.icc"
    )


@pytest.fixture
def hires_b2a_profile_path():
    """Path to a real profile with an LUT16Type A2B0 table in an XYZ PCS."""
    return os.path.join(
        os.path.dirname(__file__),
        "data",
        "icc",
        "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.icc",
    )


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
    # Info-panel text (and other lang.getstr() calls) is baked into widgets
    # at construction time below, so translations must already be loaded --
    # under pytest-xdist this may be the first MainWindow built in this
    # worker process, and lang.init() elsewhere (e.g. in a test body, after
    # construction) is too late to affect already-built widgets.
    lang.init()
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


def test_whitepoint_locus_persists(window):
    setcfg("show_advanced_options", 1)
    window.whitepoint_colortemp_locus_ctrl.setCurrentIndex(1)  # blackbody
    assert getcfg("whitepoint.colortemp.locus") == "T"
    window.whitepoint_colortemp_locus_ctrl.setCurrentIndex(0)  # daylight
    assert getcfg("whitepoint.colortemp.locus") == "t"


def test_whitepoint_locus_row_gated_by_advanced_options_and_mode(window):
    window.whitepoint_ctrl.setCurrentIndex(1)  # color temperature

    setcfg("show_advanced_options", 0)
    window._apply_whitepoint_mode()
    assert window.whitepoint_colortemp_locus_ctrl.isHidden() is True

    setcfg("show_advanced_options", 1)
    window._apply_whitepoint_mode()
    assert window.whitepoint_colortemp_locus_ctrl.isHidden() is False

    window.whitepoint_ctrl.setCurrentIndex(2)  # x,y chromaticity
    assert window.whitepoint_colortemp_locus_ctrl.isHidden() is True


def test_whitepoint_locus_repopulates_from_config(window):
    setcfg("whitepoint.colortemp.locus", "T")
    window.update_calibration_controls()
    assert window.whitepoint_colortemp_locus_ctrl.currentIndex() == 1

    setcfg("whitepoint.colortemp.locus", "t")
    window.update_calibration_controls()
    assert window.whitepoint_colortemp_locus_ctrl.currentIndex() == 0


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


def test_profile_type_persists(window, monkeypatch):
    # A real combo click can pop the CCXX-testchart-recommendation dialog
    # (see the tests further below) -- stub it so this test only exercises
    # the persistence itself.
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Ok)
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


def test_profile_type_ctrl_enables_gamap_only_for_lut_types(window, monkeypatch):
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Ok)
    window.profile_type_ctrl.setCurrentIndex(2)  # LabLUT ("l", a LUT type)
    assert window.gamap_btn.isEnabled()
    window.profile_type_ctrl.setCurrentIndex(4)  # 1xCurve+MTX ("S", not LUT)
    assert not window.gamap_btn.isEnabled()


def test_profile_type_ctrl_locks_quality_for_gamma_types(window, monkeypatch):
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Ok)
    window.profile_type_ctrl.setCurrentIndex(5)  # 3xGamma+MTX ("g")
    assert not window.profile_quality_ctrl.isEnabled()
    assert getcfg("profile.quality") == "h"
    window.profile_type_ctrl.setCurrentIndex(0)  # back to a non-gamma type
    assert window.profile_quality_ctrl.isEnabled()


def test_profile_type_ctrl_nudges_bpc_default(window, monkeypatch):
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Ok)
    setcfg("profile.type", "s")  # shaper+matrix, not yet a LUT type
    window.black_point_compensation_cb.setChecked(False)
    window.profile_type_ctrl.setCurrentIndex(1)  # XYZLUT ("x", a LUT type)
    assert getcfg("profile.black_point_compensation") == 0
    window.profile_type_ctrl.setCurrentIndex(4)  # 1xCurve+MTX ("S")
    assert getcfg("profile.black_point_compensation") == 1


def test_profile_type_ctrl_resets_testchart_on_type_change(window, monkeypatch):
    # Entering the LUT category from outside it is a "proftype_changed"
    # transition (see ``_profile_type_ctrl_changed``'s ``curve_or_gamma``
    # logic), so it should force the testchart back to its "auto" default.
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Ok)
    setcfg("profile.type", "S")
    window._set_testchart(window._testchart_paths[1])
    assert getcfg("testchart.file") != "auto"
    window.profile_type_ctrl.setCurrentIndex(2)  # LabLUT ("l", a LUT type)
    assert getcfg("testchart.file") == "auto"


def test_profile_type_ctrl_resets_testchart_within_same_category_too(
    window, monkeypatch
):
    # wx's ``set_default_testchart`` runs unconditionally on every profile-
    # type-handler call (only the separate CCXX-recommendation dialog is
    # gated on ``force``/a real event) -- a custom testchart is reset even
    # for a same-category "s" -> "S" change. ``force`` (True only on an
    # actual category change) has no observable effect here: it only
    # protects a testchart whose basename is already one of the bundled
    # default names, and every ``TESTCHART_DEFAULTS`` entry resolves to
    # "auto" today, which short-circuits before ``force`` is ever consulted.
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Ok)
    setcfg("profile.type", "s")
    window._set_testchart(window._testchart_paths[1])
    assert getcfg("testchart.file") != "auto"
    window.profile_type_ctrl.setCurrentIndex(4)  # 1xCurve+MTX ("S"), same category
    assert getcfg("testchart.file") == "auto"


def test_profile_type_ctrl_offers_testchart_recommendation(window, monkeypatch):
    setcfg("profile.type", "S")
    # ``_apply_default_testchart`` (always run first) resets the testchart to
    # "auto" and recomputes the patch count from ``testchart.auto_optimize``
    # before the recommendation check ever runs, so the low patch count has
    # to be set up via this key, not the label directly.
    setcfg("testchart.auto_optimize", 1)  # patches=34, well under any recommendation
    questions = []
    monkeypatch.setattr(
        mw.QMessageBox,
        "question",
        lambda *a, **k: questions.append(a) or mw.QMessageBox.Ok,
    )

    window.profile_type_ctrl.setCurrentIndex(2)  # LabLUT ("l"), user click

    assert questions
    assert getcfg("testchart.file") == "auto"
    assert getcfg("testchart.auto_optimize") > 1


def test_profile_type_ctrl_declines_testchart_recommendation(window, monkeypatch):
    setcfg("profile.type", "S")
    setcfg("testchart.auto_optimize", 1)
    monkeypatch.setattr(
        mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Cancel
    )

    window.profile_type_ctrl.setCurrentIndex(2)  # LabLUT ("l"), user click

    assert getcfg("testchart.auto_optimize") == 1


def test_profile_type_ctrl_no_recommendation_dialog_for_ccxx_testchart(
    window, monkeypatch
):
    setcfg("profile.type", "S")
    setcfg("testchart.auto_optimize", 1)
    monkeypatch.setattr(mw.config, "is_ccxx_testchart", lambda *a, **k: True)
    questions = []
    monkeypatch.setattr(
        mw.QMessageBox, "question", lambda *a, **k: questions.append(a) or mw.QMessageBox.Ok
    )

    window.profile_type_ctrl.setCurrentIndex(2)  # LabLUT ("l"), user click

    assert questions == []


def test_profile_type_ctrl_internal_reentry_skips_recommendation_dialog(
    window, monkeypatch
):
    # ``_apply_testchart_patches_amount``'s own profile-type nudge re-enters
    # ``_profile_type_ctrl_changed`` synthetically (wx's ``event=None`` path)
    # -- it must never pop the recommendation dialog, only wx's real combo
    # click does.
    setcfg("3dlut.create", 0)
    setcfg("profile.type", "S")
    questions = []
    monkeypatch.setattr(
        mw.QMessageBox, "question", lambda *a, **k: questions.append(a) or mw.QMessageBox.Ok
    )

    window.testchart_patches_amount_ctrl.setValue(10)  # nudges profile.type to "X"

    assert getcfg("profile.type") == "X"
    assert questions == []


# --- lut3d_check_bpc warning -------------------------------------------------


def test_check_lut3d_bpc_noop_when_3dlut_create_off(window, monkeypatch):
    setcfg("3dlut.create", 0)
    setcfg("profile.black_point_compensation", 1)
    exec_calls = []
    monkeypatch.setattr(mw.QMessageBox, "exec_", lambda self: exec_calls.append(True))

    window._check_lut3d_bpc()

    assert exec_calls == []


def test_check_lut3d_bpc_noop_when_bpc_off(window, monkeypatch):
    setcfg("3dlut.create", 1)
    setcfg("profile.black_point_compensation", 0)
    exec_calls = []
    monkeypatch.setattr(mw.QMessageBox, "exec_", lambda self: exec_calls.append(True))

    window._check_lut3d_bpc()

    assert exec_calls == []


def test_check_lut3d_bpc_turn_off_disables_bpc(window, monkeypatch):
    setcfg("3dlut.create", 1)
    setcfg("profile.black_point_compensation", 1)
    monkeypatch.setattr(mw, "QMessageBox", _FakeTwoButtonMessageBox)
    _FakeTwoButtonMessageBox.clicked_role = "accept"
    updated = []
    monkeypatch.setattr(window, "_update_bpc", lambda *a, **k: updated.append(True))

    window._check_lut3d_bpc()

    assert getcfg("profile.black_point_compensation") == 0
    assert updated == [True]


def test_check_lut3d_bpc_keep_current_leaves_bpc(window, monkeypatch):
    setcfg("3dlut.create", 1)
    setcfg("profile.black_point_compensation", 1)
    monkeypatch.setattr(mw, "QMessageBox", _FakeTwoButtonMessageBox)
    _FakeTwoButtonMessageBox.clicked_role = "reject"

    window._check_lut3d_bpc()

    assert getcfg("profile.black_point_compensation") == 1


def test_check_handler_bpc_change_triggers_bpc_warning(window, monkeypatch):
    setcfg("3dlut.create", 1)
    checked = []
    monkeypatch.setattr(
        window, "_check_lut3d_bpc", lambda: checked.append(True)
    )

    window._check_handler("profile.black_point_compensation", True)

    assert checked == [True]


def test_check_handler_lut3d_create_change_triggers_bpc_warning(window, monkeypatch):
    setcfg("profile.black_point_compensation", 1)
    checked = []
    monkeypatch.setattr(
        window, "_check_lut3d_bpc", lambda: checked.append(True)
    )

    window._check_handler("3dlut.create", True)

    assert checked == [True]


def test_check_handler_unrelated_key_does_not_trigger_bpc_warning(window, monkeypatch):
    checked = []
    monkeypatch.setattr(
        window, "_check_lut3d_bpc", lambda: checked.append(True)
    )

    window._check_handler("calibration.interactive_display_adjustment", True)

    assert checked == []


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


def test_gamap_btn_handler_opens_window(window):
    window._gamap_btn_handler()
    try:
        assert window._gamap_window is not None
    finally:
        window._gamap_window.close()


def test_gamap_btn_handler_reuses_window_instance(window):
    window._gamap_btn_handler()
    try:
        first = window._gamap_window
        window._gamap_btn_handler()
        assert window._gamap_window is first
    finally:
        window._gamap_window.close()


def test_gamap_window_profile_settings_changed_marks_calibration_file_ctrl(window):
    setcfg("settings.changed", 0)
    window._gamap_btn_handler()
    try:
        window._gamap_window.profile_settings_changed.emit()
        assert getcfg("settings.changed") == 1
    finally:
        window._gamap_window.close()


def test_gamap_window_b2a_quality_changed_updates_bpc_and_lut3d(window):
    setcfg("profile.type", "l")
    window._gamap_btn_handler()
    try:
        window.black_point_compensation_cb.setEnabled(False)
        window._gamap_window.b2a_quality_changed.emit()
        # _update_bpc / _update_lut3d_b2a_controls both ran without error and
        # left the checkbox in a config-derived (not stale) enabled state.
        assert window.black_point_compensation_cb.isEnabled() == gamap_settings.compute_bpc_enabled(
            "l", bool(getcfg("profile.b2a.hires")), getcfg("profile.quality.b2a")
        )
    finally:
        window._gamap_window.close()


def test_create_testchart_btn_handler_opens_window(window):
    window._create_testchart_btn_handler()
    try:
        assert window._testchart_editor_window is not None
    finally:
        window._testchart_editor_window.close()


def test_open_testchart_editor_reuses_window_instance(window):
    window._open_testchart_editor()
    try:
        first = window._testchart_editor_window
        window._open_testchart_editor()
        assert window._testchart_editor_window is first
    finally:
        window._testchart_editor_window.close()


def test_ccxx_import_action_handler_refreshes_after_finish(window, monkeypatch):
    from DisplayCAL.ui import colorimeter_correction_io as ccio

    def fake_run(self):
        self.finished.emit()

    monkeypatch.setattr(ccio.ImportController, "run", fake_run)
    calls = []
    monkeypatch.setattr(
        window,
        "update_colorimeter_correction_matrix_ctrl_items",
        lambda *a, **k: calls.append((a, k)),
    )
    window._ccxx_import_action_handler()
    assert calls
    assert window._ccxx_import_controller is None


def test_ccxx_upload_action_handler_clears_controller_after_finish(
    window, monkeypatch
):
    from DisplayCAL.ui import colorimeter_correction_io as ccio

    def fake_run(self, path=None):
        self.finished.emit()

    monkeypatch.setattr(ccio.UploadController, "run", fake_run)
    window._ccxx_upload_action_handler()
    assert window._ccxx_upload_controller is None


def test_measurement_report_btn_handler_opens_window(window):
    window.measurement_report_btn_handler()
    try:
        assert window._report_window is not None
    finally:
        window._report_window.close()


def test_measurement_report_btn_handler_reuses_window_instance(window):
    window.measurement_report_btn_handler()
    try:
        first = window._report_window
        window.measurement_report_btn_handler()
        assert window._report_window is first
    finally:
        window._report_window.close()


def test_report_window_edit_chart_requested_opens_testchart_editor(window):
    window.measurement_report_btn_handler()
    try:
        window._report_window.edit_chart_requested.emit()
        assert window._testchart_editor_window is not None
    finally:
        window._report_window.close()
        if window._testchart_editor_window is not None:
            window._testchart_editor_window.close()


def _fake_report_context(**overrides):
    """A minimal, valid ``ReportContext`` for the Qt-wiring tests below.

    The pipeline internals (chart_lookup, ICC/CGATS parsing, ...) are covered
    by ``tests/test_measurement_report.py``; these tests only need to verify
    ``main_window.py`` threads a context through to the right dialogs / worker
    calls, so the field values themselves mostly don't matter.
    """
    from DisplayCAL import measurement_report as mrp

    fields = {
        "chart": object(),
        "ti1": object(),
        "ti3_ref": object(),
        "gray": None,
        # A bare ``object()`` has no ``.tags``, which
        # ``measurement_report.profile_b2a_is_lowres()`` reads unconditionally
        # -- an empty tags dict short-circuits it to ``False`` without a real
        # ICCProfile.
        "profile": SimpleNamespace(tags={}, creator=b"XXXX"),
        "oprof": SimpleNamespace(tags={}, creator=b"XXXX"),
        "sim_profile": None,
        "devlink": None,
        "sim_ti3": None,
        "intent": "r",
        "sim_intent": None,
        "apply_trc": False,
        "colormanaged": False,
        "use_sim": False,
        "use_sim_as_output": False,
        "report_type": "Measurement",
        "default_file": "Measurement Report 1.0 - Test Display - now.html",
    }
    fields.update(overrides)
    return mrp.ReportContext(**fields)


@pytest.fixture
def report_window(window):
    window.measurement_report_btn_handler()
    yield window._report_window
    window._report_window.close()


def test_report_measure_requested_missing_argyll_reenables_button(
    window, report_window, monkeypatch
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: False)
    report_window.measurement_report_btn.setEnabled(False)

    window._on_report_measure_requested()

    assert report_window.measurement_report_btn.isEnabled() is True


def test_report_measure_requested_setup_error_shows_dialog(
    window, report_window, monkeypatch
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    from DisplayCAL import measurement_report as mrp

    def fake_resolve(*a, **k):
        raise mrp.ReportSetupError("no chart")

    monkeypatch.setattr(
        mw.measurement_report_pipeline, "resolve_report_context", fake_resolve
    )
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    report_window.measurement_report_btn.setEnabled(False)

    window._on_report_measure_requested()

    assert "no chart" in errors[0][2]
    assert report_window.measurement_report_btn.isEnabled() is True


def test_report_measure_requested_cancelled_save_dialog_is_noop(
    window, report_window, monkeypatch
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "resolve_report_context",
        lambda *a, **k: _fake_report_context(),
    )
    monkeypatch.setattr(
        mw.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    began = []
    monkeypatch.setattr(window, "_begin_report_measurement", lambda: began.append(True))
    report_window.measurement_report_btn.setEnabled(False)

    window._on_report_measure_requested()

    assert began == []
    assert report_window.measurement_report_btn.isEnabled() is True


def test_report_measure_requested_overwrite_declined_is_noop(
    window, report_window, monkeypatch, tmp_path
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "resolve_report_context",
        lambda *a, **k: _fake_report_context(),
    )
    existing = tmp_path / "report.html"
    existing.write_text("existing")
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(existing), "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    monkeypatch.setattr(
        mw.QMessageBox,
        "warning",
        staticmethod(lambda *a, **k: mw.QMessageBox.Cancel),
    )
    began = []
    monkeypatch.setattr(window, "_begin_report_measurement", lambda: began.append(True))

    window._on_report_measure_requested()

    assert began == []


def test_report_measure_requested_success_stages_and_begins(
    window, report_window, monkeypatch, tmp_path
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    context = _fake_report_context()
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "resolve_report_context",
        lambda *a, **k: context,
    )
    target = tmp_path / "My Report.html"
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    began = []
    monkeypatch.setattr(window, "_begin_report_measurement", lambda: began.append(True))

    window._on_report_measure_requested()

    assert began == [True]
    assert window._pending_report_context is context
    assert window._pending_report_save_path == str(target)
    assert getcfg("last_filedialog_path") == str(target)


def test_report_measure_requested_write_access_denied_shows_error(
    window, report_window, monkeypatch, tmp_path
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "resolve_report_context",
        lambda *a, **k: _fake_report_context(),
    )
    target = tmp_path / "My Report.html"
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: False)
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    began = []
    monkeypatch.setattr(window, "_begin_report_measurement", lambda: began.append(True))

    window._on_report_measure_requested()

    assert errors
    assert began == []


def test_begin_report_measurement_call_pending_runs_immediately(
    window, monkeypatch, _no_writecfg
):
    _force_mode(window, monkeypatch, mf.PresentationMode.CALL_PENDING)
    ran = []
    monkeypatch.setattr(window, "_run_report_measurement", lambda: ran.append(True))
    _run_pending_synchronously(window)

    window._begin_report_measurement()

    assert ran == [True]


def test_begin_report_measurement_show_frame_presents_measureframe(
    window, monkeypatch, _no_writecfg
):
    _force_mode(window, monkeypatch, mf.PresentationMode.SHOW_FRAME)
    presented = []
    monkeypatch.setattr(window, "_present_measureframe", lambda: presented.append(True))

    window._begin_report_measurement()

    assert presented == [True]


def test_run_report_measurement_stage_failure_shows_error(window, monkeypatch):
    context = _fake_report_context()
    window._pending_report_context = context
    window._pending_report_save_path = "/tmp/report.html"
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "stage_measurement_files",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stage failed")),
    )
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    wrapup_calls = []
    monkeypatch.setattr(
        window.worker, "wrapup", lambda *a, **k: wrapup_calls.append(a) or True
    )
    ran = []
    monkeypatch.setattr(mw.WorkerRunController, "run", lambda *a, **k: ran.append(True))

    window._run_report_measurement()

    assert "stage failed" in errors[0][2]
    assert wrapup_calls == [(False,)]
    assert ran == []


def test_run_report_measurement_success_runs_measure_ti1(window, monkeypatch):
    context = _fake_report_context(colormanaged=True)
    window._pending_report_context = context
    window._pending_report_save_path = "/tmp/report.html"
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "stage_measurement_files",
        lambda *a, **k: ("/tmp/ti1path.ti1", "/tmp/cal.cal"),
    )
    calls = {}

    def fake_run(_ctrl, producer, consumer=None, **kwargs):
        calls["producer"] = producer
        calls["consumer"] = consumer
        calls["wargs"] = kwargs.get("wargs")

    monkeypatch.setattr(mw.WorkerRunController, "run", fake_run)

    window._run_report_measurement()

    assert calls["producer"] == window.worker.measure_ti1
    assert calls["consumer"] == window._on_report_measurement_finished
    assert calls["wargs"] == ("/tmp/ti1path.ti1", "/tmp/cal.cal", True)
    assert window._pending_report_ti1_path == "/tmp/ti1path.ti1"
    assert window.worker.dispread_after_dispcal is False


def test_report_measurement_finished_exception_shows_error_and_wraps_up(
    window, monkeypatch
):
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    wrapup_calls = []
    monkeypatch.setattr(
        window.worker, "wrapup", lambda *a, **k: wrapup_calls.append(a) or True
    )
    exc = ValueError("boom")

    window._on_report_measurement_finished(exc)

    assert "boom" in errors[0][2]
    assert wrapup_calls == [(exc,)]


def test_report_measurement_finished_incomplete_wraps_up_silently(
    window, monkeypatch
):
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    wrapup_calls = []
    monkeypatch.setattr(
        window.worker, "wrapup", lambda *a, **k: wrapup_calls.append(a) or True
    )

    window._on_report_measurement_finished(False)

    assert errors == []
    assert wrapup_calls == [(False,)]


def _stage_real_ti3(tmp_path, data_path, name="work"):
    """Copy a real (zero-suspicious-patches) fixture TI3 into ``tmp_path``.

    ``_on_report_measurement_finished`` now loads the measured TI3 for real
    (to run the sanity-check review, see :meth:`MainWindow
    ._check_measurement_sanity`) before calling
    ``finalize_measurement_report``, so tests need an actual file at the
    derived path rather than a nonexistent placeholder. ``sample/0_16.ti3``
    is confirmed clean under ``check_ti3`` (see
    ``tests/test_ui_measurement_sanity_dialog.py``), so the sanity check is a
    silent no-op even if ``ti3.check_sanity.auto`` were enabled.
    """
    ti3_path = tmp_path / f"{name}.ti3"
    ti3_path.write_bytes((data_path / "sample" / "0_16.ti3").read_bytes())
    return str(tmp_path / f"{name}.ti1"), str(ti3_path)


def test_report_measurement_finished_success_calls_finalize(
    window, monkeypatch, tmp_path, data_path
):
    context = _fake_report_context()
    window._pending_report_context = context
    window._pending_report_save_path = "/tmp/report.html"
    window._pending_report_ti1_path, ti3_path = _stage_real_ti3(tmp_path, data_path)
    calls = {}
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "finalize_measurement_report",
        lambda **kwargs: calls.update(kwargs),
    )

    window._on_report_measurement_finished(True)

    assert calls["ti3_path"] == ti3_path
    assert calls["profile"] is context.profile
    assert calls["save_path"] == "/tmp/report.html"
    assert calls["instrument_name"] == window.comport_ctrl.currentText()
    assert calls["observers"] is window._observers
    assert calls["removed_items"] == []
    assert calls["self_check_report"] is False


def test_report_measurement_finished_finalize_error_shows_dialog(
    window, monkeypatch, tmp_path, data_path
):
    context = _fake_report_context()
    window._pending_report_context = context
    window._pending_report_save_path = "/tmp/report.html"
    window._pending_report_ti1_path, _ti3_path = _stage_real_ti3(tmp_path, data_path)
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "finalize_measurement_report",
        lambda **k: (_ for _ in ()).throw(RuntimeError("write failed")),
    )
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))

    window._on_report_measurement_finished(True)

    assert "write failed" in errors[0][2]


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


def test_lut3d_trc_ctrl_gamma22_persists(window):
    window.lut3d_trc_ctrl.setCurrentIndex(0)
    assert getcfg("3dlut.trc") == "gamma2.2"
    assert getcfg("3dlut.trc_gamma") == 2.2
    assert getcfg("3dlut.trc_gamma_type") == "b"
    assert getcfg("3dlut.trc_output_offset") == 1.0


def test_lut3d_trc_ctrl_bt1886_persists(window):
    window.lut3d_trc_ctrl.setCurrentIndex(1)
    assert getcfg("3dlut.trc") == "bt1886"
    assert getcfg("3dlut.trc_gamma") == 2.4
    assert getcfg("3dlut.trc_gamma_type") == "B"


def test_lut3d_trc_ctrl_smpte2084_hardclip_forces_maxmll_10000(window):
    setcfg("3dlut.hdr_maxmll", 1000.0)
    window.lut3d_trc_ctrl.setCurrentIndex(2)
    assert getcfg("3dlut.trc") == "smpte2084.hardclip"
    assert getcfg("3dlut.hdr_maxmll") == 10000


def test_lut3d_trc_ctrl_hlg_persists(window):
    window.lut3d_trc_ctrl.setCurrentIndex(4)
    assert getcfg("3dlut.trc") == "hlg"


def test_lut3d_trc_gamma_ctrl_rejects_out_of_range_value(window):
    window.lut3d_trc_ctrl.setCurrentIndex(5)  # custom
    before = getcfg("3dlut.trc_gamma")
    window.lut3d_trc_gamma_ctrl.setCurrentText("99")
    window._lut3d_trc_gamma_changed()
    assert getcfg("3dlut.trc_gamma") == before
    assert window.lut3d_trc_gamma_ctrl.currentText() == str(before)


def test_lut3d_trc_gamma_ctrl_accepts_valid_value(window):
    window.lut3d_trc_ctrl.setCurrentIndex(5)  # custom
    window.lut3d_trc_gamma_ctrl.setCurrentText("1.8")
    window._lut3d_trc_gamma_changed()
    assert getcfg("3dlut.trc_gamma") == 1.8


def test_lut3d_content_colorspace_selection_sets_primaries(window):
    window.lut3d_content_colorspace_ctrl.setCurrentIndex(2)  # Rec. 709
    assert getcfg("3dlut.content.colorspace.red.x") == 0.64
    assert getcfg("3dlut.content.colorspace.red.y") == 0.33


def test_lut3d_content_colorspace_xy_edit_persists_and_selects_custom(window):
    window.lut3d_content_colorspace_ctrl.setCurrentIndex(2)  # Rec. 709
    red_x = window._lut3d_content_colorspace_xy_ctrls[("red", "x")]
    red_x.setValue(0.5)
    assert getcfg("3dlut.content.colorspace.red.x") == 0.5
    assert window.lut3d_content_colorspace_ctrl.currentIndex() == len(
        l3d.CONTENT_COLORSPACE_NAMES
    )


def test_lut3d_hdr_peak_luminance_raises_maxmll_floor(window):
    setcfg("3dlut.hdr_maxmll", 1000.0)
    window.lut3d_hdr_peak_luminance_ctrl.setValue(4000.0)
    assert getcfg("3dlut.hdr_peak_luminance") == 4000.0
    assert getcfg("3dlut.hdr_maxmll") == 4000.0
    assert window.lut3d_hdr_maxmll_ctrl.minimum() == 4000.0


def test_lut3d_hdr_maxmll_alt_clip_checkbox_is_inverted(window):
    setcfg("3dlut.hdr_maxmll_alt_clip", 1)
    window.update_lut3d_controls()
    assert window.lut3d_hdr_maxmll_alt_clip_cb.isChecked() is False
    window.lut3d_hdr_maxmll_alt_clip_cb.setChecked(True)
    assert getcfg("3dlut.hdr_maxmll_alt_clip") == 0


def test_lut3d_hdr_sat_slider_persists_and_updates_readout(window):
    window.lut3d_hdr_sat_ctrl.setValue(30)
    assert getcfg("3dlut.hdr_sat") == 0.3
    assert window.lut3d_hdr_sat_sat_val.text() == "30.0%"
    assert window.lut3d_hdr_sat_lum_val.text() == "70.0%"


def test_lut3d_hdr_hue_slider_and_intctrl_stay_in_sync(window):
    window.lut3d_hdr_hue_ctrl.setValue(40)
    assert window.lut3d_hdr_hue_intctrl.value() == 40
    assert getcfg("3dlut.hdr_hue") == 0.4

    window.lut3d_hdr_hue_intctrl.setValue(60)
    assert window.lut3d_hdr_hue_ctrl.value() == 60
    assert getcfg("3dlut.hdr_hue") == 0.6


def test_lut3d_black_output_offset_slider_and_intctrl_stay_in_sync(window):
    window.lut3d_trc_black_output_offset_ctrl.setValue(25)
    assert window.lut3d_trc_black_output_offset_intctrl.value() == 25
    assert getcfg("3dlut.trc_output_offset") == 0.25


def test_lut3d_apply_cal_checkbox_persists(window):
    setcfg("3dlut.create", 1)
    window.update_lut3d_controls()
    assert window.lut3d_apply_cal_cb.isEnabled() is True
    window.lut3d_apply_cal_cb.setChecked(True)
    assert getcfg("3dlut.output.profile.apply_cal") == 1
    window.lut3d_apply_cal_cb.setChecked(False)
    assert getcfg("3dlut.output.profile.apply_cal") == 0


def test_lut3d_gamut_mapping_radios_persist_use_b2a(window):
    setcfg("3dlut.create", 1)
    setcfg("profile.type", "l")
    setcfg("profile.b2a.hires", 1)
    window.update_lut3d_controls()
    assert window.gamut_mapping_b2a.isEnabled() is True

    window.gamut_mapping_b2a.setChecked(True)
    assert getcfg("3dlut.gamap.use_b2a") == 1

    window.gamut_mapping_inverse_a2b.setChecked(True)
    assert getcfg("3dlut.gamap.use_b2a") == 0


def test_lut3d_format_madvr_forces_encoding_and_size(qapp, stub_worker):
    # madVR is only offered in the format combo for Argyll 1.6+, and that
    # combo's item set is fixed at window-construction time (mirrors wx's
    # ``lut3d_setup_language``), so pin the version before constructing.
    setcfg("argyll.version", "1.9.0")
    win = mw.MainWindow()
    try:
        values = win._lut3d_format_values
        assert "madVR" in values
        win.lut3d_format_ctrl.setCurrentIndex(values.index("madVR"))
        assert getcfg("3dlut.format") == "madVR"
        assert getcfg("3dlut.encoding.input") == "t"
        assert getcfg("3dlut.encoding.output") == "t"
        assert getcfg("3dlut.size") == 65
    finally:
        win.close()


def test_lut3d_format_change_rebuilds_encoding_combo(window):
    values = window._lut3d_format_values
    window.lut3d_format_ctrl.setCurrentIndex(values.index("dcl"))
    assert window._lut3d_encoding_input_values == ["n"]
    assert window.encoding_input_ctrl.count() == 1


def test_lut3d_visibility_trc_gamma_hidden_without_advanced_options(window):
    setcfg("show_advanced_options", 0)
    window.lut3d_trc_ctrl.setCurrentIndex(1)  # BT.1886
    assert window.lut3d_trc_gamma_ctrl.isHidden() is True


def test_lut3d_visibility_apply_cal_row_gated_by_advanced_options(window):
    setcfg("show_advanced_options", 0)
    window.update_lut3d_controls()
    assert window._lut3d_form.isRowVisible(window.lut3d_apply_cal_cb) is False

    setcfg("show_advanced_options", 1)
    window._update_advanced_options_visibility()
    assert window._lut3d_form.isRowVisible(window.lut3d_apply_cal_cb) is True


def test_lut3d_visibility_hdr_display_only_for_smpte2084_madvr(qapp, stub_worker):
    setcfg("argyll.version", "1.9.0")
    win = mw.MainWindow()
    try:
        values = win._lut3d_format_values
        win.lut3d_format_ctrl.setCurrentIndex(values.index("madVR"))
        win.lut3d_trc_ctrl.setCurrentIndex(2)  # SMPTE 2084 hard clip
        assert win.lut3d_hdr_display_ctrl.isHidden() is False

        win.lut3d_trc_ctrl.setCurrentIndex(4)  # HLG
        assert win.lut3d_hdr_display_ctrl.isHidden() is True
    finally:
        win.close()


def test_lut3d_input_profile_ctrl_persists_selection(window):
    assert window.lut3d_input_profile_ctrl.count() > 0
    paths = list(window.input_profiles.values())
    window.lut3d_input_profile_ctrl.setCurrentIndex(len(paths) - 1)
    assert getcfg("3dlut.input.profile") == paths[-1]
    assert window.lut3d_input_profile_ctrl.toolTip() == paths[-1]


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
def _stub_preflight_checks(window, monkeypatch):
    """Bypass the pre-flight confirm/overwrite dialogs (own tests below).

    ``calibrate_btn_handler`` / ``calibrate_and_profile_btn_handler`` /
    ``profile_btn_handler`` now show real modal dialogs before staging a
    measurement (see :meth:`MainWindow._check_overwrite` /
    :meth:`_check_show_macos_bugs_warning` / :meth:`_current_cal_choice`); tests
    that only care about the staging/dispatch behaviour need those answered
    without a live event loop, matching a plain "proceed" click.
    """
    monkeypatch.setattr(window, "_check_overwrite", lambda *a, **k: True)
    monkeypatch.setattr(window, "_check_show_macos_bugs_warning", lambda *a, **k: None)
    monkeypatch.setattr(window, "_current_cal_choice", lambda *a, **k: True)
    monkeypatch.setattr(window, "_fast_matrix_shaper_choice", lambda *a, **k: False)
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)


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
    window,
    _no_writecfg,
    _stub_measurement_run,
    _stub_preflight_checks,
    monkeypatch,
    button_attr,
    action,
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


# --- pre-flight confirm/overwrite dialogs -----------------------------------


def test_check_overwrite_no_existing_file_no_dialog(window, monkeypatch, tmp_path):
    setcfg("profile.save_path", str(tmp_path))
    setcfg("profile.name.expanded", "MyProfile")
    called = []
    monkeypatch.setattr(
        mw.QMessageBox, "warning", lambda *a, **k: called.append(a) or mw.QMessageBox.Ok
    )

    assert window._check_overwrite(".icc") is True
    assert called == []


def test_check_overwrite_existing_file_ok_confirms(window, monkeypatch, tmp_path):
    setcfg("profile.save_path", str(tmp_path))
    setcfg("profile.name.expanded", "MyProfile")
    (tmp_path / "MyProfile").mkdir()
    (tmp_path / "MyProfile" / "MyProfile.icc").write_bytes(b"x")
    monkeypatch.setattr(mw.QMessageBox, "warning", lambda *a, **k: mw.QMessageBox.Ok)

    assert window._check_overwrite(".icc") is True


def test_check_overwrite_existing_file_cancel_aborts(window, monkeypatch, tmp_path):
    setcfg("profile.save_path", str(tmp_path))
    setcfg("profile.name.expanded", "MyProfile")
    (tmp_path / "MyProfile").mkdir()
    (tmp_path / "MyProfile" / "MyProfile.icc").write_bytes(b"x")
    monkeypatch.setattr(
        mw.QMessageBox, "warning", lambda *a, **k: mw.QMessageBox.Cancel
    )

    assert window._check_overwrite(".icc") is False


def test_macos_bugs_warning_not_applicable_skips_dialog(window, monkeypatch):
    monkeypatch.setattr(
        mw.preflight_checks, "macos_bugs_warning_applicable", lambda: False
    )
    called = []
    monkeypatch.setattr(mw.QMessageBox, "warning", lambda *a, **k: called.append(a))

    assert window._check_show_macos_bugs_warning() is None
    assert called == []


def test_macos_bugs_cal_warning_yes_resets_controls(window, monkeypatch):
    monkeypatch.setattr(
        mw.preflight_checks, "macos_bugs_warning_applicable", lambda: True
    )
    monkeypatch.setattr(
        mw.preflight_checks, "should_warn_calibration_bugs", lambda: True
    )
    monkeypatch.setattr(mw.preflight_checks, "should_warn_profile_bugs", lambda: False)
    monkeypatch.setattr(mw.QMessageBox, "warning", lambda *a, **k: mw.QMessageBox.Yes)
    window.black_luminance_ctrl.setCurrentIndex(1)
    window.black_point_correction_ctrl.setValue(50)
    setcfg("calibration.black_point_correction.auto", 1)

    assert window._check_show_macos_bugs_warning(profile=False) is None

    assert window.black_luminance_ctrl.currentIndex() == 0
    assert window.black_point_correction_ctrl.value() == 0
    assert getcfg("calibration.black_point_correction.auto") == 0


def test_macos_bugs_cal_warning_cancel_aborts(window, monkeypatch):
    monkeypatch.setattr(
        mw.preflight_checks, "macos_bugs_warning_applicable", lambda: True
    )
    monkeypatch.setattr(
        mw.preflight_checks, "should_warn_calibration_bugs", lambda: True
    )
    monkeypatch.setattr(
        mw.QMessageBox, "warning", lambda *a, **k: mw.QMessageBox.Cancel
    )

    assert window._check_show_macos_bugs_warning(profile=False) is False


def test_macos_bugs_profile_warning_yes_updates_profile_controls(window, monkeypatch):
    monkeypatch.setattr(
        mw.preflight_checks, "macos_bugs_warning_applicable", lambda: True
    )
    monkeypatch.setattr(mw.preflight_checks, "should_warn_profile_bugs", lambda: True)
    monkeypatch.setattr(mw.QMessageBox, "warning", lambda *a, **k: mw.QMessageBox.Yes)
    setcfg("profile.type", "g")
    setcfg("profile.black_point_compensation", 0)

    assert window._check_show_macos_bugs_warning(cal=False) is None

    assert getcfg("profile.type") == "S"
    assert getcfg("profile.black_point_compensation") == 1
    assert window.black_point_compensation_cb.isChecked() is True


class _FakeCalChoiceDialog:
    """Stand-in for ``mw._CalChoiceDialog`` that skips the real modal loop."""

    answer = None  # set per-test

    def __init__(self, info, parent=None):
        self.info = info

    def exec_(self):
        return self.__class__.answer

    def embed_cal(self):
        return self.__class__.embed

    def reset_cal(self):
        return self.__class__.reset


def test_current_cal_choice_uncalibratable_display_returns_false(window, monkeypatch):
    monkeypatch.setattr(mw.config, "is_uncalibratable_display", lambda: True)

    assert window._current_cal_choice() is False


def test_current_cal_choice_invalid_profile_shows_error(window, monkeypatch, tmp_path):
    monkeypatch.setattr(mw.config, "is_uncalibratable_display", lambda: False)
    bogus = tmp_path / "bogus.icc"
    bogus.write_bytes(b"not an icc profile")
    setcfg("calibration.file", str(bogus))
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))

    result = window._current_cal_choice()

    assert result is mw.CAL_CHOICE_CANCELLED
    assert errors


def test_current_cal_choice_dialog_cancel_returns_sentinel(window, monkeypatch):
    monkeypatch.setattr(mw.config, "is_uncalibratable_display", lambda: False)
    setcfg("calibration.file", None)
    _FakeCalChoiceDialog.answer = mw.QDialog.Rejected
    monkeypatch.setattr(mw, "_CalChoiceDialog", _FakeCalChoiceDialog)

    assert window._current_cal_choice() is mw.CAL_CHOICE_CANCELLED


def _cal_choice_info(**overrides):
    base = dict(
        is_uncalibratable=False,
        cal_path=None,
        options_dispcal=None,
        can_use_current_cal=True,
        msg_key="dialog.current_cal_warning",
        icon="warning",
        show_reset_checkbox=True,
    )
    base.update(overrides)
    return mw.preflight_checks.CalChoiceInfo(**base)


def test_current_cal_choice_embed_current_returns_none(window, monkeypatch):
    monkeypatch.setattr(mw.config, "is_uncalibratable_display", lambda: False)
    setcfg("calibration.file", None)
    monkeypatch.setattr(
        mw.preflight_checks, "resolve_cal_choice_info", lambda worker: _cal_choice_info()
    )
    _FakeCalChoiceDialog.answer = mw.QDialog.Accepted
    _FakeCalChoiceDialog.embed = True
    _FakeCalChoiceDialog.reset = False
    monkeypatch.setattr(mw, "_CalChoiceDialog", _FakeCalChoiceDialog)
    reset_calls = []
    monkeypatch.setattr(window, "_reset_video_lut", lambda: reset_calls.append(True))

    result = window._current_cal_choice()

    assert result is None
    assert reset_calls == []


def test_current_cal_choice_no_embed_resets_video_lut(window, monkeypatch):
    monkeypatch.setattr(mw.config, "is_uncalibratable_display", lambda: False)
    setcfg("calibration.file", None)
    monkeypatch.setattr(
        mw.preflight_checks, "resolve_cal_choice_info", lambda worker: _cal_choice_info()
    )
    _FakeCalChoiceDialog.answer = mw.QDialog.Accepted
    _FakeCalChoiceDialog.embed = False
    _FakeCalChoiceDialog.reset = True
    monkeypatch.setattr(mw, "_CalChoiceDialog", _FakeCalChoiceDialog)
    reset_calls = []
    monkeypatch.setattr(window, "_reset_video_lut", lambda: reset_calls.append(True))

    result = window._current_cal_choice()

    assert result is False
    assert reset_calls == [True]


class _FakeFastMatrixShaperMessageBox:
    """Stand-in for ``mw.QMessageBox`` that skips the real modal loop.

    ``_fast_matrix_shaper_choice`` builds a 3-button dialog via
    ``addButton(text, role)``; this fake records the role each button was
    added with and reports whichever one ``clicked_role`` (set per-test)
    names as "clicked", the same shape ``clickedButton()`` returns for real.
    """

    Question = 0
    AcceptRole = 1
    ActionRole = 2
    RejectRole = 3

    clicked_role = None  # "ok" | "calibrate" | "cancel", set per-test

    def __init__(self, parent=None):
        self._buttons = {}

    def setWindowTitle(self, title):
        pass

    def setIcon(self, icon):
        pass

    def setText(self, text):
        self.text = text

    def addButton(self, text, role):
        button = (text, role)
        self._buttons[role] = button
        return button

    def exec_(self):
        return None

    def clickedButton(self):
        role = {
            "ok": self.AcceptRole,
            "calibrate": self.ActionRole,
            "cancel": self.RejectRole,
        }[self.clicked_role]
        return self._buttons[role]


def _fast_matrix_shaper_info(**overrides):
    base = dict(
        show_dialog=True,
        update_profile=False,
        msg_key="calibration.create_fast_matrix_shaper_choice",
        ok_key="calibration.create_fast_matrix_shaper",
    )
    base.update(overrides)
    return mw.preflight_checks.FastMatrixShaperChoiceInfo(**base)


@pytest.mark.parametrize(
    "clicked_role,expected", [("ok", True), ("calibrate", False), ("cancel", None)]
)
def test_fast_matrix_shaper_choice_maps_clicked_button(
    window, monkeypatch, clicked_role, expected
):
    monkeypatch.setattr(mw, "QMessageBox", _FakeFastMatrixShaperMessageBox)
    _FakeFastMatrixShaperMessageBox.clicked_role = clicked_role

    assert window._fast_matrix_shaper_choice(_fast_matrix_shaper_info()) is expected


class _FakeTwoButtonMessageBox:
    """Stand-in for ``mw.QMessageBox`` for the 2-button ``addButton`` dialogs
    :meth:`_check_lut3d_bpc` and :meth:`_offer_install_3dlut` build (an
    ``AcceptRole`` button plus a ``RejectRole`` one), the same shape as
    :class:`_FakeFastMatrixShaperMessageBox` minus the third button."""

    Question = 0
    Warning = 1
    AcceptRole = 1
    RejectRole = 3

    clicked_role = None  # "accept" | "reject", set per-test

    def __init__(self, parent=None):
        self._buttons = {}

    def setWindowTitle(self, title):
        pass

    def setIcon(self, icon):
        pass

    def setText(self, text):
        self.text = text

    def addButton(self, text, role):
        button = (text, role)
        self._buttons[role] = button
        return button

    def exec_(self):
        return None

    def clickedButton(self):
        role = {"accept": self.AcceptRole, "reject": self.RejectRole}[
            self.clicked_role
        ]
        return self._buttons[role]


def test_profile_btn_handler_stashes_apply_calibration_and_begins(
    window, monkeypatch
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_show_macos_bugs_warning", lambda *a, **k: None)
    monkeypatch.setattr(window, "_check_overwrite", lambda *a, **k: True)
    monkeypatch.setattr(window, "_current_cal_choice", lambda *a, **k: "/tmp/x.cal")
    begin_calls = []
    monkeypatch.setattr(
        window, "begin_measurement", lambda action, **k: begin_calls.append(action)
    )

    window.profile_btn_handler()

    assert window._pending_apply_calibration == "/tmp/x.cal"
    assert begin_calls == [mw.MeasurementAction.PROFILE]


def test_profile_btn_handler_cancelled_cal_choice_aborts(window, monkeypatch):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_show_macos_bugs_warning", lambda *a, **k: None)
    monkeypatch.setattr(window, "_check_overwrite", lambda *a, **k: True)
    monkeypatch.setattr(
        window, "_current_cal_choice", lambda *a, **k: mw.CAL_CHOICE_CANCELLED
    )
    begin_calls = []
    monkeypatch.setattr(
        window, "begin_measurement", lambda action, **k: begin_calls.append(action)
    )

    window.profile_btn_handler()

    assert begin_calls == []


def test_calibrate_btn_handler_overwrite_cancel_aborts(window, monkeypatch):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_show_macos_bugs_warning", lambda *a, **k: None)
    monkeypatch.setattr(window, "_fast_matrix_shaper_choice", lambda *a, **k: False)
    monkeypatch.setattr(window, "_check_overwrite", lambda *a, **k: False)
    begin_calls = []
    monkeypatch.setattr(
        window, "begin_measurement", lambda action, **k: begin_calls.append(action)
    )

    window.calibrate_btn_handler()

    assert begin_calls == []


def test_calibrate_btn_handler_skips_dialog_when_not_applicable(window, monkeypatch):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_show_macos_bugs_warning", lambda *a, **k: None)
    monkeypatch.setattr(
        mw.preflight_checks,
        "resolve_fast_matrix_shaper_choice_info",
        lambda: _fast_matrix_shaper_info(show_dialog=False),
    )
    called = []
    monkeypatch.setattr(
        window, "_fast_matrix_shaper_choice", lambda *a, **k: called.append(True)
    )
    monkeypatch.setattr(window, "_check_overwrite", lambda *a, **k: True)
    begin_calls = []
    monkeypatch.setattr(
        window, "begin_measurement", lambda action, **k: begin_calls.append(action)
    )

    window.calibrate_btn_handler()

    assert called == []
    assert window.worker.dispcal_create_fast_matrix_shaper is False
    assert begin_calls == [mw.MeasurementAction.CALIBRATE]


def test_calibrate_btn_handler_dialog_cancel_aborts(window, monkeypatch):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_show_macos_bugs_warning", lambda *a, **k: None)
    monkeypatch.setattr(
        mw.preflight_checks,
        "resolve_fast_matrix_shaper_choice_info",
        lambda: _fast_matrix_shaper_info(),
    )
    monkeypatch.setattr(window, "_fast_matrix_shaper_choice", lambda info: None)
    begin_calls = []
    monkeypatch.setattr(
        window, "begin_measurement", lambda action, **k: begin_calls.append(action)
    )

    window.calibrate_btn_handler()

    assert begin_calls == []


def test_calibrate_btn_handler_declined_choice_skips_profile_overwrite_check(
    window, monkeypatch
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_show_macos_bugs_warning", lambda *a, **k: None)
    monkeypatch.setattr(
        mw.preflight_checks,
        "resolve_fast_matrix_shaper_choice_info",
        lambda: _fast_matrix_shaper_info(),
    )
    monkeypatch.setattr(window, "_fast_matrix_shaper_choice", lambda info: False)
    setcfg("profile.update", 0)
    exts = []

    def fake_overwrite(ext="", filename=None):
        exts.append(ext)
        return True

    monkeypatch.setattr(window, "_check_overwrite", fake_overwrite)
    begin_calls = []
    monkeypatch.setattr(
        window, "begin_measurement", lambda action, **k: begin_calls.append(action)
    )

    window.calibrate_btn_handler()

    assert exts == [".cal"]
    assert begin_calls == [mw.MeasurementAction.CALIBRATE]
    assert window.worker.dispcal_create_fast_matrix_shaper is False


def test_calibrate_btn_handler_create_choice_also_checks_profile_overwrite(
    window, monkeypatch
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_show_macos_bugs_warning", lambda *a, **k: None)
    monkeypatch.setattr(
        mw.preflight_checks,
        "resolve_fast_matrix_shaper_choice_info",
        lambda: _fast_matrix_shaper_info(),
    )
    monkeypatch.setattr(window, "_fast_matrix_shaper_choice", lambda info: True)
    exts = []

    def fake_overwrite(ext="", filename=None):
        exts.append(ext)
        return True

    monkeypatch.setattr(window, "_check_overwrite", fake_overwrite)
    begin_calls = []
    monkeypatch.setattr(
        window, "begin_measurement", lambda action, **k: begin_calls.append(action)
    )

    window.calibrate_btn_handler()

    assert exts == [".cal", mw.PROFILE_EXT]
    assert begin_calls == [mw.MeasurementAction.CALIBRATE]
    assert window.worker.dispcal_create_fast_matrix_shaper is True


def test_calibrate_btn_handler_update_profile_choice_persists_config(
    window, monkeypatch
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_show_macos_bugs_warning", lambda *a, **k: None)
    setcfg("profile.update", 0)
    monkeypatch.setattr(
        mw.preflight_checks,
        "resolve_fast_matrix_shaper_choice_info",
        lambda: _fast_matrix_shaper_info(
            update_profile=True,
            msg_key="calibration.update_profile_choice",
            ok_key="profile.update",
        ),
    )
    monkeypatch.setattr(window, "_fast_matrix_shaper_choice", lambda info: True)
    monkeypatch.setattr(window, "_check_overwrite", lambda *a, **k: True)
    monkeypatch.setattr(window, "begin_measurement", lambda action, **k: None)

    window.calibrate_btn_handler()

    assert getcfg("profile.update") == 1


def test_calibrate_and_profile_btn_handler_runs_all_overwrite_checks(
    window, monkeypatch
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_show_macos_bugs_warning", lambda *a, **k: None)
    exts = []

    def fake_overwrite(ext="", filename=None):
        exts.append(ext)
        return True

    monkeypatch.setattr(window, "_check_overwrite", fake_overwrite)
    begin_calls = []
    monkeypatch.setattr(
        window, "begin_measurement", lambda action, **k: begin_calls.append(action)
    )

    window.calibrate_and_profile_btn_handler()

    assert exts == [".cal", ".ti3", mw.PROFILE_EXT]
    assert begin_calls == [mw.MeasurementAction.CALIBRATE_AND_PROFILE]


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


def test_calibrate_only_finished_always_refreshes_calibration_file_ctrl(
    window, monkeypatch
):
    # "" is the valid falsy value for "trc" (0 is out of its numeric range and
    # would just bounce back to the 2.2 default via validate_value_type).
    setcfg("profile.update", 0)
    setcfg("trc", "")
    window.worker.dispcal_create_fast_matrix_shaper = False
    updated = []
    monkeypatch.setattr(
        window, "update_calibration_file_ctrl", lambda: updated.append(True)
    )

    window._on_calibration_finished(mw.MeasurementAction.CALIBRATE, True)

    assert updated == [True]


def test_calibrate_only_profile_update_chains_profile_build_finished(
    window, monkeypatch
):
    setcfg("profile.update", 1)
    window.worker.dispcal_create_fast_matrix_shaper = False
    monkeypatch.setattr(window, "update_calibration_file_ctrl", lambda: None)
    monkeypatch.setattr(
        mw.profile_finish, "resolve_profile_path", lambda: "/tmp/quick.icc"
    )
    calls = []
    monkeypatch.setattr(
        window,
        "_on_profile_build_finished",
        lambda result, success_msg="": calls.append((result, success_msg)),
    )

    window._on_calibration_finished(mw.MeasurementAction.CALIBRATE, True)

    assert calls == [("/tmp/quick.icc", lang.getstr("calibration.complete"))]


def test_calibrate_only_fast_matrix_shaper_chains_profile_build_finished(
    window, monkeypatch
):
    setcfg("profile.update", 0)
    window.worker.dispcal_create_fast_matrix_shaper = True
    monkeypatch.setattr(window, "update_calibration_file_ctrl", lambda: None)
    monkeypatch.setattr(
        mw.profile_finish, "resolve_profile_path", lambda: "/tmp/quick.icc"
    )
    calls = []
    monkeypatch.setattr(
        window,
        "_on_profile_build_finished",
        lambda result, success_msg="": calls.append((result, success_msg)),
    )

    window._on_calibration_finished(mw.MeasurementAction.CALIBRATE, True)

    assert calls == [("/tmp/quick.icc", lang.getstr("calibration.complete"))]


def test_calibrate_only_trc_loads_cal_and_shows_completion(window, monkeypatch):
    setcfg("profile.update", 0)
    setcfg("trc", 2.2)
    window.worker.dispcal_create_fast_matrix_shaper = False
    monkeypatch.setattr(window, "update_calibration_file_ctrl", lambda: None)
    load_calls = []
    monkeypatch.setattr(
        window, "_load_cal", lambda **kwargs: load_calls.append(kwargs)
    )
    infos = []
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: infos.append(a))

    window._on_calibration_finished(mw.MeasurementAction.CALIBRATE, True)

    assert load_calls == [{"silent": True}]
    assert infos
    assert lang.getstr("calibration.complete") in infos[0][2]


def test_calibrate_only_neither_profile_update_nor_trc_shows_no_dialog(
    window, monkeypatch
):
    setcfg("profile.update", 0)
    setcfg("trc", "")
    window.worker.dispcal_create_fast_matrix_shaper = False
    monkeypatch.setattr(window, "update_calibration_file_ctrl", lambda: None)
    infos = []
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: infos.append(a))

    window._on_calibration_finished(mw.MeasurementAction.CALIBRATE, True)

    assert infos == []


def test_load_cal_no_file_returns_false(window, monkeypatch):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    setcfg("calibration.file", None)

    assert window._load_cal() is False


def test_load_cal_autoload_off_is_a_noop(window, monkeypatch, tmp_path):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    cal_path = tmp_path / "some.cal"
    cal_path.write_text("")
    setcfg("calibration.file", str(cal_path))
    setcfg("calibration.autoload", 0)
    called = []
    monkeypatch.setattr(
        window.worker, "prepare_dispwin", lambda *a, **k: called.append(True)
    )

    assert window._load_cal() is True
    assert called == []


def test_load_cal_autoload_on_runs_dispwin(window, monkeypatch, tmp_path):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    cal_path = tmp_path / "some.cal"
    cal_path.write_text("")
    setcfg("calibration.file", str(cal_path))
    setcfg("calibration.autoload", 1)
    prepare_calls = []
    monkeypatch.setattr(
        window.worker,
        "prepare_dispwin",
        lambda cal, profile_path, install: prepare_calls.append(
            (cal, profile_path, install)
        )
        or ("dispwin", ["-v"]),
    )
    exec_calls = []
    monkeypatch.setattr(
        window.worker,
        "exec_cmd",
        lambda *a, **k: exec_calls.append((a, k)) or True,
    )

    assert window._load_cal(silent=True) is True
    assert prepare_calls == [(str(cal_path), None, False)]
    assert exec_calls[0][1]["silent"] is True


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
    monkeypatch.setattr(window, "_build_profile_from_measurement", lambda: None)

    window._on_measurement_finished(True)

    assert logged


def test_measurement_finished_success_builds_profile(window, monkeypatch):
    monkeypatch.setattr(window.worker, "log", lambda *a, **k: None)
    built = []
    monkeypatch.setattr(
        window, "_build_profile_from_measurement", lambda: built.append(True)
    )

    window._on_measurement_finished(True)

    assert built == [True]


# --- building the profile (colprof stage) -----------------------------------


def test_build_profile_wrapup_exception_shows_error(window, monkeypatch):
    monkeypatch.setattr(
        window.worker, "wrapup", lambda **kwargs: RuntimeError("copy failed")
    )
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    ran = []
    monkeypatch.setattr(mw.WorkerRunController, "run", lambda *a, **k: ran.append(True))

    window._build_profile_from_measurement()

    assert errors
    assert "copy failed" in errors[0][2]
    assert ran == []


def test_build_profile_runs_create_profile_through_controller(window, monkeypatch):
    monkeypatch.setattr(window.worker, "wrapup", lambda **kwargs: True)
    calls = {}

    def fake_run(_ctrl, producer, consumer=None, **kwargs):
        calls["producer"] = producer
        calls["consumer"] = consumer
        calls["wkwargs"] = kwargs.get("wkwargs")
        calls["pauseable"] = kwargs.get("pauseable")

    monkeypatch.setattr(mw.WorkerRunController, "run", fake_run)

    window._build_profile_from_measurement()

    assert calls["producer"] == window.worker.create_profile
    assert calls["consumer"] == window._on_profile_build_finished
    assert calls["wkwargs"] == {"tags": True}
    assert calls["pauseable"] is False


def test_profile_build_finished_exception_shows_error(window, monkeypatch):
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))

    window._on_profile_build_finished(ValueError("colprof boom"))

    assert errors
    assert "colprof boom" in errors[0][2]


def test_profile_build_finished_incomplete_shows_notice(window, monkeypatch):
    setcfg("dry_run", 0)
    infos = []
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: infos.append(a))

    window._on_profile_build_finished(False)

    assert infos
    assert lang.getstr("profiling.incomplete") in infos[0][2]


def test_profile_build_finished_incomplete_silent_on_dry_run(window, monkeypatch):
    setcfg("dry_run", 1)
    infos = []
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: infos.append(a))

    window._on_profile_build_finished(False)

    assert infos == []


def test_profile_build_finished_invalid_profile_shows_error(window, monkeypatch, tmp_path):
    bogus = tmp_path / "bogus.icc"
    bogus.write_bytes(b"not a profile")
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))

    window._on_profile_build_finished(str(bogus))

    assert errors
    assert str(bogus) in errors[0][2]


def test_profile_build_finished_success_offers_install(
    window, monkeypatch, srgb_profile_path
):
    setcfg("calibration.file", None)
    setcfg("3dlut.create", 0)
    monkeypatch.setattr(window.worker, "log", lambda *a, **k: None)
    updated = []
    monkeypatch.setattr(
        window, "update_calibration_file_ctrl", lambda: updated.append(True)
    )
    monkeypatch.setattr(
        mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Yes
    )
    installed = []
    monkeypatch.setattr(
        window, "install_profile_btn_handler", lambda: installed.append(True)
    )

    window._on_profile_build_finished(srgb_profile_path)

    assert updated == [True]
    assert installed == [True]
    assert getcfg("calibration.file") == srgb_profile_path


def test_profile_build_finished_success_declines_install(
    window, monkeypatch, srgb_profile_path
):
    setcfg("calibration.file", None)
    setcfg("3dlut.create", 0)
    monkeypatch.setattr(window.worker, "log", lambda *a, **k: None)
    monkeypatch.setattr(window, "update_calibration_file_ctrl", lambda: None)
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.No)
    installed = []
    monkeypatch.setattr(
        window, "install_profile_btn_handler", lambda: installed.append(True)
    )

    window._on_profile_build_finished(srgb_profile_path)

    assert installed == []


# --- 3D LUT creation ---------------------------------------------------------


def test_lut3d_create_btn_handler_missing_argyll_bin_aborts(window, monkeypatch):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: False)
    ran = []
    monkeypatch.setattr(mw.WorkerRunController, "run", lambda *a, **k: ran.append(True))

    window.lut3d_create_btn_handler()

    assert ran == []


def test_lut3d_create_btn_handler_missing_input_profile_shows_error(
    window, monkeypatch
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    setcfg("3dlut.input.profile", "/no/such/profile.icc")
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    ran = []
    monkeypatch.setattr(mw.WorkerRunController, "run", lambda *a, **k: ran.append(True))

    window.lut3d_create_btn_handler()

    assert errors
    assert ran == []


def test_lut3d_create_btn_handler_invalid_input_profile_shows_error(
    window, monkeypatch, tmp_path
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    bogus = tmp_path / "bogus.icc"
    bogus.write_bytes(b"not a profile")
    setcfg("3dlut.input.profile", str(bogus))
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    ran = []
    monkeypatch.setattr(mw.WorkerRunController, "run", lambda *a, **k: ran.append(True))

    window.lut3d_create_btn_handler()

    assert errors
    assert str(bogus) in errors[0][2]
    assert ran == []


def test_lut3d_create_btn_handler_no_current_profile_shows_error(
    window, monkeypatch, lut3d_input_profile_path
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    setcfg("3dlut.input.profile", lut3d_input_profile_path)
    setcfg("calibration.file", None)
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    ran = []
    monkeypatch.setattr(mw.WorkerRunController, "run", lambda *a, **k: ran.append(True))

    window.lut3d_create_btn_handler()

    assert errors
    assert ran == []


def test_lut3d_create_btn_handler_same_profile_cancel_aborts(
    window, monkeypatch, srgb_profile_path
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    setcfg("3dlut.input.profile", srgb_profile_path)
    setcfg("calibration.file", srgb_profile_path)
    monkeypatch.setattr(
        mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Cancel
    )
    ran = []
    monkeypatch.setattr(mw.WorkerRunController, "run", lambda *a, **k: ran.append(True))

    window.lut3d_create_btn_handler()

    assert ran == []


def test_lut3d_create_btn_handler_write_access_denied_shows_error(
    window, monkeypatch, srgb_profile_path, lut3d_input_profile_path
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    setcfg("3dlut.input.profile", lut3d_input_profile_path)
    setcfg("calibration.file", srgb_profile_path)
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: False)
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    ran = []
    monkeypatch.setattr(mw.WorkerRunController, "run", lambda *a, **k: ran.append(True))

    window.lut3d_create_btn_handler()

    assert errors
    assert ran == []


def test_lut3d_create_btn_handler_overwrite_declined_aborts(
    window, monkeypatch, srgb_profile_path, lut3d_input_profile_path
):
    # ``waccess`` and the overwrite check's ``os.path.isfile`` are both
    # mocked so the handler never touches the real filesystem (a real
    # ``waccess`` write-probe next to the checked-in test fixtures is both
    # unnecessary for this test and, via ``tempfile.TemporaryFile``, prone to
    # hanging in some sandboxed environments).
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    setcfg("3dlut.input.profile", lut3d_input_profile_path)
    setcfg("calibration.file", srgb_profile_path)
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    monkeypatch.setattr(os.path, "isfile", lambda p: True)
    monkeypatch.setattr(
        mw.QMessageBox, "warning", lambda *a, **k: mw.QMessageBox.Cancel
    )
    ran = []
    monkeypatch.setattr(mw.WorkerRunController, "run", lambda *a, **k: ran.append(True))

    window.lut3d_create_btn_handler()

    assert ran == []


def test_lut3d_create_btn_handler_runs_create_3dlut_through_controller(
    window, monkeypatch, srgb_profile_path, lut3d_input_profile_path
):
    # See the overwrite-declined test above for why ``waccess`` is mocked.
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    setcfg("3dlut.input.profile", lut3d_input_profile_path)
    setcfg("calibration.file", srgb_profile_path)
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    calls = {}

    def fake_run(_ctrl, producer, consumer=None, **kwargs):
        calls["producer"] = producer
        calls["consumer"] = consumer
        calls["wargs"] = kwargs.get("wargs")
        calls["wkwargs"] = kwargs.get("wkwargs")
        calls["pauseable"] = kwargs.get("pauseable")

    monkeypatch.setattr(mw.WorkerRunController, "run", fake_run)

    window.lut3d_create_btn_handler()

    assert calls["producer"] == window.worker.create_3dlut
    assert calls["consumer"] == window._on_lut3d_create_finished
    profile_in_arg, path_arg, profile_abst_arg, profile_out_arg = calls["wargs"]
    assert profile_in_arg.filename == lut3d_input_profile_path
    assert profile_abst_arg is None
    assert profile_out_arg.filename == srgb_profile_path
    assert path_arg
    assert calls["wkwargs"]["file_format"] == getcfg("3dlut.format")
    assert calls["wkwargs"]["intent"] == getcfg("3dlut.rendering_intent")
    assert calls["pauseable"] is False


def test_lut3d_create_btn_handler_always_applies_trc_for_embedded_tab(
    window, monkeypatch, srgb_profile_path, lut3d_input_profile_path
):
    """The embedded tab has no ``lut3d_trc_apply_none_ctrl``, so wx applies
    the configured TRC regardless of ``3dlut.apply_trc`` (unlike the
    standalone 3D LUT maker)."""
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    setcfg("3dlut.input.profile", lut3d_input_profile_path)
    setcfg("calibration.file", srgb_profile_path)
    setcfg("3dlut.apply_trc", 0)
    setcfg("3dlut.trc", "gamma2.2")
    setcfg("3dlut.trc_gamma", 2.4)
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    calls = {}
    monkeypatch.setattr(
        mw.WorkerRunController,
        "run",
        lambda _ctrl, producer, consumer=None, **k: calls.update(
            {"wkwargs": k.get("wkwargs")}
        ),
    )

    window.lut3d_create_btn_handler()

    assert calls["wkwargs"]["trc_gamma"] == 2.4


def test_on_lut3d_create_finished_exception_shows_error(window, monkeypatch):
    monkeypatch.setattr(window.worker, "wrapup", lambda *a, **k: None)
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))

    window._on_lut3d_create_finished(RuntimeError("collink failed"))

    assert errors
    assert "collink failed" in errors[0][2]


def test_on_lut3d_create_finished_incomplete_is_silent(window, monkeypatch):
    monkeypatch.setattr(window.worker, "wrapup", lambda *a, **k: None)
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))

    window._on_lut3d_create_finished(False)

    assert errors == []


def test_on_lut3d_create_finished_success_no_file_on_disk_no_offer(window, monkeypatch):
    # ``worker.lut3d_get_filename`` is deterministic from config but nothing
    # actually wrote a file there, so the offer is skipped (mirrors wx, which
    # only shows the ConfirmDialog once ``self.lut3d_path`` exists on disk).
    monkeypatch.setattr(window.worker, "wrapup", lambda *a, **k: None)
    exec_calls = []
    monkeypatch.setattr(mw.QMessageBox, "exec_", lambda self: exec_calls.append(True))

    window._on_lut3d_create_finished(True)

    assert exec_calls == []


# --- 3D LUT install-offer chain ---------------------------------------------


def test_offer_install_3dlut_ok_label_madvr_uses_install_wording(
    window, monkeypatch, tmp_path
):
    lut_path = tmp_path / "lut.3dlut"
    lut_path.write_bytes(b"lut")
    monkeypatch.setattr(window.worker, "lut3d_get_filename", lambda: str(lut_path))
    setcfg("3dlut.format", "madVR")
    monkeypatch.setattr(mw, "QMessageBox", _FakeTwoButtonMessageBox)
    _FakeTwoButtonMessageBox.clicked_role = "reject"
    boxes = []

    def fake_init(self, parent=None):
        boxes.append(self)
        self._buttons = {}

    monkeypatch.setattr(_FakeTwoButtonMessageBox, "__init__", fake_init)

    window._offer_install_3dlut()

    assert boxes
    ok_label, _role = boxes[0]._buttons[_FakeTwoButtonMessageBox.AcceptRole]
    assert ok_label == lang.getstr("3dlut.install")


def test_offer_install_3dlut_ok_label_plain_format_uses_save_as_wording(
    window, monkeypatch, tmp_path
):
    lut_path = tmp_path / "lut.cube"
    lut_path.write_bytes(b"lut")
    monkeypatch.setattr(window.worker, "lut3d_get_filename", lambda: str(lut_path))
    setcfg("3dlut.format", "cube")
    monkeypatch.setattr(mw, "QMessageBox", _FakeTwoButtonMessageBox)
    _FakeTwoButtonMessageBox.clicked_role = "reject"
    boxes = []

    def fake_init(self, parent=None):
        boxes.append(self)
        self._buttons = {}

    monkeypatch.setattr(_FakeTwoButtonMessageBox, "__init__", fake_init)

    window._offer_install_3dlut()

    assert boxes
    ok_label, _role = boxes[0]._buttons[_FakeTwoButtonMessageBox.AcceptRole]
    assert ok_label == lang.getstr("3dlut.save_as")


def test_offer_install_3dlut_declines_does_not_install(window, monkeypatch, tmp_path):
    lut_path = tmp_path / "lut.cube"
    lut_path.write_bytes(b"lut")
    monkeypatch.setattr(window.worker, "lut3d_get_filename", lambda: str(lut_path))
    setcfg("3dlut.format", "cube")
    monkeypatch.setattr(mw, "QMessageBox", _FakeTwoButtonMessageBox)
    _FakeTwoButtonMessageBox.clicked_role = "reject"
    installed = []
    monkeypatch.setattr(window, "_install_3dlut", lambda *a, **k: installed.append(True))

    window._offer_install_3dlut()

    assert installed == []


def test_offer_install_3dlut_accepts_routes_to_install(window, monkeypatch, tmp_path):
    lut_path = tmp_path / "lut.cube"
    lut_path.write_bytes(b"lut")
    monkeypatch.setattr(window.worker, "lut3d_get_filename", lambda: str(lut_path))
    setcfg("3dlut.format", "cube")
    monkeypatch.setattr(mw, "QMessageBox", _FakeTwoButtonMessageBox)
    _FakeTwoButtonMessageBox.clicked_role = "accept"
    calls = []
    monkeypatch.setattr(
        window,
        "_install_3dlut",
        lambda path, fmt, prisma: calls.append((path, fmt, prisma)),
    )

    window._offer_install_3dlut("custom message")

    assert calls == [(str(lut_path), "cube", False)]


def test_install_3dlut_madvr_shows_not_available_notice(window, monkeypatch):
    setcfg("3dlut.trc", "gamma2.2")
    infos = []
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: infos.append(a))
    copies = []
    monkeypatch.setattr(
        mw.lut3d_settings, "install_via_copy", lambda *a, **k: copies.append(a)
    )

    window._install_3dlut("/tmp/lut.3dlut", "madVR", False)

    assert infos
    assert copies == []


def test_install_3dlut_prisma_shows_not_available_notice(window, monkeypatch):
    infos = []
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: infos.append(a))
    copies = []
    monkeypatch.setattr(
        mw.lut3d_settings, "install_via_copy", lambda *a, **k: copies.append(a)
    )

    window._install_3dlut("/tmp/lut.3dl", "3dl", True)

    assert infos
    assert copies == []


def test_install_3dlut_plain_format_prompts_and_copies(window, monkeypatch, tmp_path):
    src = tmp_path / "lut.cube"
    src.write_bytes(b"lut data")
    dst = tmp_path / "dest.cube"
    monkeypatch.setattr(
        window, "_prompt_3dlut_copy_destination", lambda fmt, path: str(dst)
    )
    setcfg("3dlut.size", 33)
    setcfg("3dlut.bitdepth.output", 16)

    window._install_3dlut(str(src), "cube", False)

    assert dst.read_bytes() == b"lut data"
    assert getcfg("last_3dlut_path") == str(dst)


def test_install_3dlut_cancelled_prompt_does_not_copy(window, monkeypatch, tmp_path):
    src = tmp_path / "lut.cube"
    src.write_bytes(b"lut data")
    monkeypatch.setattr(
        window, "_prompt_3dlut_copy_destination", lambda fmt, path: ""
    )
    copies = []
    monkeypatch.setattr(
        mw.lut3d_settings, "install_via_copy", lambda *a, **k: copies.append(a)
    )

    window._install_3dlut(str(src), "cube", False)

    assert copies == []


def test_install_3dlut_copy_oserror_shows_critical(window, monkeypatch, tmp_path):
    src = tmp_path / "lut.cube"
    src.write_bytes(b"lut data")
    dst = tmp_path / "dest.cube"
    monkeypatch.setattr(
        window, "_prompt_3dlut_copy_destination", lambda fmt, path: str(dst)
    )
    monkeypatch.setattr(
        mw.lut3d_settings,
        "install_via_copy",
        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
    )
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))

    window._install_3dlut(str(src), "cube", False)

    assert errors
    assert "disk full" in errors[0][2]


def test_prompt_3dlut_copy_destination_reshade_uses_folder_dialog(
    window, monkeypatch, tmp_path
):
    monkeypatch.setattr(
        mw.QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path)
    )

    result = window._prompt_3dlut_copy_destination("ReShade", "/tmp/x.png")

    assert result == os.path.join(str(tmp_path), "ColorLookupTable.png")


def test_prompt_3dlut_copy_destination_reshade_cancel_returns_empty(
    window, monkeypatch
):
    monkeypatch.setattr(mw.QFileDialog, "getExistingDirectory", lambda *a, **k: "")

    result = window._prompt_3dlut_copy_destination("ReShade", "/tmp/x.png")

    assert result == ""


def test_prompt_3dlut_copy_destination_plain_uses_save_dialog_with_extension(
    window, monkeypatch, tmp_path
):
    chosen = str(tmp_path / "installed")
    monkeypatch.setattr(
        mw.QFileDialog, "getSaveFileName", lambda *a, **k: (chosen, "")
    )

    result = window._prompt_3dlut_copy_destination("eeColor", "/tmp/lut-3d.txt")

    assert result == chosen + ".txt"


def test_prompt_3dlut_copy_destination_cancel_returns_empty(window, monkeypatch):
    monkeypatch.setattr(mw.QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))

    result = window._prompt_3dlut_copy_destination("cube", "/tmp/lut.cube")

    assert result == ""


def test_prompt_3dlut_copy_destination_overwrite_declined_returns_empty(
    window, monkeypatch, tmp_path
):
    existing = tmp_path / "installed.cube"
    existing.write_bytes(b"already there")
    monkeypatch.setattr(
        mw.QFileDialog, "getSaveFileName", lambda *a, **k: (str(existing), "")
    )
    monkeypatch.setattr(window, "_check_overwrite", lambda **k: False)

    result = window._prompt_3dlut_copy_destination("cube", "/tmp/lut.cube")

    assert result == ""


# --- 3dlut.create auto-chain after profiling --------------------------------


def test_chain_3dlut_after_profile_creates_when_missing(window, monkeypatch, tmp_path):
    missing = tmp_path / "not_there.cube"
    monkeypatch.setattr(window.worker, "lut3d_get_filename", lambda: str(missing))
    created = []
    monkeypatch.setattr(
        window, "lut3d_create_btn_handler", lambda: created.append(True)
    )
    offered = []
    monkeypatch.setattr(
        window, "_offer_install_3dlut", lambda *a, **k: offered.append(True)
    )

    window._chain_3dlut_after_profile()

    assert created == [True]
    assert offered == []


def test_chain_3dlut_after_profile_offers_when_lut_already_exists(
    window, monkeypatch, tmp_path
):
    existing = tmp_path / "already_there.cube"
    existing.write_bytes(b"lut")
    monkeypatch.setattr(window.worker, "lut3d_get_filename", lambda: str(existing))
    created = []
    monkeypatch.setattr(
        window, "lut3d_create_btn_handler", lambda: created.append(True)
    )
    offered = []
    monkeypatch.setattr(
        window, "_offer_install_3dlut", lambda *a, **k: offered.append(a)
    )

    window._chain_3dlut_after_profile()

    assert created == []
    assert offered == [(lang.getstr("calibration_profiling.complete"),)]


def test_profile_build_finished_3dlut_create_on_chains_instead_of_profile_offer(
    window, monkeypatch, srgb_profile_path
):
    setcfg("calibration.file", None)
    setcfg("3dlut.create", 1)
    monkeypatch.setattr(window.worker, "log", lambda *a, **k: None)
    monkeypatch.setattr(window, "update_calibration_file_ctrl", lambda: None)
    chained = []
    monkeypatch.setattr(
        window, "_chain_3dlut_after_profile", lambda: chained.append(True)
    )
    questions = []
    monkeypatch.setattr(
        mw.QMessageBox, "question", lambda *a, **k: questions.append(a) or mw.QMessageBox.Yes
    )

    window._on_profile_build_finished(srgb_profile_path)

    assert chained == [True]
    assert questions == []  # the plain profile-install offer never shown


def test_profile_build_finished_3dlut_create_off_shows_profile_offer_as_before(
    window, monkeypatch, srgb_profile_path
):
    setcfg("calibration.file", None)
    setcfg("3dlut.create", 0)
    monkeypatch.setattr(window.worker, "log", lambda *a, **k: None)
    monkeypatch.setattr(window, "update_calibration_file_ctrl", lambda: None)
    chained = []
    monkeypatch.setattr(
        window, "_chain_3dlut_after_profile", lambda: chained.append(True)
    )
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.No)

    window._on_profile_build_finished(srgb_profile_path)

    assert chained == []


def test_update_action_buttons_shows_lut3d_create_btn_when_manual(window):
    setcfg("3dlut.create", 0)
    window._select_tab("lut3d")

    assert window.lut3d_create_btn.isHidden() is False
    assert window.calibrate_btn.isHidden() is True
    assert window.calibrate_and_profile_btn.isHidden() is True
    assert window.profile_btn.isHidden() is True


def test_update_action_buttons_hides_lut3d_create_btn_when_auto_create(window):
    setcfg("3dlut.create", 1)
    window._select_tab("lut3d")

    assert window.lut3d_create_btn.isHidden() is True


def test_update_action_buttons_hides_lut3d_create_btn_on_other_tabs(window):
    setcfg("3dlut.create", 0)
    window._select_tab("calibration")

    assert window.lut3d_create_btn.isHidden() is True


def test_lut3d_create_btn_enabled_only_for_real_non_preset_profile(
    window, srgb_profile_path
):
    setcfg("calibration.file", srgb_profile_path)
    window._select_tab("lut3d")
    assert window.lut3d_create_btn.isEnabled()

    setcfg("calibration.file", None)
    window._update_action_buttons()
    assert not window.lut3d_create_btn.isEnabled()


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


def test_load_calibration_file_applies_display_instrument_match(window, monkeypatch):
    path = _srgb_preset_path(window)
    monkeypatch.setattr(
        mw.calibration_file,
        "match_display_and_instrument",
        lambda profile, worker: mw.calibration_file.DisplayInstrumentMatch(
            display_index=2,
            display_changed=True,
            reenable_3dlut_tab=True,
            instrument_index=1,
            instrument_match=True,
        ),
    )

    window._load_calibration_file(path, silent=True)

    assert getcfg("display.number") == 3
    assert getcfg("comport.number") == 2
    assert getcfg("3dlut.tab.enable") == 1
    assert getcfg("3dlut.tab.enable.backup") == 1


def test_load_calibration_file_no_display_match_leaves_display_number(
    window, monkeypatch
):
    path = _srgb_preset_path(window)
    setcfg("display.number", 1)
    monkeypatch.setattr(
        mw.calibration_file,
        "match_display_and_instrument",
        lambda profile, worker: mw.calibration_file.DisplayInstrumentMatch(),
    )

    window._load_calibration_file(path, silent=True)

    assert getcfg("display.number") == 1
    # Disabled unconditionally when loading an ICC profile, matching wx.
    assert getcfg("3dlut.tab.enable") == 0


def test_load_calibration_file_routes_legacy_cal_to_parser(
    window, monkeypatch, tmp_path
):
    cal_file = tmp_path / "legacy.cal"
    cal_file.write_bytes(b'DEVICE_CLASS "DISPLAY"\nTARGET_GAMMA "REC709"\n')
    monkeypatch.setattr(mw, "get_options_from_cal", lambda path: ([], []))

    window._load_calibration_file(str(cal_file), silent=True)

    assert getcfg("calibration.file") == str(cal_file)
    assert getcfg("trc") == "709"
    assert getcfg("trc.type") == "g"


def test_load_calibration_file_legacy_cal_invalid_device_class_shows_error(
    window, monkeypatch, tmp_path
):
    cal_file = tmp_path / "legacy.cal"
    cal_file.write_bytes(b'DEVICE_CLASS "PRINTER"\n')
    setcfg("calibration.file", None)
    before = getcfg("calibration.file", False)
    monkeypatch.setattr(mw, "get_options_from_cal", lambda path: ([], []))
    errors = []
    monkeypatch.setattr(
        mw.QMessageBox, "critical", lambda *a, **k: errors.append(a) or None
    )

    window._load_calibration_file(str(cal_file), silent=True)

    assert errors
    assert getcfg("calibration.file", False) == before


def test_load_calibration_file_legacy_cal_no_settings_notifies(
    window, monkeypatch, tmp_path
):
    cal_file = tmp_path / "legacy.cal"
    cal_file.write_bytes(b'DEVICE_CLASS "DISPLAY"\n')
    monkeypatch.setattr(mw, "get_options_from_cal", lambda path: ([], []))
    infos = []
    monkeypatch.setattr(
        mw.QMessageBox, "information", lambda *a, **k: infos.append(a) or None
    )

    window._load_calibration_file(str(cal_file), silent=False)

    assert infos
    assert getcfg("calibration.file") == str(cal_file)


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


def test_load_calibration_file_delegates_archive_extension_to_import(
    window, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        window, "_import_session_archive", lambda path: calls.append(path)
    )
    monkeypatch.setattr(mw.os.path, "exists", lambda _path: True)

    window._load_calibration_file("/tmp/session.zip")

    assert calls == ["/tmp/session.zip"]


def test_import_session_archive_extracts_and_loads_zip(
    window, monkeypatch, tmp_path, qapp
):
    import zipfile

    cal_file = tmp_path / "test.cal"
    cal_file.write_text("dummy")
    archive_path = tmp_path / "test.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(cal_file, "test.cal")
    setcfg("profile.save_path", str(tmp_path / "storage"))

    loaded = []
    monkeypatch.setattr(
        window, "_load_calibration_file", lambda path, **k: loaded.append(path)
    )

    window._import_session_archive(str(archive_path))

    deadline = time.time() + 5.0
    while window._archive_import_thread is not None and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)

    assert len(loaded) == 1
    assert os.path.basename(loaded[0]) == "test.cal"
    assert os.path.exists(loaded[0])


def test_import_session_archive_rejects_non_archive_zip(
    window, monkeypatch, tmp_path, qapp
):
    import zipfile

    other_file = tmp_path / "notes.txt"
    other_file.write_text("dummy")
    archive_path = tmp_path / "test.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(other_file, "notes.txt")
    setcfg("profile.save_path", str(tmp_path / "storage"))

    errors = []
    monkeypatch.setattr(
        mw.QMessageBox, "critical", lambda *a, **k: errors.append(a) or None
    )

    window._import_session_archive(str(archive_path))

    deadline = time.time() + 5.0
    while window._archive_import_thread is not None and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)

    assert errors


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


class _FakeDeleteConfirmationDialog:
    """Stand-in for ``mw._DeleteConfirmationDialog`` that skips the real modal loop."""

    answer = None  # set per-test
    checked: dict | None = None  # set per-test; None keeps every file checked

    def __init__(self, related_files, parent=None):
        self._related_files = related_files

    def exec_(self):
        return self.__class__.answer

    def related_files(self):
        if self.__class__.checked is not None:
            return self.__class__.checked
        return dict(self._related_files)


def test_delete_calibration_handler_declined_keeps_file(window, monkeypatch, tmp_path):
    cal_dir = tmp_path / "session"
    cal_dir.mkdir()
    cal_file = cal_dir / "test.cal"
    cal_file.write_text("dummy")
    setcfg("calibration.file", str(cal_file))
    _FakeDeleteConfirmationDialog.answer = mw.QDialog.Rejected
    monkeypatch.setattr(mw, "_DeleteConfirmationDialog", _FakeDeleteConfirmationDialog)

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
    _FakeDeleteConfirmationDialog.answer = mw.QDialog.Accepted
    _FakeDeleteConfirmationDialog.checked = None
    monkeypatch.setattr(mw, "_DeleteConfirmationDialog", _FakeDeleteConfirmationDialog)

    window.delete_calibration_handler()

    assert not cal_file.exists()
    # Falls back to the default preset, matching wx's own ``setcfg(..., None)``
    # (config resolves a cleared "calibration.file" to ``DEFAULTS`` rather than
    # a falsy value).
    assert getcfg("calibration.file") != str(cal_file)
    assert getcfg("settings.changed") == 1


def test_delete_calibration_handler_unchecked_file_is_kept(window, monkeypatch, tmp_path):
    cal_dir = tmp_path / "session"
    cal_dir.mkdir()
    cal_file = cal_dir / "test.cal"
    cal_file.write_text("dummy")
    related_file = cal_dir / "test.ccmx"
    related_file.write_text("dummy")
    setcfg("calibration.file", str(cal_file))
    _FakeDeleteConfirmationDialog.answer = mw.QDialog.Accepted
    _FakeDeleteConfirmationDialog.checked = {
        "test.cal": True,
        "test.ccmx": False,
    }
    monkeypatch.setattr(mw, "_DeleteConfirmationDialog", _FakeDeleteConfirmationDialog)

    window.delete_calibration_handler()

    assert not cal_file.exists()
    assert related_file.exists()


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


def test_display_tech_info_show_btn_has_label(window):
    lang.init()
    assert (
        window.display_tech_info_show_btn.text()
        == "Show information about common display technologies"
    )


def test_display_tech_info_show_btn_opens_tooltip_window(window):
    lang.init()
    assert getattr(window, "_display_tech_info_window", None) is None
    window._display_tech_info_show_btn_handler()
    assert window._display_tech_info_window is not None
    assert window._display_tech_info_window.isVisible()
    assert window._display_tech_info_window.windowTitle() == "Display technology"


def test_display_tech_info_show_btn_reuses_window_instance(window):
    lang.init()
    window._display_tech_info_show_btn_handler()
    first = window._display_tech_info_window
    window._display_tech_info_show_btn_handler()
    assert window._display_tech_info_window is first


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


# --- Tools > Advanced menu: "check measurement file" / "check automatically" ---


class _FakeTi3:
    """Stand-in for a ``CGATS`` object, controlling just what these handlers read."""

    def __init__(self, modified=True, filename=None):
        self.modified = modified
        self.filename = filename
        self.written_to = None

    def write(self, path):
        self.written_to = path


def test_measurement_file_check_action_handler_cancelled_is_noop(window, monkeypatch):
    monkeypatch.setattr(
        mw.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    calls = []
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "load_measurement_file",
        lambda path: calls.append(path),
    )
    window._measurement_file_check_action_handler()
    assert calls == []


def test_measurement_file_check_action_handler_missing_file_shows_error(
    window, monkeypatch, tmp_path
):
    missing = str(tmp_path / "nope.ti3")
    monkeypatch.setattr(
        mw.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (missing, ""))
    )
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    window._measurement_file_check_action_handler()
    assert errors


def test_measurement_file_check_action_handler_load_error_shows_dialog(
    window, monkeypatch, tmp_path
):
    bogus = tmp_path / "bogus.icc"
    bogus.write_bytes(b"not an icc profile")
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(bogus), "")),
    )
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    window._measurement_file_check_action_handler()
    assert errors


def test_measurement_file_check_action_handler_sanity_declined_is_noop(
    window, monkeypatch, tmp_path
):
    ti3_path = tmp_path / "some.ti3"
    ti3_path.write_bytes(b"dummy")
    loaded = mw.measurement_report_pipeline.MeasurementFileLoad(
        ti3=_FakeTi3(), profile=None
    )
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(ti3_path), "")),
    )
    monkeypatch.setattr(
        mw.measurement_report_pipeline, "load_measurement_file", lambda path: loaded
    )
    monkeypatch.setattr(
        window, "_check_measurement_sanity", lambda ti3, force=False: (False, [])
    )
    infos = []
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: infos.append(a))
    window._measurement_file_check_action_handler()
    assert infos == []
    assert loaded.ti3.written_to is None


def test_measurement_file_check_action_handler_no_suspicious_shows_info(
    window, monkeypatch, tmp_path
):
    ti3_path = tmp_path / "some.ti3"
    ti3_path.write_bytes(b"dummy")
    loaded = mw.measurement_report_pipeline.MeasurementFileLoad(
        ti3=_FakeTi3(modified=False), profile=None
    )
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(ti3_path), "")),
    )
    monkeypatch.setattr(
        mw.measurement_report_pipeline, "load_measurement_file", lambda path: loaded
    )
    monkeypatch.setattr(
        window, "_check_measurement_sanity", lambda ti3, force=False: (True, [])
    )
    infos = []
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: infos.append(a))
    window._measurement_file_check_action_handler()
    assert infos


class _FakeRegenProfile:
    """Stand-in for an ICCProfile, controlling just what the regenerate
    branch of ``_measurement_file_check_action_handler`` touches."""

    def __init__(self):
        self.tags = SimpleNamespace()
        self.written_to = None

    def write(self, path):
        self.written_to = path


def test_measurement_file_check_action_handler_profile_regenerate_cancelled_is_noop(
    window, monkeypatch, tmp_path
):
    icc_path = tmp_path / "some.icc"
    icc_path.write_bytes(b"dummy")
    fake_profile = _FakeRegenProfile()
    loaded = mw.measurement_report_pipeline.MeasurementFileLoad(
        ti3=_FakeTi3(modified=True), profile=fake_profile
    )
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(icc_path), "")),
    )
    monkeypatch.setattr(
        mw.measurement_report_pipeline, "load_measurement_file", lambda path: loaded
    )
    monkeypatch.setattr(
        window, "_check_measurement_sanity", lambda ti3, force=False: (True, [])
    )
    monkeypatch.setattr(
        mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Cancel
    )
    run_calls = []
    monkeypatch.setattr(
        window, "_run_create_profile", lambda paths, **k: run_calls.append(paths)
    )
    window._measurement_file_check_action_handler()
    assert run_calls == []
    assert fake_profile.written_to is None


def test_measurement_file_check_action_handler_profile_regenerate_confirmed_reruns_create_profile(
    window, monkeypatch, tmp_path
):
    icc_path = tmp_path / "some.icc"
    icc_path.write_bytes(b"dummy")
    fake_profile = _FakeRegenProfile()
    loaded = mw.measurement_report_pipeline.MeasurementFileLoad(
        ti3=_FakeTi3(modified=True), profile=fake_profile
    )
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(icc_path), "")),
    )
    monkeypatch.setattr(
        mw.measurement_report_pipeline, "load_measurement_file", lambda path: loaded
    )
    monkeypatch.setattr(
        window, "_check_measurement_sanity", lambda ti3, force=False: (True, [])
    )
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Ok)
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "build_regenerated_profile_tag_data",
        lambda ti3: b"text\0\0\0\0tagdata\0",
    )
    run_calls = []
    monkeypatch.setattr(
        window,
        "_run_create_profile",
        lambda paths, **k: run_calls.append((paths, k)),
    )
    window._measurement_file_check_action_handler()
    assert fake_profile.written_to is not None
    assert fake_profile.tags.targ is fake_profile.tags.DevD
    assert fake_profile.tags.targ is fake_profile.tags.CIED
    assert fake_profile.tags.targ == b"tagdata"
    assert run_calls == [([fake_profile.written_to], {"skip_ti3_check": True})]


def test_measurement_file_check_action_handler_saves_ti3(window, monkeypatch, tmp_path):
    ti3_path = tmp_path / "some.ti3"
    ti3_path.write_bytes(b"dummy")
    save_path = str(tmp_path / "checked.ti3")
    fake_ti3 = _FakeTi3(modified=True)
    loaded = mw.measurement_report_pipeline.MeasurementFileLoad(
        ti3=fake_ti3, profile=None
    )
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(ti3_path), "")),
    )
    monkeypatch.setattr(
        mw.measurement_report_pipeline, "load_measurement_file", lambda path: loaded
    )
    monkeypatch.setattr(
        window, "_check_measurement_sanity", lambda ti3, force=False: (True, [])
    )
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (save_path, "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    window._measurement_file_check_action_handler()
    assert fake_ti3.written_to == save_path


def test_measurement_file_check_action_handler_save_denied_shows_error(
    window, monkeypatch, tmp_path
):
    ti3_path = tmp_path / "some.ti3"
    ti3_path.write_bytes(b"dummy")
    fake_ti3 = _FakeTi3(modified=True)
    loaded = mw.measurement_report_pipeline.MeasurementFileLoad(
        ti3=fake_ti3, profile=None
    )
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(ti3_path), "")),
    )
    monkeypatch.setattr(
        mw.measurement_report_pipeline, "load_measurement_file", lambda path: loaded
    )
    monkeypatch.setattr(
        window, "_check_measurement_sanity", lambda ti3, force=False: (True, [])
    )
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(tmp_path / "out.ti3"), "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: False)
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    window._measurement_file_check_action_handler()
    assert errors
    assert fake_ti3.written_to is None


def test_measurement_file_check_auto_toggle_persists_when_confirmed(
    window, monkeypatch
):
    monkeypatch.setattr(mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Ok)
    window.measurement_file_check_auto_action.setChecked(False)
    window.measurement_file_check_auto_action.setChecked(True)
    assert getcfg("ti3.check_sanity.auto") == 1
    window.measurement_file_check_auto_action.setChecked(False)
    assert getcfg("ti3.check_sanity.auto") == 0


def test_measurement_file_check_auto_toggle_reverts_when_cancelled(
    window, monkeypatch
):
    monkeypatch.setattr(
        mw.QMessageBox, "question", lambda *a, **k: mw.QMessageBox.Cancel
    )
    window.measurement_file_check_auto_action.setChecked(False)
    window.measurement_file_check_auto_action.setChecked(True)
    assert getcfg("ti3.check_sanity.auto") == 0
    assert window.measurement_file_check_auto_action.isChecked() is False


def test_measurement_file_check_auto_toggle_off_skips_confirmation(
    window, monkeypatch
):
    setcfg("ti3.check_sanity.auto", 1)
    window.measurement_file_check_auto_action.setChecked(True)
    calls = []
    monkeypatch.setattr(
        mw.QMessageBox, "question", lambda *a, **k: calls.append(True)
    )
    window.measurement_file_check_auto_action.setChecked(False)
    assert calls == []
    assert getcfg("ti3.check_sanity.auto") == 0


# --- File menu: "create_profile" (create profile from measurement data) ----


class _FakeConfirmMessageBox:
    """Stand-in for ``mw.QMessageBox`` used by the 2-button confirm helpers
    (``_confirm_ti3_no_cal_info`` / ``_confirm_overwrite_profile``)."""

    Warning = 0
    AcceptRole = 1
    RejectRole = 2

    clicked_role = None  # "ok" | "cancel", set per-test

    def __init__(self, parent=None):
        self._buttons = {}

    def setWindowTitle(self, title):
        pass

    def setIcon(self, icon):
        pass

    def setText(self, text):
        self.text = text

    def addButton(self, text, role):
        button = (text, role)
        self._buttons[role] = button
        return button

    def exec_(self):
        return None

    def clickedButton(self):
        role = {"ok": self.AcceptRole, "cancel": self.RejectRole}[self.clicked_role]
        return self._buttons[role]


def test_confirm_ti3_no_cal_info_accepted(window, monkeypatch):
    monkeypatch.setattr(mw, "QMessageBox", _FakeConfirmMessageBox)
    _FakeConfirmMessageBox.clicked_role = "ok"
    assert window._confirm_ti3_no_cal_info() is True


def test_confirm_ti3_no_cal_info_declined(window, monkeypatch):
    monkeypatch.setattr(mw, "QMessageBox", _FakeConfirmMessageBox)
    _FakeConfirmMessageBox.clicked_role = "cancel"
    assert window._confirm_ti3_no_cal_info() is False


def test_confirm_overwrite_profile_accepted(window, monkeypatch):
    monkeypatch.setattr(mw, "QMessageBox", _FakeConfirmMessageBox)
    _FakeConfirmMessageBox.clicked_role = "ok"
    assert window._confirm_overwrite_profile("/x.icc") is True


def test_confirm_overwrite_profile_declined(window, monkeypatch):
    monkeypatch.setattr(mw, "QMessageBox", _FakeConfirmMessageBox)
    _FakeConfirmMessageBox.clicked_role = "cancel"
    assert window._confirm_overwrite_profile("/x.icc") is False


def test_create_profile_action_handler_argyll_bin_missing_is_noop(
    window, monkeypatch
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: False)
    run_calls = []
    monkeypatch.setattr(
        window, "_run_create_profile", lambda *a, **k: run_calls.append(True)
    )
    window._create_profile_action_handler()
    assert run_calls == []


def test_create_profile_action_handler_macos_bugs_warning_cancels(
    window, monkeypatch
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(
        window, "_check_show_macos_bugs_warning", lambda *a, **k: False
    )
    run_calls = []
    monkeypatch.setattr(
        window, "_run_create_profile", lambda *a, **k: run_calls.append(True)
    )
    window._create_profile_action_handler()
    assert run_calls == []


def test_create_profile_action_handler_cancelled_open_dialog_is_noop(
    window, monkeypatch
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_show_macos_bugs_warning", lambda *a, **k: None)
    monkeypatch.setattr(
        mw.QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([], ""))
    )
    run_calls = []
    monkeypatch.setattr(
        window, "_run_create_profile", lambda *a, **k: run_calls.append(True)
    )
    window._create_profile_action_handler()
    assert run_calls == []


def test_create_profile_action_handler_runs_with_selected_paths(
    window, monkeypatch
):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_show_macos_bugs_warning", lambda *a, **k: None)
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileNames",
        staticmethod(lambda *a, **k: (["/a.ti3", "/b.ti3"], "")),
    )
    run_calls = []
    monkeypatch.setattr(
        window, "_run_create_profile", lambda paths: run_calls.append(paths)
    )
    window._create_profile_action_handler()
    assert run_calls == [["/a.ti3", "/b.ti3"]]


def test_build_file_menu_matches_wx_xrc_order(window):
    # mainmenu.xrc's menu.file order, minus the Ctrl+O accelerator (asserted
    # separately) and BaseWindow's own trailing separator/Quit.
    expected = [
        "calibration.load",
        "testchart.set",
        "testchart.edit",
        "profile.set_save_path",
        "",  # separator
        "create_profile",
        "create_profile_from_edid",
        "install_display_profile",
        "profile.share",
        "profile.info",
        "",  # BaseWindow's end separator
        "menuitem.quit",
    ]
    actual = [
        lang.getstr(key) if key else "" for key in expected
    ]
    texts = [action.text() for action in window._file_menu.actions()]
    assert texts == actual
    assert window._file_menu.actions()[0].shortcut().toString() == "Ctrl+O"


def test_select_install_profile_action_handler_cancelled_dialog_is_noop(
    window, monkeypatch
):
    monkeypatch.setattr(
        mw.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    load_calls = []
    monkeypatch.setattr(
        mw, "InstallProfileWindow", lambda: SimpleNamespace(
            load_profile=lambda p: load_calls.append(p)
        )
    )
    window._select_install_profile_action_handler()
    assert load_calls == []


def test_select_install_profile_action_handler_loads_and_shows_window(
    window, monkeypatch, srgb_profile_path
):
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (srgb_profile_path, "")),
    )
    calls = SimpleNamespace(load=[], shown=False, raised=False, activated=False)

    class _FakeInstallWindow:
        def load_profile(self, path):
            calls.load.append(path)

        def show(self):
            calls.shown = True

        def raise_(self):
            calls.raised = True

        def activateWindow(self):
            calls.activated = True

    window._install_profile_window = None
    monkeypatch.setattr(mw, "InstallProfileWindow", _FakeInstallWindow)
    window._select_install_profile_action_handler()
    assert calls.load == [srgb_profile_path]
    assert calls.shown and calls.raised and calls.activated
    assert getcfg("last_icc_path") == srgb_profile_path
    assert getcfg("last_cal_or_icc_path") == srgb_profile_path


def test_profile_share_action_handler_shows_disabled_notice(window, monkeypatch):
    notices = []
    monkeypatch.setattr(
        mw.QMessageBox, "critical", staticmethod(lambda *a, **k: notices.append(a))
    )
    window._profile_share_action_handler()
    assert len(notices) == 1
    assert "icc.opensuse.org" in notices[0][-1]


class _FakeMetaDict(dict):
    def getvalue(self, key, default=None, *_args):
        return self.get(key, default)


class _FakeEdidProfile:
    def __init__(self):
        self.filename = None
        self.write_calls = []
        self.tags = SimpleNamespace(meta=_FakeMetaDict())
        self.gamut_metadata_calls = []
        self.calculate_id_called = False

    def write(self, path=None):
        self.write_calls.append(path)
        if path:
            self.filename = path

    def set_gamut_metadata(self, volume, coverage):
        self.gamut_metadata_calls.append((volume, coverage))

    def calculate_id(self):
        self.calculate_id_called = True


def test_create_profile_from_edid_action_handler_cancelled_save_dialog_is_noop(
    window, monkeypatch
):
    monkeypatch.setattr(
        window.worker, "get_display_edid", lambda: {"monitor_name": "Foo",
                                                      "product_id": 1}
    )
    monkeypatch.setattr(
        mw.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    from_edid_calls = []
    monkeypatch.setattr(
        mw.ICCProfile,
        "from_edid",
        staticmethod(lambda edid: from_edid_calls.append(edid)),
    )
    window._create_profile_from_edid_action_handler()
    assert from_edid_calls == []


def test_create_profile_from_edid_action_handler_write_access_denied_shows_error(
    window, monkeypatch, tmp_path
):
    save_path = str(tmp_path / "edid.icc")
    monkeypatch.setattr(
        window.worker, "get_display_edid", lambda: {"monitor_name": "Foo",
                                                      "product_id": 1}
    )
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (save_path, "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: False)
    errors = []
    monkeypatch.setattr(
        mw.QMessageBox, "critical", staticmethod(lambda *a, **k: errors.append(a))
    )
    from_edid_calls = []
    monkeypatch.setattr(
        mw.ICCProfile,
        "from_edid",
        staticmethod(lambda edid: from_edid_calls.append(edid)),
    )
    window._create_profile_from_edid_action_handler()
    assert len(errors) == 1
    assert from_edid_calls == []


def test_create_profile_from_edid_action_handler_writes_and_finishes_directly(
    window, monkeypatch, tmp_path
):
    save_path = str(tmp_path / "edid.icc")
    edid = {"monitor_name": "Foo", "product_id": 1}
    monkeypatch.setattr(window.worker, "get_display_edid", lambda: edid)
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (save_path, "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    fake_profile = _FakeEdidProfile()
    monkeypatch.setattr(
        mw.ICCProfile, "from_edid", staticmethod(lambda e: fake_profile)
    )
    setcfg("profile.create_gamut_views", 0)
    finish_calls = []
    monkeypatch.setattr(
        window,
        "_create_profile_from_edid_finish",
        lambda result, profile: finish_calls.append((result, profile)),
    )
    window._create_profile_from_edid_action_handler()
    assert fake_profile.write_calls == [save_path]
    assert finish_calls == [(True, fake_profile)]


def test_create_profile_from_edid_action_handler_runs_gamut_calculation(
    window, monkeypatch, tmp_path
):
    save_path = str(tmp_path / "edid.icc")
    edid = {"monitor_name": "Foo", "product_id": 1}
    monkeypatch.setattr(window.worker, "get_display_edid", lambda: edid)
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (save_path, "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    fake_profile = _FakeEdidProfile()
    monkeypatch.setattr(
        mw.ICCProfile, "from_edid", staticmethod(lambda e: fake_profile)
    )
    setcfg("profile.create_gamut_views", 1)
    run_calls = []

    class _FakeController:
        def run(self, *a, **k):
            run_calls.append((a, k))

    monkeypatch.setattr(window, "_ensure_run_controller", lambda: _FakeController())
    # Only the consumer wiring is under test here (see the dedicated
    # ``_create_profile_from_edid_finish`` tests below for its own body);
    # stub out the downstream chain so it doesn't hit a real (blocking) modal.
    monkeypatch.setattr(window, "_on_profile_build_finished", lambda *a, **k: None)
    window._create_profile_from_edid_action_handler()
    assert run_calls
    args, kwargs = run_calls[0]
    assert args[0] == window.worker.calculate_gamut
    assert kwargs["wargs"] == (save_path,)
    assert kwargs["pauseable"] is False
    # The bound consumer closes over fake_profile.
    args[1]((0.9, {}))
    assert fake_profile.gamut_metadata_calls == [(0.9, {})]


def test_create_profile_from_edid_finish_exception_shows_error(window, monkeypatch):
    errors = []
    monkeypatch.setattr(
        mw.QMessageBox, "critical", staticmethod(lambda *a, **k: errors.append(a))
    )
    window._create_profile_from_edid_finish(RuntimeError("boom"), _FakeEdidProfile())
    assert len(errors) == 1


def test_create_profile_from_edid_finish_false_result_is_noop(window, monkeypatch):
    build_calls = []
    monkeypatch.setattr(
        window, "_on_profile_build_finished", lambda *a, **k: build_calls.append(a)
    )
    window._create_profile_from_edid_finish(False, _FakeEdidProfile())
    assert build_calls == []


def test_create_profile_from_edid_finish_plain_success_writes_and_chains(
    window, monkeypatch
):
    fake_profile = _FakeEdidProfile()
    fake_profile.filename = "/tmp/edid.icc"
    build_calls = []
    monkeypatch.setattr(
        window, "_on_profile_build_finished", lambda path: build_calls.append(path)
    )
    window._create_profile_from_edid_finish(True, fake_profile)
    assert fake_profile.write_calls == [None]
    assert fake_profile.calculate_id_called is False
    assert build_calls == ["/tmp/edid.icc"]


def test_create_profile_from_edid_finish_gamut_result_sets_metadata_and_id(
    window, monkeypatch
):
    fake_profile = _FakeEdidProfile()
    fake_profile.filename = "/tmp/edid.icc"
    fake_profile.tags.meta["prefix"] = b"DATA_"
    monkeypatch.setattr(window.worker, "get_device_id", lambda quirk=True: "DEV123")
    build_calls = []
    monkeypatch.setattr(
        window, "_on_profile_build_finished", lambda path: build_calls.append(path)
    )
    window._create_profile_from_edid_finish((0.95, {"sRGB": 0.9}), fake_profile)
    assert fake_profile.gamut_metadata_calls == [(0.95, {"sRGB": 0.9})]
    assert fake_profile.tags.meta["MAPPING_device_id"] == "DEV123"
    assert fake_profile.tags.meta["prefix"] == "DATA_,MAPPING_"
    assert fake_profile.calculate_id_called is True
    assert fake_profile.write_calls == [None]
    assert build_calls == ["/tmp/edid.icc"]


@pytest.fixture
def cp_ti3_path():
    """Path to a real ``.ti3`` with ``CAL``/``ARGYLL_DISPCAL_ARGS`` sections."""
    return os.path.join(
        os.path.dirname(__file__),
        "data",
        "icc",
        "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.ti3",
    )


def test_run_create_profile_missing_file_shows_error(window, monkeypatch, tmp_path):
    missing = str(tmp_path / "nope.ti3")
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    window._run_create_profile([missing])
    assert errors


def test_run_create_profile_load_error_shows_error(window, monkeypatch, tmp_path):
    bogus = tmp_path / "bogus.icc"
    bogus.write_bytes(b"nope")
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    window._run_create_profile([str(bogus)])
    assert errors


def test_run_create_profile_no_cal_info_declined_aborts(window, monkeypatch, tmp_path):
    ti3_path = tmp_path / "no_cal.ti3"
    ti3_path.write_bytes(b"NO_CAL_HERE\n")
    monkeypatch.setattr(window, "_confirm_ti3_no_cal_info", lambda: False)
    save_calls = []
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: save_calls.append(True) or ("", "")),
    )
    window._run_create_profile([str(ti3_path)])
    assert save_calls == []


def test_run_create_profile_save_dialog_cancelled_is_noop(
    window, monkeypatch, cp_ti3_path
):
    monkeypatch.setattr(
        mw.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    controller_calls = []
    monkeypatch.setattr(
        window, "_ensure_run_controller", lambda: controller_calls.append(True)
    )
    window._run_create_profile([cp_ti3_path])
    assert controller_calls == []


def test_run_create_profile_write_access_denied_shows_error(
    window, monkeypatch, cp_ti3_path, tmp_path
):
    save_path = str(tmp_path / "out.icc")
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (save_path, "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: False)
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    window._run_create_profile([cp_ti3_path])
    assert errors


def test_run_create_profile_overwrite_declined_aborts(
    window, monkeypatch, cp_ti3_path, tmp_path
):
    # No .icc/.icm extension typed, so PROFILE_EXT is appended after the save
    # dialog's own overwrite prompt already ran -- the extra confirm is the
    # only thing standing between this and silently clobbering an existing file.
    existing_final = tmp_path / "out.icc"
    existing_final.write_bytes(b"existing")
    typed_path = str(tmp_path / "out")
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (typed_path, "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    monkeypatch.setattr(window, "_confirm_overwrite_profile", lambda path: False)
    controller_calls = []
    monkeypatch.setattr(
        window, "_ensure_run_controller", lambda: controller_calls.append(True)
    )
    window._run_create_profile([cp_ti3_path])
    assert controller_calls == []


def test_run_create_profile_single_file_runs_controller(
    window, monkeypatch, cp_ti3_path, tmp_path
):
    save_path = str(tmp_path / "out.icc")
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (save_path, "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    monkeypatch.setattr(window, "_check_measurement_sanity", lambda ti3: (True, []))
    run_calls = []

    class _FakeController:
        def run(self, *a, **k):
            run_calls.append((a, k))

    monkeypatch.setattr(window, "_ensure_run_controller", lambda: _FakeController())
    window._run_create_profile([cp_ti3_path])
    assert run_calls
    args, kwargs = run_calls[0]
    assert args[0] == window.worker.create_profile
    assert args[1] == window._on_profile_build_finished
    assert kwargs["wkwargs"]["dst_path"] == save_path
    assert kwargs["pauseable"] is False
    assert window.worker.options_targen == ["-d3"]
    assert window.worker.options_dispcal


def test_run_create_profile_sanity_declined_aborts(
    window, monkeypatch, cp_ti3_path, tmp_path
):
    save_path = str(tmp_path / "out.icc")
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (save_path, "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    monkeypatch.setattr(window, "_check_measurement_sanity", lambda ti3: (False, []))
    controller_calls = []
    monkeypatch.setattr(
        window, "_ensure_run_controller", lambda: controller_calls.append(True)
    )
    window._run_create_profile([cp_ti3_path])
    assert controller_calls == []


def test_run_create_profile_skip_ti3_check_bypasses_sanity(
    window, monkeypatch, cp_ti3_path, tmp_path
):
    save_path = str(tmp_path / "out.icc")
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (save_path, "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    sanity_calls = []
    monkeypatch.setattr(
        window,
        "_check_measurement_sanity",
        lambda ti3: sanity_calls.append(True) or (True, []),
    )
    run_calls = []

    class _FakeController:
        def run(self, *a, **k):
            run_calls.append((a, k))

    monkeypatch.setattr(window, "_ensure_run_controller", lambda: _FakeController())
    window._run_create_profile([cp_ti3_path], skip_ti3_check=True)
    assert sanity_calls == []
    assert run_calls


def test_run_create_profile_multi_file_merges_via_average(
    window, monkeypatch, cp_ti3_path, tmp_path
):
    second_path = str(tmp_path / "second.ti3")
    shutil.copyfile(cp_ti3_path, second_path)
    save_path = str(tmp_path / "out.icc")
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (save_path, "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    monkeypatch.setattr(window, "_check_measurement_sanity", lambda ti3: (True, []))
    monkeypatch.setattr(mw.create_profile, "get_argyll_util", lambda name: "average")

    def fake_exec_cmd(cmd, args, **kwargs):
        shutil.copyfile(cp_ti3_path, args[-1])
        return True

    monkeypatch.setattr(window.worker, "exec_cmd", fake_exec_cmd)
    run_calls = []

    class _FakeController:
        def run(self, *a, **k):
            run_calls.append((a, k))

    monkeypatch.setattr(window, "_ensure_run_controller", lambda: _FakeController())
    window._run_create_profile([cp_ti3_path, second_path])
    assert run_calls


def test_run_create_profile_merge_failure_shows_error(
    window, monkeypatch, cp_ti3_path, tmp_path
):
    second_path = str(tmp_path / "second.ti3")
    shutil.copyfile(cp_ti3_path, second_path)
    save_path = str(tmp_path / "out.icc")
    monkeypatch.setattr(
        mw.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (save_path, "")),
    )
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    monkeypatch.setattr(mw.create_profile, "get_argyll_util", lambda name: "average")
    monkeypatch.setattr(window.worker, "exec_cmd", lambda *a, **k: None)
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    window._run_create_profile([cp_ti3_path, second_path])
    assert errors


# --- Tools > Advanced menu: "profile.b2a.hires" (arbitrary-profile picker) ---


class _FakeProfileChoiceMessageBox:
    """Stand-in for ``mw.QMessageBox`` used by ``_select_profile_for_hires_b2a``.

    Mirrors ``_FakeFastMatrixShaperMessageBox``'s ``addButton``/``clickedButton``
    shape for a 3-button dialog.
    """

    Question = 0
    AcceptRole = 1
    ActionRole = 2
    RejectRole = 3

    clicked_role = None  # "current" | "browse" | "cancel", set per-test

    def __init__(self, parent=None):
        self._buttons = {}

    def setWindowTitle(self, title):
        pass

    def setIcon(self, icon):
        pass

    def setText(self, text):
        self.text = text

    def addButton(self, text, role):
        button = (text, role)
        self._buttons[role] = button
        return button

    def exec_(self):
        return None

    def clickedButton(self):
        role = {
            "current": self.AcceptRole,
            "browse": self.ActionRole,
            "cancel": self.RejectRole,
        }[self.clicked_role]
        return self._buttons[role]


def test_select_profile_for_hires_b2a_no_current_profile_browses(
    window, monkeypatch, hires_b2a_profile_path
):
    monkeypatch.setattr(mw.config, "get_current_profile", lambda *a, **k: None)
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (hires_b2a_profile_path, "")),
    )
    profile = window._select_profile_for_hires_b2a()
    assert isinstance(profile, mw.ICCProfile)


def test_select_profile_for_hires_b2a_no_current_profile_cancelled_browse(
    window, monkeypatch
):
    monkeypatch.setattr(mw.config, "get_current_profile", lambda *a, **k: None)
    monkeypatch.setattr(
        mw.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    assert window._select_profile_for_hires_b2a() is None


def test_select_profile_for_hires_b2a_invalid_profile_shows_error(
    window, monkeypatch, tmp_path
):
    monkeypatch.setattr(mw.config, "get_current_profile", lambda *a, **k: None)
    bogus = tmp_path / "bogus.icc"
    bogus.write_bytes(b"nope")
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(bogus), "")),
    )
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    assert window._select_profile_for_hires_b2a() is None
    assert errors


def test_select_profile_for_hires_b2a_uses_current_profile(
    window, monkeypatch, hires_b2a_profile_path
):
    current = mw.ICCProfile(hires_b2a_profile_path)
    monkeypatch.setattr(mw.config, "get_current_profile", lambda *a, **k: current)
    monkeypatch.setattr(mw, "QMessageBox", _FakeProfileChoiceMessageBox)
    _FakeProfileChoiceMessageBox.clicked_role = "current"
    assert window._select_profile_for_hires_b2a() is current


def test_select_profile_for_hires_b2a_browse_from_current_choice(
    window, monkeypatch, hires_b2a_profile_path
):
    current = mw.ICCProfile(hires_b2a_profile_path)
    monkeypatch.setattr(mw.config, "get_current_profile", lambda *a, **k: current)
    monkeypatch.setattr(mw, "QMessageBox", _FakeProfileChoiceMessageBox)
    _FakeProfileChoiceMessageBox.clicked_role = "browse"
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (hires_b2a_profile_path, "")),
    )
    profile = window._select_profile_for_hires_b2a()
    assert profile is not current
    assert isinstance(profile, mw.ICCProfile)


def test_select_profile_for_hires_b2a_cancel_from_current_choice(
    window, monkeypatch, hires_b2a_profile_path
):
    current = mw.ICCProfile(hires_b2a_profile_path)
    monkeypatch.setattr(mw.config, "get_current_profile", lambda *a, **k: current)
    monkeypatch.setattr(mw, "QMessageBox", _FakeProfileChoiceMessageBox)
    _FakeProfileChoiceMessageBox.clicked_role = "cancel"
    assert window._select_profile_for_hires_b2a() is None


def test_profile_hires_b2a_action_handler_no_profile_selected_is_noop(
    window, monkeypatch
):
    monkeypatch.setattr(window, "_select_profile_for_hires_b2a", lambda: None)
    controller_calls = []
    monkeypatch.setattr(
        window,
        "_ensure_run_controller",
        lambda: controller_calls.append(True),
    )
    window._profile_hires_b2a_action_handler()
    assert controller_calls == []


def test_profile_hires_b2a_action_handler_missing_a2b_shows_error(
    window, monkeypatch
):
    profile = SimpleNamespace(tags={})
    monkeypatch.setattr(window, "_select_profile_for_hires_b2a", lambda: profile)
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    window._profile_hires_b2a_action_handler()
    assert errors


def test_profile_hires_b2a_action_handler_wrong_pcs_shows_error(
    window, monkeypatch, hires_b2a_profile_path
):
    profile = mw.ICCProfile(hires_b2a_profile_path)
    profile.connectionColorSpace = b"RGB"
    monkeypatch.setattr(window, "_select_profile_for_hires_b2a", lambda: profile)
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    window._profile_hires_b2a_action_handler()
    assert errors


def test_profile_hires_b2a_action_handler_runs_worker(
    window, monkeypatch, hires_b2a_profile_path
):
    profile = mw.ICCProfile(hires_b2a_profile_path)
    monkeypatch.setattr(window, "_select_profile_for_hires_b2a", lambda: profile)
    run_calls = []

    class _FakeController:
        def run(self, *a, **k):
            run_calls.append((a, k))

    monkeypatch.setattr(window, "_ensure_run_controller", lambda: _FakeController())
    window._profile_hires_b2a_action_handler()
    assert run_calls
    assert window._pending_hires_b2a_profile is profile
    args, kwargs = run_calls[0]
    assert args[0] == window.worker.update_profile_B2A
    assert kwargs["wargs"] == (profile,)


# --- Tools > Advanced menu: "synthicc.create" -------------------------------


def test_synthicc_create_action_handler_opens_window(window):
    window._synthicc_create_action_handler()
    try:
        assert window._synthicc_window is not None
    finally:
        window._synthicc_window.close()


def test_synthicc_create_action_handler_reuses_window_instance(window):
    window._synthicc_create_action_handler()
    try:
        first = window._synthicc_window
        window._synthicc_create_action_handler()
        assert window._synthicc_window is first
    finally:
        window._synthicc_window.close()


# --- Tools > Advanced menu: "specplot.run" ----------------------------------


def test_specplot_action_handler_no_argyll_bin_is_noop(window, monkeypatch):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: False)
    calls = []
    monkeypatch.setattr(
        mw.QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: calls.append(True) or ("", "")),
    )
    window._specplot_action_handler()
    assert calls == []


def test_specplot_action_handler_cancelled_dialog_is_noop(window, monkeypatch):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(
        mw.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", ""))
    )
    ran = []
    monkeypatch.setattr(mw.WorkerRunController, "run", lambda *a, **k: ran.append(True))
    window._specplot_action_handler()
    assert ran == []


def test_specplot_action_handler_missing_util_shows_error(window, monkeypatch, tmp_path):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    path = str(tmp_path / "sample.sp")
    monkeypatch.setattr(
        mw.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (path, ""))
    )
    monkeypatch.setattr(mw, "get_argyll_util", lambda name: None)
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    window._specplot_action_handler()
    assert errors
    assert getcfg("last_specplot_path") == path


def test_specplot_action_handler_runs_worker(window, monkeypatch, tmp_path):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    path = str(tmp_path / "sample.sp")
    monkeypatch.setattr(
        mw.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (path, ""))
    )
    monkeypatch.setattr(mw, "get_argyll_util", lambda name: "/usr/bin/specplot")
    setcfg("extra_args.specplot", "")
    calls = {}

    def fake_run(_ctrl, producer, consumer=None, **kwargs):
        calls["producer"] = producer
        calls["consumer"] = consumer
        calls["wargs"] = kwargs.get("wargs")
        calls["wkwargs"] = kwargs.get("wkwargs")

    monkeypatch.setattr(mw.WorkerRunController, "run", fake_run)

    window._specplot_action_handler()

    assert calls["producer"] == window.worker.exec_cmd
    assert calls["consumer"] == window._on_specplot_finished
    assert calls["wargs"] == ("/usr/bin/specplot", ["-v", path])
    assert calls["wkwargs"] == {"skip_scripts": True}
    assert window.worker.interactive is False


def test_specplot_action_handler_appends_extra_args(window, monkeypatch, tmp_path):
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    path = str(tmp_path / "sample.sp")
    monkeypatch.setattr(
        mw.QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (path, ""))
    )
    monkeypatch.setattr(mw, "get_argyll_util", lambda name: "/usr/bin/specplot")
    setcfg("extra_args.specplot", "-foo bar")
    calls = {}

    def fake_run(_ctrl, producer, consumer=None, **kwargs):
        calls["wargs"] = kwargs.get("wargs")

    monkeypatch.setattr(mw.WorkerRunController, "run", fake_run)

    window._specplot_action_handler()

    assert calls["wargs"] == ("/usr/bin/specplot", ["-v", "-foo", "bar", path])


def test_on_specplot_finished_exception_shows_error_and_wraps_up(window, monkeypatch):
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    wrapup_calls = []
    monkeypatch.setattr(
        window.worker, "wrapup", lambda *a, **k: wrapup_calls.append(a)
    )
    window._on_specplot_finished(RuntimeError("specplot boom"))
    assert errors
    assert "specplot boom" in errors[0][2]
    assert wrapup_calls == [(False,)]


def test_on_specplot_finished_success_wraps_up(window, monkeypatch):
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    wrapup_calls = []
    monkeypatch.setattr(
        window.worker, "wrapup", lambda *a, **k: wrapup_calls.append(a)
    )
    window._on_specplot_finished(True)
    assert errors == []
    assert wrapup_calls == [(False,)]


# --- Tools > Advanced menu: "measure.testchart" -----------------------------


def test_setup_ccxx_measurement_non_ccxx_is_noop(window, monkeypatch):
    monkeypatch.setattr(mw.config, "is_ccxx_testchart", lambda *a, **k: False)
    assert window._setup_ccxx_measurement() is True
    assert getcfg("measurement.save_path", False) in (False, None, "")


def test_setup_ccxx_measurement_writes_measurement_config(
    window, monkeypatch, tmp_path
):
    monkeypatch.setattr(mw.config, "is_ccxx_testchart", lambda *a, **k: True)
    setcfg("profile.save_path", str(tmp_path))
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "compute_ccxx_measurement_basename",
        lambda worker: "My Measurement",
    )
    assert window._setup_ccxx_measurement() is True
    assert getcfg("measurement.save_path") == str(tmp_path)
    assert getcfg("measurement.name.expanded") == "My Measurement"


def test_setup_ccxx_measurement_prompts_for_save_path_when_unset(
    window, monkeypatch, tmp_path
):
    monkeypatch.setattr(mw.config, "is_ccxx_testchart", lambda *a, **k: True)
    setcfg("profile.save_path", "")
    prompted = []

    def fake_prompt():
        prompted.append(True)
        setcfg("profile.save_path", str(tmp_path))

    monkeypatch.setattr(window, "_profile_save_path_btn_handler", fake_prompt)
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: True)
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "compute_ccxx_measurement_basename",
        lambda worker: "basename",
    )
    assert window._setup_ccxx_measurement() is True
    assert prompted == [True]


def test_setup_ccxx_measurement_save_path_still_empty_after_prompt(
    window, monkeypatch
):
    monkeypatch.setattr(mw.config, "is_ccxx_testchart", lambda *a, **k: True)
    setcfg("profile.save_path", "")
    monkeypatch.setattr(window, "_profile_save_path_btn_handler", lambda: None)
    assert window._setup_ccxx_measurement() is False


def test_setup_ccxx_measurement_write_access_denied_shows_error(
    window, monkeypatch, tmp_path
):
    monkeypatch.setattr(mw.config, "is_ccxx_testchart", lambda *a, **k: True)
    setcfg("profile.save_path", str(tmp_path))
    monkeypatch.setattr(mw, "waccess", lambda *a, **k: False)
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    assert window._setup_ccxx_measurement() is False
    assert errors


def test_measure_testchart_action_handler_ccxx_setup_failure_is_noop(
    window, monkeypatch
):
    monkeypatch.setattr(window, "_setup_ccxx_measurement", lambda: False)
    restored = []
    monkeypatch.setattr(
        window, "_restore_measurement_mode_and_testchart", lambda: restored.append(True)
    )
    began = []
    monkeypatch.setattr(
        window, "_begin_testchart_measurement", lambda: began.append(True)
    )
    window._measure_testchart_action_handler()
    assert began == []
    assert restored == [True]


def test_measure_testchart_action_handler_no_argyll_bin_restores(
    window, monkeypatch
):
    monkeypatch.setattr(window, "_setup_ccxx_measurement", lambda: True)
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: False)
    restored = []
    monkeypatch.setattr(
        window, "_restore_measurement_mode_and_testchart", lambda: restored.append(True)
    )
    began = []
    monkeypatch.setattr(
        window, "_begin_testchart_measurement", lambda: began.append(True)
    )
    window._measure_testchart_action_handler()
    assert began == []
    assert restored == [True]


def test_measure_testchart_action_handler_overwrite_declined_restores(
    window, monkeypatch
):
    monkeypatch.setattr(window, "_setup_ccxx_measurement", lambda: True)
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_overwrite", lambda *a, **k: False)
    restored = []
    monkeypatch.setattr(
        window, "_restore_measurement_mode_and_testchart", lambda: restored.append(True)
    )
    began = []
    monkeypatch.setattr(
        window, "_begin_testchart_measurement", lambda: began.append(True)
    )
    window._measure_testchart_action_handler()
    assert began == []
    assert restored == [True]


def test_measure_testchart_action_handler_ccxx_uses_linear_cal(
    window, monkeypatch
):
    monkeypatch.setattr(window, "_setup_ccxx_measurement", lambda: True)
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_overwrite", lambda *a, **k: True)
    monkeypatch.setattr(mw.config, "is_ccxx_testchart", lambda *a, **k: True)
    monkeypatch.setattr(mw.config, "get_data_path", lambda name: f"/data/{name}")
    began = []
    monkeypatch.setattr(
        window, "_begin_testchart_measurement", lambda: began.append(True)
    )
    window._measure_testchart_action_handler()
    assert began == [True]
    assert window._pending_apply_calibration == "/data/linear.cal"


def test_measure_testchart_action_handler_cal_choice_cancelled_restores(
    window, monkeypatch
):
    monkeypatch.setattr(window, "_setup_ccxx_measurement", lambda: True)
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_overwrite", lambda *a, **k: True)
    monkeypatch.setattr(mw.config, "is_ccxx_testchart", lambda *a, **k: False)
    monkeypatch.setattr(
        window, "_current_cal_choice", lambda *a, **k: mw.CAL_CHOICE_CANCELLED
    )
    restored = []
    monkeypatch.setattr(
        window, "_restore_measurement_mode_and_testchart", lambda: restored.append(True)
    )
    began = []
    monkeypatch.setattr(
        window, "_begin_testchart_measurement", lambda: began.append(True)
    )
    window._measure_testchart_action_handler()
    assert began == []
    assert restored == [True]


def test_measure_testchart_action_handler_stages_cal_choice(window, monkeypatch):
    monkeypatch.setattr(window, "_setup_ccxx_measurement", lambda: True)
    monkeypatch.setattr(mw, "check_set_argyll_bin", lambda: True)
    monkeypatch.setattr(window, "_check_overwrite", lambda *a, **k: True)
    monkeypatch.setattr(mw.config, "is_ccxx_testchart", lambda *a, **k: False)
    monkeypatch.setattr(window, "_current_cal_choice", lambda *a, **k: "/path/to.cal")
    began = []
    monkeypatch.setattr(
        window, "_begin_testchart_measurement", lambda: began.append(True)
    )
    window._measure_testchart_action_handler()
    assert began == [True]
    assert window._pending_apply_calibration == "/path/to.cal"


def test_begin_testchart_measurement_call_pending_runs_immediately(
    window, monkeypatch, _no_writecfg
):
    _force_mode(window, monkeypatch, mf.PresentationMode.CALL_PENDING)
    ran = []
    monkeypatch.setattr(window, "_run_measure_testchart", lambda: ran.append(True))
    _run_pending_synchronously(window)

    window._begin_testchart_measurement()

    assert ran == [True]


def test_begin_testchart_measurement_show_frame_presents_measureframe(
    window, monkeypatch, _no_writecfg
):
    _force_mode(window, monkeypatch, mf.PresentationMode.SHOW_FRAME)
    presented = []
    monkeypatch.setattr(window, "_present_measureframe", lambda: presented.append(True))

    window._begin_testchart_measurement()

    assert presented == [True]


def test_run_measure_testchart_runs_worker(window, monkeypatch):
    monkeypatch.setattr(mw.config, "get_display_name", lambda *a, **k: "DELL U2413")
    window._pending_apply_calibration = "/path/to.cal"
    calls = {}

    def fake_run(_ctrl, producer, consumer=None, **kwargs):
        calls["producer"] = producer
        calls["consumer"] = consumer
        calls["wkwargs"] = kwargs.get("wkwargs")

    monkeypatch.setattr(mw.WorkerRunController, "run", fake_run)

    window._run_measure_testchart()

    assert calls["producer"] == window.worker.measure
    assert calls["consumer"] == window._on_measure_testchart_finished
    assert calls["wkwargs"] == {"apply_calibration": "/path/to.cal"}
    assert window.worker.dispread_after_dispcal is False
    # Reset to the wx default so a later real run isn't left CANCELLED.
    assert window._pending_apply_calibration is True


def test_check_copy_ti3_no_working_ti3_runs_wrapup(window, monkeypatch):
    monkeypatch.setattr(
        mw.measurement_report_pipeline, "resolve_working_ti3_path", lambda w: None
    )
    monkeypatch.setattr(window.worker, "wrapup", lambda **kwargs: True)
    assert window._check_copy_ti3() is True


def test_check_copy_ti3_load_failure_returns_exception(window, monkeypatch, tmp_path):
    ti3_path = str(tmp_path / "missing.ti3")
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "resolve_working_ti3_path",
        lambda w: ti3_path,
    )
    result = window._check_copy_ti3()
    assert isinstance(result, Exception)


def test_check_copy_ti3_sanity_cancelled_skips_wrapup(window, monkeypatch, tmp_path):
    ti3_path = str(tmp_path / "working.ti3")
    (tmp_path / "working.ti3").write_text("dummy")
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "resolve_working_ti3_path",
        lambda w: ti3_path,
    )
    monkeypatch.setattr(mw, "CGATS", lambda path: SimpleNamespace(filename=path))
    monkeypatch.setattr(
        window, "_check_measurement_sanity", lambda ti3, force=False: (False, [])
    )
    ran = []
    monkeypatch.setattr(
        window.worker, "wrapup", lambda **kwargs: ran.append(True) or True
    )
    assert window._check_copy_ti3() is False
    assert ran == []


def test_check_copy_ti3_sanity_proceeds_runs_wrapup(window, monkeypatch, tmp_path):
    ti3_path = str(tmp_path / "working.ti3")
    (tmp_path / "working.ti3").write_text("dummy")
    monkeypatch.setattr(
        mw.measurement_report_pipeline,
        "resolve_working_ti3_path",
        lambda w: ti3_path,
    )
    monkeypatch.setattr(mw, "CGATS", lambda path: SimpleNamespace(filename=path))
    monkeypatch.setattr(
        window, "_check_measurement_sanity", lambda ti3, force=False: (True, [])
    )
    monkeypatch.setattr(window.worker, "wrapup", lambda **kwargs: True)
    assert window._check_copy_ti3() is True


def test_measure_testchart_finished_exception_shows_error(window, monkeypatch):
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    monkeypatch.setattr(window.worker, "wrapup", lambda **kwargs: None)
    restored = []
    monkeypatch.setattr(
        window, "_restore_measurement_mode_and_testchart", lambda: restored.append(True)
    )
    window._on_measure_testchart_finished(RuntimeError("measure boom"))
    assert errors
    assert "measure boom" in errors[0][2]
    assert restored == [True]


def test_measure_testchart_finished_falsy_result_is_silent(window, monkeypatch):
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    monkeypatch.setattr(window.worker, "wrapup", lambda **kwargs: None)
    opened = []
    monkeypatch.setattr(
        window, "_offer_open_measurement_folder", lambda: opened.append(True)
    )
    restored = []
    monkeypatch.setattr(
        window, "_restore_measurement_mode_and_testchart", lambda: restored.append(True)
    )
    window._on_measure_testchart_finished(False)
    assert errors == []
    assert opened == []
    assert restored == [True]


def test_measure_testchart_finished_success_non_ccxx_offers_folder(
    window, monkeypatch
):
    monkeypatch.setattr(window, "_check_copy_ti3", lambda: True)
    monkeypatch.setattr(window.worker, "wrapup", lambda **kwargs: None)
    monkeypatch.setattr(mw.config, "is_ccxx_testchart", lambda *a, **k: False)
    opened = []
    monkeypatch.setattr(
        window, "_offer_open_measurement_folder", lambda: opened.append(True)
    )
    window._on_measure_testchart_finished(True)
    assert opened == [True]


def test_measure_testchart_finished_success_ccxx_records_paths(window, monkeypatch):
    monkeypatch.setattr(window, "_check_copy_ti3", lambda: True)
    monkeypatch.setattr(window.worker, "wrapup", lambda **kwargs: None)
    monkeypatch.setattr(mw.config, "is_ccxx_testchart", lambda *a, **k: True)
    recorded = []
    monkeypatch.setattr(
        window, "_record_ccxx_measurement_paths", lambda: recorded.append(True)
    )
    window._on_measure_testchart_finished(True)
    assert recorded == [True]


def test_record_ccxx_measurement_paths_spectral(window, monkeypatch, tmp_path):
    setcfg("measurement.save_path", str(tmp_path))
    setcfg("measurement.name.expanded", "meas")
    ti3_path = os.path.join(str(tmp_path), "meas", "meas.ti3")

    class _FakeCGATS:
        def __init__(self, path):
            self.filename = path

        def queryv1(self, key):
            return b"YES" if key == "INSTRUMENT_TYPE_SPECTRAL" else None

    monkeypatch.setattr(mw, "CGATS", _FakeCGATS)
    window._record_ccxx_measurement_paths()
    assert getcfg("last_reference_ti3_path") == ti3_path


def test_record_ccxx_measurement_paths_colorimeter(window, monkeypatch, tmp_path):
    setcfg("measurement.save_path", str(tmp_path))
    setcfg("measurement.name.expanded", "meas")
    ti3_path = os.path.join(str(tmp_path), "meas", "meas.ti3")

    class _FakeCGATS:
        def __init__(self, path):
            self.filename = path

        def queryv1(self, key):
            return None

    monkeypatch.setattr(mw, "CGATS", _FakeCGATS)
    window._record_ccxx_measurement_paths()
    assert getcfg("last_colorimeter_ti3_path") == ti3_path


def test_record_ccxx_measurement_paths_load_failure_shows_error(window, monkeypatch):
    setcfg("measurement.save_path", "/nonexistent")
    setcfg("measurement.name.expanded", "meas")
    errors = []
    monkeypatch.setattr(mw.QMessageBox, "critical", lambda *a, **k: errors.append(a))
    window._record_ccxx_measurement_paths()
    assert errors


def test_offer_open_measurement_folder_yes_launches(window, monkeypatch):
    monkeypatch.setattr(mw.config, "is_ccxx_testchart", lambda *a, **k: False)
    setcfg("profile.save_path", "/some/path")
    setcfg("profile.name.expanded", "name")
    monkeypatch.setattr(
        mw.QMessageBox,
        "question",
        lambda *a, **k: mw.QMessageBox.Yes,
    )
    launched = []
    monkeypatch.setattr(mw, "launch_file", lambda path: launched.append(path))
    window._offer_open_measurement_folder()
    assert launched == [os.path.join("/some/path", "name")]


def test_offer_open_measurement_folder_no_skips_launch(window, monkeypatch):
    monkeypatch.setattr(mw.config, "is_ccxx_testchart", lambda *a, **k: False)
    setcfg("profile.save_path", "/some/path")
    setcfg("profile.name.expanded", "name")
    monkeypatch.setattr(
        mw.QMessageBox,
        "question",
        lambda *a, **k: mw.QMessageBox.No,
    )
    launched = []
    monkeypatch.setattr(mw, "launch_file", lambda path: launched.append(path))
    window._offer_open_measurement_folder()
    assert launched == []


def test_restore_measurement_mode_and_testchart_noop_without_backups(
    window, monkeypatch
):
    setcfg("measurement_mode.backup", None)
    setcfg("observer.backup", None)
    setcfg("testchart.file.backup", None)
    calls = []
    monkeypatch.setattr(window, "update_comports", lambda: calls.append("comports"))
    monkeypatch.setattr(
        window, "update_measurement_mode_ctrl", lambda: calls.append("mode")
    )
    monkeypatch.setattr(window, "_set_testchart", lambda path=None: calls.append(path))
    window._restore_measurement_mode_and_testchart()
    assert calls == []


def test_restore_measurement_mode_and_testchart_restores_mode_and_comport(
    window, monkeypatch
):
    setcfg("measurement_mode.backup", "p")
    setcfg("comport.number.backup", 3)
    calls = []
    monkeypatch.setattr(window, "update_comports", lambda: calls.append("comports"))
    window._restore_measurement_mode_and_testchart()
    assert getcfg("measurement_mode") == "p"
    assert getcfg("measurement_mode.backup", False) in (False, None, "")
    assert getcfg("comport.number") == 3
    assert calls == ["comports"]


def test_restore_measurement_mode_and_testchart_restores_mode_without_comport(
    window, monkeypatch
):
    setcfg("measurement_mode.backup", "l")
    setcfg("comport.number.backup", None)
    calls = []
    monkeypatch.setattr(
        window, "update_measurement_mode_ctrl", lambda: calls.append("mode")
    )
    window._restore_measurement_mode_and_testchart()
    assert getcfg("measurement_mode") == "l"
    assert calls == ["mode"]


def test_restore_measurement_mode_and_testchart_restores_observer(window):
    setcfg("observer.backup", "1964_10")
    window._restore_measurement_mode_and_testchart()
    assert getcfg("observer") == "1964_10"
    assert getcfg("observer.backup", False) in (False, None, "")


def test_restore_measurement_mode_and_testchart_restores_testchart(
    window, monkeypatch
):
    setcfg("testchart.file.backup", "/path/to.ti1")
    calls = []
    monkeypatch.setattr(window, "_set_testchart", lambda path=None: calls.append(path))
    window._restore_measurement_mode_and_testchart()
    assert calls == ["/path/to.ti1"]
    assert getcfg("testchart.file.backup", False) in (False, None, "")


# --- Help menu / post-launch update-check + instrument-setup/donation nag ----


def test_help_menu_actions_present(window):
    assert window.update_check_action is not None
    assert window.update_check_onstartup_action is not None
    assert window.update_check_onstartup_action.isCheckable()
    assert window.update_check_onstartup_action.isChecked() == bool(
        getcfg("update_check")
    )


def test_update_check_onstartup_action_persists_toggle(window):
    window.update_check_onstartup_action.setChecked(False)
    assert getcfg("update_check") == 0
    window.update_check_onstartup_action.setChecked(True)
    assert getcfg("update_check") == 1


def test_check_for_updates_action_handler_runs_non_silent_check(window, monkeypatch):
    calls = []
    monkeypatch.setattr(
        window, "_run_update_check", lambda silent: calls.append(silent)
    )
    window._check_for_updates_action_handler()
    assert calls == [False]


def test_run_update_check_wires_controller_and_clears_on_finish(window, monkeypatch):
    from DisplayCAL.ui import update_check_window as ucw

    def fake_run(self, silent=False):
        self.finished.emit(False)

    monkeypatch.setattr(ucw.UpdateCheckController, "run", fake_run)
    monkeypatch.setattr(
        window, "_run_instrument_setup_and_donation_check", lambda: None
    )
    window._run_update_check(silent=True)
    assert window._update_check_controller is None


def test_run_post_launch_checks_runs_update_check_when_enabled(window, monkeypatch):
    setcfg("update_check", 1)
    calls = []
    monkeypatch.setattr(
        window, "_run_update_check", lambda silent: calls.append(silent)
    )
    window.run_post_launch_checks()
    assert calls == [True]


def test_run_post_launch_checks_skips_to_instrument_setup_when_disabled(
    window, monkeypatch
):
    setcfg("update_check", 0)
    calls = []
    monkeypatch.setattr(
        window,
        "_run_instrument_setup_and_donation_check",
        lambda: calls.append(True),
    )
    window.run_post_launch_checks()
    assert calls == [True]


def test_on_update_check_finished_chains_when_silent_and_not_found(
    window, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        window,
        "_run_instrument_setup_and_donation_check",
        lambda: calls.append(True),
    )
    window._on_update_check_finished(found=False, silent=True)
    assert calls == [True]


def test_on_update_check_finished_does_not_chain_when_update_found(
    window, monkeypatch
):
    monkeypatch.setattr(
        window,
        "_run_instrument_setup_and_donation_check",
        lambda: pytest.fail("should not chain"),
    )
    window._on_update_check_finished(found=True, silent=True)


def test_on_update_check_finished_does_not_chain_when_not_silent(window, monkeypatch):
    monkeypatch.setattr(
        window,
        "_run_instrument_setup_and_donation_check",
        lambda: pytest.fail("should not chain"),
    )
    window._on_update_check_finished(found=False, silent=False)


def test_instrument_setup_spyder2_needed_shows_notice_then_donation_check(
    window, monkeypatch
):
    from DisplayCAL import instrument_setup as isetup

    monkeypatch.setattr(
        isetup,
        "resolve_instrument_setup_needs",
        lambda *a, **k: isetup.InstrumentSetupNeeds(
            needs_spyder2_enable=True, needs_correction_import=False
        ),
    )
    infos = []
    monkeypatch.setattr(mw.QMessageBox, "information", lambda *a, **k: infos.append(a))
    donation_calls = []
    monkeypatch.setattr(
        window, "_show_donation_message_if_needed", lambda: donation_calls.append(True)
    )
    window._run_instrument_setup_and_donation_check()
    assert infos
    assert donation_calls == [True]


def test_instrument_setup_import_needed_runs_import_controller(window, monkeypatch):
    from DisplayCAL import instrument_setup as isetup
    from DisplayCAL.ui import colorimeter_correction_io as ccio

    monkeypatch.setattr(
        isetup,
        "resolve_instrument_setup_needs",
        lambda *a, **k: isetup.InstrumentSetupNeeds(
            needs_spyder2_enable=False, needs_correction_import=True
        ),
    )

    def fake_run(self):
        self.finished.emit()

    monkeypatch.setattr(ccio.ImportController, "run", fake_run)
    refresh_calls = []
    monkeypatch.setattr(
        window,
        "update_colorimeter_correction_matrix_ctrl_items",
        lambda *a, **k: refresh_calls.append((a, k)),
    )
    donation_calls = []
    monkeypatch.setattr(
        window, "_show_donation_message_if_needed", lambda: donation_calls.append(True)
    )
    window._run_instrument_setup_and_donation_check()
    assert refresh_calls
    assert donation_calls == [True]
    assert window._instrument_setup_import_controller is None


def test_instrument_setup_nothing_needed_goes_straight_to_donation_check(
    window, monkeypatch
):
    from DisplayCAL import instrument_setup as isetup

    monkeypatch.setattr(
        isetup,
        "resolve_instrument_setup_needs",
        lambda *a, **k: isetup.InstrumentSetupNeeds(
            needs_spyder2_enable=False, needs_correction_import=False
        ),
    )
    donation_calls = []
    monkeypatch.setattr(
        window, "_show_donation_message_if_needed", lambda: donation_calls.append(True)
    )
    window._run_instrument_setup_and_donation_check()
    assert donation_calls == [True]


def test_show_donation_message_if_needed_shows_dialog_when_flagged(
    window, monkeypatch
):
    from DisplayCAL import instrument_setup as isetup

    monkeypatch.setattr(isetup, "should_show_donation_message", lambda: True)
    shown = []
    monkeypatch.setattr(mw._DonationDialog, "exec_", lambda self: shown.append(True))
    window._show_donation_message_if_needed()
    assert shown == [True]


def test_show_donation_message_if_needed_skips_dialog_when_not_flagged(
    window, monkeypatch
):
    from DisplayCAL import instrument_setup as isetup

    monkeypatch.setattr(isetup, "should_show_donation_message", lambda: False)
    monkeypatch.setattr(
        mw._DonationDialog, "exec_", lambda self: pytest.fail("should not show")
    )
    window._show_donation_message_if_needed()


class TestDonationDialog:
    def test_accept_launches_donate_url_and_clears_flag(self, window, monkeypatch):
        setcfg("show_donation_message", 1)
        launched = []
        monkeypatch.setattr(mw, "launch_file", lambda url: launched.append(url))
        dialog = mw._DonationDialog(window)
        dialog.accept()
        assert launched and launched[0].endswith("/#donate")
        assert getcfg("show_donation_message") == 0

    def test_reject_without_checkbox_keeps_flag_set(self, window):
        setcfg("show_donation_message", 1)
        dialog = mw._DonationDialog(window)
        dialog.reject()
        assert getcfg("show_donation_message") == 1

    def test_reject_with_do_not_show_again_clears_flag(self, window):
        setcfg("show_donation_message", 1)
        dialog = mw._DonationDialog(window)
        dialog._do_not_show_again_cb.setChecked(True)
        dialog.reject()
        assert getcfg("show_donation_message") == 0
