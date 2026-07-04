"""Tests for the toolkit-neutral profile install / load-on-login helpers.

Covers the pure pieces extracted from ``MainFrame.install_profile_handler`` /
``profile_finish`` / ``profile_finish_consumer`` in
``DisplayCAL/profile_install.py``. No display or QApplication is needed.
"""

import sys

import pytest

from DisplayCAL import localization as lang
from DisplayCAL import profile_install as pi
from DisplayCAL.icc_profile import ICCProfileInvalidError


class TestLoadInstallableProfile:
    def test_valid_rgb_monitor_profile(self, data_path):
        path = data_path / "icc" / "vcgt_cm_test_cyanish_reddish.icc"
        profile = pi.load_installable_profile(str(path))
        assert profile.profileClass == b"mntr"
        assert profile.colorSpace == b"RGB"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises((OSError, ICCProfileInvalidError)):
            pi.load_installable_profile(str(tmp_path / "nope.icc"))

    def test_invalid_file_raises(self, tmp_path):
        bogus = tmp_path / "bogus.icc"
        bogus.write_bytes(b"not an icc profile")
        with pytest.raises((OSError, ICCProfileInvalidError)):
            pi.load_installable_profile(str(bogus))


class TestGetProfileLoadOnLoginLabel:
    """These compare against live ``lang.getstr`` output rather than a
    hardcoded raw key, since another test in the same process/worker may
    already have called ``lang.init()`` and populated real translations."""

    def test_non_windows_ignores_os_cal(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        base = lang.getstr("profile.load_on_login")
        assert pi.get_profile_load_on_login_label(True) == base
        assert pi.get_profile_load_on_login_label(False) == base

    def test_windows_appends_preserve_when_not_os_managed(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        base = lang.getstr("profile.load_on_login")
        preserve = lang.getstr("calibration.preserve")
        if lang.getcode() != "de":
            preserve = preserve[0].lower() + preserve[1:]
        label = pi.get_profile_load_on_login_label(False)
        assert label == f"{base} && {preserve}"

    def test_windows_omits_suffix_when_os_managed(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        base = lang.getstr("profile.load_on_login")
        assert pi.get_profile_load_on_login_label(True) == base


class TestResolveInstallScopeOptions:
    def test_darwin_superuser_offers_user_and_local(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        options = pi.resolve_install_scope_options(
            argyll_version=[1, 9, 0],
            is_superuser_or_sudo=True,
            windows_version=None,
            network_profiles_dir_exists=False,
        )
        assert options == ["u", "l"]

    def test_darwin_with_network_dir_offers_network_too(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        options = pi.resolve_install_scope_options(
            argyll_version=[1, 9, 0],
            is_superuser_or_sudo=True,
            windows_version=None,
            network_profiles_dir_exists=True,
        )
        assert options == ["u", "l", "n"]

    def test_no_privilege_offers_nothing(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        options = pi.resolve_install_scope_options(
            argyll_version=[1, 9, 0],
            is_superuser_or_sudo=False,
            windows_version=None,
            network_profiles_dir_exists=False,
        )
        assert options == []

    def test_old_argyll_on_linux_offers_nothing(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        options = pi.resolve_install_scope_options(
            argyll_version=[1, 0, 0],
            is_superuser_or_sudo=True,
            windows_version=None,
            network_profiles_dir_exists=False,
        )
        assert options == []

    def test_windows_vista_and_later_offers_user_and_local(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        options = pi.resolve_install_scope_options(
            argyll_version=[1, 1, 2],
            is_superuser_or_sudo=False,
            windows_version=(6, 1),
            network_profiles_dir_exists=False,
        )
        assert options == ["u", "l"]

    def test_windows_pre_vista_offers_nothing(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "win32")
        options = pi.resolve_install_scope_options(
            argyll_version=[1, 1, 2],
            is_superuser_or_sudo=False,
            windows_version=(5, 1),
            network_profiles_dir_exists=False,
        )
        assert options == []

    def test_test_mode_forces_options(self):
        options = pi.resolve_install_scope_options(
            argyll_version=[1, 0, 0],
            is_superuser_or_sudo=False,
            windows_version=None,
            network_profiles_dir_exists=False,
            test_mode=True,
        )
        assert options == ["u", "l"]


class TestSummarizeInstallResult:
    def test_all_none_is_success(self):
        summary = pi.summarize_install_result(None, None, None, None)
        assert summary.message_key == "success"
        assert summary.all_good
        assert summary.details == []

    def test_all_true_is_success(self):
        summary = pi.summarize_install_result(True, True, True, True)
        assert summary.message_key == "success"
        assert summary.all_good

    def test_partial_failure_on_linux_is_warning(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        summary = pi.summarize_install_result(True, False, None, None)
        assert summary.message_key == "warning"
        assert not summary.all_good
        names = [name for name, _, _ in summary.details]
        assert "ArgyllCMS" in names
        assert "colord" in names

    def test_total_failure_is_error(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        summary = pi.summarize_install_result(False, False, False, False)
        assert summary.message_key == "error"
        assert not summary.all_good

    def test_partial_failure_off_linux_is_error(self, monkeypatch):
        # darwin/win32 only ever run the ArgyllCMS installer, so a single
        # method failing (with no fallback) is a hard error, not a warning.
        monkeypatch.setattr(sys, "platform", "darwin")
        summary = pi.summarize_install_result(False, None, None, None)
        assert summary.message_key == "error"
        # No per-method breakdown is shown outside Linux.
        assert summary.details == []

    def test_warning_result_reported_as_warning_detail(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "linux")
        warning = Warning("partially applied")
        summary = pi.summarize_install_result(True, warning, None, None)
        assert summary.message_key == "warning"
        assert not summary.all_good
        detail = next(d for d in summary.details if d[0] == "colord")
        assert detail[1] is None
        assert detail[2] == "partially applied"


class TestProfileUnsupportedError:
    def test_message_mentions_class_and_space(self):
        error = pi.ProfileUnsupportedError(b"scnr", b"CMYK")
        assert isinstance(error, Exception)
        # lang.getstr falls back to the raw key when translations aren't
        # loaded, so just check the exception carries the raw values through.
        assert error.profile_class == b"scnr"
        assert error.color_space == b"CMYK"
