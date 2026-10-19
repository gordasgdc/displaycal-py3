"""Facts behind the "Measurement plan" shown before a run (no colour maths)."""

from __future__ import annotations

#: Profile type letters (``profile.type``) in the order they are explained.
PROFILE_TYPES = ("g", "G", "s", "S", "x", "X", "l")
#: Selectable block sizes; 0 means one single run.
BLOCK_CHOICES = (0, 250, 500, 1000)
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
    h, m = divmod(total_min, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"
