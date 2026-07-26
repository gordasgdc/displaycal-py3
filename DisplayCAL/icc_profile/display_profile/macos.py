"""macOS-specific display ICC profile get function."""

from __future__ import annotations

import platform
from typing import TYPE_CHECKING

from DisplayCAL.icc_profile.constants import FS_ENC
from DisplayCAL.util_list import intlist

if TYPE_CHECKING:
    from DisplayCAL.icc_profile import ICCProfile


def get_display_profile_macos(
    display_no: int = 0,
    path_only: bool = False,
) -> None | str | ICCProfile:
    """Return ICC Profile for the given display under macOS.

    Args:
        display_no (int, optional): The display number to query. Defaults to 0.
        path_only (bool, optional): If True, return the profile path as a
            string, otherwise return an ICCProfile object.

    Raises:
        OSError: If there is an error executing the AppleScript command.

    Returns:
        None | str | ICCProfile: The display profile path as a string or
            an ICCProfile object, or None if no profile is found.
    """
    from DisplayCAL.icc_profile import ICCProfile
    from DisplayCAL.util_mac import osascript

    if intlist(platform.mac_ver()[0].split(".")) >= [10, 6]:
        options = ["Image Events"]
    else:
        options = ["ColorSyncScripting"]

    for option in options:
        # applescript: one-based index
        applescript = [
            f'tell app "{option}"',
            "set displayProfile to location of display profile of "
            f"display {int(display_no + 1):d}",
            "return POSIX path of displayProfile",
            "end tell",
        ]
        retcode, output, errors = osascript(applescript)
        if retcode == 0 and output.strip():
            filename = output.strip("\n").decode(FS_ENC)
            profile = filename if path_only else ICCProfile(filename, use_cache=True)
        elif errors.strip():
            raise OSError(errors.strip())

    return profile
