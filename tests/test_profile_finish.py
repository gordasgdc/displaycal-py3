"""Tests for the toolkit-neutral profile-finish (``colprof`` stage) helpers.

Covers the pure pieces extracted from ``MainFrame.start_profile_worker`` /
``profile_finish`` in ``DisplayCAL/profile_finish.py``. No display or
QApplication is needed.
"""

import os

import pytest

from DisplayCAL import profile_finish as pf
from DisplayCAL.config import PROFILE_EXT, getcfg, setcfg
from DisplayCAL.icc_profile import GAMUT_VOLUME_SRGB, ICCProfileTag


@pytest.fixture
def srgb_profile_path(data_path):
    return str(data_path / "icc" / "vcgt_cm_test_cyanish_reddish.icc")


class TestResolveProfilePath:
    def test_explicit_path_returned_unchanged(self):
        assert pf.resolve_profile_path("/tmp/explicit.icc") == "/tmp/explicit.icc"

    def test_default_derived_from_config(self):
        setcfg("profile.save_path", "/save")
        setcfg("profile.name.expanded", "MyProfile")
        expected = os.path.join("/save", "MyProfile", "MyProfile" + PROFILE_EXT)
        assert pf.resolve_profile_path() == expected


class TestValidateBuiltProfile:
    def test_valid_profile_with_vcgt(self, srgb_profile_path):
        built = pf.validate_built_profile(srgb_profile_path)
        assert built.profile.profileClass == b"mntr"
        assert built.has_cal is True

    def test_missing_file_raises_invalid(self, tmp_path):
        with pytest.raises(pf.ProfileFinishInvalidError):
            pf.validate_built_profile(str(tmp_path / "nope.icc"))

    def test_corrupt_file_raises_invalid(self, tmp_path):
        bogus = tmp_path / "bogus.icc"
        bogus.write_bytes(b"not an icc profile")
        with pytest.raises(pf.ProfileFinishInvalidError):
            pf.validate_built_profile(str(bogus))

    def test_non_display_profile_raises_not_display_error(
        self, srgb_profile_path, monkeypatch
    ):
        from DisplayCAL.icc_profile import ICCProfile as RealICCProfile

        def fake_ctor(path):
            profile = RealICCProfile(path)
            profile.colorSpace = b"CMYK"
            return profile

        monkeypatch.setattr(pf, "ICCProfile", fake_ctor)
        with pytest.raises(pf.ProfileFinishNotDisplayError) as excinfo:
            pf.validate_built_profile(srgb_profile_path)
        assert excinfo.value.profile.colorSpace == b"CMYK"


class TestFormatCompletionExtra:
    def test_no_meta_tag_returns_empty(self, srgb_profile_path):
        built = pf.validate_built_profile(srgb_profile_path)
        assert pf.format_completion_extra(built.profile) == ""

    def test_self_check_and_gamut_figures_included(self, srgb_profile_path):
        built = pf.validate_built_profile(srgb_profile_path)
        profile = built.profile

        class _FakeMeta(ICCProfileTag):
            def __init__(self, values):
                super().__init__(b"", "meta")
                self._values = values

            def getvalue(self, key):
                return self._values.get(key)

        profile.tags["meta"] = _FakeMeta(
            {
                "ACCURACY_dE76_avg": "0.5",
                "ACCURACY_dE76_max": "1.25",
                "ACCURACY_dE76_rms": "0.7",
                "GAMUT_coverage(srgb)": "0.987",
                "GAMUT_volume": str(GAMUT_VOLUME_SRGB),
            }
        )
        text = pf.format_completion_extra(profile)
        assert "0.50" in text
        assert "1.25" in text
        assert "98.7%" in text
        assert "sRGB" in text


class TestSyncCalibrationFileConfig:
    def test_unchanged_path_returns_false_and_does_not_write(
        self, srgb_profile_path, monkeypatch
    ):
        setcfg("calibration.file", srgb_profile_path)
        calls = []
        monkeypatch.setattr(
            "DisplayCAL.profile_finish.setcfg",
            lambda *a, **k: calls.append(a),
        )
        assert pf.sync_calibration_file_config(srgb_profile_path) is False
        assert calls == []

    def test_new_path_updates_dependent_keys(self, data_path, srgb_profile_path):
        old_path = str(data_path / "icc" / "vcgt_cm_test_blueish_yellowish.icc")
        setcfg("calibration.file", old_path)
        assert pf.sync_calibration_file_config(srgb_profile_path) is True
        assert getcfg("calibration.file") == srgb_profile_path
        assert getcfg("3dlut.output.profile") == srgb_profile_path
        assert getcfg("measurement_report.output_profile") == srgb_profile_path
