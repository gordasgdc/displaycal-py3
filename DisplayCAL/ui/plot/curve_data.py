"""Extract a profile's tone curves for plotting.

Binding-agnostic counterpart to the curve-building parts of
``wx_lut_viewer``. Curves are normalised to the unit square (0..1):

* ``vcgt`` — the calibration video-card-gamma curves (table or formula),
* ``trc`` — the ``rTRC``/``gTRC``/``bTRC`` tone-response tags,
* ``measured`` — the live ``xicclu`` tone response (``measured_tone_response``).

It also bridges profile sources that aren't ``.icc``/``.icm`` files: loading a
``.cal`` calibration file and reading the live video-card LUT, both via
:func:`DisplayCAL.argyll_cgats.cal_to_fake_profile`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from DisplayCAL import colormath
from DisplayCAL.icc_profile import CurveType

if TYPE_CHECKING:
    from DisplayCAL.icc_profile import ICCProfile, VideoCardGammaType
    from DisplayCAL.worker import Worker

#: Plot mode -> human label key (for UI). Order is the preferred default order.
#: Mode key -> lang key. "vcgt"/"trc" reuse wx_lut_viewer's own labels
#: ("Calibration curves"/"Tone response curves"); "measured" has no wx
#: equivalent (wx always computes its "[rgb]TRC" curve via a live xicclu
#: lookup, it doesn't distinguish a separate "raw tag data" vs. "measured"
#: mode), so there's no existing translation for it.
CURVE_MODES = {
    "vcgt": "vcgt",
    "trc": "[rgb]TRC",
    "measured": "measured_tone_response",
}

#: TRC tag -> channel name.
_TRC_TAGS = {"rTRC": "R", "gTRC": "G", "bTRC": "B"}


def available_curve_modes(profile: ICCProfile) -> list[str]:
    """Return the curve modes present/derivable for ``profile``.

    ``"measured"`` is offered only for RGB profiles that ``xicclu`` can actually
    look up: a colorimetric matrix (``rXYZ``/``gXYZ``/``bXYZ``) or a cLUT
    (``A2B0``). Vcgt-only "fake" profiles (e.g. the video-card LUT read back for
    "show actual LUT") have neither and no media white point, so ``xicclu``
    would fail with "missing Media White Point Tag"; measured is skipped there.

    Args:
        profile (ICCProfile): The profile to inspect.

    Returns:
        list[str]: The available mode keys (subset of ``CURVE_MODES``).
    """
    modes = []
    if "vcgt" in profile.tags:
        modes.append("vcgt")
    if any(isinstance(profile.tags.get(tag), CurveType) for tag in _TRC_TAGS):
        modes.append("trc")
    has_matrix = all(tag in profile.tags for tag in ("rXYZ", "gXYZ", "bXYZ"))
    has_clut = "A2B0" in profile.tags
    if profile.colorSpace == b"RGB" and (has_matrix or has_clut):
        modes.append("measured")
    return modes


#: Lookup directions offered for the measured tone response: label key -> code.
#: ``f`` forward (device→PCS); ``if`` inverse-forward (PCS→device, default for
#: matrix profiles); ``b``/``ib`` backward variants (cLUT B2A profiles only).
DIRECTIONS = {
    "forward": "f",
    "inverse": "if",
    "backward": "b",
    "inverse_backward": "ib",
}


def available_directions(profile: ICCProfile) -> list[str]:
    """Return the measured-curve directions usable for ``profile``.

    Backward (``b``/``ib``) lookups require a cLUT ``B2A0`` table.

    Args:
        profile (ICCProfile): The profile to inspect.

    Returns:
        list[str]: Direction codes (subset of ``f``/``if``/``b``/``ib``).
    """
    if "B2A0" in profile.tags:
        return ["f", "if", "b", "ib"]
    return ["f", "if"]


def measured_tone_response(
    profile: ICCProfile,
    worker: Worker,
    intent: str = "r",
    use_clut: bool = True,
    direction: str = "f",
    size: int = 256,
) -> dict[str, list[tuple[float, float]]]:
    """Return the *measured* per-channel tone response via Argyll ``xicclu``.

    Unlike the ``vcgt``/``trc`` tags (read straight from the profile), this looks
    the profile up to get its actual behaviour. The ``direction`` selects the
    presentation, mirroring ``LUTFrame.lookup_tone_response_curves``:

    * ``"f"`` forward — ramp each primary 0→1, look up forward to PCS XYZ and
      plot input vs the resulting (per-channel-normalised) luminance.
    * ``"if"``/``"b"``/``"ib"`` inverse/backward — ramp a neutral target through
      the profile inverse to get the device values needed, and plot the target
      relative luminance vs device value.

    For cLUT profiles the ``use_clut`` flag selects the cLUT (``A2B``) path
    versus the colorimetric matrix/shaper path (the ``order`` choice).

    Args:
        profile (ICCProfile): An RGB profile to measure.
        worker (Worker): A :class:`DisplayCAL.worker.Worker` driving ``xicclu``.
        intent (str): Rendering intent (``a``/``r``/``p``/``s``).
        use_clut (bool): Use the cLUT path when the profile has one.
        direction (str): ``f``/``if``/``b``/``ib`` (see above).
        size (int): Number of ramp samples per channel.

    Returns:
        dict[str, list[tuple[float, float]]]: ``{"R": ..., "G": ..., "B": ...}``
        of normalised ``(x, y)`` points.

    Raises:
        ValueError: If the profile is not an RGB device profile.
    """
    if profile.colorSpace != b"RGB":
        raise ValueError("Measured tone response requires an RGB profile")

    has_clut = "A2B0" in profile.tags or "B2A0" in profile.tags
    order = "n" if has_clut and use_clut else "r"

    # "f" and "ib" are device-input (forward-like); "b" and "if" are
    # target-input (inverse), mirroring the grouping in the wx original.
    if direction in ("b", "if"):
        return _inverse_tone_response(profile, worker, intent, order, direction, size)
    return _forward_tone_response(profile, worker, intent, order, direction, size)


def _forward_tone_response(
    profile: ICCProfile, worker: Worker, intent: str, order: str, direction: str,
    size: int,
) -> dict[str, list[tuple[float, float]]]:
    """Forward measurement: input device value → measured luminance.

    Args:
        profile (ICCProfile): The RGB profile to measure.
        worker (Worker): The worker driving ``xicclu``.
        intent (str): Rendering intent (``a``/``r``/``p``/``s``).
        order (str): ``xicclu`` order (``n`` cLUT or ``r`` matrix/shaper).
        direction (str): Device-input direction (``f`` or ``ib``).
        size (int): Number of ramp samples per channel.

    Returns:
        dict[str, list[tuple[float, float]]]: Per-channel ``(input, luminance)``
        points normalised to 0..1.
    """
    curves = {}
    for channel, name in enumerate(("R", "G", "B")):
        ramp = []
        for i in range(size):
            values = [0.0, 0.0, 0.0]
            values[channel] = i / (size - 1)
            ramp.append(values)
        xyz = worker.xicclu(profile, ramp, intent, direction, order, pcs="x")
        luminance = [triplet[1] for triplet in xyz]
        curves[name] = _normalise_channel(luminance, size)
    return curves


def _neutral_lab_ramp(
    profile: ICCProfile, intent: str, size: int
) -> list[list[float]]:
    """Build the neutral L* target ramp fed to the profile inverse.

    Args:
        profile (ICCProfile): The profile being measured.
        intent (str): Rendering intent; ``a`` adapts the ramp to profile white.
        size (int): Number of ramp samples.

    Returns:
        list[list[float]]: The neutral ``[L*, a*, b*]`` target ramp.
    """
    ramp = []
    for i in range(size):
        if intent == "a" and "wtpt" in profile.tags:
            # Adapt the neutral axis to the profile (illuminant-relative) white,
            # so absolute-colorimetric targets land on paper/display white.
            wp_ir = list(profile.tags.wtpt.ir.values())
            lab_wp_ir = profile.tags.wtpt.ir.Lab
            wp_d50 = colormath.Lab2XYZ(lab_wp_ir[0], 0, 0)
            x, y, z = colormath.Lab2XYZ(
                min(i * (100.0 / (size - 1)), lab_wp_ir[0]), 0, 0
            )
            adapted = colormath.adapt(x, y, z, wp_d50, wp_ir)
            lab = list(colormath.XYZ2Lab(*[v * 100 for v in adapted]))
        else:
            lab = [i * (100.0 / (size - 1)), 0.0, 0.0]
        ramp.append(lab)
    return ramp


def _inverse_tone_response(
    profile: ICCProfile, worker: Worker, intent: str, order: str, direction: str,
    size: int,
) -> dict[str, list[tuple[float, float]]]:
    """Inverse/backward measurement: target luminance → device value.

    Args:
        profile (ICCProfile): The RGB profile to measure.
        worker (Worker): The worker driving ``xicclu``.
        intent (str): Rendering intent (``a``/``r``/``p``/``s``).
        order (str): ``xicclu`` order (``n`` cLUT or ``r`` matrix/shaper).
        direction (str): Target-input direction (``if`` or ``b``).
        size (int): Number of ramp samples.

    Returns:
        dict[str, list[tuple[float, float]]]: Per-channel
        ``(target luminance, device value)`` points normalised to 0..1.
    """
    lab_ramp = _neutral_lab_ramp(profile, intent, size)
    odata = worker.xicclu(
        profile, lab_ramp, intent, direction, order, pcs="l",
        get_clip=direction == "if",
    )
    odata = _clean_inverse_output(odata, size) if direction == "if" else [
        list(values[:3]) for values in odata
    ]

    curves = {"R": [], "G": [], "B": []}
    for j, sample in enumerate(odata):
        # x = target relative luminance (X = Z = Y for the neutral axis).
        x = colormath.Lab2XYZ(*lab_ramp[j], scale=100)[1] / 100.0
        for channel, name in enumerate(("R", "G", "B")):
            curves[name].append((x, max(0.0, min(1.0, sample[channel]))))
    return curves


def _clean_inverse_output(
    odata: list[list[float]], size: int
) -> list[list[float]]:
    """Resolve clipped samples for the ``if`` direction and drop clip flags.

    Mirrors the effective behaviour of the clipping pass in
    ``LUTFrame.lookup_tone_response_curves``: clamp the first sample to black and
    a clipped final all-ones sample to white. (The wx monotonicity pass that
    follows is dead code — its index is the stale outer-loop value, so its
    guard never holds — and is intentionally not reproduced.)

    Args:
        odata (list[list[float]]): ``xicclu`` output, possibly with a trailing
            clip flag per sample.
        size (int): Number of ramp samples.

    Returns:
        list[list[float]]: Cleaned RGB device values (clip flags removed).
    """
    cleaned = []
    for i, values in enumerate(odata):
        clipped = len(values) > 3 and values[3] is True
        rgb = list(values[:3])
        if i == 0:
            rgb = [0.0, 0.0, 0.0]
        elif clipped and i == size - 1 and [round(v, 4) for v in rgb] == [1, 1, 1]:
            rgb = [1.0, 1.0, 1.0]
        cleaned.append(rgb)
    return cleaned


def _normalise_channel(luminance: list[float], size: int) -> list[tuple[float, float]]:
    """Map a luminance ramp to ``(input, output)`` points normalised to 0..1.

    Args:
        luminance (list[float]): The measured luminance per ramp step.
        size (int): Number of ramp samples.

    Returns:
        list[tuple[float, float]]: ``(input, output)`` points in 0..1.
    """
    black, white = luminance[0], luminance[-1]
    span = (white - black) or 1.0
    return [
        (i / (size - 1), max(0.0, min(1.0, (luminance[i] - black) / span)))
        for i in range(size)
    ]


def extract_curves(
    profile: ICCProfile, mode: str
) -> dict[str, list[tuple[float, float]]]:
    """Return ``{channel: [(x, y), ...]}`` (0..1) for ``mode``.

    Args:
        profile (ICCProfile): Profile to read curves from.
        mode (str): ``"vcgt"`` or ``"trc"``.

    Returns:
        dict[str, list[tuple[float, float]]]: Channel name → normalised point
        list. Empty if the mode has no data.
    """
    if mode == "vcgt" and "vcgt" in profile.tags:
        return _vcgt_curves(profile.tags["vcgt"])
    if mode == "trc":
        return _trc_curves(profile)
    return {}


def curve_display(
    mode: str,
    curves: dict[str, list[tuple[float, float]]],
    show_as_l: bool = True,
) -> tuple[dict[str, list[tuple[float, float]]], float, float, str, str]:
    """Map normalised (input, output) curves onto wx's display axes.

    Mirrors ``wx_lut_viewer.LUTCanvas.DrawLUT``:

    * ``vcgt`` — device in / device out, both ``0..255`` ("RGB" / "RGB").
    * ``trc`` / ``measured`` — the response, plotted with the device value on
      the Y axis (``0..255``, "RGB") against the response on the X axis: either
      perceptual L* (``0..100``, "L*") when ``show_as_l`` else linear luminance
      Y (``0..100``, "Y"). Note the axes are transposed relative to ``vcgt``.

    Args:
        mode (str): ``"vcgt"``, ``"trc"`` or ``"measured"``.
        curves (dict[str, list[tuple[float, float]]]): Normalised (0..1) points.
        show_as_l (bool): For trc/measured, map luminance to L* (else linear Y).

    Returns:
        tuple: ``(channels, x_max, y_max, x_label, y_label)`` where ``channels``
        holds the display-scaled points and the labels have no in/out suffix.
    """
    if mode == "vcgt":
        scaled = {
            name: [(x * 255.0, y * 255.0) for x, y in points]
            for name, points in curves.items()
        }
        return scaled, 255.0, 255.0, "RGB", "RGB"
    # trc / measured: transpose (device on Y) and map luminance to L*/Y on X.
    display: dict[str, list[tuple[float, float]]] = {}
    for name, points in curves.items():
        row = []
        for value_in, value_out in points:
            device = value_in * 255.0
            luminance = value_out * 100.0
            x = colormath.XYZ2Lab(0, luminance, 0)[0] if show_as_l else luminance
            row.append((x, device))
        display[name] = row
    return display, 100.0, 255.0, ("L*" if show_as_l else "Y"), "RGB"


def _curve_type_points(curve: CurveType) -> list[tuple[float, float]]:
    """Normalise a ``CurveType`` (table, single-gamma, or linear) to 0..1.

    Args:
        curve (CurveType): The tone-response curve tag.

    Returns:
        list[tuple[float, float]]: ``(input, output)`` points in 0..1.
    """
    n = len(curve)
    if n == 0:  # identity / linear
        return [(0.0, 0.0), (1.0, 1.0)]
    if n == 1:  # single gamma value
        gamma = float(curve[0]) or 1.0
        return [(i / 255.0, (i / 255.0) ** gamma) for i in range(256)]
    return [(i / (n - 1), curve[i] / 65535.0) for i in range(n)]


def _trc_curves(profile: ICCProfile) -> dict[str, list[tuple[float, float]]]:
    """Return the rTRC/gTRC/bTRC tone-response curves.

    Args:
        profile (ICCProfile): Profile carrying the ``*TRC`` tags.

    Returns:
        dict[str, list[tuple[float, float]]]: Per-channel normalised points.
    """
    curves = {}
    for tag, name in _TRC_TAGS.items():
        curve = profile.tags.get(tag)
        if isinstance(curve, CurveType):
            curves[name] = _curve_type_points(curve)
    return curves


def _vcgt_curves(vcgt: VideoCardGammaType) -> dict[str, list[tuple[float, float]]]:
    """Return the video-card-gamma calibration curves (table or formula).

    Args:
        vcgt (VideoCardGammaType): The profile's ``vcgt`` tag.

    Returns:
        dict[str, list[tuple[float, float]]]: Per-channel normalised points.
    """
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


# -- profile sources ---------------------------------------------------------


def load_profile_or_cal(path: str) -> ICCProfile | None:
    """Load ``path`` as an ICC profile, or a ``.cal`` calibration file.

    ``.cal`` files are wrapped in a fake profile (vcgt only) via
    :func:`DisplayCAL.argyll_cgats.cal_to_fake_profile`, mirroring the wx LUT
    viewer's drag-and-drop handling.

    Args:
        path (str): Path to an ``.icc``/``.icm`` profile or a ``.cal`` file.

    Returns:
        ICCProfile | None: The loaded profile, or ``None`` if it could not be
        read.
    """
    if os.path.splitext(path)[1].lower() == ".cal":
        from DisplayCAL.argyll_cgats import cal_to_fake_profile

        return cal_to_fake_profile(path)
    from DisplayCAL.icc_profile import ICCProfile

    return ICCProfile(path)


def read_current_lut(worker: Worker, display_no: int = 1) -> ICCProfile:
    """Read the live video-card LUT of ``display_no`` as a fake profile.

    Saves the current hardware gamma ramp with Argyll ``dispwin`` and wraps it
    in a fake profile (vcgt) so its calibration curves can be plotted — the Qt
    equivalent of the wx "show actual LUT" option.

    Args:
        worker (Worker): A :class:`DisplayCAL.worker.Worker` to drive
            ``dispwin``.
        display_no (int): Argyll display index (1-based).

    Returns:
        ICCProfile: A fake profile carrying the read-back vcgt.

    Raises:
        Exception: If the LUT could not be read or converted.
    """
    from DisplayCAL.argyll_cgats import cal_to_fake_profile

    tmp = worker.create_tempdir()
    if isinstance(tmp, Exception):
        raise tmp
    outfilename = os.path.join(tmp, "Video LUT")
    result = worker.save_current_video_lut(display_no, outfilename, silent=True)
    if isinstance(result, Exception):
        raise result
    profile = cal_to_fake_profile(outfilename)
    if not profile:
        raise ValueError("Could not read the current video card LUT")
    return profile
