"""ICC profile utilities for color management across devices.

ICC profiles describe device or color space color characteristics for
consistent color reproduction. This module provides, utilities for parsing,
validating, and manipulating ICC profile data.
"""

from __future__ import annotations

import binascii
import contextlib
import ctypes
import datetime
import functools
import json
import math
import operator
import os
import pathlib
import platform
import re
import struct
import subprocess as sp
import sys
import warnings
from copy import copy
from hashlib import md5
from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    Callable,
    ClassVar,
    TextIO,
)
from weakref import WeakValueDictionary

if sys.platform == "win32":
    import winreg

    try:
        import win32api  # noqa: F401  # availability checked via sys.modules below
        import win32gui
    except ImportError:
        pass

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
from DisplayCAL import colormath, edid
from DisplayCAL.defaultpaths import ICCPROFILES, ICCPROFILES_HOME
from DisplayCAL.options import TEST_INPUT_CURVE_CLIPPING
from DisplayCAL.util_list import intlist

if sys.platform not in ("darwin", "win32"):
    from DisplayCAL.defaultpaths import XDG_CONFIG_DIRS, XDG_CONFIG_HOME
    from DisplayCAL.edid import get_edid
    from DisplayCAL.util_x import get_display

    try:
        from DisplayCAL import xrandr
    except ImportError:
        xrandr = None
    from DisplayCAL.util_os import dlopen, which
elif sys.platform == "win32":
    from DisplayCAL import util_win
    from DisplayCAL.mscms import WCSManagerProxy

    # WCS only available under Vista and later
    mscms = None if sys.getwindowsversion() < (6,) else WCSManagerProxy()


if TYPE_CHECKING:
    import multiprocessing
    import threading
    from typing import BinaryIO, TextIO

    from DisplayCAL.worker import Worker, Xicclu  # noqa: TC004

    if sys.version_info >= (3, 11):
        from typing import Self
    else:
        from typing_extensions import Self


from DisplayCAL.icc_profile.codecs import (
    dateTimeNumber,
    dateTimeNumber_tohex,
    hexrepr,
    legacy_PCSLab_dec_to_uInt16,
    legacy_PCSLab_uInt16_to_dec,
    s15f16_is_equal,
    s15Fixed16Number,
    s15Fixed16Number_tohex,
    u16Fixed16Number,
    u16Fixed16Number_tohex,
    uInt8Number,
    uInt8Number_tohex,
    uInt16Number,
    uInt16Number_tohex,
    uInt32Number,
    uInt32Number_tohex,
    uInt64Number,
    uInt64Number_tohex,
    videoCardGamma,
)
from DisplayCAL.icc_profile.constants import (
    CIIS,
    CMMS,
    COLOR_PROFILE_SUBTYPE,
    COLOR_PROFILE_TYPE,
    DEBUG,
    ENC,
    ENCODINGS,
    ERROR_PROFILE_NOT_ASSOCIATED_WITH_DEVICE,
    ERROR_SUCCESS,
    FS_ENC,
    GAMUT_VOLUME_ADOBERGB,
    GAMUT_VOLUME_SMPTE431_P3,
    GAMUT_VOLUME_SRGB,
    MANUFACTURERS,
    PLATFORM,
    PROFILE_CLASS,
    TAGS,
    TECH,
    WCS_PROFILE_MANAGEMENT_SCOPE,
)
from DisplayCAL.icc_profile.structures import (
    ADict,
    AODict,
    CRInterpolation,
    DictList,
    DictListItem,
)
from DisplayCAL.icc_profile.tags.base import (
    ChromaticAdaptionTag,
    DateTimeType,
    ICCProfileTag,
    LazyLoadTagAODict,
    S15Fixed16ArrayType,
    TagData,
    Text,
    XYZNumber,
    XYZType,
)
from DisplayCAL.icc_profile.tags.colorant import (
    ChromaticityType,
    Colorant,
    ColorantTableType,
    Geometry,
    Illuminant,
    MeasurementType,
    Observer,
    ProfileSequenceDescType,
    ViewingConditionsType,
)
from DisplayCAL.icc_profile.tags.curve import CurveType, ParametricCurveType
from DisplayCAL.icc_profile.tags.lut import LUT16Type


def create_RGB_A2B_XYZ(  # noqa: N802
    input_curves: list, clut: list, logfn: Callable = print
) -> LUT16Type:
    """Create RGB device A2B from input curve XYZ values and cLUT.

    Note that input curves and cLUT should already be adapted to D50.

    Args:
        input_curves (list): List of input curves for R, G, B channels.
        clut (list): cLUT data as a list of lists, where each inner list
            contains XYZ values for each grid point.
        logfn (Callable, optional): Function to log messages. Defaults to
            `print`.

    Returns:
        LUT16Type: An instance of LUT16Type representing the A2B table.
    """
    if len(input_curves) != 3:
        raise ValueError(f"Wrong number of input curves: {len(input_curves)}")

    white_XYZ = clut[-1][-1]  # noqa: N806
    clutres = len(clut[0])
    itable = LUT16Type(None, "A2B0")
    itable.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])

    # Input curve interpolation
    # Normlly the input curves would either be linear (= 1:1 mapping to
    # cLUT) or the respective tone response curve.
    # We use a overall linear curve that is 'bent' in <clutres> intervals
    # to accomodate the non-linear TRC. Thus, we can get away with much
    # fewer cLUT grid points.

    # Use higher interpolation size than actual number of curve entries
    steps = 2**15 + 1
    maxv = steps - 1.0

    fwd = []
    bwd = []
    for input_curve in input_curves:
        if isinstance(input_curve, (tuple, list)):
            linear = [v / (len(input_curve) - 1.0) for v in range(len(input_curve))]
            fwd.append(colormath.Interp(linear, input_curve, use_numpy=True))
            bwd.append(colormath.Interp(input_curve, linear, use_numpy=True))
        else:
            # Gamma
            fwd.append(lambda v, p=input_curve: colormath.special_pow(v, p))
            bwd.append(lambda v, p=input_curve: colormath.special_pow(v, 1.0 / p))
        itable.input.append([])
        itable.output.append([0, 65535])

    logfn("cLUT input curve segments:", clutres)
    for i in range(3):
        maxi = bwd[i](white_XYZ[1])
        segment = 1.0 / (clutres - 1.0) * maxi
        iv = 0.0
        prevpow = fwd[i](0.0)
        nextpow = fwd[i](segment)
        prevv = 0
        pprevpow = 0
        clipped = nextpow <= prevpow
        xp = []
        for j in range(steps):
            v = (j / maxv) * maxi
            if v > iv + segment:
                iv += segment
                prevpow = nextpow
                nextpow = fwd[i](iv + segment)
                clipped = nextpow <= prevpow
                logfn(
                    "#{:d} {}".format(int(iv * (clutres - 1)), "XYZ"[i]),
                    f"prev {prevpow:.6f}",
                    f"next {nextpow:.6f}",
                    "clip",
                    clipped,
                )
            if not clipped:
                prevs = 1.0 - (v - iv) / segment
                nexts = (v - iv) / segment
                vv = prevs * prevpow + nexts * nextpow
                prevv = v
                pprevpow = prevpow
            else:
                # Linearly interpolate
                vv = colormath.convert_range(v, prevv, 1, prevpow, 1)
            out = bwd[i](vv)
            xp.append(out)
        # Fill input curves from interpolated values
        interp = colormath.Interp(xp, list(range(steps)), use_numpy=True)
        entries = 2049
        threshold = bwd[i](pprevpow)
        k = None
        for j in range(entries):
            n = j / (entries - 1.0)
            v = interp(n) / maxv
            if clipped and n + (1 / (entries - 1.0)) > threshold:
                # Linear interpolate shaper for last n cLUT steps to prevent
                # clipping in shaper
                if k is None:
                    k = j
                    ov = v
                v = min(ov + (1.0 - ov) * ((j - k) / (entries - k - 1.0)), 1.0)
            # Slope limit for 16-bit encoding
            itable.input[i].append(max(v, j / 65535.0) * 65535)

    # Fill cLUT
    clut = list(clut)
    itable.clut = []
    # step = 1.0 / (clutres - 1.0)
    for _R in range(clutres):  # noqa: N806
        for _G in range(clutres):  # noqa: N806
            row = list(clut.pop(0))
            itable.clut.append([])
            for _B in range(clutres):  # noqa: N806
                X, Y, Z = row.pop(0)  # noqa: N806
                itable.clut[-1].append(
                    [max(v / white_XYZ[1] * 32768, 0) for v in (X, Y, Z)]
                )

    return itable


def create_synthetic_clut_profile(
    rgb_space: None | str | list | tuple,
    description: str,
    XYZbp: None | tuple = None,  # noqa: N803
    white_Y: float = 1.0,  # noqa: N803
    clutres: int = 9,
    entries: int = 2049,
    cat: str = "Bradford",
) -> ICCProfile:
    """Create a synthetic cLUT profile from a colorspace definition.

    Args:
        rgb_space (None | str | list | tuple): The RGB space to use for
            conversion. Defaults to sRGB if not set. If a string is given, it
            must be a valid RGB space name. If a list or tuple is given, it
            must be in the format (gamma, whitepoint, red, green, blue). The
            whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or int).
            The gamma should be a float. The RGB primaries red, green, blue
            should be lists or tuples of xyY coordinates (only x and y will be
            used, so Y can be zero or None).
        description (str): A description for the profile.
        XYZbp (None | tuple, optional): A tuple with the black point in XYZ
            format. If None, it will be derived from the RGB space.
        white_Y (float, optional): The Y value of the white point, default is
            1.0.
        clutres (int, optional): The number of grid points in the cLUT, default
            is 9.
        entries (int, optional): The number of entries in the input curves,
            default is 2049.
        cat (str, optional): Chromatic adaptation transform, default is
            "Bradford".

    Returns:
        ICCProfile: An instance of ICCProfile with the synthetic cLUT profile.
    """
    profile = ICCProfile()
    profile.version = 2.2  # Match ArgyllCMS

    profile.tags.desc = TextDescriptionType(b"", "desc")
    profile.tags.desc.ASCII = description
    profile.tags.cprt = TextType(b"text\0\0\0\0Public domain\0", "cprt")

    profile.tags.wtpt = XYZType(profile=profile)
    (
        profile.tags.wtpt.X,
        profile.tags.wtpt.Y,
        profile.tags.wtpt.Z,
    ) = colormath.get_whitepoint(rgb_space[1])

    profile.tags.arts = ChromaticAdaptionTag()
    profile.tags.arts.update(colormath.get_cat_matrix(cat))

    itable = profile.tags.A2B0 = LUT16Type(None, "A2B0", profile)
    itable.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])

    otable = profile.tags.B2A0 = LUT16Type(None, "B2A0", profile)
    Xr, Yr, Zr = colormath.adapt(  # noqa: N806
        *colormath.RGB2XYZ(1, 0, 0, rgb_space=rgb_space),
        whitepoint_source=rgb_space[1],
        cat=cat,
    )
    Xg, Yg, Zg = colormath.adapt(  # noqa: N806
        *colormath.RGB2XYZ(0, 1, 0, rgb_space=rgb_space),
        whitepoint_source=rgb_space[1],
        cat=cat,
    )
    Xb, Yb, Zb = colormath.adapt(  # noqa: N806
        *colormath.RGB2XYZ(0, 0, 1, rgb_space=rgb_space),
        whitepoint_source=rgb_space[1],
        cat=cat,
    )
    m1 = colormath.Matrix3x3(((Xr, Xg, Xb), (Yr, Yg, Yb), (Zr, Zg, Zb))).inverted()
    scale = 1 + (32767 / 32768.0)
    m3 = colormath.Matrix3x3(((scale, 0, 0), (0, scale, 0), (0, 0, scale)))
    otable.matrix = m1 * m3

    # Input curve interpolation
    # Normlly the input curves would either be linear (= 1:1 mapping to
    # cLUT) or the respective tone response curve.
    # We use a overall linear curve that is 'bent' in <clutres> intervals
    # to accomodate the non-linear TRC. Thus, we can get away with much
    # fewer cLUT grid points.

    # Use higher interpolation size than actual number of curve entries
    steps = 2**15 + 1
    maxv = steps - 1.0
    gammas = rgb_space[0]
    if not isinstance(gammas, (list, tuple)):
        gammas = [gammas]
    for i, gamma in enumerate(gammas):
        maxi = colormath.special_pow(white_Y, 1.0 / gamma)
        segment = 1.0 / (clutres - 1.0) * maxi
        iv = 0.0
        prevpow = 0.0
        nextpow = colormath.special_pow(segment, gamma)
        xp = []
        for j in range(steps):
            v = (j / maxv) * maxi
            if v > iv + segment:
                iv += segment
                prevpow = nextpow
                nextpow = colormath.special_pow(iv + segment, gamma)
            prevs = 1.0 - (v - iv) / segment
            nexts = (v - iv) / segment
            vv = prevs * prevpow + nexts * nextpow
            out = colormath.special_pow(vv, 1.0 / gamma)
            xp.append(out)
        interp = colormath.Interp(xp, list(range(steps)), use_numpy=True)

        # Create input curves
        itable.input.append([])
        otable.input.append([])
        for j in range(4096):
            otable.input[i].append(
                colormath.special_pow(j / 4095.0 * white_Y, 1.0 / gamma) * 65535
            )

        # Fill input curves from interpolated values
        for j in range(entries):
            v = j / (entries - 1.0)
            itable.input[i].append(interp(v) / maxv * 65535)

    # Fill remaining input curves from first input curve and create output curves
    for _ in range(3):
        if len(itable.input) < 3:
            itable.input.append(itable.input[0])
            otable.input.append(otable.input[0])
        itable.output.append([0, 65535])
        otable.output.append([0, 65535])

    # Create and fill cLUT
    itable.clut = []
    step = 1.0 / (clutres - 1.0)
    for R in range(clutres):  # noqa: N806
        for G in range(clutres):  # noqa: N806
            itable.clut.append([])
            for B in range(clutres):  # noqa: N806
                X, Y, Z = colormath.adapt(  # noqa: N806
                    *colormath.RGB2XYZ(
                        *[v * step * maxi for v in (R, G, B)], rgb_space=rgb_space
                    ),
                    whitepoint_source=rgb_space[1],
                    cat=cat,
                )
                X, Y, Z = colormath.blend_blackpoint(X, Y, Z, None, XYZbp)  # noqa: N806
                itable.clut[-1].append([max(v / white_Y * 32768, 0) for v in (X, Y, Z)])

    otable.clut = []
    for R in range(2):  # noqa: N806
        for G in range(2):  # noqa: N806
            otable.clut.append([])
            for B in range(2):  # noqa: N806
                otable.clut[-1].append([v * 65535 for v in (R, G, B)])

    return profile


def create_synthetic_smpte2084_clut_profile(
    rgb_space: None | str | list | tuple,
    description: str,
    black_cdm2: float = 0,
    white_cdm2: float = 400,
    master_black_cdm2: float = 0,
    master_white_cdm2: float = 10000,
    use_alternate_master_white_clip: bool = True,
    content_rgb_space: str = "DCI P3",
    rolloff: bool = True,
    clutres: int = 33,
    mode: str = "HSV_ICtCp",
    sat: float = 1.0,
    hue: float = 0.5,
    forward_xicclu: None | Xicclu = None,
    backward_xicclu: None | Xicclu = None,
    generate_B2A: bool = False,  # noqa: N803
    worker: None | Worker = None,
    logfile: None | TextIO = None,
    cat: str = "Bradford",
) -> ICCProfile:
    """Create a synthetic cLUT profile with SMPTE 2084 TRC from a colorspace definition.

    The roll-off saturation and hue preservation can be controlled with the
    `hue` and `sat` arguments.

    Args:
        rgb_space (None | str | list | tuple): The RGB space to use for
            conversion. Defaults to sRGB if not set. If a string is given, it
            must be a valid RGB space name. If a list or tuple is given, it
            must be in the format (gamma, whitepoint, red, green, blue). The
            whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or int).
            The gamma should be a float. The RGB primaries red, green, blue
            should be lists or tuples of xyY coordinates (only x and y will be
            used, so Y can be zero or None).
        description (str): Description of the profile.
        black_cdm2 (float): Black level in cd/m^2.
        white_cdm2 (float): White level in cd/m^2.
        master_black_cdm2 (float): Mastering display black level in cd/m^2.
        master_white_cdm2 (float): Mastering display white level in cd/m^2.
        use_alternate_master_white_clip (bool): Use alternate master white clip
            for PQ.
        content_rgb_space (str): RGB space for content, e.g. "DCI P3".
        rolloff (bool): Whether to apply roll-off. If False, raises NotImplementedError.
        clutres (int): Resolution of the cLUT.
        mode (str): Gamut mapping mode for roll-off. The gamut mapping mode
            when rolling off. Valid values:
                "HSV_ICtCp" (default, recommended)
                "ICtCp"
                "XYZ" (not recommended, unpleasing hue shift)
                "HSV" (not recommended, saturation loss)
                "RGB" (not recommended, saturation loss, pleasing hue shift)
        sat (float): Saturation preservation factor [0.0, 1.0]:
            0.0 = Favor luminance preservation over saturation
            1.0 = Favor saturation preservation over luminance
        hue (float): Selective hue preservation factor [0.0, 1.0]:
           0.0 = Allow hue shift for redorange/orange/yellowgreen towards
                 yellow to preserve more saturation and detail
           1.0 = Preserve hue
        forward_xicclu (callable): Forward XICCLU function, not used for HLG.
        backward_xicclu (callable): Backward XICCLU function, not used for HLG.
        generate_B2A (bool): Generate B2A table, not used for HLG.
        worker (callable): Worker function for parallel processing, not used here.
        logfile (file): Log file for output, can be None.
        cat (str): Chromatic adaptation transform, default is "Bradford".

    Returns:
        ICCProfile: A synthetic cLUT profile with SMPTE 2084 TRC.
    """
    if not rolloff:
        raise NotImplementedError("rolloff needs to be True")

    return create_synthetic_hdr_clut_profile(
        "PQ",
        rgb_space,
        description,
        black_cdm2,
        white_cdm2,
        master_black_cdm2,
        master_white_cdm2,
        use_alternate_master_white_clip,
        1.2,  # Not used for PQ
        5.0,  # Not used for PQ
        1.0,  # Not used for PQ
        content_rgb_space,
        clutres,
        mode,
        sat,
        hue,
        forward_xicclu,
        backward_xicclu,
        generate_B2A,
        worker,
        logfile,
        cat,
    )


def create_synthetic_hdr_clut_profile(
    hdr_format: str,
    rgb_space: None | str | list | tuple,
    description: str,
    black_cdm2: float = 0,
    white_cdm2: float = 400,
    master_black_cdm2: float = 0,  # Not used for HLG
    master_white_cdm2: float = 10000,  # Not used for HLG
    use_alternate_master_white_clip: bool = True,  # Not used for HLG
    system_gamma: float = 1.2,  # Not used for PQ
    ambient_cdm2: float = 5,  # Not used for PQ
    maxsignal: float = 1.0,  # Not used for PQ
    content_rgb_space: str = "DCI P3",
    clutres: int = 33,
    mode: str = "HSV_ICtCp",  # Not used for HLG
    sat: float = 1.0,  # Not used for HLG
    hue: float = 0.5,  # Not used for HLG
    forward_xicclu: None | Xicclu = None,
    backward_xicclu: None | Xicclu = None,
    generate_B2A: bool = False,  # noqa: N803
    worker: None | Worker = None,
    logfile: None | TextIO = None,
    cat: str = "Bradford",
) -> ICCProfile:
    """Create a synthetic HDR cLUT profile from a colorspace definition.

    Args:
        hdr_format (str): HDR format, either "PQ" or "HLG".
        rgb_space (None | str | list | tuple): The RGB space to use for
            conversion. Defaults to sRGB if not set. If a string is given, it
            must be a valid RGB space name. If a list or tuple is given, it
            must be in the format (gamma, whitepoint, red, green, blue). The
            whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or int).
            The gamma should be a float. The RGB primaries red, green, blue
            should be lists or tuples of xyY coordinates (only x and y will be
            used, so Y can be zero or None).
        description (str): Description of the profile.
        black_cdm2 (float): Black level in cd/m^2.
        white_cdm2 (float): White level in cd/m^2.
        master_black_cdm2 (int): Mastering display black level in cd/m^2.
        master_white_cdm2 (int): Mastering display white level in cd/m^2.
        use_alternate_master_white_clip (bool): Use alternate master white clip
            for PQ.
        system_gamma (float): System gamma, not used for PQ.
        ambient_cdm2 (float): Ambient light level in cd/m^2, not used for PQ.
        maxsignal (float): Maximum signal value, not used for PQ.
        content_rgb_space (str): RGB space for content, e.g. "DCI P3".
        clutres (int): Resolution of the cLUT.
        mode (str): Gamut mapping mode for roll-off, not used for HLG.
        sat (float): Saturation preservation factor for roll-off, not used for HLG.
        hue (float): Hue preservation factor for roll-off, not used for HLG.
        forward_xicclu (callable): Forward XICCLU function, not used for HLG.
        backward_xicclu (callable): Backward XICCLU function, not used for HLG.
        generate_B2A (bool): Generate B2A table, not used for HLG.
        worker (callable): Worker function for parallel processing, not used here.
        logfile (file): Log file for output, can be None.
        cat (str): Chromatic adaptation transform, default is "Bradford".

    Returns:
        ICCProfile: A synthetic HDR cLUT profile.
    """
    rgb_space = colormath.get_rgb_space(rgb_space)
    content_rgb_space = colormath.get_rgb_space(content_rgb_space)

    if hdr_format == "PQ":
        bt2390 = colormath.BT2390(
            black_cdm2,
            white_cdm2,
            master_black_cdm2,
            master_white_cdm2,
            use_alternate_master_white_clip,
        )
        # Preserve detail in saturated colors if mastering display peak < 10K cd/m2
        # XXX: Effect is detrimental to contrast at low target peak, and looks
        # artificial for BT.2390-4. Don't use for now.
        preserve_saturated_detail = False  # master_white_cdm2 < 10000
        if preserve_saturated_detail:
            bt2390s = colormath.BT2390(black_cdm2, white_cdm2, master_black_cdm2, 10000)

        maxv = white_cdm2 / 10000.0

        def eotf(v: float) -> float:
            """Electro-Optical Transfer Function (EOTF) for PQ.

            Args:
                v (float): Input value in range [0, 1].

            Returns:
                float: Output value in range [0, 1] after applying EOTF.
            """
            return colormath.special_pow(v, -2084)

        _oetf = eotf_inverse = lambda v: colormath.special_pow(v, 1.0 / -2084)
        eetf = bt2390.apply

        # Apply a slight power to the segments to optimize encoding
        encpow = min(max(bt2390.omaxi * (5 / 3.0), 1.0), 1.5)

        def encf(v: float) -> float:
            """Encoding function for PQ.

            Args:
                v (float): Input value in range [0, 1].

            Returns:
                float: Output value in range [0, 1] after applying encoding
                    function.
            """
            if v < bt2390.mmaxi:
                v = colormath.convert_range(v, 0, bt2390.mmaxi, 0, 1)
                v = colormath.special_pow(v, 1.0 / encpow, 2)
                return colormath.convert_range(v, 0, 1, 0, bt2390.mmaxi)
            return v

        def encf_inverse(v: float) -> float:
            """Inverse encoding function for PQ.

            Args:
                v (float): Input value in range [0, 1].

            Returns:
                float: Output value in range [0, 1] after applying inverse
                    encoding function.
            """
            if v < bt2390.mmaxi:
                v = colormath.convert_range(v, 0, bt2390.mmaxi, 0, 1)
                v = colormath.special_pow(v, encpow, 2)
                return colormath.convert_range(v, 0, 1, 0, bt2390.mmaxi)
            return v

    elif hdr_format == "HLG":
        # Note: Unlike the PQ black level lift, we apply HLG black offset as
        # separate final step, not as part of the HLG EOTF
        hlg = colormath.HLG(0, white_cdm2, system_gamma, ambient_cdm2, rgb_space)

        if maxsignal < 1:
            # Adjust EOTF so that EOTF[maxsignal] gives (approx) white_cdm2
            while hlg.eotf(maxsignal) * hlg.white_cdm2 < white_cdm2:
                hlg.white_cdm2 += 1

        lscale = 1.0 / hlg.oetf(1.0, True)
        hlg.white_cdm2 *= lscale
        if lscale < 1 and logfile:
            logfile.write(
                f"Nominal peak luminance after scaling = {hlg.white_cdm2:.2f}\n"
            )

        Ymax = hlg.eotf(maxsignal)  # noqa: N806

        maxv = 1.0
        eotf = hlg.eotf

        def eotf_inverse(v: float) -> float:
            """Inverse Electro-Optical Transfer Function (EOTF) for HLG.

            Args:
                v (float): Input value in range [0, 1].

            Returns:
                float: Output value in range [0, 1] after applying inverse EOTF.
            """
            return hlg.eotf(v, True)

        _oetf = hlg.oetf

        def eetf(v: float) -> float:
            """Rolloff encoding function for HLG.

            Args:
                v (float): Input value in range [0, 1].

            Returns:
                float: Output value in range [0, 1] after applying encoding
                    function.
            """
            return v

        def encf(v: float) -> float:
            """Encoding function for HLG.

            Args:
                v (float): Input value in range [0, 1].

            Returns:
                float: Output value in range [0, 1] after applying encoding
                    function.
            """
            return v
    else:
        raise NotImplementedError(f"Unknown HDR format {hdr_format!r}")

    tonemap = eetf(1) != 1

    profile = ICCProfile()
    profile.version = 2.2  # Match ArgyllCMS

    profile.tags.desc = TextDescriptionType(b"", "desc")
    profile.tags.desc.ASCII = description
    profile.tags.cprt = TextType(b"text\0\0\0\0Public domain\0", "cprt")

    profile.tags.wtpt = XYZType(profile=profile)
    (
        profile.tags.wtpt.X,
        profile.tags.wtpt.Y,
        profile.tags.wtpt.Z,
    ) = colormath.get_whitepoint(rgb_space[1])

    profile.tags.arts = ChromaticAdaptionTag()
    profile.tags.arts.update(colormath.get_cat_matrix(cat))

    itable = profile.tags.A2B0 = LUT16Type(None, "A2B0", profile)
    itable.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])
    # HDR RGB
    debugtable0 = profile.tags.DBG0 = LUT16Type(None, "DBG0", profile)
    debugtable0.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])
    # Display RGB
    debugtable1 = profile.tags.DBG1 = LUT16Type(None, "DBG1", profile)
    debugtable1.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])
    # Display XYZ
    debugtable2 = profile.tags.DBG2 = LUT16Type(None, "DBG2", profile)
    debugtable2.matrix = colormath.Matrix3x3([(1, 0, 0), (0, 1, 0), (0, 0, 1)])

    if generate_B2A:
        otable = profile.tags.B2A0 = LUT16Type(None, "B2A0", profile)
        Xr, Yr, Zr = colormath.adapt(  # noqa: N806
            *colormath.RGB2XYZ(1, 0, 0, rgb_space=rgb_space),
            whitepoint_source=rgb_space[1],
            cat=cat,
        )
        Xg, Yg, Zg = colormath.adapt(  # noqa: N806
            *colormath.RGB2XYZ(0, 1, 0, rgb_space=rgb_space),
            whitepoint_source=rgb_space[1],
            cat=cat,
        )
        Xb, Yb, Zb = colormath.adapt(  # noqa: N806
            *colormath.RGB2XYZ(0, 0, 1, rgb_space=rgb_space),
            whitepoint_source=rgb_space[1],
            cat=cat,
        )
        m1 = colormath.Matrix3x3(((Xr, Xg, Xb), (Yr, Yg, Yb), (Zr, Zg, Zb)))
        m2 = m1.inverted()
        scale = 1 + (32767 / 32768.0)
        m3 = colormath.Matrix3x3(((scale, 0, 0), (0, scale, 0), (0, 0, scale)))
        otable.matrix = m2 * m3

    # Input curve interpolation
    # Normlly the input curves would either be linear (= 1:1 mapping to
    # cLUT) or the respective tone response curve.
    # We use a overall linear curve that is 'bent' in <clutres> intervals
    # to accomodate the non-linear TRC. Thus, we can get away with much
    # fewer cLUT grid points.

    # Use higher interpolation size than actual number of curve entries
    steps = 2**15 + 1
    maxstep = steps - 1.0
    segment = 1.0 / (clutres - 1.0)
    iv = 0.0
    prevpow = eotf(eetf(0))
    # Apply a slight power to segments to optimize encoding
    nextpow = eotf(eetf(encf(segment)))
    prevv = 0
    pprevpow = [0]
    # clipped = False
    xp = []
    if generate_B2A:
        oxp = []
    for j in range(steps):
        v = j / maxstep
        if v > iv + segment:
            iv += segment
            prevpow = nextpow
            # Apply a slight power to segments to optimize encoding
            nextpow = eotf(eetf(encf(iv + segment)))
        if nextpow > prevpow or TEST_INPUT_CURVE_CLIPPING:
            prevs = 1.0 - (v - iv) / segment
            nexts = (v - iv) / segment
            vv = prevs * prevpow + nexts * nextpow
            prevv = v
            if prevpow > pprevpow[-1]:
                pprevpow.append(prevpow)
        else:
            # clipped = True
            # Linearly interpolate
            vv = colormath.convert_range(v, prevv, 1, prevpow, 1)
        out = eotf_inverse(vv)
        xp.append(out)
        if generate_B2A:
            oxp.append(eotf(eetf(v)) / maxv)
    interp = colormath.Interp(xp, list(range(steps)), use_numpy=True)
    if generate_B2A:
        ointerp = colormath.Interp(oxp, list(range(steps)), use_numpy=True)

    # Save interpolation input values for diagnostic purposes
    profile.tags.kTRC = CurveType()
    interp_inverse = colormath.Interp(list(range(steps)), xp, use_numpy=True)
    profile.tags.kTRC[:] = [
        interp_inverse(colormath.convert_range(v, 0, 2048, 0, maxstep)) * 65535
        for v in range(2049)
    ]

    # Create input and output curves
    for _i in range(3):
        itable.input.append([])
        itable.output.append([0, 65535])
        debugtable0.input.append([0, 65535])
        debugtable0.output.append([0, 65535])
        debugtable1.input.append([0, 65535])
        debugtable1.output.append([0, 65535])
        debugtable2.input.append([0, 65535])
        debugtable2.output.append([0, 65535])
        if generate_B2A:
            otable.input.append([])
            otable.output.append([0, 65535])

    # Generate device-to-PCS shaper curves from interpolated values
    if logfile:
        logfile.write("Generating device-to-PCS shaper curves...\n")
    entries = 1025
    prevperc = 0
    endperc = 1 if generate_B2A else 2
    threshold = eotf_inverse(pprevpow[-2])
    k = None
    end = eotf_inverse(pprevpow[-1])
    l = entries - 1
    if end > threshold:
        for j in range(entries):
            n = j / (entries - 1.0)
            if eetf(n) > end:
                l = j - 1
                break
    for j in range(entries):
        if worker and worker.thread_abort:
            if forward_xicclu:
                forward_xicclu.exit()
            if backward_xicclu:
                backward_xicclu.exit()
            raise Exception("aborted")
        n = j / (entries - 1.0)
        v = interp(eetf(n)) / maxstep
        if hdr_format == "PQ":
            # threshold = 1.0 - segment * math.ceil((1.0 - bt2390.mmaxi) *
            # (clutres - 1.0) + 1)
            # check = n >= threshold
            check = tonemap and eetf(n + (1 / (entries - 1.0))) > threshold
        elif hdr_format == "HLG":
            check = maxsignal < 1 and n >= maxsignal
        if check and not TEST_INPUT_CURVE_CLIPPING:
            # Linear interpolate shaper for last n cLUT steps to prevent
            # clipping in shaper
            if k is None:
                k = j
                ov = v
                ev = interp(eetf(l / (entries - 1.0))) / maxstep
            # v = min(ov + (1.0 - ov) * ((j - k) / (entries - k - 1.0)), 1.0)
            v = min(colormath.convert_range(j, k, l, ov, ev), n)
        for i in range(3):
            itable.input[i].append(v * 65535)
        perc = math.floor(n * endperc)
        if logfile and perc > prevperc:
            logfile.write(f"\r{perc:.0f}%")
            prevperc = perc
    startperc = perc

    if generate_B2A:
        # Generate PCS-to-device shaper curves from interpolated values
        if logfile:
            logfile.write("\rGenerating PCS-to-device shaper curves...\n")
            logfile.write(f"\r{perc:.0f}%")
        for j in range(4096):
            if worker and worker.thread_abort:
                if forward_xicclu:
                    forward_xicclu.exit()
                if backward_xicclu:
                    backward_xicclu.exit()
                raise Exception("aborted")
            n = j / 4095.0
            v = ointerp(n) / maxstep * 65535
            for i in range(3):
                otable.input[i].append(v)
            perc = startperc + math.floor(n)
            if logfile and perc > prevperc:
                logfile.write(f"\r{perc:.0f}%")
                prevperc = perc
        startperc = perc

    # Scene RGB -> HDR tone mapping -> HDR XYZ -> backward lookup -> display RGB
    itable.clut = []
    debugtable0.clut = []
    debugtable1.clut = []
    debugtable2.clut = []
    clutmax = clutres - 1.0
    step = 1.0 / clutmax
    count = 0
    # Lpt is the preferred mode for chroma blending. Some preliminary visual
    # comparison has shown it does overall the best job preserving hue and
    # saturation (blue hues superior to IPT). DIN99d is the second best,
    # but vibrant red turns slightly orange when desaturated (DIN99d has best
    # blue saturation preservation though).
    blendmode = "Lpt"
    IPT_white_XYZ = colormath.get_cat_matrix("IPT").inverted() * (1, 1, 1)  # noqa: N806
    Cmode = ("all", "primaries_secondaries")[0]  # noqa: N806
    RGB_in = []  # noqa: N806
    HDR_ICtCp = []  # noqa: N806
    HDR_RGB = []  # noqa: N806
    HDR_XYZ = []  # noqa: N806
    HDR_min_I = []  # noqa: N806
    logmsg = "\rGenerating lookup table"
    if hdr_format == "PQ" and tonemap:
        logmsg += " and applying HDR tone mapping"
        endperc = 25
    else:
        endperc = 50
    if logfile:
        logfile.write(f"{logmsg}...\n")
        logfile.write(f"\r{perc:.0f}%")
    # Selective hue preservation for redorange/orange
    # (otherwise shift towards yellow to preserve more saturation and detail)
    # Hue angles (RGB):
    # red, yellow, yellow, green, red
    hinterp = colormath.Interp(
        [0, 0.166666, 0.166666, 1], [1, hue, 1, 1], use_numpy=True
    )
    # Saturation adjustment for yellow/green/cyan
    # Hue angles (RGB):
    # red, orange, yellow, green, cyan, cyan/blue, red
    sinterp = colormath.Interp(
        [0, 0.083333, 0.166666, 0.333333, 0.5, 0.583333, 1],
        [1, 1, 0.5, 0.5, 0.5, 1, 1],
        use_numpy=True,
    )
    for R in range(clutres):  # noqa: N806
        for G in range(clutres):  # noqa: N806
            for B in range(clutres):  # noqa: N806
                if worker and worker.thread_abort:
                    if forward_xicclu:
                        forward_xicclu.exit()
                    if backward_xicclu:
                        backward_xicclu.exit()
                    raise Exception("aborted")
                # Apply a slight power to the segments to optimize encoding
                RGB = [encf(v * step) for v in (R, G, B)]  # noqa: N806
                RGB_in.append(tuple(RGB))
                if DEBUG and R == G == B:
                    print("RGB {:5.3f} {:5.3f} {:5.3f}".format(*RGB), end=" ")
                # RGB_sum = sum(RGB)
                if hdr_format == "PQ" and mode in (
                    "HSV",
                    "HSV_ICtCp",
                    "ICtCp",
                    "RGB_ICtCp",
                ):
                    # Record original hue angle, saturation and value
                    H, S, V = colormath.RGB2HSV(*RGB)  # noqa: N806
                if hdr_format == "PQ" and mode in ("HSV_ICtCp", "ICtCp", "RGB_ICtCp"):
                    I1, Ct1, Cp1 = colormath.RGB2ICtCp(  # noqa: N806
                        *RGB, rgb_space=rgb_space, eotf=eotf, oetf=eotf_inverse
                    )
                    if DEBUG and R == G == B:
                        print(
                            f"-> ICtCp {I1:5.3f} {Ct1:5.3f} {Cp1:5.3f}",
                            end=" ",
                        )
                    I2 = eetf(I1)  # noqa: N806
                    if preserve_saturated_detail and S:
                        sf = S
                        I2 *= 1 - sf  # noqa: N806
                        I2 += bt2390s.apply(I1) * sf  # noqa: N806
                if hdr_format == "HLG":
                    X, Y, Z = hlg.RGB2XYZ(*RGB)  # noqa: N806
                    if Y:
                        Y1 = Y  # noqa: N806
                        I1 = hlg.eotf(Y, True)  # noqa: N806
                        I2 = min(I1, maxsignal)  # noqa: N806
                        Y2 = hlg.eotf(I2)  # noqa: N806
                        Y3 = Y2 / Ymax  # noqa: N806
                        X, Y, Z = (v / Y * Y3 if Y else v for v in (X, Y, Z))  # noqa: N806
                        if R == G == B and logfile and DEBUG:
                            logfile.write(
                                f"\rE {Y1:.4f} -> E' {I1:.4f} -> roll-off -> "
                                f"{I2:.4f} -> E {Y2:.4f} -> "
                                f"scale ({Y3 / Y2:.0%}) -> {Y3:.4f}\n"
                            )
                elif mode == "XYZ":
                    X, Y, Z = colormath.RGB2XYZ(*RGB, rgb_space=rgb_space, eotf=eotf)  # noqa: N806
                    if Y:
                        I1 = colormath.special_pow(Y, 1.0 / -2084)  # noqa: N806
                        I2 = eetf(I1)  # noqa: N806
                        Y2 = colormath.special_pow(I2, -2084)  # noqa: N806
                        X, Y, Z = (v / Y * Y2 for v in (X, Y, Z))  # noqa: N806
                    else:
                        I1 = I2 = 0  # noqa: N806
                elif mode in ("HSV", "HSV_ICtCp", "ICtCp", "RGB", "RGB_ICtCp"):
                    if mode in ("HSV", "RGB"):
                        I1 = max(RGB)  # noqa: N806
                    if mode in ("HSV", "HSV_ICtCp", "ICtCp", "RGB_ICtCp"):
                        # Allow hue shift based on hue angle
                        hf = hinterp(H)

                        # Saturation adjustment
                        cf = sinterp(H)
                    for i, v in enumerate(RGB):
                        RGB[i] = eetf(v)  # noqa: N806
                        if preserve_saturated_detail and S:
                            sf = S
                            RGB[i] *= 1 - sf  # noqa: N806
                            RGB[i] += bt2390s.apply(v) * sf  # noqa: N806
                    RGB_shifted = RGB  # Potentially hue shifted RGB  # noqa: N806
                    if mode in ("HSV", "HSV_ICtCp"):
                        HSV = list(colormath.RGB2HSV(*RGB_shifted))  # noqa: N806

                        if mode == "HSV":
                            # Allow hue shift based on hue angle
                            H = H * hf + HSV[0] * (1 - hf)  # noqa: N806

                        # Set hue angle
                        HSV[0] = H  # noqa: N806
                        RGB = colormath.HSV2RGB(*HSV)  # noqa: N806
                    if mode in ("HSV", "RGB"):
                        I2 = max(RGB)  # noqa: N806
                elif mode == "YRGB":
                    LinearRGB = [eotf(v) for v in RGB]  # noqa: N806
                    I1 = (  # noqa: N806
                        0.2627 * LinearRGB[0]
                        + 0.678 * LinearRGB[1]
                        + 0.0593 * LinearRGB[2]
                    )
                    I2 = eotf(eetf(eotf_inverse(I1)))  # noqa: N806
                    min_I = I2 / I1 if I1 else 1  # noqa: N806
                    RGB = [eotf_inverse(min_I * v) for v in LinearRGB]  # noqa: N806
                if (
                    hdr_format == "PQ"
                    and mode in ("HSV_ICtCp", "ICtCp", "RGB_ICtCp", "XYZ")
                    and I1
                    and I2
                ):
                    if mode != "ICtCp" or (forward_xicclu and backward_xicclu):
                        # Don't desaturate colors which are lighter after
                        # roll-off if mode is not ICtCp or if doing
                        # display-based desaturation
                        dsat = 1.0
                    else:
                        # Desaturate colors which are lighter after roll-off
                        # if mode is ICtCp and not doing display-based
                        # desaturation
                        dsat = I1 / I2
                    min_I = min(dsat, I2 / I1)  # noqa: N806
                else:
                    min_I = 1  # noqa: N806
                if hdr_format == "PQ" and mode in ("HSV_ICtCp", "ICtCp", "RGB_ICtCp"):
                    if DEBUG and R == G == B:
                        print(f"* {min_I:5.3f}", "->", end=" ")
                    Ct2, Cp2 = (min_I * v for v in (Ct1, Cp1))  # noqa: N806
                    if DEBUG and R == G == B:
                        print(f"{I2:5.3f} {Ct2:5.3f} {Cp2:5.3f}", "->", end=" ")
                if hdr_format == "HLG":
                    pass
                elif mode == "XYZ":
                    X, Y, Z = colormath.XYZsaturation(X, Y, Z, min_I, rgb_space[1])[0]  # noqa: N806
                    RGB = colormath.XYZ2RGB(X, Y, Z, rgb_space, oetf=eotf_inverse)  # noqa: N806
                elif mode == "ICtCp":
                    X, Y, Z = colormath.ICtCp2XYZ(I2, Ct2, Cp2)  # noqa: N806
                    RGB = colormath.XYZ2RGB(  # noqa: N806
                        X, Y, Z, rgb_space, clamp=False, oetf=eotf_inverse
                    )
                if DEBUG and R == G == B:
                    print("RGB {:5.3f} {:5.3f} {:5.3f}".format(*RGB))
                HDR_RGB.append(RGB)
                if hdr_format == "HLG":
                    pass
                elif mode not in ("XYZ", "ICtCp"):
                    X, Y, Z = colormath.RGB2XYZ(*RGB, rgb_space=rgb_space, eotf=eotf)  # noqa: N806
                if hdr_format == "PQ" and mode in ("HSV_ICtCp", "ICtCp", "RGB_ICtCp"):
                    # Use hue and chroma from ICtCp
                    I, Ct, Cp = colormath.XYZ2ICtCp(X, Y, Z)  # noqa: N806
                    L, C, H = colormath.Lab2LCHab(I * 100, Ct * 100, Cp * 100)  # noqa: N806
                    L2, C2, H2 = colormath.Lab2LCHab(I2 * 100, Ct2 * 100, Cp2 * 100)  # noqa: N806

                    # Allow hue shift based on hue angle
                    I3, Ct3, Cp3 = colormath.RGB2ICtCp(  # noqa: N806
                        *RGB_shifted, rgb_space=rgb_space, eotf=eotf, oetf=eotf_inverse
                    )
                    L3, C3, H3 = colormath.Lab2LCHab(I3 * 100, Ct3 * 100, Cp3 * 100)  # noqa: N806
                    L = L * hf + L3 * (1 - hf)  # noqa: N806
                    C = C * hf + C3 * (1 - hf)  # noqa: N806
                    H2 = H2 * hf + H3 * (1 - hf)  # noqa: N806

                    # Saturation adjustment
                    C = colormath.convert_range(I1, I2, 1, C2, min(C2, C) * cf)  # noqa: N806
                    I, Ct2, Cp2 = (v / 100.0 for v in colormath.LCHab2Lab(L, C, H2))  # noqa: N806
                    Ct, Cp = Ct2, Cp2  # noqa: N806
                    if I1 > I2:
                        f = colormath.convert_range(I1, I2, 1, 1, 0)
                        Ct2, Cp2 = (v * f for v in (Ct2, Cp2))  # noqa: N806
                    if mode in ("HSV_ICtCp", "RGB_ICtCp"):
                        f = colormath.convert_range(sum(RGB_in[-1]), 0, 3, 1, sat)
                        Ct2 = Ct * f + Ct2 * (1 - f)  # noqa: N806
                        Cp2 = Cp * f + Cp2 * (1 - f)  # noqa: N806
                        I2 = I * f + I2 * (1 - f)  # noqa: N806
                    X, Y, Z = colormath.ICtCp2XYZ(I2, Ct2, Cp2)  # noqa: N806
                RGB_ICtCp_XYZ = [X, Y, Z]  # noqa: N806
                # X, Y, Z = (v / maxv for v in (X, Y, Z))
                HDR_XYZ.append((RGB_in[-1], [X, Y, Z], RGB_ICtCp_XYZ))
                HDR_min_I.append(min_I)
                count += 1
                perc = startperc + math.floor(
                    count / clutres**3.0 * (endperc - startperc)
                )
                if logfile and perc > prevperc:
                    logfile.write(f"\r{perc:.0f}%")
                    prevperc = perc

    if hdr_format == "PQ" and tonemap:
        from DisplayCAL.multiprocess import cpu_count, pool_slice

        num_cpus = cpu_count()
        num_workers = num_cpus
        if num_cpus > 2:
            num_workers -= 1
        num_batches = clutres // 6

        HDR_XYZ = functools.reduce(  # noqa: N806
            operator.iadd,
            pool_slice(
                _mp_hdr_tonemap,
                HDR_XYZ,
                (rgb_space, maxv, sat, cat),
                {},
                num_workers,
                worker and worker.thread_abort,
                logfile,
                num_batches,
                perc,
            ),
            [],
        )
        prevperc = startperc = perc = 75
    else:
        prevperc = startperc = perc = 50

    for i, item in enumerate(HDR_XYZ):
        if not item and worker and worker.thread_abort:  # Aborted
            if forward_xicclu:
                forward_xicclu.exit()
            if backward_xicclu:
                backward_xicclu.exit()
            raise Exception("aborted")
        (RGB, (X, Y, Z), RGB_ICtCp_XYZ) = item  # noqa: N806
        I, Ct, Cp = colormath.XYZ2ICtCp(X, Y, Z, oetf=eotf_inverse)  # noqa: N806
        X, Y, Z = (v / maxv for v in (X, Y, Z))  # noqa: N806
        HDR_ICtCp.append((I, Ct, Cp))
        # Adapt to D50
        X, Y, Z = colormath.adapt(X, Y, Z, whitepoint_source=rgb_space[1], cat=cat)  # noqa: N806
        if max(X, Y, Z) * 32768 > 65535 or min(X, Y, Z) < 0 or round(Y, 6) > 1:
            # This should not happen
            print(
                f"#{i}",
                "RGB {:.3f} {:.3f} {:.3f}".format(*RGB),
                f"XYZ {X:.6f} {Y:.6f} {Z:.6f}",
                "not in range [0,1]",
            )
        HDR_XYZ[i] = (X, Y, Z)  # noqa: N806
        perc = startperc + math.floor(i / clutres**3.0 * (100 - startperc))
        if logfile and perc > prevperc:
            logfile.write(f"\r{perc:.0f}%")
            prevperc = perc
    prevperc = startperc = perc = 0

    if forward_xicclu and backward_xicclu and logfile:
        logfile.write("\rDoing backward lookup...\n")
        logfile.write(f"\r{perc:.0f}%")
    count = 0
    from DisplayCAL.worker import Xicclu

    for _i, (X, Y, Z) in enumerate(HDR_XYZ):  # noqa: N806
        if worker and worker.thread_abort:
            if forward_xicclu:
                forward_xicclu.exit()
            if backward_xicclu:
                backward_xicclu.exit()
            raise Exception("aborted")
        if forward_xicclu and backward_xicclu and Cmode != "primaries_secondaries":
            # HDR XYZ -> backward lookup -> display RGB
            backward_xicclu((X, Y, Z))
            count += 1
            perc = startperc + math.floor(count / clutres**3.0 * (100 - startperc))
            if logfile and perc > prevperc and isinstance(backward_xicclu, Xicclu):
                logfile.write(f"\r{perc:.0f}%")
                prevperc = perc
    prevperc = startperc = perc = 0

    Cdiff = []  # noqa: N806
    Cmax = {}  # noqa: N806
    Cdmax = {}  # noqa: N806
    if forward_xicclu and backward_xicclu:
        # Display RGB -> forward lookup -> display XYZ
        backward_xicclu.close()
        try:
            display_RGB = backward_xicclu.get()  # noqa: N806
        except Exception:
            if forward_xicclu:
                # Make sure resources are not held in use
                forward_xicclu.exit()
            raise
        finally:
            backward_xicclu.exit()
        if logfile:
            logfile.write("\rDoing forward lookup...\n")
            logfile.write(f"\r{perc:.0f}%")

        # Smooth
        row = 0
        for _ in range(clutres):
            for _ in range(clutres):
                debugtable1.clut.append([])
                for _ in range(clutres):
                    RGBdisp = display_RGB[row]  # noqa: N806
                    debugtable1.clut[-1].append(
                        [min(max(v * 65535, 0), 65535) for v in RGBdisp]
                    )
                    row += 1
        debugtable1.smooth()
        display_RGB = []  # noqa: N806
        for block in debugtable1.clut:
            for row in block:
                display_RGB.append([v / 65535.0 for v in row])

        from DisplayCAL.worker import Xicclu

        for i, (R, G, B) in enumerate(display_RGB):  # noqa: N806
            if worker and worker.thread_abort:
                if forward_xicclu:
                    forward_xicclu.exit()
                if backward_xicclu:
                    backward_xicclu.exit()
                raise Exception("aborted")
            forward_xicclu((R, G, B))
            perc = startperc + math.floor((i + 1) / clutres**3.0 * (100 - startperc))
            if logfile and perc > prevperc and isinstance(forward_xicclu, Xicclu):
                logfile.write(f"\r{perc:.0f}%")
                prevperc = perc
        prevperc = startperc = perc = 0

        if Cmode == "primaries_secondaries":
            # Compare to chroma of content primaries/secondaries to determine
            # general chroma compression factor
            forward_xicclu((0, 0, 1))
            forward_xicclu((0, 1, 0))
            forward_xicclu((1, 0, 0))
            forward_xicclu((0, 1, 1))
            forward_xicclu((1, 0, 1))
            forward_xicclu((1, 1, 0))
        forward_xicclu.close()
        display_XYZ = forward_xicclu.get()  # noqa: N806
        if Cmode == "primaries_secondaries":
            for i in range(6):
                if i == 0:
                    # Blue
                    j = clutres - 1
                elif i == 1:
                    # Green
                    j = clutres**2 - clutres
                elif i == 2:
                    # Red
                    j = clutres**3 - clutres**2
                elif i == 3:
                    # Cyan
                    j = clutres**2 - 1
                elif i == 4:
                    # Magenta
                    j = clutres**3 - clutres**2 + clutres - 1
                elif i == 5:
                    # Yellow
                    j = clutres**3 - clutres
                R, G, B = RGB_in[j]  # noqa: N806
                XYZsrc = HDR_XYZ[j]  # noqa: N806
                XYZdisp = display_XYZ[-(6 - i)]  # noqa: N806
                XYZc = colormath.RGB2XYZ(R, G, B, content_rgb_space, eotf=eotf)  # noqa: N806
                XYZc = colormath.adapt(  # noqa: N806
                    *XYZc, whitepoint_source=content_rgb_space[1], cat=cat
                )
                L, C, H = colormath.XYZ2DIN99dLCH(*(v * 100 for v in XYZc))  # noqa: N806
                Ld, Cd, Hd = colormath.XYZ2DIN99dLCH(*(v * 100 for v in XYZdisp))  # noqa: N806
                Cdmaxk = tuple(map(round, (Ld, Hd)))  # noqa: N806
                if C > Cmax.get(Cdmaxk, -1):  # noqa: SIM300
                    Cmax[Cdmaxk] = C
                Cdiff.append(min(Cd / C, 1.0))
                if Cd > Cdmax.get(Cdmaxk, -1):
                    Cdmax[Cdmaxk] = Cd
                print(f"RGB in {R:5.2f} {G:5.2f} {B:5.2f}")
                print(
                    "Content BT2020 XYZ (DIN99d) {:5.2f} {:5.2f} {:5.2f}".format(
                        *(v * 100 for v in XYZc)
                    )
                )
                print(f"Content BT2020 LCH (DIN99d) {L:5.2f} {C:5.2f} {H:5.2f}")
                print(
                    "Display XYZ {:5.2f} {:5.2f} {:5.2f}".format(
                        *(v * 100 for v in XYZdisp)
                    )
                )
                print(f"Display LCH (DIN99d) {Ld:5.2f} {Cd:5.2f} {Hd:5.2f}")
                if logfile:
                    logfile.write(
                        "\r{} chroma compression factor: {:6.4f}\n".format(
                            {0: "B", 1: "G", 2: "R", 3: "C", 4: "M", 5: "Y"}[i],
                            Cdiff[-1],
                        )
                    )
            # Tweak so that it gives roughly 0.91 for a Rec. 709 target
            general_compression_factor = (sum(Cdiff) / len(Cdiff)) * 0.99
    else:
        display_RGB = False  # noqa: N806
        display_XYZ = False  # noqa: N806

    display_LCH = []  # noqa: N806
    if Cmode != "primaries_secondaries" and display_XYZ:
        # Determine compression factor by comparing display to content
        # colorspace in BT.2020
        if logfile:
            logfile.write("\rDetermining chroma compression factors...\n")
            logfile.write(f"\r{perc:.0f}%")
        for i, XYZsrc in enumerate(HDR_XYZ):  # noqa: N806
            if worker and worker.thread_abort:
                if forward_xicclu:
                    forward_xicclu.exit()
                if backward_xicclu:
                    backward_xicclu.exit()
                raise Exception("aborted")

            XYZdisp = display_XYZ[i] if display_XYZ else XYZsrc  # noqa: N806
            # # Adjust luminance from destination to source
            # Ydisp = XYZdisp[1]
            # if Ydisp:
            #     XYZdisp = [v / Ydisp * XYZsrc[1] for v in XYZdisp]
            X, Y, Z = (v * maxv for v in XYZsrc)  # noqa: N806
            X, Y, Z = colormath.adapt(  # noqa: N806
                X, Y, Z, whitepoint_destination=content_rgb_space[1], cat=cat
            )
            R, G, B = colormath.XYZ2RGB(X, Y, Z, content_rgb_space, oetf=eotf_inverse)  # noqa: N806
            XYZc = colormath.RGB2XYZ(R, G, B, content_rgb_space, eotf=eotf)  # noqa: N806
            XYZc = colormath.adapt(  # noqa: N806
                *XYZc,
                whitepoint_source=content_rgb_space[1],
                whitepoint_destination=rgb_space[1],
                cat=cat,
            )
            RGBc_r2020 = colormath.XYZ2RGB(  # noqa: N806
                *XYZc, rgb_space=rgb_space, oetf=eotf_inverse
            )
            XYZc_r2020 = colormath.RGB2XYZ(*RGBc_r2020, rgb_space=rgb_space, eotf=eotf)  # noqa: N806
            if blendmode == "ICtCp":
                I, Ct, Cp = colormath.XYZ2ICtCp(*XYZc_r2020, oetf=eotf_inverse)  # noqa: N806
                L, C, H = colormath.Lab2LCHab(I * 100, Cp * 100, Ct * 100)  # noqa: N806
                XYZdispa = colormath.adapt(  # noqa: N806
                    *XYZdisp, whitepoint_destination=rgb_space[1], cat=cat
                )
                Id, Ctd, Cpd = colormath.XYZ2ICtCp(  # noqa: N806
                    *(v * maxv for v in XYZdispa), oetf=eotf_inverse
                )
                Ld, Cd, Hd = colormath.Lab2LCHab(Id * 100, Cpd * 100, Ctd * 100)  # noqa: N806
            elif blendmode == "IPT":
                XYZc_r2020 = colormath.adapt(  # noqa: N806
                    *XYZc_r2020,
                    whitepoint_source=rgb_space[1],
                    whitepoint_destination=IPT_white_XYZ,
                    cat=cat,
                )
                I, CP, CT = colormath.XYZ2IPT(*XYZc_r2020)  # noqa: N806
                L, C, H = colormath.Lab2LCHab(I * 100, CP * 100, CT * 100)  # noqa: N806
                XYZdispa = colormath.adapt(  # noqa: N806
                    *XYZdisp, whitepoint_destination=IPT_white_XYZ, cat=cat
                )
                Id, Pd, Td = colormath.XYZ2IPT(*XYZdispa)  # noqa: N806
                Ld, Cd, Hd = colormath.Lab2LCHab(Id * 100, Pd * 100, Td * 100)  # noqa: N806
            elif blendmode == "Lpt":
                XYZc_r2020 = colormath.adapt(  # noqa: N806
                    *XYZc_r2020, whitepoint_source=rgb_space[1], cat=cat
                )
                L, p, t = colormath.XYZ2Lpt(*(v / maxv * 100 for v in XYZc_r2020))  # noqa: N806
                L, C, H = colormath.Lab2LCHab(L, p, t)  # noqa: N806
                Ld, pd, td = colormath.XYZ2Lpt(*(v * 100 for v in XYZdisp))  # noqa: N806
                Ld, Cd, Hd = colormath.Lab2LCHab(Ld, pd, td)  # noqa: N806
            elif blendmode == "XYZ":
                XYZc_r2020 = colormath.adapt(  # noqa: N806
                    *XYZc_r2020, whitepoint_source=rgb_space[1], cat=cat
                )
                wx, wy = colormath.XYZ2xyY(*colormath.get_whitepoint())[:2]
                x, y, Y = colormath.XYZ2xyY(*XYZc_r2020)  # noqa: N806
                x -= wx
                y -= wy
                L, C, H = colormath.Lab2LCHab(*(v * 100 for v in (Y, x, y)))  # noqa: N806
                x, y, Y = colormath.XYZ2xyY(*XYZdisp)  # noqa: N806
                x -= wx
                y -= wy
                Ld, Cd, Hd = colormath.Lab2LCHab(*(v * 100 for v in (Y, x, y)))  # noqa: N806
            else:
                # DIN99d
                XYZc_r202099 = colormath.adapt(  # noqa: N806
                    *XYZc_r2020, whitepoint_source=rgb_space[1], cat=cat
                )
                L, C, H = colormath.XYZ2DIN99dLCH(  # noqa: N806
                    *(v / maxv * 100 for v in XYZc_r202099)
                )
                Ld, Cd, Hd = colormath.XYZ2DIN99dLCH(*(v * 100 for v in XYZdisp))  # noqa: N806
            Cdmaxk = tuple(map(round, (Ld, Hd), (2, 2)))  # noqa: N806
            if C > Cmax.get(Cdmaxk, -1):  # noqa: SIM300
                Cmax[Cdmaxk] = C
            if C:
                # print(f"{Cd:6.3f} {C:6.3f}")
                Cdiff.append(min(Cd / C, 1.0))
            # if Cdiff[-1] < 0.0001:
            #     raise RuntimeError(
            #         f"#{i} RGB {R:5.3f} {G:5.3f} {B:5.3f} Cdiff {Cdiff[-1]:5.3f}"
            #     )
            else:
                Cdiff.append(1.0)
            display_LCH.append((Ld, Cd, Hd))
            if Cd > Cdmax.get(Cdmaxk, -1):
                Cdmax[Cdmaxk] = Cd
            if DEBUG:
                print("RGB in {:5.2f} {:5.2f} {:5.2f}".format(*RGB_in[i]))
                print(f"RGB out {R:5.2f} {G:5.2f} {B:5.2f}")
                print(
                    "Content BT2020 XYZ {:5.2f} {:5.2f} {:5.2f}".format(
                        *(v / maxv * 100 for v in XYZc_r2020)
                    )
                )
                print(f"Content BT2020 LCH {L:5.2f} {C:5.2f} {H:5.2f}")
                print(
                    "Display XYZ {:5.2f} {:5.2f} {:5.2f}".format(
                        *(v * 100 for v in XYZdisp)
                    )
                )
                print(f"Display LCH {Ld:5.2f} {Cd:5.2f} {Hd:5.2f}")
            perc = startperc + math.floor(i / clutres**3.0 * (80 - startperc))
            if logfile and perc > prevperc:
                logfile.write(f"\r{perc:.0f}%")
                prevperc = perc
        startperc = perc

        general_compression_factor = sum(Cdiff) / len(Cdiff)

    if display_XYZ:
        Cmaxv = max(Cmax.values())  # noqa: N806
        # Cdmaxv = max(Cdmax.values())

    if logfile and display_LCH and Cmode == "primaries_secondaries":
        logfile.write(
            f"\rChroma compression factor: {general_compression_factor:6.4f}\n"
        )

    # Chroma compress to display XYZ
    if logfile:
        if display_XYZ:
            logfile.write("\rApplying chroma compression and filling cLUT...\n")
        else:
            logfile.write("\rFilling cLUT...\n")
        logfile.write(f"\r{perc:.0f}%")
    row = 0
    oog_count = 0
    # if forward_xicclu:
    #     forward_xicclu.spawn()
    # if backward_xicclu:
    #     backward_xicclu.spawn()
    for col_0 in range(clutres):
        for col_1 in range(clutres):
            itable.clut.append([])
            debugtable0.clut.append([])
            if not display_RGB:
                debugtable1.clut.append([])
            debugtable2.clut.append([])
            for col_2 in range(clutres):
                if worker and worker.thread_abort:
                    if forward_xicclu:
                        forward_xicclu.exit()
                    if backward_xicclu:
                        backward_xicclu.exit()
                    raise Exception("aborted")
                R, G, B = HDR_RGB[row]  # noqa: N806
                I, Ct, Cp = HDR_ICtCp[row]  # noqa: N806
                X, Y, Z = HDR_XYZ[row]  # noqa: N806
                min_I = HDR_min_I[row]  # noqa: N806
                if not (col_0 == col_1 == col_2) and display_XYZ:
                    # Desaturate based on compression factor
                    if display_LCH:
                        blend = 1
                    else:
                        # Blending threshold: Don't desaturate dark colors
                        # (< 26 cd/m2). Preserves more "pop"
                        thresh_I = 0.381  # noqa: N806
                        blend = min_I * min(
                            max((I - thresh_I) / (0.5081 - thresh_I), 0), 1
                        )
                    if blend:
                        if blendmode == "XYZ":
                            wx, wy = colormath.XYZ2xyY(*colormath.get_whitepoint())[:2]
                            x, y, Y = colormath.XYZ2xyY(X, Y, Z)  # noqa: N806
                            x -= wx
                            y -= wy
                            L, C, H = colormath.Lab2LCHab(*(v * 100 for v in (Y, x, y)))  # noqa: N806
                        elif blendmode == "ICtCp":
                            L, C, H = colormath.Lab2LCHab(I * 100, Cp * 100, Ct * 100)  # noqa: N806
                        elif blendmode == "DIN99d":
                            XYZ = X, Y, Z  # noqa: N806
                            L, C, H = colormath.XYZ2DIN99dLCH(*[v * 100 for v in XYZ])  # noqa: N806
                        elif blendmode == "IPT":
                            XYZ = colormath.adapt(  # noqa: N806
                                X, Y, Z, whitepoint_destination=IPT_white_XYZ, cat=cat
                            )
                            I, CP, CT = colormath.XYZ2IPT(*XYZ)  # noqa: N806
                            L, C, H = colormath.Lab2LCHab(I * 100, CP * 100, CT * 100)  # noqa: N806
                        elif blendmode == "Lpt":
                            XYZ = X, Y, Z  # noqa: N806
                            L, p, t = colormath.XYZ2Lpt(*[v * 100 for v in XYZ])  # noqa: N806
                            L, C, H = colormath.Lab2LCHab(L, p, t)  # noqa: N806
                        if blendmode:
                            if display_LCH:
                                Ld, Cd, Hd = display_LCH[row]  # noqa: N806
                                # Cdmaxk = tuple(map(round, (Ld, Hd), (2, 2)))
                                # # Lookup HDR max chroma for given display
                                # # luminance and hue
                                # HCmax = Cmax[Cdmaxk]
                                # if C and HCmax:
                                #     # Lookup display max chroma for given display
                                #     # luminance and hue
                                #     HCdmax = Cdmax[Cdmaxk]
                                #     # Display max chroma in 0..1 range
                                #     maxCc = min(HCdmax / HCmax, 1.0)
                                #     KSCc = 1.5 * maxCc - 0.5
                                #     # HDR chroma in 0..1 range
                                #     Cc1 = min(C / HCmax, 1.0)
                                #     if Cc1 >= KSCc <= 1 and maxCc > KSCc >= 0:
                                #         # Roll-off chroma
                                #         Cc2 = bt2390.apply(
                                #             Cc1, KSCc, maxCc, 1.0, 0, normalize=False
                                #         )
                                #         C = HCmax * Cc2
                                #     else:
                                #         # Use display chroma as-is (clip)
                                #         if debug:
                                #             print(
                                #                 "CLUT grid point "
                                #                 f"{int(col_0):d} {int(col_1):d} "
                                #                 f"{int(col_2):d}: "
                                #                 f"C {C:6.4f} Cd {Cd:6.4f} "
                                #                 f"HCmax {HCmax:6.4f} "
                                #                 f"maxCc {maxCc:6.4f} "
                                #                 f"KSCc {KSCc:6.4f} "
                                #                 f"Cc1 {Cc1:6.4f}"
                                #             )
                                #         C = Cd
                                if C:
                                    C *= min(Cd / C, 1.0)  # noqa: N806
                                    C *= min(Ld / L, 1.0)  # noqa: N806
                            else:
                                Cc = general_compression_factor  # noqa: N806
                                Cc **= C / Cmaxv  # noqa: N806
                                C = C * (1 - blend) + (C * Cc) * blend  # noqa: N806
                        if blendmode == "ICtCp":
                            I, Cp, Ct = [  # noqa: N806
                                v / 100.0 for v in colormath.LCHab2Lab(L, C, H)
                            ]
                            XYZ = colormath.ICtCp2XYZ(I, Ct, Cp, eotf=eotf)  # noqa: N806
                            X, Y, Z = (v / maxv for v in XYZ)  # noqa: N806
                            # Adapt to D50
                            X, Y, Z = colormath.adapt(  # noqa: N806
                                X, Y, Z, whitepoint_source=rgb_space[1], cat=cat
                            )
                        elif blendmode == "DIN99d":
                            L, a, b = colormath.DIN99dLCH2Lab(L, C, H)  # noqa: N806
                            X, Y, Z = colormath.Lab2XYZ(L, a, b)  # noqa: N806
                        elif blendmode == "IPT":
                            I, CP, CT = [  # noqa: N806
                                v / 100.0 for v in colormath.LCHab2Lab(L, C, H)
                            ]
                            X, Y, Z = colormath.IPT2XYZ(I, CP, CT)  # noqa: N806
                            # Adapt to D50
                            X, Y, Z = colormath.adapt(  # noqa: N806
                                X, Y, Z, whitepoint_source=IPT_white_XYZ, cat=cat
                            )
                        elif blendmode == "Lpt":
                            L, p, t = colormath.LCHab2Lab(L, C, H)  # noqa: N806
                            X, Y, Z = colormath.Lpt2XYZ(L, p, t)  # noqa: N806
                        elif blendmode == "XYZ":
                            Y, x, y = [v / 100.0 for v in colormath.LCHab2Lab(L, C, H)]  # noqa: N806
                            x += wx
                            y += wy
                            X, Y, Z = colormath.xyY2XYZ(x, y, Y)  # noqa: N806
                    else:
                        print(
                            "CLUT grid point "
                            f"{int(col_0):d} {int(col_1):d} {int(col_2):d}: blend = 0"
                        )
                # if backward_xicclu and forward_xicclu:
                #     backward_xicclu((X, Y, Z))
                # else:
                #     HDR_XYZ[row] = (X, Y, Z)
                #     row += 1
                #     perc = startperc + math.floor(row / clutres ** 3.0 *
                #     (90 - startperc))
                # if logfile and perc > prevperc:
                #     logfile.write(f"\r{perc:.0f}%")
                # prevperc = perc
                # startperc = perc

                # if backward_xicclu and forward_xicclu:
                # # Get XYZ clipped to display RGB
                # backward_xicclu.exit()
                # for R, G, B in backward_xicclu.get():
                # forward_xicclu((R, G, B))
                # forward_xicclu.exit()
                # display_XYZ = forward_xicclu.get()
                # else:
                # display_XYZ = HDR_XYZ
                # row = 0
                # for a in range(clutres):
                # for b in range(clutres):
                # itable.clut.append([])
                # debugtable0.clut.append([])
                # for c in range(clutres):
                # if worker and worker.thread_abort:
                # if forward_xicclu:
                # forward_xicclu.exit()
                # if backward_xicclu:
                # backward_xicclu.exit()
                # raise Exception("aborted")
                # X, Y, Z = display_XYZ[row]
                itable.clut[-1].append(
                    [min(max(v * 32768, 0), 65535) for v in (X, Y, Z)]
                )
                debugtable0.clut[-1].append(
                    [min(max(v * 65535, 0), 65535) for v in (R, G, B)]
                )
                if not display_RGB:
                    debugtable1.clut[-1].append([0, 0, 0])
                XYZdisp = display_XYZ[row] if display_XYZ else [0, 0, 0]  # noqa: N806
                debugtable2.clut[-1].append(
                    [min(max(v * 65535, 0), 65535) for v in XYZdisp]
                )
                row += 1
                perc = startperc + math.floor(row / clutres**3.0 * (100 - startperc))
                if logfile and perc > prevperc:
                    logfile.write(f"\r{perc:.0f}%")
                    prevperc = perc
    prevperc = startperc = perc = 0

    if DEBUG:
        print("Num OOG:", oog_count)

    if generate_B2A:
        if logfile:
            logfile.write("\rGenerating PCS-to-device table...\n")

        otable.clut = []
        count = 0
        for R in range(clutres):  # noqa: N806
            for G in range(clutres):  # noqa: N806
                otable.clut.append([])
                for B in range(clutres):  # noqa: N806
                    RGB = [v * step for v in (R, G, B)]  # noqa: N806
                    X, Y, Z = colormath.RGB2XYZ(*RGB, rgb_space=rgb_space, eotf=eotf)  # noqa: N806
                    if hdr_format == "PQ":
                        I1, Ct1, Cp1 = colormath.XYZ2ICtCp(X, Y, Z)  # noqa: N806
                        I2 = eetf(I1)  # noqa: N806
                        Ct2, Cp2 = (min(I1 / I2, I2 / I1) * v for v in (Ct1, Cp1))  # noqa: N806
                        RGB = colormath.ICtCp2RGB(I1, Ct2, Cp2, rgb_space)  # noqa: N806
                    else:
                        RGB = hlg.XYZ2RGB(X, Y, Z)  # noqa: N806
                    if (
                        max(X, Y, Z) * 32768 > 65535
                        or min(X, Y, Z) < 0
                        or round(Y, 6) > 1
                        or max(RGB) > 1
                        or min(RGB) < 0
                    ):
                        print(
                            f"#{count:d}",
                            "RGB {:.3f} {:.3f} {:.3f}".format(*RGB),
                            f"XYZ {X:.6f} {Y:.6f} {Z:.6f}",
                            "not in range [0,1]",
                        )
                    otable.clut[-1].append([min(max(v, 0), 1) * 65535 for v in RGB])
                    count += 1

    if logfile:
        logfile.write("\n")

    if forward_xicclu:
        forward_xicclu.exit()
    if backward_xicclu:
        backward_xicclu.exit()

    if hdr_format == "HLG" and black_cdm2:
        # Apply black offset
        XYZbp = colormath.get_whitepoint(scale=black_cdm2 / float(white_cdm2))  # noqa: N806
        if logfile:
            logfile.write("Applying black offset...\n")
        profile.tags.A2B0.apply_black_offset(
            XYZbp, logfile=logfile, thread_abort=worker and worker.thread_abort
        )

    return profile


def create_synthetic_hlg_clut_profile(
    rgb_space: None | str | list | tuple,
    description: str,
    black_cdm2: float = 0,
    white_cdm2: float = 400,
    system_gamma: float = 1.2,
    ambient_cdm2: float = 5,
    maxsignal: float = 1.0,
    content_rgb_space: str = "DCI P3",
    rolloff: bool = True,
    clutres: int = 33,
    mode: str = "HSV_ICtCp",
    forward_xicclu: None | Xicclu = None,
    backward_xicclu: None | Xicclu = None,
    generate_B2A: bool = True,  # noqa: N803
    worker: None | Worker = None,
    logfile: None | TextIO = None,
    cat: str = "Bradford",
) -> ICCProfile:
    """Create a synthetic cLUT profile with the HLG TRC from a colorspace definition.

    mode:  The gamut mapping mode when rolling off. Valid values:
           "RGB_ICtCp" (default, recommended)
           "ICtCp"
           "XYZ" (not recommended, unpleasing hue shift)
           "HSV" (not recommended, saturation loss)
           "RGB" (not recommended, saturation loss, pleasing hue shift)

    Args:
        rgb_space (None | str | list | tuple): The RGB space to use for
            conversion. Defaults to sRGB if not set. If a string is given, it
            must be a valid RGB space name. If a list or tuple is given, it
            must be in the format (gamma, whitepoint, red, green, blue). The
            whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or int).
            The gamma should be a float. The RGB primaries red, green, blue
            should be lists or tuples of xyY coordinates (only x and y will be
            used, so Y can be zero or None).
        description (str): The profile description.
        black_cdm2 (float, optional): The black level in cd/m2. Defaults to 0.
        white_cdm2 (float, optional): The white level in cd/m2. Defaults to
            400.
        system_gamma (float, optional): The system gamma value. Defaults to
            1.2.
        ambient_cdm2 (float, optional): The ambient light level in cd/m2.
            Defaults to 5.
        maxsignal (float, optional): The maximum signal value. Defaults to 1.0.
        content_rgb_space (str, optional): The RGB colorspace of the content.
            Defaults to "DCI P3".
        rolloff (bool, optional): If True, apply roll-off to the cLUT.
            Defaults to True.
        clutres (int, optional): The resolution of the cLUT. Defaults to 33.
        mode (str, optional): The gamut mapping mode when rolling off. Valid
            values: "RGB_ICtCp" (default, recommended), "ICtCp", "XYZ" (not
            recommended, unpleasing hue shift), "HSV" (not recommended,
            saturation loss), "RGB" (not recommended, saturation loss, pleasing
            hue shift).
        forward_xicclu (Xicclu, optional): An instance of Xicclu for forward
            color space conversion. If None, a new instance will be created.
        backward_xicclu (Xicclu, optional): An instance of Xicclu for backward
            color space conversion. If None, a new instance will be created.
        generate_B2A (bool, optional): If True, generate the PCS-to-device
            conversion table. Defaults to True.
        worker (Worker, optional): A Worker instance for threading support.
            Defaults to None.
        logfile (TextIO, optional): A file-like object to log progress.
            Defaults to None.
        cat (str, optional): The chromatic adaptation transform to use.
            Defaults to "Bradford".

    Returns:
        ICCProfile: An ICCProfile object representing the synthetic HLG cLUT
            profile.
    """
    if not rolloff:
        raise NotImplementedError("rolloff needs to be True")

    return create_synthetic_hdr_clut_profile(
        "HLG",
        rgb_space,
        description,
        black_cdm2,
        white_cdm2,
        0,  # Not used for HLG
        10000,  # Not used for HLG
        True,  # Not used for HLG
        system_gamma,
        ambient_cdm2,
        maxsignal,
        content_rgb_space,
        clutres,
        mode,  # Not used for HLG
        1.0,  # Sat - Not used for HLG
        0.5,  # Hue - Not used for HLG
        forward_xicclu,
        backward_xicclu,
        generate_B2A,
        worker,
        logfile,
        cat,
    )


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


def _wcs_get_display_profile(
    devicekey: str,
    scope: int = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"],
    profile_type: int = COLOR_PROFILE_TYPE["ICC"],
    profile_subtype: int = COLOR_PROFILE_SUBTYPE["NONE"],
    profile_id: int = 0,
    path_only: bool = False,
    use_cache: bool = True,
) -> None | str | ICCProfile:
    """Get display profile using WCS API.

    Args:
        devicekey (str): The device key to query.
        scope (int, optional): The scope of the profile management.
        profile_type (int, optional): The type of the color profile.
        profile_subtype (int, optional): The subtype of the color profile.
        profile_id (int, optional): The ID of the color profile.
        path_only (bool, optional): If True, return the profile path as a
            string, otherwise return an ICCProfile object.
        use_cache (bool, optional): If True, use cached profile if available.

    Returns:
        None | str | ICCProfile: The display profile path as a string or
            an ICCProfile object, or None if no profile is found.
    """
    prof = mscms.get_default_color_profile(
        scope, devicekey, profile_type, profile_subtype, profile_id
    )
    if prof:
        if path_only:
            return os.path.join(ICCPROFILES[0], prof)
        return ICCProfile(prof, use_cache=use_cache)
    return None


def _winreg_get_display_profile(
    monkey: list,
    current_user: bool = False,
    path_only: bool = False,
    use_cache: bool = True,
    advanced_color_active: bool | None = None,
) -> None | str | ICCProfile:
    """Get display profile from Windows registry.

    Args:
        monkey (list): Registry key path components for the display.
        current_user (bool): If True, use HKEY_CURRENT_USER, otherwise
            HKEY_LOCAL_MACHINE.
        path_only (bool): If True, return the profile path as a string,
            otherwise return an ICCProfile object.
        use_cache (bool): If True, use cached profile if available.
        advanced_color_active (bool | None): Whether the display is currently
            in Advanced Color (HDR) mode.  If explicitly False, the
            ICMProfileAC (Windows HDR Calibration) profile is excluded so the
            SDR profile is returned instead.  None means unknown (include all).

    Returns:
        None | str | ICCProfile: The display profile path as a string or
            an ICCProfile object, or None if no profile is found.
    """
    filename = None
    filenames = _winreg_get_display_profiles(
        monkey,
        current_user,
        exclude_advanced_color=advanced_color_active is False,
    )
    if filenames:
        # last existing file in the list is active
        filename = filenames.pop()
    if not filename and not current_user:
        # fall back to sRGB
        filename = os.path.join(ICCPROFILES[0], "sRGB Color Space Profile.icm")
    if filename:
        if path_only:
            return os.path.join(ICCPROFILES[0], filename)
        return ICCProfile(filename, use_cache=use_cache)
    return None


def _winreg_get_display_profiles(
    monkey: list,
    current_user: bool = False,
    exclude_advanced_color: bool = False,
) -> list:
    """Get display profile filenames from Windows registry.

    Args:
        monkey (list): Registry key path components for the display.
        current_user (bool): If True, use HKEY_CURRENT_USER, otherwise
            HKEY_LOCAL_MACHINE.
        exclude_advanced_color (bool): If True, skip profiles stored under
            ICMProfileAC (the Windows HDR Calibration / Advanced Color profile
            slot).  Pass True when the display is not currently in HDR mode so
            the SDR profile is used instead.

    Returns:
        list: List of profile filenames.
    """
    filenames = []
    try:
        if current_user and sys.getwindowsversion() >= (6,):
            # Vista / Windows 7 ONLY
            # User has to place a check in 'use my settings for this device'
            # in the color management control panel at least once to cause
            # this key to be created, otherwise it won't exist
            subkey = "\\".join(
                [
                    "Software",
                    "Microsoft",
                    "Windows NT",
                    "CurrentVersion",
                    "ICM",
                    "ProfileAssociations",
                    "Display",
                    *monkey,
                ]
            )
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey)
        else:
            subkey = "\\".join(
                ["SYSTEM", "CurrentControlSet", "Control", "Class", *monkey]
            )
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey)
        numsubkeys, numvalues, mtime = winreg.QueryInfoKey(key)
        for i in range(numvalues):
            name, value, type_ = winreg.EnumValue(key, i)
            if name not in ["ICMProfile", "ICMProfileAC"] or not value:
                continue
            if name == "ICMProfileAC" and exclude_advanced_color:
                continue

            if type_ == winreg.REG_BINARY:
                # Win2k/XP
                # convert to list of strings
                value = value.decode("utf-16").split("\0")
            elif type_ == winreg.REG_MULTI_SZ:
                # Vista / Windows 7
                # nothing to be done, _winreg returns a list of strings
                pass
            if not isinstance(value, list):
                value = [value]
            while "" in value:
                value.remove("")
            filenames.extend(value)
        winreg.CloseKey(key)
    except OSError as exception:
        if exception.args[0] == 2:
            # Key does not exist
            pass
        else:
            raise
    return [
        filename
        for filename in filenames
        if os.path.isfile(os.path.join(ICCPROFILES[0], filename))
    ]


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


def get_display_profile_windows(
    display_no: int = 0,
    path_only: bool = False,
    devicekey: None | str = None,
    use_active_display_device: bool = True,
    use_registry: bool = True,
) -> None | str | ICCProfile:
    """Return ICC Profile for the given display under Windows.

    Args:
        display_no (int): The display number to query.
        path_only (bool, optional): If True, return the profile path as a
            string, otherwise return an ICCProfile object.
        devicekey (None | str, optional): The device key to query. If None, the
            active display device will be used.
        use_active_display_device (bool, optional): If True, use the active
            display device, otherwise use the first display device.
        use_registry (bool, optional): If True, use the Windows registry to
            get the display profile.

    Raises:
        ImportError: If pywin32 is not available.

    Returns:
        None | str | ICCProfile: The display profile path as a string or
            an ICCProfile object, or None if no profile is found.
    """
    profile = None
    if "win32api" not in sys.modules:
        raise ImportError("pywin32 not available")
    gdi_device_name = None
    if not devicekey:
        # The ordering will work as long as Argyll continues using
        # EnumDisplayMonitors
        monitors = util_win.get_real_display_devices_info()
        moninfo = monitors[display_no]
        gdi_device_name = moninfo["Device"]
    if not mscms and not devicekey:
        # Via GetICMProfile. Sucks royally in a multi-monitor setup
        # where one monitor is disabled, because it'll always get
        # the profile of the first monitor regardless if that is the active
        # one or not. Yuck. Also, in this case it does not reflect runtime
        # changes to profile assignments. Double yuck.
        buflen = ctypes.c_ulong(260)
        dc = win32gui.CreateDC(moninfo["Device"], None, None)
        try:
            buf = ctypes.create_unicode_buffer(buflen.value)
            if ctypes.windll.gdi32.GetICMProfileW(
                dc,
                ctypes.byref(buflen),
                ctypes.byref(buf),  # WCHARs
            ):
                if path_only:
                    profile = buf.value
                else:
                    profile = ICCProfile(buf.value, use_cache=True)
        finally:
            win32gui.DeleteDC(dc)
    else:
        if devicekey:
            device = None
        elif use_active_display_device:
            # This would be the correct way. Unfortunately that is not
            # what other apps (or Windows itself) do.
            device = util_win.get_active_display_device(moninfo["Device"])
        else:
            # This is wrong, but it's what other apps use. Matches
            # GetICMProfile sucky behavior i.e. should return the same
            # profile, but atleast reflects runtime changes to profile
            # assignments.
            device = util_win.get_first_display_device(moninfo["Device"])
        if device:
            devicekey = device.DeviceKey
    if devicekey:
        if mscms:
            # Via WCS
            if util_win.per_user_profiles_isenabled(devicekey=devicekey):
                scope = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
            else:
                scope = WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"]
            if not use_registry:
                # NOTE: WcsGetDefaultColorProfile causes the whole system
                # to hitch if the profile of the active display device is
                # queried. Windows bug?
                return _wcs_get_display_profile(
                    str(devicekey), scope, path_only=path_only
                )
        else:
            scope = None
            # Via registry
        monkey = devicekey.split("\\")[-2:]  # pun totally intended
        # Current user scope
        current_user = scope == WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
        # Detect Advanced Color (HDR) state so we can skip the ICMProfileAC
        # entry when the display is in SDR mode (issue #627).
        if gdi_device_name is None:
            gdi_device_name = util_win.get_gdi_device_name_for_devicekey(devicekey)
        advanced_color_active = (
            util_win.is_advanced_color_enabled(gdi_device_name)
            if gdi_device_name
            else None
        )
        if current_user:
            profile = _winreg_get_display_profile(
                monkey,
                True,
                path_only=path_only,
                advanced_color_active=advanced_color_active,
            )
        else:
            # System scope
            profile = _winreg_get_display_profile(
                monkey,
                path_only=path_only,
                advanced_color_active=advanced_color_active,
            )

    return profile


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


def _wcs_set_display_profile(
    devicekey: str,
    profile_name: str,
    scope: int = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"],
) -> bool:
    """Set the current default WCS color profile for the given device.

    If the device is a display, this will also set its video card gamma ramps
    to linear* if the given profile is the display's current default profile
    and Windows calibration management isn't enabled.

    Note that the profile needs to have been already installed.

    * 0..65535 will get mapped to 0..65280, which is a Windows bug.

    Args:
        devicekey (str): The device key of the display.
        profile_name (str): The name of the profile to be set.
        scope (int): The scope of the profile management, either
            WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"] or
            WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"].

    Returns:
        bool: True if the profile was set successfully, False otherwise.
    """
    mscms.associate_color_profile_with_device(scope, profile_name, str(devicekey))
    profiles = mscms.get_device_color_profile_list(scope, str(devicekey))
    return profile_name in profiles


def _wcs_unset_display_profile(
    devicekey: str,
    profile_name: str,
    scope: int = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"],
) -> bool:
    """Unset the current default WCS color profile for the given device.

    If the device is a display, this will also set its video card gamma ramps
    to linear* if the given profile is the display's current default profile
    and Windows calibration management isn't enabled.

    Note that the profile needs to have been already installed.

    * 0..65535 will get mapped to 0..65280, which is a Windows bug.

    Args:
        devicekey (str): The device key of the display.
        profile_name (str): The name of the profile to be unset.
        scope (int): The scope of the profile management, either
            WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"] or
            WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"].

    Returns:
        bool: True if the profile was unset successfully, False otherwise.
    """
    mscms.disassociate_color_profile_from_device(scope, profile_name, str(devicekey))
    profiles = mscms.get_device_color_profile_list(scope, str(devicekey))
    return profile_name not in profiles


def set_display_profile(
    profile_name: str,
    display_no: int = 0,
    devicekey: None | str = None,
    use_active_display_device: bool = True,
) -> bool:
    """Set the current default WCS color profile for the given device.

    Args:
        profile_name (str): The name of the profile to be set.
        display_no (int): The display number to set the profile for.
        devicekey (str): The device key of the display.
        use_active_display_device (bool): Whether to use the active display
            device.

    Returns:
        bool: True if the profile was set successfully, False otherwise.
    """
    # Currently only implemented for Windows.
    # The profile to be assigned has to be already installed!
    if not devicekey:
        device = util_win.get_display_device(display_no, use_active_display_device)
        if not device:
            return False
        devicekey = device.DeviceKey
    if mscms:
        if util_win.per_user_profiles_isenabled(devicekey=devicekey):
            scope = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
        else:
            scope = WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"]
        return _wcs_set_display_profile(str(devicekey), profile_name, scope)
    # TODO: Implement for XP
    return False


def unset_display_profile(
    profile_name: str,
    display_no: int = 0,
    devicekey: None | str = None,
    use_active_display_device: bool = True,
) -> bool:
    """Unset the current default WCS color profile for the given device.

    If the device is a display, this will also set its video card gamma ramps
    to linear* if the given profile is the display's current default profile
    and Windows calibration management isn't enabled.

    Note that the profile needs to have been already installed.
    * 0..65535 will get mapped to 0..65280, which is a Windows bug.

    Args:
        profile_name (str): The name of the profile to be unset.
        display_no (int, optional): The display number to unset the profile
            for. Defaults to 0.
        devicekey (None | str): The device key of the display. Defatults to
            None, which means the active display device will be used.
        use_active_display_device (bool, optional): Whether to use the active
            display device. Defaults to True.

    Returns:
        bool: True if the profile was unset successfully, False otherwise.
    """
    # Currently only implemented for Windows.
    # The profile to be unassigned has to be already installed!
    if not devicekey:
        device = util_win.get_display_device(display_no, use_active_display_device)
        if not device:
            return False
        devicekey = device.DeviceKey
    if mscms:
        if util_win.per_user_profiles_isenabled(devicekey=devicekey):
            scope = WCS_PROFILE_MANAGEMENT_SCOPE["CURRENT_USER"]
        else:
            scope = WCS_PROFILE_MANAGEMENT_SCOPE["SYSTEM_WIDE"]
        return _wcs_unset_display_profile(str(devicekey), profile_name, scope)
    # TODO: Implement for XP
    return False


def _blend_blackpoint(
    row: tuple[float, float, float],
    bp_in: None | tuple,
    bp_out: None | tuple,
    wp: None | float | str | list | tuple = None,
    use_bpc: bool = False,
    weight: bool = False,
) -> tuple[float, float, float]:
    """Blend black point compensation or offset into XYZ values.

    Args:
        row (tuple): A tuple containing XYZ values.
        bp_in (tuple): Input black point (X, Y, Z).
        bp_out (tuple): Output black point (X, Y, Z).
        wp (None | float | str | list | tuple, optional): White point, if using
            BPC.
        use_bpc (bool, optional): Whether to use black point compensation.
        weight (bool, optional): Whether to apply weighting.

    Returns:
        tuple: Adjusted XYZ values after applying black point compensation or
            offset.
    """
    X, Y, Z = row  # noqa: N806
    if use_bpc:
        X, Y, Z = colormath.apply_bpc(X, Y, Z, bp_in, bp_out, wp, weight=weight)  # noqa: N806
    else:
        X, Y, Z = colormath.blend_blackpoint(X, Y, Z, bp_in, bp_out, wp)  # noqa: N806
    return X, Y, Z


def _mp_apply(
    blocks: list,
    thread_abort_event: threading.Event,
    progress_queue: multiprocessing.Queue,
    pcs: str,
    fn: Callable,
    args: tuple,
    D50: None | float | str | list | tuple,  # noqa: N803
    interp: list,
    rinterp: list,
    abortmessage: str = "Aborted",
) -> list:
    """Worker for applying function to cLUT.

    This should be spawned as a multiprocessing process.

    Args:
        blocks (list): List of blocks to process.
        thread_abort_event (threading.Event): Event to signal abort.
        progress_queue (multiprocessing.Queue): Queue for progress updates.
        pcs (str): PCS type, either "Lab" or "XYZ".
        fn (callable): Function to apply to each block.
        args (tuple): Arguments to pass to the function.
        D50 (None | float | str | list | tuple): D50 whitepoint.
        interp (list): Interpolation functions for each channel.
        rinterp (list): Reverse interpolation functions for each channel.
        abortmessage (str): Message to return if aborted.

    Returns:
        list: Processed blocks after applying the function.
    """
    from DisplayCAL.debughelpers import Info

    for interp_tuple in (interp, rinterp):
        if interp_tuple:
            # Use numpy for speed
            interp_list = list(interp_tuple)
            for i, ointerp in enumerate(interp_list):
                interp_list[i] = colormath.Interp(
                    ointerp.xp, ointerp.fp, use_numpy=True
                )
                interp_list[i].lookup = ointerp.lookup
            if interp_tuple is interp:
                interp = interp_list
            else:
                rinterp = interp_list
    prevperc = 0
    count = 0
    numblocks = len(blocks)
    for block in blocks:
        if thread_abort_event and thread_abort_event.is_set():
            return Info(abortmessage)
        for i, row in enumerate(block):
            if interp:
                for column, value in enumerate(row):
                    row[column] = interp[column](value)
            if pcs == "Lab":
                L, a, b = legacy_PCSLab_uInt16_to_dec(*row)  # noqa: N806
                X, Y, Z = colormath.Lab2XYZ(L, a, b, D50)  # noqa: N806
            else:
                X, Y, Z = [v / 32768.0 for v in row]  # noqa: N806
            X, Y, Z = fn((X, Y, Z), *args)  # noqa: N806
            if pcs == "Lab":
                L, a, b = colormath.XYZ2Lab(X, Y, Z, D50)  # noqa: N806
                row = [
                    min(max(0, v), 65535) for v in legacy_PCSLab_dec_to_uInt16(L, a, b)
                ]
            else:
                row = [min(max(0, v) * 32768.0, 65535) for v in (X, Y, Z)]
            if rinterp:
                for column, value in enumerate(row):
                    row[column] = rinterp[column](value)
            block[i] = row
        count += 1.0
        perc = round(count / numblocks * 100)
        if progress_queue and perc > prevperc:
            progress_queue.put(perc - prevperc)
            prevperc = perc
    return blocks


def _mp_apply_black(
    blocks: list,
    thread_abort_event: threading.Event,
    progress_queue: multiprocessing.Queue,
    pcs: str,
    bp: tuple[float, float, float],
    bp_out: tuple[float, float, float],
    wp: None | float | str | list | tuple,
    use_bpc: bool,
    weight: bool,
    D50: None | float | str | list | tuple,  # noqa: N803
    interp: list,
    rinterp: list,
    abortmessage: str = "Aborted",
) -> list:
    """Worker for applying black point compensation or offset.

    This should be spawned as a multiprocessing process.

    Args:
        blocks (list): List of blocks to process.
        thread_abort_event (threading.Event): Event to signal abort.
        progress_queue (multiprocessing.Queue): Queue for progress updates.
        pcs (str): PCS type, either "Lab" or "XYZ".
        bp (tuple): Black point to apply.
        bp_out (tuple): Black point output.
        wp (None | float | str | list | tuple): White point, if using BPC.
        use_bpc (bool): Whether to use black point compensation.
        weight (bool): Whether to apply weighting.
        D50 (None | float | str | list | tuple): D50 whitepoint.
        interp (list): Interpolation functions for each channel.
        rinterp (list): Reverse interpolation functions for each channel.
        abortmessage (str): Message to return if aborted.

    Returns:
        list: Processed blocks after applying black point compensation or
            offset.
    """
    return _mp_apply(
        blocks,
        thread_abort_event,
        progress_queue,
        pcs,
        _blend_blackpoint,
        (bp, bp_out, wp if use_bpc else None, use_bpc, weight),
        D50,
        interp,
        rinterp,
        abortmessage,
    )


def _mp_hdr_tonemap(
    HDR_XYZ: list,  # noqa: N803
    thread_abort_event: threading.Event,
    progress_queue: multiprocessing.Queue,
    rgb_space: None | str | list | tuple,
    maxv: float,
    sat: float,
    cat: str = "Bradford",
) -> list:
    """Worker for HDR tonemapping.

    This should be spawned as a multiprocessing process

    Args:
        HDR_XYZ (list): List of HDR XYZ tuples.
        thread_abort_event (threading.Event): Event to signal abort.
        progress_queue (multiprocessing.Queue): Queue for progress updates.
        rgb_space (None | str | list | tuple): The RGB space to use for
            conversion. Defaults to sRGB if not set. If a string is given, it
            must be a valid RGB space name. If a list or tuple is given, it
            must be in the format (gamma, whitepoint, red, green, blue). The
            whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or int).
            The gamma should be a float. The RGB primaries red, green, blue
            should be lists or tuples of xyY coordinates (only x and y will be
            used, so Y can be zero or None).
        maxv (float): Maximum value for normalization.
        sat (float): Saturation factor for ICtCp.
        cat (str): Chromatic adaptation transform to use, defaults to
            "Bradford".

    Returns:
        list: Processed HDR XYZ tuples.
    """
    prevperc = 0
    amount = len(HDR_XYZ)
    dI = 0  # noqa: N806
    dI_max = 0  # noqa: N806
    dC = 0  # noqa: N806
    dC_max = 0  # noqa: N806
    I_reduced_count = 0  # noqa: N806
    its_hi = 0  # Highest number pf iterations seen per color
    for i, (RGB_in, ICtCp_XYZ, RGB_ICtCp_XYZ) in enumerate(HDR_XYZ):  # noqa: N806
        if thread_abort_event and thread_abort_event.is_set():
            return [False]
        is_neutral = all(v == RGB_in[0] for v in RGB_in)
        for j, XYZ in enumerate((ICtCp_XYZ, RGB_ICtCp_XYZ)):  # noqa: N806
            if j == 0 and (sat == 1 or ICtCp_XYZ == RGB_ICtCp_XYZ):
                # Set ICtCp_XYZ to the same object as RGB_ICtCp_XYZ which we
                # are going to change in-place in the next iteration of the loop
                # so that at the end of this loop, both will point to the same
                # changed data
                ICtCp_XYZ = RGB_ICtCp_XYZ  # noqa: N806
                continue
            X, Y, Z = XYZ  # noqa: N806
            H = None  # noqa: N806
            its = 10000  # Remaining iterations (limit)
            while not is_neutral and its:
                X_D50, Y_D50, Z_D50 = colormath.adapt(  # noqa: N806
                    *(v / maxv for v in (X, Y, Z)),
                    whitepoint_source=rgb_space[1],
                    cat=cat,
                )
                negative_clip = min(X_D50, Y_D50, Z_D50) < 0
                positive_clip = (
                    round(X_D50, 4) > 0.9642 or Y_D50 > 1 or round(Z_D50, 4) > 0.8249
                )
                if not (negative_clip or positive_clip):
                    break
                if H is None:
                    # Record hue angle
                    H = colormath.RGB2HSV(*RGB_in)[0]  # noqa: N806
                    # This is the initial intensity, and hue + saturation
                    I, Ct, Cp = colormath.XYZ2ICtCp(X, Y, Z)  # noqa: N806
                    Io = I  # noqa: N806
                    Co = colormath.Lab2LCHab(I, Ct, Cp)[1]  # noqa: N806
                # Desaturate
                Ct *= 0.99  # noqa: N806
                Cp *= 0.99  # noqa: N806
                # Update XYZ
                X, Y, Z = colormath.ICtCp2XYZ(I, Ct, Cp)  # noqa: N806
                if Y > XYZ[1]:  # noqa: SIM300
                    # Desaturating CtCp increases Y!
                    # As we desaturate different amounts per color,
                    # restore initial Y if lower than adjusted Y
                    # to keep luminance relation
                    X, Y, Z = (v / Y * XYZ[1] for v in (X, Y, Z))  # noqa: N806
                    I, Ct, Cp = colormath.XYZ2ICtCp(X, Y, Z)  # noqa: N806
                its -= 1
            if H is not None and round(Io - I, 4):
                # Intensity was reduced by >= 0.0001, gather statistics
                C = colormath.Lab2LCHab(I, Ct, Cp)[1]  # noqa: N806
                dI += Io - I  # noqa: N806
                dI_max = max(dI_max, Io - I)  # noqa: N806
                dC += Co - C  # noqa: N806
                dC_max = max(dC_max, Co - C)  # noqa: N806
                I_reduced_count += 1  # noqa: N806
            if not its:
                # Max iterations exceeded, print diagnostics
                # XXX: This should not happen (testing OK)
                oX_D50, oY_D50, oZ_D50 = colormath.adapt(  # noqa: N806
                    *(v / maxv for v in XYZ), whitepoint_source=rgb_space[1], cat=cat
                )
                X_D50, Y_D50, Z_D50 = colormath.adapt(  # noqa: N806
                    *(v / maxv for v in (X, Y, Z)),
                    whitepoint_source=rgb_space[1],
                    cat=cat,
                )
                print(
                    "Reached iteration limit, XYZ "
                    f"{oX_D50:.4f} {oY_D50:.4f} {oZ_D50:.4f} -> "
                    f"{X_D50:.4f} {Y_D50:.4f} {Z_D50:.4f}"
                )
            its_hi = max(its_hi, 10000 - its)
            XYZ[:] = X, Y, Z
        HDR_XYZ[i] = (RGB_in, ICtCp_XYZ, RGB_ICtCp_XYZ)
        perc = round((i + 1.0) / amount * 50)
        if progress_queue and perc > prevperc:
            progress_queue.put(perc - prevperc)
            prevperc = perc
    if I_reduced_count:
        # Intensity was reduced, print informational statistics
        print(
            f"Max iterations {int(its_hi):d} "
            f"dI avg {dI / I_reduced_count:.4f} "
            f"max {dI_max:.4f} "
            f"dC avg {dC / I_reduced_count:.4f} "
            f"max {dC_max:.4f}"
        )
    elif its_hi:
        print("Max iterations", its_hi)
    return HDR_XYZ


class DictType(ICCProfileTag, AODict):
    """ICC dictType Tag.

    Implements all features of 'Dictionary Type and Metadata TAG Definition'
    (ICC spec revision 2010-02-25), including shared data (the latter will
    only be effective for mutable types, ie. MultiLocalizedUnicodeType)

    Examples:

    tag[key]   Returns the (non-localized) value
    tag.getname(key, locale='en_US') Returns the localized name if present
    tag.getvalue(key, locale='en_US') Returns the localized value if present
    tag[key] = value   Sets the (non-localized) value

    """

    def __init__(
        self,
        tagData: None | bytes = None,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        AODict.__init__(self)
        if not tagData:
            return
        numrecords = uInt32Number(tagData[8:12])
        recordlen = uInt32Number(tagData[12:16])
        if recordlen not in (16, 24, 32):
            print(
                f"Error (non-critical): '{tagData[:4]}' invalid record length "
                f"(expected 16, 24 or 32, got {recordlen})"
            )
            return
        elements = {}
        for n in range(numrecords):
            record = tagData[16 + n * recordlen : 16 + (n + 1) * recordlen]
            if len(record) < recordlen:
                print(
                    f"Error (non-critical): '{tagData[:4]}' record {n} too short "
                    f"(expected {recordlen} bytes, got {len(record)} bytes)"
                )
                break
            for key, offsetpos in (
                ("name", 0),
                ("value", 8),
                ("display_name", 16),
                ("display_value", 24),
            ):
                if (
                    offsetpos in (0, 8)
                    or recordlen == offsetpos + 8
                    or recordlen == offsetpos + 16
                ):
                    # Required:
                    # Bytes 0..3, 4..7: Name offset and size
                    # Bytes 8..11, 12..15: Value offset and size
                    # Optional:
                    # Bytes 16..23, 24..23: Display name offset and size
                    # Bytes 24..27, 28..31: Display value offset and size
                    offset = uInt32Number(record[offsetpos : offsetpos + 4])
                    size = uInt32Number(record[offsetpos + 4 : offsetpos + 8])
                    if offset > 0:
                        if (offset, size) in elements:
                            # Use existing element if same offset and size
                            # This will really only make a difference for
                            # mutable types i.e. MultiLocalizedUnicodeType
                            data = elements[(offset, size)]
                        else:
                            data = tagData[offset : offset + size]
                            try:
                                if key.startswith("display_"):
                                    data = MultiLocalizedUnicodeType(data, "mluc")
                                else:
                                    data = data.decode("UTF-16-BE", "replace").rstrip(
                                        "\0"
                                    )
                            except Exception:
                                print(
                                    "Error (non-critical): could not decode "
                                    f"'{tagData[:4]}', offset {offset}, length {size}"
                                )
                            # Remember element by offset and size
                            elements[(offset, size)] = data
                        if key == "name":
                            name = data
                            self[name] = ""
                        else:
                            self.get(name)[key] = data

    def __getitem__(self, name: str) -> Any:  # noqa: ANN401
        """Get item from dict.

        Args:
            name (str): Name of the item.

        Returns:
            Any: Value of the item.
        """
        return self.get(name).value

    def __setitem__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Set item in dict.

        Args:
            name (str): Name of the item.
            value (Any): Value of the item.
        """
        AODict.__setitem__(self, name, ADict(value=value))

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: The raw tag data representing the dictionary.
        """
        numrecords = len(self)
        recordlen = 16
        keys = ("name", "value")
        for value in self.values():
            if not isinstance(value, dict):
                continue
            if "display_value" in value:
                recordlen = 32
                break
            if "display_name" in value:
                recordlen = 24
        if recordlen > 16:
            keys += ("display_name",)
        if recordlen > 24:
            keys += ("display_value",)
        tag_data = [
            b"dict",
            b"\0" * 4,
            uInt32Number_tohex(numrecords),
            uInt32Number_tohex(recordlen),
        ]
        storage_offset = 16 + numrecords * recordlen
        storage = []
        elements = []
        offsets = []
        for item in self.items():
            for key in keys:
                if key == "name":
                    element = item[0]
                else:
                    element = item[1].get(key) if isinstance(item[1], dict) else item[1]
                if element is None:
                    offset = 0
                    size = 0
                elif element in elements:
                    # Use existing offset and size if same element
                    offset, size = offsets[elements.index(element)]
                else:
                    offset = storage_offset + len(b"".join(storage))
                    if isinstance(element, MultiLocalizedUnicodeType):
                        data = element.tagData
                    else:
                        data = str(element).encode("UTF-16-BE")
                    size = len(data)
                    if isinstance(element, MultiLocalizedUnicodeType):
                        # Remember element, offset and size
                        elements.append(element)
                        offsets.append((offset, size))
                    # Pad all data with binary zeros so it lies on
                    # 4-byte boundaries
                    padding = math.ceil(size / 4.0) * 4 - size
                    data += b"\0" * padding
                    storage.append(data)
                tag_data.append(uInt32Number_tohex(offset))
                tag_data.append(uInt32Number_tohex(size))
        tag_data.extend(storage)
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set raw tag data.

        Does nothing, as the tagData is read-only.

        Args:
            tagData (bytes): The raw tag data to set.
        """

    def getname(
        self,
        name: str,
        default: None | Any = None,  # noqa: ANN401
        locale: str = "en_US",
    ) -> str:
        """Convenience function to get (localized) names.

        Args:
            name (str): The name of the item to get.
            default (Any, optional): Default value to return if the item is not
                found. Defaults to None.
            locale (str, optional): Locale to use for localized names. Defaults
                to "en_US".

        Returns:
            str: The localized name of the item if available, otherwise the
                default value or the non-localized name.
        """
        item = self.get(name, default)
        if item is default:
            return default
        if locale and "display_name" in item:
            return item.display_name.get_localized_string(*locale.split("_"))
        return name

    def getvalue(
        self,
        name: str,
        default: None | Any = None,  # noqa: ANN401
        locale: str = "en_US",
    ) -> Any:  # noqa: ANN401
        """Convenience function to get (localized) values.

        Args:
            name (str): The name of the item to get.
            default (Any, optional): Default value to return if the item is not
                found. Defaults to None.
            locale (str, optional): Locale to use for localized values.
                Defaults to "en_US".

        Returns:
            Any: The localized value of the item if available, otherwise the
                default value or the non-localized value.
        """
        item = self.get(name, default)
        if item is default:
            return default
        if locale and "display_value" in item:
            return item.display_value.get_localized_string(*locale.split("_"))
        if isinstance(item, dict):
            return item.value
        return item

    def setitem(
        self,
        name: str,
        value: Any,  # noqa: ANN401
        display_name: None | dict = None,
        display_value: None | dict = None,
    ) -> None:
        """Convenience function to set items.

        display_name and display_value (if given) should be dict types with
        country -> language -> string mappings, e.g.:

        {"en": {"US": u"localized string"},
         "de": {"DE": u"localized string", "CH": u"localized string"}}


        Args:
            name (str): The name of the item to set.
            value (Any): The value to set for the item.
            display_name (None | dict, optional): Localized display names for
                the item.
            display_value (None | dict, optional): Localized display values
                for the item.
        """
        self[name] = value
        item = self.get(name)
        if display_name:
            item.display_name = MultiLocalizedUnicodeType()
            item.display_name.update(display_name)
        if display_value:
            item.display_value = MultiLocalizedUnicodeType()
            item.display_value.update(display_value)

    def to_json(
        self, encoding: str = "UTF-8", errors: str = "replace", locale: str = "en_US"
    ) -> str:
        """Return a JSON representation.

        Display names/values are used if present.

        Args:
            encoding (str, optional): Encoding to use for the JSON string.
                Defaults to "UTF-8".
            errors (str, optional): Error handling scheme for encoding.
                Defaults to "replace".
            locale (str, optional): Locale to use for localized names/values.
                Defaults to "en_US".

        Returns:
            str: JSON representation of the DictType object.
        """
        return DictTypeJSONEncoder(locale=locale).encode(self)


class DictTypeJSONEncoder(json.JSONEncoder):
    """JSON Encoder for the DictType class."""

    def __init__(self, *args, **kwargs) -> None:
        self.locale = kwargs.pop("locale") or "en_US"
        super().__init__(*args, **kwargs)

    def default(self, obj: Any) -> dict:  # noqa: ANN401
        """Default method for encoding objects to JSON.

        Args:
            obj (object): The object to encode.

        Returns:
            dict: Encoded object as a dictionary.
        """
        return_data = {}
        regex = re.compile(r"\\x([0-9a-f]{2})")
        repl_str = r"\\u00\1"
        for name in obj:
            value = obj.getvalue(name, None, self.locale)
            name = obj.getname(name, None, self.locale)
            value = '"{}"'.format(repr(str(value))[2:-1].replace('"', '\\"'))
            name = regex.sub(repl_str, name)
            value = regex.sub(repl_str, value)
            return_data[name] = value
        return return_data


class MakeAndModelType(ICCProfileTag, ADict):
    """ICC makeAndModelType tag.

    Args:
        tagData (bytes): The raw tag data.
        tagSignature (str): The signature of the tag.
    """

    def __init__(self, tagData: bytes, tagSignature: str) -> None:  # noqa: N803
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.update({"manufacturer": tagData[10:12], "model": tagData[14:16]})


class MultiLocalizedUnicodeType(ICCProfileTag, AODict):  # ICC v4
    """ICC v4 MultiLocalizedUnicodeType tag.

    Args:
        tagData (None | bytes, optional): Raw tag data. Defaults to None.
        tagSignature (None | str, optional): Tag signature. Defaults to None.
    """

    def __init__(
        self,
        tagData: None | bytes = None,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        AODict.__init__(self)
        if not tagData:
            return
        records_count = uInt32Number(tagData[8:12])
        record_size = uInt32Number(tagData[12:16])  # 12
        if record_size != 12:
            print(
                f"Warning (non-critical): '{tagData[:4]}' invalid record length "
                f"(expected 12, got {record_size})"
            )
            record_size = max(record_size, 12)
        records = tagData[16 : 16 + record_size * records_count]
        for _count in range(records_count):
            record = records[:record_size]
            if len(record) < 12:
                continue
            record_language_code = record[:2].decode("ascii", "replace")
            record_country_code = record[2:4].decode("ascii", "replace")
            record_length = uInt32Number(record[4:8])
            record_offset = uInt32Number(record[8:12])
            self.add_localized_string(
                record_language_code,
                record_country_code,
                str(
                    tagData[record_offset : record_offset + record_length],
                    "utf-16-be",
                    "replace",
                ),
            )
            records = records[record_size:]

    def __str__(self) -> str:
        """Return tag as string.

        Returns:
            str: The first localized string in the tag, or an empty string if
                no localized strings are available.
        """
        # TODO: Needs some work re locales
        # (currently if en-UK or en-US is not found, simply the first entry
        # is returned)
        if "en" in self:
            for country_code in ("UK", "US"):
                if country_code in self["en"]:
                    return self["en"][country_code]
            if self["en"]:
                # return first value
                return next(iter(self["en"].values()))
            return ""
        if len(self):
            # return first value of the first dictionary
            return next(iter(next(iter(self.values())).values()))
        return ""

    def add_localized_string(
        self, languagecode: str, countrycode: str, localized_string: str
    ) -> None:
        """Convenience function for adding localized strings."""
        if languagecode not in self:
            self[languagecode] = AODict()
        self[languagecode][countrycode] = localized_string.strip("\0")

    def get_localized_string(
        self, languagecode: str = "en", countrycode: str = "US"
    ) -> str:
        """Convenience function for retrieving localized strings.

        Falls back to first locale available if the requested one isn't

        Args:
            languagecode (str): The language code to retrieve the string for.
                Defaults to "en".
            countrycode (str): The country code to retrieve the string for.
                Defaults to "US".

        Returns:
            str: The localized string for the given language and country code,
                or the first available string if the requested one is not
                found.
        """
        try:
            return self[languagecode][countrycode]
        except KeyError:
            return str(self)

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data."""
        tag_data = [b"mluc", b"\0" * 4]
        records_count = 0
        for language_code in self:
            for _ in self[language_code]:
                records_count += 1
        tag_data.append(uInt32Number_tohex(records_count))
        record_size = 12
        tag_data.append(uInt32Number_tohex(record_size))
        storage_offset = 16 + record_size * records_count
        storage = []
        offsets = []
        for language_code in self:
            for country_code in self[language_code]:
                tag_data.append((language_code + country_code).encode("ascii"))
                data = self[language_code][country_code].encode("UTF-16-BE")
                if data in storage:
                    offset, record_length = offsets[storage.index(data)]
                else:
                    record_length = len(data)
                    offset = len("".join(storage))
                    offsets.append((offset, record_length))
                    storage.append(data)
                tag_data.append(uInt32Number_tohex(record_length))
                tag_data.append(uInt32Number_tohex(storage_offset + offset))
        tag_data.append(
            b"".join(storage)
        )  # TODO: Are you sure that this needs to be bytes
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set raw tag data.

        Does nothing, as this tag is read-only.

        Args:
            tagData (bytes): Raw tag data to set.
        """


def SignatureType(tagData: bytes, tagSignature: str) -> Text:  # noqa: N802, N803
    """Generate ICC signatureType tag.

    Args:
        tagData (bytes): The raw tag data containing the signature.
        tagSignature (str): The signature of the tag.

    Returns:
        Text: An instance of the Text class representing the tag.
    """
    tag = Text(tagData[8:12].rstrip(b"\0"))
    tag.tagData = tagData
    tag.tagSignature = tagSignature
    return tag


class TextDescriptionType(ICCProfileTag, ADict):  # ICC v2
    """ICC textDescriptionType tag.

    Args:
        tagData (None | bytes, optional): Raw tag data. Defaults to None.
        tagSignature (None | str, optional): Tag signature. Defaults to None.
    """

    def __init__(
        self,
        tagData: None | bytes = None,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.ASCII = b""
        if not tagData:
            return
        ascii_description_length = uInt32Number(tagData[8:12])
        if ascii_description_length:
            ascii_description = tagData[12 : 12 + ascii_description_length].strip(
                b"\0\n\r "
            )
            if ascii_description:
                self.ASCII = ascii_description
        unicode_offset = 12 + ascii_description_length
        self.unicodeLanguageCode = uInt32Number(
            tagData[unicode_offset : unicode_offset + 4]
        )
        unicode_description_length = uInt32Number(
            tagData[unicode_offset + 4 : unicode_offset + 8]
        )
        if unicode_description_length:
            if unicode_offset + 8 + unicode_description_length * 2 > len(tagData):
                # Damn you MS. The Unicode character count should be the number of
                # double-byte characters (including trailing unicode NUL), not the
                # number of bytes as in the profiles created by Vista and later
                print(
                    f"Warning (non-critical): '{tagData[:4]}' Unicode part end points "
                    "past the tag data, assuming number of bytes instead "
                    "of number of characters for length"
                )
                unicode_description_length /= 2
            if (
                tagData[
                    unicode_offset + 8 + unicode_description_length : unicode_offset
                    + 8
                    + unicode_description_length
                    + 2
                ]
                == b"\0\0"
            ):
                print(
                    f"Warning (non-critical): '{tagData[:4]}' Unicode part "
                    "seems to be a single-byte string (double-byte "
                    "string expected)"
                )
                char_bytes = 1  # fix for fubar'd desc
            else:
                char_bytes = 2
            unicode_description = tagData[
                unicode_offset + 8 : unicode_offset
                + 8
                + (unicode_description_length) * char_bytes
            ]
            try:
                if char_bytes == 1:
                    unicode_description = str(unicode_description, errors="replace")
                elif unicode_description[:2] == b"\xfe\xff":
                    # UTF-16 Big Endian
                    if DEBUG:
                        print("UTF-16 Big endian")
                    unicode_description = unicode_description[2:]
                    if (
                        len(unicode_description.split(b" "))
                        == unicode_description_length - 1
                    ):
                        print(
                            f"Warning (non-critical): '{tagData[:4]}' "
                            "Unicode part starts with UTF-16 big "
                            "endian BOM, but actual contents seem "
                            "to be UTF-16 little endian"
                        )
                        # fix fubar'd desc
                        unicode_description = str(
                            b"\0".join(unicode_description.split(b" ")),
                            "utf-16-le",
                            errors="replace",
                        )
                    else:
                        unicode_description = str(
                            unicode_description, "utf-16-be", errors="replace"
                        )
                elif unicode_description[:2] == b"\xff\xfe":
                    # UTF-16 Little Endian
                    if DEBUG:
                        print("UTF-16 Little endian")
                    unicode_description = unicode_description[2:]
                    if unicode_description[0] == b"\0":
                        print(
                            f"Warning (non-critical): '{tagData[:4]}' "
                            "Unicode part starts with UTF-16 "
                            "little endian BOM, but actual "
                            "contents seem to be UTF-16 big "
                            "endian"
                        )
                        # fix fubar'd desc
                        unicode_description = str(
                            unicode_description, "utf-16-be", errors="replace"
                        )
                    else:
                        unicode_description = str(
                            unicode_description, "utf-16-le", errors="replace"
                        )
                else:
                    if DEBUG:
                        print("ASSUMED UTF-16 Big Endian")
                    unicode_description = str(
                        unicode_description, "utf-16-be", errors="replace"
                    )
                unicode_description = unicode_description.strip("\0\n\r ")
                if unicode_description:
                    if unicode_description.find("\0") < 0:
                        self.Unicode = unicode_description
                    else:
                        print(
                            "Error (non-critical): could not decode "
                            f"'{tagData[:4]}' Unicode part - null byte(s) "
                            "encountered"
                        )
            except UnicodeDecodeError:
                print(
                    "UnicodeDecodeError (non-critical): could not "
                    f"decode '{tagData[:4]}' Unicode part"
                )
        else:
            char_bytes = 1
        mac_offset = unicode_offset + 8 + unicode_description_length * char_bytes
        self.macScriptCode = 0
        if len(tagData) > mac_offset + 2:
            self.macScriptCode = uInt16Number(tagData[mac_offset : mac_offset + 2])
            mac_description_length = ord(tagData[mac_offset + 2 : mac_offset + 3])
            if mac_description_length:
                try:
                    mac_description = str(
                        tagData[
                            mac_offset + 3 : mac_offset + 3 + mac_description_length
                        ],
                        "mac-" + ENCODINGS["mac"][self.macScriptCode],
                        errors="replace",
                    ).strip("\0\n\r ")
                    if mac_description:
                        self.Macintosh = mac_description
                except KeyError:
                    print(
                        f"KeyError (non-critical): could not decode '{tagData[:4]}' "
                        f"Macintosh part (unsupported encoding {self.macScriptCode})"
                    )
                except LookupError:
                    print(
                        f"LookupError (non-critical): could not decode '{tagData[:4]}' "
                        "Macintosh part (unsupported encoding "
                        f"'{ENCODINGS['mac'][self.macScriptCode]}')"
                    )
                except UnicodeDecodeError:
                    print(
                        "UnicodeDecodeError (non-critical): could not decode "
                        f"'{tagData[:4]}' Macintosh part"
                    )

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: The raw tag data for the textDescriptionType tag.
        """
        tag_data = [
            b"desc",
            b"\0" * 4,
            uInt32Number_tohex(len(self.ASCII) + 1),  # count of ASCII chars + 1
            self.ASCII + b"\0",  # ASCII desc, \0 terminated
            uInt32Number_tohex(self.get("unicodeLanguageCode", 0)),
        ]
        if "Unicode" in self:
            tag_data.extend(
                [
                    # count of Unicode chars + 2 (UTF-16-BE BOM + trailing UTF-16 NUL,
                    #                             1 char = 2 byte)
                    uInt32Number_tohex(len(self.Unicode) + 2),
                    b"\xfe\xff" + self.Unicode.encode("utf-16-be", "replace") + b"\0\0",
                ]
            )  # Unicode desc, \0\0 terminated
        else:
            tag_data.append(uInt32Number_tohex(0))  # Unicode desc length = 0
        tag_data.append(uInt16Number_tohex(self.get("macScriptCode", 0)))
        if "Macintosh" in self:
            mac_description = self.Macintosh[:66]
            tag_data.extend(
                [
                    uInt8Number_tohex(
                        len(mac_description) + 1
                    ),  # count of Macintosh chars + 1
                    mac_description.encode(
                        "mac-" + ENCODINGS["mac"][self.get("macScriptCode", 0)],
                        "replace",
                    )
                    + (b"\0" * (67 - len(mac_description))),
                ]
            )
        else:
            tag_data.extend([b"\0", b"\0" * 67])  # Mac desc length = 0
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set tag data.

        Does nothing, as this tag is read-only.

        Args:
            tagData (bytes): The raw tag data to set.
        """

    def __str__(self) -> str:
        """Return tag as string.

        Returns:
            str: The localized string if available, otherwise the ASCII
                representation of the tag.
        """
        if "Unicode" not in self and len(str(self.ASCII)) < 67:
            # Do not use Macintosh description if ASCII length >= 67
            localized_types = ("Macintosh", "ASCII")
        else:
            localized_types = ("Unicode", "ASCII")

        for localized_type in localized_types:
            if localized_type not in self:
                continue
            value = self[localized_type]
            if not isinstance(value, str):
                # Even ASCII description may contain non-ASCII chars, so
                # assume system encoding and convert to unicode, replacing
                # unknown chars
                value = value.decode("utf-8", "replace")
            return value
        return None


def TextType(tagData: bytes, tagSignature: str) -> Text:  # noqa: N802, N803
    """Generate an ICC textType tag.

    Args:
        tagData (bytes): The raw tag data.
        tagSignature (str): The signature of the tag, usually "text".

    Returns:
        Text: An instance of the Text class containing the tag data and
            signature.
    """
    tag = Text(tagData[8:].rstrip(b"\0"))
    tag.tagData = tagData
    tag.tagSignature = tagSignature
    return tag


class VideoCardGammaType(ICCProfileTag, ADict):
    """Video Card Gamma Tag.

    This tag contains the gamma correction values for the red, green and blue
    channels of the video card. The values are stored in a table or as a
    formula. The table is a 256-entry table with values ranging from 0 to
    65535. The formula is a gamma correction formula with the following
    parameters: redMin, redMax, redGamma, greenMin, greenMax, greenGamma,
    blueMin, blueMax, blueGamma.

    Private tag
    http://developer.apple.com/documentation/GraphicsImaging/Reference/ColorSync_Manager/Reference/reference.html#//apple_ref/doc/uid/TP30000259-CH3g-C001473

    Args:
        tagData (bytes): The raw tag data.
        tagSignature (str): The signature of the tag, usually "vcgt".
    """

    def __init__(self, tagData: bytes, tagSignature: str) -> None:  # noqa: N803
        ICCProfileTag.__init__(self, tagData, tagSignature)

    def is_linear(self, r: bool = True, g: bool = True, b: bool = True) -> bool:
        """Check if the gamma correction is linear for the red, green and blue channels.

        Args:
            r (bool): Whether to check the red channel.
            g (bool): Whether to check the green channel.
            b (bool): Whether to check the blue channel.

        Returns:
            bool: True if the gamma correction is linear for the specified
                channels.
        """
        r_points, g_points, b_points, linear_points = self.get_values()
        if (
            (r and g and b and r_points == g_points == b_points)
            or (r and g and r_points == g_points)
            or not (g or b)
        ):
            points = r_points
        elif (
            (r and b and r_points == b_points)
            or (g and b and g_points == b_points)
            or not (r or g)
        ):
            points = b_points
        elif g:
            points = g_points
        return points == linear_points

    def get_unique_values(
        self, r: bool = True, g: bool = True, b: bool = True
    ) -> tuple:
        """Return unique values for the red, green and blue channels.

        Args:
            r (bool): Whether to include red channel values.
            g (bool): Whether to include green channel values.
            b (bool): Whether to include blue channel values.

        Returns:
            tuple: Three sets containing the unique values for the red,
        """
        r_points, g_points, b_points, linear_points = self.get_values()
        r_unique = {round(y) for x, y in r_points}
        g_unique = {round(y) for x, y in g_points}
        b_unique = {round(y) for x, y in b_points}
        return r_unique, g_unique, b_unique

    def get_values(self, r: bool = True, g: bool = True, b: bool = True) -> tuple:
        """Return the gamma correction values for the red, green and blue channels.

        Args:
            r (bool, optional): Whether to include red channel values.
            g (bool, optional): Whether to include green channel values.
            b (bool, optional): Whether to include blue channel values.

        Returns:
            tuple: Four lists containing the red, green, blue, and linear
        """
        r_points = []
        g_points = []
        b_points = []
        linear_points = []
        vcgt = self
        if "data" in vcgt:  # table
            data = list(vcgt["data"])
            while len(data) < 3:
                data.append(data[0])
            irange = list(range(vcgt["entryCount"]))
            vmax = math.pow(256, vcgt["entrySize"]) - 1
            for i in irange:
                j = i * (255.0 / (vcgt["entryCount"] - 1))
                linear_points.append(
                    [j, round(i / float(vcgt["entryCount"] - 1) * 65535)]
                )
                if r:
                    n = round(float(data[0][i]) / vmax * 65535)
                    r_points.append([j, n])
                if g:
                    n = round(float(data[1][i]) / vmax * 65535)
                    g_points.append([j, n])
                if b:
                    n = round(float(data[2][i]) / vmax * 65535)
                    b_points.append([j, n])
        else:  # formula
            irange = list(range(256))
            step = 100.0 / 255.0
            for i in irange:
                linear_points.append([i, i / 255.0 * 65535])
                if r:
                    vmin = vcgt["redMin"] * 65535
                    v = math.pow(step * i / 100.0, vcgt["redGamma"])
                    vmax = vcgt["redMax"] * 65535
                    r_points.append([i, round(vmin + v * (vmax - vmin))])
                if g:
                    vmin = vcgt["greenMin"] * 65535
                    v = math.pow(step * i / 100.0, vcgt["greenGamma"])
                    vmax = vcgt["greenMax"] * 65535
                    g_points.append([i, round(vmin + v * (vmax - vmin))])
                if b:
                    vmin = vcgt["blueMin"] * 65535
                    v = math.pow(step * i / 100.0, vcgt["blueGamma"])
                    vmax = vcgt["blueMax"] * 65535
                    b_points.append([i, round(vmin + v * (vmax - vmin))])
        return r_points, g_points, b_points, linear_points

    def printNormalizedValues(  # noqa: N802
        self, amount: None | int = None, digits: int = 12
    ) -> None:
        """Normalize and prints all values in the vcgt (range of 0.0...1.0).

        For a 256-entry table with linear values from 0 to 65535:
        #   REF            C1             C2             C3
        001 0.000000000000 0.000000000000 0.000000000000 0.000000000000
        002 0.003921568627 0.003921568627 0.003921568627 0.003921568627
        003 0.007843137255 0.007843137255 0.007843137255 0.007843137255
        ...
        You can also specify the amount of values to print (where a value
        lesser than the entry count will leave out intermediate values)
        and the number of digits.

        Args:
            amount (None | int, optional): The number of values to print.
                If None, it defaults to the entryCount if available, otherwise
                to 256.
            digits (int, optional): The number of digits to round the values
                to. Defaults to 12.
        """
        if amount is None:
            # use entryCount if exists, otherwise use the common value
            amount = self.entryCount if hasattr(self, "entryCount") else 256
        values = self.getNormalizedValues(amount)
        entry_count = len(values)
        channels = len(values[0])
        header = ["REF"]
        header.extend(f"C{k + 1}" for k in range(channels))
        header = [title.ljust(digits + 2) for title in header]
        print("#".ljust(len(str(amount)) + 1) + " ".join(header))
        for i, value in enumerate(values):
            formatted_values = [
                str(round(channel, digits)).ljust(digits + 2, "0") for channel in value
            ]
            print(
                str(i + 1).rjust(len(str(amount)), "0"),
                str(round(i / float(entry_count - 1), digits)).ljust(digits + 2, "0"),
                " ".join(formatted_values),
            )


class VideoCardGammaFormulaType(VideoCardGammaType):
    """Video card gamma formula type class.

    Args:
        tagData (bytes): The raw tag data containing the video LUT curves.
        tagSignature (str): The signature of the tag, typically "vcgt".
    """

    def __init__(self, tagData: bytes, tagSignature: str) -> None:  # noqa: N803
        VideoCardGammaType.__init__(self, tagData, tagSignature)
        data = tagData[12:]
        self.update(
            {
                "redGamma": u16Fixed16Number(data[0:4]),
                "redMin": u16Fixed16Number(data[4:8]),
                "redMax": u16Fixed16Number(data[8:12]),
                "greenGamma": u16Fixed16Number(data[12:16]),
                "greenMin": u16Fixed16Number(data[16:20]),
                "greenMax": u16Fixed16Number(data[20:24]),
                "blueGamma": u16Fixed16Number(data[24:28]),
                "blueMin": u16Fixed16Number(data[28:32]),
                "blueMax": u16Fixed16Number(data[32:36]),
            }
        )

    def getNormalizedValues(self, amount: None | int = None) -> list:  # noqa: N802
        """Return normalized values of the video LUT curves.

        Args:
            amount (None | int, optional): The number of values to return. If
                None, it defaults to 256.

        Returns:
            list: A list of tuples, each containing normalized values for the
                red, green, and blue channels.
        """
        if amount is None:
            amount = 256  # common value
        step = 1.0 / float(amount - 1)
        rgb = AODict([("red", []), ("green", []), ("blue", [])])
        for i in range(amount):
            for key in rgb:
                rgb[key].append(
                    float(self[key + "Min"])
                    + math.pow(step * i / 1.0, float(self[key + "Gamma"]))
                    * float(self[key + "Max"] - self[key + "Min"])
                )
        return list(zip(*list(rgb.values())))

    def getTableType(  # noqa: N802
        self,
        entryCount: int = 256,  # noqa: N803
        entrySize: int = 2,  # noqa: N803
        quantizer: Callable = round,  # noqa: N803
    ) -> VideoCardGammaTableType:
        """Return gamma as table type.

        Args:
            entryCount (int, optional): The number of entries in the table.
                Defaults to 256.
            entrySize (int, optional): The size of each entry in bytes.
                Defaults to 2.
            quantizer (Callable, optional): A function to quantize the values.
                Defaults to `round`.

        Returns:
            VideoCardGammaTableType: A new instance of VideoCardGammaTableType
                containing the gamma table data.
        """
        max_value = math.pow(256, entrySize) - 1
        tag_data = [
            self.tagData[:8],
            uInt32Number_tohex(0),  # type 0 = table
            uInt16Number_tohex(3),  # channels
            uInt16Number_tohex(entryCount),
            uInt16Number_tohex(entrySize),
        ]
        int2hex = {
            1: uInt8Number_tohex,
            2: uInt16Number_tohex,
            4: uInt32Number_tohex,
            8: uInt64Number_tohex,
        }
        for key in ("red", "green", "blue"):
            for i in range(entryCount):
                vmin = float(self[key + "Min"])
                vmax = float(self[key + "Max"])
                gamma = float(self[key + "Gamma"])
                v = vmin + math.pow(1.0 / (entryCount - 1) * i, gamma) * float(
                    vmax - vmin
                )
                tag_data.append(int2hex[entrySize](quantizer(v * max_value)))
        return VideoCardGammaTableType(b"".join(tag_data), self.tagSignature)


class VideoCardGammaTableType(VideoCardGammaType):
    """Video card gamma table type class.

    Args:
        tagData (bytes): The raw tag data containing the video LUT curves.
        tagSignature (str): The signature of the tag, typically "vcgt".
    """

    def __init__(self, tagData: bytes, tagSignature: str) -> None:  # noqa: N803
        VideoCardGammaType.__init__(self, tagData, tagSignature)
        if not tagData:
            self.update({"channels": 0, "entryCount": 0, "entrySize": 0, "data": []})
            return
        data = tagData[12:]
        channels = uInt16Number(data[0:2])
        entry_count = uInt16Number(data[2:4])
        entry_size = uInt16Number(data[4:6])
        self.update(
            {
                "channels": channels,
                "entryCount": entry_count,
                "entrySize": entry_size,
                "data": [],
            }
        )
        hex2int = {1: uInt8Number, 2: uInt16Number, 4: uInt32Number, 8: uInt64Number}
        if entry_size not in hex2int:
            raise ValueError(
                f"Invalid VideoCardGammaTableType entry size {int(entry_size):d}"
            )
        i = 0
        while i < channels:
            self.data.append([])
            j = 0
            while j < entry_count:
                index = 6 + i * entry_count * entry_size + j * entry_size
                self.data[i].append(
                    hex2int[entry_size](data[index : index + entry_size])
                )
                j = j + 1
            i = i + 1

    def getNormalizedValues(self, amount: None | int = None) -> list:  # noqa: N802
        """Return normalized values of the video LUT curves.

        Args:
            amount (None | int, optional): The number of values to return. If
                None, it defaults to the entryCount of the video LUT curves.

        Returns:
            list: A list of tuples, each containing normalized values for the
                red, green, and blue channels.
        """
        if amount is None:
            amount = self.entryCount
        max_value = math.pow(256, self.entrySize) - 1
        values = list(
            zip(*[[entry / max_value for entry in channel] for channel in self.data])
        )
        if amount <= self.entryCount:
            step = self.entryCount / float(amount - 1)
            all_values = values
            values = []
            for i, value in enumerate(all_values):
                if i == 0 or (i + 1) % step < 1 or i + 1 == self.entryCount:
                    values.append(value)
        return values

    def getFormulaType(self) -> VideoCardGammaFormulaType:  # noqa: N802
        """Return formula representing gamma value at 50% input.

        Returns:
            VideoCardGammaFormulaType: A new instance of
                VideoCardGammaFormulaType with the calculated gamma values and
                min/max values for each channel.
        """
        max_value = math.pow(256, self.entrySize) - 1
        tag_data = [self.tagData[:8], uInt32Number_tohex(1)]  # type 1 = formula
        data = list(self.data)
        while len(data) < 3:
            data.append(data[0])
        for channel in data:
            channel_length = (len(channel) - 1) / 2.0
            floor = float(channel[math.floor(channel_length)])
            ceil = float(channel[math.ceil(channel_length)])
            vmin = channel[0] / max_value
            vmax = channel[-1] / max_value
            v = (vmin + ((floor + ceil) / 2.0) * (vmax - vmin)) / max_value
            gamma = math.log(v) / math.log(0.5)
            print(vmin, gamma, vmax)
            tag_data.append(u16Fixed16Number_tohex(gamma))
            tag_data.append(u16Fixed16Number_tohex(vmin))
            tag_data.append(u16Fixed16Number_tohex(vmax))
        return VideoCardGammaFormulaType(b"".join(tag_data), self.tagSignature)

    def quantize(self, bits: int = 16, quantizer: Callable = round) -> None:
        """Quantize to n bits of precision.

        Note that when the quantize bits are not 8, 16, 32 or 64, double
        quantization will occur: First from the table precision bits according
        to entrySize to the chosen quantization bits, and then back to the
        table precision bits.

        Args:
            bits (int, optional): The number of bits to quantize to. Must be
                one of 8, 16, 32, or 64. Defaults to 16.
            quantizer (callable, optional): A function to quantize the values.
                Defaults to the built-in `round` function.
        """
        oldmax = math.pow(256, self.entrySize) - 1
        if bits in (8, 16, 32, 64):
            self.entrySize = int(bits / 8)
        bitv = 2.0**bits
        newmax = math.pow(256, self.entrySize) - 1
        for _i, channel in enumerate(self.data):
            for j, value in enumerate(channel):
                channel[j] = int(quantizer(value / oldmax * bitv) / bitv * newmax)

    def resize(self, length: int = 128) -> None:
        """Resize video LUT curves to a given length.

        Args:
            length (int): The desired length of the resized LUT curves.
        """
        data = [[], [], []]
        for i, channel in enumerate(self.data):
            for j in range(length):
                j *= (len(channel) - 1) / float(length - 1)
                if int(j) != j:
                    floor = channel[math.floor(j)]
                    ceil = channel[min(math.ceil(j), len(channel) - 1)]
                    interpolated = range(floor, ceil + 1)
                    fraction = j - int(j)
                    index = round(fraction * (ceil - floor))
                    v = interpolated[index]
                else:
                    v = channel[int(j)]
                data[i].append(v)
        self.data = data
        self.entryCount = len(data[0])

    def resized(self, length: int = 128) -> VideoCardGammaTableType:
        """Return a resized version of the video LUT curves.

        Args:
            length (int): The desired length of the resized LUT curves.

        Returns:
            VideoCardGammaTableType: A new instance of VideoCardGammaTableType
                with the resized LUT curves.
        """
        resized = self.__class__(self.tagData, self.tagSignature)
        resized.resize(length)
        return resized

    def smooth_cr(self, length: int = 64) -> None:
        """Smooth video LUT curves (Catmull-Rom).

        Args:
            length (int): The desired length of the smoothed LUT curves.
                Defaults to 64.
        """
        resized = self.resized(length)
        for i in range(len(self.data)):
            step = float(length - 1) / (len(self.data[i]) - 1)
            interpolation = CRInterpolation(resized.data[i])
            for j in range(len(self.data[i])):
                self.data[i][j] = interpolation(j * step)

    def smooth_avg(self, passes: int = 1, window: None | list | tuple = None) -> None:
        """Smooth video LUT curves (moving average).

        Args:
            passes (int): Number of passes to perform. Defaults to 1.
            window (None | list | tuple , optional): Tuple or list containing
                weighting factors. Its length determines the size of the window
                to use. Defaults to (1.0, 1.0, 1.0).
        """
        for i, channel in enumerate(self.data):
            self.data[i] = colormath.smooth_avg(channel, passes, window)
        self.entryCount = len(self.data[0])

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: The raw tag data formatted as bytes.
        """
        tag_data = [
            b"vcgt",
            b"\0" * 4,
            uInt32Number_tohex(0),  # type 0 = table
            uInt16Number_tohex(len(self.data)),  # channels
            uInt16Number_tohex(self.entryCount),
            uInt16Number_tohex(self.entrySize),
        ]
        int2hex = {
            1: uInt8Number_tohex,
            2: uInt16Number_tohex,
            4: uInt32Number_tohex,
            8: uInt64Number_tohex,
        }
        tag_data.extend(
            int2hex[self.entrySize](channel[i])
            for channel in self.data
            for i in range(self.entryCount)
        )
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set the tag data.

        Does nothing in this case, as the tagData is generated
        from the internal data structure.

        Args:
            tagData (bytes): The raw tag data to set.
        """


class WcsProfilesTagType(ICCProfileTag, ADict):
    """ICC WCS profiles tag type.

    Args:
        tagData (bytes): The raw tag data.
        tagSignature (str): The signature of the tag.
        profile (ICCProfile): The ICC profile to which this tag belongs.
    """

    def __init__(self, tagData: bytes, tagSignature: str, profile: ICCProfile) -> None:  # noqa: N803
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.profile = profile
        for i, modelname in enumerate(
            ["ColorDeviceModel", "ColorAppearanceModel", "GamutMapModel"]
        ):
            j = i * 8
            if len(tagData) < 16 + j:
                break
            offset = uInt32Number(tagData[8 + j : 12 + j])
            size = uInt32Number(tagData[12 + j : 16 + j])
            if offset and size:
                from io import StringIO

                from defusedxml import ElementTree

                it = ElementTree.iterparse(StringIO(tagData[offset : offset + size]))
                for _event, elem in it:
                    elem.tag = elem.tag.split("}", 1)[-1]  # Strip all namespaces
                self[modelname] = it.root

    def get_vcgt(
        self,
        quantize: int | bool = False,
        quantizer: Callable = round,
    ) -> None | VideoCardGammaType:
        """Return calibration information (if present) as VideoCardGammaType.

        If quantize is set, a table quantized to <quantize> bits is returned.

        Note that when the quantize bits are not 8, 16, 32 or 64, multiple
        quantizations will occur: For quantization bits below 32, first to 32
        bits, then to the chosen quantization bits, then back to 32 bits (which
        will be the final table precision bits).

        Args:
            quantize (bool | int, optional): If True, quantize to 16 bits
                (default). If an integer, quantize to that many bits.
            quantizer (Callable, optional): A quantization function, defaults to
                `round`.

        Returns:
            None | VideoCardGammaType: Returns a VideoCardGammaType object if
                calibration information is present, otherwise None.
        """
        if quantize and not isinstance(quantize, int):
            raise ValueError(f"Invalid quantization bits: {quantize!r}")

        if "ColorDeviceModel" not in self:
            return None

        # Parse calibration information to VCGT
        cal = self.ColorDeviceModel.find("Calibration")
        if cal is None:
            return None
        agammaconf = cal.find("AdapterGammaConfiguration")
        if agammaconf is None:
            return None
        pcurves = agammaconf.find("ParameterizedCurves")
        if pcurves is None:
            return None
        vcgt_data = "vcgt"
        vcgt_data += b"\0" * 4
        vcgt_data += uInt32Number_tohex(1)  # Type 1 = formula
        for color in ("Red", "Green", "Blue"):
            trc = pcurves.find(color + "TRC")
            if trc is None:
                trc = {}
            vcgt_data += u16Fixed16Number_tohex(float(trc.get("Gamma", 1)))
            vcgt_data += u16Fixed16Number_tohex(float(trc.get("Offset1", 0)))
            vcgt_data += u16Fixed16Number_tohex(float(trc.get("Gain", 1)))
        vcgt = VideoCardGammaFormulaType(vcgt_data, "vcgt")
        if quantize:
            if quantize in (8, 16, 32, 64):
                entry_size = quantize / 8
            elif quantize < 32:
                entry_size = 4
            else:
                entry_size = 8
            vcgt = vcgt.getTableType(entrySize=entry_size, quantizer=quantizer)
            if quantize not in (8, 16, 32, 64):
                vcgt.quantize(quantize, quantizer)
        return vcgt


class NamedColor2Value:
    """Named Color 2 Value.

    Args:
        valueData (bytes, optional): Binary data containing the named color
            values.
        deviceCoordCount (int, optional): Number of device coordinates.
        pcs (str, optional): PCS name, either "XYZ" or "Lab".
        device (str, optional): Device name, either "RGB" or "Lab".
    """

    def __init__(
        self,
        valueData: bytes = b"\0" * 38,  # noqa: N803
        deviceCoordCount: int = 0,  # noqa: N803
        pcs: str = "XYZ",
        device: str = "RGB",
    ) -> None:
        self._pcsname = pcs
        self._devicename = device
        end = valueData[0:32].find(b"\0")
        if end < 0:
            end = 32
        self.rootName = valueData[0:end]
        self.pcsvalues = [
            uInt16Number(valueData[32:34]),
            uInt16Number(valueData[34:36]),
            uInt16Number(valueData[36:38]),
        ]

        self.pcs = AODict()
        for i, pcsvalue in enumerate(self.pcsvalues):
            if pcs == "Lab":
                if i == 0:
                    # L* range 0..100 + (25500 / 65280.0)
                    self.pcs[pcs[i]] = pcsvalue / 65536.0 * 256 / 255.0 * 100
                else:
                    # a, b range -128..127 + (255/256.0)
                    self.pcs[pcs[i]] = -128 + (pcsvalue / 65536.0 * 256)
            elif pcs == "XYZ":
                # X, Y, Z range 0..100 + (32767 / 32768.0)
                self.pcs[pcs[i]] = pcsvalue / 32768.0 * 100

        device_coords = []
        if deviceCoordCount > 0:
            device_coords.extend(
                uInt16Number(valueData[i : i + 2])
                for i in range(38, 38 + deviceCoordCount * 2, 2)
            )
        self.devicevalues = device_coords
        if device == "Lab":
            # L* range 0..100 + (25500 / 65280.0)
            # a, b range range -128..127 + (255 / 256.0)
            self.device = tuple(
                (
                    v / 65536.0 * 256 / 255.0 * 100
                    if i == 0
                    else -128 + (v / 65536.0 * 256)
                )
                for i, v in enumerate(device_coords)
            )
        elif device == "XYZ":
            # X, Y, Z range 0..100 + (32767 / 32768.0)
            self.device = tuple(v / 32768.0 * 100 for v in device_coords)
        else:
            # Device range 0..100
            self.device = tuple(v / 65535.0 * 100 for v in device_coords)

    @property
    def name(self) -> str:
        """Return the name of the named color.

        Returns:
            str: The name of the named color, decoded from bytes using
                'latin-1' encoding.
        """
        return str(Text(self.rootName.strip(b"\0")), "latin-1")

    def __repr__(self) -> str:
        """Return the string representation of the object.

        Returns:
            str: The string representation of the object.
        """
        pcs = []
        for key in self.pcs:
            value = self.pcs[key]
            pcs.append(f"{key}={value}")
        dev = [f"{value}" for value in self.device]
        return "{}({}, {{{}}}, [{}])".format(
            self.__class__.__name__,
            self.name,
            ", ".join(pcs),
            ", ".join(dev),
        )

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: Raw tag data containing the named color values.
        """
        value_data = []
        value_data.append(self.rootName.ljust(32, b"\0"))
        value_data.extend([uInt16Number_tohex(pcsval) for pcsval in self.pcsvalues])
        value_data.extend(
            [uInt16Number_tohex(deviceval) for deviceval in self.devicevalues]
        )
        return b"".join(value_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set tag data.

        Does nothing, as NamedColor2Value is immutable.

        Args:
            tagData (bytes): Raw tag data to set.
        """


class NamedColor2ValueTuple(tuple):
    """Tuple subclass for NamedColor2Value.

    This class is used to represent a tuple of NamedColor2Value objects.
    """

    __slots__ = ()
    REPR_OUTPUT_SIZE = 10

    def __repr__(self) -> str:
        """Return the string representation of the object.

        Truncates the output if it exceeds the specified size.

        Returns:
            str: The string representation of the object.
        """
        data = list(self[: self.REPR_OUTPUT_SIZE + 1])
        if len(data) > self.REPR_OUTPUT_SIZE:
            data[-1] = "...(remaining elements truncated)..."
        return repr(data)

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: Concatenated tag data from all NamedColor2Value objects in
                the tuple.
        """
        return b"".join([val.tagData for val in self])

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        pass


class NamedColor2Type(ICCProfileTag, AODict):
    """Named Color 2 Type.

    This tag contains a list of named colors, each with a set of device
    coordinates and a set of PCS coordinates. The device coordinates
    are used to identify the color on the device, while the PCS
    coordinates are used to identify the color in a device-independent
    color space. The tag also contains a prefix and suffix that are
    used to format the name of the color.

    Byte offset content encoded as:

        0..3    vendorData        s4Fixed32Number
        4..7    colorCount        uInt32Number
        8..11   deviceCoordCount  uInt32Number
        12..15  reserved          uInt32Number
        16..19  reserved          uInt32Number
        20..51  prefix            s32Fixed32Number
        52..83  suffix            s32Fixed32Number
        84..n   colorValues       NamedColor2Value

    Args:
        tagData (bytes): The raw tag data.
        tagSignature (None | str): The signature of the tag.
        pcs (None | str): The PCS name, either "XYZ" or "Lab".
        device (None | str): The device name, either "RGB" or "Lab".
    """

    REPR_OUTPUT_SIZE = 10

    def __init__(
        self,
        tagData: bytes = b"\0" * 84,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
        pcs: None | str = None,
        device: None | str = None,
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        AODict.__init__(self)

        colorCount = uInt32Number(tagData[12:16])  # noqa: N806
        deviceCoordCount = uInt32Number(tagData[16:20])  # noqa: N806
        stride = 38 + 2 * deviceCoordCount

        self.vendorData = tagData[8:12]
        self.colorCount = colorCount
        self.deviceCoordCount = deviceCoordCount
        self._prefix = Text(tagData[20:52])
        self._suffix = Text(tagData[52:84])
        self._pcsname = pcs
        self._devicename = device

        keys = []
        values = []
        if colorCount > 0:
            start = 84
            end = start + (stride * colorCount)
            for i in range(start, end, stride):
                nc2 = NamedColor2Value(
                    tagData[i : i + stride], deviceCoordCount, pcs=pcs, device=device
                )
                keys.append(nc2.name)
                values.append(nc2)
        self.update(dict(list(zip(keys, values))))

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Set an attribute of the object.

        Args:
            name (str): The name of the attribute to set.
            value (Any): The value to set the attribute to.
        """
        object.__setattr__(self, name, value)

    @property
    def prefix(self) -> str:
        """Return the prefix of the named color profile.

        Returns:
            str: The prefix of the named color profile, decoded from bytes
                using 'latin-1' encoding.
        """
        return str(self._prefix.strip(b"\0"), "latin-1")

    @property
    def suffix(self) -> str:
        """Return the suffix of the named color profile.

        Returns:
            str: The suffix of the named color profile, decoded from bytes
                using 'latin-1' encoding.
        """
        return str(self._suffix.strip(b"\0"), "latin-1")

    @property
    def colorValues(self) -> NamedColor2ValueTuple:  # noqa: N802
        """Return a tuple of NamedColor2Value objects.

        Returns:
            NamedColor2ValueTuple: A tuple containing all NamedColor2Value
                objects in the profile.
        """
        return NamedColor2ValueTuple(list(self.values()))

    def add_color(
        self,
        root_name: str,
        *device_coordinates: list[float],
        **pcs_coordinates: dict[str, float],
    ) -> None:
        """Add a named color to the profile.

        Args:
            root_name (str): The name of the color.
            device_coordinates (list): Device coordinates for the color.
            pcs_coordinates (dict): PCS coordinates for the color.

        Raises:
            ICCProfileInvalidError: If the required PCS coordinates or device
                coordinates are not provided, or if the color name already
                exists.
        """
        if self._pcsname == "Lab":
            keys = ["L", "a", "b"]
        elif self._pcsname == "XYZ":
            keys = ["X", "Y", "Z"]
        else:
            keys = ["X", "Y", "Z"]

        if not set(pcs_coordinates.keys()).issuperset(set(keys)):
            raise ICCProfileInvalidError(
                "Can't add namedColor2 without all 3 PCS coordinates: "  # noqa: UP032
                "'{}'".format(set(keys) - set(pcs_coordinates.keys()))
            )

        if len(device_coordinates) != self.deviceCoordCount:
            raise ICCProfileInvalidError(
                f"Can't add namedColor2 without all {self.deviceCoordCount} "
                f"device coordinates (called with {len(device_coordinates)})"
            )

        nc2value = NamedColor2Value()
        nc2value._pcsname = self._pcsname
        nc2value._devicename = self._devicename
        nc2value.rootName = root_name

        if root_name in list(self.keys()):
            raise ICCProfileInvalidError(
                f"Can't add namedColor2 with existant name: '{root_name}'"
            )

        nc2value.devicevalues = []
        nc2value.device = tuple(device_coordinates)
        nc2value.pcs = AODict(copy(pcs_coordinates))

        for idx, key in enumerate(keys):
            val = nc2value.pcs[key]
            if key == "L":
                nc2value.pcsvalues[idx] = val * 65536 / (256 / 255.0) / 100.0
            elif key in ("a", "b"):
                nc2value.pcsvalues[idx] = (val + 128) * 65536 / 256.0
            elif key in ("X", "Y", "Z"):
                nc2value.pcsvalues[idx] = val * 32768 / 100.0

        for idx, val in enumerate(nc2value.device):
            if self._devicename == "Lab":
                if idx == 0:
                    # L* range 0..100 + (25500 / 65280.0)
                    nc2value.devicevalues[idx] = val * 65536 / (256 / 255.0) / 100.0
                else:
                    # a, b range -128..127 + (255/256.0)
                    nc2value.devicevalues[idx] = (val + 128) * 65536 / 256.0
            elif self._devicename == "XYZ":
                # X, Y. Z range 0..100 + (32767 / 32768.0)
                nc2value.devicevalues[idx] = val * 32768 / 100.0
            else:
                # Device range 0..100
                nc2value.devicevalues[idx] = val * 65535 / 100.0

        self[nc2value.name] = nc2value

    def __repr__(self) -> str:
        """Return the string representation of the object.

        Truncates the output if it exceeds the specified size.

        Returns:
            str: The string representation of the object.
        """
        data = list(self.items())[: self.REPR_OUTPUT_SIZE + 1]
        if len(data) > self.REPR_OUTPUT_SIZE:
            data[-1] = ("...", "(remaining elements truncated)")
        return repr(dict(data))

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: Raw tag data containing vendor data, color count,
                device coordinate count, prefix, suffix, and color values.
        """
        tagData = [  # noqa: N806
            b"ncl2",
            b"\0" * 4,
            self.vendorData,
            uInt32Number_tohex(len(list(self.items()))),
            uInt32Number_tohex(self.deviceCoordCount),
            self._prefix.ljust(32),
            self._suffix.ljust(32),
            self.colorValues.tagData,
        ]
        return b"".join(tagData)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        pass


TAG_SIGNATURE_TO_TAG = {"arts": ChromaticAdaptionTag, "chad": ChromaticAdaptionTag}

TYPE_SIGNATURE_TO_TYPE = {
    b"chrm": ChromaticityType,
    b"clrt": ColorantTableType,
    b"curv": CurveType,
    b"desc": TextDescriptionType,  # ICC v2
    b"dict": DictType,  # ICC v2 + v4
    b"dtim": DateTimeType,
    b"meas": MeasurementType,
    b"mluc": MultiLocalizedUnicodeType,  # ICC v4
    b"mft2": LUT16Type,
    b"mmod": MakeAndModelType,  # Apple private tag
    b"ncl2": NamedColor2Type,
    b"para": ParametricCurveType,
    b"pseq": ProfileSequenceDescType,
    b"sf32": S15Fixed16ArrayType,
    b"sig ": SignatureType,
    b"text": TextType,
    b"vcgt": videoCardGamma,
    b"view": ViewingConditionsType,
    b"MS10": WcsProfilesTagType,
    b"XYZ ": XYZType,
}


class ICCProfileInvalidError(IOError):
    """Exception raised when an invalid ICC profile is encountered."""


_ICCPROFILE_CACHE = WeakValueDictionary()


class ICCProfile:
    """Return a new ICCProfile object.

    Optionally initialized with a string containing binary profile data or
    a filename, or a file-like object. Also, if the 'load' keyword argument
    is False (default True), only the header will be read initially and
    loading of the tags will be deferred to when they are accessed the
    first time.

    Args:
        profile (None | str | pathlib.Path | bytes | BinaryIO | TextIO, optional):
            The ICC profile data to load. This can be a string or
            pathlib.Path representing a file path, a bytes object
            containing the profile data, or a file-like object.
        load (bool, optional): If True, the profile will be loaded
            immediately. If False, only the header will be read.
        use_cache (bool, optional): If True, the profile will be cached
            to avoid reloading it if it has already been loaded.
    """

    _recent: ClassVar[list] = []

    def __new__(
        cls,
        profile: None | bytes | str | pathlib.Path | BinaryIO | TextIO = None,
        load: bool = True,
        use_cache: bool = False,
    ) -> Self:
        """Look up a cached ICCProfile instance, or allocate a new one.

        This is only responsible for the cache identity check, returning an
        already-loaded instance from `_ICCPROFILE_CACHE` if one matches
        `profile`. All actual profile loading/parsing happens in `__init__`.

        Args:
            profile (None, bytes, str, pathlib.Path, file-like object, optional):
                The ICC profile data to load. This can be a string or
                pathlib.Path representing a file path, a bytes object
                containing the profile data, or a file-like object.
            load (bool, optional): Unused here, kept for signature parity
                with `__init__` since Python calls both with the same args.
            use_cache (bool, optional): If True, resolve a cache key for
                `profile` and return a matching cached instance if found.

        Raises:
            ICCProfileInvalidError: If a path profile is empty.

        Returns:
            ICCProfile: Either a cached instance, or a freshly allocated
            (not yet initialized) instance.
        """
        key = None
        # the content of the profile should be passed as bytes in Python 3.
        if isinstance(profile, (str, pathlib.Path)):
            # Filename
            if not profile:
                raise ICCProfileInvalidError("Empty path given")

            p = pathlib.Path(profile) if isinstance(profile, str) else profile

            if not p.is_file() and not p.is_absolute():
                search_paths = list(set(ICCPROFILES_HOME + ICCPROFILES))
                found_profile = False
                while search_paths and not found_profile:
                    search_path = pathlib.Path(search_paths.pop(0))
                    if not search_path.is_dir():  # only look in to directories
                        continue
                    for entry in search_path.glob(p.name):
                        if not entry.is_file():
                            continue
                        profile = str(entry)
                        # TODO: update this to stay a Path instance after
                        #       migration to pathlib is completed
                        found_profile = True
                        break

            if use_cache:
                stat = os.stat(profile)
                key = (profile, stat.st_dev, stat.st_ino, stat.st_mtime, stat.st_size)
            else:
                key = ()
        elif isinstance(profile, bytes):
            # Binary string
            if use_cache:
                key = md5(profile).hexdigest()  # noqa: S324

        if use_cache:
            chk = _ICCPROFILE_CACHE.get(key)
            if chk:
                return chk

        self = super().__new__(cls)

        if use_cache and key:
            _ICCPROFILE_CACHE[key] = self

            # Make sure most recent three are not garbage collected
            if len(ICCProfile._recent) == 3:
                ICCProfile._recent.pop(0)
            ICCProfile._recent.append(self)

        self._key = key
        self._resolved_profile = profile
        return self

    def __init__(
        self,
        profile: None | bytes | str | pathlib.Path | BinaryIO | TextIO = None,
        load: bool = True,
        use_cache: bool = False,
    ) -> None:
        """Initialize the ICCProfile instance.

        Optionally initialized with a string containing binary profile data or
        a filename, or a file-like object. Also, if the 'load' keyword argument
        is False (default True), only the header will be read initially and
        loading of the tags will be deferred to when they are accessed the
        first time.

        Args:
            profile (None, bytes, str, pathlib.Path, file-like object, optional):
                The ICC profile data to load. This can be a string or
                pathlib.Path representing a file path, a bytes object
                containing the profile data, or a file-like object.
            load (bool, optional): If True, the profile will be loaded
                immediately. If False, only the header will be read.
            use_cache (bool, optional): Unused here (already applied by
                `__new__`), kept for signature parity.

        Raises:
            ICCProfileInvalidError: If the profile data is invalid or
                if the profile cannot be loaded.
        """
        if getattr(self, "_initialized", False):
            # Cache hit: __new__ returned an already-initialized instance.
            return

        profile = self.__dict__.pop("_resolved_profile")

        self.ID = b"\0" * 16
        self._data = b""
        self._file = None
        self._tagoffsets = []  # Original tag offsets
        self._tags = LazyLoadTagAODict(self)
        self.filename = None
        self.is_loaded = False
        self.size = 0
        self._initialized = True

        if isinstance(self._key, tuple):
            # Filename
            profile = open(profile, "rb")  # noqa: SIM115

        if profile is None:
            self.set_defaults()
            return

        if isinstance(profile, bytes):
            # Binary string
            data = profile
            self.is_loaded = True
        else:
            # File object
            self._file = profile
            self.filename = self._file.name
            self._file.seek(0)
            data = self._file.read(128)
            self.close()

        if not data or len(data) < 128:
            raise ICCProfileInvalidError("Not enough data")

        if data[:5] == b"<?xml" or data[:10] == b"<\0?\0x\0m\0l\0":
            # Microsoft WCS profile
            from io import BytesIO

            from defusedxml import ElementTree

            self.filename = None
            self._data = data
            self.load()
            data = self._data
            self._data = b""
            self.set_defaults()
            it = ElementTree.iterparse(BytesIO(data))
            try:
                for _event, elem in it:
                    # Strip all namespaces
                    elem.tag = elem.tag.split("}", 1)[-1]
            except ElementTree.ParseError as e:
                raise ICCProfileInvalidError("Invalid WCS profile") from e
            desc = it.root.find(b"Description")
            if desc is not None:
                desc = desc.find(b"Text")
                if desc is not None:
                    self.setDescription(str(desc.text, "UTF-8"))
            author = it.root.find(b"Author")
            if author is not None:
                author = author.find(b"Text")
                if author is not None:
                    self.setCopyright(str(author.text, "UTF-8"))
            device = it.root.find(b"RGBVirtualDevice")
            if device is not None:
                measurement_data = device.find(b"MeasurementData")
                if measurement_data is not None:
                    for color in (b"White", b"Red", b"Green", b"Blue", b"Black"):
                        prim = measurement_data.find(color + b"Primary")
                        if prim is None:
                            continue
                        XYZ = []  # noqa: N806
                        for component in b"XYZ":
                            try:
                                XYZ.append(float(prim.get(component)) / 100.0)
                            except (TypeError, ValueError) as e:
                                raise ICCProfileInvalidError(
                                    "Invalid WCS profile"
                                ) from e
                        if color == b"White":
                            tag_name = "wtpt"
                        elif color == b"Black":
                            tag_name = "bkpt"
                        else:
                            XYZ = colormath.adapt(  # noqa: N806
                                *XYZ,
                                whitepoint_source=list(self.tags.wtpt.values()),
                            )
                            tag_name = color[0].lower().decode() + "XYZ"
                        tag = self.tags[tag_name] = XYZType(profile=self)
                        tag.X, tag.Y, tag.Z = XYZ
                    gamma = measurement_data.find(b"GammaOffsetGainLinearGain")
                    if gamma is None:
                        gamma = measurement_data.find(b"GammaOffsetGain")
                    if gamma is not None:
                        params = {
                            "Gamma": 1,
                            "Offset": 0,
                            "Gain": 1,
                            "LinearGain": 1,
                            "TransitionPoint": -1,
                        }
                        for att in list(params.keys()):
                            try:
                                params[att] = float(gamma.get(att))
                            except (TypeError, ValueError) as e:
                                if (
                                    att not in ("LinearGain", "TransitionPoint")
                                    or gamma.tag != "GammaOffsetGain"
                                ):
                                    raise ICCProfileInvalidError(
                                        "Invalid WCS profile"
                                    ) from e

                        def power(a: float) -> float:
                            """Calculate power value based on gamma and parameters.

                            Args:
                                a (float): The input value to calculate the power for.
                            """
                            if a <= params["TransitionPoint"]:
                                v = a / params["LinearGain"]
                            else:
                                v = math.pow(
                                    (a + params["Offset"]) * params["Gain"],
                                    params["Gamma"],
                                )
                            return v

                    else:
                        gamma = measurement_data.find("Gamma")
                        if gamma is not None:
                            try:
                                power = float(gamma.get("value"))
                            except (TypeError, ValueError) as e:
                                raise ICCProfileInvalidError(
                                    "Invalid WCS profile"
                                ) from e
                    if gamma is not None:
                        self.set_trc_tags(True, power)
            if it.root.tag == "ColorDeviceModel":
                ms00 = WcsProfilesTagType(b"", "MS00", self)
                ms00["ColorDeviceModel"] = it.root
                vcgt = ms00.get_vcgt()
                if vcgt:
                    self.tags["vcgt"] = vcgt
            self.size = len(self.data)
            return

        if data[36:40] != b"acsp":
            raise ICCProfileInvalidError(
                "Profile signature mismatch - expected 'acsp', found '"
                + data[36:40].decode("utf-8")
                + "'"
            )

        # ICC profile
        header = data[:128]
        self.size = uInt32Number(header[0:4])
        self.preferredCMM = header[4:8]
        minorrev_bugfixrev = binascii.hexlify(header[8:12][1:2])
        self.version = float(
            "{}.{}".format(
                header[8:12][0],
                str(int(b"0x0" + minorrev_bugfixrev[0:1], 16))
                + str(int(b"0x0" + minorrev_bugfixrev[1:2], 16)),
            )
        )
        self.profileClass = header[12:16]
        self.colorSpace = header[16:20].strip()
        self.connectionColorSpace = header[20:24].strip()
        try:
            self.dateTime = dateTimeNumber(header[24:36])
        except ValueError as e:
            raise ICCProfileInvalidError("Profile creation date/time invalid") from e
        self.platform = header[40:44]
        flags = uInt32Number(header[44:48])
        self.embedded = flags & 1 != 0
        self.independent = flags & 2 == 0
        deviceAttributes = uInt32Number(header[56:60])  # noqa: N806

        self.device = {
            "manufacturer": header[48:52],
            "model": header[52:56],
            "attributes": {
                "reflective": deviceAttributes & 1 == 0,
                "glossy": deviceAttributes & 2 == 0,
                "positive": deviceAttributes & 4 == 0,
                "color": deviceAttributes & 8 == 0,
            },
        }
        self.intent = uInt32Number(header[64:68])
        self.illuminant = XYZNumber(header[68:80])
        self.creator = header[80:84]
        if header[84:100] != b"\0" * 16:
            self.ID = header[84:100]

        self._data = data[: self.size]

        if load:
            _ = self.tags

    def set_defaults(self) -> None:
        """Set default values for the ICC profile."""
        if hasattr(self, "version"):
            return  # Already initialized
        # Default to RGB display device profile
        self.preferredCMM = b"argl"
        self.version = 2.4
        self.profileClass = b"mntr"
        self.colorSpace = b"RGB"
        self.connectionColorSpace = b"XYZ"
        self.dateTime = datetime.datetime.now()
        if sys.platform == "win32":
            platform_id = b"MSFT"  # Microsoft
        elif sys.platform == "darwin":
            platform_id = b"APPL"  # Apple
        else:
            platform_id = b"*nix"
        self.platform = platform_id
        self.embedded = False
        self.independent = True
        self.device = {
            "manufacturer": b"",
            "model": b"",
            "attributes": {
                "reflective": True,
                "glossy": True,
                "positive": True,
                "color": True,
            },
        }
        self.intent = 0
        self.illuminant = XYZNumber(b"\0\0\xf6\xd6\0\x01\0\0\0\0\xd3-")  # D50
        self.creator = b"DCAL"  # DisplayCAL

    def __len__(self) -> int:
        """Return the number of tags.

        Can also be used in boolean comparisons (profiles with no tags
        evaluate to false).

        Returns:
            int: The number of tags in the profile.
        """
        return len(self.tags)

    @property
    def data(self) -> bytes:
        """Get raw binary profile data.

        This will re-assemble the various profile parts (header, tag table and data)
        on-the-fly.

        Returns:
            bytes: The raw binary profile data.
        """
        # Assemble tag table and tag data
        tagCount = len(self.tags)  # noqa: N806
        tagTable = {}  # noqa: N806
        tagTableSize = tagCount * 12  # noqa: N806
        tagsData = []  # noqa: N806
        tagsDataOffset = []  # noqa: N806
        tagDataOffset = 128 + 4 + tagTableSize  # noqa: N806
        tags = []
        # Order of tag table and actual tag data may be different.
        # Keep order of tags according to original offsets (if any).
        for _oOffset, tagSignature in sorted(self._tagoffsets):  # noqa: N806
            if tagSignature in self.tags:
                tags.append(tagSignature)

        # Keep tag table order
        for tagSignature in self.tags:  # noqa: N806
            tagTable[tagSignature] = tagSignature.encode()
            if tagSignature not in tags:
                tags.append(tagSignature)

        for tagSignature in tags:  # noqa: N806
            tag = AODict.__getitem__(self.tags, tagSignature)
            if isinstance(tag, ICCProfileTag):
                tagData = self.tags[tagSignature].tagData  # noqa: N806
            else:
                tagData = tag[3]  # noqa: N806
            tagDataSize = len(tagData)  # noqa: N806
            # Pad all data with binary zeros, so it lies on 4-byte boundaries
            padding = math.ceil(tagDataSize / 4.0) * 4 - tagDataSize
            tagData += b"\0" * padding  # noqa: N806
            if (
                tagDataOffset,
                tagSignature,
            ) not in self._tagoffsets and tagData in tagsData:
                tagTable[tagSignature] += uInt32Number_tohex(
                    tagsDataOffset[tagsData.index(tagData)]
                )
            else:
                tagTable[tagSignature] += uInt32Number_tohex(tagDataOffset)
                tagsData.append(tagData)
                tagsDataOffset.append(tagDataOffset)
                tagDataOffset += tagDataSize + padding  # noqa: N806
            tagTable[tagSignature] += uInt32Number_tohex(tagDataSize)
        tagsData = b"".join(tagsData)  # noqa: N806
        header = self.header(tagTableSize, len(tagsData))
        return b"".join(
            [
                header,
                uInt32Number_tohex(tagCount),
                b"".join(list(tagTable.values())),
                tagsData,
            ]
        )

    def header(self, tagTableSize: int, tagDataSize: int) -> bytes:  # noqa: N803
        """Profile Header.

        Args:
            tagTableSize (int): Size of the tag table in bytes.
            tagDataSize (int): Size of the tag data in bytes.

        Returns:
            bytes: The profile header as a byte string.
        """
        # Profile size: 128 bytes header + 4 bytes tag count + tag table + data
        header = [
            uInt32Number_tohex(128 + 4 + tagTableSize + tagDataSize),
            self.preferredCMM[:4].ljust(4, b" ") if self.preferredCMM else b"\0" * 4,
            # Next three lines are ICC version
            chr(int(str(self.version).split(".")[0])).encode(),
            binascii.unhexlify((f"{self.version:.2f}").split(".")[1]),
            b"\0" * 2,
            self.profileClass[:4].ljust(4, b" "),
            self.colorSpace[:4].ljust(4, b" "),
            self.connectionColorSpace[:4].ljust(4, b" "),
            dateTimeNumber_tohex(self.dateTime),
            b"acsp",
            self.platform[:4].ljust(4, b" ") if self.platform else b"\0" * 4,
        ]

        flags = 0
        if self.embedded:
            flags += 1
        if not self.independent:
            flags += 2

        header.extend(
            [
                uInt32Number_tohex(flags),
                (
                    self.device["manufacturer"][:4].rjust(4, b"\0")
                    if self.device["manufacturer"]
                    else b"\0" * 4
                ),
                (
                    self.device["model"][:4].rjust(4, b"\0")
                    if self.device["model"]
                    else b"\0" * 4
                ),
            ]
        )
        deviceAttributes = 0  # noqa: N806
        for name, bit in {
            "reflective": 1,
            "glossy": 2,
            "positive": 4,
            "color": 8,
        }.items():
            if not self.device["attributes"][name]:
                deviceAttributes += bit  # noqa: N806
        if sys.platform == "darwin" and self.version < 4:
            # Dont't include ID under Mac OS X unless v4 profile
            # to stop pedantic ColorSync utility from complaining
            # about header padding not being null
            id_ = b""
        else:
            id_ = self.ID[:16]

        if isinstance(self._data, str):
            self._data = self._data.encode()

        header.extend(
            [
                uInt32Number_tohex(deviceAttributes) + b"\0" * 4,
                uInt32Number_tohex(self.intent),
                self.illuminant.tohex(),
                self.creator[:4].ljust(4, b" ") if self.creator else b"\0" * 4,
                id_.ljust(16, b"\0"),
                self._data[100:128] if len(self._data[100:128]) == 28 else b"\0" * 28,
            ]
        )

        return b"".join(header)

    @property
    def tags(self) -> LazyLoadTagAODict:
        """Profile Tag Table.

        Raises:
            ICCProfileInvalidError: If the tag table is truncated or
                if a tag signature is already encountered.

        Returns:
            LazyLoadTagAODict: A dictionary-like object containing the
                profile's tags.
        """
        if self._tags:
            return self._tags

        self.load()
        if not self._data or len(self._data) <= 131:
            return self._tags

        # tag table and tagged element data
        tagCount = uInt32Number(self._data[128:132])  # noqa: N806
        if DEBUG:
            print("tagCount:", tagCount)

        tagTable = self._data[132 : 132 + tagCount * 12]  # noqa: N806
        self._tagoffsets = []
        discard_len = 0
        tags = {}
        while tagTable:
            tag = tagTable[:12]
            if len(tag) < 12:
                raise ICCProfileInvalidError("Tag table is truncated")

            tagSignature = tag[:4].decode()  # noqa: N806
            if DEBUG:
                print("tagSignature:", tagSignature)

            tagDataOffset = uInt32Number(tag[4:8])  # noqa: N806
            self._tagoffsets.append((tagDataOffset, tagSignature))
            if DEBUG:
                print("    tagDataOffset:", tagDataOffset)

            tagDataSize = uInt32Number(tag[8:12])  # noqa: N806
            if DEBUG:
                print("    tagDataSize:", tagDataSize)

            if tagSignature in self._tags:
                print(
                    f"Error (non-critical): Tag '{tagSignature}' "
                    "already encountered. Skipping..."
                )
            else:
                if (tagDataOffset, tagDataSize) in tags:
                    if DEBUG:
                        print("    tagDataOffset and tagDataSize indicate shared tag")
                else:
                    start = tagDataOffset - discard_len
                    if DEBUG:
                        print("    tagData start:", start)

                    end = tagDataOffset - discard_len + tagDataSize
                    if DEBUG:
                        print("    tagData end:", end)

                    tagData = self._data[start:end]  # noqa: N806
                    if len(tagData) < tagDataSize:
                        print(
                            f"Warning: Tag data for tag {tagSignature!r} "
                            f"is truncated (offset {int(tagDataOffset):d}, "
                            f"expected size {int(tagDataSize):d}, "
                            f"actual size {len(tagData):d})"
                        )
                        tagDataSize = len(tagData)  # noqa: N806
                    typeSignature = tagData[:4]  # noqa: N806
                    if len(typeSignature) < 4:
                        print(
                            "Warning: Tag type signature for tag "
                            f"{tagSignature!r} is truncated "
                            f"(offset {int(tagDataOffset):d}, "
                            f"size {int(tagDataSize):d})"
                        )
                        typeSignature = typeSignature.ljust(4, b" ")  # noqa: N806
                    if DEBUG:
                        print("    typeSignature:", typeSignature)
                    tags[(tagDataOffset, tagDataSize)] = (
                        typeSignature,
                        tagDataOffset,
                        tagDataSize,
                        tagData,
                    )
                self._tags[tagSignature] = tags[(tagDataOffset, tagDataSize)]
            tagTable = tagTable[12:]  # noqa: N806

        self._data = self._data[:128]
        return self._tags

    def calculate_id(self, set_id: bool = True) -> bytes:
        """Calculates, sets, and returns the profile's ID (checksum).

        Calling this function always recalculates the checksum on-the-fly,
        in contrast to just accessing the ID property.

        The entire profile, based on the size field in the header, is used
        to calculate the ID after the values in the Profile Flags field
        (bytes 44 to 47), Rendering Intent field (bytes 64 to 67) and
        Profile ID field (bytes 84 to 99) in the profile header have been
        temporarily replaced with zeros.

        Args:
            set_id (bool, optional): If True, the calculated ID will be set as
                the profile's ID. If False, the ID will not be set, but still
                returned. Defaults to True.

        Returns:
            bytes: The calculated ID as a 16-byte binary string.
        """
        data = self.data
        data = (
            data[:44]
            + b"\0\0\0\0"
            + data[48:64]
            + b"\0\0\0\0"
            + data[68:84]
            + b"\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0"
            + data[100:]
        )
        id_ = md5(data).digest()  # noqa: S324
        if set_id:
            if id_ != self.ID:
                # No longer reflects original profile
                self._delfromcache()
            self.ID = id_
        return id_

    def close(self) -> None:
        """Close the associated file object (if any)."""
        if self._file and not self._file.closed:
            self._file.close()

    def convert_iccv4_tags_to_iccv2(
        self,
        version: float = 2.4,
        undo_wtpt_chad: bool = False,
    ) -> bool:
        """Convert ICCv4 parametric curve tags to ICCv2-compatible curve tags.

        If desired version after conversion is < 2.4 and undo_wtpt_chad is True,
        also set whitepoint to illuinant relative values, and remove any
        chromatic adaptation tag.

        If ICC profile version is < 4 or no [rgb]TRC tags or LUT16Type tags,
        return False.
        Otherwise, convert curve tags and return True.

        Args:
            version (float, optional): The desired ICC profile version after
                conversion. Defaults to 2.4.
            undo_wtpt_chad (bool, optional): If True, set whitepoint to
                illuminant relative values and remove chromatic adaptation tag
                if present. Defaults to False.

        Returns:
            bool: True if conversion was successful, False if the profile
        """
        if self.version < 4:
            return False
        # Fail if any LUT tag is not LUT16Type as we currently
        # have not implemented conversion (which may not even
        # be possible, depending on LUT contents)
        has_lut_tags = False
        for direction in ("A2B", "B2A"):
            for tableno in range(3):
                tag = self.tags.get(f"{direction}{tableno}")
                if tag:
                    if isinstance(tag, LUT16Type):
                        has_lut_tags = True
                    else:
                        return False
        if self.has_trc_tags():
            for channel in "rgb":
                tag = self.tags[channel + "TRC"]
                if isinstance(tag, ParametricCurveType):
                    # Convert to CurveType
                    self.tags[channel + "TRC"] = tag.get_trc()
        elif not has_lut_tags:
            return False
        # Set filename to None because our profile no longer reflects the file
        # on disk and remove from cache
        self.filename = None
        self._delfromcache()
        if version < 2.4 and undo_wtpt_chad:
            # Set whitepoint tag to illuminant relative and remove chromatic
            # adaptation tag afterwards(!)
            self.tags.wtpt = self.tags.wtpt.ir
            if "chad" in self.tags:
                del self.tags["chad"]
        # Get all multiLocalizedUnicodeType tags
        mluc = {}
        for tagname in self.tags:
            tag = self.tags[tagname]
            if isinstance(tag, MultiLocalizedUnicodeType):
                mluc[tagname] = str(tag)
        # Set profile version
        self.version = version
        # Convert to textDescriptionType/textType (after setting version to 2.x)
        for tagname in mluc:
            unistr = mluc[tagname]
            if tagname == "cprt":
                self.setCopyright(unistr)
            else:
                self.set_localizable_desc(tagname, unistr)
        return True

    def convert_iccv2_tags_to_iccv4(self) -> bool:
        """Convert ICCv2 text description tags to ICCv4 multi-localized unicode.

        Also sets whitepoint to D50, and stores illuminant-relative to D50
        matrix as chromatic adaptation tag.

        If ICC profile version is >= 4, return False.
        Otherwise, convert and return True.

        After conversion, the profile version is 4.3

        Returns:
            bool: True if conversion was successful, False if the profile
                version is already >= 4.
        """
        if self.version >= 4:
            return False
        # Set filename to None because our profile no longer reflects the file
        # on disk and remove from cache
        self.filename = None
        self._delfromcache()
        wtpt = list(self.tags.wtpt.ir.values())
        # Set whitepoint tag to D50
        self.tags.wtpt = self.tags.wtpt.pcs
        if "chad" not in self.tags:
            # Set chromatic adaptation matrix
            self.tags["chad"] = ChromaticAdaptionTag()
            wpam = colormath.wp_adaption_matrix(
                wtpt, cat=self.tags.get("arts", "Bradford")
            )
            self.tags["chad"].update(wpam)
        # Get all textDescriptionType tags
        text = {}
        for tagname in self.tags:
            tag = self.tags[tagname]
            if tagname == "cprt" or isinstance(tag, TextDescriptionType):
                text[tagname] = str(tag)
        # Set profile version to 4.3
        self.version = 4.3
        # Convert to multiLocalizedUnicodeType (after setting version to 4.x)
        for tagname in text:
            unistr = text[tagname]
            self.set_localizable_text(tagname, unistr)
        return True

    @staticmethod
    def from_named_rgb_space(
        rgb_space_name: str,
        iccv4: bool = False,
        cat: str = "Bradford",
        profile_class: bytes = b"mntr",
    ) -> ICCProfile:
        """Create an ICC Profile from a named RGB space and return it.

        Args:
            rgb_space_name (str): The name of the RGB space, e.g. "sRGB",
                "AdobeRGB".
            iccv4 (bool): Whether to create an ICC v4 profile.
            cat (str): Chromatic adaptation transform to use.
            profile_class (bytes): The profile class, e.g. b'mntr' for monitor
                profiles.

        Returns:
            ICCProfile: The created ICC profile.
        """
        rgb_space = colormath.get_rgb_space(rgb_space_name)
        return ICCProfile.from_rgb_space(
            rgb_space, rgb_space_name, iccv4, cat, profile_class
        )

    @staticmethod
    def from_rgb_space(
        rgb_space: tuple[
            tuple[float, float, float],
            tuple[float, float, float],
            tuple[float, float, float],
        ],
        description: str,
        iccv4: bool = False,
        cat: str = "Bradford",
        profile_class: bytes = b"mntr",
    ) -> ICCProfile:
        """Create an ICC Profile from RGB space and return it.

        Args:
            rgb_space (None | str | list | tuple): The RGB space to use for
                conversion. Defaults to sRGB if not set. If a string is given,
                it must be a valid RGB space name. If a list or tuple is given,
                it must be in the format (gamma, whitepoint, red, green, blue).
                The whitepoint can be a string (e.g. "D50"), a tuple of XYZ
                coordinates, or a color temperature in degrees K (float or
                int). The gamma should be a float. The RGB primaries red,
                green, blue should be lists or tuples of xyY coordinates (only
                x and y will be used, so Y can be zero or None).
            description (str): A description for the profile.
            iccv4 (bool): Whether to create an ICC v4 profile.
            cat (str): Chromatic adaptation transform to use.
            profile_class (bytes): The profile class, e.g. b'mntr' for monitor
                profiles.

        Returns:
            ICCProfile: The created ICC profile.
        """
        rx, ry = rgb_space[2:][0][:2]
        gx, gy = rgb_space[2:][1][:2]
        bx, by = rgb_space[2:][2][:2]
        wx, wy = colormath.XYZ2xyY(*rgb_space[1])[:2]
        return ICCProfile.from_chromaticities(
            rx,
            ry,
            gx,
            gy,
            bx,
            by,
            wx,
            wy,
            rgb_space[0],
            description,
            "No copyright",
            iccv4=iccv4,
            cat=cat,
            profile_class=profile_class,
        )

    @staticmethod
    def from_edid(
        edid: dict,
        iccv4: bool = False,
        cat: str = "Bradford",
    ) -> ICCProfile:
        """Create an ICC Profile from EDID data and return it.

        You may override the gamma from EDID by setting it to a list of curve
        values.

        Args:
            edid (dict): EDID data as a dictionary.
            iccv4 (bool, optional): Whether to create an ICC v4 profile.
            cat (str, optional): Chromatic adaptation transform to use.

        Returns:
            ICCProfile: The created ICC profile.
        """
        description = edid.get(
            "monitor_name", edid.get("ascii", str(edid["product_id"] or edid["hash"]))
        )
        manufacturer = edid.get("manufacturer", b"")
        manufacturer_id = edid["edid"][8:10]
        model_name = description
        model_id = edid["edid"][10:12]
        copyright_str = "Created from EDID"
        # Get chromaticities of primaries0
        xy = {}
        for color in ("red", "green", "blue", "white"):
            x, y = edid.get(color + "_x", 0.0), edid.get(color + "_y", 0.0)
            xy[color[0] + "x"] = x
            xy[color[0] + "y"] = y
        gamma = edid.get("gamma", 2.2)
        profile = ICCProfile.from_chromaticities(
            xy["rx"],
            xy["ry"],
            xy["gx"],
            xy["gy"],
            xy["bx"],
            xy["by"],
            xy["wx"],
            xy["wy"],
            gamma,
            description,
            copyright_str,
            manufacturer,
            model_name,
            manufacturer_id,
            model_id,
            iccv4,
            cat,
        )
        profile.set_edid_metadata(edid)
        spec_prefixes = "DATA_,OPENICC_"
        prefix = profile.tags.meta.getvalue("prefix", b"", None)
        if isinstance(prefix, bytes):
            prefix = prefix.decode("utf-8")
        prefixes = (prefix or spec_prefixes).split(",")
        for prefix in spec_prefixes.split(","):
            if prefix not in prefixes:
                prefixes.append(prefix)
        profile.tags.meta["prefix"] = ",".join(prefixes)
        profile.tags.meta["OPENICC_automatic_generated"] = "1"
        profile.tags.meta["DATA_source"] = "edid"
        profile.calculate_id()
        return profile

    @staticmethod
    def from_chromaticities(
        rx: float,
        ry: float,
        gx: float,
        gy: float,
        bx: float,
        by: float,
        wx: float,
        wy: float,
        gamma: float | list,
        description: str,
        copyright_: str,
        manufacturer: None | str = None,
        model_name: None | str = None,
        manufacturer_id: bytes = b"\0\0",
        model_id: bytes = b"\0\0",
        iccv4: bool = False,
        cat: str = "Bradford",
        profile_class: bytes = b"mntr",
    ) -> ICCProfile:
        r"""Create an ICC Profile from chromaticities and return it.

        Args:
            rx (float): Red primary x chromaticity.
            ry (float): Red primary y chromaticity.
            gx (float): Green primary x chromaticity.
            gy (float): Green primary y chromaticity.
            bx (float): Blue primary x chromaticity.
            by (float): Blue primary y chromaticity.
            wx (float): White point x chromaticity.
            wy (float): White point y chromaticity.
            gamma (float | list): Gamma value or list of curve values.
            description (str): A description for the profile.
            copyright_ (str): Copyright information for the profile.
            manufacturer (None | str, optional): Manufacturer name. Defaults to
                None.
            model_name (None | str, optional): Model name. Defaults to None.
            manufacturer_id (bytes, optional): Manufacturer ID as a 4-byte
                string. Defaults to b"\0\0".
            model_id (bytes, optional): Model ID as a 4-byte string. Defaults
                to b"\0\0".
            iccv4 (bool, optional): Whether to create an ICC v4 profile.
                Defaults to False.
            cat (str, optional): Chromatic adaptation transform to use.
                Defaults to "Bradford".
            profile_class (bytes, optional): The profile class, e.g. b'mntr'
                for monitor profiles. Defaults to b'mntr'.

        Returns:
            ICCProfile: The created ICC profile.
        """
        wXYZ = colormath.xyY2XYZ(wx, wy, 1.0)  # noqa: N806
        # Calculate RGB to XYZ matrix from chromaticities and white
        mtx = colormath.rgb_to_xyz_matrix(rx, ry, gx, gy, bx, by, wXYZ)
        rgb = {"r": (1.0, 0.0, 0.0), "g": (0.0, 1.0, 0.0), "b": (0.0, 0.0, 1.0)}
        XYZ = {}  # noqa: N806
        for color in "rgb":
            # Calculate XYZ for primaries
            XYZ[color] = mtx * rgb[color]

        return ICCProfile.from_XYZ(
            XYZ["r"],
            XYZ["g"],
            XYZ["b"],
            wXYZ,
            gamma,
            description,
            copyright_,
            manufacturer,
            model_name,
            manufacturer_id,
            model_id,
            iccv4,
            cat,
            profile_class,
        )

    @staticmethod
    def from_XYZ(  # noqa: N802
        rXYZ: tuple[float, float, float],  # noqa: N803
        gXYZ: tuple[float, float, float],  # noqa: N803
        bXYZ: tuple[float, float, float],  # noqa: N803
        wXYZ: tuple[float, float, float],  # noqa: N803
        gamma: float | list,
        description: str,
        copyright_: str,
        manufacturer: None | str = None,
        model_name: None | str = None,
        manufacturer_id: bytes = b"\0\0",
        model_id: bytes = b"\0\0",
        iccv4: bool = False,
        cat: str = "Bradford",
        profile_class: bytes = b"mntr",
    ) -> ICCProfile:
        r"""Create an ICC Profile from XYZ values and return it.

        Args:
            rXYZ (tuple[float, float, float]): Red primary in absolute XYZ.
            gXYZ (tuple[float, float, float]): Green primary in absolute XYZ.
            bXYZ (tuple[float, float, float]): Blue primary in absolute XYZ.
            wXYZ (tuple[float, float, float]): White point in absolute XYZ.
            gamma (float | list): Gamma value or list of curve values.
            description (str): A description for the profile.
            copyright_ (str): Copyright information for the profile.
            manufacturer (None | str, optional): Manufacturer name. Defaults to
                None.
            model_name (None | str, optional): Model name. Defaults to None.
            manufacturer_id (bytes, optional): Manufacturer ID as a 4-byte
                string. Defaults to b"\0\0".
            model_id (bytes, optional): Model ID as a 4-byte string. Defaults
                to b"\0\0".
            iccv4 (bool, optional): Whether to create an ICC v4 profile.
                Defaults to False.
            cat (str, optional): Chromatic adaptation transform to use.
                Defaults to "Bradford".
            profile_class (bytes, optional): The profile class, e.g. b'mntr'
                for monitor profiles. Defaults to b'mntr'.

        Returns:
            ICCProfile: The created ICC profile.
        """
        profile = ICCProfile()
        profile.profileClass = profile_class
        D50 = colormath.get_whitepoint("D50")  # noqa: N806
        if iccv4:
            profile.version = 4.3
        elif not s15f16_is_equal(wXYZ, D50) and (
            profile.profileClass not in (b"mntr", b"prtr")
            or colormath.is_similar_matrix(
                colormath.get_cat_matrix(cat), colormath.get_cat_matrix("Bradford")
            )
        ):
            profile.version = 2.2  # Match ArgyllCMS
        profile.setDescription(description)
        profile.setCopyright(copyright_)
        if manufacturer:
            profile.setDeviceManufacturerDescription(manufacturer)
        if model_name:
            profile.setDeviceModelDescription(model_name)

        profile.device["manufacturer"] = (
            b"\0\0" + manufacturer_id[1:] + manufacturer_id[:1]
        )
        profile.device["model"] = b"\0\0" + model_id[1:] + model_id[:1]
        # Add Apple-specific 'mmod' tag (TODO: need full spec)
        if manufacturer_id != b"\0\0" or model_id != b"\0\0":
            mmod = (
                b"mmod"
                + (b"\x00" * 6)
                + manufacturer_id
                + (b"\x00" * 2)
                + model_id[1:]
                + model_id[:1]
                + (b"\x00" * 4)
                + (b"\x00" * 20)
            )
            profile.tags.mmod = ICCProfileTag(mmod, "mmod")
        profile.set_wtpt(wXYZ, cat)
        profile.tags.chrm = ChromaticityType()
        profile.tags.chrm.type = 0

        for color_value, color_name in ((rXYZ, "r"), (gXYZ, "g"), (bXYZ, "b")):
            X, Y, Z = color_value  # noqa: N806
            # Get chromaticity of primary
            x, y = colormath.XYZ2xyY(X, Y, Z)[:2]
            profile.tags.chrm.channels.append((x, y))
            # Write XYZ and TRC tags (don't forget to adapt to D50)
            tagname = f"{color_name}XYZ"
            profile.tags[tagname] = XYZType(profile=profile)
            (
                profile.tags[tagname].X,
                profile.tags[tagname].Y,
                profile.tags[tagname].Z,
            ) = colormath.adapt(X, Y, Z, wXYZ, D50, cat)
            tagname = f"{color_name}TRC"
            profile.tags[tagname] = CurveType(profile=profile)
            if isinstance(gamma, (list, tuple)):
                profile.tags[tagname].extend(gamma)
            else:
                profile.tags[tagname].set_trc(gamma, 1)
        profile.calculate_id()
        return profile

    def set_wtpt(self, wXYZ: tuple[float, float, float], cat: str = "Bradford") -> None:  # noqa: N803
        """Set whitepoint, 'chad' tag and add ArgyllCMS 'arts' tag.

        if >= v2.4 profile or CAT is not Bradford and wtpt is not D50.

        Args:
            wXYZ (tuple[float, float, float]): White point in absolute XYZ, Y
                range 0.0..1.0.
            cat (str, optional): Chromatic adaptation transform to use.
                Defaults to 'Bradford'.
        """
        self.tags.wtpt = XYZType(profile=self)
        # Compatibility: ArgyllCMS will only read 'chad' if display or
        # output profile
        if self.profileClass in (b"mntr", b"prtr") and (
            self.version >= 2.4
            or not colormath.is_similar_matrix(
                colormath.get_cat_matrix(cat), colormath.get_cat_matrix("Bradford")
            )
        ):
            # Set wtpt to D50 and store actual white -> D50 transform in chad
            # if creating ICCv4 profile or CAT is not default Bradford
            D50 = colormath.get_whitepoint("D50")  # noqa: N806
            (self.tags.wtpt.X, self.tags.wtpt.Y, self.tags.wtpt.Z) = D50
            if not s15f16_is_equal(wXYZ, D50):
                # Only create chad if actual white is not D50
                self.tags.chad = ChromaticAdaptionTag()
                matrix = colormath.wp_adaption_matrix(wXYZ, D50, cat)
                self.tags.chad.update(matrix)
        else:
            # Store actual white in wtpt
            (self.tags.wtpt.X, self.tags.wtpt.Y, self.tags.wtpt.Z) = wXYZ
        self.tags.arts = ChromaticAdaptionTag()
        self.tags.arts.update(colormath.get_cat_matrix(cat))

    def has_trc_tags(self) -> bool:
        """Return whether the profile has [rgb]TRC tags.

        Returns:
            bool: True if the profile has [rgb]TRC tags, False otherwise.
        """
        return False not in [channel + "TRC" in self.tags for channel in "rgb"]

    def set_blackpoint(self, XYZbp: tuple[float, float, float]) -> None:  # noqa: N803
        """Set the black point tag to the given XYZ value.

        Args:
            XYZbp (tuple[float, float, float]): Black point in absolute XYZ, Y
                range 0.0..1.0.
        """
        if "chad" not in self.tags:
            cat = self.guess_cat() or "Bradford"
            XYZbp = colormath.adapt(  # noqa: N806
                *XYZbp, whitepoint_destination=list(self.tags.wtpt.ir.values()), cat=cat
            )
        self.tags.bkpt = XYZType(tagSignature="bkpt", profile=self)
        self.tags.bkpt.X, self.tags.bkpt.Y, self.tags.bkpt.Z = XYZbp

    def apply_black_offset(
        self,
        XYZbp: tuple[float, float, float],  # noqa: N803
        power: float = 40.0,
        include_A2B: bool = True,  # noqa: N803
        set_blackpoint: bool = True,
        logfile: None | TextIO = None,
        thread_abort: None | threading.Event = None,
        abortmessage: str = "Aborted",
        include_trc: bool = True,
    ) -> None:
        """Apply black point blending to the profile.

        Args:
            XYZbp (tuple[float, float, float]): Black point in absolute XYZ, Y
                range 0.0..1.0.
            power (float, optional): Power of black point blending. Defaults to
                40.0.
            include_A2B (bool, optional): Whether to apply black point blending
                to A2B tables. Defaults to True.
            set_blackpoint (bool, optional): Whether to set the black point
                tag. Defaults to True.
            logfile (None | TextIO, optional): File-like object to write the
                log messages to. Defaults to None.
            thread_abort (None | threading.Event, optional): Event to signal
                thread abort. Defaults to None.
            abortmessage (str, optional): Message to display when thread is
                aborted. Defaults to "Aborted".
            include_trc (bool, optional): Whether to apply black point blending
                to TRC tags. Defaults to True.
        """
        # Apply only the black point blending portion of BT.1886 mapping
        if include_A2B:
            tables = []
            for i in range(3):
                a2b = self.tags.get(f"A2B{i}")
                if isinstance(a2b, LUT16Type) and a2b not in tables:
                    a2b.apply_black_offset(XYZbp, logfile, thread_abort, abortmessage)
                    tables.append(a2b)
        if set_blackpoint:
            self.set_blackpoint(XYZbp)
        if not self.tags.get("rTRC") or not include_trc:
            return
        rXYZ = list(self.tags.rXYZ.values())  # noqa: N806
        gXYZ = list(self.tags.gXYZ.values())  # noqa: N806
        bXYZ = list(self.tags.bXYZ.values())  # noqa: N806
        mtx = colormath.Matrix3x3(
            [
                [rXYZ[0], gXYZ[0], bXYZ[0]],
                [rXYZ[1], gXYZ[1], bXYZ[1]],
                [rXYZ[2], gXYZ[2], bXYZ[2]],
            ]
        )
        imtx = mtx.inverted()
        for channel in "rgb":
            tag = CurveType(profile=self)
            if len(self.tags[f"{channel}TRC"]) == 1:
                gamma = self.tags[f"{channel}TRC"].get_gamma()
                tag.set_trc(gamma, 1024)
            else:
                tag.extend(self.tags[channel + "TRC"])
            self.tags[channel + "TRC"] = tag
        rgbbp_in = [self.tags[f"{channel}TRC"][0] / 65535.0 for channel in "rgb"]
        bp_in = mtx * rgbbp_in
        if tuple(bp_in) == tuple(XYZbp):
            return
        size = len(self.tags.rTRC)
        for i in range(size):
            rgb = [self.tags[f"{channel}TRC"][i] / 65535.0 for channel in "rgb"]
            X, Y, Z = mtx * rgb  # noqa: N806
            XYZ = colormath.blend_blackpoint(X, Y, Z, bp_in, XYZbp, power=power)  # noqa: N806
            rgb = imtx * XYZ
            for j, channel in enumerate("rgb"):
                self.tags[f"{channel}TRC"][i] = min(max(rgb[j], 0), 1) * 65535

    def set_bt1886_trc(
        self,
        XYZbp: tuple[float, float, float],  # noqa: N803
        outoffset: float = 0.0,
        gamma: float = 2.4,
        gamma_type: str = "B",
        size: None | int = None,
    ) -> None:
        """Set the response to the BT.1886 function.

        Args:
            XYZbp (tuple): Black point in absolute XYZ, Y range 0.0..1.0.
            outoffset (float): Output offset (default 0.0).
            gamma (float): Effective gamma (default 2.4).
            gamma_type (str, optional): Type of gamma to use, either 'b' for
                BT.1886 or 'g' for gamma (default 'B').
            size (None | int): Number of steps. Recommended >= 1024.
        """
        if gamma_type in ("b", "g"):
            # Get technical gamma needed to achieve effective gamma
            gamma = colormath.xicc_tech_gamma(gamma, XYZbp[1], outoffset)
        rXYZ = list(self.tags.rXYZ.values())  # noqa: N806
        gXYZ = list(self.tags.gXYZ.values())  # noqa: N806
        bXYZ = list(self.tags.bXYZ.values())  # noqa: N806
        mtx = colormath.Matrix3x3(
            [
                [rXYZ[0], gXYZ[0], bXYZ[0]],
                [rXYZ[1], gXYZ[1], bXYZ[1]],
                [rXYZ[2], gXYZ[2], bXYZ[2]],
            ]
        )
        bt1886 = colormath.BT1886(mtx, XYZbp, outoffset, gamma)
        values = {}
        for _i, channel in enumerate(("r", "g", "b")):
            self.tags[channel + "TRC"] = CurveType(profile=self)
            self.tags[channel + "TRC"].set_trc(-709, size)
            for j, v in enumerate(self.tags[channel + "TRC"]):
                if not values.get(j):
                    values[j] = []
                values[j].append(v / 65535.0)
        for i in values:
            r, g, b = values[i]
            X, Y, Z = mtx * (r, g, b)  # noqa: N806
            values[i] = bt1886.apply(X, Y, Z)
        for i in values:
            XYZ = values[i]  # noqa: N806
            rgb = mtx.inverted() * XYZ
            for j, channel in enumerate(("r", "g", "b")):
                self.tags[channel + "TRC"][i] = max(min(rgb[j] * 65535, 65535), 0)
        self.set_blackpoint(XYZbp)

    def set_dicom_trc(
        self,
        XYZbp: tuple[float, float, float],  # noqa: N803
        white_cdm2: float = 100,
        size: int = 1024,
    ) -> None:
        """Set the response to the DICOM Grayscale Standard Display Function.

        This response is special in that it depends on the actual black
        and white level of the display.

        XYZbp (tuple[float, float, float]: Black point in absolute XYZ, Y range
            0.05..white_cdm2.
        white_cdm2 (float, optional): White level in candelas per square
            meter, defaults to 100.
        size (int, optional): Number of steps. Recommended >= 1024.
        """
        self.set_trc_tags()
        for channel in "rgb":
            self.tags[f"{channel}TRC"].set_dicom_trc(XYZbp[1], white_cdm2, size)
        self.apply_black_offset(
            [v / white_cdm2 for v in XYZbp], 40.0 * (white_cdm2 / 40.0)
        )

    def set_hlg_trc(
        self,
        XYZbp: tuple[float, float, float] = (0, 0, 0),  # noqa: N803
        white_cdm2: float = 100,
        system_gamma: float = 1.2,
        ambient_cdm2: float = 5,
        maxsignal: float = 1.0,
        size: int = 1024,
        blend_blackpoint: bool = True,
    ) -> None:
        """Set the response to the Hybrid Log-Gamma (HLG) function.

        This response is special in that it depends on the actual black and
        white level of the display, system gamma and ambient.

        XYZbp (tuple[float, float, float], optional): Black point in absolute
            XYZ, Y range 0..white_cdm2.
        white_cdm2 (float, optional): White level in candelas per square
            meter, defaults to 100.
        system_gamma (float, optional): System gamma, defaults to 1.2.
        ambient_cdm2 (float, optional): Ambient light level in candelas per
            square meter, defaults to 5.
        maxsignal (float, optional): Set clipping point. Defaults to 1.0.
        size (int, optional): Number of steps. Recommended >= 1024.
        blend_blackpoint (bool, optional): If True, applies black point
            blending. Defaults to True.
        """
        self.set_trc_tags()
        for channel in "rgb":
            self.tags[f"{channel}TRC"].set_hlg_trc(
                XYZbp[1], white_cdm2, system_gamma, ambient_cdm2, maxsignal, size
            )
        if tuple(XYZbp) != (0, 0, 0) and blend_blackpoint:
            self.apply_black_offset(
                [v / white_cdm2 for v in XYZbp], 40.0 * (white_cdm2 / 100.0)
            )

    def set_smpte2084_trc(
        self,
        XYZbp: tuple[float, float, float] = (0, 0, 0),  # noqa: N803
        white_cdm2: float = 100,
        master_black_cdm2: float = 0,
        master_white_cdm2: float = 10000,
        use_alternate_master_white_clip: bool = True,
        rolloff: bool = False,
        size: int = 1024,
        blend_blackpoint: bool = True,
    ) -> None:
        """Set the response to the SMPTE 2084 perceptual quantizer (PQ) function.

        This response is special in that it depends on the actual black
        and white level of the display.

        Args:
            XYZbp (tuple[float, float, float]): Black point in absolute XYZ, Y
                range 0..white_cdm2
            white_cdm2 (float, optional): White level in candelas per square
                meter, defaults to 100.
            master_black_cdm2 (float, optional): Used to normalize PQ values.
                Defaults to 0.
            master_white_cdm2 (float, optional): Used to normalize PQ values.
                Defaults to 10000.
            use_alternate_master_white_clip (bool, optional): If True, uses the
                alternate master white clip. Defaults to True.
            rolloff (bool, optional): If True, applies the rolloff BT.2390.
                Defaults to False.
            size (int, optional): Number of steps. Recommended >= 1024.
            blend_blackpoint (bool, optional): If True, applies black point
                blending. Defaults to True.
        """
        self.set_trc_tags()
        for channel in "rgb":
            self.tags[f"{channel}TRC"].set_smpte2084_trc(
                XYZbp[1],
                white_cdm2,
                master_black_cdm2,
                master_white_cdm2,
                use_alternate_master_white_clip,
                rolloff,
                size,
            )
        if tuple(XYZbp) != (0, 0, 0) and blend_blackpoint:
            self.apply_black_offset(
                [v / white_cdm2 for v in XYZbp], 40.0 * (white_cdm2 / 100.0)
            )

    def set_trc_tags(
        self, identical: bool = False, power: None | float | Callable = None
    ) -> None:
        """Set the [rgb]TRC tags.

        Args:
            identical (bool, optional): If True, all channels will have the
                same TRC tag. Defaults to False.
            power (None | float | Callable, optional): If provided, sets the
                TRC to a power curve. Defaults to None, which means no power
                curve is set.
        """
        for channel in "rgb":
            if identical and channel != "r":
                tag = self.tags.rTRC
            else:
                tag = CurveType(profile=self)
                if power:
                    tag.set_trc(
                        power, size=1 if not callable(power) and power >= 0 else 1024
                    )
            self.tags[f"{channel}TRC"] = tag

    def set_localizable_desc(
        self,
        tagname: str,
        description: str,
        languagecode: str = "en",
        countrycode: str = "US",
    ) -> None:
        """Set a localizable description tag.

        Args:
            tagname (str): The tag name to set.
            description (str): The description to set for the tag.
            languagecode (str, optional): The language code for the
                description. Defaults to "en".
            countrycode (str, optional): The country code for the description.
                Defaults to "US".
        """
        # Handle ICCv2 <> v4 differences and encoding
        if self.version < 4:
            self.tags[tagname] = TextDescriptionType()
            if isinstance(description, str):
                asciidesc = description.encode("ASCII", "asciize")
            else:
                asciidesc = description
            self.tags[tagname].ASCII = asciidesc
            if asciidesc != description:
                self.tags[tagname].Unicode = description
        else:
            self.set_localizable_text(tagname, description, languagecode, countrycode)

    def set_localizable_text(
        self, tagname: str, text: str, languagecode: str = "en", countrycode: str = "US"
    ) -> None:
        """Set a localizable text tag.

        Args:
            tagname (str): The tag name to set.
            text (str): The text to set for the tag.
            languagecode (str, otional): The language code for the text.
                Defaults to "en".
            countrycode (str, optioanl): The country code for the text.
                Defaults to "US".
        """
        # Handle ICCv2 <> v4 differences and encoding
        if self.version < 4:
            if isinstance(text, str):
                text = text.encode("ASCII", "asciize")
            self.tags[tagname] = TextType(b"text\0\0\0\0%s\0" % text, tagname)
        else:
            self.tags[tagname] = MultiLocalizedUnicodeType()
            self.tags[tagname].add_localized_string(languagecode, countrycode, text)

    def setCopyright(  # noqa: N802
        self, copyright_: str, languagecode: str = "en", countrycode: str = "US"
    ) -> None:
        """Set profile copyright.

        Args:
            copyright_ (str): The profile copyright.
            languagecode (str, optional): The language code for the copyright.
                Defaults to "en".
            countrycode (str, optional): The country code for the copyright.
                Defaults to "US".
        """
        self.set_localizable_text("cprt", copyright_, languagecode, countrycode)

    def setDescription(  # noqa: N802
        self, description: str, languagecode: str = "en", countrycode: str = "US"
    ) -> None:
        """Set profile description.

        Args:
            description (str): The profile description.
            languagecode (str): The language code for the description. Defaults
                to "en".
            countrycode (str): The country code for the description. Defaults
                to "US".
        """
        self.set_localizable_desc("desc", description, languagecode, countrycode)

    def setDeviceManufacturerDescription(  # noqa: N802
        self, description: str, languagecode: str = "en", countrycode: str = "US"
    ) -> None:
        """Set device manufacturer description.

        Args:
            description (str): The device manufacturer description.
            languagecode (str, optional): The language code for the
                description. Defaults to "en".
            countrycode (str, optional): The country code for the description.
                Defafults to "US".
        """
        self.set_localizable_desc("dmnd", description, languagecode, countrycode)

    def setDeviceModelDescription(  # noqa: N802
        self, description: str, languagecode: str = "en", countrycode: str = "US"
    ) -> None:
        """Set device model description.

        Args:
            description (str): The device model description.
            languagecode (str, optional): The language code for the
                description. Defaults to "en".
            countrycode (str, optional): The country code for the description.
                Defaults to "US".
        """
        self.set_localizable_desc("dmdd", description, languagecode, countrycode)

    def getCopyright(self) -> str:  # noqa: N802
        """Return profile copyright.

        Returns:
            str: The profile copyright.
        """
        return str(self.tags.get("cprt", ""))

    def getDescription(self) -> str:  # noqa: N802
        """Return profile description.

        Returns:
            str: The profile description.
        """
        return str(self.tags.get("desc", ""))

    def getDeviceManufacturerDescription(self) -> str:  # noqa: N802
        """Return device manufacturer description.

        Returns:
            str: The device manufacturer description.
        """
        return str(self.tags.get("dmnd", ""))

    def getDeviceModelDescription(self) -> str:  # noqa: N802
        """Return device model description.

        Returns:
            str: The device model description.
        """
        return str(self.tags.get("dmdd", ""))

    def getViewingConditionsDescription(self) -> str:  # noqa: N802
        """Return viewing conditions description.

        Returns:
            str: The viewing conditions description.
        """
        return str(self.tags.get("vued", ""))

    def guess_cat(self, matrix: bool = True) -> None | str | colormath.Matrix3x3:
        """Get or guess chromatic adaptation transform.

        Args:
            matrix (bool): If 'matrix' is True, and 'arts' tag is present,
                return actual matrix instead of name if no match to known
                matrices.

        Returns:
            None | str | colormath.Matrix3x3: The guessed chromatic adaptation
                transform, either as a string name or a Matrix3x3 object.
                Returns None if no CAT can be guessed.
        """
        illuminant = list(self.illuminant.values())
        if isinstance(self.tags.get("chad"), ChromaticAdaptionTag):
            return colormath.guess_cat(
                self.tags.chad, self.tags.chad.inverted() * illuminant, illuminant
            )
        if isinstance(self.tags.get("arts"), ChromaticAdaptionTag):
            return self.tags.arts.get_cat() or (matrix and self.tags.arts)
        return None

    def is_same(
        self,
        profile: bytes | str | pathlib.Path | BinaryIO | TextIO,
        force_calculation: bool = False,
    ) -> bool:
        """Compare the ID of profiles.

        Returns a boolean indicating if the profiles have the same ID.

        profile can be a ICCProfile instance, a binary string
        containing profile data, a filename or a file object.

        Args:
            profile (str | bytes | path.Path | BinaryIO | TextIO | ICCProfile ):
                The profile to compare with.
            force_calculation (bool, optional): If True, forces recalculation
                of the ID. Defautls to False.

        Returns:
            bool: True if the profiles have the same ID, False otherwise.
        """
        if not isinstance(profile, self.__class__):
            profile = self.__class__(profile)
        if force_calculation or self.ID == b"\0" * 16:
            id1 = self.calculate_id(False)
        else:
            id1 = self.ID
        if force_calculation or profile.ID == b"\0" * 16:
            id2 = profile.calculate_id(False)
        else:
            id2 = profile.ID
        return id1 == id2

    def load(self) -> None:
        """Load the profile from the file object.

        Normally, you don't need to call this method, since the ICCProfile
        class automatically loads the profile when necessary (load does
        nothing if the profile was passed in as a binary string).
        """
        if self.is_loaded or not self._file:
            return
        if self._file.closed:
            self._file = open(self._file.name, "rb")  # noqa: SIM115
            self._file.seek(len(self._data))
        read_size = self.size - len(self._data)
        if read_size > 0:
            self._data += self._file.read(read_size)
        self._file.close()
        self.is_loaded = True

    def print_info(self) -> None:
        """Print profile information to stdout."""
        print("=" * 80)
        print("ICC profile information")
        print("-" * 80)
        print("File name:", os.path.basename(self.filename or ""))
        for label, value in self.get_info():
            if not value:
                print(label)
            else:
                print(label + ":", value)

    @staticmethod
    def add_device_info(info: DictList, device: dict, level: int = 1) -> None:
        """Add a device structure (see profile header) to info dict.

        Args:
            info (DictList): The dictionary to add the device information to.
            device (dict): The device structure from the profile header.
            level (int, optional): Indentation level for the device info.
                Defaults to 1.
        """
        indent = " " * 4 * level
        info[f"{indent}Manufacturer"] = "0x{}".format(
            binascii.hexlify(device.get("manufacturer", b"")).upper().decode()
        )
        if (
            len(device.get("manufacturer", b"")) == 4
            and device["manufacturer"][0:2] == b"\0\0"
            and device["manufacturer"][2:4] != b"\0\0"
        ):
            mnft_id = device["manufacturer"][3:4] + device["manufacturer"][2:3]
            mnft_id = edid.parse_manufacturer_id(mnft_id)
            manufacturer = edid.get_manufacturer_name(mnft_id)  # this is str
        else:
            manufacturer = (
                re.sub(b"[^\x20-\x7e]", b"", device.get("manufacturer", b""))
            ).decode()
            if manufacturer != device.get("manufacturer"):
                manufacturer = None
            else:
                manufacturer = f"'{manufacturer.decode()}'"
        if manufacturer is not None:
            info[f"{indent}Manufacturer"] += f" {manufacturer}"
        info[f"{indent}Model"] = hexrepr(device.get("model", ""))
        attributes = device.get("attributes", {})
        info[f"{indent}Media attributes"] = ", ".join(
            [
                {True: "Reflective"}.get(attributes.get("reflective"), "Transparency"),
                {True: "Glossy"}.get(attributes.get("glossy"), "Matte"),
                {True: "Positive"}.get(attributes.get("positive"), "Negative"),
                {True: "Color"}.get(attributes.get("color"), "Black & white"),
            ]
        )

    def get_info(self) -> list:
        """Return a list of profile information as tuples.

        The tuples are of the form (label, value), where label is a string
        describing the information and value is the corresponding value.
        If the value is None or empty, the label is returned without a value.
        This method is useful for displaying profile information in a
        user-friendly way.

        Returns:
            list: A list of tuples containing profile information.
        """
        info = DictList()
        info["Size"] = f"{int(self.size):d} Bytes ({self.size / 1024.0:.2f} KiB)"
        info["Preferred CMM"] = hexrepr(self.preferredCMM, CMMS)
        info["ICC version"] = f"{self.version}"
        info["Profile class"] = PROFILE_CLASS.get(self.profileClass, self.profileClass)
        info["Color model"] = self.colorSpace.decode()
        info["Profile connection space (PCS)"] = self.connectionColorSpace.decode()
        info["Created"] = "{:%Y-%m-%d %H:%M:%S}".format(self.dateTime)  # noqa: UP032
        info["Platform"] = PLATFORM.get(self.platform, hexrepr(self.platform))
        info["Is embedded"] = {True: "Yes"}.get(self.embedded, "No")
        info["Can be used independently"] = {True: "Yes"}.get(self.independent, "No")
        info["Device"] = ""
        ICCProfile.add_device_info(info, self.device)
        info["Default rendering intent"] = {
            0: "Perceptual",
            1: "Media-relative colorimetric",
            2: "Saturation",
            3: "ICC-absolute colorimetric",
        }.get(self.intent, "Unknown")
        info["PCS illuminant XYZ"] = " ".join(
            [
                " ".join([f"{v * 100:6.2f}" for v in list(self.illuminant.values())]),
                "(xy {},".format(
                    " ".join(f"{v:6.4f}" for v in self.illuminant.xyY[:2])
                ),
                "CCT {:d}K)".format(  # noqa: UP032
                    int(colormath.XYZ2CCT(*list(self.illuminant.values()))) or 0
                ),
            ]
        )
        info["Creator"] = hexrepr(self.creator, MANUFACTURERS)
        info["Checksum"] = f"0x{binascii.hexlify(self.ID).upper().decode()}"
        calculated_id = self.calculate_id(False)
        if self.ID != b"\0" * 16:
            info["    Checksum OK"] = {True: "Yes"}.get(calculated_id == self.ID, "No")
        if calculated_id != self.ID:
            info["    Calculated checksum"] = (
                f"0x{binascii.hexlify(calculated_id).upper().decode()}"
            )
        for sig in self.tags:
            tag = self.tags[sig]
            name = TAGS.get(sig, f"'{sig}'")
            if isinstance(tag, ChromaticAdaptionTag):
                info[name] = self.guess_cat(False) or "Unknown"
                name = "    Matrix"
                for i, row in enumerate(tag):
                    if i > 0:
                        name = "    " * 2
                    info[name] = " ".join(f"{v:6.4f}" for v in row)
            elif isinstance(tag, ChromaticityType):
                info["Chromaticity (illuminant-relative)"] = ""
                for i, channel in enumerate(tag.channels):
                    if self.colorSpace.endswith(b"CLR"):
                        colorant_name = ""
                    else:
                        colorant_name = "({}) ".format(
                            self.colorSpace[i : i + 1].decode("utf-8")
                        )
                    info[f"    Channel {i + 1:d} {colorant_name}xy"] = " ".join(
                        f"{v:6.4f}" for v in channel
                    )
            elif isinstance(tag, ColorantTableType):
                info["Colorants (PCS-relative)"] = ""
                for colorant_name in tag:
                    colorant = tag[colorant_name]
                    values = list(colorant.values())
                    if "".join(list(colorant.keys())) == "Lab":
                        values = colormath.Lab2XYZ(*values)
                    else:
                        values = [v / 100.0 for v in values]
                    XYZxy = [" ".join(f"{v:6.2f}" for v in list(colorant.values()))]  # noqa: N806
                    if values != [0, 0, 0]:
                        XYZxy.append(
                            "(xy {})".format(
                                " ".join(
                                    f"{v:6.4f}" for v in colormath.XYZ2xyY(*values)[:2]
                                )
                            )
                        )
                    colorant_name = colorant_name.decode()
                    info[
                        "    {} {}".format(
                            colorant_name, "".join(list(colorant.keys()))
                        )
                    ] = " ".join(XYZxy)
            elif isinstance(tag, ParametricCurveType):
                params = "".join(sorted(tag.params.keys()))
                tag_params = dict(list(tag.params.items()))
                for key in tag_params:
                    value = tag_params[key]
                    value = f"{value:3.2f}" if key == "g" else f"{value:.6f}"
                    value = value.rstrip("0").rstrip(".")
                    if key == "g" and "." not in value:
                        value += ".0"
                    tag_params[key] = value
                tag_params["E"] = sig[0].upper()
                if params == "g":
                    info[name] = f"Gamma {tag_params['g']}"
                else:
                    info[name] = ""
                if params == "abg":
                    info["    if ({E} >= - {b} / {a}):".format(**tag_params)] = (
                        "Y = pow({a} * {E} + {b}, {g})".format(**tag_params)
                    )
                    info["    if ({E} <  - {b} / {a}):".format(**tag_params)] = "Y = 0"
                elif params == "abcg":
                    info["    if ({E} >= - {b} / {a}):".format(**tag_params)] = (
                        "Y = pow({a} * {E} + {b}, {g}) + {c}".format(**tag_params)
                    )
                    info["    if ({E} <  - {b} / {a}):".format(**tag_params)] = (
                        f"Y = {tag_params['c']}"
                    )
                elif params == "abcdg":
                    info["    if ({E} >= {d}):".format(**tag_params)] = (
                        "Y = pow({a} * {E} + {b}, {g})".format(**tag_params)
                    )
                    info["    if ({E} <  {d}):".format(**tag_params)] = (
                        "Y = {c} * {E}".format(**tag_params)
                    )
                elif params == "abcdefg":
                    info["    if ({E} >= {d}):".format(**tag_params)] = (
                        "Y = pow({a} * {E} + {b}, {g}) + {e}".format(**tag_params)
                    )
                    info["    if ({E} <  {d}):".format(**tag_params)] = (
                        "Y = {c} * {E} + {f}".format(**tag_params)
                    )
                if params != "g":
                    tag = tag.get_trc()
                    # info["    Average gamma"] = f"{tag.get_gamma():3.2f}"
                    transfer_function = tag.get_transfer_function(
                        slice_=(0, 1.0), outoffset=1.0
                    )
                    if round(transfer_function[1], 2) == 1.0:
                        value = f"{transfer_function[0][0]}"
                    elif transfer_function[1] >= 0.95:
                        value = "≈ {} (Δ {:.2%})".format(  # noqa: UP032
                            transfer_function[0][0],
                            1 - transfer_function[1],
                        )
                    else:
                        value = "Unknown"
                    info["    Transfer function"] = value
            elif isinstance(tag, CurveType):
                if len(tag) == 1:
                    value = (f"{tag[0]:3.2f}").rstrip("0").rstrip(".")
                    if "." not in value:
                        value = f"{value}.0"
                    info[name] = f"Gamma {value}"
                elif len(tag):
                    info[name] = ""
                    info["    Number of entries"] = f"{len(tag):d}"
                    # info["    Average gamma"] = f"{tag.get_gamma():3.2f}"
                    transfer_function = tag.get_transfer_function(
                        slice_=(0, 1.0), outoffset=1.0
                    )
                    if round(transfer_function[1], 2) == 1.0:
                        value = f"{transfer_function[0][0]}"
                    elif transfer_function[1] >= 0.95:
                        value = "≈ {} (Δ {:.2%})".format(  # noqa: UP032
                            transfer_function[0][0],
                            1 - transfer_function[1],
                        )
                    else:
                        value = "Unknown"
                    info["    Transfer function"] = value
                    info["    Minimum Y"] = f"{tag[0] / 65535.0 * 100:6.4f}"
                    info["    Maximum Y"] = f"{tag[-1] / 65535.0 * 100:6.2f}"
            elif isinstance(tag, DictType):
                name = "Metadata" if sig == "meta" else "Generic name-value data"
                info[name] = ""
                for key in tag:
                    record = tag.get(key)
                    value = record.get("value")
                    if value and key == "prefix":
                        value = "\n".join(value.split(","))
                    info[f"    {key}"] = value
                    elements = {}
                    for subkey in ("display_name", "display_value"):
                        entry = record.get(subkey)
                        if isinstance(entry, MultiLocalizedUnicodeType):
                            for language in entry:
                                countries = entry[language]
                                for country in countries:
                                    value = countries[country]
                                    if country.strip("\0 "):
                                        country = f"/{country}"
                                    loc = f"{language}{country}"
                                    if loc not in elements:
                                        elements[loc] = {}
                                    elements[loc][subkey] = value
                    for loc in elements:
                        items = elements[loc]
                        if len(items) > 1:
                            value = "{} = {}".format(*items.values())
                        elif "display_name" in items:
                            value = "{}".format(items["display_name"])
                        else:
                            value = " = {}".format(items["display_value"])
                        info[f"        {loc}"] = value
            elif isinstance(tag, LUT16Type):
                info[name] = ""
                name = "    Matrix"
                for i, row in enumerate(tag.matrix):
                    if i > 0:
                        name = "    " * 2
                    info[name] = " ".join(f"{v:6.4f}" for v in row)
                info["    Input Table"] = ""
                info["        Channels"] = f"{int(tag.input_channels_count):d}"
                info["        Number of entries per channel"] = (
                    f"{int(tag.input_entries_count):d}"
                )
                info["    Color Look Up Table"] = ""
                info["        Grid Steps"] = f"{int(tag.clut_grid_steps):d}"
                info["        Entries"] = "{:d}".format(  # noqa: UP032
                    int(tag.clut_grid_steps**tag.input_channels_count)
                )
                info["    Output Table"] = ""
                info["        Channels"] = f"{int(tag.output_channels_count):d}"
                info["        Number of entries per channel"] = (
                    f"{int(tag.output_entries_count):d}"
                )
            elif isinstance(tag, MakeAndModelType):
                info[name] = ""
                manufacturer_code = tag.manufacturer
                manufacturer_name = edid.get_manufacturer_name(
                    edid.parse_manufacturer_id(manufacturer_code.ljust(2, b"\0")[:2])
                )
                info["    Manufacturer"] = "0x{} {}".format(
                    binascii.hexlify(manufacturer_code).decode("utf-8").upper(),
                    manufacturer_name or "",
                )
                info["    Model"] = "0x{}".format(
                    binascii.hexlify(tag.model).decode("utf-8").upper()
                )
            elif isinstance(tag, MeasurementType):
                info[name] = ""
                info["    Observer"] = tag.observer.description
                info["    Backing XYZ"] = " ".join(
                    f"{v:6.2f}" for v in list(tag.backing.values())
                )
                info["    Geometry"] = tag.geometry.description
                info["    Flare"] = f"{tag.flare:.2%}"
                info["    Illuminant"] = tag.illuminantType.description
            elif isinstance(tag, MultiLocalizedUnicodeType):
                info[name] = ""
                for language in tag:
                    countries = tag[language]
                    for country in countries:
                        value = countries[country]
                        country = "/" + country if country.strip("\0 ") else ""
                        info[f"    {language}{country}"] = value
            elif isinstance(tag, NamedColor2Type):
                info[name] = ""
                info["    Device color components"] = f"{int(tag.deviceCoordCount):d}"
                info["    Colors (PCS-relative)"] = (
                    f"{int(tag.colorCount):d} ({len(tag.tagData):d} Bytes) "
                )
                i = 1
                for k in tag:
                    v = tag[k]
                    pcsout = []
                    for _kk in v.pcs:
                        vv = v.pcs[_kk]
                        pcsout.append(f"{vv:03.2f}")
                    devout = [f"{vv:03.2f}" for vv in v.device]
                    formatstr = (
                        f"        {{:0{len(str(tag.colorCount)):d}}} {{}}{{}}{{}}"
                    )
                    key = formatstr.format(i, tag.prefix, k, tag.suffix)
                    info[key] = "{} {}".format(
                        "".join(list(v.pcs.keys())),
                        " ".join(pcsout),
                    )
                    if self.colorSpace != self.connectionColorSpace or " ".join(
                        pcsout
                    ) != " ".join(devout):
                        info[key] += " ({} {})".format(
                            self.colorSpace, " ".join(devout)
                        )
                    i += 1
            elif isinstance(tag, ProfileSequenceDescType):
                info[name] = ""
                for i, desc in enumerate(tag):
                    info[" " * 4 + f"{i + 1:d}"] = ""
                    ICCProfile.add_device_info(info, desc, 2)
                    for desc_type in ("dmnd", "dmdd"):
                        description = str(desc[desc_type])
                        if description:
                            info[" " * 8 + TAGS[desc_type]] = description
            elif isinstance(tag, Text):
                if sig == "cprt":
                    info[name] = str(tag)
                elif sig == "ciis":
                    info[name] = CIIS.get(tag, f"'{tag}'")
                elif sig == "tech":
                    print(f"tag: {tag}")
                    print(f"type(tag): {type(tag)}")
                    info[name] = TECH.get(tag, f"'{tag}'")
                elif tag.find(b"\n") > -1 or tag.find(b"\r") > -1:
                    info[name] = f"[{len(tag):d} Bytes]"
                else:
                    info[name] = tag[: 60 - len(name)] + (
                        b"...[%i more Bytes]" % (len(tag) - (60 - len(name)))
                        if len(tag) > 60 - len(name)
                        else b""
                    )
            elif isinstance(tag, TextDescriptionType):
                if not tag.get("Unicode") and not tag.get("Macintosh"):
                    info[f"{name} (ASCII)"] = tag.ASCII.decode("utf-8")
                else:
                    info[name] = ""
                    info["    ASCII"] = tag.ASCII.decode("utf-8")
                    if tag.get("Unicode"):
                        info["    Unicode"] = tag.Unicode
                    if tag.get("Macintosh"):
                        info["    Macintosh"] = tag.Macintosh
            elif isinstance(tag, VideoCardGammaFormulaType):
                info[name] = ""
                # linear = tag.is_linear()
                # info["    Is linear"] = {0: "No", 1: "Yes"}[linear]
                for key in ("red", "green", "blue"):
                    info[f"    {key.capitalize()} gamma"] = "{:.2f}".format(
                        tag[f"{key}Gamma"]
                    )
                    info[f"    {key.capitalize()} minimum"] = "{:.2f}".format(
                        tag[f"{key}Min"]
                    )
                    info[f"    {key.capitalize()} maximum"] = "{:.2f}".format(
                        tag[f"{key}Max"]
                    )
            elif isinstance(tag, VideoCardGammaTableType):
                info[name] = ""
                info["    Bitdepth"] = f"{int(tag.entrySize * 8):d}"
                info["    Channels"] = f"{int(tag.channels):d}"
                info["    Number of entries per channel"] = f"{int(tag.entryCount):d}"
                r_points, g_points, b_points, linear_points = tag.get_values()
                points = r_points, g_points, b_points
                # if r_points == g_points == b_points == linear_points:
                #     info["    Is linear".format(i)] = {
                #         True: "Yes"
                #     }.get(points[i] == linear_points, "No")
                # else:
                if True:
                    unique = tag.get_unique_values()
                    for i, channel in enumerate(tag.data):
                        scale = math.pow(2, tag.entrySize * 8) - 1
                        vmin = 0
                        vmax = scale
                        gamma = colormath.get_gamma(
                            [
                                (
                                    (len(channel) / 2 - 1)
                                    / (len(channel) - 1.0)
                                    * scale,
                                    channel[int(len(channel) / 2 - 1)],
                                )
                            ],
                            scale,
                            vmin,
                            vmax,
                            False,
                            False,
                        )
                        if gamma:
                            info[f"    Channel {i + 1} gamma at 50% input"] = (
                                f"{gamma[0]:.2f}"
                            )
                        vmin = channel[0]
                        vmax = channel[-1]
                        info[f"    Channel {i + 1} minimum"] = f"{vmin / scale:6.4%}"
                        info[f"    Channel {i + 1} maximum"] = f"{vmax / scale:6.2%}"
                        info[f"    Channel {i + 1} unique values"] = (
                            f"{len(unique[i])} @ 8 Bit"
                        )
                        info[f"    Channel {i + 1} is linear"] = (
                            "Yes" if points[i] == linear_points else "No"
                        )
            elif isinstance(tag, ViewingConditionsType):
                info[name] = ""
                info["    Illuminant"] = tag.illuminantType.description
                info["    Illuminant XYZ"] = "{} (xy {})".format(
                    " ".join(f"{v:6.2f}" for v in list(tag.illuminant.values())),
                    " ".join(f"{v:6.4f}" for v in tag.illuminant.xyY[:2]),
                )
                XYZxy = [" ".join(f"{v:6.2f}" for v in list(tag.surround.values()))]  # noqa: N806
                if list(tag.surround.values()) != [0, 0, 0]:
                    XYZxy.append(
                        "(xy {})".format(
                            " ".join(f"{v:6.4f}" for v in tag.surround.xyY[:2])
                        )
                    )
                info["    Surround XYZ"] = " ".join(XYZxy)
            elif isinstance(tag, XYZType):
                if sig == "lumi":
                    info[name] = f"{self.tags.lumi.Y:.2f} cd/m²"
                elif sig in ("bkpt", "wtpt"):
                    file_format = {"bkpt": "{:6.4f}", "wtpt": "{:6.2f}"}[sig]
                    info[name] = ""
                    if self.profileClass == b"mntr" and sig == "wtpt":
                        info["    Is illuminant"] = "Yes"
                    if self.profileClass != b"prtr":
                        label = "Illuminant-relative"
                    else:
                        label = "PCS-relative"
                    # if (self.connectionColorSpace == "Lab"
                    #    and self.profileClass == "prtr"):
                    if self.profileClass == b"prtr":
                        color = [" ".join([file_format.format(v) for v in tag.ir.Lab])]
                        info[f"    {label} Lab"] = " ".join(color)
                    else:
                        color = [
                            " ".join(
                                file_format.format(v * 100)
                                for v in list(tag.ir.values())
                            )
                        ]
                        if list(tag.ir.values()) != [0, 0, 0]:
                            xy = " ".join(f"{v:6.4f}" for v in tag.ir.xyY[:2])
                            color.append(f"(xy {xy})")
                            cct, delta = colormath.xy_CCT_delta(*tag.ir.xyY[:2])
                        else:
                            cct = None
                        info[f"    {label} XYZ"] = " ".join(color)
                        if cct:
                            info[f"    {label} CCT"] = f"{int(cct):d}K"
                            if delta:
                                info["        ΔE 2000 to daylight locus"] = (
                                    f"{delta['E']:.2f}"
                                )
                            kwargs = {"daylight": False}
                            cct, delta = colormath.xy_CCT_delta(
                                *tag.ir.xyY[:2], **kwargs
                            )
                            if delta:
                                info["        ΔE 2000 to blackbody locus"] = (
                                    f"{delta['E']:.2f}"
                                )
                    if "chad" in self.tags:
                        color = [
                            " ".join(
                                file_format.format(v * 100)
                                for v in list(tag.pcs.values())
                            )
                        ]
                        if list(tag.pcs.values()) != [0, 0, 0]:
                            xy = " ".join(f"{v:6.4f}" for v in tag.pcs.xyY[:2])
                            color.append(f"(xy {xy})")
                        info["    PCS-relative XYZ"] = " ".join(color)
                        cct, delta = colormath.xy_CCT_delta(*tag.pcs.xyY[:2])
                        if cct:
                            info["    PCS-relative CCT"] = f"{int(cct):d}K"
                        # if delta:
                        #     info[u"        ΔE 2000 to daylight locus"] = (
                        #         f"{delta['E']:.2f}"
                        #     )
                        # kwargs = {"daylight": False}
                        # cct, delta = colormath.xy_CCT_delta(
                        #     *tag.pcs.xyY[:2], **kwargs
                        # )
                        # if delta:
                        #     info[u"        ΔE 2000 to blackbody locus"] = (
                        #         f"{delta['E']:.2f}"
                        #     )
                else:
                    info[name] = ""
                    info["    Illuminant-relative XYZ"] = " ".join(
                        [
                            " ".join(f"{v * 100:6.2f}" for v in list(tag.ir.values())),
                            "(xy {})".format(
                                " ".join(f"{v:6.4f}" for v in tag.ir.xyY[:2])
                            ),
                        ]
                    )
                    info["    PCS-relative XYZ"] = " ".join(
                        [
                            " ".join(f"{v * 100:6.2f}" for v in list(tag.values())),
                            "(xy {})".format(
                                " ".join(f"{v:6.4f}" for v in tag.xyY[:2])
                            ),
                        ]
                    )
            elif isinstance(tag, ICCProfileTag):
                info[name] = (
                    f"'{tag.tagData[:4].decode()}' [{len(tag.tagData):d} Bytes]"
                )
        return info

    def get_rgb_space(
        self, relation: str = "ir", gamma: None | bool = None
    ) -> bool | list:
        """Get RGB space from profile tags.

        Args:
            relation (str, optional): 'ir' for illuminant-relative, 'pcs' for
                PCS-relative.
            gamma (None | bool, optional): If True, return gamma values,
                otherwise TRC values.

        Returns:
            bool | list: False if the required tags are not present or a list
                containing the gamma/TRC values, the illuminant XYZ values, and
                the RGB XYZ values in the specified relation.
        """
        tags = self.tags
        if "wtpt" not in tags:
            return False
        rgb_space = [gamma or [], list(getattr(tags.wtpt, relation).values())]
        for component in ("r", "g", "b"):
            if f"{component}XYZ" not in tags or (
                not gamma
                and (
                    f"{component}TRC" not in tags
                    or not isinstance(tags[f"{component}TRC"], CurveType)
                )
            ):
                return False
            rgb_space.append(getattr(tags[f"{component}XYZ"], relation).xyY)
            if not gamma:
                if len(tags[f"{component}TRC"]) > 1:
                    rgb_space[0].append([v / 65535.0 for v in tags[f"{component}TRC"]])
                else:
                    rgb_space[0].append(tags[f"{component}TRC"][0])
        return rgb_space

    def get_chardata_bkpt(self, illuminant_relative: bool = False) -> None | list:
        """Get blackpoint from embeded characterization data ('targ' tag).

        Args:
            illuminant_relative (bool): If True, return the blackpoint
                relative to the profile's illuminant, otherwise return it
                relative to D50.

        Returns:
            None | list: A list containing the blackpoint XYZ values, or None
                if the blackpoint could not be determined.
        """
        if not isinstance(self.tags.get("targ"), Text):
            return None

        from DisplayCAL.cgats import CGATS

        ti3 = CGATS(self.tags.targ)
        if 0 not in ti3:
            return None

        black = ti3[0].queryi({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0})
        # May be several samples for black. Average them.
        if not black:
            return None

        XYZbp = [0, 0, 0]  # noqa: N806
        for sample in black.values():
            for i, component in enumerate("XYZ"):
                if "XYZ_" + component in sample:
                    XYZbp[i] += sample["XYZ_" + component] / 100.0
        for i in range(3):
            XYZbp[i] /= len(black)
        if not illuminant_relative:
            # Adapt to D50
            white = ti3.get_white_cie()
            if white:
                XYZwp = [  # noqa: N806
                    v / 100.0
                    for v in (
                        white["XYZ_X"],
                        white["XYZ_Y"],
                        white["XYZ_Z"],
                    )
                ]
            else:
                XYZwp = list(self.tags.wtpt.ir.values())  # noqa: N806
            cat = self.guess_cat() or "Bradford"
            XYZbp = colormath.adapt(*XYZbp, whitepoint_source=XYZwp, cat=cat)  # noqa: N806
        return XYZbp

    def optimize(
        self, return_bytes_saved: bool = False, update_id: bool = True
    ) -> bool | int:
        """Optimize the tag data so that shared tags are only recorded once.

        Return whether or not optimization was performed (not necessarily
        indicative of a reduction in profile size).
        If return_bytes_saved is True, return number of bytes saved instead
        (this sets the 'size' property of the profile to the new size).

        If update_id is True, a non-NULL profile ID will also be updated.

        Note that for profiles created by ICCProfile (and not read from disk),
        this will always be superfluous because they are optimized by default.

        Args:
            return_bytes_saved (bool): If True, return the number of bytes
                saved by the optimization instead of a boolean indicating
                whether optimization was performed.
            update_id (bool): If True, update the profile ID after
                optimization.

        Returns:
            bool | int: If return_bytes_saved is True, returns the number of
                bytes saved by the optimization. If return_bytes_saved is False,
                returns True if optimization was performed, otherwise False.
        """
        numoffsets = len(self._tagoffsets)
        offsets = [
            (-(numoffsets - i), tag_sig)
            for i, (offset, tag_sig) in enumerate(sorted(self._tagoffsets))
        ]
        if self._tagoffsets != offsets:
            if return_bytes_saved:
                oldsize = len(self.data)
            # Discard original offsets
            self._tagoffsets = offsets
            if update_id and self.ID != b"\0" * 16:
                self.calculate_id()
            else:
                # No longer reflects original profile
                self._delfromcache()
            if return_bytes_saved:
                self.size = len(self.data)
                return oldsize - self.size
            return True
        return 0 if return_bytes_saved else False

    def read(self, profile: str | pathlib.Path | bytes | BinaryIO | TextIO) -> None:
        """Read profile from binary string, filename or file object.

        Same as self.__init__(profile)

        Args:
            profile (str | pathlib.Path | bytes | BinaryIO | TextIO): The
                profile to read, which can be a filename, a file-like
                object, or a bytes object containing the profile data.
        """
        self.__init__(profile)

    def set_edid_metadata(self, edid: dict) -> None:
        """Set metadata from EDID.

        Key names follow the ICC meta Tag for Monitor Profiles specification
        http://www.oyranos.org/wiki/index.php?title=ICC_meta_Tag_for_Monitor_Profiles_0.1
        and the GNOME Color Manager metadata specification
        http://gitorious.org/colord/master/blobs/master/doc/metadata-spec.txt

        Args:
            edid (dict): A dictionary containing EDID data, which should
                include keys like 'manufacturer_id', 'product_id',
                'year_of_manufacture', 'week_of_manufacture', 'red_x', 'red_y',
                'green_x', 'green_y', 'blue_x', 'blue_y', 'white_x', 'white_y',
                'hash', 'manufacturer', 'monitor_name', 'serial_ascii',
                'serial_32', and 'gamma'.
        """
        if "meta" not in self.tags:
            self.tags.meta = DictType()
        spec_prefixes = "EDID_"
        prefix = self.tags.meta.getvalue("prefix", b"", None)
        if isinstance(prefix, bytes):
            prefix = prefix.decode("utf-8")
        prefixes = (prefix or spec_prefixes).split(",")
        for prefix in spec_prefixes.split(","):
            if prefix not in prefixes:
                prefixes.append(prefix)
        # OpenICC keys (some shared with GCM)
        self.tags.meta.update(
            (
                ("prefix", ",".join(prefixes)),
                ("EDID_mnft", edid["manufacturer_id"]),
                ("EDID_mnft_id", struct.unpack(">H", edid["edid"][8:10])[0]),
                ("EDID_model_id", edid["product_id"]),
                (
                    "EDID_date",
                    "{:04d}-T{:d}".format(
                        int(edid["year_of_manufacture"]),
                        int(edid["week_of_manufacture"]),
                    ),
                ),
                ("EDID_red_x", edid["red_x"]),
                ("EDID_red_y", edid["red_y"]),
                ("EDID_green_x", edid["green_x"]),
                ("EDID_green_y", edid["green_y"]),
                ("EDID_blue_x", edid["blue_x"]),
                ("EDID_blue_y", edid["blue_y"]),
                ("EDID_white_x", edid["white_x"]),
                ("EDID_white_y", edid["white_y"]),
            )
        )
        manufacturer = edid.get("manufacturer")
        if manufacturer:
            self.tags.meta["EDID_manufacturer"] = manufacturer
        if "gamma" in edid:
            self.tags.meta["EDID_gamma"] = edid["gamma"]
        monitor_name = edid.get("monitor_name", edid.get("ascii"))
        if monitor_name:
            self.tags.meta["EDID_model"] = monitor_name
        if edid.get("serial_ascii"):
            self.tags.meta["EDID_serial"] = edid["serial_ascii"]
        elif edid.get("serial_32"):
            # don't try to convert the following ``str`` to ``bytes``.
            # the edid["serial_32"] is a huge number and bytes({int}) is not working
            # like str({int}). What it tries is to create a b"\0" * {int}.
            self.tags.meta["EDID_serial"] = str(edid["serial_32"])
        # Gnome Color Management keys
        self.tags.meta["EDID_md5"] = edid["hash"]

    def set_gamut_metadata(
        self, gamut_volume: None | float = None, gamut_coverage: None | dict = None
    ) -> None:
        """Set gamut volume and coverage metadata keys.

        Args:
            gamut_volume (None | float, optional): The gamut volume in cubic
                colorspace units (L*a*b*).
            gamut_coverage (None | dict, optional): A dictionary with gamut
                coverage factors for different color spaces, e.g.
                {'sRGB': 0.95, 'AdobeRGB': 0.85}.
        """
        if not gamut_volume and not gamut_coverage:
            return
        if "meta" not in self.tags:
            self.tags.meta = DictType()
        # Update meta prefix
        prefix = self.tags.meta.getvalue("prefix", b"", None)
        if isinstance(prefix, bytes):
            prefix = prefix.decode("utf-8")
        prefixes = (prefix or "GAMUT_").split(",")
        if "GAMUT_" not in prefixes:
            prefixes.append("GAMUT_")
        self.tags.meta["prefix"] = ",".join(prefixes)
        if gamut_volume:
            # Set gamut size
            self.tags.meta["GAMUT_volume"] = gamut_volume
        if gamut_coverage:
            # Set gamut coverage
            for key in gamut_coverage:
                factor = gamut_coverage[key]
                self.tags.meta[f"GAMUT_coverage({key})"] = factor

    def write(self, stream_or_filename: None | str | BinaryIO = None) -> None:
        """Write profile to stream.

        This will re-assemble the various profile parts (header,
        tag table and data) on-the-fly.

        Args:
            stream_or_filename (None | str | BinaryIO): The stream or
                filename to write the profile to. If None, the profile will
                be written to the filename it was loaded from.
        """
        if not stream_or_filename:
            if self._file and not self._file.closed:
                self.close()
            stream_or_filename = self.filename
        if isinstance(stream_or_filename, str):
            with open(stream_or_filename, "wb") as stream:
                if not self.filename:
                    self.filename = stream_or_filename
                stream.write(self.data)
        else:
            stream_or_filename.write(self.data)

    def __getattribute__(self, name: str) -> Any:  # noqa: ANN401
        """Get attribute, but also update the cache if necessary.

        Args:
            name (str): The name of the attribute to get.

        Returns:
            Any: The value of the attribute.
        """
        if name == "write" or name.startswith(("set", "apply")):
            # No longer reflects original profile
            self._delfromcache()
        return object.__getattribute__(self, name)

    def _delfromcache(self) -> None:
        """Remove ourselves from the cache."""
        # Make double sure to remove ourselves from the cache
        if self._key and self._key in _ICCPROFILE_CACHE:
            with contextlib.suppress(KeyError):
                del _ICCPROFILE_CACHE[self._key]
                # GC was faster
