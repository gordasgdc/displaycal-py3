"""State and content logic of the guided calibration flow (toolkit-neutral).

The Qt view (:mod:`DisplayCAL.ui.guide_panel`) is a thin layer over this
module, so the decisions that matter -- is the setup actually ready, which
goal suits which kind of display, what must be prepared, what a finished
run really proves -- are unit-testable without a display.

Nothing here changes colour science: goals only *select one of the bundled
calibration presets* (``DisplayCAL/presets``), exactly what the "Settings"
combo does; the measurement, Argyll arguments and profile maths stay in the
existing engine.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# --- readiness --------------------------------------------------------------

READY = "ready"
NO_ARGYLL = "no_argyll"
NO_DISPLAY = "no_display"
NO_INSTRUMENT = "no_instrument"
BUSY = "busy"


@dataclass(frozen=True)
class Readiness:
    """Whether a measurement can start, and if not, why and what to do."""

    status: str
    #: lang key of a one-line summary.
    message_key: str
    #: lang keys of recovery actions, most useful first.
    action_keys: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """Whether a measurement can start."""
        return self.status == READY


def compute_readiness(
    *,
    argyll_found: bool,
    displays: list[str],
    instruments: list[str],
    busy: bool = False,
) -> Readiness:
    """Derive the readiness state from what the engine reports.

    The order is deliberate: a missing engine explains everything else, a
    missing display is a system problem, a missing instrument is the most
    common user-side problem (not plugged in, permission, driver).
    """
    if busy:
        return Readiness(BUSY, "guide.ready.busy")
    if not argyll_found:
        return Readiness(
            NO_ARGYLL,
            "guide.ready.no_argyll",
            ("guide.action.install_argyll", "guide.action.choose_argyll"),
        )
    if not displays:
        return Readiness(NO_DISPLAY, "guide.ready.no_display", ("guide.action.rescan",))
    if not instruments:
        return Readiness(
            NO_INSTRUMENT,
            "guide.ready.no_instrument",
            (
                "guide.action.reconnect",
                "guide.action.rescan",
                "guide.action.check_permission",
            ),
        )
    return Readiness(READY, "guide.ready.ok")


# --- goals ------------------------------------------------------------------


@dataclass(frozen=True)
class Goal:
    """A usage goal that maps to one bundled calibration preset."""

    key: str
    #: Basename (no extension) of the preset in ``DisplayCAL/presets``.
    preset: str
    title_key: str
    summary_key: str
    #: Whether this goal is a sensible *default suggestion* for a built-in panel.
    suggested_for_builtin: bool = False


GOALS: tuple[Goal, ...] = (
    Goal("photo", "photo", "guide.goal.photo", "guide.goal.photo.info"),
    Goal("video", "video", "guide.goal.video", "guide.goal.video.info"),
    Goal(
        "office_web",
        "office_web",
        "guide.goal.office_web",
        "guide.goal.office_web.info",
    ),
    Goal(
        "laptop",
        "laptop",
        "guide.goal.laptop",
        "guide.goal.laptop.info",
        suggested_for_builtin=True,
    ),
    Goal("srgb", "sRGB", "guide.goal.srgb", "guide.goal.srgb.info"),
    Goal("softproof", "softproof", "guide.goal.softproof", "guide.goal.softproof.info"),
)

_GOALS_BY_KEY = {g.key: g for g in GOALS}

_BUILTIN_HINTS = ("color lcd", "built-in", "builtin", "retina", "internal", "laptop")


def looks_builtin(display_name: str | None) -> bool:
    """Heuristic: does this display name look like a laptop/built-in panel?

    Used only to *suggest* a goal; the user always chooses.
    """
    name = (display_name or "").lower()
    return any(hint in name for hint in _BUILTIN_HINTS)


def suggest_goal(display_name: str | None) -> str | None:
    """Suggest a goal key for a display, or ``None`` when we should not guess.

    A built-in panel is the only case with a defensible default (portable use
    and typically a narrower gamut and no hardware controls); for an external
    monitor the intended work decides, so no goal is pre-selected.
    """
    if looks_builtin(display_name):
        return "laptop"
    return None


def goal_by_key(key: str) -> Goal | None:
    """Return the goal with this key, or ``None``."""
    return _GOALS_BY_KEY.get(key)


def preset_path(goal_key: str, presets: list[str]) -> str | None:
    """Return the bundled preset path of a goal, or ``None`` when absent."""
    goal = goal_by_key(goal_key)
    if goal is None:
        return None
    for path in presets:
        if os.path.splitext(os.path.basename(path))[0] == goal.preset:
            return path
    return None


# --- preparation ------------------------------------------------------------


@dataclass(frozen=True)
class PrepItem:
    """One preparation item shown on the preparation step."""

    key: str
    #: Required (will affect the result) vs recommended (good practice).
    required: bool
    title_key: str
    detail_key: str


PREPARATION: tuple[PrepItem, ...] = (
    PrepItem("warmup", False, "guide.prep.warmup", "guide.prep.warmup.info"),
    PrepItem("reset", True, "guide.prep.reset", "guide.prep.reset.info"),
    PrepItem("auto", True, "guide.prep.auto", "guide.prep.auto.info"),
    PrepItem("ambient", False, "guide.prep.ambient", "guide.prep.ambient.info"),
    PrepItem(
        "screensaver", True, "guide.prep.screensaver", "guide.prep.screensaver.info"
    ),
    PrepItem("probe", True, "guide.prep.probe", "guide.prep.probe.info"),
)


@dataclass
class PrepState:
    """Which preparation items the user has confirmed (session-only)."""

    done: set[str] = field(default_factory=set)

    def toggle(self, key: str, value: bool) -> None:
        """Mark an item done or not done."""
        (self.done.add if value else self.done.discard)(key)

    def required_missing(self) -> list[str]:
        """Keys of required items not yet confirmed."""
        return [i.key for i in PREPARATION if i.required and i.key not in self.done]

    @property
    def complete(self) -> bool:
        """Whether every required item is confirmed."""
        return not self.required_missing()


# --- concept clarifications -------------------------------------------------

#: What each artefact is and is not. Shown on the last step so the user does not
#: confuse them (calibration vs ICC profile vs loading curves vs 3D LUT).
CONCEPTS: tuple[tuple[str, str], ...] = (
    ("guide.concept.calibration", "guide.concept.calibration.info"),
    ("guide.concept.profile", "guide.concept.profile.info"),
    ("guide.concept.curves", "guide.concept.curves.info"),
    ("guide.concept.lut3d", "guide.concept.lut3d.info"),
)

#: Honest limits, never promises.
LIMITS: tuple[str, ...] = (
    "guide.limit.color_management",
    "guide.limit.hdr",
    "guide.limit.multi_display",
)
