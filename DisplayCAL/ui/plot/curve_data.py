"""Extract a profile's tone curves for plotting (no Argyll required).

Binding-agnostic counterpart to the point-building parts of
``wx_lut_viewer.LUTCanvas.DrawLUT``. It pulls directly-plottable curves out of a
profile and normalises them to the unit square (input and output in 0..1):

* ``vcgt`` — the calibration video-card-gamma curves (table or formula).
* ``trc`` — the ``rTRC``/``gTRC``/``bTRC`` tone-response tags.

The "actual measured" tone-response path (looking the profile up through
``xicclu`` with rendering-intent/direction controls, i.e.
``LUTFrame.lookup_tone_response_curves``) is intentionally not handled here yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from DisplayCAL.icc_profile import CurveType

if TYPE_CHECKING:
    from DisplayCAL.icc_profile import ICCProfile, VideoCardGammaType

#: Plot mode -> human label key (for UI). Order is the preferred default order.
CURVE_MODES = {"vcgt": "calibration_curves", "trc": "tone_response_curves"}

#: TRC tag -> channel name.
_TRC_TAGS = {"rTRC": "R", "gTRC": "G", "bTRC": "B"}


def available_curve_modes(profile: ICCProfile) -> list[str]:
    """Return the curve modes (``"vcgt"``/``"trc"``) present in ``profile``."""
    modes = []
    if "vcgt" in profile.tags:
        modes.append("vcgt")
    if any(isinstance(profile.tags.get(tag), CurveType) for tag in _TRC_TAGS):
        modes.append("trc")
    return modes


def extract_curves(
    profile: ICCProfile, mode: str
) -> dict[str, list[tuple[float, float]]]:
    """Return ``{channel: [(x, y), ...]}`` (0..1) for ``mode``.

    Args:
        profile: Profile to read curves from.
        mode: ``"vcgt"`` or ``"trc"``.

    Returns:
        Channel name → normalised point list. Empty if the mode has no data.
    """
    if mode == "vcgt" and "vcgt" in profile.tags:
        return _vcgt_curves(profile.tags["vcgt"])
    if mode == "trc":
        return _trc_curves(profile)
    return {}


def _curve_type_points(curve: CurveType) -> list[tuple[float, float]]:
    """Normalise a ``CurveType`` (table, single-gamma, or linear) to 0..1."""
    n = len(curve)
    if n == 0:  # identity / linear
        return [(0.0, 0.0), (1.0, 1.0)]
    if n == 1:  # single gamma value
        gamma = float(curve[0]) or 1.0
        return [(i / 255.0, (i / 255.0) ** gamma) for i in range(256)]
    return [(i / (n - 1), curve[i] / 65535.0) for i in range(n)]


def _trc_curves(profile: ICCProfile) -> dict[str, list[tuple[float, float]]]:
    """Return the rTRC/gTRC/bTRC tone-response curves."""
    curves = {}
    for tag, name in _TRC_TAGS.items():
        curve = profile.tags.get(tag)
        if isinstance(curve, CurveType):
            curves[name] = _curve_type_points(curve)
    return curves


def _vcgt_curves(vcgt: VideoCardGammaType) -> dict[str, list[tuple[float, float]]]:
    """Return the video-card-gamma calibration curves (table or formula)."""
    if "data" in vcgt:  # VideoCardGammaTableType
        data = vcgt["data"]
        n = vcgt["entryCount"]
        maxv = 2 ** (8 * vcgt["entrySize"]) - 1
        names = ["R", "G", "B"] if len(data) >= 3 else ["Gray"]
        return {
            names[ch]: [(i / (n - 1), data[ch][i] / maxv) for i in range(n)]
            for ch in range(min(len(data), len(names)))
        }

    # VideoCardGammaFormulaType: y = min + x**gamma * (max - min)
    curves = {}
    for color, name in (("red", "R"), ("green", "G"), ("blue", "B")):
        gamma = vcgt[f"{color}Gamma"]
        vmin = vcgt[f"{color}Min"]
        vmax = vcgt[f"{color}Max"]
        curves[name] = [
            (i / 255.0, vmin + (i / 255.0) ** gamma * (vmax - vmin)) for i in range(256)
        ]
    return curves
