"""Check that an installed profile is really the one active for a monitor.

``Worker.install_profile`` reports what each backend (ArgyllCMS, colord,
Oyranos, the profile loader) *did*; it cannot tell whether the operating system
now actually uses the profile for the display. A finished process is not a
verified result, so after installing we read back the profile the OS reports
for the display and compare profile IDs.

Toolkit-neutral; the reader is injectable so the logic is testable without a
display.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

MATCH = "match"
MISMATCH = "mismatch"
NONE_ACTIVE = "none_active"
UNREADABLE = "unreadable"


@dataclass(frozen=True)
class ProfileCheck:
    """Result of comparing the installed profile with the active one."""

    status: str
    #: Description of the profile the OS reports as active (may be empty).
    active_description: str = ""

    @property
    def verified(self) -> bool:
        """True only when the active profile is the one that was installed."""
        return self.status == MATCH

    @property
    def message_key(self) -> str:
        """Language key of a plain-language explanation."""
        return f"guide.verify.{self.status}"


def _default_reader(display_no: int | None) -> object | None:
    from DisplayCAL.config import get_display_profile

    return get_display_profile(display_no)


def verify_active_profile(
    profile_path: str,
    display_no: int | None = None,
    *,
    read_active: Callable[[int | None], object | None] | None = None,
) -> ProfileCheck:
    """Compare ``profile_path`` with the profile active for ``display_no``.

    Args:
        profile_path: The profile that was just installed.
        display_no: Zero-based display index (``None`` = the configured one).
        read_active: Optional reader returning the active ICC profile object;
            defaults to :func:`DisplayCAL.config.get_display_profile`.

    Returns:
        A :class:`ProfileCheck`; ``verified`` is true only on an ID match.
    """
    from DisplayCAL.icc_profile import ICCProfile

    reader = read_active or _default_reader
    try:
        installed = ICCProfile(profile_path)
    except Exception:  # noqa: BLE001 - any read failure means "cannot confirm"
        return ProfileCheck(UNREADABLE)
    try:
        active = reader(display_no)
    except Exception:  # noqa: BLE001
        return ProfileCheck(UNREADABLE)
    if active is None:
        return ProfileCheck(NONE_ACTIVE)
    try:
        description = active.getDescription()
    except Exception:  # noqa: BLE001 - description is cosmetic
        description = ""
    try:
        same = installed.calculate_id(False) == active.calculate_id(False)
    except Exception:  # noqa: BLE001
        return ProfileCheck(UNREADABLE, description)
    return ProfileCheck(MATCH if same else MISMATCH, description)
