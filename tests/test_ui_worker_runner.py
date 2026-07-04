"""Tests for the Qt worker execution layer ``DisplayCAL.ui.worker_runner``.

These cover the toolkit-neutral ``parse_progress`` extracted from
``Worker.progress_handler`` (worker.py:15022). Pure function, no display or
``QApplication`` needed. See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 5).
"""

import pytest

from DisplayCAL.ui.worker_runner import parse_progress


def test_percent_download_progress():
    pct, lastmsg = parse_progress("", "42%")
    assert pct == 42
    assert lastmsg == "42%"


def test_percent_ignores_equals_calibration_check():
    # The '=' guard stops a calibration-check "1%" reading being treated as
    # command progress.
    pct, _ = parse_progress("", "1% = something")
    assert pct is None


def test_patch_of_progress():
    # Patch 26 of 100 -> (26 - 1) / 100 * 100 = 25.0
    pct, _ = parse_progress("", "Patch 26 of 100")
    assert pct == pytest.approx(25.0)


def test_patch_of_progress_first_patch_floors_at_zero():
    # Patch 1 of 50 -> max(1 - 1, 0) / 50 = 0.0
    pct, _ = parse_progress("", "Patch 1 of 50")
    assert pct == pytest.approx(0.0)


def test_added_targen_progress():
    # Added 30/120 -> 25%
    pct, _ = parse_progress("", "Added 30/120")
    assert pct == pytest.approx(25.0)


def test_iteration_targen_progress_clears_lastmsg():
    # It 5: ... -> min(5, 20) / 20 * 100 = 25%, and lastmsg is cleared.
    pct, lastmsg = parse_progress("It 5: refining", "some stale line")
    assert pct == pytest.approx(25.0)
    assert lastmsg == ""


def test_iteration_caps_at_twenty():
    pct, _ = parse_progress("It 40: refining", "")
    assert pct == pytest.approx(100.0)


def test_warnings_are_stripped_not_parsed():
    # A warning line must not be parsed as progress.
    pct, lastmsg = parse_progress("", "dispread: Warning - something 50%")
    assert pct is None
    assert "Warning" not in lastmsg


def test_no_match_returns_none():
    pct, lastmsg = parse_progress("just some text", "nothing numeric here")
    assert pct is None
    assert lastmsg == "nothing numeric here"


def test_percentage_is_clamped():
    pct, _ = parse_progress("", "150%")
    assert pct == 100
