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
        if goal.preset:  # "current" deliberately loads no preset
            assert gm.preset_path(goal.key, presets), goal.key


def test_prep_required_items_gate_completion():
    st = gm.PrepState()
    assert not st.complete
    for item in st.items:
        if item.required:
            st.toggle(item.key, True)
    assert st.complete
    st.toggle("run", False)
    assert st.required_missing() == ["run"]


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
    for goal in [g.key for g in gm.GOALS] + [None]:
        for variant in ("generic", "i1d3", "spyder_x"):
            for p in gm.build_preparation(goal, variant):
                keys |= {p.title_key, p.action_key, p.detail_key}
    for a, b in gm.CONCEPTS:
        keys |= {a, b}
    keys |= set(gm.LIMITS)
    from DisplayCAL import profile_verify as pv

    keys |= {f"guide.verify.{x}" for x in (pv.MATCH, pv.MISMATCH, pv.NONE_ACTIVE, pv.UNREADABLE)}
    keys.add("guide.ready.scan_failed")
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


def test_every_guide_key_used_by_the_panel_exists_in_ro_en_es():
    import re

    import yaml

    here = os.path.dirname(os.path.dirname(__file__))
    src = open(os.path.join(here, "DisplayCAL", "ui", "guide_panel.py"), encoding="utf-8").read()
    keys = set(re.findall(r'_tr\(\s*"(guide\.[a-z0-9_.]+)"', src))
    keys |= {f"guide.step.{i}" for i in range(1, 6)}
    keys |= {f"guide.s4.stage.{k}" for k in ("adjust", "calibrate", "profile", "build")}
    keys |= {f"guide.place.kind.{k}" for k in ("colorimeter", "spectro_puck", "spectro_pen", "other")}
    from DisplayCAL import instrument_catalog as ic

    keys |= {f"guide.pl.step.{x}" for x in ("calibrate", "face", "diffuser", "cover", "cable", "contact", "tilt", "position")}
    keys |= {f"guide.pl.generic.{x}" for x in ("calibrate", "face", "contact", "position")}
    for model, (variant, steps, _src, acc) in ic.VERIFIED_MODELS.items():
        keys |= {f"guide.pl.{variant}.{x}" for x in steps}
        keys |= {f"guide.acc.{a}" for a in acc}
    keys |= {
        "guide.pl.prev", "guide.pl.next", "guide.pl.play", "guide.pl.pause",
        "guide.pl.canvas_desc", "guide.pl.reduced_note", "guide.pl.choose_model",
        "guide.pl.verified_note", "guide.pl.unverified_note", "guide.pl.title",
    }
    for st in ("detected", "confirmed", "unverified", "blocking"):
        keys.add(f"guide.state.{st}")
    for k in ("monitor", "instrument", "model", "correction", "goal", "prep", "engine"):
        keys.add(f"guide.sum.{k}")
    for g in ("monitor", "room", "instrument", "run"):
        keys.add(f"guide.prep.group.{g}")
    keys |= {"guide.prep.vendor_warmup", "guide.prep.why", "guide.prep.sources"} | {
        f"guide.prep.timer.{x}" for x in ("label", "minutes", "start", "stop", "running", "done", "note")
    }
    keys.add("guide.place.generic")
    for code in ("en", "ro", "es"):
        with open(os.path.join(here, "DisplayCAL", "lang", f"{code}.yaml"), encoding="utf-8") as f:
            d = yaml.safe_load(f)
        missing = sorted(k for k in keys if k not in d)
        assert not missing, (code, missing)


def test_current_settings_goal_loads_no_preset():
    assert gm.goal_by_key("current") is not None
    assert gm.preset_path("current", ["/x/photo.icc", "/x/video.icc"]) is None


def test_objective_changes_are_listed_never_hidden():
    keys = gm.objective_keys(
        ["trc", "trc.backup", "whitepoint.colortemp", "testchart.file", "lang", "position.x"]
    )
    assert keys == ["testchart.file", "trc", "whitepoint.colortemp"]
    assert gm.objective_changes({"trc": 2.2, "a": 1}, {"trc": 2.4, "a": 1}) == ["trc"]
