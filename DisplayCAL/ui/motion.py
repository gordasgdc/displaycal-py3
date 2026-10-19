"""Operating-system "reduce motion" preference.

The placement animation must not play automatically for users who asked their
system for less motion. Detection is best-effort and conservative: when the
preference cannot be read, motion is treated as *allowed* only if no explicit
override says otherwise (``DISPLAYCAL_REDUCE_MOTION=1`` forces reduced motion,
``=0`` forces animation).
"""

from __future__ import annotations

import os
import subprocess
import sys


def _macos() -> bool | None:
    try:
        out = subprocess.run(  # noqa: S603
            ["/usr/bin/defaults", "read", "com.apple.universalaccess", "reduceMotion"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = out.stdout.strip()
    if value in ("1", "0"):
        return value == "1"
    return None


def _windows() -> bool | None:
    try:
        import ctypes

        flag = ctypes.c_int(1)
        # SPI_GETCLIENTAREAANIMATION = 0x1042
        ok = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
            0x1042, 0, ctypes.byref(flag), 0
        )
    except (AttributeError, OSError, ImportError):
        return None
    return (not flag.value) if ok else None


def prefers_reduced_motion() -> bool:
    """Return ``True`` when the user (or system) asked for reduced motion."""
    override = os.environ.get("DISPLAYCAL_REDUCE_MOTION")
    if override in ("0", "1"):
        return override == "1"
    if sys.platform == "darwin":
        value = _macos()
    elif sys.platform == "win32":
        value = _windows()
    else:
        value = None
    return bool(value)
