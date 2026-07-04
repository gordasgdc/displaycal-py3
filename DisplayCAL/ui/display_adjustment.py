"""Toolkit-neutral parser for interactive display-adjustment output (Stage 5c).

The wx interactive display-adjustment window
(``wx_display_adjustment_frame.py::DisplayAdjustmentFrame``) is shown during
``worker.calibrate`` and guides the user through adjusting the monitor
(brightness, RGB gain / offset, black level) to hit the calibration targets. It
does this by parsing the interactive text ``dispcal`` streams while it measures,
turning each reading into gauge positions, target / current read-outs and an
in-tolerance check mark.

That parsing -- the regex extraction plus the gauge / tolerance maths in
``DisplayAdjustmentFrame.parse_txt`` -- is toolkit-neutral, but in wx it is
interleaved with ``wx.Freeze``/``Thaw``, ``SetValue`` / ``SetForegroundColour``
and check-mark show/hide on live widgets, so it cannot be reused as-is under Qt.
This module lifts it out as the pure, unit-testable :func:`parse_adjustment`
(mirroring how ``worker_runner.parse_progress`` was lifted out of the
progress handler for the non-interactive path). The Qt window (sub-slice 5c-ii)
holds an :class:`AdjustmentContext`, feeds each ``dispcal`` chunk through
:func:`parse_adjustment`, and renders the returned :class:`AdjustmentReadings`
onto its gauges / labels; wiring it into the worker calibrate path is 5c-iii.

See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 5, sub-slice 5c).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from DisplayCAL import localization as lang

# Unicode bits the wx labels use verbatim.
CD_M2 = "cd/m²"
DELTA_E = "ΔE*00"
PLUS_MINUS = "±"


def _compile(pattern: str) -> re.Pattern:
    r"""Compile a ``parse_txt`` pattern (literal spaces -> ``\s+``, ignore case).

    The wx code builds every pattern with ``.replace(" ", r"\s+")`` so a run of
    spaces in ``dispcal`` output matches; this reproduces that exactly.
    """
    return re.compile(pattern.replace(" ", r"\s+"), re.I)


_NUM = r"(\d+(?:\.\d+)?)"

_TARGET_BR_RE = _compile(rf"Target white brightness = {_NUM}")
_TARGET_NEAR_BLACK_RE = _compile(rf"Target Near Black = {_NUM}, Current = {_NUM}")
_INITIAL_BR_RE = _compile(
    rf"(Initial|Target)(?: Br)? {_NUM}\s*(?:, "
    rf"x {_NUM}\s*, y {_NUM}(?:\s*, "
    rf"(?:(V[CD]T \d+K?) )?DE(?: 2K)? {_NUM})?|$)"
)
_CURRENT_BR_RE = _compile(rf"Current(?: Br)? {_NUM}")
_CHECK_ALL_TARGET_BR_RE = _compile(
    rf"Target Brightness = (?:\d+(?:\.\d+)?), Current = {_NUM}"
)
_CHECK_ALL_CURRENT_BR_RE = _compile(rf"Current Brightness = {_NUM}")
_CURRENT_BLACK_XYZ_RE = _compile(
    rf"Black = XYZ (?:\d+(?:\.\d+)?) {_NUM} (?:\d+(?:\.\d+)?)"
)
_XY_DE_RGB_RE = _compile(
    rf"x {_NUM}[=+-]*, y {_NUM}[=+-]*,? "
    rf"(?:(V[CD]T \d+K?) )?DE(?: 2K)? {_NUM} "
    r"R([=+-]+) G([=+-]+) B([=+-]+)"
)
# The ``Target white = x .., y ..`` prefix is matched but not captured (only the
# Current x / y / vt / dE feed :func:`_xy_vt_de`), matching the wx pattern.
_WHITE_XY_DE_PATTERN = (
    r"(?:Target white = x (?:\d+(?:\.\d+)?), y (?:\d+(?:\.\d+)?), "
    rf"Current|Current white) = x {_NUM}, y {_NUM}, "
    rf"(?:(?:(V[CD]T \d+K?) )?DE(?: 2K)?|error =) {_NUM}"
)
_WHITE_XY_DE_RE = _compile(_WHITE_XY_DE_PATTERN)
_BLACK_XY_DE_RE = _compile(_WHITE_XY_DE_PATTERN.replace("white", "black"))
_WHITE_XY_TARGET_RE = _compile(rf"Target white = x {_NUM}, y {_NUM}")
_BLACK_XY_TARGET_RE = _compile(rf"Target black = x {_NUM}, y {_NUM}")


def _xy_vt_de(groups: tuple) -> tuple[float, float, str, float]:
    """Port of ``get_xy_vt_dE``: pull ``(x, y, vt, dE)`` from a match's groups."""
    x = float(groups[0])
    y = float(groups[1])
    vt = ""
    de = 0.0
    if len(groups) > 2:
        vt = groups[2] or ""
        if groups[3]:
            de = float(groups[3])
    return x, y, vt, de


def _sign(diff: float) -> str:
    """The +/-/plus-minus sign wx prefixes to a rounded difference."""
    if round(diff, 2) > 0:
        return "+"
    if round(diff, 2) < 0:
        return "-"
    return PLUS_MINUS


@dataclass
class MetricLabel:
    """A parsed target / current read-out for one adjustment metric.

    Attributes:
        text (str): The multi-line label text to show (already localized).
        in_tolerance (bool): Whether the metric is within tolerance (the wx
            frame shows a check mark and greens the label when true).
    """

    text: str
    in_tolerance: bool


@dataclass
class AdjustmentContext:
    """Persistent state threaded across :func:`parse_adjustment` calls.

    Mirrors the state ``DisplayAdjustmentFrame.parse_txt`` keeps on the frame
    (``target_br``) and on the current page (``initial_br`` / ``target_bl``):
    a reading references targets seen in an earlier chunk, so the caller keeps
    one context per active adjustment page and lets the parser update it.

    Attributes:
        ctrltype (str): The active page's control type -- one of ``black_level``,
            ``rgb_gain``, ``luminance``, ``rgb_offset`` or ``check_all``.
        measurement_mode (str): ``"c"`` for CRT, else the LCD path.
        target_br (list | None): ``["Target", brightness]``, latched once seen.
        initial_br (list | None): ``[label, value, x, y, vt, dE]`` for the page.
        target_bl (list | None): ``["Target", black_luminance]`` for the page.
    """

    ctrltype: str
    measurement_mode: str = "l"
    target_br: list | None = None
    initial_br: list | None = None
    target_bl: list | None = None


@dataclass
class AdjustmentReadings:
    """What one ``dispcal`` chunk says to render.

    Attributes:
        gauges (dict[str, int]): Gauge name (``L`` / ``R`` / ``G`` / ``B``) to a
            ``1..100`` needle position.
        labels (dict[str, MetricLabel]): Metric name (``luminance`` /
            ``black_level`` / ``rgb`` / ``white_point`` / ``black_point``) to its
            read-out. The window applies only the metrics its page actually has.
        indicator (str | None): ``"record"`` / ``"record_outline"`` for the
            measuring dot, or ``None`` when this chunk is not a reading.
        reading_event (bool): True when a fresh measurement landed (the frame
            beeps and updates the indicator on this).
        phase (str | None): ``"menu"`` when ``dispcal`` returned to the
            interactive menu (adjustment ready), ``"measuring"`` when it began a
            measurement pass, else ``None``.
    """

    gauges: dict[str, int] = field(default_factory=dict)
    labels: dict[str, MetricLabel] = field(default_factory=dict)
    indicator: str | None = None
    reading_event: bool = False
    phase: str | None = None


def parse_adjustment(txt: str, ctx: AdjustmentContext) -> AdjustmentReadings:
    """Parse an interactive ``dispcal`` output chunk into render instructions.

    Pure port of ``DisplayAdjustmentFrame.parse_txt`` (regex extraction + gauge /
    tolerance maths only; no widget mutation). ``ctx`` is updated in place with
    any targets latched from ``txt``, matching the frame's stateful behaviour.

    Args:
        txt (str): A chunk of interactive ``dispcal`` output.
        ctx (AdjustmentContext): The active page's persistent parse state,
            updated in place.

    Returns:
        AdjustmentReadings: The gauges, labels and state transitions to render.
    """
    readings = AdjustmentReadings()
    if not txt:
        return readings

    indicator = "record" if "/ Current" in txt else "record_outline"

    target_br_match = _TARGET_BR_RE.search(txt)
    if target_br_match and not ctx.target_br:
        ctx.target_br = ["Target", float(target_br_match.group(1))]

    near_black = None
    if ctx.measurement_mode == "c":
        near_black = _TARGET_NEAR_BLACK_RE.search(txt)
        if near_black:
            ctx.target_bl = ["Target", float(near_black.group(1))]

    initial_match = _INITIAL_BR_RE.search(txt)
    if initial_match:
        groups = initial_match.groups()
        ctx.initial_br = [groups[0], float(groups[1]), *groups[2:]]

    current_bl = None
    if ctx.ctrltype != "check_all":
        current_br = _CURRENT_BR_RE.search(txt)
    else:
        current_br = _CHECK_ALL_TARGET_BR_RE.search(txt)
        if not current_br:
            current_br = _CHECK_ALL_CURRENT_BR_RE.search(txt)
        if ctx.measurement_mode == "c":
            if near_black:
                current_bl = float(near_black.group(2))
        else:
            black_xyz = _CURRENT_BLACK_XYZ_RE.search(txt)
            if black_xyz:
                current_bl = float(black_xyz.group(1))

    xy_dE_rgb = _XY_DE_RGB_RE.search(txt)
    white_xy_dE = _WHITE_XY_DE_RE.search(txt)
    black_xy_dE = _BLACK_XY_DE_RE.search(txt)
    white_xy_target = _WHITE_XY_TARGET_RE.search(txt)
    black_xy_target = _BLACK_XY_TARGET_RE.search(txt)

    if current_br:
        _parse_luminance(readings, ctx, float(current_br.group(1)))
    if current_bl:
        _parse_black_level(readings, ctx, current_bl)
    if xy_dE_rgb:
        _parse_rgb(readings, ctx, xy_dE_rgb)
    if white_xy_dE:
        readings.labels["white_point"] = _point_label(white_xy_dE, white_xy_target)
    if black_xy_dE:
        readings.labels["black_point"] = _point_label(black_xy_dE, black_xy_target)

    if (current_br or current_bl or xy_dE_rgb) and ctx.ctrltype != "check_all":
        readings.reading_event = True
        readings.indicator = indicator

    if "Press 1 .. 7" in txt or "8) Exit" in txt:
        readings.phase = "menu"
    elif "initial measurements" in txt or "check measurements" in txt:
        readings.phase = "measuring"

    return readings


def _parse_luminance(
    readings: AdjustmentReadings, ctx: AdjustmentContext, current: float
) -> None:
    """Fill the ``L`` gauge and the luminance read-out from a current reading."""
    initial_br = ctx.initial_br
    if ctx.ctrltype in ("rgb_gain", "luminance", "check_all"):
        target_br = ctx.target_br
    else:
        target_br = None
    if ctx.ctrltype == "rgb_gain" and initial_br:
        initial_br = ["Initial", *initial_br[1:]]
    compare_br = target_br or initial_br or ["Initial", current]
    lstr = compare_br[0].lower()
    percent = 100.0 / compare_br[1] if compare_br[1] else 100.0
    l_diff = current - compare_br[1]
    readings.gauges["L"] = min(max(round(50 + l_diff * percent), 1), 100)
    in_tolerance = lstr == "target" and abs(l_diff) * percent <= 1
    if initial_br or target_br:
        label = (
            f"{lang.getstr(lstr)} {compare_br[1]:.2f} {CD_M2}\n"
            f"{lang.getstr('current')} {current:.2f} {CD_M2} "
            f"({_sign(l_diff)}{abs(l_diff) * percent:.2f}%)"
        )
    else:
        label = f"{lang.getstr('current')} {current:.2f} {CD_M2}"
    readings.labels["luminance"] = MetricLabel(label, in_tolerance)


def _parse_black_level(
    readings: AdjustmentReadings, ctx: AdjustmentContext, current_bl: float
) -> None:
    """Fill the black-level read-out (check-all page, from a Near Black reading)."""
    target_bl = ctx.target_bl or ctx.initial_br
    if target_bl:
        percent = 100.0 / target_bl[1]
        l_diff = current_bl - target_bl[1]
        label = (
            f"{lang.getstr('target')} {target_bl[1]:.2f} {CD_M2}\n"
            f"{lang.getstr('current')} {current_bl:.2f} {CD_M2} "
            f"({_sign(l_diff)}{abs(l_diff) * percent:.2f}%)"
        )
        in_tolerance = abs(l_diff) * percent <= 1
    else:
        label = f"{lang.getstr('current')} {current_bl:.2f} {CD_M2}"
        in_tolerance = False
    readings.labels["black_level"] = MetricLabel(label, in_tolerance)


def _parse_rgb(
    readings: AdjustmentReadings, ctx: AdjustmentContext, match: re.Match
) -> None:
    """Fill the R/G/B gauges and the RGB read-out from an ``x y DE R G B`` line."""
    groups = match.groups()
    x, y, vdt, dE = _xy_vt_de(groups)
    for name, group in (("R", groups[4]), ("G", groups[5]), ("B", groups[6])):
        value = round(50 - (group.count("+") - group.count("-")) * dE)
        readings.gauges[name] = min(max(value, 1), 100)
    label = (
        f"{lang.getstr('current')} x {x:.4f} y {y:.4f} {vdt} {dE:.1f} {DELTA_E}"
    ).replace("  ", " ")
    initial_br = ctx.initial_br
    if initial_br and len(initial_br) > 3:
        ix, iy, ivdt, idE = _xy_vt_de(initial_br[2:])
        label = (
            f"{lang.getstr(initial_br[0].lower())} "
            f"x {ix:.4f} y {iy:.4f} {ivdt} {idE:.1f} {DELTA_E}\n"
        ).replace("  ", " ") + label
    readings.labels["rgb"] = MetricLabel(label, abs(dE) <= 1)


def _point_label(match: re.Match, target_match: re.Match | None) -> MetricLabel:
    """Build a white / black point read-out (current line + optional target)."""
    x, y, vdt, dE = _xy_vt_de(match.groups())
    label = (
        f"{lang.getstr('current')} x {x:.4f} y {y:.4f} {vdt} {dE:.1f} {DELTA_E}"
    ).replace("  ", " ")
    if target_match:
        tx, ty, _tvdt, _tdE = _xy_vt_de(target_match.groups())
        label = (f"{lang.getstr('target')} x {tx:.4f} y {ty:.4f}\n").replace(
            "  ", " "
        ) + label
    return MetricLabel(label, abs(dE) <= 1)
