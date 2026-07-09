"""Toolkit-neutral logic behind the gamut-mapping ("Advanced") profile options.

wx implements this as ``GamapFrame`` (``display_cal.py``, ``xrc/gamap.xrc``): a
small standalone window opened from ``MainFrame``'s Profiling tab (the
``gamap_btn``) that configures CIECAM02 gamut mapping and B2A ("perceptual" /
"saturation" table) profile quality. This module holds the pure,
Argyll-version-gated item lists and enable/disable predicates so both the wx
window and the Qt :class:`~DisplayCAL.ui.gamap_window.GamapWindow` can share
them, and so :class:`~DisplayCAL.ui.main_window.MainWindow` can compute the
black-point-compensation checkbox's enabled state (``MainFrame.update_bpc``)
without reading gamut-mapping widget state directly.
"""

from __future__ import annotations

from DisplayCAL import config
from DisplayCAL.argyll_names import INTENTS, VIEWCONDS

#: Profile types whose gamut can be usefully remapped. Mirrors wx's
#: ``enable_gamap = getcfg("profile.type") in ("l", "x", "X")``, repeated
#: throughout ``GamapFrame``.
GAMUT_MAPPABLE_PROFILE_TYPES = ("l", "x", "X")

#: Curve+matrix profile types that also enable black-point compensation by
#: default. Mirrors ``MainFrame.update_bpc``'s ``("s", "S")`` check.
CURVE_MATRIX_PROFILE_TYPES = ("s", "S")

#: Non-display output viewing conditions (print/projector/etc.), which need a
#: confirmation before being used as the *output* condition since profiles are
#: assumed to characterize a display. Mirrors
#: ``GamapFrame.viewconds_out_nondisplay``.
VIEWCONDS_OUT_NONDISPLAY = ("pp", "pe", "pc", "pcd", "ob", "cx")


def viewcond_items(argyll_version: str) -> list[str]:
    """Return the viewing-condition codes available for ``argyll_version``.

    Mirrors ``GamapFrame.setup_language``'s ``VIEWCONDS`` loop (``pc`` needs
    Argyll >= 1.1.1, ``tv`` needs Argyll >= 1.6).

    Args:
        argyll_version (str): ``getcfg("argyll.version")``.

    Returns:
        list[str]: Viewing-condition codes, in wx's fixed display order.
    """
    return [
        v
        for v in VIEWCONDS
        if not (
            (v == "pc" and argyll_version < "1.1.1")
            or (v == "tv" and argyll_version < "1.6")
        )
    ]


def intent_items(argyll_version: str) -> list[str]:
    """Return the rendering-intent codes available for ``argyll_version``.

    Mirrors ``GamapFrame.setup_language``'s ``intents`` list (``pa`` needs
    Argyll >= 1.3.3, ``lp`` needs Argyll >= 1.8.3).

    Args:
        argyll_version (str): ``getcfg("argyll.version")``.

    Returns:
        list[str]: Rendering-intent codes, in wx's fixed display order.
    """
    items = list(INTENTS)
    if argyll_version < "1.3.3":
        items.remove("pa")
    if argyll_version < "1.8.3":
        items.remove("lp")
    return items


def default_intent_items() -> list[str]:
    """Return the default-rendering-intent combo's codes.

    Returns:
        list[str]: ``config.VALID_VALUES["gamap_default_intent"]``.
    """
    return list(config.VALID_VALUES["gamap_default_intent"])


def b2a_hires_size_items() -> list[int]:
    """Return the B2A hi-res size combo's codes.

    Returns:
        list[int]: ``config.VALID_VALUES["profile.b2a.hires.size"]`` (``-1``
        stands for "auto").
    """
    return list(config.VALID_VALUES["profile.b2a.hires.size"])


def gamap_enabled(profile_type: str) -> bool:
    """Return whether gamut-mapping controls apply to ``profile_type``.

    Mirrors wx's ``enable_gamap`` / ``enable_b2a_extra``, used throughout
    ``GamapFrame`` (they are always the same check).

    Args:
        profile_type (str): ``getcfg("profile.type")``.

    Returns:
        bool: Whether the profile type is LUT-based (``l``/``x``/``X``).
    """
    return profile_type in GAMUT_MAPPABLE_PROFILE_TYPES


def compute_bpc_enabled(
    profile_type: str,
    b2a_hires: bool,
    quality_b2a: str | None,
    enable_profile: bool = True,
) -> bool:
    """Return whether black-point compensation should be enabled.

    Faithful port of ``MainFrame.update_bpc``'s ``enable_bpc`` predicate.

    Args:
        profile_type (str): ``getcfg("profile.type")``.
        b2a_hires (bool): ``getcfg("profile.b2a.hires")``.
        quality_b2a (str | None): ``getcfg("profile.quality.b2a")``.
        enable_profile (bool): Extra caller-supplied gate (wx's
            ``update_bpc(enable_profile=...)`` parameter), ANDed in.

    Returns:
        bool: Whether the black-point-compensation checkbox should be enabled.
    """
    return (
        profile_type in CURVE_MATRIX_PROFILE_TYPES
        or (
            profile_type in GAMUT_MAPPABLE_PROFILE_TYPES
            and (b2a_hires or quality_b2a in ("l", "n"))
        )
    ) and enable_profile
