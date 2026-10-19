"""ArgyllCMS downloads are never installed unverified."""

import re

import pytest

from DisplayCAL import argyll_integrity as ai


def test_pinned_table_is_well_formed():
    for version, files in ai.PINNED_SHA256.items():
        assert files
        for name, digest in files.items():
            assert name.startswith(f"Argyll_V{version}_")
            assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_every_platform_the_app_downloads_is_pinned():
    from DisplayCAL.update_check import resolve_argyll_download_url

    pinned = ai.PINNED_SHA256["3.5.0"]
    for plat, machine in (
        ("win32", "arm64"),
        ("win32", "amd64"),
        ("darwin", "arm64"),
        ("darwin", "x86_64"),
        ("linux", "x86_64"),
    ):
        import platform as pf
        import sys

        orig_p, orig_m = sys.platform, pf.machine
        sys.platform, pf.machine = plat, lambda m=machine: m
        try:
            url = resolve_argyll_download_url("3.5.0", "https://x")
        finally:
            sys.platform, pf.machine = orig_p, orig_m
        assert url.rsplit("/", 1)[1] in pinned, url


def test_pinned_used_when_api_unavailable():
    name = "Argyll_V3.5.0_macOS11_arm64_bin.tgz"
    assert (
        ai.resolve_expected_hash("3.5.0", name, None) == ai.PINNED_SHA256["3.5.0"][name]
    )


def test_api_value_used_for_unknown_version():
    assert ai.resolve_expected_hash("9.9.9", "x.tgz", "AB" * 32) == "ab" * 32


def test_no_source_means_refuse():
    assert ai.resolve_expected_hash("9.9.9", "x.tgz", None) is None


def test_conflict_between_pinned_and_api_is_an_error():
    name = "Argyll_V3.5.0_win64_exe.zip"
    with pytest.raises(ai.HashConflictError):
        ai.resolve_expected_hash("3.5.0", name, "0" * 64)


def test_matching_api_and_pinned_agree():
    name = "Argyll_V3.5.0_win64_exe.zip"
    pinned = ai.PINNED_SHA256["3.5.0"][name]
    assert ai.resolve_expected_hash("3.5.0", name, pinned.upper()) == pinned
