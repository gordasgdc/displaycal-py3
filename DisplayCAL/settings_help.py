"""What every setting changes: the registry behind the advanced-mode sections.

The advanced tabs keep every professional control. This registry groups them by
the *decision* the user takes, and says -- for each control -- what it changes,
when it fits, its unit and default, what it depends on, and whether it is
*required* (the run cannot work without it), *context* (a choice that depends on
the case) or *optional*. Texts live in the language files:

    sec.<tab>.<section>            section title
    sec.<tab>.<section>.purpose    the decision the section is about
    help.<id>.name / .what / .when / .needs

Nothing here recommends a value universally: ``when`` explains in which case a
choice fits, and defaults are shown as *the application's default*.
"""

from __future__ import annotations

from dataclasses import dataclass

REQUIRED = "required"
CONTEXT = "context"
OPTIONAL = "optional"


@dataclass(frozen=True)
class Item:
    """One setting (possibly several widgets) and how it is documented."""

    id: str
    widgets: tuple[str, ...]  # attribute names on the owning window/panel
    cfg: tuple[str, ...] = ()  # configuration keys (defaults are read from them)
    unit: str = ""
    kind: str = CONTEXT
    has_needs: bool = True


def _i(id_: str, widgets: str, cfg: str = "", unit: str = "", kind: str = CONTEXT, needs: bool = True) -> Item:
    return Item(
        id_,
        tuple(widgets.split()),
        tuple(cfg.split()),
        unit,
        kind,
        needs,
    )


ITEMS: dict[str, Item] = {
    it.id: it
    for it in (
        # --- Display & instrument -------------------------------------------
        _i("display", "display_ctrl detect_displays_and_ports_btn", "display.number", kind=REQUIRED),
        _i("lut_access", "display_lut_ctrl display_lut_link_ctrl"),
        _i("instrument", "comport_ctrl", "comport.number", kind=REQUIRED),
        _i("mode", "measurement_mode_ctrl", "measurement_mode"),
        _i(
            "correction",
            "colorimeter_correction_matrix_ctrl colorimeter_correction_info_btn "
            "colorimeter_correction_matrix_btn colorimeter_correction_web_btn "
            "colorimeter_correction_create_btn display_lookup_btn",
            "colorimeter_correction_matrix_file",
        ),
        _i("whitelevel_drift", "whitelevel_drift_compensation_cb", "drift_compensation.whitelevel", kind=OPTIONAL),
        _i("blacklevel_drift", "blacklevel_drift_compensation_cb", "drift_compensation.blacklevel", kind=OPTIONAL),
        _i(
            "update_delay",
            "override_min_display_update_delay_ms_cb min_display_update_delay_ms_ctrl",
            "measure.min_display_update_delay_ms",
            "ms",
            OPTIONAL,
        ),
        _i(
            "settle_mult",
            "override_display_settle_time_mult_cb display_settle_time_mult_ctrl",
            "measure.display_settle_time_mult",
            "×",
            OPTIONAL,
        ),
        _i(
            "ffp",
            "ffp_insertion_cb ffp_insertion_interval_ctrl ffp_insertion_duration_ctrl ffp_insertion_level_ctrl",
            "patterngenerator.ffp_insertion.interval patterngenerator.ffp_insertion.duration patterngenerator.ffp_insertion.level",
            "s / s / %",
            OPTIONAL,
        ),
        _i("output_levels", "output_levels_auto output_levels_full_range output_levels_limited_range"),
        # --- Calibration ----------------------------------------------------
        _i("interactive", "interactive_adjustment_cb", "calibration.interactive_display_adjustment"),
        _i("update_cal", "calibration_update_cb", "calibration.update", kind=OPTIONAL),
        _i("observer", "observer_ctrl", "observer"),
        _i(
            "whitepoint",
            "whitepoint_ctrl whitepoint_colortemp_ctrl whitepoint_colortemp_locus_ctrl whitepoint_x_ctrl "
            "whitepoint_y_ctrl visual_whitepoint_editor_btn whitepoint_measure_btn",
            "whitepoint.colortemp",
            "K",
        ),
        _i("white_level", "luminance_ctrl luminance_textctrl luminance_measure_btn", "calibration.luminance", "cd/m²"),
        _i("black_level", "black_luminance_ctrl black_luminance_textctrl black_luminance_measure_btn", "calibration.black_luminance", "cd/m²"),
        _i("tone_curve", "trc_ctrl trc_textctrl trc_type_ctrl", "trc trc.type"),
        _i("black_offset", "black_output_offset_ctrl black_output_offset_intctrl", "calibration.black_output_offset", "%"),
        _i(
            "ambient",
            "ambient_adjust_cb ambient_adjust_textctrl ambient_measure_btn ambient_luminance_measure_btn",
            "calibration.ambient_viewcond_adjust calibration.ambient_viewcond_adjust.lux",
            "lux",
            OPTIONAL,
        ),
        _i(
            "black_point",
            "black_point_correction_auto_cb black_point_correction_ctrl black_point_correction_intctrl "
            "black_point_rate_ctrl black_point_rate_floatctrl",
            "calibration.black_point_correction calibration.black_point_rate",
            "%",
        ),
        _i("cal_quality", "calibration_quality_ctrl", "calibration.quality"),
        # --- Profiling -------------------------------------------------------
        _i("profile_type", "profile_type_ctrl gamap_btn", "profile.type", kind=REQUIRED),
        _i("bpc", "black_point_compensation_cb", "profile.black_point_compensation", kind=OPTIONAL),
        _i("profile_quality", "profile_quality_ctrl", "profile.quality"),
        _i("testchart", "testchart_ctrl testchart_btn create_testchart_btn", "testchart.file"),
        _i("patches", "testchart_patches_amount testchart_patches_amount_ctrl"),
        _i("blocks", "plan_block_combo plan_chart_btn", "measurement.block_size"),
        _i("sequence", "testchart_patch_sequence_ctrl", "testchart.patch_sequence"),
        _i("profile_name", "profile_name_textctrl profile_name_info_btn profile_save_path_btn", "profile.name"),
        # --- 3D LUT ----------------------------------------------------------
        _i("lut3d_create", "lut3d_create_cb", "3dlut.create"),
        _i("lut3d_source", "lut3d_input_profile_ctrl", "3dlut.input.profile"),
        _i("lut3d_trc", "lut3d_trc_ctrl lut3d_trc_gamma_ctrl lut3d_trc_gamma_type_ctrl", "3dlut.trc 3dlut.trc_gamma"),
        _i(
            "lut3d_hdr",
            "lut3d_hdr_peak_luminance_ctrl lut3d_hdr_sat_ctrl lut3d_hdr_hue_ctrl lut3d_hdr_minmll_ctrl "
            "lut3d_hdr_maxmll_ctrl lut3d_hdr_maxmll_alt_clip_cb lut3d_hdr_display_ctrl",
            kind=OPTIONAL,
        ),
        _i("lut3d_black_offset", "lut3d_trc_black_output_offset_ctrl lut3d_trc_black_output_offset_intctrl", "3dlut.trc_output_offset", "%"),
        _i("lut3d_apply_cal", "lut3d_apply_cal_cb", "3dlut.output.profile.apply_cal"),
        _i("lut3d_gamut_mapping", "gamut_mapping_inverse_a2b gamut_mapping_b2a", "3dlut.gamap.use_b2a"),
        _i("lut3d_intent", "lut3d_rendering_intent_ctrl", "3dlut.rendering_intent"),
        _i("lut3d_format", "lut3d_format_ctrl", "3dlut.format"),
        _i("lut3d_encoding", "encoding_input_ctrl encoding_output_ctrl", "3dlut.encoding.input 3dlut.encoding.output"),
        _i("lut3d_size", "lut3d_size_ctrl lut3d_bitdepth_input_ctrl lut3d_bitdepth_output_ctrl", "3dlut.size 3dlut.bitdepth.input 3dlut.bitdepth.output"),
        # --- Verification (ReportPanel) ---------------------------------------
        _i("verify_chart", "fields_ctrl chart_btn", "measurement_report.chart"),
        _i("verify_simulate_white", "simulate_whitepoint_cb simulate_whitepoint_relative_cb", kind=OPTIONAL),
        _i("verify_simulation_profile", "simulation_profile_cb use_simulation_profile_as_output_cb", kind=OPTIONAL),
    )
}

#: tab -> ordered sections -> item ids.
SECTIONS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "display_instrument": (
        ("devices", ("display", "lut_access", "instrument", "mode")),
        ("correction", ("correction",)),
        ("behavior", ("whitelevel_drift", "blacklevel_drift", "update_delay", "settle_mult", "ffp", "output_levels")),
    ),
    "calibration": (
        ("process", ("interactive", "update_cal")),
        ("target", ("observer", "whitepoint", "white_level", "black_level", "tone_curve", "black_offset")),
        ("room", ("ambient", "black_point")),
        ("precision", ("cal_quality",)),
    ),
    "profiling": (
        ("type", ("profile_type", "bpc", "profile_quality")),
        ("chart", ("testchart", "patches", "blocks", "sequence")),
        ("name", ("profile_name",)),
    ),
    "lut3d": (
        ("create", ("lut3d_create",)),
        ("source", ("lut3d_source", "lut3d_trc", "lut3d_hdr", "lut3d_black_offset")),
        ("mapping", ("lut3d_apply_cal", "lut3d_gamut_mapping", "lut3d_intent")),
        ("file", ("lut3d_format", "lut3d_encoding", "lut3d_size")),
    ),
    "verification": (
        ("what", ("verify_chart",)),
        ("simulate", ("verify_simulate_white", "verify_simulation_profile")),
    ),
}


def section_keys(tab: str, section: str) -> tuple[str, str]:
    """Language keys of a section's title and purpose."""
    return f"sec.{tab}.{section}", f"sec.{tab}.{section}.purpose"


def item_keys(item_id: str) -> dict[str, str]:
    """Language keys of an item's texts."""
    base = f"help.{item_id}"
    return {k: f"{base}.{k}" for k in ("name", "what", "when", "needs")}
