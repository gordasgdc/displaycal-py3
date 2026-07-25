"""Synthetic ICC cLUT profile builders."""

from __future__ import annotations

import functools
import math
import operator
from typing import TYPE_CHECKING, Callable, TextIO

from DisplayCAL import colormath
from DisplayCAL.icc_profile.constants import DEBUG
from DisplayCAL.icc_profile.tags import (
    ChromaticAdaptionTag,
    CurveType,
    LUT16Type,
    TextDescriptionType,
    TextType,
    XYZType,
)
from DisplayCAL.options import TEST_INPUT_CURVE_CLIPPING

if TYPE_CHECKING:
    from DisplayCAL.icc_profile import ICCProfile
    from DisplayCAL.worker import Worker, Xicclu


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
    from DisplayCAL.icc_profile import ICCProfile

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

    from DisplayCAL.icc_profile import ICCProfile

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
        from DisplayCAL.icc_profile.tonemap import _mp_hdr_tonemap
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
