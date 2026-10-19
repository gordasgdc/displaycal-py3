"""Tests for the guided-flow state logic (no Qt, no display needed)."""

import glob
import os

from DisplayCAL import guide_model as gm


def test_readiness_order_explains_root_cause_first():
    assert (
        gm.compute_readiness(argyll_found=False, displays=[], instruments=[]).status
        == gm.NO_ARGYLL
    )
    assert (
        gm.compute_readiness(argyll_found=True, displays=[], instruments=["x"]).status
        == gm.NO_DISPLAY
    )
    r = gm.compute_readiness(argyll_found=True, displays=["d"], instruments=[])
    assert r.status == gm.NO_INSTRUMENT
    assert "guide.action.check_permission" in r.action_keys
    assert gm.compute_readiness(argyll_found=True, displays=["d"], instruments=["i"]).ok


def test_busy_wins():
    assert (
        gm.compute_readiness(
            argyll_found=False, displays=[], instruments=[], busy=True
        ).status
        == gm.BUSY
    )


def test_success_is_not_reported_without_both_devices():
    for d, i in (([], ["i"]), (["d"], [])):
        assert not gm.compute_readiness(argyll_found=True, displays=d, instruments=i).ok


def test_suggest_goal_only_for_builtin():
    assert gm.suggest_goal("Color LCD, at 0, 0, width 1512, height 982") == "laptop"
    assert gm.suggest_goal("DELL U2723QE, at 0, 0") is None
    assert gm.suggest_goal(None) is None


def test_every_goal_resolves_to_a_bundled_preset():
    here = os.path.dirname(os.path.dirname(__file__))
    presets = glob.glob(os.path.join(here, "DisplayCAL", "presets", "*.icc"))
    assert presets
    for goal in gm.GOALS:
        assert gm.preset_path(goal.key, presets), goal.key


def test_prep_required_items_gate_completion():
    st = gm.PrepState()
    assert not st.complete
    for item in gm.PREPARATION:
        if item.required:
            st.toggle(item.key, True)
    assert st.complete
    st.toggle("probe", False)
    assert st.required_missing() == ["probe"]


def test_all_guide_keys_exist_in_english_and_in_ro_es():
    import yaml

    here = os.path.dirname(os.path.dirname(__file__))
    langs = {}
    for code in ("en", "ro", "es"):
        with open(
            os.path.join(here, "DisplayCAL", "lang", f"{code}.yaml"), encoding="utf-8"
        ) as f:
            langs[code] = yaml.safe_load(f)
    keys = set()
    for g in gm.GOALS:
        keys |= {g.title_key, g.summary_key}
    for p in gm.PREPARATION:
        keys |= {p.title_key, p.detail_key}
    for a, b in gm.CONCEPTS:
        keys |= {a, b}
    keys |= set(gm.LIMITS)
    for r in (
        gm.compute_readiness(argyll_found=False, displays=[], instruments=[]),
        gm.compute_readiness(argyll_found=True, displays=[], instruments=[]),
        gm.compute_readiness(argyll_found=True, displays=["d"], instruments=[]),
        gm.compute_readiness(argyll_found=True, displays=["d"], instruments=["i"]),
        gm.compute_readiness(
            argyll_found=True, displays=["d"], instruments=["i"], busy=True
        ),
    ):
        keys.add(r.message_key)
        keys |= set(r.action_keys)
    missing = {c: sorted(k for k in keys if k not in langs[c]) for c in langs}
    assert not any(missing.values()), missing
