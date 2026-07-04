"""Tests for the Qt main-window shell ``DisplayCAL.ui.main_window`` (Stage 3).

These exercise the toolkit-neutral marshalling helpers directly (no display) and
drive the window itself headless via the shared offscreen ``QApplication``
fixture. Display/port enumeration is stubbed so the tests need no Argyll install.
See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 3).
"""

import os

import pytest

from DisplayCAL import config
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
    assert window.calibrate_btn.isEnabled() is True
    assert window.calibrate_and_profile_btn.isEnabled() is True
    assert window.profile_btn.isEnabled() is True


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


def _run_pending_synchronously(window):
    """Fire the window's deferred pending-run immediately (no event loop)."""
    window._defer = lambda callback: callback()


def _force_mode(window, monkeypatch, mode):
    """Pin the flow's presentation decision so dispatch is platform-independent."""

    def fake_plan(pending_function, *args, **kwargs):
        window.flow.set_pending_function(pending_function, *args)
        return mf.MeasurementPlan(mode=mode, display_name="DELL U2413")

    monkeypatch.setattr(window.flow, "plan_measurement", fake_plan)


@pytest.mark.parametrize(
    "button_attr,action",
    [
        ("calibrate_btn", mw.MeasurementAction.CALIBRATE),
        ("calibrate_and_profile_btn", mw.MeasurementAction.CALIBRATE_AND_PROFILE),
        ("profile_btn", mw.MeasurementAction.PROFILE),
    ],
)
def test_action_button_dry_run_emits_request(
    window, _no_writecfg, monkeypatch, button_attr, action
):
    # Dry run -> the flow calls the pending driver straight away.
    monkeypatch.setattr(config, "get_display_name", lambda *a, **k: "DELL U2413")
    monkeypatch.setattr(config, "is_virtual_display", lambda *a, **k: False)
    setcfg("dry_run", 1)
    _run_pending_synchronously(window)
    seen = []
    window.measurement_requested.connect(seen.append)

    getattr(window, button_attr).click()

    assert seen == [action]


def test_show_frame_mode_presents_measureframe(window, _no_writecfg, monkeypatch):
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


def test_measureframe_result_measure_runs_pending(window, _no_writecfg, monkeypatch):
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
