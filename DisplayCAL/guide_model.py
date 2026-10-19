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
SCAN_FAILED = "scan_failed"


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
    scan_failed: bool = False,
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
    if scan_failed:
        return Readiness(
            SCAN_FAILED,
            "guide.ready.scan_failed",
            (
                "guide.action.rescan",
                "guide.action.reconnect",
                "guide.action.check_permission",
            ),
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
    #: No preset at all: the guided flow runs on whatever the advanced settings
    #: hold, so moving between the two modes never overwrites them.
    Goal("current", "", "guide.goal.current", "guide.goal.current.info"),
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
    if goal is None or not goal.preset:
        return None
    for path in presets:
        if os.path.splitext(os.path.basename(path))[0] == goal.preset:
            return path
    return None


# --- one configuration for both modes --------------------------------------

#: Settings that define *what the run does* (objective, target, profile type,
#: patch chart, instrument correction). The guided flow remembers them when a
#: preset is loaded so it can say, never silently, that they were changed.
OBJECTIVE_PREFIXES = (
    "calibration.",
    "whitepoint",
    "trc",
    "testchart.",
    "measurement_mode",
    "observer",
    "colorimeter_correction_matrix_file",
    "profile.type",
    "profile.quality",
    "profile.black_point_compensation",
    "gamap",
)


def objective_keys(all_keys) -> list[str]:
    """The configuration keys that define the objective (no backups)."""
    return sorted(
        k
        for k in all_keys
        if k.startswith(OBJECTIVE_PREFIXES) and not k.endswith(".backup")
    )


def objective_changes(before: dict, after: dict) -> list[str]:
    """Keys whose values differ between two snapshots."""
    return [k for k in sorted(set(before) | set(after)) if before.get(k) != after.get(k)]


# --- preparation ------------------------------------------------------------

GROUP_MONITOR = "monitor"
GROUP_ROOM = "room"
GROUP_INSTRUMENT = "instrument"
GROUP_RUN = "run"


@dataclass(frozen=True)
class PrepItem:
    """One preparation item: a visible action plus an expandable "why"."""

    key: str
    group: str
    #: Required items gate the start; recommended ones are advice only.
    required: bool
    title_key: str
    #: One-line action, always visible (the essential step is never hidden).
    action_key: str
    #: Longer explanation, expandable.
    detail_key: str
    #: Keys of :data:`DisplayCAL.guide_sources.SOURCES` behind the advice.
    sources: tuple[str, ...] = ()


#: Vendors' own warm-up figures, shown *as that vendor's recommendation* and
#: never as a universal rule. Only documents actually read are listed.
VENDOR_WARMUP: dict[str, tuple[int, str]] = {
    # placement variant -> (minutes, source key)
    "spyder_x": (30, "datacolor_spyderx"),
}


def build_preparation(
    goal_key: str | None, placement_variant: str = "generic"
) -> list[PrepItem]:
    """Return the preparation checklist for a goal and instrument variant.

    The checklist is contextual (the room-light advice follows the goal) but
    never pre-confirmed: every item starts unconfirmed and only the user can
    confirm it.
    """
    goal = (
        goal_key if goal_key in _GOALS_BY_KEY and goal_key != "current" else "default"
    )
    warm_sources = ["argyll_dispcal", "displaycal"]
    if placement_variant in VENDOR_WARMUP:
        warm_sources.append(VENDOR_WARMUP[placement_variant][1])
    return [
        PrepItem(
            "stabilize",
            GROUP_MONITOR,
            True,
            "guide.prep.stabilize",
            "guide.prep.stabilize.action",
            "guide.prep.stabilize.info",
            tuple(warm_sources),
        ),
        PrepItem(
            "settings",
            GROUP_MONITOR,
            True,
            "guide.prep.settings",
            "guide.prep.settings.action",
            "guide.prep.settings.info",
            ("datacolor_spyderx",),
        ),
        PrepItem(
            "room",
            GROUP_ROOM,
            False,
            "guide.prep.room",
            f"guide.prep.room.{goal}",
            "guide.prep.room.info",
            ("datacolor_spyderx", "argyll_dispcal", "displaycal", "calibrite_qsg"),
        ),
        PrepItem(
            "instrument",
            GROUP_INSTRUMENT,
            True,
            "guide.prep.instrument",
            "guide.prep.instrument.action",
            "guide.prep.instrument.info",
            ("datacolor_spyderx",),
        ),
        PrepItem(
            "run",
            GROUP_RUN,
            True,
            "guide.prep.run",
            "guide.prep.run.action",
            "guide.prep.run.info",
        ),
    ]


@dataclass
class PrepState:
    """Which preparation items the user has confirmed (session-only).

    Nothing is ever confirmed automatically: warming up, lighting and
    placement are facts the application cannot observe.
    """

    items: list[PrepItem] = field(default_factory=lambda: build_preparation(None))
    done: set[str] = field(default_factory=set)

    def set_items(self, items: list[PrepItem]) -> None:
        """Replace the checklist (e.g. after the goal changed), keeping ticks."""
        self.items = items
        self.done &= {i.key for i in items}

    def toggle(self, key: str, value: bool) -> None:
        """Mark an item confirmed or not."""
        (self.done.add if value else self.done.discard)(key)

    def required_missing(self) -> list[str]:
        """Keys of required items not yet confirmed."""
        return [i.key for i in self.items if i.required and i.key not in self.done]

    @property
    def complete(self) -> bool:
        """Whether every required item is confirmed."""
        return not self.required_missing()


# --- states -----------------------------------------------------------------

DETECTED = "detected"  # reported by the system, not touched by the user
CONFIRMED = "confirmed"  # the user said so
UNVERIFIED = "unverified"  # nobody can vouch for it
BLOCKING = "blocking"  # prevents the measurement


@dataclass(frozen=True)
class StateLine:
    """A labelled fact with the *kind* of evidence behind it."""

    label_key: str
    value: str
    state: str


def start_summary(
    *,
    monitor: str | None,
    instrument: str | None,
    model: str | None,
    model_needs_choice: bool,
    correction: str,
    goal_title: str | None,
    prep: PrepState,
    readiness: Readiness,
) -> list[StateLine]:
    """Facts shown right before starting, each with its kind of evidence."""
    lines = [
        StateLine(
            "guide.sum.monitor",
            monitor or "—",
            DETECTED if monitor else BLOCKING,
        ),
        StateLine(
            "guide.sum.instrument",
            instrument or "—",
            DETECTED if instrument else BLOCKING,
        ),
    ]
    if model or model_needs_choice:
        lines.append(
            StateLine(
                "guide.sum.model",
                model or "—",
                CONFIRMED if model else UNVERIFIED,
            )
        )
    lines.append(StateLine("guide.sum.correction", correction, DETECTED))
    lines.append(
        StateLine(
            "guide.sum.goal",
            goal_title or "—",
            CONFIRMED if goal_title else BLOCKING,
        )
    )
    missing = prep.required_missing()
    confirmed = len(prep.done)
    lines.append(
        StateLine(
            "guide.sum.prep",
            f"{confirmed}/{len(prep.items)}",
            CONFIRMED if not missing else BLOCKING,
        )
    )
    if not readiness.ok:
        lines.append(StateLine("guide.sum.engine", readiness.message_key, BLOCKING))
    return lines


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
