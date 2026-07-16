"""Tests for DisplayCAL.create_profile.

Toolkit-neutral pipeline backing the Qt File menu's "Create profile from
measurement data..." action (``DisplayCAL.ui.main_window``), ported from wx's
``MainFrame.create_profile_handler``. See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``.
"""

import os
import shutil

import pytest

from DisplayCAL import create_profile as cp
from DisplayCAL.cgats import CGATS
from DisplayCAL.config import DEFAULTS, initcfg
from DisplayCAL.icc_profile import ICCProfile

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "icc")
TI3_PATH = os.path.join(
    DATA_DIR, "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.ti3"
)
ICC_PATH = os.path.join(
    DATA_DIR, "UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.icc"
)
NO_EMBEDDED_TI3_ICC_PATH = os.path.join(DATA_DIR, "vcgt_cm_test_cyanish_reddish.icc")


@pytest.fixture(autouse=True)
def _init_config():
    initcfg()


class _FakeWorker:
    """Stand-in for a ``Worker``, controlling just what these functions read."""

    def __init__(self, tempdir=None, errors=None):
        self.tempdir = tempdir
        self.errors = errors or []


class TestLoadMeasurementLines:
    def test_ti3_file(self):
        item = cp.load_measurement_lines(TI3_PATH)
        assert item.path == TI3_PATH
        assert item.profile is None
        assert item.tags == {}
        assert b"CAL" in item.ti3_lines

    def test_profile_with_embedded_ti3(self):
        item = cp.load_measurement_lines(ICC_PATH)
        assert item.profile is not None
        assert b"CAL" in item.ti3_lines
        assert "mmod" in item.tags or "meta" in item.tags

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(cp.CreateProfileError):
            cp.load_measurement_lines(str(tmp_path / "nope.ti3"))

    def test_invalid_profile_raises(self, tmp_path):
        bogus = tmp_path / "bogus.icc"
        bogus.write_bytes(b"not an icc profile")
        with pytest.raises(cp.CreateProfileError):
            cp.load_measurement_lines(str(bogus))

    def test_profile_without_embedded_ti3_raises(self):
        with pytest.raises(cp.CreateProfileError):
            cp.load_measurement_lines(NO_EMBEDDED_TI3_ICC_PATH)

    def test_ti3_open_failure_raises(self, tmp_path):
        directory = tmp_path / "adir.ti3"
        directory.mkdir()
        with pytest.raises(cp.CreateProfileError):
            cp.load_measurement_lines(str(directory))


class TestHasCalibrationCurves:
    def test_present(self):
        assert cp.has_calibration_curves([b"foo", b"CAL", b"bar"]) is True

    def test_absent(self):
        assert cp.has_calibration_curves([b"foo", b"bar"]) is False


class TestResolveSourceNaming:
    def test_single_path(self):
        assert cp.resolve_source_naming(["/a/b/c.ti3"]) == ("/a/b/c", ".ti3")

    def test_multiple_paths_falls_back_to_default(self, monkeypatch):
        monkeypatch.setitem(DEFAULTS, "last_ti3_path", "/x/y/default.ti3")
        assert cp.resolve_source_naming(["/a.ti3", "/b.icc"]) == (
            "/x/y/default",
            ".ti3",
        )


class TestIsTempPath:
    def test_no_tempdir(self):
        assert cp.is_temp_path(_FakeWorker(tempdir=None), "/any/path.ti3") is False

    def test_inside_tempdir(self, tmp_path):
        worker = _FakeWorker(tempdir=str(tmp_path))
        assert cp.is_temp_path(worker, str(tmp_path / "x.ti3")) is True

    def test_outside_tempdir(self, tmp_path):
        worker = _FakeWorker(tempdir=str(tmp_path))
        assert cp.is_temp_path(worker, "/somewhere/else.ti3") is False

    def test_win32_is_case_insensitive(self, monkeypatch):
        monkeypatch.setattr(cp.sys, "platform", "win32")
        worker = _FakeWorker(tempdir="C:\\Temp")
        assert cp.is_temp_path(worker, "c:\\temp\\file.ti3") is True


class TestMergeMeasurementFiles:
    def test_success_writes_merged_file_and_cleans_up_copies(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(cp, "get_argyll_util", lambda name: "average")
        collected = [
            cp.CollectedMeasurement(
                path="a.ti3", ti3_lines=[b"line1", b"line2"], profile=None, tags={}
            ),
            cp.CollectedMeasurement(
                path="b.ti3", ti3_lines=[b"line3"], profile=None, tags={}
            ),
        ]
        calls = {}

        def fake_exec_cmd(cmd, args, **kwargs):
            calls["cmd"] = cmd
            calls["args"] = args
            with open(args[-1], "wb") as f:
                f.write(b"merged")
            return True

        worker = _FakeWorker()
        worker.exec_cmd = fake_exec_cmd
        ti3_tmp_path = str(tmp_path / "merged.ti3")

        cp.merge_measurement_files(worker, collected, str(tmp_path), ti3_tmp_path)

        assert calls["cmd"] == "average"
        assert calls["args"][0] == "-v"
        assert calls["args"][-1] == ti3_tmp_path
        assert os.path.exists(ti3_tmp_path)
        assert not os.path.exists(str(tmp_path / "a.ti3"))
        assert not os.path.exists(str(tmp_path / "b.ti3"))

    def test_failure_raises_and_still_cleans_up(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cp, "get_argyll_util", lambda name: "average")
        collected = [
            cp.CollectedMeasurement(
                path="a.ti3", ti3_lines=[b"x"], profile=None, tags={}
            )
        ]
        worker = _FakeWorker(errors=["boom"])
        worker.exec_cmd = lambda *a, **k: None

        with pytest.raises(cp.CreateProfileError, match="boom"):
            cp.merge_measurement_files(
                worker, collected, str(tmp_path), str(tmp_path / "out.ti3")
            )
        assert not os.path.exists(str(tmp_path / "a.ti3"))

    def test_exception_result_raises_with_its_message(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cp, "get_argyll_util", lambda name: "average")
        collected = [
            cp.CollectedMeasurement(
                path="a.ti3", ti3_lines=[b"x"], profile=None, tags={}
            )
        ]
        worker = _FakeWorker()
        worker.exec_cmd = lambda *a, **k: ValueError("average boom")

        with pytest.raises(cp.CreateProfileError, match="average boom"):
            cp.merge_measurement_files(
                worker, collected, str(tmp_path), str(tmp_path / "out.ti3")
            )


class TestResolveProfileCreationInputs:
    def test_ti3_source_copies_and_extracts_options(self, tmp_path):
        ti3_tmp_path = str(tmp_path / "out.ti3")

        inputs = cp.resolve_profile_creation_inputs(
            TI3_PATH, ".ti3", ti3_tmp_path, None, False
        )

        assert os.path.exists(ti3_tmp_path)
        assert inputs.options_dispcal
        assert inputs.options_targen == ["-d3"]
        assert isinstance(inputs.ti3, CGATS)

    def test_ti3_source_already_at_tmp_path_skips_copy(self, tmp_path):
        ti3_tmp_path = str(tmp_path / "out.ti3")
        shutil.copyfile(TI3_PATH, ti3_tmp_path)

        inputs = cp.resolve_profile_creation_inputs(
            ti3_tmp_path, ".ti3", ti3_tmp_path, None, False
        )

        assert inputs.options_targen == ["-d3"]

    def test_profile_source_writes_chart_and_extracts_options(self, tmp_path):
        profile = ICCProfile(ICC_PATH)
        ti3_tmp_path = str(tmp_path / "out.ti3")

        inputs = cp.resolve_profile_creation_inputs(
            ICC_PATH, ".icc", ti3_tmp_path, profile, False
        )

        assert os.path.exists(ti3_tmp_path)
        assert inputs.options_dispcal
        assert inputs.display_manufacturer

    def test_profile_source_is_tmp_removes_source_file(self, tmp_path):
        profile_copy = tmp_path / "src.icc"
        shutil.copyfile(ICC_PATH, profile_copy)
        profile = ICCProfile(str(profile_copy))
        ti3_tmp_path = str(tmp_path / "out.ti3")

        cp.resolve_profile_creation_inputs(
            str(profile_copy), ".icc", ti3_tmp_path, profile, True
        )

        assert not os.path.exists(profile_copy)

    def test_profile_source_not_tmp_keeps_source_file(self, tmp_path):
        profile_copy = tmp_path / "src.icc"
        shutil.copyfile(ICC_PATH, profile_copy)
        profile = ICCProfile(str(profile_copy))
        ti3_tmp_path = str(tmp_path / "out.ti3")

        cp.resolve_profile_creation_inputs(
            str(profile_copy), ".icc", ti3_tmp_path, profile, False
        )

        assert os.path.exists(profile_copy)

    def test_wraps_exception_in_create_profile_error(self, tmp_path):
        with pytest.raises(cp.CreateProfileError, match="temporary .ti3"):
            cp.resolve_profile_creation_inputs(
                str(tmp_path / "missing.ti3"),
                ".ti3",
                str(tmp_path / "out.ti3"),
                None,
                False,
            )
