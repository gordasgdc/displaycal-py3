"""Install read-back: a finished install is not a verified one."""

import os

from DisplayCAL import guide_model as gm
from DisplayCAL import profile_verify as pv
from DisplayCAL.icc_profile import ICCProfile

PRESETS = os.path.join(os.path.dirname(__file__), "..", "DisplayCAL", "presets")
PHOTO = os.path.join(PRESETS, "photo.icc")
VIDEO = os.path.join(PRESETS, "video.icc")


def test_same_profile_active_is_verified():
    check = pv.verify_active_profile(PHOTO, 0, read_active=lambda n: ICCProfile(PHOTO))
    assert check.verified and check.status == pv.MATCH


def test_different_active_profile_is_a_mismatch_not_a_success():
    check = pv.verify_active_profile(PHOTO, 0, read_active=lambda n: ICCProfile(VIDEO))
    assert not check.verified and check.status == pv.MISMATCH
    assert check.active_description


def test_no_active_profile():
    check = pv.verify_active_profile(PHOTO, 0, read_active=lambda n: None)
    assert check.status == pv.NONE_ACTIVE and not check.verified


def test_reader_failure_is_unreadable_not_success():
    def boom(n):
        raise OSError("osascript failed")

    check = pv.verify_active_profile(PHOTO, 0, read_active=boom)
    assert check.status == pv.UNREADABLE and not check.verified


def test_missing_installed_file_is_unreadable():
    check = pv.verify_active_profile(
        "/nonexistent/x.icc", 0, read_active=lambda n: ICCProfile(PHOTO)
    )
    assert check.status == pv.UNREADABLE


def test_scan_failure_is_reported_with_recovery_actions():
    r = gm.compute_readiness(
        argyll_found=True, displays=["d"], instruments=["i"], scan_failed=True
    )
    assert r.status == gm.SCAN_FAILED and not r.ok
    assert "guide.action.check_permission" in r.action_keys
