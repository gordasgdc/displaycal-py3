"""Toolkit-neutral helpers for finishing profile creation (the ``colprof`` stage).

Pure pieces lifted out of ``MainFrame.start_profile_worker`` and
``MainFrame.profile_finish`` (``display_cal.py``): the default profile save
path, validating the profile ``worker.Worker.create_profile`` just built, and
the self-check / gamut-coverage summary text. None of this carries a wx (or
Qt) dependency, so both the shipping wx path and the Qt main window can call
into it, matching ``profile_install.py`` / ``main_settings.py``.

The genuinely window-shaped parts of ``profile_finish`` are not reproduced
here and stay Pile 2: the big ``ConfirmDialog`` with its share-profile
button, calibration-preview / show-LUT / show-profile-info checkboxes, the
install-scope radio buttons, the Windows profile-loader ``getcfg`` round
trip, and the automatic 3D LUT creation offer. The Qt port instead offers a
plain install confirmation that reuses the already-ported
``InstallProfileWindow`` for the actual install step. Also not reproduced:
the ``options_dispcal and options_colprof`` branch of ``profile_finish``,
which calls the giant ``load_cal_handler`` to reload every settings control
from the profile's embedded cal curves -- ``sync_calibration_file_config``
below always takes the simpler "just point at the new file" branch instead.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from DisplayCAL import localization as lang
from DisplayCAL.config import PROFILE_EXT, getcfg, setcfg
from DisplayCAL.icc_profile import (
    GAMUT_VOLUME_ADOBERGB,
    GAMUT_VOLUME_SMPTE431_P3,
    GAMUT_VOLUME_SRGB,
    ICCProfile,
    ICCProfileInvalidError,
    VideoCardGammaType,
)


def resolve_profile_path(profile_path: str | None = None) -> str:
    """Return the path a just-built profile lives/will live at.

    Ports the default-path derivation duplicated in ``start_profile_worker``
    and ``profile_finish``.

    Args:
        profile_path: An explicit path, if already known.

    Returns:
        ``profile_path`` unchanged if given, else the default
        ``profile.save_path``/``profile.name.expanded`` location.
    """
    if profile_path:
        return profile_path
    name = getcfg("profile.name.expanded")
    return os.path.join(getcfg("profile.save_path"), name, name + PROFILE_EXT)


class ProfileFinishInvalidError(Exception):
    """The built profile file could not be read/parsed."""


class ProfileFinishNotDisplayError(Exception):
    """The built profile is not an RGB monitor profile.

    Ports the ``profile.profileClass != b"mntr" or profile.colorSpace !=
    b"RGB"`` branch of ``profile_finish``, which is not really an error (the
    Argyll run did succeed) so much as a "nothing more to do" signal.
    """

    def __init__(self, profile: ICCProfile) -> None:
        self.profile = profile
        super().__init__(lang.getstr("profiling.complete"))


@dataclass
class BuiltProfile:
    """A validated profile built by ``worker.Worker.create_profile``."""

    profile: ICCProfile
    #: Whether the profile carries a ``vcgt`` (calibration curve) tag.
    has_cal: bool


def validate_built_profile(profile_path: str) -> BuiltProfile:
    """Load and validate a profile ``create_profile`` just built.

    Args:
        profile_path: Path to the built ``.icc``/``.icm`` file.

    Returns:
        The validated profile.

    Raises:
        ProfileFinishInvalidError: If the file cannot be read/parsed.
        ProfileFinishNotDisplayError: If it is not an RGB monitor profile.
    """
    try:
        profile = ICCProfile(profile_path)
    except (OSError, ICCProfileInvalidError) as exception:
        raise ProfileFinishInvalidError(
            f"{lang.getstr('profile.invalid')}\n{profile_path}"
        ) from exception
    has_cal = isinstance(profile.tags.get("vcgt"), VideoCardGammaType)
    if profile.profileClass != b"mntr" or profile.colorSpace != b"RGB":
        raise ProfileFinishNotDisplayError(profile)
    return BuiltProfile(profile=profile, has_cal=has_cal)


#: ``(meta GAMUT_coverage/GAMUT_volume key, display label, reference volume)``.
_GAMUTS = (
    ("srgb", "sRGB", GAMUT_VOLUME_SRGB),
    ("adobe-rgb", "Adobe RGB", GAMUT_VOLUME_ADOBERGB),
    ("dci-p3", "DCI P3", GAMUT_VOLUME_SMPTE431_P3),
)


def format_completion_extra(profile: ICCProfile) -> str:
    """Build the self-check / gamut coverage summary for a completion message.

    Ports the ``meta`` tag readout in ``profile_finish`` (the ``extra`` self-
    check lines plus the ``cinfo``/``vinfo`` gamut coverage/volume figures,
    which wx renders in a separate bold-labelled grid rather than folded into
    the message text -- simplified here into one plain-text block since the
    Qt port uses a single ``QMessageBox`` rather than reproducing that grid).

    Args:
        profile: The validated built profile.

    Returns:
        A summary string, or ``""`` if the profile carries no ``meta`` tag.
    """
    if "meta" not in profile.tags:
        return ""
    lines = []

    self_check = []
    for key in ("avg", "max", "rms"):
        try:
            delta_e = float(profile.tags.meta.getvalue(f"ACCURACY_dE76_{key}"))
        except (TypeError, ValueError):
            continue
        self_check.append(f"{lang.getstr(f'profile.self_check.{key}')} {delta_e:.2f}")
    if self_check:
        lines.append(f"{lang.getstr('profile.self_check')}: {', '.join(self_check)}")

    cinfo = []
    for key, name, _volume in _GAMUTS:
        try:
            coverage = profile.tags.meta.getvalue(f"GAMUT_coverage({key})")
            coverage = float(coverage) if coverage is not None else None
        except (TypeError, ValueError):
            coverage = None
        if coverage:
            cinfo.append(f"{coverage:.1%} {name}")
    if cinfo:
        lines.append(f"{lang.getstr('gamut.coverage')}: {', '.join(cinfo)}")

    vinfo = []
    try:
        gamut_volume = float(profile.tags.meta.getvalue("GAMUT_volume"))
    except (TypeError, ValueError):
        gamut_volume = None
    if gamut_volume:
        for _key, name, volume in _GAMUTS:
            vinfo.append(f"{gamut_volume * GAMUT_VOLUME_SRGB / volume:.1%} {name}")
            if len(vinfo) == len(cinfo):
                break
    if vinfo:
        lines.append(f"{lang.getstr('gamut.volume')}: {', '.join(vinfo)}")

    return "\n".join(lines)


def sync_calibration_file_config(profile_path: str) -> bool:
    """Point ``calibration.file`` (and its dependents) at a newly built profile.

    Simplified port of the ``getcfg("calibration.file") != profile_path``
    branch in ``profile_finish``: always takes the "just point at the new
    file" path rather than wx's full ``load_cal_handler`` reload for the
    combined dispcal+colprof-options case (see module docstring).

    Args:
        profile_path: Path to the newly built profile.

    Returns:
        True if ``calibration.file`` actually changed (the caller should
        refresh anything driven by it, e.g. the calibration/profile combo).
    """
    if getcfg("calibration.file", False) == profile_path:
        return False
    setcfg("calibration.file", profile_path)
    setcfg("3dlut.output.profile", profile_path)
    setcfg("measurement_report.output_profile", profile_path)
    return True
