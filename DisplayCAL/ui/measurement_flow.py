"""Measurement-flow orchestration — toolkit-neutral engine.

The wx ``display_cal.MainFrame`` drives every calibrate/measure/profile run
through a small cluster of methods that decide *how* the measurement area is
presented and *what* happens when it closes: ``setup_measurement``,
``setup_patterngenerator``, the ``measureframe`` subprocess trio
(``start_measureframe_subprocess`` / ``measureframe_subprocess`` /
``measureframe_consumer``), ``setup_observer_ctrl`` and the
``set_pending_function`` / ``call_pending_function`` pair.

The load-bearing part of that cluster is toolkit-neutral: it is decision logic
over ``config`` / platform / instrument facts, subprocess plumbing and a small
pending-function state machine. This module extracts exactly that part so both
the still-shipping wx ``MainFrame`` and the forthcoming Qt main window can drive
the same engine. See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 2).

What is intentionally *not* here: the wx pattern-generator setup **dialogs**
(the Prisma host prompt, the madTPG / Resolve / Chromecast wait dialogs). Those
are Pile-2 wx widget glue that gets rebuilt natively when the Qt main window
lands; :func:`patterngenerator_kind` captures only the toolkit-neutral choice of
*which* of those flows a given display needs, so the caller can branch. The
threading around :func:`run_measureframe_subprocess` is likewise left to the
caller (``QThread`` in Qt, ``delayedresult`` in wx).
"""

from __future__ import annotations

import enum
import subprocess as sp
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import EXE, ISEXE, PYDIR, getcfg
from DisplayCAL.util_str import safe_str

if TYPE_CHECKING:
    from collections.abc import Callable


# Exit codes the measure-frame subprocess reports back to the parent. They are
# the contract with :func:`DisplayCAL.ui.measure_frame.main`, mirroring the wx
# ``wx_measure_frame`` codes so the wx and Qt frames stay interchangeable.
MEASUREFRAME_EXITCODE_MEASURE = 255  # user pressed Measure -> run pending flow
MEASUREFRAME_EXITCODE_OK = 0  # frame closed/cancelled cleanly
MEASUREFRAME_EXITCODE_FAILED = -1  # subprocess never ran (spawn failure)


class PresentationMode(enum.Enum):
    """How the measurement area should be presented for a run.

    Derived from ``MainFrame.setup_measurement``'s branch logic.
    """

    #: Virtual display (or dry run) — skip the frame, call the pending function.
    CALL_PENDING = "call_pending"
    #: Show the measure frame in-process (native window, no subprocess).
    SHOW_FRAME = "show_frame"
    #: Launch the measure frame as a separate process and await its exit code.
    SUBPROCESS = "subprocess"


def decide_presentation(
    display_name: str,
    *,
    is_virtual_display: bool,
    dry_run: bool,
    use_patternwindow: bool,
    platform: str = sys.platform,
    isexe: bool = ISEXE,
) -> PresentationMode:
    """Decide how to present the measurement area for the given display.

    This is the toolkit-neutral core of ``MainFrame.setup_measurement``.

    Args:
        display_name (str): Resolved display name (``config.get_display_name``).
        is_virtual_display (bool): Whether the display is a virtual one.
        dry_run (bool): Whether Argyll is being driven in dry-run mode.
        use_patternwindow (bool): ``worker._use_patternwindow`` — whether our
            own software patch window is driving the display (Wayland path).
        platform (str): ``sys.platform`` value (injectable for tests).
        isexe (bool): Whether running as a frozen executable.

    Returns:
        PresentationMode: The chosen presentation.
    """
    virtual_direct = (
        is_virtual_display
        and display_name not in ("Resolve", "Prisma")
        and not display_name.startswith("Chromecast ")
        and not display_name.startswith("Prisma ")
    )
    if virtual_direct or dry_run:
        return PresentationMode.CALL_PENDING
    if platform in ("darwin", "win32") or isexe or use_patternwindow:
        return PresentationMode.SHOW_FRAME
    return PresentationMode.SUBPROCESS


class PatternGeneratorKind(enum.Enum):
    """Which pattern-generator setup flow a display needs.

    Extracted from the display-name branching in
    ``MainFrame.setup_patterngenerator``. The *dialogs* for these flows are wx
    glue rebuilt in Qt later; this only names the branch.
    """

    #: A normal local display — no pattern generator setup needed.
    NONE = "none"
    #: Prisma — prompt for host / preset.
    PRISMA = "prisma"
    #: madVR / madTPG — connect (launching a local instance on Windows).
    MADVR = "madvr"
    #: Resolve / Web / Chromecast — network pattern generator, wait for connect.
    NETWORK = "network"


def patterngenerator_kind(display_name: str) -> PatternGeneratorKind:
    """Classify the pattern-generator flow a display requires.

    Args:
        display_name (str): Resolved display name (``config.get_display_name``).

    Returns:
        PatternGeneratorKind: The flow to run before measuring.
    """
    if display_name == "Prisma":
        return PatternGeneratorKind.PRISMA
    if display_name == "madVR":
        return PatternGeneratorKind.MADVR
    if display_name in ("Resolve", "Web @ localhost") or display_name.startswith(
        "Chromecast "
    ):
        return PatternGeneratorKind.NETWORK
    return PatternGeneratorKind.NONE


def build_measureframe_command(exe: str = EXE, pydir: str = PYDIR) -> list[str]:
    """Build the command that runs the Qt measure frame as a subprocess.

    Mirrors ``MainFrame.start_measureframe_subprocess``'s script, but launches
    the Qt :mod:`DisplayCAL.ui.measure_frame` rather than the wx one. The child
    exits with :attr:`DisplayCAL.ui.measure_frame.MeasureFrame.exitcode`.

    Args:
        exe (str): The Python executable to run.
        pydir (str): The package parent directory to put on ``sys.path``.

    Returns:
        list[str]: The argument vector for :class:`subprocess.Popen`.
    """
    script = (
        "import sys;"
        f"sys.path.insert(0, {pydir!r});"
        "from DisplayCAL.ui import measure_frame;"
        "sys.exit(measure_frame.main())"
    )
    return [exe, "-c", script]


def run_measureframe_subprocess(
    args: list[str],
    env: dict[str, str],
    on_start: Callable[[sp.Popen], None] | None = None,
) -> tuple[int, str]:
    """Run the measure-frame subprocess and block for its result.

    Toolkit-neutral port of ``MainFrame.measureframe_subprocess``. The caller is
    responsible for running this off the UI thread. ``on_start`` receives the
    live :class:`~subprocess.Popen` so the caller can keep a handle for
    cancellation (the wx code stashed it as ``self._measureframe_subprocess``).

    Args:
        args (list[str]): The command to run (see :func:`build_measureframe_command`).
        env (dict[str, str]): Environment for the child process.
        on_start (Callable | None): Optional callback given the ``Popen`` once
            it has been spawned.

    Returns:
        tuple[int, str]: The child's return code and its (decoded) stderr.
            The return code is :data:`MEASUREFRAME_EXITCODE_FAILED` (-1) if the
            process could not be spawned at all.
    """
    returncode = MEASUREFRAME_EXITCODE_FAILED
    stderr = ""
    try:
        process = sp.Popen(
            args,
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            env=env,
        )
    except Exception as exception:
        stderr = safe_str(exception)
    else:
        if on_start is not None:
            on_start(process)
        _stdout, stderr_bytes = process.communicate()
        returncode = process.returncode
        if stderr_bytes:
            stderr = safe_str(stderr_bytes)
    return returncode, stderr


@dataclass
class MeasureframeResult:
    """The decoded meaning of a measure-frame subprocess exit code.

    Port of the branching in ``MainFrame.measureframe_consumer``.
    """

    #: Config may have changed on disk (the subprocess actually ran).
    config_changed: bool
    #: The user pressed Measure — run the pending function.
    should_call_pending: bool
    #: Show the main window again and restore measurement mode / testchart.
    should_restore: bool
    #: A non-empty error message to surface, or ``None``.
    error_message: str | None = None


def interpret_measureframe_result(
    returncode: int, stderr: str = ""
) -> MeasureframeResult:
    """Interpret a measure-frame subprocess exit code.

    Args:
        returncode (int): The subprocess return code.
        stderr (str): The subprocess stderr, used only to build the error
            message when the run failed.

    Returns:
        MeasureframeResult: What the caller should do next.
    """
    config_changed = returncode != MEASUREFRAME_EXITCODE_FAILED
    should_call_pending = returncode == MEASUREFRAME_EXITCODE_MEASURE
    should_restore = returncode != MEASUREFRAME_EXITCODE_MEASURE
    error_message = None
    if (
        should_restore
        and returncode != MEASUREFRAME_EXITCODE_OK
        and stderr
        and stderr.strip()
    ):
        error_message = stderr.strip()
    return MeasureframeResult(
        config_changed=config_changed,
        should_call_pending=should_call_pending,
        should_restore=should_restore,
        error_message=error_message,
    )


def observer_items() -> dict[str, str]:
    """Return the ``observer value -> localized label`` map for the UI.

    Toolkit-neutral port of ``MainFrame.setup_observer_ctrl``: the choice of
    observers varies with the installed ArgyllCMS version, so it is derived from
    ``config.VALID_VALUES["observer"]``.

    Returns:
        dict[str, str]: Ordered mapping of observer key to display label.
    """
    return {
        observer: lang.getstr(f"observer.{observer}")
        for observer in config.VALID_VALUES["observer"]
    }


@dataclass
class MeasurementPlan:
    """The outcome of :meth:`MeasurementFlow.plan_measurement`."""

    #: How to present the measurement area.
    mode: PresentationMode
    #: The resolved display name the decision was made for.
    display_name: str
    #: Whether the caller should wrap up the worker before presenting.
    wrapup: bool = True


class MeasurementFlow:
    """Holds the pending measurement and stages how it is presented.

    This is the toolkit-neutral home for the ``set_pending_function`` /
    ``call_pending_function`` state machine plus the ``setup_measurement``
    decision. It does not touch any widgets: the caller pushes a *pending
    function* (the actual calibrate/measure/profile driver), asks how to present
    the frame, and later pops the pending function to run it once the user
    commits. The wx-specific bits ``call_pending_function`` still owns (hiding
    the frame, the 100 ms ``CallLater``) belong to the window layer.
    """

    def __init__(self) -> None:
        self.pending_function: Callable | None = None
        self.pending_function_args: tuple = ()
        self.pending_function_kwargs: dict = {}

    def set_pending_function(
        self,
        pending_function: Callable,
        *pending_function_args: object,
        **pending_function_kwargs: object,
    ) -> None:
        """Stage the function to run once the user commits to measuring."""
        self.pending_function = pending_function
        self.pending_function_args = pending_function_args
        self.pending_function_kwargs = pending_function_kwargs

    def clear_pending_function(self) -> None:
        """Drop any staged pending function."""
        self.pending_function = None
        self.pending_function_args = ()
        self.pending_function_kwargs = {}

    @property
    def has_pending_function(self) -> bool:
        """Whether a pending function is currently staged."""
        return self.pending_function is not None

    def take_pending_function(
        self,
    ) -> tuple[Callable | None, tuple, dict]:
        """Pop and return the staged ``(function, args, kwargs)``, clearing it.

        The caller invokes the function itself (in Qt, deferred via
        ``QTimer.singleShot(100, ...)`` to let the display settle, matching the
        wx ``CallLater``).
        """
        pending = (
            self.pending_function,
            self.pending_function_args,
            self.pending_function_kwargs,
        )
        self.clear_pending_function()
        return pending

    def plan_measurement(
        self,
        pending_function: Callable,
        *pending_function_args: object,
        use_patternwindow: bool = False,
        wrapup: bool = True,
        **pending_function_kwargs: object,
    ) -> MeasurementPlan:
        """Stage the pending function and decide how to present the frame.

        Args:
            pending_function (Callable): The measurement driver to run once the
                user commits.
            *pending_function_args: Positional args for the pending function.
            use_patternwindow (bool): ``worker._use_patternwindow``.
            wrapup (bool): Passed through on the plan so the caller knows whether
                to wrap up the worker before presenting (kept out of the pending
                kwargs, matching the wx ``pending_function_kwargs.pop``).
            **pending_function_kwargs: Keyword args for the pending function.

        Returns:
            MeasurementPlan: The presentation decision.
        """
        self.set_pending_function(
            pending_function, *pending_function_args, **pending_function_kwargs
        )
        display_name = config.get_display_name(None, True)
        mode = decide_presentation(
            display_name,
            is_virtual_display=config.is_virtual_display(),
            dry_run=bool(getcfg("dry_run")),
            use_patternwindow=use_patternwindow,
        )
        return MeasurementPlan(mode=mode, display_name=display_name, wrapup=wrapup)
