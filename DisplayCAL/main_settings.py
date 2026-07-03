"""Toolkit-neutral settings marshalling extracted from ``display_cal.MainFrame``.

This module holds the pure ``option string -> config`` logic that used to live
as methods on the wxPython ``MainFrame``. None of it touches a GUI toolkit: it
only reads/writes :mod:`DisplayCAL.config` and calls binding-agnostic helpers,
so both the legacy wx ``MainFrame`` (which delegates here) and the forthcoming
Qt main window can share it. See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``
(Stage 0).

The function names mirror the original ``MainFrame`` method names one-to-one so
the delegation is transparent and greppable. Functions that are genuinely
coupled to the running window (``set_display_number_config_with_option``,
``set_video_levels_config_with_option``) are intentionally *not* extracted and
remain on ``MainFrame``.
"""

import os
import sys

from DisplayCAL.colormath import CIEDCCT2xyY, planckianCT2xyY
from DisplayCAL.config import getcfg, setcfg
from DisplayCAL.util_decimal import stripzeros
from DisplayCAL.util_os import safe_glob


def update_whitepoint_config_from_temperature() -> None:
    """Update the whitepoint configuration from the color temperature."""
    if getcfg("whitepoint.colortemp", False):
        # Color temperature
        if getcfg("whitepoint.colortemp.locus") == "T":
            # Planckian locus
            xyY = planckianCT2xyY(getcfg("whitepoint.colortemp"))  # noqa: N806
        else:
            # Daylight locus
            xyY = CIEDCCT2xyY(getcfg("whitepoint.colortemp"))  # noqa: N806
            # Update 3D LUT whitepoint target
        if xyY:
            setcfg("3dlut.whitepoint.x", xyY[0])
            setcfg("3dlut.whitepoint.y", xyY[1])
        else:
            setcfg("3dlut.whitepoint.x", None)
            setcfg("3dlut.whitepoint.y", None)


def update_ccmx_items_from_path(
    ccmx: str, path: str, ccxxsetting: str, update_ccmx_items: bool
) -> bool:
    """Update the colorimeter correction matrix items based on the path.

    Args:
        ccmx (str): The colorimeter correction matrix file path.
        path (str): The path to the profile.
        ccxxsetting (str): The colorimeter correction setting.
        update_ccmx_items (bool): Whether to update the CCMX items.

    Returns:
        bool: True if CCMX items were updated, False otherwise.
    """
    if not ccmx:
        ccxx = safe_glob(
            os.path.join(os.path.dirname(path), "*.ccmx")
        ) or safe_glob(os.path.join(os.path.dirname(path), "*.ccss"))
        if ccxx and len(ccxx) == 1:
            ccmx = ccxx[0]
            update_ccmx_items = True
    if ccmx:
        setcfg(
            "colorimeter_correction_matrix_file",
            f"{ccxxsetting}:{ccmx}",
        )
    return update_ccmx_items


def set_profile_quality_config_with_option(option: str) -> None:
    """Set the profile quality configuration.

    Args:
        option (str): The option string containing the profile quality setting.
    """
    setcfg("profile.quality", option[1])


def set_profile_quality_b2a_config_with_option(option: str) -> None:
    """Set the profile quality B2A configuration.

    Args:
        option (str): The option string containing the profile quality B2A
            setting.
    """
    setcfg("profile.quality.b2a", option[1] or "l")


def set_profile_black_point_compenstation_config_with_option(
    option: str, is_preset: bool, is_3dlut_preset: bool
) -> None:
    """Set the profile black point compensation configuration.

    Args:
        option (str): The option string containing the profile black point
            compensation setting.
        is_preset (bool): Whether the profile is a preset.
        is_3dlut_preset (bool): Whether the profile is a 3D LUT preset.
    """
    if is_preset and not is_3dlut_preset and sys.platform == "darwin":
        # Force profile type to single shaper + matrix
        # due to OS X bugs with cLUT profiles and
        # matrix profiles with individual shaper curves
        option = "aS"
        # Force black point compensation due to OS X
        # bugs with non BPC profiles
        setcfg("profile.black_point_compensation", 1)
    setcfg("profile.type", option[1])


def set_gamap_profile_config_with_option(option: str) -> None:
    """Set the gamap profile configuration.

    Args:
        option (str): The option string containing the profile.
    """
    option = option.split(None, 1)
    setcfg("gamap_profile", option[-1][1:-1])
    setcfg("gamap_perceptual", 1)
    if option[0:1] == "S":
        setcfg("gamap_saturation", 1)


def set_gamap_src_viewcond_config_with_option(option: str) -> None:
    """Set the gamap source view condition configuration.

    Args:
        option (str): The option string containing the source view condition.
    """
    setcfg("gamap_src_viewcond", option[1:])


def set_gamap_out_viewcond_config_with_option(option: str) -> None:
    """Set the gamap output view condition configuration.

    Args:
        option (str): The option string containing the output view condition.
    """
    setcfg("gamap_out_viewcond", option[1:])


def set_gamap_perceptual_intent_config_with_option(option: str) -> None:
    """Set the gamap perceptual intent configuration.

    Args:
        option (str): The option string containing the perceptual intent.
    """
    setcfg("gamap_perceptual_intent", option[1:])


def set_gamap_saturation_intent_config_with_option(option: str) -> None:
    """Set the gamap saturation intent configuration.

    Args:
        option (str): The option string containing the saturation intent.
    """
    setcfg("gamap_saturation_intent", option[1:])


def set_interactive_display_adjustment_config_with_option(option: str) -> None:
    """Set the interactive display adjustment configuration.

    Args:
        option (str): The option string containing the interactive display
            adjustment setting.
    """
    setcfg("calibration.interactive_display_adjustment", 0)


def set_calibration_quality_config_with_option(option: str) -> None:
    """Set the calibration quality configuration.

    Args:
        option (str): The option string containing the calibration quality
            setting.
    """
    setcfg("calibration.quality", option[1])


def set_measurement_mode_config_with_option(option: str) -> None:
    """Set the measurement mode configuration.

    Args:
        option (str): The option string containing the measurement mode setting.
    """
    if getcfg("measurement_mode") != "auto":
        setcfg("measurement_mode", option[1])


def set_whitepoint_temperature_config_with_option(option: str) -> None:
    """Set the whitepoint temperature configuration.

    Args:
        option (str): The option string containing the whitepoint temperature
            setting.
    """
    setcfg("whitepoint.colortemp.locus", option[0:1])
    if option[1:]:
        setcfg("whitepoint.colortemp", int(float(option[1:])))
    setcfg("whitepoint.x", None)
    setcfg("whitepoint.y", None)


def set_whitepoint_config_with_option(option: str) -> None:
    """Set the whitepoint configuration.

    Args:
        option (str): The option string containing the whitepoint setting.
    """
    option = option[1:].split(",")
    setcfg("whitepoint.colortemp", None)
    setcfg("whitepoint.x", option[0])
    setcfg("whitepoint.y", option[1])
    setcfg("3dlut.whitepoint.x", option[0])
    setcfg("3dlut.whitepoint.y", option[1])


def set_calibration_luminance_config_with_option(option: str) -> None:
    """Set the calibration luminance configuration.

    Args:
        option (str): The option string containing the luminance setting.
    """
    setcfg("calibration.luminance", option[1:])


def set_tone_response_curve_config_with_option(option: str) -> None:
    """Set the tone response curve configuration.

    Args:
        option (str): The option string containing the tone response curve
            setting.
    """
    setcfg("trc.type", option[0:1])
    setcfg("trc", option[1:])


def set_calibration_black_output_offset_config_with_option(option: str) -> None:
    """Set the calibration black output offset configuration.

    Args:
        option (str): The option string containing the black output.
    """
    setcfg("calibration.black_output_offset", option[1:])


def set_ambient_view_condition_adjustment_config_with_option(option: str) -> None:
    """Set the ambient view condition adjustment configuration.

    Args:
        option (str): The option string containing the ambient view condition
            adjustment setting.
    """
    try:
        ambient = float(option[1:])
    except ValueError:
        pass
    else:
        setcfg("calibration.ambient_viewcond_adjust", 1)
        # Argyll dispcal uses 20% of ambient (in lux,
        # fixed steradiant of 3.1415) as adapting
        # luminance, but we assume it already *is*
        # the adapting luminance. To correct for this,
        # scale so that dispcal gets the correct value.
        setcfg(
            "calibration.ambient_viewcond_adjust.lux",
            ambient / 5.0,
        )


def set_black_point_correction_config_with_option(
    option: str, black_point_correction: bool
) -> tuple[bool]:
    """Set the calibration black point correction configuration.

    Args:
        option (str): The option string containing the black point correction
            setting.
        black_point_correction (bool): Current state of black point correction.

    Returns:
        tuple(bool): Updated state of black point correction.
    """
    if stripzeros(option[1:]) >= 0:
        black_point_correction = True
        setcfg("calibration.black_point_correction", option[1:])
    return (black_point_correction,)


def set_calibration_black_point_rate_config_with_option(option: str) -> None:
    """Set the calibration black point rate configuration.

    Args:
        option (str): The option string containing the black point rate setting.
    """
    setcfg("calibration.black_point_rate", option[1:])


def set_calibration_black_luminance_config_with_option(option: str) -> None:
    """Set the calibration black luminance configuration.

    Args:
        option (str): The option string containing the black luminance setting.
    """
    setcfg("calibration.black_luminance", option[1:])


def set_measureframe_config_with_option(option: str) -> None:
    """Set the measure frame configuration.

    Args:
        option (str): The option string containing the measure frame setting.
    """
    if len(option[1:]) >= 5:
        setcfg("dimensions.measureframe", option[1:])
        setcfg("dimensions.measureframe.unzoomed", option[1:])


def set_measurement_mode_adaptive_config_with_option(option: str) -> None:
    """Set the measurement mode adaptive configuration.

    Args:
        option (str): The option string containing the adaptive setting.
    """
    setcfg("measurement_mode.adaptive", option)


def set_measurement_mode_highres_config_with_option(option: str) -> None:
    """Set the measurement mode high resolution configuration.

    Args:
        option (str): The option string containing the high resolution setting.
    """
    setcfg("measurement_mode.highres", option)


def set_measurement_mode_projector_config_with_option(option: str) -> None:
    """Set the measurement mode projector configuration.

    Args:
        option (str): The option string containing the projector setting.
    """
    if len(option[1:]) == 0:
        setcfg("measurement_mode.projector", 1)
    set_measureframe_config_with_option(option)


def set_measure_darken_background_config_with_option(option: str) -> None:
    """Set the measure darken background configuration.

    Args:
        option (str): The option string containing the darken background setting.
    """
    setcfg("measure.darken_background", option)


def set_ccss_config_with_option(option: str, path: str) -> tuple[str, bool]:
    """Set the colorimeter correction matrix file configuration.

    Args:
        option (str): The option string containing the ccmx file path.
        path (str): The path to the calibration file.

    Returns:
        tuple[str, bool]: The ccmx file path and a boolean indicating whether to
            update ccmx items.
    """
    option = option.split(None, 1)
    ccmx = option[-1][1:-1]
    if not os.path.isabs(ccmx):
        ccmx = os.path.join(os.path.dirname(path), ccmx)
    # Need to update ccmx items again even if
    # comport_ctrl_handler already did
    update_ccmx_items = True
    return ccmx, update_ccmx_items


def set_drift_compensation_config_with_option(option: str) -> None:
    """Set the drift compensation configuration.

    Args:
        option (str): The option string containing the drift compensation
            setting.
    """
    if "b" in option[1:]:
        setcfg("drift_compensation.blacklevel", 1)
    if "w" in option[1:]:
        setcfg("drift_compensation.whitelevel", 1)


def set_tristimulus_observer_config_with_option(option: str) -> tuple[bool]:
    """Set the tristimulus observer configuration.

    Args:
        option (str): The option string containing the observer setting.

    Returns:
        tuple(bool): Always returns True in a tuple.
    """
    setcfg("observer", option[1:])
    # Need to update ccmx items again even if
    # comport_ctrl_handler already did because CCMX
    # observer may override calibration observer
    return (True,)
