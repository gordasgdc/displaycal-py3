"""Measurement plan helpers."""

from DisplayCAL import measurement_plan as mp


def test_every_profile_type_has_texts():
    import os

    import yaml

    here = os.path.dirname(os.path.dirname(__file__))
    for code in ("en", "ro", "es"):
        with open(os.path.join(here, "DisplayCAL", "lang", f"{code}.yaml"), encoding="utf-8") as f:
            d = yaml.safe_load(f)
        for t in mp.PROFILE_TYPES:
            for key in mp.type_keys(t):
                assert key in d, (code, key)


def test_recommendation_only_for_long_supported_runs():
    assert mp.recommend_block_size(11000, 7.5, True) == 500
    assert mp.recommend_block_size(11000, 7.5, False) is None  # not supported
    assert mp.recommend_block_size(300, 0.2, True) is None  # short
    assert mp.recommend_block_size(11000, 7.5, True, current=250) is None  # chosen
    assert mp.recommend_block_size(2000, None, True) == 500  # unknown time, big chart
    assert mp.recommend_block_size(550, 1.5, True) is None  # would not split


def test_hours_text():
    assert mp.hours_text(7.5) == "7 h 30 min"
    assert mp.hours_text(0.25) == "15 min"
    assert mp.hours_text(None) == ""


# --- the plan shown is the plan executed -----------------------------------
import os
import time

import pytest

from DisplayCAL import measured_speed, measurement_blocks as mb
from test_measurement_blocks import fake_ti3, make_ti1


class _P:
    def __init__(self, path):
        self.path = path

    def write_text(self, t):
        with open(self.path, "w", encoding="latin-1") as f:
            f.write(t)


@pytest.mark.parametrize("total", [2, 50, 600, 601, 721, 722, 1200, 2501, 11140])
@pytest.mark.parametrize("size", [0, 20, 100, 250, 500, 1000, 2000])
def test_displayed_plan_equals_the_blocks_that_are_cut(tmp_path, total, size):
    ti1 = str(tmp_path / "c.ti1")
    make_ti1(_P(ti1), total)
    plan = mp.make_plan(total, size)
    blocks = mb.split_ti1(ti1, "c", size)
    assert len(blocks) == plan.blocks
    rows = [len(b.row_indices) for b in blocks]  # each includes the repeated white
    assert max(rows) - 1 == plan.per_block or plan.blocks == 1 and max(rows) == total
    assert sum(rows) == plan.readings  # total + one extra white per later block
    covered = {i for b in blocks for i in b.row_indices}
    assert len(covered) == total  # every patch of the chart, none lost, none new
    assert plan.total == total


def test_large_chart_keeps_its_total_whatever_the_block_size(tmp_path):
    """11,140 patches: split, 'measure' (stand-in ti3), merge -- nothing capped."""
    total = 11140
    ti1 = str(tmp_path / "big.ti1")
    make_ti1(_P(ti1), total)
    seen = []
    for size in (100, 250, 500, 1000, 2000, 0):
        plan = mp.make_plan(total, size)
        assert plan.total == total
        seen.append(plan.blocks)
        assert plan.readings == total + plan.blocks - 1
    assert seen == sorted(seen, reverse=True) and seen[-1] == 1
    started = time.monotonic()
    blocks = mb.split_ti1(ti1, "big", 500)
    parts = []
    for b in blocks:
        fake_ti3(b.base + ".ti1", b.base + ".ti3")
        parts.append(b.base + ".ti3")
    report = mb.merge_ti3(parts, ti1, str(tmp_path / "big.ti3"))
    assert report["patches"] == total
    assert len(mb.read_table(str(tmp_path / "big.ti3")).rows) == total
    assert time.monotonic() - started < 30  # no pathological cost at this size


def test_runner_and_screen_agree_at_the_boundary(tmp_path):
    """A chart 1 patch over 1.2x the block size: both count the same blocks."""
    for total in (600, 601, 602):
        ti1 = str(tmp_path / f"b{total}.ti1")
        make_ti1(_P(ti1), total)
        assert len(mb.split_ti1(ti1, "b", 500)) == mp.make_plan(total, 500).blocks


def test_count_and_block_wording():
    assert mp.count_text(11140, "en") == "11,140"
    assert mp.count_text(11140, "ro") == "11.140"
    assert mp.count_text(11140, "es") == "11.140"
    assert mp.count_text(950, "ro") == "950"


def test_time_range_uses_speed_and_is_empty_without_one():
    plan = mp.make_plan(1000, 500)
    assert mp.time_range_text(plan, None) == ""
    spec = measured_speed.specified(2.0)
    assert mp.time_range_text(plan, spec) == mp.hours_text(2.0 * plan.readings / 3600)
    seen = mp.Speed(2.0, 1.5, 3.0, True)
    text = mp.time_range_text(plan, seen)
    assert "(" in text and "–" in text


def test_measured_speed_needs_a_history_and_ignores_tiny_pieces(tmp_path):
    path = str(tmp_path / "speed.json")
    assert measured_speed.observed("i1 Display Pro", path) is None
    measured_speed.record("i1 Display Pro", 500, 650.0, path)
    assert measured_speed.observed("i1 Display Pro", path) is None  # one sample only
    measured_speed.record("i1 Display Pro", 5, 400.0, path)  # start-up dominated
    measured_speed.record("i1 Display Pro", 500, 700.0, path)
    s = measured_speed.observed("i1 Display Pro", path)
    assert s is not None and s.observed
    assert 1.2 < s.low <= s.typical <= s.high < 1.5
    assert measured_speed.observed("another", path) is None
    with open(path, "w") as f:
        f.write("{damaged")
    assert measured_speed.observed("i1 Display Pro", path) is None  # no crash
