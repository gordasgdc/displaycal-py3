"""Toolkit-neutral helpers for "Create profile from measurement data..." (File menu).

Pure pieces lifted out of ``MainFrame.create_profile_handler`` (``display_cal.py``):
loading/validating one or more ``.ti3``/ICC-profile source files, averaging
several of them into one TI3 via Argyll's ``average`` utility, and extracting
the dispcal/targen options and display name/manufacturer the subsequent
``colprof`` run needs. None of this touches wx (or Qt) widgets -- it takes a
:class:`~DisplayCAL.worker.Worker` and plain values, matching the
``preflight_checks.py`` / ``measurement_report.py`` precedent.

The genuinely window-shaped parts (the multi-file open dialog, the "no CAL
info" and overwrite confirms, the save-path dialog, and the progress dialog
around the ``colprof`` run itself) stay in the wx and Qt window code. The
``colprof`` run and its completion handling are not reproduced here either --
both UIs feed the source data this module resolves into the same
``worker.create_profile`` / completion-handler pair the live-measurement
"build profile" flow already uses (``profile_finish.py``), matching wx's own
reuse of a single shared ``profile_finish`` consumer for both flows.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from io import BytesIO

from DisplayCAL import localization as lang
from DisplayCAL.argyll import get_argyll_util
from DisplayCAL.cgats import CGATS
from DisplayCAL.config import DEFAULTS
from DisplayCAL.icc_profile import ICCProfile, ICCProfileInvalidError
from DisplayCAL.worker import get_arg, get_options_from_profile, get_options_from_ti3


class CreateProfileError(Exception):
    """A file/step involved in creating a profile from measurements failed.

    ``str(exception)`` is already the fully-formatted, translated message the
    caller should show verbatim (matching the ``MeasurementFileError``
    precedent in ``measurement_report.py``).
    """


@dataclass
class CollectedMeasurement:
    """One source file collected by :func:`load_measurement_lines`."""

    #: Path the file was loaded from.
    path: str
    #: Raw, stripped lines of the (possibly profile-embedded) TI3 chart.
    ti3_lines: list[bytes]
    #: The ICC profile this was extracted from, or ``None`` for a plain ``.ti3``.
    profile: ICCProfile | None
    #: Preserved ``mmod``/``meta`` tags, if the source was a profile.
    tags: dict = field(default_factory=dict)


def load_measurement_lines(path: str) -> CollectedMeasurement:
    """Load one ``.ti3`` file or ICC profile with an embedded TI3 chart.

    Pure port of the per-file half of ``create_profile_handler``'s collection
    loop (``display_cal.py``): unlike
    :func:`DisplayCAL.measurement_report.load_measurement_file`, this keeps
    the chart as raw stripped lines (not a parsed :class:`CGATS`), since
    :func:`merge_measurement_files` needs to re-serialize several charts
    verbatim for Argyll's ``average`` utility before anything is parsed.

    Args:
        path: Path to a ``.ti3`` file, or an ``.icc``/``.icm`` profile with a
            ``CIED`` or ``targ`` tag holding an embedded CTI3 chart.

    Returns:
        The loaded :class:`CollectedMeasurement`.

    Raises:
        CreateProfileError: The profile could not be parsed, had no embedded
            TI3 chart, or the ``.ti3`` file could not be opened.
    """
    tags: dict = {}
    _stem, source_ext = os.path.splitext(path)
    if source_ext.lower() != ".ti3":
        try:
            profile = ICCProfile(path)
        except (OSError, ICCProfileInvalidError) as exception:
            raise CreateProfileError(
                f"{lang.getstr('profile.invalid')}\n{path}"
            ) from exception
        ti3_data = profile.tags.get("CIED", b"") or profile.tags.get("targ", b"")
        if ti3_data[0:4] != b"CTI3":
            raise CreateProfileError(
                f"{lang.getstr('profile.no_embedded_ti3')}\n{path}"
            )
        with BytesIO(ti3_data) as ti3:
            ti3_lines = [line.strip() for line in ti3]
        for tagname in ("mmod", "meta"):
            if tagname in profile.tags:
                tags[tagname] = profile.tags[tagname]
    else:
        profile = None
        try:
            with open(path, "rb") as ti3:
                ti3_lines = [line.strip() for line in ti3]
        except OSError as exception:
            raise CreateProfileError(
                lang.getstr("error.file.open", path)
            ) from exception
    return CollectedMeasurement(path=path, ti3_lines=ti3_lines, profile=profile, tags=tags)


def has_calibration_curves(ti3_lines: list[bytes]) -> bool:
    """Whether a loaded chart's raw lines contain calibration curve data.

    Port of ``create_profile_handler``'s ``b"CAL" not in ti3_lines`` check,
    which gates the "the measurement data does not contain calibration
    curves, continue anyway?" confirm.
    """
    return b"CAL" in ti3_lines


def resolve_source_naming(paths: list[str]) -> tuple[str, str]:
    """Derive the ``(source_filename_without_ext, source_ext)`` pair to name after.

    Port of ``create_profile_handler``'s naming fallback: a single source file
    is named after itself; multiple files have no single name to inherit, so
    wx falls back to the ``last_ti3_path`` default and forces the ``.ti3``
    branch of the later options-extraction step (merging always produces a
    ``.ti3``, never a profile).

    Args:
        paths: The collected source paths, in selection order.

    Returns:
        ``(source_filename_without_ext, source_ext)``.
    """
    if len(paths) > 1:
        return os.path.splitext(DEFAULTS["last_ti3_path"])[0], ".ti3"
    return os.path.splitext(paths[0])


def is_temp_path(worker, path: str) -> bool:
    """Whether ``path`` already lives inside the worker's own temp dir.

    Port of the ``is_tmp`` detection in ``create_profile_handler``, used to
    decide whether the save-path dialog defaults to ``last_ti3_path`` (temp
    source, e.g. a just-regenerated profile) or the source file's own
    directory.
    """
    tmp_working_dir = worker.tempdir
    if not tmp_working_dir:
        return False
    if sys.platform == "win32":
        return path.lower().startswith(tmp_working_dir.lower())
    return path.startswith(tmp_working_dir)


def merge_measurement_files(
    worker,
    collected: list[CollectedMeasurement],
    tmp_working_dir: str,
    ti3_tmp_path: str,
) -> None:
    """Average several collected TI3s into one via Argyll's ``average`` utility.

    Port of ``create_profile_handler``'s multi-file averaging step: writes
    each collected chart to its own temp copy, runs ``average`` to merge them
    into ``ti3_tmp_path``, then removes the per-file copies regardless of
    outcome.

    Args:
        worker: The :class:`~DisplayCAL.worker.Worker` to run ``average`` on.
        collected: The source files to merge (2 or more).
        tmp_working_dir: Directory to write per-file temp copies into.
        ti3_tmp_path: Destination path for the merged TI3.

    Raises:
        CreateProfileError: ``average`` failed or produced no output.
    """
    collected_paths = []
    for item in collected:
        collected_path = os.path.join(tmp_working_dir, os.path.basename(item.path))
        with open(collected_path, "wb") as ti3_file:
            ti3_file.write(b"\n".join(item.ti3_lines))
        collected_paths.append(collected_path)
    args = ["-v", *collected_paths, ti3_tmp_path]
    cmd = get_argyll_util("average")
    result = worker.exec_cmd(cmd, args, capture_output=True, skip_scripts=True)
    for collected_path in collected_paths:
        os.remove(collected_path)
    if isinstance(result, Exception) or not result:
        message = str(result) if isinstance(result, Exception) else "\n".join(worker.errors)
        raise CreateProfileError(message)


@dataclass
class ProfileCreationInputs:
    """The ``colprof``-run inputs :func:`resolve_profile_creation_inputs` derives."""

    #: The final (merged/copied) TI3, parsed.
    ti3: CGATS
    #: Dispcal options recovered from the source (``-`` prefixed).
    options_dispcal: list[str]
    #: Targen options implied by the chart (``["-d3"]`` for an RGB source).
    options_targen: list[str]
    display_name: str | None
    display_manufacturer: str | None


def resolve_profile_creation_inputs(
    source_path: str,
    source_ext: str,
    ti3_tmp_path: str,
    profile: ICCProfile | None,
    is_tmp: bool,
) -> ProfileCreationInputs:
    """Stage the final TI3 and extract the options ``create_profile`` needs.

    Port of ``create_profile_handler``'s options-extraction block: for a
    ``.ti3`` source, copies it into place (unless it's already the merged
    file) and pulls dispcal/colprof options out of its embedded
    ``ARGYLL_DISPCAL_ARGS``/``ARGYLL_COLPROF_ARGS`` comments; for a profile
    source, writes its embedded chart out and pulls the same options from the
    profile's own tags. Either way, an RGB chart implies ``targen -d3``.

    Args:
        source_path: The (possibly merged) TI3 path, or the original source
            file for a single-file profile source.
        source_ext: The original source extension (always ``.ti3`` when
            :func:`resolve_source_naming` was given more than one path).
        ti3_tmp_path: Where the final TI3 should end up.
        profile: The source profile, for a single-file non-``.ti3`` source.
        is_tmp: Whether the original source already lived in the worker's
            temp dir (see :func:`is_temp_path`) -- if so, and it isn't the
            same file as ``ti3_tmp_path``, it is closed and removed once its
            chart has been extracted.

    Returns:
        The resolved :class:`ProfileCreationInputs`.

    Raises:
        CreateProfileError: Any failure while staging/parsing the TI3, wrapped
            with the same message ``create_profile_handler`` shows.
    """
    try:
        options_dispcal: list[str] = []
        options_targen: list[str] = []
        display_name = None
        display_manufacturer = None
        if source_ext.lower() == ".ti3":
            if source_path != ti3_tmp_path:
                shutil.copyfile(source_path, ti3_tmp_path)
            options_dispcal_raw, options_colprof = get_options_from_ti3(source_path)
            options_dispcal = ["-" + arg for arg in options_dispcal_raw]
            arg = get_arg("M", options_colprof)
            if arg:
                display_name = arg[1][2:].strip('"')
            arg = get_arg("A", options_colprof)
            if arg:
                display_manufacturer = arg[1][2:].strip('"')
        else:
            with open(ti3_tmp_path, "wb") as ti3_file:
                ti3_file.write(
                    profile.tags.get("CIED", b"") or profile.tags.get("targ", b"")
                )
            options_dispcal = [
                "-" + arg for arg in get_options_from_profile(profile)[0]
            ]
            if "dmdd" in profile.tags:
                display_name = profile.getDeviceModelDescription()
            if "dmnd" in profile.tags:
                display_manufacturer = profile.getDeviceManufacturerDescription()
            if is_tmp and source_path != ti3_tmp_path:
                profile.close()
                os.remove(source_path)
        ti3 = CGATS(ti3_tmp_path)
        color_rep = ti3.queryv1("COLOR_REP")
        if color_rep and color_rep[:3] == b"RGB":
            options_targen = ["-d3"]
    except Exception as exception:
        raise CreateProfileError(
            "Error - temporary .ti3 file could not be created: " + str(exception)
        ) from exception
    return ProfileCreationInputs(
        ti3=ti3,
        options_dispcal=options_dispcal,
        options_targen=options_targen,
        display_name=display_name,
        display_manufacturer=display_manufacturer,
    )
