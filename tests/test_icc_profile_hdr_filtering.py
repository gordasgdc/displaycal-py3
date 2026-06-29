"""Tests for issue #627: Profile loader must not apply HDR calibration profile in SDR mode.

The Windows HDR Calibration app stores its profile under the ICMProfileAC
registry value.  When the display is in SDR mode that value must be ignored so
the correct SDR profile (ICMProfile) is used instead.
"""

import os
import sys
import types
from unittest import mock

import pytest

from DisplayCAL import icc_profile as _icc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_winreg(registry_values):
    """Return a minimal fake winreg module seeded with the given values.

    registry_values: sequence of (name, value, type_) tuples as EnumValue
        would return.
    """
    m = types.ModuleType("winreg")
    m.HKEY_CURRENT_USER = 0x80000001
    m.HKEY_LOCAL_MACHINE = 0x80000002
    m.REG_BINARY = 3
    m.REG_MULTI_SZ = 7

    fake_key = mock.MagicMock()
    m.OpenKey = mock.Mock(return_value=fake_key)
    m.CloseKey = mock.Mock()
    m.QueryInfoKey = mock.Mock(return_value=(0, len(registry_values), 0))
    m.EnumValue = mock.Mock(side_effect=lambda key, i: registry_values[i])
    return m


@pytest.fixture()
def registry_with_both_profiles(tmp_path):
    """Inject a fake winreg with both ICMProfile and ICMProfileAC into icc_profile."""
    sdr_file = tmp_path / "sdr_profile.icm"
    hdr_file = tmp_path / "windows_hdr_calibration.icm"
    sdr_file.write_bytes(b"")
    hdr_file.write_bytes(b"")

    registry_values = [
        ("ICMProfile", [sdr_file.name], 7),
        ("ICMProfileAC", [hdr_file.name], 7),
    ]
    fake_winreg = _make_fake_winreg(registry_values)

    orig_winreg = getattr(_icc, "winreg", None)
    orig_profiles = _icc.ICCPROFILES

    _icc.winreg = fake_winreg
    _icc.ICCPROFILES = [str(tmp_path)]

    yield _icc, sdr_file.name, hdr_file.name

    if orig_winreg is None:
        if hasattr(_icc, "winreg"):
            del _icc.winreg
    else:
        _icc.winreg = orig_winreg
    _icc.ICCPROFILES = orig_profiles


# Monkey-key that represents the last two components of a typical device key.
_MONKEY = ["{4d36e96e-e325-11ce-bfc1-08002be10318}", "0002"]


# ---------------------------------------------------------------------------
# _winreg_get_display_profiles
# ---------------------------------------------------------------------------

class TestWinregGetDisplayProfiles:
    def test_returns_both_profiles_by_default(self, registry_with_both_profiles):
        """Both ICMProfile and ICMProfileAC are returned when filtering is off."""
        icc, sdr, hdr = registry_with_both_profiles
        profiles = icc._winreg_get_display_profiles(_MONKEY)
        assert sdr in profiles
        assert hdr in profiles

    def test_exclude_advanced_color_removes_hdr_entry(self, registry_with_both_profiles):
        """With exclude_advanced_color=True, ICMProfileAC entries are dropped."""
        icc, sdr, hdr = registry_with_both_profiles
        profiles = icc._winreg_get_display_profiles(
            _MONKEY, exclude_advanced_color=True
        )
        assert sdr in profiles
        assert hdr not in profiles

    def test_exclude_false_keeps_hdr_entry(self, registry_with_both_profiles):
        """Explicitly passing exclude_advanced_color=False keeps both entries."""
        icc, sdr, hdr = registry_with_both_profiles
        profiles = icc._winreg_get_display_profiles(
            _MONKEY, exclude_advanced_color=False
        )
        assert hdr in profiles


# ---------------------------------------------------------------------------
# _winreg_get_display_profile
# ---------------------------------------------------------------------------

class TestWinregGetDisplayProfile:
    def test_sdr_mode_returns_sdr_profile(self, registry_with_both_profiles):
        """advanced_color_active=False must exclude ICMProfileAC and pick ICMProfile."""
        icc, sdr, hdr = registry_with_both_profiles
        result = icc._winreg_get_display_profile(
            _MONKEY, path_only=True, advanced_color_active=False
        )
        assert result is not None
        assert sdr in result
        assert hdr not in result

    def test_hdr_mode_returns_hdr_profile(self, registry_with_both_profiles):
        """advanced_color_active=True must keep ICMProfileAC (last entry wins)."""
        icc, sdr, hdr = registry_with_both_profiles
        result = icc._winreg_get_display_profile(
            _MONKEY, path_only=True, advanced_color_active=True
        )
        assert result is not None
        assert hdr in result

    def test_unknown_hdr_state_returns_hdr_profile(self, registry_with_both_profiles):
        """advanced_color_active=None (unknown) must not filter; last entry wins."""
        icc, sdr, hdr = registry_with_both_profiles
        result = icc._winreg_get_display_profile(
            _MONKEY, path_only=True, advanced_color_active=None
        )
        assert result is not None
        assert hdr in result

    def test_only_sdr_profile_in_registry(self, tmp_path):
        """When no ICMProfileAC exists, SDR profile is still returned correctly."""
        sdr_file = tmp_path / "sdr_only.icm"
        sdr_file.write_bytes(b"")

        fake_winreg = _make_fake_winreg([("ICMProfile", [sdr_file.name], 7)])
        orig_winreg = getattr(_icc, "winreg", None)
        orig_profiles = _icc.ICCPROFILES
        _icc.winreg = fake_winreg
        _icc.ICCPROFILES = [str(tmp_path)]
        try:
            result = _icc._winreg_get_display_profile(
                _MONKEY, path_only=True, advanced_color_active=False
            )
            assert result is not None
            assert sdr_file.name in result
        finally:
            if orig_winreg is None:
                if hasattr(_icc, "winreg"):
                    del _icc.winreg
            else:
                _icc.winreg = orig_winreg
            _icc.ICCPROFILES = orig_profiles
