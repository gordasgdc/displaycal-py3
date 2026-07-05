"""Toolkit-neutral helpers for the calibration/profile-file header bar.

Pure pieces lifted out of ``MainFrame``'s calibration-file-bar handlers
(``display_cal.py``): the recent-calibrations/presets bootstrap, current-file
resolution, calibration-file parsing, the config-restore /
CGATS-option-to-config dispatch behind ``load_cal_handler``, the
related-files-for-deletion scan, and session-archive file selection. The
per-option setter functions this module dispatches to already live in
:mod:`DisplayCAL.main_settings` (Stage 0); this module supplies the
orchestration ``load_cal_handler`` used to call them. None of it touches a GUI
toolkit, so both the still-shipping wx path and the Qt header bar
(:mod:`DisplayCAL.ui.main_window`) can share it.

Deliberately not reproduced here (documented, not silently dropped):

* EDID/instrument-ID auto-matching of the profile being loaded against the
  currently enumerated displays (``load_cal_handler``'s
  ``display_name_indexes`` / ``edid_md5_indexes`` block), and the "d" dispcal
  option's virtual-display auto-select (``-dweb`` / ``-dmadvr``, used by the
  ``video_*`` pattern-generator presets) -- both are conveniences for
  multi-display / pattern-generator setups, which are already deferred Pile-2
  scope (see ``MAINFRAME_PORT_PLAN.md``'s "Deferred to the Qt main window").
* The legacy pre-``ARGYLL_DISPCAL_ARGS`` ``.cal`` parsing branch (files from
  Argyll releases old enough to predate that section) -- vanishing real-world
  usage.
* The ``3DLUT_*`` / ``SIMULATION_PROFILE`` HDR config-mapper block -- the 3D
  LUT tab's HDR/encoding sub-controls are already documented deferred scope.
* Cross-window resync (``lut3dframe``, ``reportframe``) -- those tool windows
  aren't ported to Qt.
"""

from __future__ import annotations

import io
import os
import zipfile
from dataclasses import dataclass
from typing import Callable

from send2trash import send2trash

from DisplayCAL import localization as lang
from DisplayCAL import main_settings
from DisplayCAL.config import DEFAULTS, PROFILE_EXT, get_data_path, getcfg, setcfg
from DisplayCAL.icc_profile import ICCProfile, ICCProfileInvalidError, Text
from DisplayCAL.util_io import TarFileProper
from DisplayCAL.util_list import index_fallback_ignorecase, natsort
from DisplayCAL.util_os import safe_glob
from DisplayCAL.util_str import strtr

#: Recognized calibration/profile file extensions (mirrors ``display_cal``'s
#: module-level constants of the same name, duplicated here to avoid pulling
#: wx into this toolkit-neutral module).
ICCPROFILE_FILE_EXTENSIONS = (".icc", ".icm")
COMPRESSED_FILE_EXTENSIONS = (".7z", ".tar.gz", ".tgz", ".zip")


class CalibrationFileError(Exception):
    """A calibration/profile file failed to validate or parse.

    Args:
        lang_key: A :mod:`DisplayCAL.localization` key describing the error.
        path: The file path involved, appended to the message if given.
    """

    def __init__(self, lang_key: str, path: str | None = None) -> None:
        self.lang_key = lang_key
        self.path = path
        message = lang.getstr(lang_key)
        if path:
            message = f"{message}\n{path}"
        super().__init__(message)


def build_recent_calibrations() -> tuple[list[str], list[str]]:
    """Return ``(recent_cals, presets)``, mirroring ``MainFrame.__init__``.

    ``recent_cals`` always starts with a leading ``""`` entry (the "new
    settings" / no-calibration choice), followed by any bundled presets, then
    the paths persisted in the ``recent_cals`` config option.
    """
    recent_cals = getcfg("recent_cals").split(os.pathsep)
    while "" in recent_cals:
        recent_cals.remove("")
    recent_cals.insert(0, "")

    presets: list[str] = []
    found = get_data_path("presets", r".*\.(?:icc|icm)$")
    if isinstance(found, list):
        presets = natsort(found)
        presets.reverse()
        for preset in presets:
            if preset in recent_cals:
                recent_cals.remove(preset)
            recent_cals.insert(1, preset)
    return recent_cals, presets


def get_unpreseted_recent_calibrations(
    recent_cals: list[str], presets: list[str]
) -> list[str]:
    """Return ``recent_cals`` entries that are not bundled presets."""
    return [recent_cal for recent_cal in recent_cals if recent_cal not in presets]


@dataclass
class CalibrationSelection:
    """The result of resolving the current ``calibration.file`` config value."""

    cal: str | None
    filename: str | None
    profile_path: str | None
    profile_exists: bool
    #: True if ``cal`` was not already in ``recent_cals`` and should be
    #: appended (and persisted to the ``recent_cals`` config option).
    is_new_recent: bool
    #: True if ``cal`` no longer exists on disk and should be dropped from
    #: ``recent_cals`` (mirrors wx clearing the selection back to "new").
    missing: bool = False


def resolve_calibration_selection(
    cal: str | None, recent_cals: list[str]
) -> CalibrationSelection:
    """Resolve ``cal`` against ``recent_cals``.

    Mirrors wx's ``update_calibration_file_ctrl`` method of the same name.

    Args:
        cal: The ``calibration.file`` config value (may be ``None``/falsy).
        recent_cals: The current in-memory recent-calibrations list.

    Returns:
        A :class:`CalibrationSelection` describing what to show / persist.
        Callers are responsible for actually mutating ``recent_cals`` and the
        ``recent_cals`` config option based on ``is_new_recent`` / ``missing``,
        since this function does not mutate its input.
    """
    if cal and os.path.isfile(cal):
        filename, ext = os.path.splitext(cal)
        is_new_recent = cal not in recent_cals
        if ext.lower() in ICCPROFILE_FILE_EXTENSIONS:
            profile_path = cal
        else:
            profile_path = filename + PROFILE_EXT
        return CalibrationSelection(
            cal=cal,
            filename=filename,
            profile_path=profile_path,
            profile_exists=os.path.exists(profile_path),
            is_new_recent=is_new_recent,
        )
    return CalibrationSelection(
        cal=None,
        filename=None,
        profile_path=None,
        profile_exists=False,
        is_new_recent=False,
        missing=bool(cal) and cal in recent_cals[1:],
    )


def parse_calibration_file(path: str) -> tuple[ICCProfile | None, list[bytes]]:
    """Parse a ``.cal`` file or ICC profile, returning ``(profile, ti3_lines)``.

    Faithful port of ``parse_calibration_file`` / ``validate_icc_profile`` /
    ``validate_calibration_data``, minus the wx ``InfoDialog`` calls (raises
    :class:`CalibrationFileError` instead).
    """
    ext = os.path.splitext(path)[-1]
    if ext.lower() not in ICCPROFILE_FILE_EXTENSIONS:
        try:
            with open(path, "rb") as cal_file:
                return None, [line.strip() for line in cal_file]
        except OSError as exception:
            raise CalibrationFileError("error.file.open", path) from exception

    try:
        profile = ICCProfile(path)
    except (OSError, ICCProfileInvalidError) as exception:
        raise CalibrationFileError("profile.invalid", path) from exception
    if profile.profileClass != b"mntr" or profile.colorSpace != b"RGB":
        raise CalibrationFileError("profile.invalid", path)

    cied = profile.tags.get("CIED")
    if cied:
        with io.BytesIO(cied) as cal_data:
            return profile, [line.strip() for line in cal_data]

    targ = profile.tags.get("targ")
    if not (targ and isinstance(targ, Text)):
        raise CalibrationFileError("profile.no_targ", path)
    with io.BytesIO(targ.tagData) as cal_data:
        return profile, [line.strip() for line in cal_data]


#: Config keys never touched by :func:`restore_defaults`, mirroring
#: ``restore_defaults_handler``'s ``skip`` list verbatim.
_RESTORE_SKIP = (
    "allow_skip_sensor_cal",
    "app.allow_network_clients",
    "app.port",
    "argyll.dir",
    "argyll.version",
    "calibration.autoload",
    "calibration.black_point_rate.enabled",
    "calibration.file.previous",
    "calibration.update",
    "colorimeter_correction.instrument",
    "colorimeter_correction.instrument.reference",
    "colorimeter_correction.measurement_mode",
    "colorimeter_correction.measurement_mode.reference",
    "colorimeter_correction.measurement_mode.reference.projector",
    "colorimeter_correction_matrix_file",
    "comport.number",
    "copyright",
    "dimensions.measureframe.whitepoint.visual_editor",
    "display.number",
    "display.technology",
    "display_lut.link",
    "display_lut.number",
    "displays",
    "dry_run",
    "enumerate_ports.auto",
    "gamma",
    "iccgamut.surface_detail",
    "instruments",
    "lang",
    "last_3dlut_path",
    "last_cal_path",
    "last_cal_or_icc_path",
    "last_colorimeter_ti3_path",
    "last_filedialog_path",
    "last_icc_path",
    "last_reference_ti3_path",
    "last_testchart_export_path",
    "last_ti1_path",
    "last_ti3_path",
    "last_vrml_path",
    "log.show",
    "lut_viewer.show",
    "lut_viewer.show_actual_lut",
    "measurement_mode",
    "measurement_mode.projector",
    "measurement.name.expanded",
    "measurement.play_sound",
    "measurement.save_path",
    "multiprocessing.max_cpus",
    "patterngenerator.apl",
    "patterngenerator.resolve",
    "patterngenerator.resolve.port",
    "profile.b2a.hires.diagpng",
    "profile.create_gamut_views",
    "profile.install_scope",
    "profile.license",
    "profile.load_on_login",
    "profile.name",
    "profile.name.expanded",
    "profile.save_path",
    "profile_loader.check_gamma_ramps",
    "profile_loader.error.show_msg",
    "profile_loader.exceptions",
    "profile_loader.fix_profile_associations",
    "profile_loader.known_apps",
    "profile_loader.known_window_classes",
    "profile_loader.reset_gamma_ramps",
    "profile_loader.use_madhcnet",
    "profile_loader.verify_calibration",
    "profile.update",
    "position.x",
    "position.y",
    "position.info.x",
    "position.info.y",
    "position.lut_viewer.x",
    "position.lut_viewer.y",
    "position.lut3dframe.x",
    "position.lut3dframe.y",
    "position.synthiccframe.x",
    "position.synthiccframe.y",
    "position.profile_info.x",
    "position.profile_info.y",
    "position.progress.x",
    "position.progress.y",
    "position.reportframe.x",
    "position.reportframe.y",
    "position.scripting.x",
    "position.scripting.y",
    "position.tcgen.x",
    "position.tcgen.y",
    "recent_cals",
    "report.pack_js",
    "settings.changed",
    "show_advanced_options",
    "show_donation_message",
    "skip_legacy_serial_ports",
    "skip_scripts",
    "sudo.preserve_environment",
    "tc_precond_profile",
    "tc_vrml_cie",
    "tc_vrml_cie_colorspace",
    "tc_vrml_device",
    "tc_vrml_device_colorspace",
    "tc.show",
    "uniformity.measure.continuous",
    "untethered.measure.auto",
    "untethered.measure.manual.delay",
    "untethered.max_delta.chroma",
    "untethered.min_delta",
    "untethered.min_delta.lightness",
    "update_check",
    "webserver.portnumber",
    "whitepoint.visual_editor.bg_v",
    "whitepoint.visual_editor.b",
    "whitepoint.visual_editor.g",
    "whitepoint.visual_editor.r",
    "x3dom.cache",
    "x3dom.embed",
)


def restore_defaults(
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    override: dict | None = None,
) -> None:
    """Reset config keys to their defaults, mirroring ``restore_defaults_handler``.

    Only the config-mutating body is ported (the confirmation dialog and the
    window-refresh tail in wx only run when triggered from a menu, i.e. with a
    real event; ``load_cal_handler`` always calls this with no event).
    """
    override_default = {
        "app.dpi": None,
        "calibration.black_luminance": None,
        "calibration.luminance": None,
        "gamap_src_viewcond": None,
        "gamap_out_viewcond": None,
        "testchart.file": "auto",
        "trc": DEFAULTS["gamma"],
        "whitepoint.colortemp": None,
        "whitepoint.x": None,
        "whitepoint.y": None,
        "3dlut.whitepoint.x": None,
        "3dlut.whitepoint.y": None,
    }
    if override:
        override_default.update(override)
    override = override_default

    def _matches(name: str) -> bool:
        included = len(include) == 0 or any(name.find(item) == 0 for item in include)
        excluded = len(exclude) != 0 and any(name.find(item) == 0 for item in exclude)
        return included and not excluded

    for name in DEFAULTS:
        if name not in _RESTORE_SKIP and name not in override and _matches(name):
            if name.endswith(".backup") and name == "measurement_mode.backup":
                setcfg("measurement_mode", getcfg("measurement_mode.backup"))
            setcfg(name, None)
    for name in override:
        if _matches(name):
            setcfg(name, override[name])


#: dispcal option letter -> ``main_settings`` setter taking just ``option``.
#: The "d" (display number) and "X"/"E" options are intentionally excluded,
#: see module docstring; "k", "V", "YA", "H", "F" need a constant or extra
#: argument instead of ``option`` itself and are handled inline below.
_DISPCAL_OPTION_SETTERS = {
    "m": main_settings.set_interactive_display_adjustment_config_with_option,
    "q": main_settings.set_calibration_quality_config_with_option,
    "y": main_settings.set_measurement_mode_config_with_option,
    "t": main_settings.set_whitepoint_temperature_config_with_option,
    "T": main_settings.set_whitepoint_temperature_config_with_option,
    "W": main_settings.set_whitepoint_config_with_option,
    "b": main_settings.set_calibration_luminance_config_with_option,
    "g": main_settings.set_tone_response_curve_config_with_option,
    "G": main_settings.set_tone_response_curve_config_with_option,
    "f": main_settings.set_calibration_black_output_offset_config_with_option,
    "a": main_settings.set_ambient_view_condition_adjustment_config_with_option,
    "A": main_settings.set_calibration_black_point_rate_config_with_option,
    "B": main_settings.set_calibration_black_luminance_config_with_option,
    "P": main_settings.set_measureframe_config_with_option,
    "p": main_settings.set_measurement_mode_projector_config_with_option,
    "I": main_settings.set_drift_compensation_config_with_option,
    "Q": main_settings.set_tristimulus_observer_config_with_option,
}

#: colprof option letter -> ``main_settings`` setter taking just ``option``.
_COLPROF_OPTION_SETTERS = {
    "q": main_settings.set_profile_quality_config_with_option,
    "b": main_settings.set_profile_quality_b2a_config_with_option,
    "s": main_settings.set_gamap_profile_config_with_option,
    "S": main_settings.set_gamap_profile_config_with_option,
    "c": main_settings.set_gamap_src_viewcond_config_with_option,
    "d": main_settings.set_gamap_out_viewcond_config_with_option,
    "t": main_settings.set_gamap_perceptual_intent_config_with_option,
    "T": main_settings.set_gamap_saturation_intent_config_with_option,
}


def _dispatch_dispcal_option(option: str, black_point_correction: bool) -> bool:
    """Apply one dispcal option, returning the updated black-point-correction flag."""
    head, pair = option[0:1], option[0:2]
    if head == "k":
        (black_point_correction,) = (
            main_settings.set_black_point_correction_config_with_option(
                option, black_point_correction
            )
        )
    elif head == "V":
        main_settings.set_measurement_mode_adaptive_config_with_option(1)
    elif pair == "YA":
        main_settings.set_measurement_mode_adaptive_config_with_option(0)
    elif head == "H":
        main_settings.set_measurement_mode_highres_config_with_option(1)
    elif head == "F":
        main_settings.set_measure_darken_background_config_with_option(1)
    else:
        setter = _DISPCAL_OPTION_SETTERS.get(head, _DISPCAL_OPTION_SETTERS.get(pair))
        if setter is not None:
            setter(option)
    return black_point_correction


def apply_calibration_options(
    options_dispcal: list[str] | None, options_colprof: list[str] | None
) -> None:
    """Dispatch dispcal/colprof options to their ``main_settings`` config setters.

    Faithful port of ``load_cal_handler``'s two dispatch loops for the setters
    that ``main_settings`` already exposes (see module docstring for what's
    excluded: the "d"/display-number option, and the HDR 3D LUT config-mapper
    block that follows them in wx).
    """
    trc = bool(options_dispcal) and any(
        option[0:1] in ("g", "G") for option in options_dispcal
    )
    restore_defaults(
        include=(
            "calibration",
            "drift_compensation",
            "measure.darken_background",
            "measure.override_min_display_update_delay_ms",
            "measure.min_display_update_delay_ms",
            "measure.override_display_settle_time_mult",
            "measure.display_settle_time_mult",
            "observer",
            "patterngenerator.ffp_insertion",
            "trc",
            "whitepoint",
        ),
        exclude=(
            "calibration.black_point_correction_choice.show",
            "calibration.update",
            "calibration.use_video_lut",
            "measure.darken_background.show_warning",
            "patterngenerator.ffp_insertion.interval",
            "patterngenerator.ffp_insertion.duration",
            "patterngenerator.ffp_insertion.level",
            "trc.should_use_viewcond_adjust.show_msg",
        ),
        override={"trc": ""} if not trc else None,
    )

    black_point_correction = False
    if options_dispcal:
        for option in options_dispcal:
            black_point_correction = _dispatch_dispcal_option(
                option, black_point_correction
            )
        if trc and not black_point_correction:
            setcfg("calibration.black_point_correction.auto", 1)
    main_settings.update_whitepoint_config_from_temperature()

    if options_colprof:
        restore_defaults(
            include=(
                "profile",
                "gamap_",
                "3dlut.create",
                "3dlut.output.profile.apply_cal",
                "3dlut.trc",
                "testchart.auto_optimize",
                "testchart.patch_sequence",
            ),
            exclude=(
                "3dlut.tab.enable.backup",
                "profile.update",
                "profile.name",
                "gamap_default_intent",
            ),
        )
        for option in options_colprof:
            setter = _COLPROF_OPTION_SETTERS.get(
                option[0:1], _COLPROF_OPTION_SETTERS.get(option[0:2])
            )
            if setter is None:
                continue
            setter(option)


def related_files_for(cal: str, dircontents: list[str]) -> dict[str, bool]:
    """Return the calibration dir entries related to ``cal``, all pre-checked.

    Faithful port of ``initialize_related_files``.
    """
    related_files: dict[str, bool] = {}
    for entry in dircontents:
        fn, ext = os.path.splitext(entry)
        if ext.lower() in (".app", ".command", ".sh", ".bat"):
            fn, ext = os.path.splitext(fn)
        if (
            fn.startswith(os.path.splitext(os.path.basename(cal))[0])
            or ext.lower() in (".ccss", ".ccmx")
            or entry.lower() in ("0_16.ti1", "0_16.ti3", "0_16.log")
        ):
            related_files[entry] = True
    return related_files


def delete_related_files(
    cal: str, related_files: dict[str, bool]
) -> tuple[list[str], list[str]]:
    """Send the checked related files to the trash.

    Faithful port of ``delete_related_files_and_cleanup``'s send2trash half
    (minus the wx error dialogs -- callers inspect ``orphan_related_files``,
    the entries that survived, to report failures themselves).

    Returns:
        ``(delete_related_files, orphan_related_files)``: the files that were
        selected for deletion, and the subset that could not be removed.
    """
    delete_files = [
        os.path.join(os.path.dirname(cal), related_file)
        for related_file, checked in related_files.items()
        if checked
    ]
    if not delete_files:
        return delete_files, []
    send2trash(delete_files)
    orphan_files = [path for path in delete_files if os.path.exists(path)]
    return delete_files, orphan_files


def session_archive_filenames(cal: str) -> tuple[list[str], list[str], str]:
    """Return ``(filenames, dirfilenames, dirname)`` for a session archive of ``cal``.

    Faithful port of the file-selection half of ``create_session_archive_handler``.
    """
    dirname = os.path.dirname(cal)
    path_name = os.path.splitext(cal)[0]
    dirfilenames = sorted(os.path.join(dirname, name) for name in os.listdir(dirname))
    filenames = sorted(
        set(
            safe_glob(path_name + "*")
            + safe_glob(os.path.join(dirname, "*.ccmx"))
            + safe_glob(os.path.join(dirname, "*.ccss"))
            + safe_glob(os.path.join(dirname, "0_16.ti1"))
            + safe_glob(os.path.join(dirname, "0_16.ti3"))
            + safe_glob(os.path.join(dirname, "0_16.log"))
        )
    )
    return filenames, dirfilenames, dirname


def session_archive_has_3dlut_files(
    filenames: list[str], lut3d_formats: list[str]
) -> tuple[bool, list[str]]:
    """Return ``(has_3dlut, lut3d_ext)`` for the given archive file list.

    ``lut3d_formats`` should be ``config.VALID_VALUES["3dlut.format"]``.
    """
    lut3d_ext = [
        "." + strtr(lut3d_format, {"eeColor": "txt", "madVR": "3dlut"})
        for lut3d_format in lut3d_formats
        if lut3d_format not in ("icc", "icm", "png")
    ]
    has_3dlut = any(
        os.path.splitext(filename)[1].lower() in lut3d_ext for filename in filenames
    )
    return has_3dlut, lut3d_ext


@dataclass
class SessionArchiveRequest:
    """Bundles :func:`create_session_archive`'s arguments for one archive run."""

    dirname: str
    dirfilenames: list[str]
    filenames: list[str]
    archive_path: str
    exclude_ext: list[str] | None = None
    sevenzip: str | None = None


def create_session_archive(
    request: SessionArchiveRequest, exec_cmd: Callable[..., bool | Exception]
) -> bool | Exception:
    """Create the session archive described by ``request``.

    Faithful port of ``create_session_archive_producer``. ``exec_cmd`` runs
    the 7-Zip command line (``worker.exec_cmd`` in practice); the ZIP/TAR path
    doesn't need it.
    """
    dirname = request.dirname
    dirfilenames = request.dirfilenames
    filenames = list(request.filenames)
    archive_path = request.archive_path
    exclude_ext = request.exclude_ext
    sevenzip = request.sevenzip

    if sevenzip:
        if filenames == dirfilenames:
            filenames = [dirname]
        if os.path.isfile(archive_path):
            os.remove(archive_path)
        args = ["a", "-y"]
        if exclude_ext:
            args.extend(f"-xr!*{ext}" for ext in exclude_ext)
        return exec_cmd(
            sevenzip, [*args, archive_path, *filenames], capture_output=True
        )

    dirbasename = ""
    if filenames == dirfilenames:
        dirbasename = os.path.basename(dirname)
    try:
        if archive_path.lower().endswith((".tgz", ".tar.gz")):
            archive = TarFileProper.open(archive_path, "w:gz", encoding="UTF-8")
            writefile = archive.add
        else:
            archive = zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED)
            writefile = archive.write
        with archive:
            for filename in filenames:
                if exclude_ext and os.path.splitext(filename)[1].lower() in exclude_ext:
                    continue
                writefile(
                    filename, os.path.join(dirbasename, os.path.basename(filename))
                )
    except Exception as exception:  # noqa: BLE001 (reported to caller, not logged here)
        return exception
    return True


__all__ = [
    "COMPRESSED_FILE_EXTENSIONS",
    "ICCPROFILE_FILE_EXTENSIONS",
    "CalibrationFileError",
    "CalibrationSelection",
    "SessionArchiveRequest",
    "apply_calibration_options",
    "build_recent_calibrations",
    "create_session_archive",
    "delete_related_files",
    "get_unpreseted_recent_calibrations",
    "index_fallback_ignorecase",
    "parse_calibration_file",
    "related_files_for",
    "resolve_calibration_selection",
    "restore_defaults",
    "session_archive_filenames",
    "session_archive_has_3dlut_files",
]
