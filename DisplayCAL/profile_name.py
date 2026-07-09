"""Toolkit-neutral helpers for the Profiling tab's testchart/profile-name controls.

Pure pieces lifted out of ``MainFrame`` (``display_cal.py``): the profile-name
placeholder expansion (``create_profile_name``), profile-name validation and
sanitizing (``check_profile_name`` / ``profile_name_ctrl_handler``), the
testchart file listing (``get_testchart_names``), the auto-optimize
patch-count/profile-type suggestion (``testchart_patches_amount_ctrl_handler``),
and the estimated-measurement-time computation
(``wx_report_frame.ReportFrame.update_estimated_measurement_time``). None of
this touches a GUI toolkit, so both the still-shipping wx path and the Qt
Profiling tab (:mod:`DisplayCAL.ui.main_window`) can share it.

Also holds the pure path-resolution/gating halves of
``MainFrame.set_default_testchart`` (:func:`resolve_default_testchart`) and
``MainFrame.check_testchart_patches_amount``
(:func:`testchart_recommendation_auto_optimize`) -- both leave the actual
confirm dialog / ``set_testchart`` application to the caller.

Deliberately not reproduced here (documented, not silently dropped): the
legacy testchart-editor-refresh side effects of ``set_testchart`` -- that's
tool-window shaped, not pure data, and the testchart editor itself
(``TestchartEditor``) isn't ported to Qt yet.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from time import gmtime, strftime
from zlib import crc32

from DisplayCAL import colormath, config
from DisplayCAL import localization as lang
from DisplayCAL.argyll_cgats import ti3_to_ti1, verify_ti1_rgb_xyz
from DisplayCAL.cgats import CGATS
from DisplayCAL.config import DEFAULTS, RES_FILES, get_data_path, getcfg
from DisplayCAL.icc_profile import ICCProfile
from DisplayCAL.util_list import natsort
from DisplayCAL.util_os import listdir_re
from DisplayCAL.util_str import strtr

#: Testchart/profile file extensions recognized by the testchart chooser.
TESTCHART_FILE_EXTENSIONS = (".icc", ".icm", ".ti1", ".ti3")


@dataclass
class ProfileNameContext:
    """Resolved, toolkit-neutral inputs for :func:`expand_profile_name`.

    Each field is the already-resolved equivalent of a wx widget read in
    ``MainFrame.create_profile_name`` (e.g. ``whitepoint`` is the return value
    of ``get_whitepoint()``, not a widget). Callers build this from live Qt
    control state before expanding.
    """

    computer_name: str | None
    display_win32_short: str | None
    display_win32: str | None
    display_short: str | None
    display: str | None
    edid: dict
    is_virtual_display: bool
    display_number: int
    instrument: str | None
    measurement_mode: str | None
    trc: str
    trc_type: str
    do_cal: bool
    whitepoint: str | None
    whitepoint_locus: str
    luminance: str | None
    black_luminance: str | None
    ambient: str | None
    black_output_offset: str
    black_point_correction: str
    black_point_correction_auto: bool
    black_point_rate: str | None
    calibration_quality: str
    profile_quality: str
    profile_type: str
    testchart_patches_amount: str


def _measurement_mode_label(measurement_mode: str | None) -> str:
    """Return the ``%im`` replacement text for a measurement-mode code."""
    if not measurement_mode:
        return lang.getstr("default")
    mode = ""
    if "c" in measurement_mode:
        mode += lang.getstr("measurement_mode.refresh")
    elif "l" in measurement_mode:
        mode += lang.getstr("measurement_mode.lcd")
    if "p" in measurement_mode:
        if mode:
            mode += "-"
        mode += lang.getstr("projector")
    if "V" in measurement_mode:
        if mode:
            mode += "-"
        mode += lang.getstr("measurement_mode.adaptive")
    if "H" in measurement_mode:
        if mode:
            mode += "-"
        mode += lang.getstr("measurement_mode.highres")
    return mode


class ProfileType(str, Enum):
    """Profile type codes for modern Argyll (>= 1.1.0 RC4).

    Matches the wx ordering in ``update_profile_type_ctrl_items``. Mixing in
    ``str`` means a member compares and serializes as its plain ``profile.type``
    config letter (e.g. ``ProfileType.LAB_LUT == "l"`` and
    ``setcfg("profile.type", ProfileType.LAB_LUT)`` stores ``"l"``), so it's a
    drop-in replacement anywhere a raw config-value string was used.
    """

    XYZ_LUT_MATRIX = ("X", "profile.type.lut_matrix.xyz", "XYZLUT+MTX")
    XYZ_LUT = ("x", "profile.type.lut.xyz", "XYZLUT")
    LAB_LUT = ("l", "profile.type.lut.lab", "LabLUT")
    SHAPER_MATRIX = ("s", "profile.type.shaper_matrix", "3xCurve+MTX")
    SINGLE_SHAPER_MATRIX = ("S", "profile.type.single_shaper_matrix", "1xCurve+MTX")
    GAMMA_MATRIX = ("g", "profile.type.gamma_matrix", "3xGamma+MTX")
    SINGLE_GAMMA_MATRIX = ("G", "profile.type.single_gamma_matrix", "1xGamma+MTX")

    def __new__(cls, value: str, label_key: str, short_label: str) -> ProfileType:
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.label_key = label_key
        obj.short_label = short_label
        return obj

    def __str__(self) -> str:
        # Enum.__str__ would otherwise print "ProfileType.LAB_LUT" instead of
        # the plain config letter this is a drop-in replacement for.
        return self.value

    @classmethod
    def from_config_value(cls, value: object) -> ProfileType | None:
        """Return the member for ``value``, or ``None`` if it isn't one."""
        try:
            return cls(value)
        except ValueError:
            return None


#: ``(config value, label key)`` pairs, in combo-display order -- the shape
#: the Qt ``profile_type_ctrl`` combo (:mod:`DisplayCAL.ui.main_window`) and
#: wx's ``update_profile_type_ctrl_items`` both build their items from.
PROFILE_TYPES = tuple((member.value, member.label_key) for member in ProfileType)

_DATE_DIRECTIVES = (
    "a", "A", "b", "B", "d", "H", "I", "j", "m", "M", "p", "S", "U", "w", "W", "y", "Y",
)


def expand_profile_name(template: str, ctx: ProfileNameContext) -> str:
    """Expand ``%``-placeholders in a profile-name template.

    Faithful, toolkit-neutral port of ``MainFrame.create_profile_name``
    (minus the final ``make_argyll_compatible_path`` call, which the caller
    applies afterward exactly as wx's ``update_profile_name`` does).
    """
    profile_name = template

    if "%nn" in profile_name:
        profile_name = profile_name.replace("%nn", ctx.computer_name or "\0")
    if "%dnws" in profile_name:
        profile_name = profile_name.replace("%dnws", ctx.display_win32_short or "\0")
    if "%dnw" in profile_name:
        profile_name = profile_name.replace("%dnw", ctx.display_win32 or "\0")

    if "%ds" in profile_name:
        serial = ctx.edid.get("serial_ascii", hex(ctx.edid.get("serial_32", 0))[2:])
        if serial and serial not in ("0", "1010101", "fffffff"):
            profile_name = profile_name.replace("%ds", serial)
        else:
            profile_name = profile_name.replace("%ds", "\0")
    if "%crc32" in profile_name:
        raw_edid = ctx.edid.get("edid")
        if isinstance(raw_edid, str):
            raw_edid = raw_edid.encode("utf-8")
        if raw_edid:
            profile_name = profile_name.replace(
                "%crc32", "%X" % (crc32(raw_edid) & 0xFFFFFFFF)
            )
        else:
            profile_name = profile_name.replace("%crc32", "\0")

    if "%dns" in profile_name:
        profile_name = profile_name.replace("%dns", ctx.display_short or "\0")
    if "%dn" in profile_name:
        profile_name = profile_name.replace("%dn", ctx.display or "\0")

    output = "\0" if ctx.is_virtual_display else f"#{ctx.display_number}"
    profile_name = profile_name.replace("%out", output or "\0")

    if "%in" in profile_name:
        profile_name = profile_name.replace("%in", ctx.instrument or "\0")

    if "%im" in profile_name:
        profile_name = profile_name.replace(
            "%im", _measurement_mode_label(ctx.measurement_mode)
        )

    trc = ctx.trc
    do_cal = ctx.do_cal

    if "%wp" in profile_name:
        whitepoint = ctx.whitepoint
        if isinstance(whitepoint, str):
            if whitepoint.find(",") < 0:
                if ctx.whitepoint_locus == "t":
                    whitepoint = "D" + whitepoint
                else:
                    whitepoint += "K"
            else:
                whitepoint = "x ".join(whitepoint.split(",")) + "y"
        profile_name = profile_name.replace("%wp", (do_cal and whitepoint) or "\0")

    if "%cb" in profile_name:
        luminance = ctx.luminance
        profile_name = profile_name.replace(
            "%cb", "\0" if luminance is None or not do_cal else luminance + "cdm²"
        )

    if "%cB" in profile_name:
        black_luminance = ctx.black_luminance
        profile_name = profile_name.replace(
            "%cB",
            (
                "\0"
                if black_luminance is None or not do_cal
                else black_luminance + "cdm²"
            ),
        )

    black_output_offset = ctx.black_output_offset

    if "%cg" in profile_name and trc:
        bt1886 = (
            trc == "2.4" and ctx.trc_type == "G" and black_output_offset == "0"
        )
        if bt1886:
            trc = "Rec. 1886"
        elif trc not in ("l", "709", "s", "240"):
            if ctx.trc_type == "G":
                trc = "{} ({})".format(trc, lang.getstr("trc.type.absolute").lower())
        else:
            trc = strtr(
                trc, {"l": "L", "709": "Rec. 709", "s": "sRGB", "240": "SMPTE240M"}
            )
    profile_name = profile_name.replace("%cg", trc or "\0")

    if "%ca" in profile_name:
        ambient = ctx.ambient
        profile_name = profile_name.replace(
            "%ca", "\0" if ambient is None or not trc else ambient + "lx"
        )

    if "%cf" in profile_name:
        f = int(float(black_output_offset) * 100)
        profile_name = profile_name.replace("%cf", (f"{f:.0f}%") if trc else "\0")

    black_point_correction = ctx.black_point_correction

    if "%ck" in profile_name:
        k = int(float(black_point_correction) * 100)
        profile_name = profile_name.replace(
            "%ck",
            (
                (str(k) + "% " if 0 < k < 100 else "")
                + (lang.getstr("neutral") if k > 0 else "\0").lower()
                if trc and not ctx.black_point_correction_auto
                else "\0"
            ),
        )

    if "%cA" in profile_name:
        black_point_rate = ctx.black_point_rate
        if black_point_rate and float(black_point_correction) < 1 and trc:
            profile_name = profile_name.replace("%cA", black_point_rate)
        else:
            profile_name = profile_name.replace("%cA", "\0")

    if "%cq" in profile_name or "%pq" in profile_name:
        aspects = {
            "c": ctx.calibration_quality if trc else "",
            "p": ctx.profile_quality,
        }
        msgs = {"u": "VS", "h": "S", "m": "M", "l": "F", "v": "VF", "": "\0"}
        quality = {}
        if "%cq" in profile_name:
            quality["c"] = msgs[aspects["c"]]
        if "%pq" in profile_name:
            quality["p"] = msgs[aspects["p"]]
        if len(quality) == 2 and (
            quality["c"] == quality["p"] or quality["c"] == "\0"
        ):
            profile_name = re.sub(r"%cq\W*%pq", quality["p"], profile_name)
        for q in quality:
            profile_name = profile_name.replace(f"%{q}q", quality[q])

    if "%pt" in profile_name:
        profile_type = ProfileType.from_config_value(ctx.profile_type)
        short_label = profile_type.short_label if profile_type else None
        profile_name = profile_name.replace("%pt", short_label or "\0")

    if "%tpa" in profile_name:
        profile_name = profile_name.replace("%tpa", ctx.testchart_patches_amount)

    for directive in _DATE_DIRECTIVES:
        if f"%{directive}" in profile_name:
            try:
                profile_name = profile_name.replace(
                    f"%{directive}", strftime(f"%{directive}")
                )
            except UnicodeDecodeError:
                pass

    profile_name = re.sub(r"\s", " ", profile_name)

    if "\0" in profile_name:
        profile_name = re.sub(r"^(\0[_\- ]?)+|([_\- ]?\0)+$", "", profile_name)
        while "_\0" in profile_name or "\0_" in profile_name:
            while re.search(r"_\0+_", profile_name):
                profile_name = re.sub(r"_\0+_", "_", profile_name)
            profile_name = re.sub(r"_\0+", "_", profile_name)
            profile_name = re.sub(r"\0+_", "_", profile_name)
        while "-\0" in profile_name or "\0-" in profile_name:
            while re.search(r"-\0+-", profile_name):
                profile_name = re.sub(r"-\0+-", "-", profile_name)
            profile_name = re.sub(r"-\0+", "-", profile_name)
            profile_name = re.sub(r"\0+-", "-", profile_name)
        while " \0" in profile_name or "\0 " in profile_name:
            while re.search(r" \0+ ", profile_name):
                profile_name = re.sub(r" \0+ ", " ", profile_name)
            profile_name = re.sub(r" \0+", " ", profile_name)
            profile_name = re.sub(r"\0+ ", " ", profile_name)
        profile_name = re.sub(r"\0+", "", profile_name)

    profile_name = profile_name.rstrip(" .")
    profile_name = re.sub(r"[\\/:;*?\"<>|]+", "_", profile_name).lstrip("-")

    return truncate_profile_name_for_path(profile_name, getcfg("profile.save_path"))


def truncate_profile_name_for_path(profile_name: str, profile_save_path: str) -> str:
    """Shorten ``profile_name`` until its save path fits common filesystem limits.

    Port of the tail end of ``create_profile_name`` (Windows ``MAX_PATH`` /
    HFS+ 255-character headroom check).
    """
    maxpath = 255 - 31
    if maxpath < len(profile_save_path):
        maxpath = len(profile_save_path) + 2
    profile_path = os.path.join(profile_save_path, profile_name, profile_name)
    while len(profile_path) > maxpath:
        profile_name = profile_name[:-1]
        profile_path = os.path.join(profile_save_path, profile_name, profile_name)
    return profile_name


def is_valid_profile_name(profile_name: str) -> bool:
    r"""Return whether ``profile_name`` is a valid profile name.

    Port of ``MainFrame.check_profile_name``: must not contain
    ``\ / : ; * ? " < > |``, must not start with ``-``, and must not end in a
    combination of trailing spaces/dots (Windows silently strips those).
    """
    return bool(
        re.match(r'^[^\\/:;*?"<>|]+$', profile_name)
        and not profile_name.startswith("-")
        and profile_name == profile_name.rstrip(" .")
    )


def sanitize_profile_name(value: str) -> str:
    """Strip characters that would make ``value`` an invalid profile name.

    Port of the fallback branch in ``MainFrame.profile_name_ctrl_handler``,
    used when the text a user typed fails :func:`is_valid_profile_name`.
    """
    if value == "":
        return str(DEFAULTS.get("profile.name", ""))
    newval = re.sub(r'[\\/:;*?"<>|]+', "", value).lstrip("-")[:80]
    return newval.rstrip(" .")


def profile_name_placeholders() -> str:
    """Return the formatted profile-name placeholder legend.

    Port of ``MainFrame.profile_name_info``, reusing the same already
    translated ``lang`` strings (not re-authored for Qt).
    """
    info = [
        f"%nn\t{lang.getstr('computer.name')}",
        f"%dn\t{lang.getstr('display')}",
        f"%dns\t{lang.getstr('display_short')}",
        f"%dnw\t{lang.getstr('display')} ({lang.getstr('windows_only')})",
        f"%dnws\t{lang.getstr('display_short')} ({lang.getstr('windows_only')})",
        f"%out\t{lang.getstr('display.output')}",
        f"%ds\t{lang.getstr('edid.serial')} ({lang.getstr('if_available')})",
        f"%crc32\t{lang.getstr('edid.crc32')} ({lang.getstr('if_available')})",
        f"%in\t{lang.getstr('instrument')}",
        f"%im\t{lang.getstr('measurement_mode')}",
        f"%wp\t{lang.getstr('whitepoint')}",
        f"%cb\t{lang.getstr('calibration.luminance')}",
        f"%cB\t{lang.getstr('calibration.black_luminance')}",
        f"%cg\t{lang.getstr('trc')}",
        f"%ca\t{lang.getstr('calibration.ambient_viewcond_adjust')}",
        f"%cf\t{lang.getstr('calibration.black_output_offset')}",
        f"%ck\t{lang.getstr('calibration.black_point_correction')}",
    ]
    if DEFAULTS["calibration.black_point_rate.enabled"]:
        info.append(f"%cA\t{lang.getstr('calibration.black_point_rate')}")
    info.extend(
        [
            f"%cq\t{lang.getstr('calibration.speed')}",
            f"%pq\t{lang.getstr('profile.quality')}",
            f"%pt\t{lang.getstr('profile.type')}",
            f"%tpa\t{lang.getstr('testchart.info')}",
        ]
    )
    return "{}\n{}".format(lang.getstr("profile.name.placeholders"), "\n".join(info))


def get_testchart_names(path: str | None = None) -> tuple[list[str], list[str]]:
    """Return ``(display_names, chart_paths)`` for the testchart chooser.

    Port of ``MainFrame.get_testchart_names``: lists sibling testcharts next
    to ``path`` (same base name, ``.icc``/``.icm``/``.ti1``/``.ti3``) plus the
    bundled default testcharts (via ``get_data_path``), deduplicated and
    natural-sorted, always led by the synthetic ``"auto"`` entry.

    Args:
        path: The currently configured ``testchart.file`` path, or ``None``
            to read it from config.

    Returns:
        A tuple of the localized display names (for the combo box) and the
        parallel list of resolvable chart paths/identifiers (``"auto"`` first).
    """
    testchart_names: list[str] = []
    testcharts: list[str] = []
    if path is None:
        path = getcfg("testchart.file")
    if path != "auto" and os.path.exists(path):
        testchart_dir = os.path.dirname(path)
        try:
            found = listdir_re(
                testchart_dir,
                re.escape(os.path.splitext(os.path.basename(path))[0])
                + r"\.(?:icc|icm|ti1|ti3)$",
            )
        except Exception as exception:
            print(f"Error - directory '{testchart_dir}' listing failed: {exception}")
        else:
            for testchart_name in found:
                if testchart_name not in testchart_names:
                    testchart_names.append(testchart_name)
                    testcharts.append(os.pathsep.join((testchart_name, testchart_dir)))
    default_testcharts = get_data_path("ti1", r"\.(?:icc|icm|ti1|ti3)$")
    if isinstance(default_testcharts, list):
        for testchart in default_testcharts:
            testchart_dir = os.path.dirname(testchart)
            testchart_name = os.path.basename(testchart)
            if testchart_name not in testchart_names:
                testchart_names.append(testchart_name)
                testcharts.append(os.pathsep.join((testchart_name, testchart_dir)))
    testcharts = ["auto", *natsort(testcharts)]
    names = []
    for i, chart in enumerate(testcharts):
        parts = chart.split(os.pathsep)
        parts.reverse()
        testcharts[i] = os.path.join(*parts)
        chart_name = "auto_optimized" if parts[-1] == "auto" else parts[-1]
        names.append(lang.getstr(chart_name))
    return names, testcharts


@dataclass(frozen=True)
class DistributedTestcharts:
    """Bundled ``.ti1`` testcharts shipped alongside the application."""

    paths: list[str]
    names: list[str]  # basenames, parallel to ``paths``


def discover_distributed_testcharts() -> DistributedTestcharts:
    """Port of ``MainFrame.__init__``'s ``RES_FILES`` ``.ti1`` scan."""
    paths: list[str] = []
    names: list[str] = []
    for filename in RES_FILES:
        path = get_data_path(os.path.sep.join(filename.split("/")))
        ext = os.path.splitext(filename)[1]
        if path and os.path.isfile(path) and ext.lower() == ".ti1":
            paths.append(path)
            names.append(os.path.basename(path))
    return DistributedTestcharts(paths, names)


def default_testchart_names() -> list[str]:
    """Port of the ``default_testchart_names`` list built from ``TESTCHART_DEFAULTS``."""  # noqa: E501
    names: list[str] = []
    for testcharts in config.TESTCHART_DEFAULTS.values():
        for chart in testcharts.values():
            if chart not in names:
                names.append(chart)
    return names


@dataclass(frozen=True)
class DefaultTestchartResolution:
    """What :func:`resolve_default_testchart` decided to do.

    Mirrors ``MainFrame.set_default_testchart``'s three outcomes, split so
    the Qt caller can apply each independently: ``corrected_file``, if set,
    should be persisted to ``testchart.file`` first (a basename-only path
    was resolved to its bundled location); ``testchart_path``, if set, is
    the value to load via the caller's own ``set_testchart`` equivalent;
    ``missing_ti1``, if set, is the basename of a default ``.ti1`` that
    couldn't be found on disk (the caller decides how to alert).
    """

    corrected_file: str | None
    testchart_path: str | None
    missing_ti1: str | None


def resolve_default_testchart(
    current_path: str,
    profile_type: str,
    profile_quality: str,
    force: bool = False,
    dist: DistributedTestcharts | None = None,
) -> DefaultTestchartResolution:
    """Port of ``MainFrame.set_default_testchart``'s pure path-resolution half.

    Deliberately excludes the missing-``.ti1`` ``InfoDialog`` and actually
    applying the result -- see :class:`DefaultTestchartResolution`.
    """
    if dist is None:
        dist = discover_distributed_testcharts()
    names = default_testchart_names()
    path = current_path
    if path == "auto":
        return DefaultTestchartResolution(None, "auto", None)
    corrected = None
    basename = os.path.basename(path)
    if basename in dist.names:
        path = dist.paths[dist.names.index(basename)]
        corrected = path
    already_default = lang.getstr(os.path.basename(path)) in ("", *names)
    if not force and already_default and os.path.isfile(path):
        return DefaultTestchartResolution(corrected, None, None)
    if not force and already_default:
        ti1 = os.path.basename(path)
    else:
        type_defaults = config.TESTCHART_DEFAULTS.get(profile_type, {None: "auto"})
        ti1 = type_defaults.get(profile_quality, type_defaults[None])
    if ti1 == "auto":
        return DefaultTestchartResolution(corrected, "auto", None)
    resolved = get_data_path(os.path.join("ti1", ti1))
    if not resolved or not os.path.isfile(resolved):
        return DefaultTestchartResolution(corrected, None, ti1)
    return DefaultTestchartResolution(corrected, resolved, None)


#: Recommended minimum patch count per ``profile_type (+ profile_quality)``.
#: Port of ``check_testchart_patches_amount``'s ``recommended`` dict -- lower
#: quality actually needs a *higher* patch count, higher quality can get away
#: with fewer. The ``+quality`` keys (``"lh"``/``"xh"``/``"Xh"``) happen to
#: carry the same value as their base type, kept only for fidelity with wx.
_RECOMMENDED_TESTCHART_PATCHES = {
    "G": 6, "g": 6, "l": 125, "lh": 125, "S": 12, "s": 12,
    "X": 73, "Xh": 73, "x": 73, "xh": 73,
}


def testchart_recommendation_auto_optimize(
    profile_type: str, profile_quality: str, current_patches: int, is_ccxx: bool
) -> int | None:
    """Return the ``testchart.auto_optimize`` value to suggest, or ``None``.

    Port of ``check_testchart_patches_amount``'s gating and suggested-value
    math; the confirm dialog itself (and the ``profile_quality_ctrl``
    enable/disable bracketing it) stays with the caller.
    """
    if is_ccxx:
        return None
    fallback = _RECOMMENDED_TESTCHART_PATCHES[profile_type]
    recommended = _RECOMMENDED_TESTCHART_PATCHES.get(
        profile_type + profile_quality, fallback
    )
    if recommended <= current_patches:
        return None
    return max(
        config.VALID_VALUES["testchart.auto_optimize"][1],
        round(colormath.cbrt(recommended)),
    )


def testchart_patches_amount_for_auto(auto: int) -> int:
    """Return the estimated patch count for an auto-optimize slider value.

    Port of the patch-count formula in
    ``MainFrame.testchart_patches_amount_ctrl_handler``.
    """
    if auto > 4:
        s = min(auto, 11) * 4 - 3
        g = s * 3 - 2
        patches_amount = config.get_total_patches(4, 4, s, g, auto, auto, 0) + 34
        return patches_amount + 120
    return {1: 34, 2: 79, 3: 115}.get(auto, 175)


def suggested_profile_type_for_auto(
    auto: int, current_profile_type: str, lut3d_create: bool
) -> str | None:
    """Return a suggested ``profile.type`` change for an auto-optimize value.

    Port of the ``if event: ...`` profile-type nudging in
    ``testchart_patches_amount_ctrl_handler`` (only applied by the caller on
    an actual user-triggered change, matching wx's ``if event`` guard).
    Returns ``None`` when no change is suggested.
    """
    if auto > 4:
        if current_profile_type not in (
            ProfileType.LAB_LUT,
            ProfileType.XYZ_LUT,
            ProfileType.XYZ_LUT_MATRIX,
        ):
            return ProfileType.XYZ_LUT if lut3d_create else ProfileType.XYZ_LUT_MATRIX
        return None
    if auto > 1:
        if current_profile_type not in (ProfileType.XYZ_LUT, ProfileType.XYZ_LUT_MATRIX):
            return ProfileType.XYZ_LUT if lut3d_create else ProfileType.XYZ_LUT_MATRIX
        return None
    if current_profile_type not in (
        ProfileType.GAMMA_MATRIX,
        ProfileType.SINGLE_GAMMA_MATRIX,
        ProfileType.SHAPER_MATRIX,
        ProfileType.SINGLE_SHAPER_MATRIX,
    ):
        return ProfileType.SINGLE_SHAPER_MATRIX if getcfg("trc") else ProfileType.SHAPER_MATRIX
    return None


@dataclass
class MeasurementTimeEstimate:
    """Result of :func:`estimate_measurement_time`."""

    hours: int | None
    minutes: int | None

    def label(self) -> str:
        """Return the localized ``"~Hh Mm"``-style label."""
        return lang.getstr(
            "estimated_measurement_time",
            (self.hours if self.hours is not None else "--",
             self.minutes if self.minutes is not None else "--"),
        )

    def is_long(self) -> bool:
        """Whether the estimate is long enough to warrant a warning color."""
        return self.hours is not None and self.hours > 3


def estimate_measurement_time(
    worker,
    patches: int,
    which: str = "testchart",
    ffp_insertion_visible: bool = False,
) -> MeasurementTimeEstimate:
    """Estimate wall-clock measurement time for ``patches`` test patches.

    Faithful port of ``wx_report_frame.ReportFrame.update_estimated_measurement_time``'s
    numeric computation, minus the wx label/color side effects (the caller
    applies :meth:`MeasurementTimeEstimate.label` / :meth:`is_long` to its own
    widget).

    Args:
        worker: The :class:`~DisplayCAL.worker.Worker` instance (for
            instrument features).
        patches: The number of patches to measure.
        which: ``"testchart"``, ``"chart"``, or ``"cal"`` -- only affects
            whether the patch-sequence response-delay adjustment applies.
        ffp_insertion_visible: Whether the flash-field-pattern-insertion row
            is currently shown (wx gates the FFP delay addition on
            ``self.ffp_insertion.IsShown()``, since that row is itself only
            shown for Prisma/Resolve/madVR pattern generators).
    """
    integration_time = worker.get_instrument_features().get("integration_time")
    if not integration_time:
        return MeasurementTimeEstimate(None, None)

    opatches = patches
    tech = getcfg("display.technology").lower()
    if isinstance(tech, bytes):
        tech = tech.decode("utf-8")
    prop = [1, 1]
    if "plasma" in tech or "crt" in tech:
        prop[0] = 1.9
    elif "projector" in tech or "dlp" in tech:
        prop[0] = 2.2
        prop[1] = 2.2
    elif "oled" in tech:
        prop[0] = 2.2
    integration_time = [min(prop[i] * v, 20) for i, v in enumerate(integration_time)]

    tpp = list(integration_time)
    if (
        ("plasma" in tech or "crt" in tech or "projector" in tech or "dlp" in tech)
        and worker.get_instrument_features().get("refresh")
    ):
        tpp = [v + 0.25 for v in tpp]
    if config.get_display_name() == "madVR":
        tpp = [v + 0.45 for v in tpp]
    min_delay_s = 0.2
    if getcfg("measure.override_min_display_update_delay_ms"):
        min_delay_ms = getcfg("measure.min_display_update_delay_ms")
        min_delay_s = max(min_delay_ms / 1000.0, min_delay_s)
    if getcfg("measure.override_display_settle_time_mult"):
        settle_mult = getcfg("measure.display_settle_time_mult")
    else:
        settle_mult = 1.0
    tpp = [v + min_delay_s + 0.145 * settle_mult for v in tpp]
    avg_delay = sum(tpp) / (8 / 3.0)
    seconds = avg_delay * patches
    oseconds = seconds

    if getcfg("drift_compensation.blacklevel"):
        seconds += math.ceil(oseconds / 60.0) * ((20 - tpp[0]) / 2.0 + tpp[0])
        seconds += math.ceil(opatches / 40.0) * ((20 - tpp[0]) / 2.0 + tpp[0])
    if getcfg("drift_compensation.whitelevel"):
        seconds += math.ceil(oseconds / 60.0) * tpp[1]
        seconds += math.ceil(opatches / 40.0) * tpp[1]
    if (
        which in ("testchart", "chart")
        and getcfg("testchart.patch_sequence") != "optimize_display_response_delay"
    ):
        seconds -= 0.65 / 1.75 * patches
        seconds += 0.65 * patches
    if ffp_insertion_visible and getcfg("patterngenerator.ffp_insertion"):
        interval = getcfg("patterngenerator.ffp_insertion.interval")
        duration = getcfg("patterngenerator.ffp_insertion.duration")
        if getcfg("measure.override_min_display_update_delay_ms"):
            dur = getcfg("measure.min_display_update_delay_ms") / 1000.0
        else:
            dur = 0
        ffp_delay = max(0.8 - dur, 0)
        seconds += seconds / max(interval, avg_delay) * (duration + ffp_delay)

    timestamp = gmtime(seconds)
    hours = int(strftime("%H", timestamp))
    minutes = int(strftime("%M", timestamp))
    minutes += math.ceil(int(strftime("%S", timestamp)) / 60.0)
    if minutes > 59:
        minutes = 0
        hours += 1
    return MeasurementTimeEstimate(hours, minutes)


def icc_profile_has_embedded_ti3(profile: ICCProfile) -> bool:
    """Return whether ``profile`` embeds a TI3 measurement file.

    Port of the ``"CTI3" not in ti3_lines`` check in
    ``MainFrame.testchart_btn_handler``, used to reject ``.icc``/``.icm``
    files picked as a testchart that don't actually contain one.
    """
    ti3_lines = [
        line.strip()
        for line in BytesIO(profile.tags.get("CIED", b"") or profile.tags.get("targ", b""))
    ]
    return b"CTI3" in ti3_lines


def load_testchart_from_file(path: str) -> CGATS:
    """Load and validate a testchart (``.ti1``/``.ti3``/``.icc``/``.icm``).

    Port of ``MainFrame.load_testchart_from_file``: raises
    :class:`~DisplayCAL.cgats.CGATSError` (or an ``OSError``/
    :class:`~DisplayCAL.icc_profile.ICCProfileInvalidError` for a malformed
    ICC profile) on invalid content -- the caller is responsible for showing
    an error dialog, matching wx's ``InfoDialog`` call site.
    """
    ext = os.path.splitext(path)[-1].lower()
    if ext in (".ti1", ".ti3"):
        if ext == ".ti3":
            with open(path, "rb") as f:
                ti3_data = f.read()
            ti1 = CGATS(ti3_to_ti1(ti3_data))
        else:
            ti1 = CGATS(path)
    else:
        profile = ICCProfile(path)
        ti1 = CGATS(
            ti3_to_ti1(profile.tags.get("CIED", "") or profile.tags.get("targ", ""))
        )
    verify_ti1_rgb_xyz(ti1)
    return ti1
