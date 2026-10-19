"""How fast this instrument really measured on this computer.

The time shown before a run is an estimate from the instrument's specification.
Once real runs have completed, their own speed is a better basis: this module
keeps a short history (readings and seconds of finished blocks or runs, per
instrument) and turns it into a typical speed with the spread that was seen.
Nothing here touches measurement or colour; a missing or damaged file just
means "no history", and the specification-based estimate stays in use.
"""

from __future__ import annotations

import contextlib
import json
import os
import time

from DisplayCAL import config
from DisplayCAL.measurement_plan import Speed

KEEP = 40  # samples kept per instrument
MIN_READINGS = 20  # shorter pieces are dominated by start-up, not by speed
MIN_SAMPLES = 2  # one sample says nothing about spread


def _path() -> str:
    return os.path.join(config.CONFIG_HOME, "measured_speed.json")


def _load() -> dict:
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def record(instrument: str, readings: int, seconds: float, path: str | None = None) -> None:
    """Remember one finished block/run (never raises: this is only a hint)."""
    if not instrument or readings < MIN_READINGS or seconds <= 0:
        return
    target = path or _path()
    try:
        data = _load() if path is None else _read(path)
        rows = data.setdefault(instrument, [])
        rows.append([int(readings), round(float(seconds), 2), int(time.time())])
        data[instrument] = rows[-KEEP:]
        os.makedirs(os.path.dirname(target), exist_ok=True)
        tmp = f"{target}.tmp-{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, target)
    except (OSError, ValueError):
        with contextlib.suppress(OSError):
            os.unlink(f"{target}.tmp-{os.getpid()}")


def _read(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def observed(instrument: str, path: str | None = None) -> Speed | None:
    """Typical seconds per reading with the observed spread, or ``None``."""
    data = _read(path) if path else _load()
    per = sorted(
        s / r
        for r, s, _t in (row for row in data.get(instrument, []) if len(row) == 3)
        if r >= MIN_READINGS and s > 0
    )
    if len(per) < MIN_SAMPLES:
        return None
    mid = per[len(per) // 2] if len(per) % 2 else (per[len(per) // 2 - 1] + per[len(per) // 2]) / 2
    lo = per[max(int(len(per) * 0.1), 0)]
    hi = per[min(int(len(per) * 0.9), len(per) - 1)]
    return Speed(mid, lo, hi, True)


def specified(seconds_per_patch: float) -> Speed:
    """A speed taken from the instrument specification (no spread known)."""
    return Speed(seconds_per_patch, seconds_per_patch, seconds_per_patch, False)
