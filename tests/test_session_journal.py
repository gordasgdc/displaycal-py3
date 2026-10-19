"""Session journal: what survives, what is claimed, what can be continued."""

import errno
import json
import os
import shutil
import time

import pytest

from DisplayCAL import session_journal as sj


def new(tmp_path, **kw):
    j = sj.SessionJournal(str(tmp_path), **kw)
    j.begin({"display": "D1", "instrument": "i1"})
    return j


def test_state_is_written_atomically_and_readable(tmp_path):
    j = new(tmp_path)
    j.stage("measuring", total=100)
    st = sj.load_state(j.dir)
    assert st["stage"] == "measuring" and st["outcome"] is None
    assert not [f for f in os.listdir(j.dir) if ".tmp-" in f]


def test_checkpoint_keeps_previous_good_copy(tmp_path):
    j = new(tmp_path)
    src = tmp_path / "data.ti3"
    src.write_text("v1")
    assert j.checkpoint(str(src))
    src.write_text("v2")
    assert j.checkpoint(str(src))
    base = os.path.join(j.dir, "files", "data.ti3")
    assert open(base).read() == "v2" and open(base + ".prev").read() == "v1"


def test_disk_full_never_destroys_the_last_valid_copy(tmp_path, monkeypatch):
    j = new(tmp_path)
    src = tmp_path / "data.ti3"
    src.write_text("good")
    assert j.checkpoint(str(src))

    def full(*a, **k):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(shutil, "copyfile", full)
    src.write_text("newer")
    assert j.checkpoint(str(src)) is False
    assert open(os.path.join(j.dir, "files", "data.ti3")).read() == "good"
    assert j.write_errors == 1


def test_state_write_failure_keeps_previous_state(tmp_path, monkeypatch):
    j = new(tmp_path)
    j.stage("calibrating")
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError(errno.ENOSPC, "full")))
    j.stage("measuring")
    monkeypatch.undo()
    assert sj.load_state(j.dir)["stage"] == "calibrating"
    assert j.write_errors >= 1


def test_suspend_gap_is_recorded_as_evidence(tmp_path):
    wall = [1000.0]
    mono = [50.0]
    j = new(tmp_path, wall=lambda: wall[0], mono=lambda: mono[0])
    wall[0] += 3600 * 5  # five hours of wall time...
    mono[0] += 20  # ...but only 20 s of awake time
    j.beat(lambda: {"app_rss": 1})
    st = sj.load_state(j.dir)
    assert 17000 < st["slept_seconds"] < 18100
    keys = [k for k, _ in sj.diagnose(st)]
    assert "recover.fact.slept" in keys


def test_incomplete_session_is_found_and_not_blamed(tmp_path):
    j = new(tmp_path)
    j.progress(4231, 11008, "patches")
    j.stage("measuring")
    j.beat(lambda: {"app_rss": 100, "disk_free": 5})
    j.beat(lambda: {"app_rss": 900, "disk_free": 4})
    st = sj.load_state(j.dir)
    st["app_pid"] = 2**30  # the process that wrote it is gone
    sj._atomic_json(os.path.join(j.dir, "session.json"), st)
    found = sj.scan_incomplete(str(tmp_path))
    assert len(found) == 1
    keys = [k for k, _ in found[0].facts]
    assert "recover.fact.no_clean_exit" in keys and "recover.fact.progress" in keys
    assert "recover.fact.memory" in keys
    # facts only: nothing in the vocabulary names a cause
    assert not any("cause" in k or "crash" in k for k in keys)


def test_finished_and_running_sessions_are_not_offered(tmp_path):
    done = new(tmp_path)
    done.finish("completed")
    running = new(tmp_path)  # pid is this process
    assert sj.scan_incomplete(str(tmp_path)) == []
    assert running.id != done.id


def test_child_exit_is_part_of_the_facts(tmp_path):
    j = new(tmp_path)
    j.child_started("dispread", ["-d1"], 123)
    j.child_exited(-9)
    keys = [k for k, _ in sj.diagnose(sj.load_state(j.dir))]
    assert "recover.fact.child_exit" in keys


def test_resume_only_remaining_blocks_and_only_if_conditions_match(tmp_path):
    j = new(tmp_path)
    fp = sj.fingerprint({"display": "D1", "instrument": "i1", "mode": "l"})
    j.set_plan({"blocks": 5, "fingerprint": fp})
    for n in (1, 2, 3):
        j.block_done(n, 5)
    st = sj.load_state(j.dir)
    ok = sj.resume_plan(st, fp)
    assert ok["possible"] and ok["remaining"] == [4, 5]
    changed = sj.resume_plan(st, sj.fingerprint({"display": "D1", "instrument": "i1", "mode": "r"}))
    assert not changed["possible"] and changed["reason"] == "recover.conditions_changed"


def test_export_copies_without_moving(tmp_path):
    j = new(tmp_path)
    (tmp_path / "x.ti3").write_text("data")
    j.checkpoint(str(tmp_path / "x.ti3"))
    dest = tmp_path / "out"
    dest.mkdir()
    target = sj.export_session(j.dir, str(dest))
    assert os.path.exists(os.path.join(target, "files", "x.ti3"))
    assert os.path.exists(os.path.join(j.dir, "files", "x.ti3"))


def test_review_hides_the_session_next_time(tmp_path):
    j = new(tmp_path)
    j.progress(3, 10)  # something was measured, so it is worth offering
    j.beat()
    st = sj.load_state(j.dir)
    st["app_pid"] = 2**30
    sj._atomic_json(os.path.join(j.dir, "session.json"), st)
    assert sj.scan_incomplete(str(tmp_path))
    sj.mark_reviewed(j.dir, "export")
    assert sj.scan_incomplete(str(tmp_path)) == []


def test_heartbeat_thread_runs_and_stops(tmp_path):
    j = new(tmp_path)
    j.start_heartbeat(lambda: {"app_rss": 1}, interval=0.05)
    import time

    time.sleep(0.3)
    j.stop_heartbeat()
    assert len(sj.load_state(j.dir)["samples"]) >= 2
    assert json.loads(open(os.path.join(j.dir, "events.jsonl")).readline())["e"] == "begin"


def test_prune_removes_only_old_finished_sessions(tmp_path):
    old = time.time() - 40 * 86400
    for name, outcome in (("a", "completed"), ("b", None), ("c", "completed")):
        d = tmp_path / name
        d.mkdir()
        sj._atomic_json(
            str(d / "session.json"),
            {"id": name, "outcome": outcome, "last_heartbeat": old if name != "c" else time.time()},
        )
    assert sj.prune_finished(str(tmp_path)) == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["b", "c"]


def test_sessions_that_measured_nothing_are_not_offered(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    sj._atomic_json(
        str(d / "session.json"),
        {"id": "s", "app_pid": 99999999, "outcome": None, "plan": None, "progress": None,
         "blocks_done": [], "child": {"name": "dispcal"}, "child_exit": {"code": 1}},
    )
    assert sj.scan_incomplete(str(tmp_path)) == []
