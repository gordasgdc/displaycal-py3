"""Tests for the VideoLUT verify/re-load logic that mitigates issue #694.

The shared detection/recovery helpers live on ``worker.Worker`` and are used
both by the in-session calibration flow (worker.install_profile) and by the
profile loader's macOS watch.
"""

from unittest import mock

from DisplayCAL import config
from DisplayCAL.worker import Worker, reload_black_videoluts


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
