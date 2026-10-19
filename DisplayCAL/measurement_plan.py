"""Facts behind the "Measurement plan" shown before a run (no colour maths)."""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Profile type letters (``profile.type``) in the order they are explained.
PROFILE_TYPES = ("g", "G", "s", "S", "x", "X", "l")
#: Selectable block sizes (the MAXIMUM patches in a block, not the chart total);
#: 0 means one single run. Any other positive size is accepted by the runner.
BLOCK_CHOICES = (0, 100, 250, 500, 1000, 2000)
#: From this estimated duration (hours) blocks are recommended, if available.
RECOMMEND_FROM_HOURS = 1.0


def type_keys(letter: str) -> tuple[str, str]:
    """Language keys of the purpose/compatibility text and the cost text."""
    return f"plan.type.{letter}.use", f"plan.type.{letter}.cost"


def recommend_block_size(
    patches: int, hours: float | None, supported: bool, current: int = 0
) -> int | None:
    """Block size worth recommending, or ``None`` when no advice applies.

    Only for runs estimated at an hour or more (or of unknown but large size),
    only when the instrument supports blocks, and only if blocks would
    actually split the chart.
    """
    if not supported or current:
        return None
    long_run = (hours is not None and hours >= RECOMMEND_FROM_HOURS) or (
        hours is None and patches >= 1500
    )
    if not long_run:
        return None
    return 500 if patches > 500 * 1.2 else None


def hours_text(hours: float | None) -> str:
    """``7 h 30 min`` style text for an estimate, ``""`` when unknown."""
    if hours is None:
        return ""
    total_min = round(hours * 60)
    if total_min < 1:
        return "< 1 min"
    h, m = divmod(total_min, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


@dataclass(frozen=True)
class Plan:
    """What a run will do, in numbers; the runner uses the very same function.

    ``total`` is the chart's patch count. ``block_size`` is the configured
    maximum per block (0 = one run). ``per_block`` is the largest block really
    produced (patches of the chart, without the repeated reference white).
    ``readings`` counts what the instrument measures: the chart plus one extra
    white per block after the first.
    """

    total: int
    block_size: int
    blocks: int
    per_block: int
    extra_white: int

    @property
    def split(self) -> bool:
        return self.blocks > 1

    @property
    def readings(self) -> int:
        return self.total + self.extra_white


def make_plan(total: int, block_size: int) -> Plan:
    """The plan for a chart of ``total`` patches (one of them the white).

    Mirrors :func:`DisplayCAL.measurement_blocks.split_ti1`, which spreads the
    non-white patches evenly over ``plan_blocks`` blocks and adds the white to
    each; a chart this function and the runner disagree on is a bug (tested).
    """
    from DisplayCAL import measurement_blocks

    total = max(int(total), 0)
    others = max(total - 1, 0)
    n = measurement_blocks.plan_blocks(others, int(block_size or 0)) if others else 1
    per = -(-others // n) if others else 0
    return Plan(total, int(block_size or 0), n, per, n - 1)


def count_text(n: int, code: str) -> str:
    """``11.000`` / ``11,000`` with the thousands separator of the language."""
    sep = "," if code == "en" else "."
    return f"{int(n):,}".replace(",", sep)


@dataclass(frozen=True)
class Speed:
    """Seconds per reading with the spread seen in earlier runs (or a guess)."""

    typical: float
    low: float
    high: float
    observed: bool  # False: derived from instrument specification, not measured


def seconds_text(seconds: float, code: str = "en") -> str:
    return hours_text(seconds / 3600.0)


def time_range_text(plan: Plan, speed: Speed | None, restart_s: float = 0.0) -> str:
    """``about 6 h 10 min (5 h 40 min – 6 h 50 min)``; ``""`` without a speed."""
    if speed is None or not plan.readings:
        return ""
    extra = restart_s * plan.blocks
    mid = speed.typical * plan.readings + extra
    if not speed.observed or speed.low >= speed.high:
        return hours_text(mid / 3600.0)
    lo = speed.low * plan.readings + extra
    hi = speed.high * plan.readings + extra
    return f"{hours_text(mid / 3600.0)} ({hours_text(lo / 3600.0)} – {hours_text(hi / 3600.0)})"
