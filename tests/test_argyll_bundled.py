"""The bundled ArgyllCMS is a fallback, never an override."""

import os
import sys

from DisplayCAL import argyll


def test_no_bundle_means_unchanged_paths(monkeypatch):
    monkeypatch.delenv("DISPLAYCAL_BUNDLED_ARGYLL", raising=False)
    assert argyll.get_bundled_argyll_dir() is None
    assert argyll.get_bundled_argyll_dir() is None


def test_override_dir_is_found_and_appended_last(tmp_path, monkeypatch):
    bundled = tmp_path / "ArgyllCMS" / "bin"
    bundled.mkdir(parents=True)
    monkeypatch.setenv("DISPLAYCAL_BUNDLED_ARGYLL", str(bundled))
    monkeypatch.setattr(argyll, "getcfg", lambda name, *a, **k: "/opt/user-argyll/bin")
    paths = argyll.validate_search_paths()
    assert paths[0] == "/opt/user-argyll/bin"  # configured dir first
    assert paths[-1] == str(bundled)  # bundled only as fallback


def test_missing_override_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("DISPLAYCAL_BUNDLED_ARGYLL", str(tmp_path / "nope"))
    assert argyll.get_bundled_argyll_dir() is None


def test_explicit_paths_are_left_alone(tmp_path, monkeypatch):
    bundled = tmp_path / "bin"
    bundled.mkdir()
    monkeypatch.setenv("DISPLAYCAL_BUNDLED_ARGYLL", str(bundled))
    assert argyll.validate_search_paths(["/x"]) == ["/x"]


def test_frozen_mac_layout(tmp_path, monkeypatch):
    monkeypatch.delenv("DISPLAYCAL_BUNDLED_ARGYLL", raising=False)
    app = tmp_path / "DisplayCAL.app" / "Contents"
    (app / "MacOS").mkdir(parents=True)
    (app / "Resources" / "ArgyllCMS" / "bin").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "executable", str(app / "MacOS" / "DisplayCAL"))
    assert argyll.get_bundled_argyll_dir() == os.path.join(
        str(app), "Resources", "ArgyllCMS", "bin"
    )
