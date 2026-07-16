"""Tests for the toolkit-neutral ``DisplayCAL/gamap_settings.py`` helpers.

Covers the pieces ported from wx's ``GamapFrame`` (``display_cal.py``) that
back the Qt gamut-mapping options window and ``MainWindow``'s black-point
compensation sync. No display or QApplication is needed.
"""

from DisplayCAL import gamap_settings as gs


# -- viewcond_items -----------------------------------------------------------


def test_viewcond_items_old_argyll_excludes_pc_and_tv():
    items = gs.viewcond_items("1.0.0")
    assert "pc" not in items
    assert "tv" not in items


def test_viewcond_items_modern_argyll_includes_pc_and_tv():
    items = gs.viewcond_items("1.9.2")
    assert "pc" in items
    assert "tv" in items


def test_viewcond_items_preserves_order():
    items = gs.viewcond_items("1.9.2")
    assert items == [
        "pp",
        "pe",
        "pc",
        "mt",
        "mb",
        "md",
        "jm",
        "jd",
        "tv",
        "pcd",
        "ob",
        "cx",
    ]


# -- intent_items -------------------------------------------------------------


def test_intent_items_old_argyll_excludes_pa_and_lp():
    items = gs.intent_items("1.0.0")
    assert "pa" not in items
    assert "lp" not in items


def test_intent_items_modern_argyll_includes_pa_and_lp():
    items = gs.intent_items("1.9.2")
    assert "pa" in items
    assert "lp" in items


def test_intent_items_partial_argyll_version():
    # >= 1.3.3 (has "pa") but < 1.8.3 (no "lp" yet).
    items = gs.intent_items("1.5.0")
    assert "pa" in items
    assert "lp" not in items


# -- default_intent_items / b2a_hires_size_items ------------------------------


def test_default_intent_items_matches_valid_values():
    from DisplayCAL import config

    assert gs.default_intent_items() == config.VALID_VALUES["gamap_default_intent"]


def test_b2a_hires_size_items_matches_valid_values():
    from DisplayCAL import config

    assert (
        gs.b2a_hires_size_items() == config.VALID_VALUES["profile.b2a.hires.size"]
    )


# -- gamap_enabled ------------------------------------------------------------


def test_gamap_enabled_lut_types():
    assert gs.gamap_enabled("l")
    assert gs.gamap_enabled("x")
    assert gs.gamap_enabled("X")


def test_gamap_enabled_non_lut_types():
    assert not gs.gamap_enabled("s")
    assert not gs.gamap_enabled("S")
    assert not gs.gamap_enabled("g")
    assert not gs.gamap_enabled("G")


# -- compute_bpc_enabled -------------------------------------------------------


def test_compute_bpc_enabled_shaper_matrix_always_on():
    assert gs.compute_bpc_enabled("s", False, None)
    assert gs.compute_bpc_enabled("S", False, None)


def test_compute_bpc_enabled_lut_needs_hires_or_low_quality():
    assert not gs.compute_bpc_enabled("l", False, "h")
    assert gs.compute_bpc_enabled("l", True, "h")
    assert gs.compute_bpc_enabled("l", False, "l")
    assert gs.compute_bpc_enabled("l", False, "n")


def test_compute_bpc_enabled_gamma_only_types_always_off():
    assert not gs.compute_bpc_enabled("g", True, "l")
    assert not gs.compute_bpc_enabled("G", True, "l")


def test_compute_bpc_enabled_enable_profile_gate():
    assert not gs.compute_bpc_enabled("s", False, None, enable_profile=False)
