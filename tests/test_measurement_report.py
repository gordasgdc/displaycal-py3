"""Tests for the toolkit-neutral measurement report helpers.

Covers the pure pieces extracted from ``MainFrame.measurement_report_handler`` /
``measurement_report_consumer`` in ``DisplayCAL/measurement_report.py``. No
display or QApplication is needed.
"""

import os

import pytest

from DisplayCAL import measurement_report as mr
from DisplayCAL.cgats import CGATS
from DisplayCAL.config import setcfg
from DisplayCAL.icc_profile import ICCProfile

#: Real dispread/colprof output fixture set (matching .ti1/.ti3/.icc/.cal),
#: reused across the pipeline tests so ``finalize_measurement_report`` runs
#: against real CGATS/ICCProfile structures instead of hand-rolled stand-ins.
_FIXTURE_STEM = "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX"


@pytest.fixture
def icc_path(data_path):
    return str(data_path / "icc" / f"{_FIXTURE_STEM}.icc")


@pytest.fixture
def ti1_path(data_path):
    return str(data_path / "icc" / f"{_FIXTURE_STEM}.ti1")


@pytest.fixture
def ti3_path(data_path):
    return str(data_path / "icc" / f"{_FIXTURE_STEM}.ti3")


class FakeWorker:
    """Minimal worker exposing what the measurement-report pipeline touches."""

    def __init__(self, chart_lookup_result=None, xicclu_result=None, tempdir=None):
        self._chart_lookup_result = chart_lookup_result
        self._xicclu_result = xicclu_result
        self.tempdir = tempdir
        self.options_dispread = []
        self.wrapup_calls = []

    def ensure_patch_sequence(self, ti1, write=True):
        return ti1

    def chart_lookup(self, *args, **kwargs):
        return self._chart_lookup_result

    def xicclu(self, *args, **kwargs):
        return self._xicclu_result

    def create_tempdir(self):
        return self.tempdir

    def add_measurement_features(self, args, *a, **kw):
        return True

    def wrapup(self, *args, **kwargs):
        self.wrapup_calls.append(args[0] if args else None)
        return True

    def instrument_can_use_ccxx(self):
        return False


class TestDefaultReportFilename:
    def test_basic(self):
        name = mr.default_report_filename(
            "Measurement", "3.9.16", "DELL U2410", "2026-07-04 12-30"
        )
        assert name == "Measurement Report 3.9.16 - DELL U2410 - 2026-07-04 12-30.html"

    def test_self_check_type(self):
        name = mr.default_report_filename(
            "Self Check", "3.9.16", "DELL U2410", "2026-07-04 12-30"
        )
        assert name.startswith("Self Check Report 3.9.16 - ")

    def test_unsafe_characters_sanitized(self):
        name = mr.default_report_filename(
            "Measurement", "3.9.16", 'DELL:U2410/2*?"<>|', "2026-07-04 12-30"
        )
        # The whole run of unsafe chars collapses to a single underscore.
        assert name == "Measurement Report 3.9.16 - DELL_U2410_2_ - 2026-07-04 12-30.html"

    def test_timestamp_defaults_to_now(self):
        name = mr.default_report_filename("Measurement", "3.9.16", "DELL U2410")
        assert name.startswith("Measurement Report 3.9.16 - DELL U2410 - ")
        assert name.endswith(".html")


class TestResolveQuantizationBits:
    def test_separate_z_argument(self):
        assert mr.resolve_quantization_bits(["-v", "-Z", "10", "-d1"]) == 10

    def test_inline_z_argument(self):
        assert mr.resolve_quantization_bits(["-v", "-Z8", "-d1"]) == 8

    def test_video_encoding_implies_eight_bits(self):
        assert mr.resolve_quantization_bits(["-v", "-E", "-d1"]) == 8

    def test_z_takes_precedence_over_e(self):
        assert mr.resolve_quantization_bits(["-Z", "12", "-E"]) == 12

    def test_no_quantization(self):
        assert mr.resolve_quantization_bits(["-v", "-d1"]) is None

    def test_separate_z_missing_value_returns_none(self):
        assert mr.resolve_quantization_bits(["-v", "-Z"]) is None

    def test_separate_z_non_integer_value_returns_none(self):
        assert mr.resolve_quantization_bits(["-Z", "high"]) is None


class TestQuantizeGray:
    def test_eight_bit_snaps_to_grid(self):
        # 50.0 in 0-100 -> round(0.5 * 255) = 128 -> 128/255*100 = 50.1961
        result = mr.quantize_gray([[50.0, 50.0, 50.0]], 8)
        assert result == [[50.1961, 50.1961, 50.1961]]

    def test_extremes_are_exact(self):
        result = mr.quantize_gray([[0.0, 0.0, 0.0], [100.0, 100.0, 100.0]], 8)
        assert result == [[0.0, 0.0, 0.0], [100.0, 100.0, 100.0]]

    def test_empty_gray(self):
        assert mr.quantize_gray([], 8) == []

    def test_does_not_mutate_input(self):
        gray = [[50.0, 50.0, 50.0]]
        mr.quantize_gray(gray, 8)
        assert gray == [[50.0, 50.0, 50.0]]


class TestReportTrcLabel:
    def test_default_target_is_bt1886(self):
        assert mr.report_trc_label(2.4, "B", 0) == "BT.1886"

    def test_non_default_gamma_unlabelled(self):
        assert mr.report_trc_label(2.2, "B", 0) == ""

    def test_non_default_type_unlabelled(self):
        assert mr.report_trc_label(2.4, "b", 0) == ""

    def test_output_offset_unlabelled(self):
        assert mr.report_trc_label(2.4, "B", 0.5) == ""


def _configure_no_simulation():
    setcfg("measurement_report.use_simulation_profile", 0)
    setcfg("measurement_report.use_simulation_profile_as_output", 0)
    setcfg("measurement_report.use_devlink_profile", 0)
    setcfg("measurement_report.whitepoint.simulate", 0)
    setcfg("measurement_report.whitepoint.simulate.relative", 0)
    setcfg("measurement_report.chart.fields", "RGB")


class TestResolveReportContext:
    def test_chart_load_failure_raises(self):
        _configure_no_simulation()
        setcfg("measurement_report.chart", "/nonexistent/path.ti1")
        with pytest.raises(mr.ReportSetupError):
            mr.resolve_report_context(FakeWorker(), "3.9.16", "Test Display")

    def test_no_display_profile_raises(self, ti1_path, monkeypatch):
        _configure_no_simulation()
        setcfg("measurement_report.chart", ti1_path)
        monkeypatch.setattr(mr, "get_current_profile", lambda include=False: None)
        with pytest.raises(mr.ReportSetupError):
            mr.resolve_report_context(FakeWorker(), "3.9.16", "Test Display")

    def test_chart_lookup_failure_raises(self, ti1_path, icc_path, monkeypatch):
        _configure_no_simulation()
        setcfg("measurement_report.chart", ti1_path)
        profile = ICCProfile(icc_path)
        monkeypatch.setattr(mr, "get_current_profile", lambda include=False: profile)
        worker = FakeWorker(chart_lookup_result=(None, None, None))
        with pytest.raises(mr.ReportSetupError):
            mr.resolve_report_context(worker, "3.9.16", "Test Display")

    def test_successful_resolution_without_simulation(
        self, ti1_path, icc_path, monkeypatch
    ):
        _configure_no_simulation()
        setcfg("measurement_report.chart", ti1_path)
        profile = ICCProfile(icc_path)
        monkeypatch.setattr(mr, "get_current_profile", lambda include=False: profile)
        ti1 = CGATS(ti1_path, True)
        ti3_ref = CGATS(ti1_path, True)
        worker = FakeWorker(chart_lookup_result=(ti1, ti3_ref, None))

        context = mr.resolve_report_context(worker, "3.9.16", "Test Display")

        assert context.profile is profile
        assert context.oprof is profile
        assert context.sim_profile is None
        assert context.devlink is None
        assert context.use_sim is False
        assert context.apply_trc is False
        assert context.colormanaged is False
        assert context.intent == "r"
        assert context.report_type == "Measurement"
        assert context.default_file.startswith(
            "Measurement Report 3.9.16 - Test Display - "
        )

    def test_devlink_lookup_failure_raises(self, ti1_path, icc_path, monkeypatch):
        _configure_no_simulation()
        setcfg("measurement_report.use_simulation_profile", 1)
        setcfg("measurement_report.use_simulation_profile_as_output", 1)
        setcfg("measurement_report.use_devlink_profile", 1)
        setcfg("measurement_report.simulation_profile", icc_path)
        setcfg("measurement_report.devlink_profile", icc_path)
        profile = ICCProfile(icc_path)
        monkeypatch.setattr(mr, "get_current_profile", lambda include=False: profile)
        ti1 = CGATS(ti1_path, True)
        ti3_ref = CGATS(ti1_path, True)

        class DevlinkWorker(FakeWorker):
            def chart_lookup(self, *args, **kwargs):
                # First two calls (sim lookup, reference lookup) succeed; the
                # third (devlink lookup) is the one under test.
                if kwargs.get("white_patches") == 1:
                    return (None, None, None)
                return (ti1, ti3_ref, None)

        with pytest.raises(mr.ReportSetupError):
            mr.resolve_report_context(DevlinkWorker(), "3.9.16", "Test Display")


class TestStageMeasurementFiles:
    def test_writes_ti1_and_falls_back_to_linear_cal(
        self, ti1_path, icc_path, tmp_path
    ):
        profile = ICCProfile(icc_path)
        # A profile with no embedded TI3 / vcgt calibration to extract falls
        # back to the bundled linear.cal.
        profile.tags.pop("vcgt", None)
        profile.tags.pop("CIED", None)
        profile.tags.pop("targ", None)
        ti1 = CGATS(ti1_path, True)
        worker = FakeWorker(tempdir=str(tmp_path))

        save_path = str(tmp_path / "My Report.html")
        got_ti1_path, cal_path = mr.stage_measurement_files(
            worker, save_path, ti1, profile, profile, False, None
        )

        assert got_ti1_path == str(tmp_path / "My Report.ti1")
        assert os.path.isfile(got_ti1_path)
        assert os.path.basename(cal_path) == "linear.cal"
        assert os.path.isfile(cal_path)

    def test_extracts_calibration_when_present(self, ti1_path, icc_path, tmp_path):
        profile = ICCProfile(icc_path)
        assert "vcgt" in profile.tags, "fixture profile should carry a vcgt tag"
        ti1 = CGATS(ti1_path, True)
        worker = FakeWorker(tempdir=str(tmp_path))

        save_path = str(tmp_path / "My Report.html")
        _ti1_path, cal_path = mr.stage_measurement_files(
            worker, save_path, ti1, profile, profile, False, None
        )

        assert cal_path == str(tmp_path / "My Report.cal")
        assert os.path.isfile(cal_path)


class TestFinalizeMeasurementReport:
    def _worker(self, monkeypatch):
        monkeypatch.setattr(
            mr.config, "get_display_name", lambda *a, **kw: "Test Display"
        )
        return FakeWorker()

    def test_cgats_load_failure_wraps_up_and_reraises(self, monkeypatch, tmp_path):
        worker = self._worker(monkeypatch)
        missing_ti3 = str(tmp_path / "nope.ti3")
        with pytest.raises(Exception):
            mr.finalize_measurement_report(
                worker=worker,
                ti3_path=missing_ti3,
                profile=None,
                sim_profile=None,
                intent="r",
                sim_intent=None,
                devlink=None,
                ti3_ref=None,
                sim_ti3=None,
                save_path=str(tmp_path / "report.html"),
                chart=None,
                gray=None,
                apply_trc=False,
                use_sim=False,
                use_sim_as_output=False,
                oprof=None,
                instrument_name="Instrument",
                measurement_mode_name="Mode",
                display_name="Test Display",
                observers={},
                version_string="3.9.16",
            )
        assert worker.wrapup_calls, "wrapup should run even on a load failure"

    def test_happy_path_writes_html_report(
        self, monkeypatch, ti1_path, ti3_path, icc_path, tmp_path
    ):
        worker = self._worker(monkeypatch)
        profile = ICCProfile(icc_path)
        # Real dispread ti3 files carry a CAL section (1) alongside the data
        # section (0); ``chart_lookup`` would already have handed back just
        # the data section, so index it here too.
        ti3_ref = CGATS(ti3_path, True)[0]
        chart = CGATS(ti1_path, True)
        # Simulate "measured == predicted" by staging a copy of the same
        # fixture ti3 as the worker's measurement output.
        measured_ti3_path = str(tmp_path / "measured.ti3")
        with open(ti3_path, "rb") as source, open(measured_ti3_path, "wb") as dest:
            dest.write(source.read())

        save_path = str(tmp_path / "report.html")
        mr.finalize_measurement_report(
            worker=worker,
            ti3_path=measured_ti3_path,
            profile=profile,
            sim_profile=None,
            intent="r",
            sim_intent=None,
            devlink=None,
            ti3_ref=ti3_ref,
            sim_ti3=None,
            save_path=save_path,
            chart=chart,
            gray=None,
            apply_trc=False,
            use_sim=False,
            use_sim_as_output=False,
            oprof=profile,
            instrument_name="i1 Pro 2",
            measurement_mode_name="High res",
            display_name="Test Display",
            observers={},
            version_string="3.9.16",
        )

        assert os.path.isfile(save_path)
        html = open(save_path, encoding="utf-8").read()
        assert "Test Display" in html
        assert worker.wrapup_calls == [False]
