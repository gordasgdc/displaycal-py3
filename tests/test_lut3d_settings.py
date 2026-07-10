"""Tests for the toolkit-neutral ``DisplayCAL/lut3d_settings.py`` helpers.

Covers the pieces ported from wx's ``LUT3DMixin`` (``wx_lut_3d_frame.py``)
for the 3D LUT tab embedded in ``MainFrame``. No display or QApplication is
needed.
"""

import os

import pytest

from DisplayCAL import lut3d_settings as l3d
from DisplayCAL.config import PROFILE_EXT


# -- TRC combo selection -----------------------------------------------------


def test_trc_selection_side_effects_gamma22():
    assert l3d.trc_selection_side_effects(0) == {
        "3dlut.trc_gamma": 2.2,
        "3dlut.trc_gamma_type": "b",
        "3dlut.trc_output_offset": 1.0,
        "3dlut.trc": "gamma2.2",
    }


def test_trc_selection_side_effects_bt1886():
    assert l3d.trc_selection_side_effects(1) == {
        "3dlut.trc_gamma": 2.4,
        "3dlut.trc_gamma_type": "B",
        "3dlut.trc_output_offset": 0.0,
        "3dlut.trc": "bt1886",
    }


def test_trc_selection_side_effects_smpte2084_hardclip():
    result = l3d.trc_selection_side_effects(2)
    assert result["3dlut.trc"] == "smpte2084.hardclip"
    assert result["3dlut.hdr_maxmll"] == 10000


def test_trc_selection_side_effects_smpte2084_rolloffclip():
    result = l3d.trc_selection_side_effects(3)
    assert result["3dlut.trc"] == "smpte2084.rolloffclip"
    assert result["3dlut.hdr_maxmll"] == 10000


def test_trc_selection_side_effects_hlg():
    assert l3d.trc_selection_side_effects(4) == {
        "3dlut.trc_output_offset": 0.0,
        "3dlut.trc": "hlg",
    }


def test_trc_selection_side_effects_custom():
    assert l3d.trc_selection_side_effects(5) == {"3dlut.trc": "customgamma"}


def test_resolve_trc_selection_smpte2084_hardclip():
    assert l3d.resolve_trc_selection("smpte2084.hardclip", "b", 0.0, 2.2) == (
        2,
        "smpte2084.hardclip",
    )


def test_resolve_trc_selection_smpte2084_rolloffclip():
    assert l3d.resolve_trc_selection("smpte2084.rolloffclip", "b", 0.0, 2.2) == (
        3,
        "smpte2084.rolloffclip",
    )


def test_resolve_trc_selection_hlg():
    assert l3d.resolve_trc_selection("hlg", "b", 0.0, 2.2) == (4, "hlg")


def test_resolve_trc_selection_bt1886_recognized_by_shape():
    # Even if "3dlut.trc" itself was hand-edited to something else, the
    # gamma/type/output-offset triple that defines BT.1886 is recognized and
    # "3dlut.trc" is corrected to match (mirrors the wx self-healing logic).
    assert l3d.resolve_trc_selection("customgamma", "B", 0.0, 2.4) == (1, "bt1886")


def test_resolve_trc_selection_gamma22_recognized_by_shape():
    assert l3d.resolve_trc_selection("customgamma", "b", 1.0, 2.2) == (0, "gamma2.2")


def test_resolve_trc_selection_falls_back_to_custom():
    assert l3d.resolve_trc_selection("bt1886", "b", 0.5, 2.6) == (5, "customgamma")


# -- TRC/HDR row visibility --------------------------------------------------


def _visibility(**overrides):
    kwargs = dict(
        trc="customgamma",
        trc_format="cube",
        argyll_version="1.9.0",
        show_advanced_options=False,
        lut3d_create=True,
        hdr_maxmll=10000.0,
        content_colorspace_is_custom=False,
    )
    kwargs.update(overrides)
    return l3d.compute_trc_visibility(**kwargs)


def test_visibility_old_argyll_hides_everything():
    v = _visibility(argyll_version="1.4.0")
    assert v.trc_row is False
    assert v.trc_gamma is False
    assert v.black_output_offset is False


def test_visibility_custom_gamma_shown_without_advanced_options():
    # "customgamma" is visible even without show_advanced_options (matches
    # wx: ``trc == "customgamma" or show_advanced_options``).
    v = _visibility(trc="customgamma", show_advanced_options=False)
    assert v.trc_gamma is True
    assert v.trc_gamma_type is True
    assert v.black_output_offset is True


def test_visibility_bt1886_hidden_without_advanced_options():
    v = _visibility(trc="bt1886", show_advanced_options=False)
    assert v.trc_gamma is False
    assert v.black_output_offset is False


def test_visibility_bt1886_shown_with_advanced_options():
    v = _visibility(trc="bt1886", show_advanced_options=True)
    assert v.trc_gamma is True
    assert v.trc_gamma_type is True
    assert v.black_output_offset is True


def test_visibility_black_output_offset_requires_lut3d_create():
    v = _visibility(trc="bt1886", show_advanced_options=True, lut3d_create=False)
    assert v.black_output_offset is False


def test_visibility_smpte2084_hardclip_shows_peak_and_minmll_not_maxmll():
    v = _visibility(
        trc="smpte2084.hardclip", show_advanced_options=True, lut3d_create=True
    )
    assert v.hdr_peak_luminance is True
    assert v.hdr_minmll is True
    assert v.hdr_maxmll is False
    assert v.hdr_diffuse_white is False
    # SMPTE 2084 hides the gamma/gamma-type fields (they're not applicable).
    assert v.trc_gamma is False
    assert v.trc_gamma_type is False


def test_visibility_smpte2084_rolloffclip_shows_maxmll_and_diffuse_white():
    v = _visibility(
        trc="smpte2084.rolloffclip", show_advanced_options=True, lut3d_create=True
    )
    assert v.hdr_maxmll is True
    assert v.hdr_diffuse_white is True
    assert v.hdr_sat_hue is True
    assert v.content_colorspace is True


def test_visibility_maxmll_alt_clip_hidden_at_ceiling():
    v = _visibility(
        trc="smpte2084.rolloffclip",
        show_advanced_options=True,
        hdr_maxmll=10000.0,
    )
    assert v.hdr_maxmll_alt_clip is False


def test_visibility_maxmll_alt_clip_shown_below_ceiling():
    v = _visibility(
        trc="smpte2084.rolloffclip",
        show_advanced_options=True,
        hdr_maxmll=4000.0,
    )
    assert v.hdr_maxmll_alt_clip is True


def test_visibility_hlg_shows_ambient_and_system_gamma_not_peak():
    v = _visibility(trc="hlg", show_advanced_options=True, lut3d_create=True)
    assert v.hdr_ambient_luminance is True
    assert v.hdr_system_gamma is True
    assert v.hdr_peak_luminance is False
    # HLG is excluded from the "trailing" black-output-offset/gamma-type rows.
    assert v.black_output_offset is False
    assert v.trc_gamma_type is False


def test_visibility_content_colorspace_xy_only_when_custom_selected():
    v = _visibility(
        trc="hlg", show_advanced_options=True, content_colorspace_is_custom=False
    )
    assert v.content_colorspace is True
    assert v.content_colorspace_xy is False
    v = _visibility(
        trc="hlg", show_advanced_options=True, content_colorspace_is_custom=True
    )
    assert v.content_colorspace_xy is True


def test_visibility_hdr_display_requires_smpte2084_and_madvr():
    v = _visibility(trc="smpte2084.hardclip", trc_format="madVR")
    assert v.hdr_display is True
    v = _visibility(trc="smpte2084.hardclip", trc_format="cube")
    assert v.hdr_display is False
    v = _visibility(trc="hlg", trc_format="madVR")
    assert v.hdr_display is False


# -- HDR readouts -------------------------------------------------------------


def test_diffuse_white_cdm2_full_range_matches_reference():
    # With no roll-off applied (mastering white == 10000 == reference max),
    # the diffuse white readout should reproduce the reference cd/m2 closely.
    value, below_reference = l3d.diffuse_white_cdm2(10000.0, 0.0, 10000.0, 1)
    assert value == pytest.approx(94.37844, abs=1e-6)
    assert below_reference is False


def test_diffuse_white_cdm2_rolled_off_darkens():
    # BT.2390's roll-off only compresses highlights near the knee, so a
    # low target peak relative to a much higher mastering peak pulls the
    # diffuse-white readout down.
    value, below_reference = l3d.diffuse_white_cdm2(100.0, 0.0, 10000.0, 1)
    assert value < 94.37844
    assert below_reference is True


def test_hlg_system_gamma_default_ambient():
    # 5 cd/m2 is the BT.2390-4 nominal reference ambient, so the adjustment
    # factor is 1 and the system gamma stays at the base 1.2.
    assert round(l3d.hlg_system_gamma(5), 4) == 1.2


def test_hlg_system_gamma_varies_with_ambient():
    assert l3d.hlg_system_gamma(100) != l3d.hlg_system_gamma(5)


# -- Content colorspace -------------------------------------------------------


def test_content_colorspace_xy_rec709():
    result = l3d.content_colorspace_xy("Rec. 709")
    assert result["3dlut.content.colorspace.red.x"] == 0.64
    assert result["3dlut.content.colorspace.red.y"] == 0.33
    assert result["3dlut.content.colorspace.white.x"] == 0.3127
    assert result["3dlut.content.colorspace.white.y"] == 0.329


def test_resolve_content_colorspace_selection_matches_known_space():
    colors_xy = l3d.content_colorspace_xy("Rec. 709")
    index = l3d.resolve_content_colorspace_selection(colors_xy)
    assert l3d.CONTENT_COLORSPACE_NAMES[index] == "Rec. 709"


def test_resolve_content_colorspace_selection_custom_when_unmatched():
    colors_xy = {
        f"3dlut.content.colorspace.{color}.{coord}": v
        for color, v in (
            ("white", (0.31, 0.32)),
            ("red", (0.61, 0.31)),
            ("green", (0.21, 0.71)),
            ("blue", (0.14, 0.05)),
        )
        for coord, v in zip("xy", v)
    }
    index = l3d.resolve_content_colorspace_selection(colors_xy)
    assert index == len(l3d.CONTENT_COLORSPACE_NAMES)


# -- Size snapping ------------------------------------------------------------


def test_lut3d_size_snap_mga_rounds_to_nearest_supported():
    assert l3d.lut3d_size_snap("mga", 24) == 17
    assert l3d.lut3d_size_snap("mga", 40) == 33
    assert l3d.lut3d_size_snap("mga", 17) == 17


def test_lut3d_size_snap_reshade_rounds_down_to_supported():
    assert l3d.lut3d_size_snap("ReShade", 24) == 16
    assert l3d.lut3d_size_snap("ReShade", 40) == 32
    assert l3d.lut3d_size_snap("ReShade", 65) == 64
    assert l3d.lut3d_size_snap("ReShade", 32) == 32


def test_lut3d_size_snap_unrestricted_format_passthrough():
    assert l3d.lut3d_size_snap("cube", 24) == 24


# -- Format side effects -------------------------------------------------------


def _base_cfg(**overrides):
    cfg = {
        "3dlut.encoding.input": "n",
        "3dlut.encoding.output": "n",
        "3dlut.encoding.input.backup": "n",
        "3dlut.encoding.output.backup": "n",
        "3dlut.size": 65,
        "3dlut.size.backup": 65,
        "3dlut.bitdepth.output": 12,
    }
    cfg.update(overrides)
    return cfg


def test_format_side_effects_madvr_forces_encoding_and_size():
    updates = l3d.lut3d_format_side_effects("cube", "madVR", _base_cfg())
    assert updates["3dlut.format"] == "madVR"
    assert updates["3dlut.encoding.input"] == "t"
    assert updates["3dlut.encoding.output"] == "t"
    assert updates["3dlut.size"] == 65
    # Switching into an override format backs up the prior encoding.
    assert updates["3dlut.encoding.input.backup"] == "n"
    assert updates["3dlut.encoding.output.backup"] == "n"


def test_format_side_effects_eecolor_forces_size_65():
    updates = l3d.lut3d_format_side_effects(
        "cube", "eeColor", _base_cfg(**{"3dlut.size": 33})
    )
    assert updates["3dlut.size"] == 65
    assert updates["3dlut.encoding.output"] == "t"


def test_format_side_effects_mga_forces_bitdepth_16_and_snaps_size():
    updates = l3d.lut3d_format_side_effects(
        "cube", "mga", _base_cfg(**{"3dlut.size": 24})
    )
    assert updates["3dlut.bitdepth.output"] == 16
    assert updates["3dlut.size"] == 17


def test_format_side_effects_dcl_forces_fixed_settings():
    updates = l3d.lut3d_format_side_effects("cube", "dcl", _base_cfg())
    assert updates["3dlut.encoding.input"] == "n"
    assert updates["3dlut.encoding.output"] == "n"
    assert updates["3dlut.size"] == 33
    assert updates["3dlut.bitdepth.output"] == 12


def test_format_side_effects_reshade_forces_8bit_and_snaps_size():
    updates = l3d.lut3d_format_side_effects(
        "cube", "ReShade", _base_cfg(**{"3dlut.size": 65})
    )
    assert updates["3dlut.encoding.input"] == "n"
    assert updates["3dlut.encoding.output"] == "n"
    assert updates["3dlut.bitdepth.output"] == 8
    assert updates["3dlut.size"] == 64


def test_format_side_effects_leaving_override_restores_backup():
    cfg = _base_cfg(
        **{
            "3dlut.encoding.input": "t",
            "3dlut.encoding.output": "t",
            "3dlut.encoding.input.backup": "5",
            "3dlut.encoding.output.backup": "5",
            "3dlut.size": 65,
            "3dlut.size.backup": 17,
        }
    )
    updates = l3d.lut3d_format_side_effects("madVR", "cube", cfg)
    assert updates["3dlut.encoding.input"] == "5"
    assert updates["3dlut.encoding.output"] == "5"
    assert updates["3dlut.size"] == 17
    assert updates["3dlut.format"] == "cube"


def test_format_side_effects_png_defaults_bitdepth_to_8_when_unsupported():
    updates = l3d.lut3d_format_side_effects(
        "cube", "png", _base_cfg(**{"3dlut.bitdepth.output": 12})
    )
    assert updates["3dlut.bitdepth.output"] == 8


def test_format_side_effects_png_keeps_16bit():
    updates = l3d.lut3d_format_side_effects(
        "cube", "png", _base_cfg(**{"3dlut.bitdepth.output": 16})
    )
    assert "3dlut.bitdepth.output" not in updates


# -- Encoding lists ------------------------------------------------------------


def test_lut3d_encoding_codes_madvr_output_is_t_only():
    # madVR always forces "t" input/output in practice (the format handler
    # sets it directly), but the combo's populated *code list* still gets
    # "T" spliced in for modern Argyll like every non-"dcl" format (mirrors
    # wx's ``lut3d_setup_encoding_ctrl``, which doesn't special-case madVR
    # for this insertion even though it starts from a single-item list).
    inputs, outputs = l3d.lut3d_encoding_codes("madVR", "1.9.0")
    assert inputs == ["t", "T"]
    assert outputs == ["t"]


def test_lut3d_encoding_codes_madvr_old_argyll_is_t_only():
    inputs, outputs = l3d.lut3d_encoding_codes("madVR", "1.5.0")
    assert inputs == ["t"]
    assert outputs == ["t"]


def test_lut3d_encoding_codes_dcl_is_n_only():
    inputs, outputs = l3d.lut3d_encoding_codes("dcl", "1.9.0")
    assert inputs == ["n"]
    assert outputs == ["n"]


def test_lut3d_encoding_codes_inserts_clip_wtw_for_modern_argyll():
    inputs, outputs = l3d.lut3d_encoding_codes("cube", "1.9.0")
    assert "T" in inputs
    assert "T" not in outputs  # collink doesn't support xvYCC output encoding.


def test_lut3d_encoding_codes_omits_clip_wtw_for_old_argyll():
    inputs, _outputs = l3d.lut3d_encoding_codes("cube", "1.5.0")
    assert "T" not in inputs


def test_lut3d_encoding_codes_output_excludes_x_and_bigx():
    _inputs, outputs = l3d.lut3d_encoding_codes("cube", "1.9.0")
    assert "x" not in outputs
    assert "X" not in outputs


def test_lut3d_encoding_controls_visible_gated_on_argyll_1_6():
    assert l3d.lut3d_encoding_controls_visible("1.6.0") is True
    assert l3d.lut3d_encoding_controls_visible("1.9.0") is True
    assert l3d.lut3d_encoding_controls_visible("1.5.0") is False


def test_lut3d_bitdepth_controls_visible():
    assert l3d.lut3d_bitdepth_controls_visible("3dl") == (True, True)
    assert l3d.lut3d_bitdepth_controls_visible("png") == (False, True)
    assert l3d.lut3d_bitdepth_controls_visible("cube") == (False, False)


# -- install_via_copy --------------------------------------------------------


def test_install_via_copy_plain_single_file(tmp_path):
    src = tmp_path / "lut.cube"
    src.write_bytes(b"cube data")
    dst = tmp_path / "dest" / "lut.cube"
    dst.parent.mkdir()

    result = l3d.install_via_copy("cube", 33, 16, str(src), str(dst))

    assert result == [str(dst)]
    assert dst.read_bytes() == b"cube data"


def test_install_via_copy_eecolor_copies_companion_1d_luts(tmp_path):
    src = tmp_path / "lut-3d.txt"
    src.write_bytes(b"3d lut")
    for part in ("first", "second"):
        for channel in ("blue", "green", "red"):
            (tmp_path / f"lut-3d-{part}1d{channel}.txt").write_bytes(
                f"{part}-{channel}".encode()
            )
    dst_dir = tmp_path / "dest"
    dst_dir.mkdir()
    dst = dst_dir / "installed.txt"

    result = l3d.install_via_copy("eeColor", 17, 16, str(src), str(dst))

    assert len(result) == 7  # primary LUT + 6 companions
    assert dst.read_bytes() == b"3d lut"
    for part in ("first", "second"):
        for channel in ("blue", "green", "red"):
            companion = dst_dir / f"installed-{part}1d{channel}.txt"
            assert companion.read_bytes() == f"{part}-{channel}".encode()


def test_install_via_copy_eecolor_skips_missing_companions(tmp_path):
    src = tmp_path / "lut-3d.txt"
    src.write_bytes(b"3d lut")
    dst_dir = tmp_path / "dest"
    dst_dir.mkdir()
    dst = dst_dir / "installed.txt"

    result = l3d.install_via_copy("eeColor", 17, 16, str(src), str(dst))

    assert result == [str(dst)]


def test_install_via_copy_reshade_modern_shaders_folder(tmp_path):
    src = tmp_path / "lut.png"
    src.write_bytes(b"png data")
    dst_dir = tmp_path / "install"
    shaders = dst_dir / "reshade-shaders"
    (shaders / "Textures").mkdir(parents=True)
    (shaders / "Shaders").mkdir(parents=True)
    dst = dst_dir / "ColorLookupTable.png"

    result = l3d.install_via_copy("ReShade", 32, 16, str(src), str(dst))

    installed_texture = shaders / "Textures" / "ColorLookupTable.png"
    installed_fx = shaders / "Shaders" / "ColorLookupTable.fx"
    assert result == [str(installed_texture)]
    assert installed_texture.read_bytes() == b"png data"
    assert installed_fx.is_file()
    fx_text = installed_fx.read_text()
    assert "${WIDTH}" not in fx_text
    assert "${HEIGHT}" not in fx_text
    assert "1024" in fx_text  # WIDTH = size**2 = 32**2
    assert "RGBA16" in fx_text


def test_install_via_copy_reshade_legacy_patches_existing_fx(tmp_path):
    src = tmp_path / "lut.png"
    src.write_bytes(b"png data")
    dst_dir = tmp_path / "install"
    dst_dir.mkdir()
    (dst_dir / "ReShade.fx").write_bytes(b"// existing shader content\n")
    dst = dst_dir / "ColorLookupTable.png"

    result = l3d.install_via_copy("ReShade", 32, 16, str(src), str(dst))

    assert result == [str(dst)]
    assert dst.read_bytes() == b"png data"
    patched = (dst_dir / "ReShade.fx").read_bytes()
    assert b'#include "ColorLookupTable.fx"' in patched
    assert b"// existing shader content" in patched
    assert (dst_dir / "ColorLookupTable.fx").is_file()


def test_install_via_copy_reshade_no_existing_layout_writes_shader_only(tmp_path):
    src = tmp_path / "lut.png"
    src.write_bytes(b"png data")
    dst_dir = tmp_path / "install"
    dst_dir.mkdir()
    dst = dst_dir / "ColorLookupTable.png"

    result = l3d.install_via_copy("ReShade", 32, 16, str(src), str(dst))

    assert result == [str(dst)]
    assert dst.read_bytes() == b"png data"
    assert (dst_dir / "ColorLookupTable.fx").is_file()
    assert not (dst_dir / "ReShade.fx").exists()


# -- resolve_lut3d_path_info --------------------------------------------------


class _FakeWorker:
    """Mimics ``Worker.lut3d_get_filename``'s two call shapes used here."""

    def __init__(self, input_profile_stem: str = "lut3d_input"):
        self._input_profile_stem = input_profile_stem
        self.calls: list[tuple] = []

    def lut3d_get_filename(
        self, path=None, include_input_profile=True, include_ext=True
    ):
        self.calls.append((path, include_input_profile, include_ext))
        if not include_input_profile and not include_ext:
            return self._input_profile_stem
        return path or "/default/calibration.cube"


def _base_kwargs(**overrides):
    kwargs = dict(
        set_mr_sim_profile=False,
        current_devlink_profile=None,
        current_simulation_profile=None,
        tab_enabled=False,
        trc="",
        whitepoint_x=False,
        input_profile="",
    )
    kwargs.update(overrides)
    return kwargs


def test_resolve_lut3d_path_info_devlink_changed(tmp_path):
    lut3d_path = str(tmp_path / "profile.cube")
    info = l3d.resolve_lut3d_path_info(
        _FakeWorker(), lut3d_path, **_base_kwargs()
    )
    assert info.lut3d_path == lut3d_path
    assert info.devlink_profile == os.path.splitext(lut3d_path)[0] + PROFILE_EXT
    assert info.devlink_changed is True
    assert info.simulation_profile is None
    assert info.mr_option_changed is True


def test_resolve_lut3d_path_info_devlink_unchanged(tmp_path):
    lut3d_path = str(tmp_path / "profile.cube")
    devlink = os.path.splitext(lut3d_path)[0] + PROFILE_EXT
    info = l3d.resolve_lut3d_path_info(
        _FakeWorker(),
        lut3d_path,
        **_base_kwargs(current_devlink_profile=devlink),
    )
    assert info.devlink_changed is False
    assert info.mr_option_changed is False


def test_resolve_lut3d_path_info_uses_default_path_when_none():
    worker = _FakeWorker()
    l3d.resolve_lut3d_path_info(worker, None, **_base_kwargs())
    assert worker.calls == [(None, True, True)]


@pytest.mark.parametrize("trc", ["smpte2084.hardclip", "smpte2084.rolloffclip", "hlg"])
def test_resolve_lut3d_path_info_simulation_profile_applied_when_file_exists(
    tmp_path, trc
):
    lut3d_path = str(tmp_path / "profile.cube")
    candidate = tmp_path / "lut3d_input.icm"
    candidate.write_bytes(b"icc")
    info = l3d.resolve_lut3d_path_info(
        _FakeWorker(),
        lut3d_path,
        **_base_kwargs(
            set_mr_sim_profile=True,
            tab_enabled=True,
            trc=trc,
            input_profile=str(tmp_path / "input.icm"),
        ),
    )
    assert info.simulation_profile == str(candidate)
    assert info.mr_option_changed is True


def test_resolve_lut3d_path_info_simulation_profile_via_whitepoint_x():
    lut3d_path = "/does/not/matter.cube"
    info = l3d.resolve_lut3d_path_info(
        _FakeWorker(),
        lut3d_path,
        **_base_kwargs(set_mr_sim_profile=True, tab_enabled=True, whitepoint_x=0.3128),
    )
    # No real candidate file exists at this path, so nothing is applied, but
    # the gate itself (trc doesn't qualify, whitepoint_x does) must be reached
    # without error.
    assert info.simulation_profile is None


def test_resolve_lut3d_path_info_simulation_profile_skipped_when_not_requested(
    tmp_path,
):
    lut3d_path = str(tmp_path / "profile.cube")
    (tmp_path / "lut3d_input.icm").write_bytes(b"icc")
    info = l3d.resolve_lut3d_path_info(
        _FakeWorker(),
        lut3d_path,
        **_base_kwargs(
            set_mr_sim_profile=False,
            tab_enabled=True,
            trc="hlg",
            input_profile=str(tmp_path / "input.icm"),
        ),
    )
    assert info.simulation_profile is None


def test_resolve_lut3d_path_info_simulation_profile_skipped_when_tab_disabled(
    tmp_path,
):
    lut3d_path = str(tmp_path / "profile.cube")
    (tmp_path / "lut3d_input.icm").write_bytes(b"icc")
    info = l3d.resolve_lut3d_path_info(
        _FakeWorker(),
        lut3d_path,
        **_base_kwargs(
            set_mr_sim_profile=True,
            tab_enabled=False,
            trc="hlg",
            input_profile=str(tmp_path / "input.icm"),
        ),
    )
    assert info.simulation_profile is None


def test_resolve_lut3d_path_info_simulation_profile_skipped_when_trc_not_hdr(
    tmp_path,
):
    lut3d_path = str(tmp_path / "profile.cube")
    (tmp_path / "lut3d_input.icm").write_bytes(b"icc")
    info = l3d.resolve_lut3d_path_info(
        _FakeWorker(),
        lut3d_path,
        **_base_kwargs(
            set_mr_sim_profile=True,
            tab_enabled=True,
            trc="gamma2.2",
            input_profile=str(tmp_path / "input.icm"),
        ),
    )
    assert info.simulation_profile is None


def test_resolve_lut3d_path_info_simulation_profile_skipped_when_file_missing(
    tmp_path,
):
    lut3d_path = str(tmp_path / "profile.cube")
    info = l3d.resolve_lut3d_path_info(
        _FakeWorker(),
        lut3d_path,
        **_base_kwargs(
            set_mr_sim_profile=True,
            tab_enabled=True,
            trc="hlg",
            input_profile=str(tmp_path / "input.icm"),
        ),
    )
    assert info.simulation_profile is None


def test_resolve_lut3d_path_info_simulation_profile_skipped_when_unchanged(tmp_path):
    lut3d_path = str(tmp_path / "profile.cube")
    candidate = tmp_path / "lut3d_input.icm"
    candidate.write_bytes(b"icc")
    info = l3d.resolve_lut3d_path_info(
        _FakeWorker(),
        lut3d_path,
        **_base_kwargs(
            current_devlink_profile=os.path.splitext(lut3d_path)[0] + PROFILE_EXT,
            current_simulation_profile=str(candidate),
            set_mr_sim_profile=True,
            tab_enabled=True,
            trc="hlg",
            input_profile=str(tmp_path / "input.icm"),
        ),
    )
    assert info.simulation_profile is None
    assert info.mr_option_changed is False
