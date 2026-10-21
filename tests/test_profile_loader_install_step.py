"""Tests for the Windows installer steps run through the loader executable.

The Inno Setup script used to start ``lib\\python.exe`` with an inline script
for these steps. That interpreter cannot import the application's Windows
modules, so after an installation the logon task did not exist and the
calibration-loading mode chosen in the installer was not applied. The steps are
now run by the application executable itself.
"""

import sys
from pathlib import Path
from unittest import mock

import pytest

from DisplayCAL import profile_loader

ROOT = Path(__file__).resolve().parent.parent


def test_no_option_means_no_install_step():
    assert profile_loader.run_install_step(["--force"]) is None
    assert profile_loader.run_install_step([]) is None


def test_displaycal_step_turns_os_management_off_and_creates_the_task(monkeypatch):
    calls = []
    monkeypatch.setattr(
        profile_loader, "calibration_management_isenabled", lambda: True
    )
    monkeypatch.setattr(
        profile_loader,
        "disable_calibration_management",
        lambda: calls.append("disable"),
        raising=False,
    )
    monkeypatch.setattr(
        profile_loader,
        "setup_profile_loader_task",
        lambda *a: calls.append("task"),
    )

    assert profile_loader.run_install_step(["--install-step=displaycal"]) == 0
    assert calls == ["disable", "task"]


def test_displaycal_step_leaves_management_alone_when_already_off(monkeypatch):
    calls = []
    monkeypatch.setattr(
        profile_loader, "calibration_management_isenabled", lambda: False
    )
    monkeypatch.setattr(
        profile_loader,
        "disable_calibration_management",
        lambda: calls.append("disable"),
        raising=False,
    )
    monkeypatch.setattr(
        profile_loader, "setup_profile_loader_task", lambda *a: calls.append("task")
    )

    assert profile_loader.run_install_step(["--install-step=displaycal"]) == 0
    assert calls == ["task"]


def test_os_step_turns_os_management_on(monkeypatch):
    calls = []
    monkeypatch.setattr(
        profile_loader, "calibration_management_isenabled", lambda: False
    )
    monkeypatch.setattr(
        profile_loader,
        "enable_calibration_management",
        lambda: calls.append("enable"),
        raising=False,
    )

    assert profile_loader.run_install_step(["--install-step=os"]) == 0
    assert calls == ["enable"]


def test_failing_step_reports_failure_instead_of_raising(monkeypatch):
    monkeypatch.setattr(
        profile_loader, "calibration_management_isenabled", lambda: False
    )
    monkeypatch.setattr(
        profile_loader,
        "setup_profile_loader_task",
        mock.Mock(side_effect=OSError("denied")),
    )

    assert profile_loader.run_install_step(["--install-step=displaycal"]) == 1


def test_unknown_step_is_rejected():
    assert profile_loader.run_install_step(["--install-step=nonsense"]) == 2


def test_installer_script_does_not_use_the_bundled_python_for_its_steps():
    script = (ROOT / "misc" / "DisplayCAL-Setup-py2exe.iss").read_text()
    run_section = script.split("[Run]", 1)[1].split("[", 1)[0]
    assert "lib\\python.exe" not in run_section
    assert "--install-step=displaycal" in run_section
    assert "--install-step=os" in run_section
