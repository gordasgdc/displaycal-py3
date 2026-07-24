"""Toolkit-neutral logic behind the 3D LUT settings tab.

wx implements this behavior as ``LUT3DMixin`` (``wx_lut_3d_frame.py``), shared
between the standalone ``LUT3DFrame`` tool window (``3dlut.xrc``) and the 3D
LUT tab embedded directly in ``MainFrame`` (``main.xrc``'s
``lut3d_settings_panel``). This module ports only the pieces that embedded tab
actually exercises: the mixin's ``isinstance(self, LUT3DFrame)`` branches are
always False here and ``hasattr(self, "lut3d_create_cb")`` is always True, so
those branches are baked in rather than reproduced as branches.

Also includes :func:`resolve_create_trc_gamma` and
:func:`content_rgb_space_for_creation`, the two branches of
``LUT3DMixin.lut3d_create_producer`` with actual logic worth sharing between
the embedded tab and the standalone 3D LUT maker's own (independently
written) ``create_3dlut``; the rest of that method is a flat, untestable
config-to-kwarg mapping and is built inline by each caller.

Also includes :func:`install_via_copy`, the toolkit-neutral half of
``LUT3DMixin.lut3d_create_handler``'s ``copy_from_path`` branch (the
"copy an already-created 3D LUT to its install location" flow used by both
the manual create button and the ``3dlut.create`` auto-chain's install
offer): eeColor's 6 companion 1D-LUT files, and ReShade's folder-layout
detection + shader patching. The madVR/Prisma **API** install path
(``Worker.install_3dlut``) is not wrapped here since it needs a live
``madtpg``/pattern-generator connection and the (still unported)
``setup_patterngenerator`` Prisma-host-prompt / madTPG-connect-wait dialogs;
:mod:`DisplayCAL.ui.main_window` shows a not-yet-available notice for that
branch instead, matching the CCXX-info-button precedent.

Not reproduced: ``XYZbpout`` (the last measured/loaded profile's output black
point) which wx factors into ``lut3d_show_trc_controls``'s black-output-offset
row visibility; this port treats it as always ``[0, 0, 0]`` (its value before
any profile has been measured), so that row's visibility reduces to just
``3dlut.create``; and the dead ``MasterEffect`` sub-branch of the ReShade copy
flow (guarded upstream by a hardcoded ``use_mclut3d = False``, so it can never
run).
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass

from DisplayCAL import colormath
from DisplayCAL.argyll import argyll_version_at_least
from DisplayCAL.argyll_names import VIDEO_ENCODINGS
from DisplayCAL.config import PROFILE_EXT, get_data_path
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.meta import VERSION_STRING
from DisplayCAL.util_os import islink, readlink
from DisplayCAL.util_str import strtr
from DisplayCAL.worker import Worker

#: 3D LUT tone curve combo rows, in UI order (``lut3d_trc_ctrl``'s ``main.xrc``
#: population order, distinct from ``config.VALID_VALUES["3dlut.trc"]``'s
#: alphabetic-ish order).
TRC_COMBO_TRC_VALUES = (
    "gamma2.2",
    "bt1886",
    "smpte2084.hardclip",
    "smpte2084.rolloffclip",
    "hlg",
    "customgamma",
)

#: TRC gamma type combo rows -> ``3dlut.trc_gamma_type`` value.
TRC_GAMMA_TYPE_AB = {0: "b", 1: "B"}
TRC_GAMMA_TYPE_BA = {"b": 0, "B": 1}

#: Content colorspace combo rows (the last row, "custom", has no fixed
#: primaries and is appended by the caller).
CONTENT_COLORSPACE_NAMES = ("Rec. 2020", "DCI P3 D65", "Rec. 709")

#: 3D LUT formats that force a specific input/output video encoding.
_ENCODING_OVERRIDE_FORMATS = ("dcl", "eeColor", "madVR", "ReShade")

#: 3D LUT formats that force a specific grid size.
_SIZE_OVERRIDE_FORMATS = ("dcl", "eeColor", "madVR", "mga", "ReShade")

#: Reference diffuse white used for the BT.2390 roll-off preview (cd/m2).
_DIFFUSE_REF_CDM2 = 94.37844


def trc_selection_side_effects(index: int) -> dict[str, object]:
    """Return the config updates ``lut3d_trc_ctrl``'s selection implies.

    Mirrors ``LUT3DMixin.lut3d_trc_ctrl_handler`` (minus the custom-gamma
    focus/select-all UI action, which has no config side effect).

    Args:
        index (int): The selected combo row (0-5, see
            :data:`TRC_COMBO_TRC_VALUES`).

    Returns:
        dict[str, object]: Config keys to set, in application order.
    """
    if index == 0:  # Pure power gamma 2.2
        return {
            "3dlut.trc_gamma": 2.2,
            "3dlut.trc_gamma_type": "b",
            "3dlut.trc_output_offset": 1.0,
            "3dlut.trc": "gamma2.2",
        }
    if index == 1:  # BT.1886
        return {
            "3dlut.trc_gamma": 2.4,
            "3dlut.trc_gamma_type": "B",
            "3dlut.trc_output_offset": 0.0,
            "3dlut.trc": "bt1886",
        }
    if index == 2:  # SMPTE 2084, hard clip
        return {
            "3dlut.trc_output_offset": 0.0,
            "3dlut.trc": "smpte2084.hardclip",
            "3dlut.hdr_maxmll": 10000,
        }
    if index == 3:  # SMPTE 2084, roll-off clip
        return {
            "3dlut.trc_output_offset": 0.0,
            "3dlut.trc": "smpte2084.rolloffclip",
            "3dlut.hdr_maxmll": 10000,
        }
    if index == 4:  # HLG
        return {"3dlut.trc_output_offset": 0.0, "3dlut.trc": "hlg"}
    return {"3dlut.trc": "customgamma"}  # Custom


def resolve_trc_selection(
    trc: object, trc_gamma_type: str, trc_output_offset: object, trc_gamma: object
) -> tuple[int, str]:
    """Return the TRC combo row implied by the stored config.

    Mirrors ``LUT3DMixin.lut3d_update_trc_control``, including its
    self-correcting ``3dlut.trc`` rewrites (e.g. a hand-edited config with
    ``trc_gamma_type=B``, ``trc_output_offset=0`` and ``trc_gamma=2.4`` is
    recognized and relabeled as ``"bt1886"``).

    Returns:
        tuple[int, str]: ``(combo row, corrected "3dlut.trc" value)``.
    """
    trc = str(trc)
    if trc.startswith("smpte2084"):
        return (2 if trc == "smpte2084.hardclip" else 3), trc
    if trc == "hlg":
        return 4, "hlg"
    if trc_gamma_type == "B" and trc_output_offset == 0 and trc_gamma == 2.4:
        return 1, "bt1886"
    if trc_gamma_type == "b" and trc_output_offset == 1 and trc_gamma == 2.2:
        return 0, "gamma2.2"
    return 5, "customgamma"


@dataclass(frozen=True)
class Lut3dTrcVisibility:
    """Row visibility for the TRC/HDR block of the 3D LUT tab.

    Mirrors ``LUT3DMixin.lut3d_show_trc_controls`` specialized for the
    ``MainFrame``-embedded tab (see this module's docstring).
    """

    trc_row: bool
    trc_gamma: bool
    trc_gamma_type: bool
    hdr_peak_luminance: bool
    hdr_minmll: bool
    hdr_maxmll: bool
    hdr_maxmll_alt_clip: bool
    hdr_diffuse_white: bool
    hdr_ambient_luminance: bool
    hdr_system_gamma: bool
    hdr_sat_hue: bool
    content_colorspace: bool
    content_colorspace_xy: bool
    black_output_offset: bool
    hdr_display: bool


def compute_trc_visibility(
    *,
    trc: str,
    trc_format: str,
    argyll_version: str,
    show_advanced_options: bool,
    lut3d_create: bool,
    hdr_maxmll: float,
    content_colorspace_is_custom: bool,
) -> Lut3dTrcVisibility:
    """Compute TRC/HDR row visibility for the current settings.

    Args:
        trc (str): Stored ``3dlut.trc`` value.
        trc_format (str): Stored ``3dlut.format`` value (only ``"madVR"``
            matters here, for the HDR-display row).
        argyll_version (str): ``getcfg("argyll.version")``.
        show_advanced_options (bool): The Options-menu toggle.
        lut3d_create (bool): Stored ``3dlut.create`` value.
        hdr_maxmll (float): Stored ``3dlut.hdr_maxmll`` value (gates the
            alt-clip checkbox once it's already at the 10000 ceiling).
        content_colorspace_is_custom (bool): Whether the content-colorspace
            combo's selection is its trailing "custom" row.
    """
    base_show = argyll_version_at_least(argyll_version, "1.6")
    smpte2084 = trc.startswith("smpte2084")
    smpte2084r = trc == "smpte2084.rolloffclip"
    hlg = trc == "hlg"
    hdr = smpte2084 or hlg

    gamma_show = base_show and (trc == "customgamma" or show_advanced_options)
    showcc = (smpte2084r or hlg) and show_advanced_options
    hdr_maxmll_shown = gamma_show and smpte2084r

    trailing_pre = (gamma_show or smpte2084) and not hlg
    trailing_show = trailing_pre and lut3d_create

    return Lut3dTrcVisibility(
        trc_row=base_show,
        trc_gamma=gamma_show and not hdr,
        trc_gamma_type=trailing_show and not hdr,
        hdr_peak_luminance=smpte2084,
        hdr_minmll=gamma_show and smpte2084,
        hdr_maxmll=hdr_maxmll_shown,
        hdr_maxmll_alt_clip=hdr_maxmll_shown and hdr_maxmll < 10000,
        hdr_diffuse_white=gamma_show and smpte2084r,
        hdr_ambient_luminance=gamma_show and hlg,
        hdr_system_gamma=gamma_show and hlg,
        hdr_sat_hue=gamma_show and smpte2084r,
        content_colorspace=showcc,
        content_colorspace_xy=showcc and content_colorspace_is_custom,
        black_output_offset=trailing_show,
        hdr_display=smpte2084 and trc_format == "madVR",
    )


def diffuse_white_cdm2(
    peak_luminance: float, minmll: float, maxmll: float, hdr_maxmll_alt_clip: object
) -> tuple[float, bool]:
    """Return the BT.2390 roll-off preview for the diffuse-white readout.

    Mirrors ``LUT3DMixin.lut3d_hdr_update_diffuse_white``.

    Returns:
        tuple[float, bool]: ``(diffuse white cd/m2, below_reference)``; the
            caller colors the readout red when ``below_reference`` is True
            (roll-off darkened the reference diffuse white), green otherwise.
    """
    bt2390 = colormath.BT2390(
        0, peak_luminance, minmll, maxmll, bool(hdr_maxmll_alt_clip)
    )
    diffuse_pq = colormath.special_pow(_DIFFUSE_REF_CDM2 / 10000, 1.0 / -2084)
    diffuse_tgt_cdm2 = colormath.special_pow(bt2390.apply(diffuse_pq), -2084) * 10000
    return diffuse_tgt_cdm2, diffuse_tgt_cdm2 < _DIFFUSE_REF_CDM2


def hlg_system_gamma(ambient_cdm2: float) -> float:
    """Return the HLG system gamma for the given ambient luminance (BT.2390-4)."""
    return colormath.HLG(ambient_cdm2=ambient_cdm2).gamma


def content_colorspace_xy(rgb_space_name: str) -> dict[str, float]:
    """Return the 8 primaries/whitepoint xy config values for a named RGB space.

    Mirrors the non-custom branch of
    ``LUT3DMixin.lut3d_content_colorspace_handler``.
    """
    rgb_space = colormath.get_rgb_space(rgb_space_name)
    result: dict[str, float] = {}
    for i, color in enumerate(("white", "red", "green", "blue")):
        xyy = colormath.XYZ2xyY(*rgb_space[1]) if i == 0 else rgb_space[2:][i - 1]
        for j, coord in enumerate("xy"):
            result[f"3dlut.content.colorspace.{color}.{coord}"] = round(xyy[j], 4)
    return result


def resolve_content_colorspace_selection(
    colors_xy: dict[str, float], names: tuple[str, ...] = CONTENT_COLORSPACE_NAMES
) -> int:
    """Return the content-colorspace combo row matching the stored xy values.

    Mirrors the trailing part of ``LUT3DMixin.lut3d_update_trc_controls``.
    The last row (``len(names)``) means "custom" (no exact match).
    """
    content_colors = [
        round(colors_xy[f"3dlut.content.colorspace.{color}.{coord}"], 4)
        for color in ("red", "green", "blue", "white")
        for coord in "xy"
    ]
    name = colormath.find_primaries_wp_xy_rgb_space_name(content_colors, list(names))
    return names.index(name) if name else len(names)


def lut3d_size_snap(file_format: str, size: int) -> int:
    """Snap ``size`` to a value the given format actually supports.

    Mirrors ``LUT3DMixin.lut3d_snap_size``.
    """
    if file_format == "mga" and size not in (17, 33):
        return 17 if size < 33 else 33
    if file_format == "ReShade" and size not in (16, 32, 64):
        if size < 32:
            return 16
        return 32 if size < 64 else 64
    return size


def lut3d_format_side_effects(
    old_format: str, new_format: str, cfg: dict[str, object]
) -> dict[str, object]:
    """Return the config updates switching 3D LUT format implies.

    Mirrors ``LUT3DMixin.lut3d_format_ctrl_handler`` (minus the widget
    ``SetSelection`` calls, which the caller performs after applying these).

    Args:
        old_format (str): The format being switched away from.
        new_format (str): The newly selected format.
        cfg (dict[str, object]): Current values for
            ``3dlut.encoding.input(.backup)``, ``3dlut.encoding.output(.backup)``,
            ``3dlut.size(.backup)`` and ``3dlut.bitdepth.output``.

    Returns:
        dict[str, object]: Config keys to set, in application order.
    """
    updates: dict[str, object] = {}

    if old_format in _ENCODING_OVERRIDE_FORMATS and new_format not in (
        _ENCODING_OVERRIDE_FORMATS
    ):
        updates["3dlut.encoding.input"] = cfg["3dlut.encoding.input.backup"]
        updates["3dlut.encoding.output"] = cfg["3dlut.encoding.output.backup"]
    if old_format in _SIZE_OVERRIDE_FORMATS:
        updates["3dlut.size"] = cfg["3dlut.size.backup"]
    if (
        old_format not in _ENCODING_OVERRIDE_FORMATS
        and new_format in _ENCODING_OVERRIDE_FORMATS
    ):
        updates["3dlut.encoding.input.backup"] = updates.get(
            "3dlut.encoding.input", cfg["3dlut.encoding.input"]
        )
        updates["3dlut.encoding.output.backup"] = updates.get(
            "3dlut.encoding.output", cfg["3dlut.encoding.output"]
        )

    updates["3dlut.format"] = new_format

    if new_format in _SIZE_OVERRIDE_FORMATS:
        updates["3dlut.size.backup"] = updates.get("3dlut.size", cfg["3dlut.size"])

    if new_format == "eeColor":
        if cfg["3dlut.encoding.input"] not in ("t", "T"):
            updates["3dlut.encoding.input"] = "t"
        updates["3dlut.encoding.output"] = "t"
        updates["3dlut.size"] = 65
    elif new_format == "mga":
        updates["3dlut.bitdepth.output"] = 16
    elif new_format == "madVR":
        if cfg["3dlut.encoding.input"] not in ("t", "T"):
            updates["3dlut.encoding.input"] = "t"
        updates["3dlut.encoding.output"] = "t"
        updates["3dlut.size"] = 65
    elif new_format in ("png", "ReShade"):
        if new_format == "ReShade":
            updates["3dlut.encoding.input"] = "n"
            updates["3dlut.encoding.output"] = "n"
            updates["3dlut.bitdepth.output"] = 8
        elif cfg["3dlut.bitdepth.output"] not in (8, 16):
            updates["3dlut.bitdepth.output"] = 8
    elif new_format == "dcl":
        updates["3dlut.encoding.input"] = "n"
        updates["3dlut.encoding.output"] = "n"
        updates["3dlut.size"] = 33
        updates["3dlut.bitdepth.output"] = 12

    size = updates.get("3dlut.size", cfg["3dlut.size"])
    snapped = lut3d_size_snap(new_format, size)
    if snapped != size:
        updates["3dlut.size"] = snapped

    return updates


def lut3d_encoding_codes(
    file_format: str, argyll_version: str
) -> tuple[list[str], list[str]]:
    """Return the ``(input codes, output codes)`` valid for ``file_format``.

    Mirrors ``LUT3DMixin.lut3d_setup_encoding_ctrl``.
    """
    if file_format == "madVR":
        encodings = ["t"]
    else:
        encodings = ["n"] if file_format == "dcl" else list(VIDEO_ENCODINGS)
    if (
        argyll_version_at_least(argyll_version, "1.7")
        and argyll_version != "1.7.0_beta"
        and file_format != "dcl"
    ):
        # Argyll 1.7 beta 3 (2015-04-02) added clip WTW on input TV encoding.
        encodings.insert(2, "T")
    # collink: xvYCC output encoding is not supported.
    output_encodings = [e for e in encodings if e not in ("T", "x", "X")]
    return encodings, output_encodings


def lut3d_encoding_controls_visible(argyll_version: str) -> bool:
    """Return whether the encoding input/output rows should be shown.

    Mirrors ``LUT3DMixin.lut3d_show_encoding_controls``, whose two-clause
    Argyll-version check reduces to a plain ``>= "1.6"`` (the "exclude Argyll
    1.7.0 beta 3" clause has no effect on the result: every version it would
    exclude from the first OR-clause still satisfies the second).
    """
    return argyll_version_at_least(argyll_version, "1.6")


def lut3d_bitdepth_controls_visible(file_format: str) -> tuple[bool, bool]:
    """Return ``(input row visible, output row visible)``.

    Mirrors ``LUT3DMixin.lut3d_show_bitdepth_controls``.
    """
    return file_format == "3dl", file_format in ("3dl", "png")


def resolve_create_trc_gamma(
    *,
    apply_trc: bool,
    trc: str,
    trc_gamma: float,
    has_trc_apply_toggle: bool = False,
) -> float | str | None:
    """Return the ``trc_gamma`` kwarg for ``Worker.create_3dlut``.

    Mirrors ``LUT3DMixin.lut3d_create_producer``'s ``trc_gamma`` branch,
    gated on ``getcfg("3dlut.apply_trc") or not hasattr(self,
    "lut3d_trc_apply_none_ctrl")``. The embedded ``MainFrame`` tab has no such
    toggle (``has_trc_apply_toggle=False``), so wx always applies the
    configured TRC there; the standalone 3D LUT maker has the toggle and
    additionally honors ``3dlut.apply_trc``.
    """
    if apply_trc or not has_trc_apply_toggle:
        if trc.startswith("smpte2084") or trc == "hlg":
            return trc
        return trc_gamma
    return None


def content_rgb_space_for_creation(colors_xy: dict[str, float]):
    """Build the ``content_rgb_space`` kwarg for ``Worker.create_3dlut``.

    Mirrors the ``content_rgb_space`` construction shared by
    ``LUT3DMixin.lut3d_create_producer`` and the standalone 3D LUT maker's own
    ``create_3dlut``. ``colors_xy`` uses the same
    ``3dlut.content.colorspace.<color>.<coord>`` keys as
    :func:`content_colorspace_xy`.
    """
    space = [1.0, [], [], [], []]
    for i, color in enumerate(("white", "red", "green", "blue")):
        for coord in "xy":
            space[i + 1].append(colors_xy[f"3dlut.content.colorspace.{color}.{coord}"])
        space[i + 1].append(1.0)
    space[1] = colormath.xyY2XYZ(*space[1])
    return colormath.get_rgb_space(space)


def resolve_creation_whitepoint(
    x: float | None, y: float | None
) -> tuple[float, float, float] | None:
    """Return the ``XYZwp`` kwarg for ``Worker.create_3dlut``.

    Mirrors ``LUT3DMixin.lut3d_create_producer``'s ``XYZwp`` branch, only
    taken outside the standalone 3D LUT maker (this port's only caller).
    ``x``/``y`` are ``getcfg("3dlut.whitepoint.x"/"y", False)`` (``False``
    fallback, so an unset value comes back falsy rather than the class
    default); this Qt port never sets either key (no ambient/visual
    whitepoint-measurement flow yet), so this currently always returns
    ``None``, but stays ready for when one lands.
    """
    if not x or not y:
        return None
    return colormath.xyY2XYZ(x, y)


def install_via_copy(
    file_format: str, size: int, bitdepth_output: int, src_path: str, dst_path: str
) -> list[str]:
    """Copy an already-created 3D LUT file to its install location.

    Faithful port of the ``copy_from_path`` branch of
    ``LUT3DMixin.lut3d_create_handler`` (``wx_lut_3d_frame.py:880-1009``),
    minus the dead ``MasterEffect`` sub-branch. Two formats need more than a
    single file copy:

    - ``eeColor``: also copies the 6 companion 1D-LUT ``.txt`` files
      (``-first1d{red,green,blue}.txt`` / ``-second1d...``) that sit next to
      ``src_path``, if present.
    - ``ReShade``: detects the ReShade install layout at ``dst_path``'s
      directory (>=3.x ``reshade-shaders/{Textures,Shaders}`` split, or <3.0's
      ``ReShade.fx`` -- following it if it's a symlink -- patched in place to
      ``#include`` the generated shader) and writes ``ColorLookupTable.fx``
      (templated from the bundled ``ColorLookupTable.fx`` data file) next to
      the copied texture.

    Args:
        file_format: ``3dlut.format`` at creation time.
        size: ``3dlut.size`` (only used for the ReShade shader template).
        bitdepth_output: ``3dlut.bitdepth.output`` (ditto).
        src_path: Path to the already-created 3D LUT file.
        dst_path: The user-chosen destination (for ReShade, the target
            texture path inside the chosen folder).

    Returns:
        The destination paths actually written, in copy order (the first
        entry is always the primary LUT file's final path, which may differ
        from ``dst_path`` for ReShade once its folder layout is resolved).

    Raises:
        FileNotFoundError: If the bundled ``ColorLookupTable.fx`` template is
            missing (a packaging error, not a user error).
    """
    src_paths = [src_path]
    dst_paths = [dst_path]
    if file_format == "eeColor":
        src_name = os.path.splitext(src_path)[0]
        dst_name = os.path.splitext(dst_path)[0]
        for part in ("first", "second"):
            for channel in ("blue", "green", "red"):
                companion = f"{src_name}-{part}1d{channel}.txt"
                if os.path.isfile(companion):
                    src_paths.append(companion)
                    dst_paths.append(f"{dst_name}-{part}1d{channel}.txt")
    elif file_format == "ReShade":
        dst_dir = os.path.dirname(dst_path)
        clut_fx_path = get_data_path("ColorLookupTable.fx")
        if not clut_fx_path:
            raise FileNotFoundError("ColorLookupTable.fx")
        with open(clut_fx_path, "rb") as clut_fx_file:
            clut_fx = clut_fx_file.read()
        clut_fx = strtr(
            clut_fx,
            {
                "${VERSION}": VERSION_STRING,
                "${WIDTH}": str(size**2),
                "${HEIGHT}": str(size),
                "${FORMAT}": f"RGBA{bitdepth_output}",
            },
        )
        reshade_shaders = os.path.join(dst_dir, "reshade-shaders")
        if os.path.isdir(reshade_shaders):
            # ReShade >= 3.x with default shaders
            dst_path = os.path.join(
                reshade_shaders, "Textures", os.path.basename(dst_path)
            )
            dst_paths = [dst_path]
            dst_dir = os.path.join(reshade_shaders, "Shaders")
        else:
            reshade_fx_path = os.path.join(dst_dir, "ReShade.fx")
            if islink(reshade_fx_path):
                # ReShade < 3.0
                reshade_fx_path = readlink(reshade_fx_path)
                dst_dir = os.path.dirname(reshade_fx_path)
                dst_path = os.path.join(dst_dir, os.path.basename(dst_path))
                dst_paths = [dst_path]
            if os.path.isfile(reshade_fx_path):
                # ReShade < 3.0: alter existing ReShade.fx
                with open(reshade_fx_path, "rb") as reshade_fx_file:
                    reshade_fx = reshade_fx_file.read()
                # Remove existing shader include
                reshade_fx = re.sub(
                    rb"[ \t]*//\s*Automatically\s+\S+\s+by\s+"
                    + re.escape(APPNAME.encode())
                    + rb"\s+.+[ \t]*\r?\n?",
                    b"",
                    reshade_fx,
                )
                reshade_fx = re.sub(
                    rb'[ \t]*#include\s+"ColorLookupTable.fx"[ \t]*\r?\n?',
                    b"",
                    reshade_fx,
                ).rstrip(b"\r\n")
                reshade_fx += (
                    f"{os.linesep * 2}// Automatically added by "
                    f"{APPNAME} {VERSION_STRING}{os.linesep}"
                ).encode()
                reshade_fx += (f'#include "ColorLookupTable.fx"{os.linesep}').encode()
                with open(reshade_fx_path, "wb") as reshade_fx_file:
                    reshade_fx_file.write(reshade_fx)
        clut_fx_dst = os.path.join(dst_dir, "ColorLookupTable.fx")
        with open(clut_fx_dst, "wb") as clut_fx_file:
            clut_fx_file.write(clut_fx)
    for src, dst in zip(src_paths, dst_paths):
        shutil.copyfile(src, dst)
    return dst_paths


@dataclass
class Lut3dPathInfo:
    """Result of :func:`resolve_lut3d_path_info`."""

    #: The 3D LUT's own path, mirroring wx's ``self.lut3d_path``.
    lut3d_path: str
    #: The devicelink-profile path derived from ``lut3d_path``.
    devlink_profile: str
    #: True if ``devlink_profile`` differs from the caller's current
    #: ``measurement_report.devlink_profile`` (caller should ``setcfg`` it).
    devlink_changed: bool
    #: The simulation-profile path to apply, or ``None`` if unchanged /
    #: not applicable (caller should ``setcfg`` it when not ``None``).
    simulation_profile: str | None = None

    @property
    def mr_option_changed(self) -> bool:
        """True if either measurement-report profile option needs updating."""
        return self.devlink_changed or self.simulation_profile is not None


def resolve_lut3d_path_info(
    worker: Worker,
    path: str | None = None,
    *,
    set_mr_sim_profile: bool = True,
    current_devlink_profile: str | None,
    current_simulation_profile: str | None,
    tab_enabled: bool,
    trc: str,
    whitepoint_x: float | bool,
    input_profile: str,
) -> Lut3dPathInfo:
    """Derive the 3D LUT path and its dependent measurement-report profiles.

    Faithful port of ``MainFrame.lut3d_set_path`` (``display_cal.py:6544-6584``),
    minus its trailing ``self.mr_update_controls()`` UI refresh (left to the
    caller, which only needs to run it when :attr:`Lut3dPathInfo
    .mr_option_changed` is true).

    Args:
        worker: The ``Worker`` used to derive filenames
            (``Worker.lut3d_get_filename``).
        path: Explicit base path for the 3D LUT filename, or ``None`` to use
            ``calibration.file`` (``Worker.lut3d_get_filename``'s own default).
        set_mr_sim_profile: Whether to also derive the measurement-report
            simulation profile (``False`` for the profile-build call site,
            which hasn't written the profile file yet).
        current_devlink_profile: ``getcfg("measurement_report.devlink_profile")``.
        current_simulation_profile: ``getcfg("measurement_report.simulation_profile")``.
        tab_enabled: ``getcfg("3dlut.tab.enable")``.
        trc: ``getcfg("3dlut.trc")``.
        whitepoint_x: ``getcfg("3dlut.whitepoint.x", False)``.
        input_profile: ``getcfg("3dlut.input.profile")``.

    Returns:
        Lut3dPathInfo: What changed, for the caller to apply via ``setcfg``.
    """
    lut3d_path = worker.lut3d_get_filename(path)
    devlink_profile = os.path.splitext(lut3d_path)[0] + PROFILE_EXT
    devlink_changed = devlink_profile != current_devlink_profile
    simulation_profile = None
    if (
        set_mr_sim_profile
        and tab_enabled
        and (trc.startswith("smpte2084") or trc == "hlg" or whitepoint_x)
    ):
        # Use 3D LUT input profile, but only its filename (it lives in the
        # same directory as the 3D LUT itself once installed).
        cfgfn, cfgext = os.path.splitext(os.path.basename(input_profile))
        lut3d_fn = worker.lut3d_get_filename(cfgfn, False, False)
        candidate = os.path.join(os.path.dirname(lut3d_path), lut3d_fn + cfgext)
        if candidate != current_simulation_profile and os.path.isfile(candidate):
            simulation_profile = candidate
    return Lut3dPathInfo(
        lut3d_path=lut3d_path,
        devlink_profile=devlink_profile,
        devlink_changed=devlink_changed,
        simulation_profile=simulation_profile,
    )
