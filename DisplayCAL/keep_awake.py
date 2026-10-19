"""Prevent idle sleep for the duration of a measurement session, nothing more.

Uses the platform's own mechanism and releases it when the session ends or the
application exits; no power setting is ever changed:

* macOS: ``caffeinate -d -i -w <our pid>`` (the system tool; it also exits by
  itself if the application dies, so a crash cannot leave the Mac awake).
* Windows: ``SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED |
  ES_DISPLAY_REQUIRED)`` from a dedicated thread that clears it on release.
* Other systems: not handled here (the worker has its own session inhibitor).

What this *cannot* prevent is reported in :data:`NOT_PREVENTED` so the user can be
told honestly: closing the lid, choosing Sleep, the power button, a low battery,
locking the screen or switching user. If the display path is interrupted the
measurement may not continue; nothing here promises that it does.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass

#: Language keys of the things the user must still keep in mind.
NOT_PREVENTED = (
    "awake.not.lid",
    "awake.not.manual_sleep",
    "awake.not.lock",
    "awake.not.battery",
)

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


@dataclass
class AwakeStatus:
    """Outcome of an acquire attempt."""

    active: bool
    method: str
    error: str | None = None


class KeepAwake:
    """Hold the system (and display) awake while a session runs."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.status = AwakeStatus(False, "none")

    @property
    def active(self) -> bool:
        """Whether sleep prevention is currently held."""
        return self.status.active

    def acquire(self) -> AwakeStatus:
        """Start preventing idle sleep (idempotent)."""
        if self.status.active:
            return self.status
        if sys.platform == "darwin":
            self.status = self._acquire_macos()
        elif sys.platform == "win32":
            self.status = self._acquire_windows()
        else:
            self.status = AwakeStatus(False, "unsupported")
        return self.status

    def release(self) -> None:
        """Stop preventing sleep and clean up (idempotent)."""
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except (OSError, subprocess.SubprocessError):
                pass
            self._proc = None
        if self._thread is not None:
            self._stop.set()
            self._thread.join(timeout=3)
            self._thread = None
        self.status = AwakeStatus(False, "none")

    # -- platforms --------------------------------------------------------
    def _acquire_macos(self) -> AwakeStatus:
        exe = shutil.which("caffeinate") or "/usr/bin/caffeinate"
        try:
            self._proc = subprocess.Popen(  # noqa: S603
                [exe, "-d", "-i", "-w", str(os.getpid())],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            return AwakeStatus(False, "caffeinate", str(exc))
        return AwakeStatus(True, "caffeinate")

    def _acquire_windows(self) -> AwakeStatus:
        try:
            import ctypes

            func = ctypes.windll.kernel32.SetThreadExecutionState  # type: ignore[attr-defined]
        except (AttributeError, OSError) as exc:
            return AwakeStatus(False, "SetThreadExecutionState", str(exc))
        self._stop.clear()
        ready = threading.Event()
        result: list[int] = []

        def hold() -> None:
            result.append(
                func(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
            )
            ready.set()
            self._stop.wait()
            func(ES_CONTINUOUS)  # clear: back to the user's own settings

        self._thread = threading.Thread(target=hold, name="keep-awake", daemon=True)
        self._thread.start()
        ready.wait(2)
        if not result or result[0] == 0:
            self._stop.set()
            return AwakeStatus(False, "SetThreadExecutionState", "call failed")
        return AwakeStatus(True, "SetThreadExecutionState")
