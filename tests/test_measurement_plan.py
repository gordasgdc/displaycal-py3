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
