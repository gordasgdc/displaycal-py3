"""Cross-platform display ICC profile get/set dispatch.

Submodules group the platform-specific implementations (`windows`, `macos`,
`linux`). This package re-exports the platform functions plus the
`get_display_profile()` dispatcher that picks the right one for the running
platform.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from DisplayCAL.icc_profile.display_profile.linux import get_display_profile_linux
from DisplayCAL.icc_profile.display_profile.macos import get_display_profile_macos
from DisplayCAL.icc_profile.display_profile.windows import (
    _winreg_get_display_profiles,
    get_display_profile_windows,
    set_display_profile,
    unset_display_profile,
)

if TYPE_CHECKING:
    from DisplayCAL.icc_profile import ICCProfile


def get_display_profile(
    display_no: int = 0,
    x_hostname: None | str = None,
    x_display: None | str = None,
    x_screen: None | int = None,
    path_only: bool = False,
    devicekey: None | str = None,
    use_active_display_device: bool = True,
    use_registry: bool = True,
) -> None | str | ICCProfile:
    """Return ICC Profile for display n or None.

    Args:
        display_no (int, optional): The display number to query. Defaults to 0.
        x_hostname (str, optional): The X server hostname.
        x_display (str, optional): The X display name.
        x_screen (int, optional): The X screen number.
        path_only (bool, optional): If True, return the profile path as a
            string, otherwise return an ICCProfile object.
        devicekey (None | str, optional): The device key to query. If None,
            the active display device will be used.
        use_active_display_device (bool, optional): If True, use the active
            display device, otherwise use the first display device.
        use_registry (bool, optional): If True, use the Windows registry to
            get the display profile.

    Returns:
        None | str | ICCProfile: The display profile path as a string or
            an ICCProfile object, or None if no profile is found.
    """
    if sys.platform == "win32":
        return get_display_profile_windows(
            display_no, path_only, devicekey, use_active_display_device, use_registry
        )
    if sys.platform == "darwin":
        return get_display_profile_macos(display_no, path_only)
    return get_display_profile_linux(
        display_no, x_hostname, x_display, x_screen, path_only
    )
