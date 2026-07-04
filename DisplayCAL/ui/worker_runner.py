"""Qt worker execution layer (Stage 5, worker execution).

Home of the Qt-side driver that runs :class:`DisplayCAL.worker.Worker`
operations for the Qt main window, replacing the wx-event-loop-bound
``Worker.start()`` path (``delayedresult`` threading, ``wx.CallAfter``, the wx
``ProgressDialog`` and its ``wx.Timer``-driven ``progress_handler``). See
``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 5).

This first piece is the toolkit-neutral progress parser lifted out of
``Worker.progress_handler`` (worker.py:15022). The wx handler cannot be reused
under Qt because it is interleaved with ``wx.GetApp()`` / ``wx.CallAfter`` /
``DisplayAdjustmentFrame`` calls that require a running wx app; only the
numeric percentage extraction is toolkit-neutral, and that is what the Qt
progress poll needs. Keeping it here as a pure function makes it unit-testable
without a display and lets the wx handler delegate to it later.
"""

from __future__ import annotations

import contextlib
import re

# Argyll warnings look like ``dispread: Warning - ...``; they must not be parsed
# as progress and are stripped before matching, matching the wx handler.
_WARNING_RE = re.compile(r"\D+: Warning -.*")
_PERCENT_RE = re.compile(r"\s*\d+%\s*(?:[^=]+)?$")
_PATCH_RE = re.compile(r"Patch \d+ of \d+", re.IGNORECASE)
_ADDED_RE = re.compile(r"Added \d+/\d+", re.IGNORECASE)
_ITERATION_RE = re.compile(r"It (\d+):")

# targen refines over at most this many iterations.
_TARGEN_ITERATIONS = 20.0


def parse_progress(msg: str, lastmsg: str) -> tuple[float | None, str]:
    """Extract a completion percentage from Argyll command output.

    Toolkit-neutral port of the parsing in ``Worker.progress_handler``. Handles
    the four shapes Argyll emits:

    * ``NN%`` download / colprof progress,
    * ``Patch N of M`` dispcal / dispread measurement progress,
    * ``Added N/M`` targen patch generation,
    * ``It N:`` targen optimisation iterations (which also clears ``lastmsg``).

    Args:
        msg (str): The recent accumulated output (``Worker.recent``).
        lastmsg (str): The most recent single line (``Worker.lastmsg``).

    Returns:
        tuple[float | None, str]: The percentage in ``0..100`` (or ``None`` when
        no progress could be parsed) and the possibly-cleared ``lastmsg``.
    """
    msg = _WARNING_RE.sub("", msg)
    lastmsg = _WARNING_RE.sub("", lastmsg).strip()
    percentage: float | None = None
    # Filter for '=' (via the regex) so a 1% reading during calibration-check
    # measurements doesn't get treated as command progress.
    if _PERCENT_RE.match(lastmsg):
        with contextlib.suppress(ValueError):
            percentage = int(lastmsg.split("%")[0])
    elif _PATCH_RE.match(lastmsg):
        components = lastmsg.split()
        with contextlib.suppress(ValueError, IndexError):
            start = float(components[1])
            end = float(components[3])
            percentage = max(start - 1, 0) / end * 100
    elif _ADDED_RE.match(lastmsg):
        components = lastmsg.lower().replace("added ", "").split("/")
        with contextlib.suppress(ValueError, IndexError):
            start = float(components[0])
            end = float(components[1])
            percentage = start / end * 100
    else:
        iteration = _ITERATION_RE.search(msg)
        if iteration:
            with contextlib.suppress(ValueError):
                start = float(iteration.groups()[0])
                percentage = min(start, _TARGEN_ITERATIONS) / _TARGEN_ITERATIONS * 100
                lastmsg = ""
    if percentage is not None:
        percentage = max(min(percentage, 100), 0)
    return percentage, lastmsg
