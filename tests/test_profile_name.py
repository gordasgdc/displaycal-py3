"""Tests for the toolkit-neutral profile-name/testchart helpers.

Covers the pure pieces extracted from ``MainFrame.create_profile_name`` /
``get_testchart_names`` / ``testchart_patches_amount_ctrl_handler`` /
``wx_report_frame.ReportFrame.update_estimated_measurement_time`` in
``DisplayCAL/profile_name.py``. No display or QApplication is needed.
"""

import os

import pytest

from DisplayCAL import config, profile_name as pn
from DisplayCAL import localization as lang
from DisplayCAL.cgats import CGATSError


def _ctx(**overrides):
    base = dict(
        computer_name="my-computer",
        display_win32_short=None,
        display_win32=None,
        display_short="Display 1",
        display="Display 1 @ 0, 0",
        edid={},
        is_virtual_display=False,
        display_number=1,
        instrument="i1 DisplayPro",
        measurement_mode=None,
        trc="",
        trc_type="g",
        do_cal=False,
        whitepoint=None,
        whitepoint_locus="t",
        luminance=None,
        black_luminance=None,
        ambient=None,
        black_output_offset="0",
        black_point_correction="0",
        black_point_correction_auto=False,
        black_point_rate=None,
        calibration_quality="m",
        profile_quality="m",
        profile_type="X",
        testchart_patches_amount="34",
    )
    base.update(overrides)
    return pn.ProfileNameContext(**base)


class TestExpandProfileName:
    def test_display_short_placeholder(self):
        assert pn.expand_profile_name("%dns", _ctx()) == "Display 1"

    def test_computer_name_placeholder(self):
        assert pn.expand_profile_name("%nn", _ctx()) == "my-computer"

    def test_output_number_placeholder(self):
        assert pn.expand_profile_name("%out", _ctx(display_number=2)) == "#2"

    def test_output_virtual_display_is_dropped(self):
        # A lone "\0" placeholder collapses to an empty name.
        assert pn.expand_profile_name("%out", _ctx(is_virtual_display=True)) == ""

    def test_whitepoint_kelvin(self):
        name = pn.expand_profile_name(
            "%wp", _ctx(whitepoint="6500", do_cal=True, whitepoint_locus="t")
        )
        assert name == "D6500"

    def test_whitepoint_xy(self):
        name = pn.expand_profile_name(
            "%wp", _ctx(whitepoint="0.31,0.32", do_cal=True)
        )
        assert name == "0.31x 0.32y"

    def test_whitepoint_dropped_without_cal(self):
        assert pn.expand_profile_name("%wp", _ctx(whitepoint="6500")) == ""

    def test_profile_type_placeholder(self):
        assert pn.expand_profile_name("%pt", _ctx(profile_type="x")) == "XYZLUT"

    def test_testchart_patches_amount_placeholder(self):
        assert (
            pn.expand_profile_name("%tpa", _ctx(testchart_patches_amount="115"))
            == "115"
        )

    def test_quality_placeholders_collapse_when_equal(self):
        # Both quality codes map to the same abbreviation and are adjacent,
        # so wx collapses "%cq %pq" into a single quality marker.
        name = pn.expand_profile_name(
            "%cq %pq",
            _ctx(do_cal=True, trc="s", calibration_quality="h", profile_quality="h"),
        )
        assert name == "S"

    def test_invalid_filename_characters_are_replaced(self):
        assert pn.expand_profile_name("a/b:c", _ctx()) == "a_b_c"

    def test_null_placeholder_padding_is_cleaned_up(self):
        # %in has no instrument configured -> dropped, and the surrounding
        # underscore separators collapse rather than leaving doubled ones.
        name = pn.expand_profile_name("foo_%wp_bar", _ctx(whitepoint=None))
        assert name == "foo_bar"

    def test_truncates_for_long_save_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            pn,
            "getcfg",
            lambda key: str(tmp_path) if key == "profile.save_path" else None,
        )
        long_name = "x" * 300
        result = pn.expand_profile_name(long_name, _ctx())
        assert len(result) <= len(long_name)


class TestTruncateProfileNameForPath:
    def test_short_name_is_unchanged(self):
        assert pn.truncate_profile_name_for_path("My Profile", "/tmp/profiles") == (
            "My Profile"
        )

    def test_long_name_is_shortened(self):
        long_name = "x" * 300
        result = pn.truncate_profile_name_for_path(long_name, "/tmp/profiles")
        assert len(result) < len(long_name)


class TestProfileNameValidation:
    @pytest.mark.parametrize(
        "value",
        ["My Profile", "profile_2026", "a"],
    )
    def test_valid_names(self, value):
        assert pn.is_valid_profile_name(value)

    @pytest.mark.parametrize(
        "value",
        ["-leading-dash", "has/slash", 'has"quote', "trailing.", "trailing "],
    )
    def test_invalid_names(self, value):
        assert not pn.is_valid_profile_name(value)

    def test_sanitize_strips_invalid_characters(self):
        assert pn.sanitize_profile_name("a/b:c*d") == "abcd"

    def test_sanitize_strips_leading_dash(self):
        assert pn.sanitize_profile_name("-foo") == "foo"

    def test_sanitize_empty_falls_back_to_default(self):
        assert pn.sanitize_profile_name("") == str(pn.DEFAULTS.get("profile.name", ""))

    def test_sanitize_truncates_to_80_chars(self):
        assert len(pn.sanitize_profile_name("x" * 200)) <= 80


class TestProfileNamePlaceholders:
    def test_returns_nonempty_legend_with_all_tokens(self):
        legend = pn.profile_name_placeholders()
        for token in ("%nn", "%dn", "%wp", "%cg", "%pt", "%tpa"):
            assert token in legend


class TestGetTestchartNames:
    def test_auto_is_always_first(self):
        names, paths = pn.get_testchart_names("auto")
        assert paths[0] == "auto"
        assert len(names) == len(paths)

    def test_bundled_defaults_are_included(self):
        _names, paths = pn.get_testchart_names("auto")
        assert any(path.endswith("ccxx.ti1") for path in paths)


class TestTestchartPatchesAmountForAuto:
    @pytest.mark.parametrize(
        "auto,expected", [(1, 34), (2, 79), (3, 115), (4, 175)]
    )
    def test_fixed_lookup_table(self, auto, expected):
        assert pn.testchart_patches_amount_for_auto(auto) == expected

    def test_above_four_uses_formula_and_grows(self):
        low = pn.testchart_patches_amount_for_auto(5)
        high = pn.testchart_patches_amount_for_auto(18)
        assert low > 175
        assert high > low


class TestSuggestedProfileTypeForAuto:
    def test_high_auto_suggests_xyz_lut(self):
        assert pn.suggested_profile_type_for_auto(10, "S", False) == "X"
        assert pn.suggested_profile_type_for_auto(10, "S", True) == "x"

    def test_high_auto_no_change_when_already_lut(self):
        assert pn.suggested_profile_type_for_auto(10, "l", False) is None

    def test_mid_auto_suggests_lut_matrix(self):
        assert pn.suggested_profile_type_for_auto(2, "S", False) == "X"

    def test_low_auto_suggests_curve_matrix(self, monkeypatch):
        monkeypatch.setattr(
            pn, "getcfg", lambda key: "" if key == "trc" else None
        )
        assert pn.suggested_profile_type_for_auto(1, "X", False) == "s"
        monkeypatch.setattr(
            pn, "getcfg", lambda key: "2.2" if key == "trc" else None
        )
        assert pn.suggested_profile_type_for_auto(1, "X", False) == "S"

    def test_low_auto_no_change_when_already_curve_matrix(self):
        assert pn.suggested_profile_type_for_auto(1, "s", False) is None


class TestEstimateMeasurementTime:
    class _FakeWorker:
        def __init__(self, features):
            self._features = features

        def get_instrument_features(self):
            return self._features

    def test_no_integration_time_returns_unknown(self):
        estimate = pn.estimate_measurement_time(self._FakeWorker({}), 100)
        assert estimate.hours is None
        assert estimate.minutes is None
        # Compare against live ``lang.getstr`` output rather than a hardcoded
        # substring, since another test in the same process may already have
        # called ``lang.init()`` and populated real translations (or not).
        assert estimate.label() == lang.getstr(
            "estimated_measurement_time", ("--", "--")
        )

    def test_more_patches_take_longer(self):
        worker = self._FakeWorker({"integration_time": (0.1, 0.1)})
        short = pn.estimate_measurement_time(worker, 10)
        long = pn.estimate_measurement_time(worker, 10000)
        short_seconds = (short.hours or 0) * 3600 + (short.minutes or 0) * 60
        long_seconds = (long.hours or 0) * 3600 + (long.minutes or 0) * 60
        assert long_seconds > short_seconds

    def test_is_long_reflects_hours_threshold(self):
        worker = self._FakeWorker({"integration_time": (0.1, 0.1)})
        brief = pn.estimate_measurement_time(worker, 10)
        assert not brief.is_long()


class TestLoadTestchartFromFile:
    def test_loads_bundled_ti1(self):
        path = os.path.join(
            os.path.dirname(config.__file__), "ti1", "ccxx.ti1"
        )
        ti1 = pn.load_testchart_from_file(path)
        assert ti1.queryv1("NUMBER_OF_SETS")

    def test_missing_fields_raise_cgats_error(self, tmp_path):
        bogus = tmp_path / "bogus.ti1"
        bogus.write_text("CTI1\nBEGIN_DATA_FORMAT\nEND_DATA_FORMAT\nBEGIN_DATA\nEND_DATA\n")
        with pytest.raises(CGATSError):
            pn.load_testchart_from_file(str(bogus))


class TestIccProfileHasEmbeddedTi3:
    def test_profile_without_embedded_ti3_returns_false(self, data_path):
        from DisplayCAL.icc_profile import ICCProfile

        path = data_path / "icc" / "vcgt_cm_test_cyanish_reddish.icc"
        profile = ICCProfile(str(path))
        assert pn.icc_profile_has_embedded_ti3(profile) is False
