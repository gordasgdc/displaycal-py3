"""Tests for the toolkit-neutral measurement report helpers.

Covers the pure pieces extracted from ``MainFrame.measurement_report_handler`` /
``measurement_report_consumer`` in ``DisplayCAL/measurement_report.py``. No
display or QApplication is needed.
"""

import os
import shutil
from types import SimpleNamespace

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
        self.errors = []

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

    def test_self_check_report_overrides_display_instrument_and_type(
        self, monkeypatch, ti1_path, ti3_path, icc_path, tmp_path
    ):
        worker = self._worker(monkeypatch)
        profile = ICCProfile(icc_path)
        ti3_ref = CGATS(ti3_path, True)[0]
        chart = CGATS(ti1_path, True)
        measured_ti3_path = str(tmp_path / "measured.ti3")
        with open(ti3_path, "rb") as source, open(measured_ti3_path, "wb") as dest:
            dest.write(source.read())

        captured = {}

        def fake_create(save_path, placeholders2data, pack_js):
            captured.update(placeholders2data)
            open(save_path, "w").close()

        monkeypatch.setattr(mr.report, "create", fake_create)
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
            self_check_report=True,
        )

        assert captured["${REPORT_TYPE}"] == "Self Check"
        assert captured["${INSTRUMENT}"] == "N/A"
        assert captured["${CORRECTION_MATRIX}"] == "N/A"
        # The fixture profile's device-model description is empty.
        assert captured["${DISPLAY}"] == "N/A"

    def test_removed_items_resync_reference_ti3(
        self, monkeypatch, ti1_path, ti3_path, icc_path, tmp_path
    ):
        worker = self._worker(monkeypatch)
        profile = ICCProfile(icc_path)
        ti3_ref = CGATS(ti3_path, True)[0]
        chart = CGATS(ti1_path, True)
        measured_ti3_path = str(tmp_path / "measured.ti3")
        with open(ti3_path, "rb") as source, open(measured_ti3_path, "wb") as dest:
            dest.write(source.read())
        before = len(ti3_ref.queryv1("DATA"))

        class _Removed:
            def __init__(self, key):
                self.key = key

        monkeypatch.setattr(
            mr.report, "create", lambda save_path, *a, **kw: open(save_path, "w").close()
        )
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
            removed_items=[_Removed(0)],
        )

        assert len(ti3_ref.queryv1("DATA")) == before - 1


class TestProfileB2AIsLowres:
    def test_hires_profile_not_flagged(self, icc_path):
        profile = ICCProfile(icc_path)
        # Real fixture: creator is "DCAL" (not Argyll), so never flagged
        # regardless of resolution.
        assert mr.profile_b2a_is_lowres(profile) is False

    def test_argyll_creator_but_hires_not_flagged(self, icc_path):
        profile = ICCProfile(icc_path)
        profile.creator = b"argl"
        # Real fixture's B2A0 has 33 grid steps.
        assert mr.profile_b2a_is_lowres(profile) is False

    def test_argyll_creator_and_lowres_is_flagged(self, icc_path):
        profile = ICCProfile(icc_path)
        profile.creator = b"argl"
        # ``clut_grid_steps`` is a read-only property; override the private
        # backing field it falls back to instead.
        profile.tags.B2A0._g = 10
        assert mr.profile_b2a_is_lowres(profile) is True

    def test_no_b2a0_tag_not_flagged(self, icc_path):
        profile = ICCProfile(icc_path)
        profile.creator = b"argl"
        del profile.tags["B2A0"]
        assert mr.profile_b2a_is_lowres(profile) is False


class TestResolveWorkingTi3Path:
    def test_missing_tempdir_returns_none(self):
        worker = FakeWorker(tempdir=None)
        assert mr.resolve_working_ti3_path(worker) is None

    def test_missing_file_returns_none(self, tmp_path):
        setcfg("profile.name.expanded", "Missing Profile")
        worker = FakeWorker(tempdir=str(tmp_path))
        assert mr.resolve_working_ti3_path(worker) is None

    def test_returns_path_when_file_exists(self, tmp_path):
        setcfg("profile.name.expanded", "My Profile")
        (tmp_path / "My Profile.ti3").write_bytes(b"stub")
        worker = FakeWorker(tempdir=str(tmp_path))
        assert mr.resolve_working_ti3_path(worker) == str(tmp_path / "My Profile.ti3")


class TestPerformSelfCheckLookup:
    def test_writes_ti3_without_devlink(self, ti1_path, icc_path, tmp_path):
        oprof = ICCProfile(icc_path)
        ti1 = CGATS(ti1_path, True)
        ti3_stub = CGATS(ti1_path, True)[0]
        worker = FakeWorker(
            chart_lookup_result=(None, ti3_stub, None), tempdir=str(tmp_path)
        )
        save_path = str(tmp_path / "My Report.html")

        ti3_path, returned_oprof = mr.perform_self_check_lookup(
            worker, ti1, oprof, None, save_path
        )

        assert returned_oprof is oprof
        assert ti3_path == str(tmp_path / "My Report.ti3")
        assert os.path.isfile(ti3_path)
        assert os.path.isfile(str(tmp_path / "My Report.icc"))
        with open(ti3_path, "rb") as ti3_file:
            assert b"LUMINANCE_XYZ_CDM2" in ti3_file.read()

    def test_tempdir_failure_raises(self, ti1_path, icc_path, tmp_path):
        oprof = ICCProfile(icc_path)
        ti1 = CGATS(ti1_path, True)
        worker = FakeWorker(tempdir=RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            mr.perform_self_check_lookup(
                worker, ti1, oprof, None, str(tmp_path / "r.html")
            )

    def test_apply_cal_reloads_profile_with_baked_in_calibration(
        self, monkeypatch, ti1_path, icc_path, tmp_path
    ):
        oprof = ICCProfile(icc_path)
        ti1 = CGATS(ti1_path, True)
        ti3_stub = CGATS(ti1_path, True)[0]

        class ApplyCalWorker(FakeWorker):
            def exec_cmd(self, executable, args, **kwargs):
                # args: ["-v", oprof_cal_path, profile_path, profile_with_cal_path]
                shutil.copyfile(args[2], args[3])
                return True

        worker = ApplyCalWorker(
            chart_lookup_result=(None, ti3_stub, None), tempdir=str(tmp_path)
        )
        devlink = SimpleNamespace(tags={"meta": {"collink.args": {"value": "-a"}}})
        monkeypatch.setattr(mr, "get_argyll_util", lambda name: "applycal")

        save_path = str(tmp_path / "Report.html")
        ti3_path, returned_oprof = mr.perform_self_check_lookup(
            worker, ti1, oprof, devlink, save_path
        )

        assert os.path.isfile(ti3_path)
        assert returned_oprof is not oprof
        assert returned_oprof.getDescription() == oprof.getDescription()

    def test_apply_cal_missing_applycal_util_raises(
        self, monkeypatch, ti1_path, icc_path, tmp_path
    ):
        oprof = ICCProfile(icc_path)
        ti1 = CGATS(ti1_path, True)
        devlink = SimpleNamespace(tags={"meta": {"collink.args": {"value": "-a"}}})
        worker = FakeWorker(tempdir=str(tmp_path))
        monkeypatch.setattr(mr, "get_argyll_util", lambda name: None)
        with pytest.raises(Exception):
            mr.perform_self_check_lookup(
                worker, ti1, oprof, devlink, str(tmp_path / "r.html")
            )


def _stub_suspicious_pair(item_a, item_b):
    """Build a ``check_ti3``-shaped suspicious tuple for ``item_a``/``item_b``.

    ``item_a`` plays the "previous" patch (no delta of its own), ``item_b``
    the flagged patch, matching ``check_ti3``'s own tuple shape.
    """
    delta = {"E": 5.0, "E_ok": False, "L_ok": True}
    sRGB_delta = {"E": 1.0}  # noqa: N806
    prev_delta_to_sRGB = {  # noqa: N806
        "E": 0.1,
        "L": 0,
        "C": 0,
        "H": 0,
        "ok": True,
        "E_ok": True,
        "L_ok": True,
        "C_ok": True,
        "H_ok": True,
    }
    delta_to_sRGB = {  # noqa: N806
        "E": 12.0,
        "L": 1,
        "C": 1,
        "H": 1,
        "ok": False,
        "E_ok": False,
        "L_ok": True,
        "C_ok": True,
        "H_ok": True,
    }
    return (item_a, item_b, delta, sRGB_delta, prev_delta_to_sRGB, delta_to_sRGB)


class TestResolveSanityCheck:
    def test_disabled_by_default_returns_none(self, ti3_path):
        setcfg("ti3.check_sanity.auto", 0)
        ti3 = CGATS(ti3_path, True)[0]
        assert mr.resolve_sanity_check(ti3) is None

    def test_enabled_but_nothing_suspicious_returns_none(self, monkeypatch, ti3_path):
        setcfg("ti3.check_sanity.auto", 1)
        ti3 = CGATS(ti3_path, True)[0]
        monkeypatch.setattr(mr, "check_ti3", lambda *a, **kw: [])
        assert mr.resolve_sanity_check(ti3) is None

    def test_force_still_requires_suspicious_data(self, monkeypatch, ti3_path):
        setcfg("ti3.check_sanity.auto", 0)
        ti3 = CGATS(ti3_path, True)[0]
        monkeypatch.setattr(mr, "check_ti3", lambda *a, **kw: [])
        assert mr.resolve_sanity_check(ti3, force=True) is None

    def test_builds_rows_for_suspicious_pair(self, monkeypatch, ti3_path):
        setcfg("ti3.check_sanity.auto", 1)
        ti3 = CGATS(ti3_path, True)[0]
        data = ti3.queryv1("DATA")
        item0, item1 = data[0], data[1]
        monkeypatch.setattr(
            mr, "check_ti3", lambda *a, **kw: [_stub_suspicious_pair(item0, item1)]
        )

        ctx = mr.resolve_sanity_check(ti3)

        assert ctx is not None
        assert [row.sample_id for row in ctx.rows] == [
            item0.SAMPLE_ID,
            item1.SAMPLE_ID,
        ]
        assert ctx.rows[0].has_delta is False
        assert ctx.rows[1].has_delta is True
        assert ctx.items == [item0, item1]

    def test_deduplicates_repeated_items_across_pairs(self, monkeypatch, ti3_path):
        setcfg("ti3.check_sanity.auto", 1)
        ti3 = CGATS(ti3_path, True)[0]
        data = ti3.queryv1("DATA")
        item0, item1, item2 = data[0], data[1], data[2]
        suspicious = [
            _stub_suspicious_pair(item0, item1),
            _stub_suspicious_pair(item1, item2),
        ]
        monkeypatch.setattr(mr, "check_ti3", lambda *a, **kw: suspicious)

        ctx = mr.resolve_sanity_check(ti3)

        # item1 appears as both the "item" of the first pair and the "prev"
        # of the second; it must only be represented once.
        assert ctx.items == [item0, item1, item2]


class TestRecomputeSanityRow:
    def _ctx(self, monkeypatch, ti3_path):
        setcfg("ti3.check_sanity.auto", 1)
        ti3 = CGATS(ti3_path, True)[0]
        data = ti3.queryv1("DATA")
        item0, item1 = data[0], data[1]
        monkeypatch.setattr(
            mr, "check_ti3", lambda *a, **kw: [_stub_suspicious_pair(item0, item1)]
        )
        return mr.resolve_sanity_check(ti3)

    def test_row_without_previous_has_no_delta(self, monkeypatch, ti3_path):
        ctx = self._ctx(monkeypatch, ti3_path)
        delta, sRGB_delta, delta_to_sRGB = mr.recompute_sanity_row(
            ctx, 0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
        )
        assert delta is None
        assert sRGB_delta is None
        assert "E" in delta_to_sRGB

    def test_row_with_previous_recomputes_delta(self, monkeypatch, ti3_path):
        ctx = self._ctx(monkeypatch, ti3_path)
        delta, sRGB_delta, delta_to_sRGB = mr.recompute_sanity_row(
            ctx, 1, (50.0, 50.0, 50.0), (20.0, 20.0, 20.0)
        )
        assert delta is not None and "E" in delta
        assert sRGB_delta is not None and "E" in sRGB_delta
        assert "E" in delta_to_sRGB


class TestApplySanityCheckResult:
    def test_removes_unchecked_rows_and_applies_mods(self, monkeypatch, ti3_path):
        setcfg("ti3.check_sanity.auto", 1)
        ti3 = CGATS(ti3_path, True)[0]
        data = ti3.queryv1("DATA")
        item0, item1, item2 = data[0], data[1], data[2]
        suspicious = [
            _stub_suspicious_pair(item0, item1),
            _stub_suspicious_pair(item1, item2),
        ]
        monkeypatch.setattr(mr, "check_ti3", lambda *a, **kw: suspicious)
        ctx = mr.resolve_sanity_check(ti3)
        before_count = len(ti3.queryv1("DATA"))

        removed = mr.apply_sanity_check_result(ctx, [1], {0: {"RGB_R": 42.0}})

        assert len(removed) == 1
        assert removed[0] is item1
        assert len(ti3.queryv1("DATA")) == before_count - 1
        assert item0["RGB_R"] == 42.0
        assert ti3.modified is True

    def test_no_removals_or_mods_leaves_ti3_untouched(self, monkeypatch, ti3_path):
        setcfg("ti3.check_sanity.auto", 1)
        ti3 = CGATS(ti3_path, True)[0]
        data = ti3.queryv1("DATA")
        item0, item1 = data[0], data[1]
        monkeypatch.setattr(
            mr, "check_ti3", lambda *a, **kw: [_stub_suspicious_pair(item0, item1)]
        )
        ctx = mr.resolve_sanity_check(ti3)
        before_count = len(ti3.queryv1("DATA"))

        removed = mr.apply_sanity_check_result(ctx, [], {})

        assert removed == []
        assert len(ti3.queryv1("DATA")) == before_count


class TestResyncReportTi3Removals:
    class _Removed:
        def __init__(self, key):
            self.key = key

    def test_removes_matching_offset_patches(self, ti1_path):
        ti3_ref = CGATS(ti1_path, True)[0]
        sim_ti3 = CGATS(ti1_path, True)[0]
        before = len(ti3_ref.queryv1("DATA"))

        mr.resync_report_ti3_removals(
            ti3_ref, sim_ti3, [self._Removed(0), self._Removed(1)], offset=0
        )

        assert len(ti3_ref.queryv1("DATA")) == before - 2
        assert len(sim_ti3.queryv1("DATA")) == before - 2

    def test_sim_ti3_none_is_skipped(self, ti1_path):
        ti3_ref = CGATS(ti1_path, True)[0]
        before = len(ti3_ref.queryv1("DATA"))

        mr.resync_report_ti3_removals(ti3_ref, None, [self._Removed(0)], offset=0)

        assert len(ti3_ref.queryv1("DATA")) == before - 1
