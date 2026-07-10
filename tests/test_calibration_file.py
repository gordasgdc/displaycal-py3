"""Tests for the toolkit-neutral calibration/profile-file header-bar helpers.

Covers the pure pieces of ``MainFrame.load_cal_handler`` extracted into
``DisplayCAL/calibration_file.py``: the EDID/instrument auto-matching, the
ICC-profile-load config defaults, and the session-archive import. No display
or QApplication is needed.
"""

import os
import zipfile
from types import SimpleNamespace

from DisplayCAL import calibration_file as cf
from DisplayCAL import localization as lang
from DisplayCAL.config import getcfg, setcfg


class FakeProfile:
    """Minimal stand-in for :class:`~DisplayCAL.icc_profile.ICCProfile`."""

    def __init__(self, model_description="", meta=None):
        self._model_description = model_description
        self.tags = {"meta": meta or {}}

    def getDeviceModelDescription(self):  # noqa: N802 (matches ICCProfile's API)
        return self._model_description


class FakeWorker:
    """Minimal worker exposing what ``match_display_and_instrument`` touches."""

    def __init__(self, display_edid=None, display_names=None, instruments=None):
        self.display_edid = display_edid or []
        self.display_names = display_names or []
        self.instruments = instruments or []


class TestMatchDisplayAndInstrument:
    def test_no_metadata_finds_nothing(self):
        setcfg("displays", ["Display 1 @ 0, 0, 1920x1080"])
        setcfg("display.number", 1)
        profile = FakeProfile()
        worker = FakeWorker(
            display_edid=[{}], display_names=["Display 1"], instruments=[]
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.display_index is None
        assert match.instrument_index is None

    def test_unique_model_description_match_selects_display(self):
        setcfg("displays", ["Display 1 @ 0, 0, 1920x1080", "Display 2 @ 0, 0, 1024x768"])
        setcfg("display.number", 1)
        profile = FakeProfile(model_description="Display 2")
        worker = FakeWorker(
            display_edid=[{}, {}],
            display_names=["Display 1", "Display 2"],
            instruments=[],
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.display_index == 1
        assert match.display_changed is True

    def test_currently_selected_display_is_not_flagged_changed(self):
        setcfg("displays", ["Display 1 @ 0, 0, 1920x1080", "Display 2 @ 0, 0, 1024x768"])
        setcfg("display.number", 1)
        profile = FakeProfile(model_description="Display 1")
        worker = FakeWorker(
            display_edid=[{}, {}],
            display_names=["Display 1", "Display 2"],
            instruments=[],
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.display_index == 0
        assert match.display_changed is False

    def test_ambiguous_model_description_match_is_not_applied(self):
        setcfg("displays", ["Display 1 @ 0, 0, 1920x1080", "Display 1 @ 0, 0, 1024x768"])
        setcfg("display.number", 1)
        profile = FakeProfile(model_description="Display 1")
        worker = FakeWorker(
            display_edid=[{}, {}],
            display_names=["Display 1", "Display 1"],
            instruments=[],
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.display_index is None

    def test_edid_md5_match_used_when_no_model_description(self):
        setcfg("displays", ["Display 1 @ 0, 0, 1920x1080", "Display 2 @ 0, 0, 1024x768"])
        setcfg("display.number", 1)
        profile = FakeProfile(meta={"EDID_md5": {"value": "abc123"}})
        worker = FakeWorker(
            display_edid=[{}, {b"hash": "abc123"}],
            display_names=["Display 1", "Display 2"],
            instruments=[],
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.display_index == 1

    def test_virtual_display_match_reenables_3dlut_tab(self):
        setcfg("displays", ["madVR"])
        setcfg("display.number", 1)
        profile = FakeProfile(model_description="madVR")
        worker = FakeWorker(
            display_edid=[{}], display_names=["madVR"], instruments=[]
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.reenable_3dlut_tab is True

    def test_instrument_match_by_measurement_device(self):
        profile = FakeProfile(
            meta={"MEASUREMENT_device": {"value": "colormunki display"}}
        )
        worker = FakeWorker(
            display_edid=[], display_names=[], instruments=["ColorMunki Display"]
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.instrument_index == 0
        assert match.instrument_match is True

    def test_no_instrument_match_leaves_index_none(self):
        profile = FakeProfile(
            meta={"MEASUREMENT_device": {"value": "some other device"}}
        )
        worker = FakeWorker(
            display_edid=[], display_names=[], instruments=["ColorMunki Display"]
        )

        match = cf.match_display_and_instrument(profile, worker)

        assert match.instrument_index is None
        assert match.instrument_match is False


class TestApplyIccProfileLoadDefaults:
    def test_non_preset_updates_3dlut_source_profiles(self):
        setcfg("3dlut.tab.enable", 1)
        setcfg("3dlut.tab.enable.backup", 1)

        cf.apply_icc_profile_load_defaults("/path/to/profile.icc", is_preset=False)

        assert getcfg("last_icc_path") == "/path/to/profile.icc"
        assert getcfg("3dlut.output.profile") == "/path/to/profile.icc"
        assert getcfg("measurement_report.output_profile") == "/path/to/profile.icc"
        assert getcfg("3dlut.tab.enable") == 0
        assert getcfg("3dlut.tab.enable.backup") == 0

    def test_preset_does_not_overwrite_3dlut_source_profiles(self):
        setcfg("3dlut.output.profile", "/existing.icc")
        setcfg("measurement_report.output_profile", "/existing.icc")

        cf.apply_icc_profile_load_defaults("/path/to/preset.icc", is_preset=True)

        assert getcfg("last_icc_path") == "/path/to/preset.icc"
        assert getcfg("3dlut.output.profile") == "/existing.icc"
        assert getcfg("measurement_report.output_profile") == "/existing.icc"


class TestParseLegacyCal:
    def test_non_display_device_class_is_invalid(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [b'DEVICE_CLASS "PRINTER"']

        result = cf.parse_legacy_cal(lines, worker)

        assert result.invalid is True

    def test_device_type_sets_measurement_mode(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [b'DEVICE_CLASS "DISPLAY"', b'DEVICE_TYPE "CRT"']

        result = cf.parse_legacy_cal(lines, worker)

        assert result.invalid is False
        assert getcfg("measurement_mode") == "c"
        assert "-yc" in worker.options_dispcal

    def test_target_gamma_named_curve_sets_trc(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [b'DEVICE_CLASS "DISPLAY"', b'TARGET_GAMMA "REC709"']

        result = cf.parse_legacy_cal(lines, worker)

        assert getcfg("trc") == "709"
        assert getcfg("trc.type") == "g"
        assert any(opt.startswith("-g709") for opt in worker.options_dispcal)
        assert lang.getstr("trc") in result.settings

    def test_target_gamma_numeric_value_sets_trc(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [b'DEVICE_CLASS "DISPLAY"', b'TARGET_GAMMA "2.200000"']

        cf.parse_legacy_cal(lines, worker)

        assert float(getcfg("trc")) == 2.2
        assert getcfg("trc.type") == "g"

    def test_target_white_xyz_sets_whitepoint_and_luminance(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [
            b'DEVICE_CLASS "DISPLAY"',
            b'TARGET_WHITE_XYZ "95.045000 100.000000 108.905000"',
        ]

        result = cf.parse_legacy_cal(lines, worker)

        # setcfg(..., None) resets to the config default (not a real None),
        # matching the rest of this module's ``setcfg(name, None)`` resets.
        assert getcfg("whitepoint.colortemp") == cf.DEFAULTS["whitepoint.colortemp"]
        assert abs(float(getcfg("whitepoint.x")) - 0.3127) < 0.001
        assert abs(float(getcfg("whitepoint.y")) - 0.3290) < 0.001
        assert float(getcfg("calibration.luminance")) == 100
        assert any(opt.startswith("-w") for opt in worker.options_dispcal)
        assert any(opt.startswith("-b") for opt in worker.options_dispcal)
        assert lang.getstr("whitepoint") in result.settings
        assert lang.getstr("calibration.luminance") in result.settings

    def test_degree_of_black_output_offset(self):
        # NOTE: the legacy CGATS keyword is a 0-100 percentage, but
        # ``calibration.black_output_offset`` is scoped to [0, 1] in the
        # current config schema (VALID_VALUES) -- a pre-existing mismatch
        # already present in the wx original this is a faithful port of
        # (only the bytes/str comparisons were fixed), so a "50" input
        # clamps to the config key's max (1), not 50. Ported faithfully
        # rather than rescaled.
        worker = SimpleNamespace(options_dispcal=[])
        lines = [
            b'DEVICE_CLASS "DISPLAY"',
            b'DEGREE_OF_BLACK_OUTPUT_OFFSET "50.000000"',
        ]

        cf.parse_legacy_cal(lines, worker)

        assert float(getcfg("calibration.black_output_offset")) == 1
        assert any(opt.startswith("-f1") for opt in worker.options_dispcal)

    def test_black_point_correction_present_disables_auto(self):
        setcfg("calibration.black_point_correction.auto", 0)
        worker = SimpleNamespace(options_dispcal=[])
        lines = [
            b'DEVICE_CLASS "DISPLAY"',
            b'BLACK_POINT_CORRECTION "0.500000"',
        ]

        cf.parse_legacy_cal(lines, worker)

        assert float(getcfg("calibration.black_point_correction")) == 0.5
        assert any(opt.startswith("-k0.5") for opt in worker.options_dispcal)
        # An explicit, non-negative value was found -- don't fall back to auto.
        assert getcfg("calibration.black_point_correction.auto") == 0

    def test_missing_black_point_correction_enables_auto(self):
        setcfg("calibration.black_point_correction.auto", 0)
        worker = SimpleNamespace(options_dispcal=[])
        lines = [b'DEVICE_CLASS "DISPLAY"']

        cf.parse_legacy_cal(lines, worker)

        assert getcfg("calibration.black_point_correction.auto") == 1

    def test_target_black_brightness(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [
            b'DEVICE_CLASS "DISPLAY"',
            b'TARGET_BLACK_BRIGHTNESS "0.500000"',
        ]

        cf.parse_legacy_cal(lines, worker)

        assert float(getcfg("calibration.black_luminance")) == 0.5
        assert any(opt.startswith("-B0.5") for opt in worker.options_dispcal)

    def test_quality(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [b'DEVICE_CLASS "DISPLAY"', b'QUALITY "High"']

        cf.parse_legacy_cal(lines, worker)

        assert getcfg("calibration.quality") == "h"
        assert "-qh" in worker.options_dispcal

    def test_unrecognized_lines_are_ignored(self):
        worker = SimpleNamespace(options_dispcal=[])
        lines = [b'DEVICE_CLASS "DISPLAY"', b"# just a comment", b"NUMBER_OF_FIELDS 3"]

        result = cf.parse_legacy_cal(lines, worker)

        assert result.invalid is False
        assert result.settings == []


class TestImportSessionArchive:
    def test_zip_extracts_and_returns_storage_path(self, tmp_path):
        cal_file = tmp_path / "test.cal"
        cal_file.write_text("dummy")
        archive_path = tmp_path / "test.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.write(cal_file, "test.cal")
        tempdir = tmp_path / "extract"
        tempdir.mkdir()
        setcfg("profile.save_path", str(tmp_path / "storage"))

        request = cf.SessionArchiveImportRequest(
            path=str(archive_path),
            basename="test",
            ext=".zip",
            tempdir=str(tempdir),
        )
        result = cf.import_session_archive(request, exec_cmd=None)

        assert not isinstance(result, Exception)
        # Uses the extracted file's own extension (.cal), not the archive's
        # (.zip) -- a latent bug in the wx original this port also fixes.
        assert result == os.path.join(str(tmp_path / "storage"), "test", "test.cal")
        assert (tempdir / "test.cal").exists()

    def test_zip_without_session_file_returns_error(self, tmp_path):
        other_file = tmp_path / "notes.txt"
        other_file.write_text("dummy")
        archive_path = tmp_path / "test.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.write(other_file, "notes.txt")
        tempdir = tmp_path / "extract"
        tempdir.mkdir()

        request = cf.SessionArchiveImportRequest(
            path=str(archive_path),
            basename="test",
            ext=".zip",
            tempdir=str(tempdir),
        )
        result = cf.import_session_archive(request, exec_cmd=None)

        assert isinstance(result, Exception)

    def test_7z_without_sevenzip_returns_error(self, tmp_path):
        request = cf.SessionArchiveImportRequest(
            path=str(tmp_path / "test.7z"),
            basename="test",
            ext=".7z",
            tempdir=str(tmp_path),
            sevenzip=None,
        )

        result = cf.import_session_archive(request, exec_cmd=None)

        assert isinstance(result, Exception)

    def test_7z_extracts_using_exec_cmd(self, tmp_path):
        tempdir = tmp_path / "extract"
        tempdir.mkdir()

        def fake_exec_cmd(*args, **kwargs):
            (tempdir / "test.icc").write_text("dummy")
            return True

        setcfg("profile.save_path", str(tmp_path / "storage"))
        request = cf.SessionArchiveImportRequest(
            path=str(tmp_path / "test.7z"),
            basename="test",
            ext=".7z",
            tempdir=str(tempdir),
            sevenzip="/usr/bin/7z",
        )

        result = cf.import_session_archive(request, exec_cmd=fake_exec_cmd)

        assert result == os.path.join(str(tmp_path / "storage"), "test", "test.icc")
