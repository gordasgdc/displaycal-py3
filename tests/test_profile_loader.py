"""Tests for the VideoLUT verify/re-load logic that mitigates issue #694.

The shared detection/recovery helpers live on ``worker.Worker`` and are used
both by the in-session calibration flow (worker.install_profile) and by the
profile loader's macOS watch.
"""

from unittest import mock

from DisplayCAL import config
from DisplayCAL.profile_loader import ProfileLoader
from DisplayCAL.worker import Worker, reload_black_videoluts


class FakeMultiDisplayWorker:
    """A stand-in for Worker with a configurable per-display clobbered set."""

    def __init__(self, ndisplays, clobbered):
        self.displays = [f"Display {i + 1}" for i in range(ndisplays)]
        self.clobbered = set(clobbered)

    def get_dispwin_display_profile_argument(self, display_no):
        return f"/tmp/display{display_no}.icc"

    def calibration_is_clobbered(self, dispwin, display_no, profile_arg):
        return display_no in self.clobbered


def _profile_loader_stub():
    """A ProfileLoader instance without the heavy wx/thread __init__ side effects."""
    pl = ProfileLoader.__new__(ProfileLoader)
    pl._shutdown = False
    return pl


class FakeExec:
    """Records dispwin args and feeds canned 'Verify:' output to a Worker."""

    def __init__(self, errors=None, output=None):
        self._errors = errors or []
        self._output = output or []
        self.calls = []

    def __call__(self, worker, cmd, args, **kwargs):
        self.calls.append((cmd, args, kwargs))
        worker.errors = list(self._errors)
        worker.output = list(self._output)
        return True


def _worker_with_output(errors=None, output=None):
    """A Worker whose exec_cmd is replaced by a FakeExec."""
    worker = Worker.__new__(Worker)
    worker.errors = []
    worker.output = []
    fake = FakeExec(errors=errors, output=output)
    worker.exec_cmd = lambda cmd, args, **kw: fake(worker, cmd, args, **kw)
    worker._fake = fake
    return worker


def test_discrepancy_parsed_from_not_loaded():
    worker = _worker_with_output(
        output=["Verify: '/tmp/p.icc' is NOT loaded (discrepancy 8.6%)"]
    )
    assert worker.get_calibration_load_discrepancy("dispwin", 0, "/tmp/p.icc") == 8.6


def test_discrepancy_parsed_from_is_loaded():
    worker = _worker_with_output(
        output=["Verify: '/tmp/p.icc' IS loaded (discrepancy 0.3%)"]
    )
    assert worker.get_calibration_load_discrepancy("dispwin", 0, "/tmp/p.icc") == 0.3


def test_discrepancy_none_without_videolut_access():
    worker = _worker_with_output(errors=["We don't have access to the VideoLUT"])
    assert worker.get_calibration_load_discrepancy("dispwin", 0, "/tmp/p.icc") is None


def test_discrepancy_none_when_unparseable():
    worker = _worker_with_output(output=["some unrelated message"])
    assert worker.get_calibration_load_discrepancy("dispwin", 0, "/tmp/p.icc") is None


def test_verify_uses_verify_only_args():
    """Verification must use -V (read-only) and not load (-L would change the LUT)."""
    worker = _worker_with_output(
        output=["Verify: '/tmp/p.icc' IS loaded (discrepancy 0.1%)"]
    )
    worker.get_calibration_load_discrepancy("dispwin", 1, "/tmp/p.icc")
    _cmd, args, _kw = worker._fake.calls[0]
    assert "-V" in args and "-d2" in args and "/tmp/p.icc" in args
    assert "-L" not in args


def test_clobbered_true_for_black_screen():
    config.initcfg()
    worker = _worker_with_output(
        output=["Verify: '/tmp/p.icc' is NOT loaded (discrepancy 98.4%)"]
    )
    assert worker.calibration_is_clobbered("dispwin", 0, "/tmp/p.icc") is True


def test_clobbered_false_for_quantization_noise():
    """A small discrepancy (quantization) must NOT be treated as clobbered.

    dispwin would report this as 'is NOT loaded' (its tolerance is ~0.4%), but
    re-loading on such noise would needlessly re-trigger the macOS bug.
    """
    config.initcfg()
    worker = _worker_with_output(
        output=["Verify: '/tmp/p.icc' is NOT loaded (discrepancy 3.0%)"]
    )
    assert worker.calibration_is_clobbered("dispwin", 0, "/tmp/p.icc") is False


def test_clobbered_false_when_undetermined():
    config.initcfg()
    worker = _worker_with_output(errors=["We don't have access to the VideoLUT"])
    assert worker.calibration_is_clobbered("dispwin", 0, "/tmp/p.icc") is False


def test_clobbered_threshold_is_configurable():
    config.initcfg()
    config.setcfg("profile_loader.clobbered_discrepancy_threshold", 5)
    worker = _worker_with_output(
        output=["Verify: '/tmp/p.icc' is NOT loaded (discrepancy 8.6%)"]
    )
    try:
        assert worker.calibration_is_clobbered("dispwin", 0, "/tmp/p.icc") is True
    finally:
        config.setcfg("profile_loader.clobbered_discrepancy_threshold", 25)


def test_reload_black_videoluts_noop_off_macos():
    """The recovery is macOS-only; elsewhere it does nothing."""
    with mock.patch("DisplayCAL.worker.sys.platform", "win32"):
        assert reload_black_videoluts("dispwin") == []


def test_reload_black_videoluts_reloads_only_black_displays():
    """Only displays whose VideoLUT max is below threshold get re-loaded."""
    runs = []
    # display 0 is fine (1.0), display 1 is black (0.0); after one reload all fine.
    maxima_seq = iter([[1.0, 0.0], [1.0, 1.0]])
    with mock.patch("DisplayCAL.worker.sys.platform", "darwin"):
        reloaded = reload_black_videoluts(
            "dispwin",
            retries=4,
            _maxima_fn=lambda: next(maxima_seq),
            _run=runs.append,
            _sleep=lambda s: None,
        )
    assert reloaded == [1]
    assert runs == [["dispwin", "-v", "-d2", "-L"]]


def test_reload_black_videoluts_retries_until_sticks():
    """If a re-load gets clobbered again, it retries until it sticks."""
    runs = []
    # black, black again after first reload, then clean.
    maxima_seq = iter([[0.0], [0.0], [1.0]])
    with mock.patch("DisplayCAL.worker.sys.platform", "darwin"):
        reloaded = reload_black_videoluts(
            "dispwin",
            retries=5,
            _maxima_fn=lambda: next(maxima_seq),
            _run=runs.append,
            _sleep=lambda s: None,
        )
    assert reloaded == [0]
    assert runs == [["dispwin", "-v", "-d1", "-L"], ["dispwin", "-v", "-d1", "-L"]]


def test_reload_black_videoluts_noop_when_all_fine():
    """No re-load when every display has a healthy VideoLUT."""
    runs = []
    with mock.patch("DisplayCAL.worker.sys.platform", "darwin"):
        reloaded = reload_black_videoluts(
            "dispwin",
            _maxima_fn=lambda: [1.0, 0.98],
            _run=runs.append,
            _sleep=lambda s: None,
        )
    assert reloaded == []
    assert runs == []


def test_reload_black_videoluts_ignores_unreadable_displays():
    """A display that couldn't be read (None) is left alone."""
    runs = []
    with mock.patch("DisplayCAL.worker.sys.platform", "darwin"):
        reloaded = reload_black_videoluts(
            "dispwin",
            _maxima_fn=lambda: [None, 1.0],
            _run=runs.append,
            _sleep=lambda s: None,
        )
    assert reloaded == []
    assert runs == []


def test_clobbered_displays_skips_virtual_and_uninstalled():
    """Virtual displays and displays with no installed profile are skipped."""
    worker = FakeMultiDisplayWorker(ndisplays=3, clobbered={0, 1, 2})
    worker.get_dispwin_display_profile_argument = lambda display_no: (
        "-L" if display_no == 1 else f"/tmp/display{display_no}.icc"
    )
    pl = _profile_loader_stub()
    with mock.patch(
        "DisplayCAL.profile_loader.config.is_virtual_display",
        side_effect=lambda i: i == 2,
    ):
        assert pl._clobbered_displays(worker, "dispwin") == [0]


def test_reload_clobbered_displays_batches_simultaneous_clobbers_in_one_pass():
    """Two displays black at once are both reloaded within a single pass."""
    worker = FakeMultiDisplayWorker(ndisplays=2, clobbered={0, 1})
    pl = _profile_loader_stub()
    calls = []

    def fake_apply_profiles(index=None):
        calls.append(index)
        worker.clobbered.discard(index)

    pl.apply_profiles = fake_apply_profiles
    with (
        mock.patch(
            "DisplayCAL.profile_loader.config.is_virtual_display",
            return_value=False,
        ),
        mock.patch("DisplayCAL.profile_loader.time.sleep"),
    ):
        converged = pl._reload_clobbered_displays(
            worker, "dispwin", max_passes=5, settle=0
        )
    assert calls == [0, 1]
    assert converged is True


def test_reload_clobbered_displays_converges_after_ping_pong():
    """Fixing one display re-clobbers the other (issue #824); it must still converge.

    This reproduces the reported multi-display loop: reloading display 0
    "clobbers" display 1 and vice-versa, but on the third pass nothing is
    clobbered any more (the OS settles), and the batched reload must notice
    that and stop instead of looping forever.
    """
    worker = FakeMultiDisplayWorker(ndisplays=2, clobbered={0})
    pl = _profile_loader_stub()
    calls = []
    passes_done = 0

    def fake_apply_profiles(index=None):
        nonlocal passes_done
        calls.append(index)
        worker.clobbered.discard(index)
        other = 1 - index
        if passes_done < 2:
            worker.clobbered.add(other)

    def fake_sleep(_seconds):
        nonlocal passes_done
        passes_done += 1

    pl.apply_profiles = fake_apply_profiles
    with (
        mock.patch(
            "DisplayCAL.profile_loader.config.is_virtual_display",
            return_value=False,
        ),
        mock.patch("DisplayCAL.profile_loader.time.sleep", side_effect=fake_sleep),
    ):
        converged = pl._reload_clobbered_displays(
            worker, "dispwin", max_passes=10, settle=0
        )
    assert not worker.clobbered
    assert calls == [0, 1, 0]
    assert converged is True


def test_reload_clobbered_displays_stops_after_max_passes_without_hanging():
    """A never-converging ping-pong must be bounded, not loop forever."""
    worker = FakeMultiDisplayWorker(ndisplays=2, clobbered={0})
    pl = _profile_loader_stub()
    calls = []

    def fake_apply_profiles(index=None):
        calls.append(index)
        worker.clobbered.discard(index)
        worker.clobbered.add(1 - index)

    pl.apply_profiles = fake_apply_profiles
    with (
        mock.patch(
            "DisplayCAL.profile_loader.config.is_virtual_display",
            return_value=False,
        ),
        mock.patch("DisplayCAL.profile_loader.time.sleep"),
    ):
        converged = pl._reload_clobbered_displays(
            worker, "dispwin", max_passes=4, settle=0
        )
    assert len(calls) == 4
    assert worker.clobbered
    assert converged is False


def test_reload_clobbered_displays_stops_on_shutdown():
    """The shutdown flag must break out of the reload loop promptly."""
    worker = FakeMultiDisplayWorker(ndisplays=1, clobbered={0})
    pl = _profile_loader_stub()
    calls = []

    def fake_apply_profiles(index=None):
        calls.append(index)
        pl._shutdown = True
        # Still "clobbered" - a real shutdown just stops trying.
        worker.clobbered.add(0)

    pl.apply_profiles = fake_apply_profiles
    with (
        mock.patch(
            "DisplayCAL.profile_loader.config.is_virtual_display",
            return_value=False,
        ),
        mock.patch("DisplayCAL.profile_loader.time.sleep"),
    ):
        converged = pl._reload_clobbered_displays(
            worker, "dispwin", max_passes=10, settle=0
        )
    assert calls == [0]
    assert converged is True


def test_macos_watch_backs_off_after_repeated_non_convergence():
    """Non-converging displays trigger a notification and a backoff pause.

    Some multi-display Macs never converge (issue #824): reloading display A
    deterministically clobbers display B and vice-versa, confirmed by hand.
    Retrying forever would just keep flickering the screens, so after a few
    consecutive non-converging ticks the watch must stop touching the
    displays for a while and notify the user once, instead of hammering
    dispwin indefinitely.
    """
    config.initcfg()
    config.setcfg("profile_loader.macos_reapply_watch_interval", 1)
    config.setcfg("profile_loader.macos_reapply_watch_unstable_threshold", 2)
    config.setcfg("profile_loader.macos_reapply_watch_backoff_seconds", 9999)

    pl = _profile_loader_stub()
    pl._reload_clobbered_displays = mock.Mock(return_value=False)
    pl._notify_macos_watch_unstable = mock.Mock()

    tick_count = {"n": 0}

    def fake_is_displaycal_running():
        tick_count["n"] += 1
        if tick_count["n"] >= 5:
            pl._shutdown = True
        return False

    pl._is_displaycal_running = fake_is_displaycal_running

    try:
        with (
            mock.patch("DisplayCAL.profile_loader.time.sleep"),
            mock.patch("DisplayCAL.worker.get_argyll_util", return_value="dispwin"),
            mock.patch("DisplayCAL.worker.Worker") as mock_worker_cls,
        ):
            mock_worker_cls.return_value.enumerate_displays_and_ports = mock.Mock()
            pl._macos_watch()
        # Only the first two ticks actually attempt a reload (that's what
        # trips the unstable threshold); the rest are skipped by the backoff.
        assert pl._reload_clobbered_displays.call_count == 2
        assert pl._notify_macos_watch_unstable.call_count == 1
    finally:
        config.setcfg("profile_loader.macos_reapply_watch_interval", 5)
        config.setcfg("profile_loader.macos_reapply_watch_unstable_threshold", 3)
        config.setcfg("profile_loader.macos_reapply_watch_backoff_seconds", 300)
