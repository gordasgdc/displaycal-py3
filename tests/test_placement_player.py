"""The placement sequence: controllable, calm, and motion-respecting."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("qtpy")

from DisplayCAL import instrument_catalog as ic  # noqa: E402
from DisplayCAL.ui import placement_player as pp  # noqa: E402
from DisplayCAL.ui.motion import prefers_reduced_motion  # noqa: E402


def test_timeline_manual_steps_pause_playback():
    tl = pp.Timeline(4)
    tl.play()
    tl.next()
    assert tl.step == 1 and not tl.playing and tl.t == 1.0
    tl.prev()
    tl.prev()
    assert tl.step == 0


def test_timeline_plays_through_once_then_stops():
    tl = pp.Timeline(3)
    tl.play()
    for _ in range(10_000):
        tl.tick(33)
        if not tl.playing:
            break
    assert tl.step == 2 and not tl.playing and tl.t == 1.0


def test_timeline_replay_from_end_restarts():
    tl = pp.Timeline(3)
    tl.goto(2)
    tl.play()
    assert tl.step == 0 and tl.playing


def test_reduced_motion_never_animates_frames():
    tl = pp.Timeline(3, reduced=True)
    assert tl.t == 1.0
    tl.play()
    seen = set()
    for _ in range(5000):
        tl.tick(33)
        seen.add(tl.t)
        if not tl.playing:
            break
    assert seen == {1.0}  # step changes only, no in-between frames
    assert tl.step == 2


def test_reduced_motion_override(monkeypatch):
    monkeypatch.setenv("DISPLAYCAL_REDUCE_MOTION", "1")
    assert prefers_reduced_motion() is True
    monkeypatch.setenv("DISPLAYCAL_REDUCE_MOTION", "0")
    assert prefers_reduced_motion() is False


@pytest.fixture(scope="module")
def qapp():
    from qtpy.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_every_variant_and_step_paints_and_animated_steps_move(qapp):
    from qtpy.QtGui import QImage, QPainter

    steps = ("calibrate", "face", "diffuser", "cover", "cable", "contact", "tilt", "position")

    def render(step, t, variant, kind):
        img = QImage(380, 250, QImage.Format_ARGB32)
        img.fill(0)
        p = QPainter(img)
        pp.draw_scene(p, step, t, variant, kind, dark=True)
        p.end()
        return img.constBits().tobytes()

    for variant in ("generic", "i1d3", "spyder_x"):
        for kind in (ic.KIND_COLORIMETER, ic.KIND_SPECTRO_PUCK, ic.KIND_OTHER):
            for step in steps:
                a = render(step, 0.0, variant, kind)
                b = render(step, 1.0, variant, kind)
                assert a != b, (variant, kind, step)


def test_player_stop_halts_the_timer_and_controls_work(qapp):
    player = pp.PlacementPlayer()
    player.set_sequence(["face", "contact", "position"], "generic", ic.KIND_COLORIMETER)
    assert not player.is_playing()
    player.play_btn.click()
    assert player.is_playing()
    player.stop()
    assert not player.is_playing() and not player._timer.isActive()
    player.next_btn.click()
    assert player.canvas.step == "contact"
    player.prev_btn.click()
    assert player.canvas.step == "face"
    assert player.prev_btn.isEnabled() is False


def test_player_does_not_autoplay_when_reduced(qapp, monkeypatch):
    monkeypatch.setenv("DISPLAYCAL_REDUCE_MOTION", "1")
    player = pp.PlacementPlayer()
    player.autoplay_once()
    assert not player.is_playing()
    assert player.reduced_motion


def test_player_has_text_alternative_names(qapp):
    player = pp.PlacementPlayer()
    assert player.canvas.accessibleName()
    assert player.prev_btn.accessibleName() and player.next_btn.accessibleName()
