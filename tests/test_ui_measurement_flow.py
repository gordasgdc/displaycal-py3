"""Tests for the toolkit-neutral ``DisplayCAL.ui.measurement_flow`` engine.

These cover the measurement-flow logic extracted from ``display_cal.MainFrame``
(see ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``, Stage 2): the presentation-mode
decision, the pattern-generator classification, the measure-frame subprocess
command / result contract, the observer item derivation and the pending-function
state machine. None of it needs a GUI toolkit or a display.
"""

import subprocess as sp

import pytest

from DisplayCAL import config
from DisplayCAL.config import getcfg, setcfg
from DisplayCAL.ui import measurement_flow as mf


@pytest.fixture(autouse=True)
def _init_config():
    """Ensure config is initialised (default values) before each test."""
    config.initcfg()
    yield


# --- decide_presentation ---------------------------------------------------


def test_decide_presentation_virtual_display_calls_pending():
    mode = mf.decide_presentation(
        "Untethered",
        is_virtual_display=True,
        dry_run=False,
        use_patternwindow=False,
        platform="linux",
    )
    assert mode is mf.PresentationMode.CALL_PENDING


def test_decide_presentation_dry_run_calls_pending():
    mode = mf.decide_presentation(
        "DELL U2413",
        is_virtual_display=False,
        dry_run=True,
        use_patternwindow=False,
        platform="linux",
    )
    assert mode is mf.PresentationMode.CALL_PENDING


@pytest.mark.parametrize("display_name", ["Resolve", "Prisma", "Chromecast 1", "Prisma 2"])
def test_decide_presentation_networked_virtual_still_shows_frame(display_name):
    """Networked virtual displays are excluded from the direct-call shortcut."""
    mode = mf.decide_presentation(
        display_name,
        is_virtual_display=True,
        dry_run=False,
        use_patternwindow=False,
        platform="linux",
    )
    assert mode is mf.PresentationMode.SUBPROCESS


@pytest.mark.parametrize("platform", ["darwin", "win32"])
def test_decide_presentation_desktop_shows_frame_in_process(platform):
    mode = mf.decide_presentation(
        "DELL U2413",
        is_virtual_display=False,
        dry_run=False,
        use_patternwindow=False,
        platform=platform,
    )
    assert mode is mf.PresentationMode.SHOW_FRAME


def test_decide_presentation_patternwindow_shows_frame_in_process():
    """The Wayland software-patch path shows the frame in-process on Linux."""
    mode = mf.decide_presentation(
        "DELL U2413",
        is_virtual_display=False,
        dry_run=False,
        use_patternwindow=True,
        platform="linux",
        isexe=False,
    )
    assert mode is mf.PresentationMode.SHOW_FRAME


def test_decide_presentation_linux_defaults_to_subprocess():
    mode = mf.decide_presentation(
        "DELL U2413",
        is_virtual_display=False,
        dry_run=False,
        use_patternwindow=False,
        platform="linux",
        isexe=False,
    )
    assert mode is mf.PresentationMode.SUBPROCESS


# --- patterngenerator_kind -------------------------------------------------


@pytest.mark.parametrize(
    "display_name,expected",
    [
        ("DELL U2413", mf.PatternGeneratorKind.NONE),
        ("Prisma", mf.PatternGeneratorKind.PRISMA),
        ("madVR", mf.PatternGeneratorKind.MADVR),
        ("Resolve", mf.PatternGeneratorKind.NETWORK),
        ("Web @ localhost", mf.PatternGeneratorKind.NETWORK),
        ("Chromecast Living Room", mf.PatternGeneratorKind.NETWORK),
    ],
)
def test_patterngenerator_kind(display_name, expected):
    assert mf.patterngenerator_kind(display_name) is expected


# --- subprocess command / result contract ---------------------------------


def test_build_measureframe_command_targets_qt_frame():
    args = mf.build_measureframe_command(exe="/usr/bin/python3", pydir="/pkg/parent")
    assert args[0] == "/usr/bin/python3"
    assert args[1] == "-c"
    script = args[2]
    assert "DisplayCAL.ui import measure_frame" in script
    assert "measure_frame.main()" in script
    assert "/pkg/parent" in script


def test_run_measureframe_subprocess_reports_exit_code():
    args = ["/nonexistent/python-binary-xyz", "-c", "pass"]
    returncode, stderr = mf.run_measureframe_subprocess(args, env={})
    # Spawn failure -> the sentinel failed code and a non-empty message.
    assert returncode == mf.MEASUREFRAME_EXITCODE_FAILED
    assert stderr


def test_run_measureframe_subprocess_success_and_on_start(tmp_path):
    seen = []
    args = ["python3", "-c", "import sys; sys.exit(255)"]
    returncode, _stderr = mf.run_measureframe_subprocess(
        args, env={}, on_start=seen.append
    )
    assert returncode == mf.MEASUREFRAME_EXITCODE_MEASURE
    assert len(seen) == 1
    assert isinstance(seen[0], sp.Popen)


def test_interpret_measureframe_result_measure_calls_pending():
    result = mf.interpret_measureframe_result(255)
    assert result.should_call_pending is True
    assert result.should_restore is False
    assert result.config_changed is True
    assert result.error_message is None


def test_interpret_measureframe_result_clean_close_restores():
    result = mf.interpret_measureframe_result(0)
    assert result.should_call_pending is False
    assert result.should_restore is True
    assert result.error_message is None


def test_interpret_measureframe_result_spawn_failure_not_config_changed():
    result = mf.interpret_measureframe_result(-1, "boom")
    assert result.config_changed is False
    assert result.should_restore is True
    # -1 is not the OK code, so a message is surfaced.
    assert result.error_message == "boom"


def test_interpret_measureframe_result_error_message_only_when_stderr():
    assert mf.interpret_measureframe_result(3, "   ").error_message is None
    assert mf.interpret_measureframe_result(3, "kaput").error_message == "kaput"


# --- observer items --------------------------------------------------------


def test_observer_items_covers_valid_values():
    items = mf.observer_items()
    assert set(items) == set(config.VALID_VALUES["observer"])
    # Every value is a non-empty label string.
    assert all(isinstance(label, str) and label for label in items.values())


# --- MeasurementFlow pending-function state machine ------------------------


def test_pending_function_set_take_roundtrip():
    flow = mf.MeasurementFlow()
    assert flow.has_pending_function is False

    def target():
        return "ran"

    flow.set_pending_function(target, 1, 2, key="v")
    assert flow.has_pending_function is True
    func, args, kwargs = flow.take_pending_function()
    assert func is target
    assert args == (1, 2)
    assert kwargs == {"key": "v"}
    # Taking clears the slot.
    assert flow.has_pending_function is False


def test_clear_pending_function():
    flow = mf.MeasurementFlow()
    flow.set_pending_function(lambda: None, 1)
    flow.clear_pending_function()
    assert flow.has_pending_function is False
    func, args, kwargs = flow.take_pending_function()
    assert func is None
    assert args == ()
    assert kwargs == {}


def test_plan_measurement_stages_and_decides(monkeypatch):
    flow = mf.MeasurementFlow()
    monkeypatch.setattr(config, "get_display_name", lambda *a, **k: "DELL U2413")
    monkeypatch.setattr(config, "is_virtual_display", lambda *a, **k: False)
    setcfg("dry_run", 0)

    def target():
        return None

    plan = flow.plan_measurement(target, "arg", use_patternwindow=True, wrapup=False)
    assert plan.display_name == "DELL U2413"
    assert plan.mode is mf.PresentationMode.SHOW_FRAME
    assert plan.wrapup is False
    # wrapup must not leak into the staged kwargs.
    func, args, kwargs = flow.take_pending_function()
    assert func is target
    assert args == ("arg",)
    assert kwargs == {}


def test_plan_measurement_dry_run_calls_pending(monkeypatch):
    flow = mf.MeasurementFlow()
    monkeypatch.setattr(config, "get_display_name", lambda *a, **k: "DELL U2413")
    monkeypatch.setattr(config, "is_virtual_display", lambda *a, **k: False)
    setcfg("dry_run", 1)
    plan = flow.plan_measurement(lambda: None)
    assert plan.mode is mf.PresentationMode.CALL_PENDING
    assert getcfg("dry_run") == 1
