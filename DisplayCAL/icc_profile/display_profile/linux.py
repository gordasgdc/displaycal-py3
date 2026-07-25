"""Linux-specific display ICC profile get function."""

from __future__ import annotations

import binascii
import json
import os
import subprocess as sp
import sys
import warnings
from typing import TYPE_CHECKING

try:
    from DisplayCAL import colord
except ImportError:

    class Colord:
        """Dummy class for colord support."""

        Colord = None

        def quirk_manufacturer(self, manufacturer: str) -> str:
            """Quirk the manufacturer name.

            Args:
                manufacturer (str): The manufacturer name to quirk.

            Returns:
                str: The quirked manufacturer name.
            """
            return manufacturer

        def which(self, executable: str, paths: None | list[str] = None) -> None | str:
            """Check if an executable is available in the system paths.

            Args:
                executable (str): The name of the executable to check.
                paths (None | list[str], optional): List of paths to search for
                    the executable. If None, uses the system PATH.

            Returns:
                None | str: The full path to the executable if found, else None.
            """
            return

    colord = Colord()

if sys.platform not in ("darwin", "win32"):
    from DisplayCAL.defaultpaths import XDG_CONFIG_DIRS, XDG_CONFIG_HOME
from DisplayCAL.edid import get_edid
from DisplayCAL.icc_profile.constants import DEBUG
from DisplayCAL.util_os import dlopen, which
from DisplayCAL.util_x import get_display

try:
    from DisplayCAL import xrandr
except ImportError:
    xrandr = None

if TYPE_CHECKING:
    from DisplayCAL.icc_profile import ICCProfile


def _colord_get_display_profile(
    display_no: int = 0, path_only: bool = False, use_cache: bool = True
) -> None | str | ICCProfile:
    """Use a brute force way of getting display profile.

    Args:
        display_no (int): The display number to query.
        path_only (bool, optional): If True, return the profile path as a
            string, otherwise return an ICCProfile object.
        use_cache (bool, optional): If True, use cached profile if available.

    Returns:
        None | str | ICCProfile: The display profile path as a string or
            an ICCProfile object, or None if no profile is found.
    """
    from DisplayCAL.icc_profile import ICCProfile

    edid_ = get_edid(display_no)
    device_ids = []
    if edid_:
        # Try a range of possible device IDs
        dife = colord.device_id_from_edid
        device_ids = [
            dife(edid_, quirk=False, query=True),
            dife(edid_, quirk=True, truncate_edid_strings=True),
            dife(edid_, quirk=True, use_serial_32=False),
            dife(edid_, quirk=True, use_serial_32=False, truncate_edid_strings=True),
            dife(edid_, quirk=True),
            dife(edid_, quirk=False, truncate_edid_strings=True),
            dife(edid_, quirk=False, use_serial_32=False),
            dife(edid_, quirk=False, use_serial_32=False, truncate_edid_strings=True),
            # Try with manufacturer omitted
            dife(edid_, omit_manufacturer=True),
            dife(edid_, truncate_edid_strings=True, omit_manufacturer=True),
            dife(edid_, use_serial_32=False, omit_manufacturer=True),
            dife(
                edid_,
                use_serial_32=False,
                truncate_edid_strings=True,
                omit_manufacturer=True,
            ),
        ]
    else:
        # Fall back to XrandR name
        try:
            from DisplayCAL import real_display_size_mm
        except ImportError as exception:
            warnings.warn(str(exception), Warning, stacklevel=2)
            return None
        display = real_display_size_mm.get_display(display_no)
        if display:
            xrandr_name = display.get("xrandr_name")
            if xrandr_name:
                edid_ = {"monitor_name": xrandr_name}
                device_ids = [f"xrandr-{xrandr_name.decode()}"]
            elif os.getenv("XDG_SESSION_TYPE") == "wayland":
                # Preliminary Wayland support under non-GNOME desktops.
                # This still needs a lot of work.
                device_ids = colord.get_display_device_ids()
                if device_ids and display_no < len(device_ids):
                    edid_ = {
                        "monitor_name": device_ids[display_no].split("xrandr-", 1).pop()
                    }
                    device_ids = [device_ids[display_no]]
    if not edid_:
        return None
    for device_id in dict.fromkeys(device_ids):
        if not device_id:
            continue
        try:
            profile = colord.get_default_profile(device_id)
            profile_path = profile.properties.get("Filename")
        except colord.CDObjectQueryError:
            # Device ID was not found, try next one
            continue
        except colord.CDError as exception:
            warnings.warn(str(exception), Warning, stacklevel=2)
        except colord.DBusException as exception:
            warnings.warn(str(exception), Warning, stacklevel=2)
        else:
            if profile_path:
                if "hash" in edid_:
                    colord.device_ids[edid_["hash"]] = device_id
                if path_only:
                    print(
                        "Got profile from colord for display "
                        f"{int(display_no):d} ({device_id}):",
                        profile_path,
                    )
                    return profile_path
                return ICCProfile(profile_path, use_cache=use_cache)
        break
    return None


def _ucmm_get_display_profile(
    display_no: int, name: str | bytes, path_only: bool = False, use_cache: bool = True
) -> None | str | ICCProfile:
    """Argyll UCMM.

    Args:
        display_no (int): The display number to query.
        name (str | bytes): The display name to search for.
        path_only (bool, optional): If True, return the profile path as a
            string, otherwise return an ICCProfile object.
        use_cache (bool, optional): If True, use cached profile if available.

    Returns:
        None | str | ICCProfile: The display profile path as a string or
            an ICCProfile object, or None if no profile is found.
    """
    from DisplayCAL.icc_profile import ICCProfile

    search = []
    edid = get_edid(display_no)
    if edid:
        # Look for matching EDID entry first
        search.append((b"EDID", b"0x" + binascii.hexlify(edid["edid"]).upper()))
    # Fallback to X11 name
    search.append((b"NAME", name))
    for path in [XDG_CONFIG_HOME, *XDG_CONFIG_DIRS]:
        color_jcnf = os.path.join(path, "color.jcnf")
        if not os.path.isfile(color_jcnf):
            continue

        with open(color_jcnf) as f:
            data = json.load(f)
        displays = data.get("devices", {}).get("display")
        if not isinstance(displays, dict):
            continue

        # Look for matching entry
        for key, value in search:
            for item in displays.values():
                if not isinstance(item, dict):
                    continue
                if item.get(key) != value:
                    continue
                profile_path = item.get("ICC_PROFILE")
                if path_only:
                    print(
                        "Got profile from Argyll UCMM for display "
                        f"{int(display_no):d} ({key} {value}):",
                        profile_path,
                    )
                    return profile_path
                return ICCProfile(profile_path, use_cache=use_cache)
    return None


def get_display_profile_linux(
    display_no: int = 0,
    x_hostname: None | str = None,
    x_display: None | int = None,
    x_screen: None | int = None,
    path_only: bool = False,
) -> None | str | ICCProfile:
    """Return ICC Profile for the given display under Linux.

    Args:
        display_no (int): The display number to query.
        x_hostname (str, optional): The X server hostname.
        x_display (int, optional): The X display number.
        x_screen (int, optional): The X screen number.
        path_only (bool, optional): If True, return the profile path as a
            string, otherwise return an ICCProfile object.

    Returns:
        None | str | ICCProfile: The display profile path as a string or
            an ICCProfile object, or None if no profile is found.
    """
    from DisplayCAL.icc_profile import ICCProfile

    options = ["_ICC_PROFILE"]
    try:
        from DisplayCAL import real_display_size_mm
    except ImportError as exception:
        warnings.warn(str(exception), Warning, stacklevel=2)
        display = get_display()
    else:
        display = real_display_size_mm.get_x_display(display_no)
    if display:
        if x_hostname is None:
            x_hostname = display[0]
        if x_display is None:
            x_display = display[1]
        if x_screen is None:
            x_screen = display[2]
        x_display_name = f"{x_hostname}:{x_display}.{x_screen}"
    for option in options:
        # Linux
        # Try colord
        if colord.which("colormgr") and (
            profile := (_colord_get_display_profile(display_no, path_only=path_only))
        ):
            return profile
        if path_only:
            # No way to figure out the profile path from X atom, so use
            # Argyll's UCMM if libcolordcompat.so is not present
            if dlopen("libcolordcompat.so"):
                # UCMM configuration might be stale, ignore
                return None
            return _ucmm_get_display_profile(display_no, x_display_name, path_only)
        # Try XrandR
        if (
            xrandr
            and real_display_size_mm
            and option == "_ICC_PROFILE"
            and None not in (x_hostname, x_display, x_screen)
        ):
            with xrandr.XDisplay(x_display_name) as display:
                if DEBUG:
                    print("Using XrandR")
                for i, atom_id in enumerate(
                    [
                        real_display_size_mm.get_x_icc_profile_output_atom_id(
                            display_no
                        ),
                        real_display_size_mm.get_x_icc_profile_atom_id(display_no),
                    ]
                ):
                    if not atom_id:
                        continue
                    if i == 0:
                        meth = display.get_output_property
                        what = real_display_size_mm.get_xrandr_output_xid(display_no)
                    else:
                        meth = display.get_window_property
                        what = display.root_window(0)
                    try:
                        window_property = meth(what, atom_id)
                    except ValueError as exception:
                        warnings.warn(str(exception), Warning, stacklevel=2)
                    else:
                        if window_property and (
                            profile := ICCProfile(
                                b"".join(
                                    bytes(chr(n), "utf-8") for n in window_property
                                ),
                                use_cache=True,
                            )
                        ):
                            return profile
                    if DEBUG:
                        if i == 0:
                            print("Couldn't get _ICC_PROFILE XrandR output property")
                            print("Using X11")
                        else:
                            print("Couldn't get _ICC_PROFILE X atom")
            return None

        # Read up to 8 MB of any X properties
        if DEBUG:
            print("Using xprop")
        xprop = which("xprop")
        if not xprop:
            return None
        atom = "{}{}".format(option, "" if display_no == 0 else f"_{display_no}")
        tgt_proc = sp.Popen(
            [
                xprop,
                "-display",
                f"{x_hostname}:{x_display}.{x_screen}",
                "-len",
                "8388608",
                "-root",
                "-notype",
                atom,
            ],
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
        )
        stdout, stderr = [data.strip(b"\n") for data in tgt_proc.communicate()]
        if stdout:
            raw = [item.strip() for item in stdout.split("=")]
            if raw[0] == atom and len(raw) == 2:
                binary_data = "".join([chr(int(part)) for part in raw[1].split(", ")])
                profile = ICCProfile(binary_data, use_cache=True)
        elif stderr and tgt_proc.wait() != 0:
            raise OSError(stderr)
        if profile:
            break
    return profile
