"""Tests for the interactive-adjustment parser ``DisplayCAL.ui.display_adjustment``.

``parse_adjustment`` is the toolkit-neutral core lifted out of the wx
``DisplayAdjustmentFrame.parse_txt`` (see ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``,
Stage 5, sub-slice 5c-i). It needs no display, so these run as plain unit tests
against real ``dispcal`` interactive output captured from the wx frame's own test
fixtures (``tests/test_wx_display_adjustment_frame.py``).
"""

import pytest

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.ui.display_adjustment import (
    AdjustmentContext,
    parse_adjustment,
)


@pytest.fixture(autouse=True)
def _init():
    """Config + localization must be live for the localized read-out labels."""
    config.initcfg()
    lang.init()
    yield


# --- real dispcal output samples -------------------------------------------

# White point page (Adjust R,G & B gain), LCD.
WHITE_POINT = """Doing some initial measurements
Red   = XYZ  81.08  39.18   2.41
Green = XYZ  27.63  80.13  10.97
Blue  = XYZ  18.24   9.90  99.75
White = XYZ 126.53 128.96 112.57

Adjust R,G & B gain to desired white point. Press space when done.
  Initial Br 128.96, x 0.3438 , y 0.3504 , VDT 5152K DE 2K  4.7
/ Current Br 128.85, x 0.3439-, y 0.3502+  VDT 5151K DE 2K  4.8  R-  G++ B-"""

# Black point page (Adjust R,G & B offsets), converged (DE 0.0, R= G= B=).
BLACK_POINT_CONVERGED = """Doing some initial measurements
Black = XYZ   0.19   0.21   0.29
Grey  = XYZ  23.56  24.14  21.83
White = XYZ 124.87 130.00 112.27

Adjust R,G & B offsets to get target x,y. Press space when done.
   Target Br 1.28, x 0.3401 , y 0.3540
/ Current Br 1.28, x 0.3401=, y 0.3540=  DE  0.0  R=  G= B="""

# White level page (Adjust Contrast/Brightness), LCD.
WHITE_LEVEL = """Doing some initial measurements
White = XYZ 125.87 128.23 113.43

Adjust CRT Contrast or LCD Brightness to get target level. Press space when done.
   Target 130.00
/ Current 128.24  +"""

# Check-all page (summary of every metric), then back to the menu.
CHECK_ALL = """Doing check measurements
Black = XYZ   0.19   0.20   0.29
Grey  = XYZ  27.22  27.80  24.49
White = XYZ 126.71 128.91 112.34
1%    = XYZ   1.94   1.98   1.76

  Current Brightness = 128.91
  Target 50% Level  = 24.42, Current = 27.80, error =  2.6%
  Target Near Black =  1.29, Current =  2.02, error =  0.6%
  Current white = x 0.3443, y 0.3503, VDT 5137K DE 2K  5.0
  Target black = x 0.3443, y 0.3503, Current = x 0.3411, y 0.3486, error =  1.73 DE

Press 1 .. 7"""

MENU = """
Press 1 .. 7
1) Black level (CRT: Offset/Brightness)
7) Continue on to calibration
8) Exit
"""


# --- parsing ---------------------------------------------------------------


def test_empty_text_yields_nothing():
    readings = parse_adjustment("", AdjustmentContext("luminance"))
    assert readings.gauges == {}
    assert readings.labels == {}
    assert readings.phase is None


def test_white_point_sets_rgb_gauges_from_deltas():
    # R- G++ B- with DE 4.8 -> R/B nudged one step up, G two steps down.
    ctx = AdjustmentContext("rgb_gain", "l")
    readings = parse_adjustment(WHITE_POINT, ctx)
    assert readings.gauges["R"] == 55
    assert readings.gauges["G"] == 40
    assert readings.gauges["B"] == 55
    # DE 4.8 is out of tolerance.
    assert readings.labels["rgb"].in_tolerance is False


def test_white_point_latches_initial_brightness():
    ctx = AdjustmentContext("rgb_gain", "l")
    parse_adjustment(WHITE_POINT, ctx)
    assert ctx.initial_br[0] == "Initial"
    assert ctx.initial_br[1] == 128.96


def test_white_point_rgb_label_prepends_initial_line():
    ctx = AdjustmentContext("rgb_gain", "l")
    readings = parse_adjustment(WHITE_POINT, ctx)
    text = readings.labels["rgb"].text
    assert text.startswith(lang.getstr("initial"))
    assert lang.getstr("current") in text
    assert "0.3439" in text  # the current x reading


def test_reading_and_indicator_on_measurement():
    ctx = AdjustmentContext("rgb_gain", "l")
    readings = parse_adjustment(WHITE_POINT, ctx)
    assert readings.reading_event is True
    assert readings.indicator == "record"  # "/ Current" present


def test_measuring_phase_detected():
    ctx = AdjustmentContext("rgb_gain", "l")
    readings = parse_adjustment(WHITE_POINT, ctx)
    assert readings.phase == "measuring"


def test_converged_rgb_is_in_tolerance_and_centred():
    ctx = AdjustmentContext("rgb_offset", "l")
    readings = parse_adjustment(BLACK_POINT_CONVERGED, ctx)
    # DE 0.0 with R= G= B= -> every needle centred and in tolerance.
    assert readings.gauges == {"L": 50, "R": 50, "G": 50, "B": 50}
    assert readings.labels["rgb"].in_tolerance is True


def test_white_level_without_target_shows_current_only():
    # dispcal's "Target 130.00" line here is not a full initial-brightness line,
    # so (matching the wx frame) only the current luminance is reported.
    ctx = AdjustmentContext("luminance", "l")
    readings = parse_adjustment(WHITE_LEVEL, ctx)
    assert ctx.initial_br is None
    assert readings.labels["luminance"].in_tolerance is False
    assert lang.getstr("current") in readings.labels["luminance"].text
    assert "128.24" in readings.labels["luminance"].text


def test_check_all_reports_every_metric_without_reading_event():
    ctx = AdjustmentContext("check_all", "l")
    readings = parse_adjustment(CHECK_ALL, ctx)
    assert set(readings.labels) == {
        "luminance",
        "black_level",
        "white_point",
        "black_point",
    }
    # check_all is a summary page: no beep / indicator dot.
    assert readings.reading_event is False
    assert readings.indicator is None
    assert readings.phase == "menu"


def test_check_all_black_level_lcd_uses_black_xyz():
    ctx = AdjustmentContext("check_all", "l")
    readings = parse_adjustment(CHECK_ALL, ctx)
    # LCD path reads black luminance from "Black = XYZ .. 0.20 ..".
    assert "0.20" in readings.labels["black_level"].text


def test_check_all_black_level_crt_uses_near_black():
    ctx = AdjustmentContext("check_all", "c")
    readings = parse_adjustment(CHECK_ALL, ctx)
    # CRT path reads it from "Target Near Black = 1.29, Current = 2.02".
    assert ctx.target_bl == ["Target", 1.29]
    assert "2.02" in readings.labels["black_level"].text
    assert lang.getstr("target") in readings.labels["black_level"].text


def test_check_all_black_point_has_target_and_current():
    ctx = AdjustmentContext("check_all", "l")
    readings = parse_adjustment(CHECK_ALL, ctx)
    text = readings.labels["black_point"].text
    assert lang.getstr("target") in text
    assert lang.getstr("current") in text
    assert "0.3411" in text  # current black x


def test_menu_phase_detected_and_no_readings():
    readings = parse_adjustment(MENU, AdjustmentContext("luminance"))
    assert readings.phase == "menu"
    assert readings.gauges == {}
    assert readings.labels == {}


def test_target_brightness_latched_once():
    ctx = AdjustmentContext("luminance", "l")
    parse_adjustment("Target white brightness = 120.0", ctx)
    assert ctx.target_br == ["Target", 120.0]
    # A later, different target does not overwrite the latched one.
    parse_adjustment("Target white brightness = 99.0", ctx)
    assert ctx.target_br == ["Target", 120.0]
