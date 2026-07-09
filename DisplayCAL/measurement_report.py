"""Toolkit-neutral helpers for the measurement report feature.

These are the pure pieces lifted out of ``MainFrame.measurement_report_handler``,
``MainFrame.measurement_report`` and ``MainFrame.measurement_report_consumer``
(``display_cal.py``): chart/profile resolution, the worker-driven TI1/TI3
staging, and the big ``placeholders2data`` assembly, none of which touch wx (or
Qt) widgets directly -- they take a :class:`~DisplayCAL.worker.Worker` and plain
values, matching the ``preflight_checks.py`` precedent of treating ``Worker`` as
an already-toolkit-neutral collaborator. A plain ``DisplayCAL`` module so
importing it never pulls in Qt, matching ``main_settings.py``. The wx frame
delegates to these; the Qt main window (``ui/main_window.py``) reuses them for
its report layer.

The genuinely window-shaped parts (file-save dialog, overwrite confirm, the
progress dialog around the worker run) stay in their respective UI layers.

Deliberately not reproduced by :func:`resolve_report_context` /
:func:`finalize_measurement_report` (both callers -- wx and Qt -- only get the
simplified behaviour now, matching the drops already made for the calibrate/
profile pipeline in ``profile_finish.py``):

* The self-check report (holding Alt while clicking Measure looks up the chart
  through the display profile's own B2A table instead of measuring) -- a
  distinct diagnostic flow layered on top of the same setup, left for a future
  slice.
* ``check_profile_b2a_hires``'s low-res-B2A refusal + "regenerate hires
  tables?" offer -- always proceeds with the profile as-is now.
* ``measurement_file_check_confirm``'s interactive suspicious-patch review
  grid -- always proceeds with the measured data unmodified (the
  ``isinstance(result, tuple)`` patch-removal branch in the original consumer
  can then never trigger and is dropped with it).
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from time import strftime
from typing import TYPE_CHECKING

from DisplayCAL import colormath, config, report
from DisplayCAL import localization as lang
from DisplayCAL.argyll import make_argyll_compatible_path
from DisplayCAL.argyll_cgats import extract_cal_from_profile
from DisplayCAL.cgats import (
    CGATS,
    CGATSError,
    CGATSInvalidError,
    CGATSInvalidOperationError,
    CGATSKeyError,
    CGATSTypeError,
    CGATSValueError,
)
from DisplayCAL.colormath import XYZ2Lab
from DisplayCAL.config import DEFAULTS, get_current_profile, get_data_path, getcfg
from DisplayCAL.icc_profile import (
    ChromaticAdaptionTag,
    ICCProfile,
    ICCProfileInvalidError,
    LUT16Type,
    VideoCardGammaType,
    XYZType,
)
from DisplayCAL.util_decimal import float2dec
from DisplayCAL.util_os import launch_file
from DisplayCAL.util_str import ellipsis_
from DisplayCAL.worker import (
    get_arg,
    get_cfg_option_from_args,
    get_options_from_profile,
    parse_argument_string,
)

if TYPE_CHECKING:
    from DisplayCAL.worker import Worker

# Characters Argyll / the filesystem cannot carry in a report filename, matching
# the sanitisation the wx handler applies to the display name.
_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:;*?"<>|]+')

#: The white-patch device-value query used throughout the report pipeline.
_WHITE_RGB = {"RGB_R": 100, "RGB_G": 100, "RGB_B": 100}


class ReportSetupError(Exception):
    """Raised when the report chart/profile resolution cannot proceed."""


@dataclass
class ReportContext:
    """Everything :func:`resolve_report_context` resolved for one report run.

    Mirrors the local variables ``measurement_report_handler`` builds up before
    calling ``setup_measurement`` (minus the self-check-report branch).
    """

    chart: CGATS
    ti1: CGATS
    ti3_ref: CGATS
    gray: list | None
    profile: ICCProfile
    oprof: ICCProfile
    sim_profile: ICCProfile | None
    devlink: ICCProfile | None
    sim_ti3: CGATS | None
    intent: str
    sim_intent: str | None
    apply_trc: bool
    colormanaged: bool
    use_sim: bool
    use_sim_as_output: bool
    report_type: str
    default_file: str


def default_report_filename(
    report_type: str,
    version_string: str,
    display_name: str,
    timestamp: str | None = None,
) -> str:
    """Build the default ``.html`` filename offered in the save dialog.

    Ports the ``default_file`` construction in ``measurement_report_handler``.

    Args:
        report_type: ``"Measurement"`` or ``"Self Check"``.
        version_string: The application version string (``VERSION_STRING``).
        display_name: The display name, already stripped of the localized
            ``display.primary`` suffix by the caller.
        timestamp: ``"%Y-%m-%d %H-%M"`` timestamp; defaults to now.

    Returns:
        The suggested filename, including the ``.html`` extension.
    """
    if timestamp is None:
        timestamp = strftime("%Y-%m-%d %H-%M")
    safe_display = _UNSAFE_FILENAME_CHARS.sub("_", display_name)
    return f"{report_type} Report {version_string} - {safe_display} - {timestamp}.html"


def resolve_quantization_bits(args: list) -> int | None:
    """Determine the reference-value quantization bit depth from dispread args.

    Ports the ``qbits`` derivation in ``measurement_report_consumer``: an
    explicit ``-Z <bits>`` (or ``-Zbits``) wins, otherwise video encoding
    (``-E``) implies ArgyllCMS' 8-bit default.

    Args:
        args: The dispread argument list (after
            ``worker.add_measurement_features``).

    Returns:
        The bit depth, or ``None`` if no quantization applies.
    """
    quantize_arg = get_arg("-Z", args)
    if quantize_arg:
        try:
            if quantize_arg[1] == "-Z":
                # Next arg is quantization bit depth
                return int(args[quantize_arg[0] + 1])
            # Quantization bit depth is part of arg string
            return int(quantize_arg[1][2:])
        except (IndexError, TypeError, ValueError):
            return None
    elif "-E" in args:
        return 8  # ArgyllCMS default for video encoding (see dispread doc)
    return None


def quantize_gray(gray: list, qbits: int) -> list:
    """Quantize grayscale RGB reference values to ``qbits`` bits.

    Ports the ``gray`` rescaling in ``measurement_report_consumer``.

    Args:
        gray: A list of ``[R, G, B]`` triples in 0-100.
        qbits: The quantization bit depth.

    Returns:
        A new list of quantized ``[R, G, B]`` triples.
    """
    qmax = 2**qbits - 1.0
    return [
        [round(round(v / 100.0 * qmax) / qmax * 100.0, 4) for v in rgb] for rgb in gray
    ]


def report_trc_label(
    trc_gamma: float, trc_gamma_type: str, trc_output_offset: float
) -> str:
    """Return the report's TRC label for the given TRC config values.

    Ports the ``trc`` derivation in ``measurement_report_consumer``: the default
    BT.1886 target (gamma 2.4, type ``B``, no output offset) is labelled
    ``"BT.1886"``, anything else is unlabelled.

    Args:
        trc_gamma: ``measurement_report.trc_gamma``.
        trc_gamma_type: ``measurement_report.trc_gamma_type``.
        trc_output_offset: ``measurement_report.trc_output_offset``.

    Returns:
        ``"BT.1886"`` for the default target, otherwise ``""``.
    """
    if trc_gamma != 2.4 or trc_gamma_type != "B" or trc_output_offset:
        return ""
    return "BT.1886"


def resolve_report_context(
    worker: Worker, version_string: str, display_name: str
) -> ReportContext:
    """Resolve the chart/profile/simulation setup for a measurement report.

    Ports ``measurement_report_handler``'s body up to (not including) the
    save-path file dialog: loads the configured chart, resolves the
    simulation/devlink/output profiles, computes the optional BT.1886-style
    TRC target, and runs the reference-value chart lookups. The self-check
    report branch is not reproduced (see module docstring).

    Args:
        worker: The worker whose ``chart_lookup`` / ``xicclu`` do the actual
            colour-managed lookups.
        version_string: ``VERSION_STRING``, used in the default filename.
        display_name: The target display's label, already stripped of the
            localized ``display.primary`` suffix by the caller.

    Returns:
        The resolved :class:`ReportContext`.

    Raises:
        ReportSetupError: The chart or a configured profile could not be
            loaded, or none of the chart lookups produced usable data.
    """
    try:
        chart = CGATS(getcfg("measurement_report.chart"), True)
    except (OSError, CGATSError) as exception:
        raise ReportSetupError(str(exception)) from exception

    chart = worker.ensure_patch_sequence(chart, False)
    fields = getcfg("measurement_report.chart.fields")

    paths = []
    use_sim = bool(getcfg("measurement_report.use_simulation_profile"))
    use_sim_as_output = bool(
        getcfg("measurement_report.use_simulation_profile_as_output")
    )
    use_devlink = bool(getcfg("measurement_report.use_devlink_profile"))
    if use_sim:
        if use_sim_as_output and use_devlink:
            devlink_path = getcfg("measurement_report.devlink_profile")
            if devlink_path:
                paths.append(devlink_path)
            else:
                use_devlink = False
        paths.append(getcfg("measurement_report.simulation_profile"))

    sim_profile = None
    devlink = None
    oprof = profile = get_current_profile(True)
    for i, profilepath in enumerate(paths):
        try:
            profile = ICCProfile(profilepath)
        except (OSError, ICCProfileInvalidError) as exception:
            if isinstance(exception, ICCProfileInvalidError):
                message = f"{lang.getstr('profile.invalid')}\n{profilepath}"
            else:
                message = str(exception)
            raise ReportSetupError(message) from exception
        if profile.version >= 4 and not profile.convert_iccv4_tags_to_iccv2():
            raise ReportSetupError(
                "\n".join(
                    [lang.getstr("profile.iccv4.unsupported"), profile.getDescription()]
                )
            )
        if i in (0, 1) and use_sim:
            if use_sim_as_output and profile.colorSpace == b"RGB":
                if i == 0 and use_devlink:
                    devlink = profile
            else:
                if profile.colorSpace != b"RGB":
                    use_sim_as_output = False
                    devlink = None
                sim_profile = profile
                profile = oprof
    if not profile and not oprof:
        raise ReportSetupError(
            lang.getstr(
                "display_profile.not_detected", config.get_display_name(None, True)
            )
        )

    colormanaged = (
        use_sim
        and use_sim_as_output
        and not sim_profile
        and config.get_display_name(None, True) in ("madVR", "Prisma")
        and bool(getcfg("3dlut.enable"))
    )

    mprof = (sim_profile if sim_profile else profile) if use_sim else None
    apply_map = (
        use_sim
        and mprof.colorSpace == b"RGB"
        and isinstance(mprof.tags.get("rXYZ"), XYZType)
        and isinstance(mprof.tags.get("gXYZ"), XYZType)
        and isinstance(mprof.tags.get("bXYZ"), XYZType)
        and not isinstance(mprof.tags.get("A2B0"), LUT16Type)
    )
    apply_off = apply_map and bool(getcfg("measurement_report.apply_black_offset"))
    apply_trc = apply_map and bool(getcfg("measurement_report.apply_trc"))
    bt1886 = None
    if apply_trc or apply_off:
        try:
            odata = worker.xicclu(oprof, (0, 0, 0), pcs="x")
            if len(odata) != 1 or len(odata[0]) != 3:
                raise ValueError(f"Blackpoint is invalid: {odata}")
        except Exception as exception:
            raise ReportSetupError(str(exception)) from exception
        if odata[0][1]:
            xyz_bp = odata[0]
        else:
            xyz_bp = oprof.get_chardata_bkpt()
            if xyz_bp:
                xyz_bp = [v * xyz_bp[1] for v in list(oprof.tags.wtpt.pcs.values())]
            else:
                xyz_bp = [0, 0, 0]
        if apply_trc:
            gamma = getcfg("measurement_report.trc_gamma")
            gamma_type = getcfg("measurement_report.trc_gamma_type")
            outoffset = getcfg("measurement_report.trc_output_offset")
            if gamma_type == "b":
                gamma = colormath.xicc_tech_gamma(gamma, xyz_bp[1], outoffset)
        else:
            outoffset = 1.0
            gamma = 0.0
            for channel in "rgb":
                gamma += mprof.tags[f"{channel}TRC"].get_gamma()
            gamma /= 3.0
        r_xyz = list(mprof.tags.rXYZ.values())
        g_xyz = list(mprof.tags.gXYZ.values())
        b_xyz = list(mprof.tags.bXYZ.values())
        mtx = colormath.Matrix3x3(
            [
                [r_xyz[0], g_xyz[0], b_xyz[0]],
                [r_xyz[1], g_xyz[1], b_xyz[1]],
                [r_xyz[2], g_xyz[2], b_xyz[2]],
            ]
        )
        bt1886 = colormath.BT1886(mtx, xyz_bp, outoffset, gamma, apply_trc)
        if apply_trc:
            for channel in ("r", "g", "b"):
                if channel + "TRC" in mprof.tags:
                    mprof.tags[channel + "TRC"].set_trc(-709)
            mprof.filename = None

    sim_gray = None
    if sim_profile:
        sim_intent = "a" if getcfg("measurement_report.whitepoint.simulate") else "r"
        _void, sim_ti3, sim_gray = worker.chart_lookup(
            chart,
            sim_profile,
            check_missing_fields=True,
            intent=sim_intent,
            bt1886=bt1886,
        )
        if not sim_ti3:
            raise ReportSetupError(
                "Chart lookup produced no usable data for the measurement report."
            )
        intent = (
            "r"
            if sim_intent == "r"
            or getcfg("measurement_report.whitepoint.simulate.relative")
            else "a"
        )
        bt1886 = None
    else:
        sim_ti3 = None
        sim_intent = None
        intent = "r"
        if fields in ("LAB", "XYZ"):
            if getcfg("measurement_report.whitepoint.simulate"):
                sim_intent = "a"
                if not getcfg("measurement_report.whitepoint.simulate.relative"):
                    intent = "a"
            else:
                chart.fix_device_values_scaling()
                chart.adapt(cat=profile.guess_cat() or "Bradford")

    ti1, ti3_ref, gray = worker.chart_lookup(
        sim_ti3 or chart,
        profile,
        bool(sim_ti3) or fields in ("LAB", "XYZ"),
        fields=None if sim_ti3 else fields,
        intent=intent,
        bt1886=bt1886,
    )
    if not ti3_ref:
        raise ReportSetupError(
            "Chart lookup produced no usable data for the measurement report."
        )
    if not gray and sim_gray:
        gray = sim_gray

    if devlink:
        _void, ti1, _void2 = worker.chart_lookup(
            ti1,
            devlink,
            check_missing_fields=True,
            white_patches=1,
            white_patches_total=False,
        )
        if not ti1:
            raise ReportSetupError(
                "Chart lookup produced no usable data for the measurement report."
            )

    report_type = "Measurement"
    return ReportContext(
        chart=chart,
        ti1=ti1,
        ti3_ref=ti3_ref,
        gray=gray,
        profile=profile,
        oprof=oprof,
        sim_profile=sim_profile,
        devlink=devlink,
        sim_ti3=sim_ti3,
        intent=intent,
        sim_intent=sim_intent,
        apply_trc=apply_trc,
        colormanaged=colormanaged,
        use_sim=use_sim,
        use_sim_as_output=use_sim_as_output,
        report_type=report_type,
        default_file=default_report_filename(report_type, version_string, display_name),
    )


def stage_measurement_files(
    worker: Worker,
    save_path: str,
    ti1: CGATS,
    oprof: ICCProfile,
    profile: ICCProfile,
    use_sim_as_output: bool,
    devlink: ICCProfile | None,
) -> tuple[str, str]:
    """Write the TI1 / profile / calibration files a measurement run needs.

    Ports the temp-dir setup in ``measurement_report`` (the part before
    ``worker.start``): creates the temp dir, writes ``ti1`` and ``profile``
    there, and extracts a calibration curve to apply during the read.

    Args:
        worker: The worker whose temp dir / calibration extraction is used.
        save_path: The report's destination path (only its basename is used
            to name the staged files).
        ti1: The TI1 chart to measure.
        oprof: The original (display) profile.
        profile: The profile actually used for the lookup (``oprof`` unless a
            simulation profile is standing in as the output profile).
        use_sim_as_output: ``measurement_report.use_simulation_profile_as_output``.
        devlink: The device-link profile, if any.

    Returns:
        ``(ti1_path, cal_path)``, both inside the worker's temp dir (or
        ``cal_path`` pointing at the bundled ``linear.cal`` when the source
        profile carries no calibration curve).

    Raises:
        Exception: Whatever ``worker.create_tempdir`` / file I/O /
            ``extract_cal_from_profile`` raise.
    """
    temp = worker.create_tempdir()
    if isinstance(temp, Exception):
        raise temp
    name = os.path.splitext(os.path.basename(save_path))[0]
    ti1_path = os.path.join(temp, f"{name}.ti1")
    profile_path = os.path.join(temp, f"{name}.icc")

    with open(ti1_path, "wb") as ti1_file:
        ti1_file.write(bytes(ti1))
    profile.write(profile_path)

    if not use_sim_as_output or (
        devlink
        and "-a"
        not in parse_argument_string(
            devlink.tags.get("meta", {})
            .get("collink.args", {})
            .get("value", "-a" if getcfg("3dlut.output.profile.apply_cal") else "")
        )
    ):
        calprof = oprof
    else:
        calprof = profile

    cal_path = os.path.join(temp, f"{name}.cal")
    cal = extract_cal_from_profile(calprof, cal_path, False)
    if not cal:
        cal_path = get_data_path("linear.cal")
    return ti1_path, cal_path


def finalize_measurement_report(
    *,
    worker: Worker,
    ti3_path: str,
    profile: ICCProfile,
    sim_profile: ICCProfile | None,
    intent: str,
    sim_intent: str | None,
    devlink: ICCProfile | None,
    ti3_ref: CGATS,
    sim_ti3: CGATS | None,
    save_path: str,
    chart: CGATS,
    gray: list | None,
    apply_trc: bool,
    use_sim: bool,
    use_sim_as_output: bool,
    oprof: ICCProfile,
    instrument_name: str,
    measurement_mode_name: str,
    display_name: str,
    observers: dict,
    version_string: str,
    pack_js: bool = True,
) -> None:
    """Process a completed measurement and write the HTML report.

    Ports ``measurement_report_consumer``'s body from just after the
    (dropped, see module docstring) sanity-check dialog through
    ``report.create`` / launching the finished file. The caller is expected to
    have already handled the ``Exception`` / falsy-result branches of the
    worker run (matching how ``MainWindow._on_measurement_finished`` handles
    those before calling into ``profile_finish.py``) -- this function assumes
    the measurement succeeded.

    Args:
        worker: The worker the measurement ran on (used for ``wrapup`` and
            re-deriving the quantization args).
        ti3_path: Path to the measured TI3 (``measure_ti1``'s working file).
        profile: The profile used for the lookup.
        sim_profile: The simulation profile, if any.
        intent: The rendering intent used for the reference lookup.
        sim_intent: The simulation rendering intent, if any.
        devlink: The device-link profile, if any.
        ti3_ref: The reference TI3 (mutated in place, matching the original).
        sim_ti3: The simulation TI3, if any.
        save_path: Where to write the ``.html`` report.
        chart: The original chart CGATS (only its filename is inspected).
        gray: Grayscale reference patches, if any.
        apply_trc: Whether a BT.1886-style TRC target was applied.
        use_sim: ``measurement_report.use_simulation_profile``.
        use_sim_as_output: ``measurement_report.use_simulation_profile_as_output``.
        oprof: The original (display) profile.
        instrument_name: The selected instrument's label (``comport_ctrl``).
        measurement_mode_name: The selected measurement mode's label.
        display_name: The target display's label, already stripped of the
            localized ``display.primary`` suffix by the caller.
        observers: Observer code -> localized label map (``self.observers_ab``
            / ``self._observers``).
        version_string: ``VERSION_STRING``, embedded in the report.
        pack_js: ``report.pack_js``.

    Raises:
        Exception: Any CGATS / I/O error encountered while processing the
            measured data or writing the report.
    """
    try:
        ti3_measured = CGATS(ti3_path)[0]
    except (
        OSError,
        CGATSInvalidError,
        CGATSInvalidOperationError,
        CGATSKeyError,
        CGATSTypeError,
        CGATSValueError,
    ) as exception:
        worker.wrapup(exception)
        raise

    qbits = None
    if config.get_display_name() != "Untethered":
        args = []
        if getcfg("extra_args.dispread").strip():
            args += parse_argument_string(getcfg("extra_args.dispread"))
        worker.add_measurement_features(
            args, True, allow_video_levels=True, quantize=True
        )
        qbits = resolve_quantization_bits(args)
    if qbits:
        ti3_ref.quantize_device_values(qbits)
        if gray:
            gray = quantize_gray(gray, qbits)

    ti3_ref.write(f"{os.path.splitext(ti3_path)[0]}_ref.ti3")

    white_ref = ti3_ref.queryi(_WHITE_RGB)
    if devlink:
        ti3_measured.DATA.remove(0)
        offset = len(ti3_measured.DATA) - len(ti3_ref.DATA)
        for i in range(offset):
            for label in ("RGB_R", "RGB_G", "RGB_B"):
                ti3_measured.DATA[i][label] = 100.0
        for i in ti3_ref.DATA:
            for label in ("RGB_R", "RGB_G", "RGB_B"):
                ti3_measured.DATA[i + offset][label] = ti3_ref.DATA[i][label]
        white_measured = ti3_measured.queryi(_WHITE_RGB)
        luminance = float(ti3_measured.LUMINANCE_XYZ_CDM2.split()[1])
        white_xyz_cdm2 = [0, 0, 0]
        for i, label in enumerate(("XYZ_X", "XYZ_Y", "XYZ_Z")):
            white_xyz_cdm2[i] = white_measured[0][label] * luminance / 100.0
        ti3_measured.LUMINANCE_XYZ_CDM2 = "{:.6f} {:.6f} {:.6f}".format(*white_xyz_cdm2)
        scale = 100.0 / white_measured[0]["XYZ_Y"]
        for i in ti3_measured.DATA:
            for label in ("XYZ_X", "XYZ_Y", "XYZ_Z"):
                ti3_measured.DATA[i][label] *= scale
    else:
        white_measured = ti3_measured.queryi(_WHITE_RGB)
        offset = max(len(white_measured) - len(white_ref), 0)

    planckian = False
    if (profile.tags.get("CIED", "") or profile.tags.get("targ", ""))[0:4] == "CTI3":
        options_dispcal = get_options_from_profile(profile)[0]
        for option in options_dispcal:
            if option.startswith("T"):
                planckian = True
                break

    cal_entrycount = 256
    if isinstance(profile.tags.get("vcgt"), VideoCardGammaType):
        rgb = [[], [], []]
        vcgt = profile.tags.vcgt
        if "data" in vcgt:
            cal_entrycount = vcgt["entryCount"]
            for i in range(cal_entrycount):
                for j in range(3):
                    rgb[j].append(
                        float(vcgt["data"][j][i])
                        / (math.pow(256, vcgt["entrySize"]) - 1)
                        * 255
                    )
        else:
            step = 100.0 / 255.0
            for i in range(cal_entrycount):
                for j, chname in enumerate(("red", "green", "blue")):
                    vmin = float2dec(vcgt[chname + "Min"] * 255)
                    v = float2dec(math.pow(step * i / 100.0, vcgt[chname + "Gamma"]))
                    vmax = float2dec(vcgt[chname + "Max"] * 255)
                    rgb[j].append(float2dec(vmin + v * (vmax - vmin), 8))
        cal_rgblevels = [len({round(n) for n in channel}) for channel in rgb]
    else:
        cal_rgblevels = [256, 256, 256]

    if not chart.filename.lower().endswith(".ti1") or sim_ti3:
        for i in ti3_ref.DATA:
            for color in ("RGB_R", "RGB_G", "RGB_B"):
                if sim_ti3 and sim_ti3.DATA[i].get(color) is not None:
                    ti3_ref.DATA[i][color] = sim_ti3.DATA[i][color]
                else:
                    ti3_ref.DATA[i][color] = ti3_measured.DATA[i + offset][color]

    cat = "Bradford"
    ti3_joined = CGATS(bytes(ti3_ref))[0]
    ti3_joined.LUMINANCE_XYZ_CDM2 = ti3_measured.LUMINANCE_XYZ_CDM2
    labels_xyz = ("XYZ_X", "XYZ_Y", "XYZ_Z")
    if (
        "XYZ_X" not in list(ti3_joined.DATA_FORMAT.values())
        and "XYZ_Y" not in list(ti3_joined.DATA_FORMAT.values())
        and "XYZ_Z" not in list(ti3_joined.DATA_FORMAT.values())
    ):
        ti3_joined.DATA_FORMAT.add_data(labels_xyz)
    for i in ti3_joined.DATA:
        for color in labels_xyz:
            ti3_joined.DATA[i][color] = ti3_measured.DATA[i + offset][color]

    worker.wrapup(False)

    wtpt_profile_norm = tuple(n * 100 for n in list(profile.tags.wtpt.values()))
    if isinstance(profile.tags.get("chad"), ChromaticAdaptionTag):
        w_x, w_y, w_z = profile.tags.chad.inverted() * wtpt_profile_norm
        wtpt_profile_norm = tuple((n / w_y) * 100.0 for n in (w_x, w_y, w_z))
        cat = profile.guess_cat() or cat
    elif isinstance(profile.tags.get("arts"), ChromaticAdaptionTag):
        cat = profile.guess_cat() or cat
    if oprof and isinstance(oprof.tags.get("lumi"), XYZType):
        scale = oprof.tags.lumi.Y / 100.0
        wtpt_profile = tuple(n * scale for n in wtpt_profile_norm)
    else:
        wtpt_profile = wtpt_profile_norm

    if sim_profile and "chad" in sim_profile.tags:
        # NOTE: matches the original, which computes this but never uses it.
        wtpt_sim_profile_norm = tuple(  # noqa: F841
            n * 100 for n in list(sim_profile.tags.wtpt.values())
        )

    wtpt_measured = tuple(float(n) for n in ti3_joined.LUMINANCE_XYZ_CDM2.split())
    wtpt_measured_norm = tuple((n / wtpt_measured[1]) * 100 for n in wtpt_measured)

    if intent != "a" and sim_intent != "a":
        white = ti3_joined.queryi(_WHITE_RGB)
        for i in white:
            white[i].update(
                {
                    "XYZ_X": wtpt_measured_norm[0],
                    "XYZ_Y": wtpt_measured_norm[1],
                    "XYZ_Z": wtpt_measured_norm[2],
                }
            )

    black = ti3_joined.queryi1({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0})
    if black:
        bkpt_measured_norm = (black["XYZ_X"], black["XYZ_Y"], black["XYZ_Z"])
        bkpt_measured = tuple(wtpt_measured[1] / 100 * n for n in bkpt_measured_norm)
    else:
        bkpt_measured = None

    labels_lab = ("LAB_L", "LAB_A", "LAB_B")
    for data in (ti3_ref, ti3_joined):
        data_formats = list(data.DATA_FORMAT.values())
        if (
            b"XYZ_X" in data_formats
            and b"XYZ_Y" in data_formats
            and b"XYZ_Z" in data_formats
        ):
            if (
                b"LAB_L" not in data_formats
                and b"LAB_A" not in data_formats
                and b"LAB_B" not in data_formats
            ):
                data.DATA_FORMAT.add_data(labels_lab)
                has_lab = False
            else:
                has_lab = True
            if data is ti3_joined or not has_lab:
                for i in data.DATA:
                    x, y, z = (data.DATA[i][color] for color in labels_xyz)
                    if data is ti3_joined:
                        x, y, z = colormath.adapt(x, y, z, wtpt_measured_norm, cat=cat)
                    lab = XYZ2Lab(x, y, z)
                    for j, color in enumerate(labels_lab):
                        data.DATA[i][color] = lab[j]
        if data is ti3_ref and sim_intent == "a" and intent == "a":
            for i in data.DATA:
                lab_l, lab_a, lab_b = (data.DATA[i][color] for color in labels_lab)
                x, y, z = colormath.Lab2XYZ(lab_l, lab_a, lab_b, scale=100)
                x, y, z = colormath.adapt(x, y, z, wtpt_profile_norm, cat=cat)
                lab = XYZ2Lab(x, y, z)
                for j, color in enumerate(labels_lab):
                    data.DATA[i][color] = lab[j]

    instrument = f"{instrument_name} — {measurement_mode_name}"
    observer = get_cfg_option_from_args(
        "observer", "-Q", getattr(worker, "options_dispread", [])
    )
    if observer != DEFAULTS["observer"]:
        instrument += " — " + observers.get(observer, observer)

    ccmx = "None"
    reference_observer = None
    if worker.instrument_can_use_ccxx():
        ccmx = getcfg("colorimeter_correction_matrix_file").split(":", 1)
        if len(ccmx) > 1 and ccmx[1]:
            ccmxpath = ccmx[1]
            ccmx = os.path.basename(ccmx[1])
            try:
                cgats = CGATS(ccmxpath)
            except (OSError, CGATSError):
                pass
            else:
                filename, ext = os.path.splitext(ccmx)
                desc = cgats.get_descriptor()
                desc = lang.getstr(
                    ext[1:] + "." + filename, default=desc.decode("utf-8")
                )
                argyll_compatible_path = make_argyll_compatible_path(desc)
                if re.sub(r"[\\/:;*?\"<>|]+", "_", argyll_compatible_path) != filename:
                    ccmx = "{} &amp;lt;{}&amp;gt;".format(
                        desc, ellipsis_(ccmx, 31, "m")
                    )
                if cgats.get(0, cgats).type == "CCMX":
                    reference_observer = cgats.queryv1("REFERENCE_OBSERVER")
                    if (
                        reference_observer
                        and reference_observer != DEFAULTS["observer"]
                    ):
                        reference_observer = observers.get(
                            reference_observer, reference_observer
                        )
                        if reference_observer.lower() not in ccmx.lower():
                            ccmx += " — " + reference_observer
        else:
            ccmx = "None"

    if not sim_profile and use_sim and use_sim_as_output:
        sim_profile = profile

    trc = report_trc_label(
        getcfg("measurement_report.trc_gamma"),
        getcfg("measurement_report.trc_gamma_type"),
        getcfg("measurement_report.trc_output_offset"),
    )

    placeholders2data = {
        "${PLANCKIAN}": 'checked="checked"' if planckian else "",
        "${DISPLAY}": display_name,
        "${INSTRUMENT}": instrument,
        "${CORRECTION_MATRIX}": ccmx,
        "${BLACKPOINT}": "{:f} {:f} {:f}".format(
            *(bkpt_measured if bkpt_measured else (-1.0, -1.0, -1.0))
        ),
        "${WHITEPOINT}": "{:f} {:f} {:f}".format(*wtpt_measured),
        "${WHITEPOINT_NORMALIZED}": "{:f} {:f} {:f}".format(*wtpt_measured_norm),
        "${PROFILE}": profile.getDescription(),
        "${PROFILE_WHITEPOINT}": "{:f} {:f} {:f}".format(*wtpt_profile),
        "${PROFILE_WHITEPOINT_NORMALIZED}": "{:f} {:f} {:f}".format(*wtpt_profile_norm),
        "${SIMULATION_PROFILE}": sim_profile.getDescription() if sim_profile else "",
        "${TRC_GAMMA}": str(
            getcfg("measurement_report.trc_gamma") if apply_trc else "null"
        ),
        "${TRC_GAMMA_TYPE}": str(
            getcfg("measurement_report.trc_gamma_type") if apply_trc else ""
        ),
        "${TRC_OUTPUT_OFFSET}": str(
            getcfg("measurement_report.trc_output_offset") if apply_trc else 0
        ),
        "${TRC}": trc if apply_trc else "",
        "${WHITEPOINT_SIMULATION}": str(sim_intent == "a").lower(),
        "${WHITEPOINT_SIMULATION_RELATIVE}": str(
            sim_intent == "a" and intent == "r"
        ).lower(),
        "${DEVICELINK_PROFILE}": devlink.getDescription() if devlink else "",
        "${TESTCHART}": os.path.basename(chart.filename),
        "${ADAPTION}": str(profile.guess_cat(False) or cat),
        "${DATETIME}": strftime("%Y-%m-%d %H:%M:%S"),
        "${REF}": bytes(ti3_ref).decode("utf-8", "replace").replace('"', "&quot;"),
        "${MEASURED}": bytes(ti3_joined)
        .decode("utf-8", "replace")
        .replace('"', "&quot;"),
        "${CAL_ENTRYCOUNT}": str(cal_entrycount),
        "${CAL_RGBLEVELS}": repr(cal_rgblevels),
        "${GRAYSCALE}": repr(gray) if gray else "null",
        "${REPORT_VERSION}": version_string,
        "${REPORT_TYPE}": "Measurement",
    }

    report.create(save_path, placeholders2data, pack_js)
    launch_file(save_path)
