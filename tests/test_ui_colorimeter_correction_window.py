"""Headless tests for the Qt colorimeter-correction create window.

Exercise ``DisplayCAL.ui.colorimeter_correction_window.CreateCorrectionWindow``
under the shared offscreen ``QApplication``: instrument/type wiring, the
create-button enablement, the deferred measure signals, the CCXX-patch
trimming, and (when a real Argyll install is available) the full
``ccxxmake`` pipeline end to end. See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``
(Stage 5+, colorimeter-correction create window).
"""

import os

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL import config  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL.argyll import get_argyll_util  # noqa: E402
from DisplayCAL.cgats import CGATSError  # noqa: E402
from DisplayCAL.ui import colorimeter_correction_window as ccxx_window  # noqa: E402
from DisplayCAL.worker import Worker  # noqa: E402

REFERENCE_TI3 = """CTI3

DESCRIPTOR "Argyll Calibration Target chart information 3"
ORIGINATOR "Argyll dispread"
CREATED "Thu Apr 19 13:24:37 2012"
KEYWORD "DEVICE_CLASS"
DEVICE_CLASS "DISPLAY"
KEYWORD "TARGET_INSTRUMENT"
TARGET_INSTRUMENT "Spectrometer"
KEYWORD "DISPLAY_TYPE_REFRESH"
DISPLAY_TYPE_REFRESH "NO"
KEYWORD "INSTRUMENT_TYPE_SPECTRAL"
INSTRUMENT_TYPE_SPECTRAL "YES"

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 4
BEGIN_DATA
1 100.00 100.00 100.00 95.046 100.00 108.91
2 100.00 0.0000 0.0000 41.238 21.260 1.9306
3 0.0000 100.00 0.0000 35.757 71.520 11.921
4 0.0000 0.0000 100.00 18.050 7.2205 95.055
END_DATA
"""

COLORIMETER_TI3 = """CTI3

DESCRIPTOR "Argyll Calibration Target chart information 3"
ORIGINATOR "Argyll dispread"
CREATED "Thu Apr 19 13:24:37 2012"
KEYWORD "DEVICE_CLASS"
DEVICE_CLASS "DISPLAY"
KEYWORD "TARGET_INSTRUMENT"
TARGET_INSTRUMENT "i1 DisplayPro, ColorMunki Display"
KEYWORD "DISPLAY_TYPE_REFRESH"
DISPLAY_TYPE_REFRESH "NO"
KEYWORD "INSTRUMENT_TYPE_SPECTRAL"
INSTRUMENT_TYPE_SPECTRAL "NO"

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT

NUMBER_OF_SETS 4
BEGIN_DATA
1 100.00 100.00 100.00 94.046 99.00 107.91
2 100.00 0.0000 0.0000 40.238 20.260 1.7306
3 0.0000 100.00 0.0000 36.757 70.520 11.421
4 0.0000 0.0000 100.00 17.050 7.4205 94.055
END_DATA
"""

#: A colorimeter TI3 missing the "green" patch, for the trimming-error test.
COLORIMETER_TI3_MISSING_GREEN = COLORIMETER_TI3.replace(
    "3 0.0000 100.00 0.0000 36.757 70.520 11.421\n", ""
).replace("NUMBER_OF_SETS 4", "NUMBER_OF_SETS 3")


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
def stub_worker(monkeypatch):
    """Stub instrument/display enumeration so no hardware is needed."""

    def fake(self, *args, **kwargs):
        self.displays = ["DELL U2413 @ 0, 0, 1920x1080 [PRIMARY]"]
        self.instruments = ["i1 DisplayPro, ColorMunki Display"]

    monkeypatch.setattr(Worker, "enumerate_displays_and_ports", fake)
    # CreateCorrectionWindow._populate_instruments() -> _instrument_handler()
    # calls this for the stubbed instrument above on every window construction
    # (i.e. every test in this file). The real implementation shells out to
    # `spotread -?` and `ccxxmake -??` to enumerate modes/technologies, which
    # has caused CI to hang indefinitely with orphaned Argyll subprocesses
    # (seemingly stuck probing for real instrument hardware that doesn't
    # exist in CI), rather than just failing fast.
    monkeypatch.setattr(
        Worker, "get_instrument_measurement_modes", lambda self, *a, **k: {}
    )
    # CreateCorrectionWindow._populate_details() -> _populate_technology()
    # calls this once a TI3 pair is selected (i.e. any test using the
    # test_ti3/ref_ti3 fixtures). The real implementation shells out to
    # `ccxxmake -??` with no timeout, which hangs CI the same way as the
    # other real-Argyll calls stubbed in this fixture.
    monkeypatch.setattr(
        Worker,
        "get_technology_strings",
        lambda self, *a, **k: {"l": "LCD", "c": "CRT", "u": "Unknown"},
    )
    # CreateCorrectionWindow.__init__() also unconditionally calls this on
    # every window construction. The real implementation shells out to
    # `ccxxmake -?` with a 30s timeout, which reliably eats the full 30s on
    # CI (same "no real hardware" cause as above) instead of returning fast.
    # Set a realistic modern version via the string parser (no subprocess)
    # rather than a bare no-op: TestBuildCorrectionEndToEnd's two tests run
    # the real ccxxmake pipeline below, and modern ccxxmake (matching the
    # 3.5.0 CI pins in .github/workflows/pytest.yml) has dropped the old
    # "-T <tech>" flag in favor of "-t <dtech-id>", which is only selected
    # when self.worker.argyll_version reads as >= [1, 7].
    def fake_set_argyll_version(self, name, silent=False, cfg=False):
        self.set_argyll_version_from_string("3.5.0", cfg=cfg)

    monkeypatch.setattr(Worker, "set_argyll_version", fake_set_argyll_version)
    # _build_correction() separately calls the module-level get_argyll_version()
    # (not via self.worker), which shells out the same way. Stub it to the
    # same version so both stay on the modern "-t" branch together.
    monkeypatch.setattr(ccxx_window, "get_argyll_version", lambda *a, **k: [3, 5, 0])


@pytest.fixture
def window(qapp, stub_worker):
    """Create a fresh CreateCorrectionWindow with config isolated per test."""
    from DisplayCAL.ui.colorimeter_correction_window import CreateCorrectionWindow

    saved = dict(config.CFG["Default"])
    win = CreateCorrectionWindow()
    try:
        yield win
    finally:
        win.close()
        config.CFG["Default"] = saved


@pytest.fixture
def ti3_paths(tmp_path):
    """Write matched reference/colorimeter TI3 fixtures, return their paths."""
    reference = tmp_path / "reference.ti3"
    reference.write_text(REFERENCE_TI3)
    colorimeter = tmp_path / "colorimeter.ti3"
    colorimeter.write_text(COLORIMETER_TI3)
    return str(reference), str(colorimeter)


class TestConstruction:
    def test_expected_controls_exist(self, window):
        for attr in (
            "correction_type_matrix",
            "correction_type_spectral",
            "four_color_matrix",
            "reference_instrument",
            "reference_measurement_mode",
            "reference_observer",
            "reference_ti3",
            "measure_reference_btn",
            "colorimeter_instrument",
            "colorimeter_measurement_mode",
            "colorimeter_observer",
            "colorimeter_ti3",
            "measure_colorimeter_btn",
            "description_ctrl",
            "display_ctrl",
            "manufacturer_ctrl",
            "technology_ctrl",
            "create_btn",
        ):
            assert hasattr(window, attr), attr

    def test_colorimeter_instrument_populated_from_worker(self, window):
        items = [
            window.colorimeter_instrument.itemText(i)
            for i in range(window.colorimeter_instrument.count())
        ]
        assert items == ["i1 DisplayPro, ColorMunki Display"]
        # This instrument is not spectral, so the reference list stays empty.
        assert window.reference_instrument.count() == 0

    def test_create_button_disabled_by_default(self, window):
        assert window.create_btn.isEnabled() is False


class TestCorrectionType:
    def test_spectral_hides_colorimeter_box(self, window):
        window.show()
        assert window.colorimeter_box.isVisible() is True
        window.correction_type_spectral.setChecked(True)
        assert window.colorimeter_box.isVisible() is False

    def test_switching_to_spectral_disables_four_color_matrix(self, window):
        window.four_color_matrix.setChecked(True)
        window.correction_type_spectral.setChecked(True)
        assert window.four_color_matrix.isEnabled() is False
        assert window.four_color_matrix.isChecked() is False


class TestCreateButtonEnablement:
    def test_enabled_once_both_ti3_paths_exist(self, window, ti3_paths):
        reference_path, colorimeter_path = ti3_paths
        window.correction_type_matrix.setChecked(True)
        window.reference_ti3.set_path(reference_path)
        window._ti3_changed("reference")
        assert window.create_btn.isEnabled() is False  # colorimeter still missing
        window.colorimeter_ti3.set_path(colorimeter_path)
        window._ti3_changed("colorimeter")
        assert window.create_btn.isEnabled() is True

    def test_spectral_only_needs_reference(self, window, ti3_paths):
        reference_path, _ = ti3_paths
        window.correction_type_spectral.setChecked(True)
        window.reference_ti3.set_path(reference_path)
        window._ti3_changed("reference")
        assert window.create_btn.isEnabled() is True

    def test_nonexistent_path_does_not_enable(self, window):
        window.correction_type_spectral.setChecked(True)
        window.reference_ti3.set_path("/no/such/file.ti3")
        window._ti3_changed("reference")
        assert window.create_btn.isEnabled() is False


class TestMeasureSignals:
    def test_measure_reference_emits_request(self, window):
        received = []
        window.measure_reference_requested.connect(lambda: received.append(True))
        # No spectral (reference) instrument in the stub, so the button starts
        # disabled; enable it to test the wiring, not the enablement rule.
        window.measure_reference_btn.setEnabled(True)
        window.measure_reference_btn.click()
        assert received == [True]

    def test_measure_colorimeter_emits_request(self, window):
        received = []
        window.measure_colorimeter_requested.connect(lambda: received.append(True))
        window.measure_colorimeter_btn.click()
        assert received == [True]


class TestTi3Loading:
    def test_load_ti3_files_trims_to_ccxx_patches(self, window, ti3_paths):
        reference_path, colorimeter_path = ti3_paths
        window.correction_type_matrix.setChecked(True)
        window.reference_ti3.set_path(reference_path)
        window.colorimeter_ti3.set_path(colorimeter_path)
        reference, colorimeter = window._load_ti3_files()
        assert reference.queryv1("DATA")
        assert colorimeter.queryv1("DATA")
        # DISPLAY_TYPE_BASE_ID is added by check_add_display_type_base_id.
        assert colorimeter.queryv1("DISPLAY_TYPE_BASE_ID") is not None

    def test_missing_patch_raises(self, window, tmp_path, ti3_paths):
        reference_path, _ = ti3_paths
        colorimeter_path = tmp_path / "colorimeter_missing.ti3"
        colorimeter_path.write_text(COLORIMETER_TI3_MISSING_GREEN)
        window.correction_type_matrix.setChecked(True)
        window.reference_ti3.set_path(reference_path)
        window.colorimeter_ti3.set_path(str(colorimeter_path))
        with pytest.raises(CGATSError):
            window._load_ti3_files()


class TestPreviewDialog:
    def test_builds_table_from_rows(self, qapp):
        from DisplayCAL.ui.colorimeter_correction_window import _PreviewDialog

        rows = [
            {
                "sample_id": "1",
                "ref_xyY": (0.3127, 0.3290, 100.0),
                "corrected_xyY": (0.3128, 0.3291, 99.5),
                "ref_rgb": [255, 255, 255],
                "corrected_rgb": [254, 254, 254],
                "delta_e00": 0.15,
            }
        ]
        dlg = _PreviewDialog(rows)
        assert dlg.findChild(object, None) is not None  # smoke: children built
        dlg.close()


@pytest.mark.skipif(
    not get_argyll_util("ccxxmake"), reason="requires an Argyll CMS install"
)
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason=(
        "real ccxxmake hangs indefinitely on GitHub Actions runners (no "
        "physical instrument/display), leaving orphaned Argyll subprocesses "
        "that eat the full 300s pytest-timeout per test; root cause not "
        "reproducible locally (single and 20-way concurrent runs of the "
        "exact CI-pinned Argyll build complete in ~2s under a matching "
        "headless Xvfb setup). Run locally with a real Argyll install."
    ),
)
class TestBuildCorrectionEndToEnd:
    """Exercise the real ``ccxxmake`` pipeline against synthetic TI3 fixtures."""

    def test_matrix_correction(self, window, ti3_paths):
        reference_path, colorimeter_path = ti3_paths
        window.correction_type_matrix.setChecked(True)
        window.reference_ti3.set_path(reference_path)
        window.colorimeter_ti3.set_path(colorimeter_path)
        window._reference_cgats, window._colorimeter_cgats = window._load_ti3_files()
        window._populate_details()
        # The stubbed worker has no real display enumeration, so
        # get_display_name() is empty; set one explicitly so create_ccxx()
        # sees an -I argument instead of falling back to its own -T (which
        # would collide with our -t and abort ccxxmake).
        window.display_ctrl.setText("Test Display")

        result = window._build_correction()

        assert not isinstance(result, Exception), result
        assert result["is_ccmx"] is True
        assert len(result["preview_rows"]) == 4
        cgats = result["cgats"].decode("utf-8")
        assert cgats.startswith("CCMX")
        assert 'TECHNOLOGY "LCD"' in cgats
        assert "FIT_METHOD" in cgats
        assert "FIT_AVG_DE00" in cgats

    def test_four_color_matrix_correction(self, window, ti3_paths):
        reference_path, colorimeter_path = ti3_paths
        window.four_color_matrix.setChecked(True)
        window.correction_type_matrix.setChecked(True)
        window.reference_ti3.set_path(reference_path)
        window.colorimeter_ti3.set_path(colorimeter_path)
        window._reference_cgats, window._colorimeter_cgats = window._load_ti3_files()
        window._populate_details()
        window.display_ctrl.setText("Test Display")

        result = window._build_correction()

        assert not isinstance(result, Exception), result
        assert 'FIT_METHOD "xy"' in result["cgats"].decode("utf-8")
