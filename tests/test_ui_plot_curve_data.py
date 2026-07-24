"""Tests for the curve-viewer profile-action helpers in ``curve_data.py``.

Covers the pure-data functions added for issue #849 (BPC apply, install/reload
vcgt, advanced per-tag shaper curves): no Qt import needed, since these are
plain functions operating on ``ICCProfile``/``Worker`` objects. See
``DisplayCAL.wx_lut_viewer.LUTFrame`` for the wx originals these mirror.
"""

import os

import pytest

from DisplayCAL import config
from DisplayCAL.icc_profile import ICCProfile
from DisplayCAL.ui.plot.curve_data import (
    apply_bpc,
    available_shaper_modes,
    extract_shaper_curve,
    install_vcgt,
    reload_display_vcgt,
    shaper_mode_lang_key,
)
from DisplayCAL.worker import Worker

_ICC_DIR = os.path.join(os.path.dirname(__file__), "data", "icc")

#: Has a non-zero vcgt black point *and* A2B0/A2B1/B2A0/B2A1 LUT16Type tags,
#: so it exercises both the BPC and shaper-curve helpers.
_CLUT_PROFILE = os.path.join(
    _ICC_DIR, "Monitor 1 #1 2022-03-09 16-13 D6500 2.2 F-S XYZLUT+MTX.icc"
)


@pytest.fixture(autouse=True)
def _init_config():
    config.initcfg()
    yield


@pytest.fixture
def clut_profile():
    return ICCProfile(_CLUT_PROFILE)


@pytest.fixture
def vcgt_profile():
    # A profile with a clean ASCII description (unlike _CLUT_PROFILE, whose
    # "mluc" desc tag getDescription() mis-decodes) so the temp-file naming
    # in install_vcgt() doesn't trip over an unrelated parsing quirk.
    return ICCProfile(os.path.join(_ICC_DIR, "vcgt_cm_test_cyanish_reddish.icc"))


# -- apply_bpc ----------------------------------------------------------------


def test_apply_bpc_zeroes_the_black_point(clut_profile):
    before = clut_profile.tags["vcgt"].getNormalizedValues()
    assert before[0] != (0.0, 0.0, 0.0)  # fixture must have a lifted black point

    fake = apply_bpc(clut_profile)

    after = fake.tags["vcgt"].getNormalizedValues()
    assert after[0] == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    # White should be essentially unaffected by BPC.
    assert after[-1] == pytest.approx(before[-1], abs=1e-6)


# -- shaper curves --------------------------------------------------------------


def test_available_shaper_modes_respects_show_advanced_options(clut_profile):
    config.setcfg("show_advanced_options", 0)
    assert available_shaper_modes(clut_profile) == []

    config.setcfg("show_advanced_options", 1)
    modes = available_shaper_modes(clut_profile)
    assert modes == [
        "A2B0.input", "A2B0.output",
        "A2B1.input", "A2B1.output",
        "B2A0.input", "B2A0.output",
        "B2A1.input", "B2A1.output",
    ]


def test_shaper_mode_lang_key():
    assert shaper_mode_lang_key("A2B0.input") == "profile.tags.A2B0.shaper_curves.input"
    assert (
        shaper_mode_lang_key("B2A2.output") == "profile.tags.B2A2.shaper_curves.output"
    )


def test_extract_shaper_curve_device_rgb_input(clut_profile):
    channels, x_max, y_max, x_label, y_label = extract_shaper_curve(
        clut_profile, "A2B0.input"
    )
    assert set(channels) == {"R", "G", "B"}
    assert (x_max, y_max) == (255.0, 255.0)
    assert (x_label, y_label) == ("RGB", "RGB")
    for points in channels.values():
        assert points[0] == (0.0, 0.0)
        assert points[-1] == (255.0, 255.0)


def test_extract_shaper_curve_connection_xyz_output(clut_profile):
    channels, x_max, y_max, x_label, y_label = extract_shaper_curve(
        clut_profile, "A2B0.output"
    )
    assert set(channels) == {"X", "Y", "Z"}
    assert (x_max, y_max) == (100.0, 100.0)
    assert (x_label, y_label) == ("XYZ", "XYZ")


class _FakeShaperTag:
    def __init__(self, input_tables, output_tables):
        self.input = input_tables
        self.output = output_tables


class _FakeProfile:
    def __init__(self, tags, color_space, connection_color_space):
        self.tags = tags
        self.colorSpace = color_space
        self.connectionColorSpace = connection_color_space


def test_extract_shaper_curve_lab_l_channel_resampled():
    # B2A0.input operates on the connection colour space (Lab): the L*
    # channel is stored in the v2 0..25500/65280 encoding and must be
    # resampled onto the same uniform grid as a*/b*.
    n = 5
    l_table = [round(i / (n - 1) * 65280) for i in range(n)]
    ab_table = [round(i / (n - 1) * 65535) for i in range(n)]
    tag = _FakeShaperTag(
        input_tables=[l_table, ab_table, ab_table],
        output_tables=[[0, 65535]] * 3,
    )
    profile = _FakeProfile({"B2A0": tag}, b"RGB", b"Lab")

    channels, x_max, y_max, x_label, y_label = extract_shaper_curve(
        profile, "B2A0.input"
    )

    assert set(channels) == {"L*", "a*", "b*"}
    assert (x_max, y_max) == (100.0, 100.0)
    assert (x_label, y_label) == ("L*a*b*", "L*a*b*")
    l_points = channels["L*"]
    assert l_points[0] == pytest.approx((0.0, 0.0), abs=1e-6)
    assert l_points[-1] == pytest.approx((100.0, 100.0), abs=1e-6)


# -- install / reload vcgt -----------------------------------------------------


def test_install_vcgt_writes_cal_and_runs_dispwin(vcgt_profile, monkeypatch, tmp_path):
    worker = Worker()
    monkeypatch.setattr(worker, "create_tempdir", lambda: str(tmp_path))
    calls = {}

    def fake_prepare_dispwin(cal):
        calls["cal"] = cal
        assert os.path.isfile(cal)
        return ["dispwin"], ["-d1", cal]

    def fake_exec_cmd(cmd, args, **kwargs):
        calls["cmd"] = (cmd, args)
        return True

    monkeypatch.setattr(worker, "prepare_dispwin", fake_prepare_dispwin)
    monkeypatch.setattr(worker, "exec_cmd", fake_exec_cmd)

    install_vcgt(vcgt_profile, worker)

    assert calls["cmd"][0] == ["dispwin"]
    # The temporary .cal file is cleaned up afterwards.
    assert not os.path.isfile(calls["cal"])


def test_install_vcgt_raises_on_exec_failure(vcgt_profile, monkeypatch, tmp_path):
    worker = Worker()
    monkeypatch.setattr(worker, "create_tempdir", lambda: str(tmp_path))
    monkeypatch.setattr(
        worker, "prepare_dispwin", lambda cal: (["dispwin"], ["-d1", cal])
    )
    monkeypatch.setattr(worker, "exec_cmd", lambda *a, **k: False)
    worker.errors = ["dispwin failed"]

    with pytest.raises(RuntimeError, match="dispwin failed"):
        install_vcgt(vcgt_profile, worker)


def test_reload_display_vcgt_returns_display_profile(clut_profile, monkeypatch):
    worker = Worker()
    monkeypatch.setattr(worker, "prepare_dispwin", lambda cal: (["dispwin"], ["-d1"]))
    monkeypatch.setattr(worker, "exec_cmd", lambda *a, **k: True)
    # get_display_profile is imported lazily from DisplayCAL.config inside the
    # function, so patch it at the source.
    monkeypatch.setattr(config, "get_display_profile", lambda: clut_profile)

    result = reload_display_vcgt(worker)

    assert result is clut_profile


def test_reload_display_vcgt_raises_when_no_profile(monkeypatch):
    worker = Worker()
    monkeypatch.setattr(worker, "prepare_dispwin", lambda cal: (["dispwin"], ["-d1"]))
    monkeypatch.setattr(worker, "exec_cmd", lambda *a, **k: True)
    monkeypatch.setattr(config, "get_display_profile", lambda: None)

    with pytest.raises(ValueError):
        reload_display_vcgt(worker)
