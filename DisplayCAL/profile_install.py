"""Toolkit-neutral helpers for the profile install / load-on-login feature.

These are the pure pieces lifted out of ``MainFrame.install_profile_handler``,
``MainFrame.profile_finish`` and ``MainFrame.profile_finish_consumer``
(``display_cal.py``): profile validation, the install-scope offer decision, the
load-on-login checkbox label, and the install-result message derivation. None
of this carries a wx (or Qt) dependency, so both the shipping wx path and the
future Qt window call into it (a plain ``DisplayCAL`` module so importing it
never pulls in Qt, matching ``main_settings.py`` / ``measurement_report.py``).

The genuinely window-shaped parts (the install confirmation dialog, the
scope radio buttons, the Windows profile-loader IPC resync, and
``worker.Worker.install_profile`` itself) stay in their respective UI layers.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

from DisplayCAL import localization as lang
from DisplayCAL.icc_profile import ICCProfile


class ProfileUnsupportedError(Exception):
    """A profile is not installable (not an RGB monitor profile)."""

    def __init__(self, profile_class: bytes, color_space: bytes) -> None:
        self.profile_class = profile_class
        self.color_space = color_space
        super().__init__(
            lang.getstr("profile.unsupported", (profile_class, color_space))
        )


def load_installable_profile(profile_path: str) -> ICCProfile:
    """Load and validate a profile for installation.

    Ports the validation in ``install_profile_handler``: only ``mntr`` (display)
    profiles with an ``RGB`` color space can be installed.

    Args:
        profile_path: Path to the ``.icc``/``.icm`` file.

    Returns:
        The loaded profile.

    Raises:
        OSError | ICCProfileInvalidError: If the file cannot be read/parsed.
        ProfileUnsupportedError: If the profile is not an RGB monitor profile.
    """
    profile = ICCProfile(profile_path)
    if profile.profileClass != b"mntr" or profile.colorSpace != b"RGB":
        raise ProfileUnsupportedError(profile.profileClass, profile.colorSpace)
    return profile


def get_profile_load_on_login_label(os_cal: bool) -> str:
    """Get the label for the profile load on login checkbox.

    Args:
        os_cal: True if the OS calibration management is active.

    Returns:
        The label for the profile load on login checkbox.
    """
    label = lang.getstr("profile.load_on_login")
    if sys.platform == "win32" and not os_cal:
        lstr = lang.getstr("calibration.preserve")
        if lang.getcode() != "de":
            lstr = lstr[0].lower() + lstr[1:]
        label += " && " + lstr
    return label


def resolve_install_scope_options(
    *,
    argyll_version: list[int],
    is_superuser_or_sudo: bool,
    windows_version: tuple[int, ...] | None,
    network_profiles_dir_exists: bool,
    test_mode: bool = False,
) -> list[str]:
    """Determine which install-scope choices ("u"/"l"/"n") to offer.

    Ports the big boolean condition guarding the scope radio buttons in
    ``profile_finish``. Returns an empty list when only the (implicit) user
    scope is available, in which case the caller should force
    ``profile.install_scope`` to ``"u"`` without showing any radio buttons.

    Args:
        argyll_version: ``Worker.argyll_version``.
        is_superuser_or_sudo: ``os.geteuid() == 0 or which("sudo")`` (ignored
            on win32, where elevation works differently).
        windows_version: ``sys.getwindowsversion()`` tuple, or ``None`` off
            win32.
        network_profiles_dir_exists: Whether
            ``/Network/Library/ColorSync/Profiles`` exists (macOS only).
        test_mode: Force-enable, matching the wx ``TEST`` flag.

    Returns:
        A list containing any of ``"u"``, ``"l"``, ``"n"`` that should be
        offered. ``"u"`` (current user) is always first when the list is
        non-empty.
    """
    non_windows_dispwin_ok = sys.platform != "win32" and argyll_version >= [1, 1, 0]
    offer_non_user_scopes = (
        (
            (sys.platform == "darwin" or non_windows_dispwin_ok)
            and is_superuser_or_sudo
        )
        or (
            sys.platform == "win32"
            and windows_version is not None
            and windows_version >= (6,)
            and argyll_version > [1, 1, 1]
        )
        or test_mode
    )
    if not offer_non_user_scopes:
        return []
    options = ["u", "l"]
    if sys.platform == "darwin" and network_profiles_dir_exists:
        options.append("n")
    return options


@dataclass
class InstallResultSummary:
    """The outcome of :func:`summarize_install_result`."""

    #: ``"success"``, ``"warning"`` or ``"error"`` -> ``profile.install.<key>``.
    message_key: str
    #: True if every attempted install method reported success or ``None``.
    all_good: bool
    #: ``(method_name, ok, text)`` for each method that reported a result
    #: (``ok`` is True/False/None for warning), only populated when not
    #: ``all_good`` and relevant (Linux, where multiple install backends run).
    details: list[tuple[str, bool | None, str]] = field(default_factory=list)


def summarize_install_result(
    argyll_install: object,
    colord_install: object,
    oy_install: object,
    loader_install: object,
) -> InstallResultSummary:
    """Derive the install outcome message from ``Worker.install_profile``'s result.

    Ports the ``all_good`` / ``some_good`` / per-method breakdown in
    ``profile_finish_consumer``.

    Args:
        argyll_install: ArgyllCMS install result (``True``/``None``/exception).
        colord_install: colord install result.
        oy_install: Oyranos install result.
        loader_install: Profile loader install result.

    Returns:
        The summary to render (message key + optional per-method details).
    """
    results = (argyll_install, colord_install, oy_install, loader_install)
    all_good = all(result in (None, True) for result in results)
    some_good = any(result is True for result in results)
    linux = sys.platform not in ("darwin", "win32")
    if all_good:
        message_key = "success"
    elif some_good and linux:
        message_key = "warning"
    else:
        message_key = "error"
    details: list[tuple[str, bool | None, str]] = []
    if not all_good and linux:
        names = (
            "ArgyllCMS",
            "colord",
            "Oyranos",
            lang.getstr("profile_loader"),
        )
        for name, result in zip(names, results):
            if result is None:
                continue
            if result is True:
                details.append((name, True, lang.getstr("ok")))
            elif isinstance(result, Warning):
                details.append((name, None, str(result)))
            else:
                details.append((name, False, str(result) or lang.getstr("failure")))
    return InstallResultSummary(
        message_key=message_key, all_good=all_good, details=details
    )
