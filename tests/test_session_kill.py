"""A real process is killed in the middle of a session; a new process finds it."""

import os
import signal
import subprocess
import sys
import textwrap

from DisplayCAL import session_journal as sj

CHILD = textwrap.dedent(
    """
    import sys, time
    from DisplayCAL import session_journal as sj
    j = sj.SessionJournal(sys.argv[1])
    j.begin({"display": "fixture"})
    j.set_plan({"blocks": 3, "block_size": 250, "fingerprint": "fp"})
    j.stage("measuring")
    j.block_done(1, 3)
    j.progress(120, 400)
    j.beat(lambda: {"app_rss": 1000, "disk_free": 5000})
    print("ready", flush=True)
    time.sleep(60)
    """
)


def _run_and_kill(root, sig):
    p = subprocess.Popen(
        [sys.executable, "-c", CHILD, root],
        stdout=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": os.getcwd()},
    )
    assert p.stdout.readline().strip() == "ready"
    p.send_signal(sig)
    p.wait(timeout=10)
    return p


def test_sigkill_leaves_a_recoverable_session(tmp_path):
    _run_and_kill(str(tmp_path), signal.SIGKILL)
    found = sj.scan_incomplete(str(tmp_path))
    assert len(found) == 1
    state = found[0].state
    assert state["blocks_done"] == [1]
    assert (state["progress"]["done"], state["progress"]["total"]) == (120, 400)
    keys = [k for k, _ in found[0].facts]
    assert "recover.fact.no_clean_exit" in keys
    # the facts never name a cause
    assert not any("crash" in k or "sleep_cause" in k for k in keys)
    plan = sj.resume_plan(state, "fp")
    assert plan["possible"] and plan["remaining"] == [2, 3]


def test_sigterm_also_leaves_a_readable_session(tmp_path):
    _run_and_kill(str(tmp_path), signal.SIGTERM)
    assert len(sj.scan_incomplete(str(tmp_path))) == 1
    assert sj.load_state(sj.scan_incomplete(str(tmp_path))[0].dir) is not None
