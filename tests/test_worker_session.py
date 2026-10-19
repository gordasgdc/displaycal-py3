"""Worker session safety: journal, blocks, interruption, runaway output."""

import os

import pytest

from DisplayCAL import config, measurement_blocks as mb, session_journal as sj
from DisplayCAL import worker_session as ws
from DisplayCAL.config import setcfg
from DisplayCAL.worker import Worker

from test_measurement_blocks import fake_ti3, make_ti1


@pytest.fixture
def worker(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_HOME", str(tmp_path / "data"))
    w = Worker()
    monkeypatch.setattr(w, "blocks_supported", lambda: (True, ""))
    setcfg("session.keep_awake", 0)  # tests must not hold the machine awake
    yield w
    w.session_end("cancelled", "test teardown")
    setcfg("measurement.block_size", 0)


def run_chart(worker, tmp_path, n=401, size=100, fail_at=None):
    work = worker.create_tempdir()
    base = os.path.join(work, "chart")
    make_ti1(type("P", (), {"write_text": lambda self, t: open(base + ".ti1", "w").write(t)})(), n)
    calls = []

    def impl(cmd, args=None, *a, **k):
        calls.append(list(args))
        blk = args[-1]
        if fail_at is not None and len(calls) == fail_at:
            worker.retcode = -9
            return False
        fake_ti3(blk + ".ti1", blk + ".ti3")
        worker.retcode = 0
        return True

    worker._exec_cmd_impl = impl
    setcfg("measurement.block_size", size)
    result = worker.measure_main("dispread", ["-d1", base], [base])
    return result, base, calls


def test_tempdir_is_durable_not_system_temp(worker, tmp_path):
    d = worker.create_tempdir()
    assert d.startswith(str(tmp_path / "data" / "work"))


def test_blocks_merge_into_the_ti3_the_rest_of_the_app_expects(worker, tmp_path):
    result, base, calls = run_chart(worker, tmp_path)
    assert result is True
    assert len(calls) == 4
    assert "-N" not in calls[0] and "-N" in calls[1] and "-Yp" in calls[1]
    merged = mb.read_table(base + ".ti3")
    assert len(merged.rows) == 401
    assert not [f for f in os.listdir(os.path.dirname(base)) if ".blk" in f]
    j = worker.session_journal
    assert j.state["blocks_done"] == [1, 2, 3, 4]
    assert os.path.exists(os.path.join(j.dir, "files", "chart.blk0003.ti3"))


def test_interruption_keeps_finished_blocks_and_offers_resume(worker, tmp_path):
    result, base, calls = run_chart(worker, tmp_path, fail_at=3)
    assert result is False
    assert not os.path.exists(base + ".ti3")  # no incomplete result presented
    j = worker.session_journal
    st = sj.load_state(j.dir)
    assert st["blocks_done"] == [1, 2]
    assert os.path.exists(os.path.join(j.dir, "files", "chart.blk0002.ti3"))
    assert st["child_exit"]["code"] == -9
    # the application dies here: nothing records an outcome
    st["app_pid"] = 2**30
    sj._atomic_json(os.path.join(j.dir, "session.json"), st)
    found = sj.scan_incomplete(str(tmp_path / "data" / "sessions"))
    assert len(found) == 1
    plan = sj.resume_plan(found[0].state, worker.session_fingerprint())
    assert plan["possible"] and plan["remaining"] == [3, 4]


def test_user_cancel_between_blocks_stops_cleanly(worker, tmp_path):
    work = worker.create_tempdir()
    base = os.path.join(work, "chart")
    make_ti1(type("P", (), {"write_text": lambda self, t: open(base + ".ti1", "w").write(t)})(), 401)
    seen = []

    def impl(cmd, args=None, *a, **k):
        seen.append(1)
        fake_ti3(args[-1] + ".ti1", args[-1] + ".ti3")
        worker.subprocess_abort = len(seen) == 2  # user cancels after block 2
        return True

    worker._exec_cmd_impl = impl
    setcfg("measurement.block_size", 100)
    assert worker.measure_main("dispread", ["-d1", base], [base]) is None
    assert len(seen) == 2
    worker.subprocess_abort = False


def test_small_charts_and_block_size_zero_run_as_before(worker, tmp_path):
    result, base, calls = run_chart(worker, tmp_path, n=120, size=100)
    assert result is True and len(calls) == 1
    setcfg("measurement.block_size", 0)
    work = worker.create_tempdir()
    calls.clear()
    worker._exec_cmd_impl = lambda cmd, args=None, *a, **k: calls.append(args) or True
    assert worker.measure_main("dispread", ["x"], [os.path.join(work, "nochart")]) is True
    assert calls == [["x"]]


def test_unsupported_instrument_is_never_blocked(worker, tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "blocks_supported", lambda: (False, "blocks.needs_calibration"))
    result, base, calls = run_chart(worker, tmp_path)
    assert result is True and len(calls) == 1


def test_measuring_commands_are_journaled_with_exit_code(worker, tmp_path):
    worker._exec_cmd_impl = lambda *a, **k: setattr(worker, "retcode", 0) or True
    assert worker.exec_cmd("/x/dispread", ["-v", "/home/u/secret.name"]) is True
    j = worker.session_journal
    assert j.state["child"]["name"] == "dispread"
    assert j.state["child_exit"]["code"] == 0
    assert "secret.name" in " ".join(j.state["child"]["args"])  # path kept, user dir redacted below
    worker.wrapup(True)
    assert worker.session_journal is None
    done = sj.load_state(os.path.join(str(tmp_path / "data" / "sessions"), os.listdir(tmp_path / "data" / "sessions")[0]))
    assert done["outcome"] == "completed" and done["clean_exit"]


def test_non_measuring_commands_create_no_session(worker):
    worker._exec_cmd_impl = lambda *a, **k: True
    worker.exec_cmd("/x/colprof", ["-v"])
    assert worker.session_journal is None


def test_runaway_output_is_stopped_and_recorded(worker, monkeypatch):
    monkeypatch.setattr(ws, "FLOOD_LINES", 50)
    worker.session_begin()
    dropped = [worker._session_output("same line\n") for _ in range(60)]
    assert dropped[-1] is True and dropped[0] is False
    assert worker.subprocess_abort is True
    events = open(os.path.join(worker.session_journal.dir, "events.jsonl")).read()
    assert "output_flood" in events
    worker.subprocess_abort = False


def test_progress_is_tracked_across_blocks(worker):
    worker.session_begin()
    worker._block_ctx = (200, 1000)
    worker._session_output("patch 7 of 51\n")
    assert worker.session_journal.state["progress"]["done"] == 207
    assert worker.session_journal.state["progress"]["total"] == 1000
    worker._block_ctx = None


def _interrupted(worker, tmp_path):
    result, base, calls = run_chart(worker, tmp_path, fail_at=3)
    assert result is False
    sd = worker.session_journal.dir
    st = sj.load_state(sd)
    st["app_pid"] = 2**30
    sj._atomic_json(os.path.join(sd, "session.json"), st)
    worker.session_journal.stop_heartbeat()
    worker.session_journal = None  # the application is gone
    return sd


def test_resume_measures_only_the_remaining_blocks(worker, tmp_path):
    sd = _interrupted(worker, tmp_path)
    worker.tempdir = None
    worker.resume_from = sd
    result, base, calls = run_chart(worker, tmp_path)  # a fresh run with the same settings
    assert result is True
    assert len(calls) == 2  # blocks 3 and 4 only
    assert len(mb.read_table(base + ".ti3").rows) == 401
    assert sj.load_state(sd)["outcome"] == "reviewed:resumed"
    assert worker.resume_from is None


def test_resume_refuses_when_conditions_changed(worker, tmp_path):
    sd = _interrupted(worker, tmp_path)
    worker.tempdir = None
    worker.resume_from = sd
    setcfg("measurement_mode", "r")  # the monitor/instrument mode is not the same
    try:
        result, base, calls = run_chart(worker, tmp_path)
    finally:
        setcfg("measurement_mode", "l")
    assert isinstance(result, Exception)
    assert calls == []  # nothing was measured, nothing combined
    assert not os.path.exists(base + ".ti3")
