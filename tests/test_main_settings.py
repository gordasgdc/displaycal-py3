"""Tests for the toolkit-neutral ``DisplayCAL.main_settings`` module.

These cover the ``option string -> config`` marshalling extracted from
``display_cal.MainFrame`` (see ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``,
Stage 0). The functions only read/write :mod:`DisplayCAL.config`, so the tests
drive them purely through ``getcfg``/``setcfg`` without any GUI toolkit.
"""

import pytest

from DisplayCAL import config, main_settings
from DisplayCAL.config import getcfg, setcfg


@pytest.fixture(autouse=True)
def _init_config():
    """Ensure config is initialised (default values) before each test."""
    config.initcfg()
    yield


def test_set_profile_quality():
    main_settings.set_profile_quality_config_with_option("qh")
    assert getcfg("profile.quality") == "h"


def test_set_profile_quality_b2a_uses_value():
    main_settings.set_profile_quality_b2a_config_with_option("qm")
    assert getcfg("profile.quality.b2a") == "m"


def test_set_profile_quality_b2a_uses_low_value():
    main_settings.set_profile_quality_b2a_config_with_option("ql")
    assert getcfg("profile.quality.b2a") == "l"


def test_set_profile_black_point_compensation_non_preset():
    main_settings.set_profile_black_point_compenstation_config_with_option(
        "aX", is_preset=False, is_3dlut_preset=False
    )
    assert getcfg("profile.type") == "X"


def test_set_gamap_src_viewcond():
    main_settings.set_gamap_src_viewcond_config_with_option("cmt")
    assert getcfg("gamap_src_viewcond") == "mt"


def test_set_gamap_out_viewcond():
    main_settings.set_gamap_out_viewcond_config_with_option("dmt")
    assert getcfg("gamap_out_viewcond") == "mt"


def test_set_gamap_perceptual_intent():
    main_settings.set_gamap_perceptual_intent_config_with_option("Ip")
    assert getcfg("gamap_perceptual_intent") == "p"


def test_set_gamap_saturation_intent():
    main_settings.set_gamap_saturation_intent_config_with_option("Is")
    assert getcfg("gamap_saturation_intent") == "s"


def test_set_interactive_display_adjustment_disables():
    setcfg("calibration.interactive_display_adjustment", 1)
    main_settings.set_interactive_display_adjustment_config_with_option("m")
    assert getcfg("calibration.interactive_display_adjustment") == 0


def test_set_calibration_quality():
    main_settings.set_calibration_quality_config_with_option("qh")
    assert getcfg("calibration.quality") == "h"


def test_set_measurement_mode():
    setcfg("measurement_mode", "l")
    main_settings.set_measurement_mode_config_with_option("yc")
    assert getcfg("measurement_mode") == "c"


def test_set_measurement_mode_left_alone_when_auto():
    setcfg("measurement_mode", "auto")
    main_settings.set_measurement_mode_config_with_option("yc")
    assert getcfg("measurement_mode") == "auto"


def test_set_whitepoint_temperature_planckian():
    main_settings.set_whitepoint_temperature_config_with_option("t6500")
    assert getcfg("whitepoint.colortemp.locus") == "t"
    assert getcfg("whitepoint.colortemp") == 6500
    assert getcfg("whitepoint.x", False) in (None, "")
    assert getcfg("whitepoint.y", False) in (None, "")


def test_set_whitepoint_temperature_locus_only():
    setcfg("whitepoint.colortemp", 5000)
    main_settings.set_whitepoint_temperature_config_with_option("T")
    # No numeric part -> colortemp value is left untouched, only locus set
    assert getcfg("whitepoint.colortemp.locus") == "T"
    assert getcfg("whitepoint.colortemp") == 5000


def test_set_whitepoint_xy():
    main_settings.set_whitepoint_config_with_option("W0.3127,0.3290")
    assert float(getcfg("whitepoint.x")) == 0.3127
    assert float(getcfg("whitepoint.y")) == 0.3290
    assert float(getcfg("3dlut.whitepoint.x")) == 0.3127
    assert float(getcfg("3dlut.whitepoint.y")) == 0.3290
    assert getcfg("whitepoint.colortemp", False) in (None, "")


def test_set_calibration_luminance():
    main_settings.set_calibration_luminance_config_with_option("b120")
    assert float(getcfg("calibration.luminance")) == 120


def test_set_tone_response_curve():
    main_settings.set_tone_response_curve_config_with_option("g2.4")
    assert getcfg("trc.type") == "g"
    assert str(getcfg("trc")) == "2.4"


def test_set_calibration_black_output_offset():
    main_settings.set_calibration_black_output_offset_config_with_option("f1.0")
    assert str(getcfg("calibration.black_output_offset")) == "1.0"


def test_set_ambient_view_condition_adjustment():
    main_settings.set_ambient_view_condition_adjustment_config_with_option("a100")
    assert getcfg("calibration.ambient_viewcond_adjust") == 1
    assert getcfg("calibration.ambient_viewcond_adjust.lux") == 100 / 5.0


def test_set_ambient_view_condition_adjustment_ignores_non_numeric():
    setcfg("calibration.ambient_viewcond_adjust", 0)
    main_settings.set_ambient_view_condition_adjustment_config_with_option("axyz")
    assert getcfg("calibration.ambient_viewcond_adjust") == 0


def test_set_black_point_correction_sets_and_returns_true():
    result = main_settings.set_black_point_correction_config_with_option("k1", False)
    assert result == (True,)
    assert float(getcfg("calibration.black_point_correction")) == 1


def test_set_calibration_black_point_rate():
    main_settings.set_calibration_black_point_rate_config_with_option("A4")
    assert float(getcfg("calibration.black_point_rate")) == 4


def test_set_calibration_black_luminance():
    main_settings.set_calibration_black_luminance_config_with_option("B0.5")
    assert str(getcfg("calibration.black_luminance")) == "0.5"


def test_set_measureframe():
    main_settings.set_measureframe_config_with_option("P0.5,0.5,1.0")
    assert getcfg("dimensions.measureframe") == "0.5,0.5,1.0"
    assert getcfg("dimensions.measureframe.unzoomed") == "0.5,0.5,1.0"


def test_set_measureframe_ignores_short_option():
    setcfg("dimensions.measureframe", "0.4,0.4,1.0")
    main_settings.set_measureframe_config_with_option("P1,2")
    assert getcfg("dimensions.measureframe") == "0.4,0.4,1.0"


def test_set_measurement_mode_adaptive():
    main_settings.set_measurement_mode_adaptive_config_with_option(1)
    assert getcfg("measurement_mode.adaptive") == 1


def test_set_measurement_mode_highres():
    main_settings.set_measurement_mode_highres_config_with_option(1)
    assert getcfg("measurement_mode.highres") == 1


def test_set_measurement_mode_projector_sets_flag_and_measureframe():
    main_settings.set_measurement_mode_projector_config_with_option("p")
    assert getcfg("measurement_mode.projector") == 1


def test_set_measure_darken_background():
    main_settings.set_measure_darken_background_config_with_option(1)
    assert getcfg("measure.darken_background") == 1


def test_set_ccss_relative_path_is_joined(tmp_path):
    cal_path = str(tmp_path / "session" / "foo.cal")
    ccmx, update = main_settings.set_ccss_config_with_option('X "bar.ccss"', cal_path)
    assert update is True
    assert ccmx.endswith("bar.ccss")
    # Relative ccmx is resolved against the cal file's directory
    assert ccmx.startswith(str(tmp_path / "session"))


def test_set_ccss_absolute_path_kept(tmp_path):
    abs_ccmx = str(tmp_path / "abs.ccss")
    ccmx, update = main_settings.set_ccss_config_with_option(
        f'X "{abs_ccmx}"', str(tmp_path / "foo.cal")
    )
    assert ccmx == abs_ccmx
    assert update is True


def test_set_drift_compensation_black_and_white():
    setcfg("drift_compensation.blacklevel", 0)
    setcfg("drift_compensation.whitelevel", 0)
    main_settings.set_drift_compensation_config_with_option("Ibw")
    assert getcfg("drift_compensation.blacklevel") == 1
    assert getcfg("drift_compensation.whitelevel") == 1


def test_set_tristimulus_observer():
    result = main_settings.set_tristimulus_observer_config_with_option("Q1931_2")
    assert result == (True,)
    assert getcfg("observer") == "1931_2"


def test_update_whitepoint_config_from_temperature_planckian():
    setcfg("whitepoint.colortemp", 6500)
    setcfg("whitepoint.colortemp.locus", "T")
    main_settings.update_whitepoint_config_from_temperature()
    # A valid temperature yields concrete 3D LUT whitepoint xy targets
    assert getcfg("3dlut.whitepoint.x", False) not in (None, "", False)
    assert getcfg("3dlut.whitepoint.y", False) not in (None, "", False)


def test_update_ccmx_items_from_path_sets_config_when_ccmx_given():
    result = main_settings.update_ccmx_items_from_path(
        "/path/to/corr.ccmx", "/path/to/foo.cal", "1", False
    )
    assert result is False
    assert getcfg("colorimeter_correction_matrix_file") == "1:/path/to/corr.ccmx"
