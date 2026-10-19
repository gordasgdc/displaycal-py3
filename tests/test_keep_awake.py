"""Sleep prevention is held only while asked, and always released."""

import subprocess
import sys

import pytest

from DisplayCAL import keep_awake as ka


def test_honest_list_of_what_is_not_prevented():
    assert "awake.not.lock" in ka.NOT_PREVENTED and "awake.not.lid" in ka.NOT_PREVENTED


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS tool")
def test_macos_caffeinate_acquire_and_release():
    k = ka.KeepAwake()
    st = k.acquire()
    assert st.active and st.method == "caffeinate"
    pid = k._proc.pid
    assert subprocess.run(["/bin/ps", "-p", str(pid)], capture_output=True).returncode == 0
    k.release()
    assert not k.active
    import time

    time.sleep(0.3)
    assert subprocess.run(["/bin/ps", "-p", str(pid)], capture_output=True).returncode != 0


def test_failure_to_start_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")

    def boom(*a, **k):
        raise OSError("no caffeinate")

    monkeypatch.setattr(subprocess, "Popen", boom)
    st = ka.KeepAwake().acquire()
    assert not st.active and "no caffeinate" in st.error


def test_release_is_idempotent():
    k = ka.KeepAwake()
    k.release()
    k.release()
    assert not k.active
