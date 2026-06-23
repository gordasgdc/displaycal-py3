"""Compute a profile's gamut-surface samples (linear XYZ) for plotting.

This is the binding-agnostic backend extracted from
``wx_profile_info.GamutCanvas.setup`` (a ~250-line method). It samples a
profile's device-value cube along the primary→secondary edges and looks the
samples up through the profile with Argyll's ``xicclu`` to obtain PCS (XYZ)
coordinates, which :class:`DisplayCAL.ui.plot.gamut.GamutPlot` then draws.

Kept here (not in the widget) so the data path can be tested and reused without
any UI. Only the common device-profile and named-colour cases are handled; the
exotic colour spaces follow the same structure as the wx original.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from DisplayCAL import colormath
from DisplayCAL.icc_profile import NamedColor2Type

if TYPE_CHECKING:
    from DisplayCAL.icc_profile import ICCProfile
    from DisplayCAL.worker import Worker

#: Device channel counts by ICC colour-space signature.
_CHANNELS = {
    b"XYZ": 3, b"Lab": 3, b"Luv": 3, b"YCbr": 3, b"Yxy": 3, b"RGB": 3,
    b"GRAY": 1, b"HSV": 3, b"HLS": 3, b"CMYK": 4, b"CMY": 3, b"2CLR": 2,
    b"3CLR": 3, b"4CLR": 4, b"5CLR": 5, b"6CLR": 6, b"7CLR": 7, b"8CLR": 8,
    b"9CLR": 9, b"ACLR": 10, b"BCLR": 11, b"CCLR": 12, b"DCLR": 13,
    b"ECLR": 14, b"FCLR": 15,
}


def is_supported(profile: ICCProfile) -> bool:
    """Return whether a gamut can be computed for ``profile``."""
    return bool(
        profile
        and profile.profileClass != b"link"
        and profile.connectionColorSpace in (b"Lab", b"XYZ")
    )


def _named_color_triplets(profile: ICCProfile, intent: str) -> list[list[float]]:
    """Return XYZ triplets for a named-colour (nmcl/ncl2) profile."""
    triplets = []
    for key in profile.tags.ncl2:
        color = list(profile.tags.ncl2[key].pcs.values())
        if profile.connectionColorSpace == b"Lab":
            color = list(colormath.Lab2XYZ(*color))
        if intent == "a" and "wtpt" in profile.tags:
            color = list(
                colormath.adapt(
                    *color,
                    whitepoint_destination=list(profile.tags.wtpt.ir.values()),
                )
            )
        triplets.append(color)
    triplets.sort()
    return triplets


def _device_sample_values(
    profile: ICCProfile, channels: int, size: int
) -> list[list[float]]:
    """Build the device-value cube edge samples to look up through ``profile``."""
    if profile.colorSpace in (b"Lab", b"Luv", b"XYZ", b"Yxy"):
        minv, maxv = 0.0, 0xFFFF / 32768.0  # ICC PCSXYZ encoding range
    else:
        minv, maxv = 0.0, 1.0
    step = (maxv - minv) / (size - 1)

    values: list[list[float]] = []
    for j in range(min(3, channels)):
        for k in range(min(3, channels)):
            base = [0.0] * channels
            base[j] = maxv
            if j != k or channels == 1:
                for step_i in range(size):
                    base[k] = minv + step * step_i
                    values.append(list(base))

    # Add the white point sample so the profile whitepoint marker can be drawn.
    if profile.colorSpace == b"RGB":
        values.append([1.0] * channels)
    elif profile.colorSpace in (b"XYZ",):
        values.append(list(profile.tags.wtpt.pcs.values()))
    elif profile.colorSpace == b"GRAY":
        pass
    else:
        values.append([0.0] * channels)
    return values


def compute_profile_gamut(
    profile: ICCProfile,
    worker: Worker,
    intent: str = "r",
    direction: str = "f",
    order: str = "n",
    size: int = 40,
) -> list[list[float]]:
    """Return the profile's gamut-surface samples as linear-XYZ triplets.

    Args:
        profile: The profile to sample.
        worker: A :class:`DisplayCAL.worker.Worker` used to drive ``xicclu``.
        intent: Rendering intent (``a``/``r``/``p``/``s``).
        direction: ``f`` forward, or ``ib`` inverted-backward (round-trip).
        order: ``n`` normal or ``c`` chromatic-adaptation order.
        size: Segments per primary→secondary edge.

    Returns:
        A list of ``[X, Y, Z]`` triplets; the last is the profile whitepoint.

    Raises:
        ValueError: If the profile's colour space is unsupported.
    """
    if (
        profile.profileClass == b"nmcl"
        and "ncl2" in profile.tags
        and isinstance(profile.tags.ncl2, NamedColor2Type)
    ):
        return _named_color_triplets(profile, intent)

    if profile.version >= 4:
        profile.convert_iccv4_tags_to_iccv2()

    channels = _CHANNELS.get(profile.colorSpace)
    if not channels:
        raise ValueError(
            f"Unsupported profile: {profile.profileClass} {profile.colorSpace}"
        )

    device_values = _device_sample_values(profile, channels, size)

    # Device -> PCS (forward); optionally round-trip for the inverted view.
    fwd_intent = "r" if direction == "ib" and intent not in "ar" else intent
    odata = worker.xicclu(profile, device_values, intent, "f", order)
    if direction == "ib":
        odata = worker.xicclu(profile, odata, intent, "b", order)
        odata = worker.xicclu(profile, odata, fwd_intent, "f", order)

    to_xyz = profile.connectionColorSpace == b"Lab"
    return [
        list(colormath.Lab2XYZ(*pcs)) if to_xyz else list(pcs) for pcs in odata
    ]
