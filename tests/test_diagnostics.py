"""Observability: bounded logs, redaction, correlation, support package."""

import json
import logging
import os
import re
import sys
import threading
import zipfile

import pytest

from DisplayCAL import diagnostics as dg
from DisplayCAL import log as dlog
from DisplayCAL import redaction
from DisplayCAL import session_journal as sj


@pytest.fixture
def logger(tmp_path, monkeypatch):
    """A real file logger as the application builds it, in a temp folder."""
    name = f"t{id(tmp_path)}"
    lg = dlog.get_file_logger(
        name, logdir=str(tmp_path), filename="DisplayCAL", backup_count=3
    )
    monkeypatch.setattr(dlog, "LOGGER", lg)
    monkeypatch.setattr(dlog, "_LOGDIR", str(tmp_path))
    yield lg
    for h in list(lg.handlers):
        h.close()
        lg.removeHandler(h)


def _log_text(tmp_path):
    p = tmp_path / "DisplayCAL.log"
    return p.read_text(encoding="utf-8")


# --- format and structure ---------------------------------------------------


def test_lines_have_iso_time_level_and_run_id(logger, tmp_path):
    dg.event("warning", "deps", "deps.argyll_missing", "no engine", found=False)
    line = _log_text(tmp_path).splitlines()[-1]
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d\d:\d\d:\d\d\.\d{3}[+-]\d{4} WARNING", line)
    assert f"[{dlog.APP_SESSION_ID}]" in line
    assert "event=deps.argyll_missing" in line and "subsystem=deps" in line
    assert "found=False" in line and "| no engine" in line


def test_secrets_and_email_never_reach_the_file(logger, tmp_path):
    dg.event("info", "app", "x", "token=abcd1234 password: hunter2 mail me@example.com")
    dg.event("info", "app", "y", "https://user:pw@example.com/a")
    text = _log_text(tmp_path)
    for secret in ("abcd1234", "hunter2", "me@example.com", "user:pw"):
        assert secret not in text


# --- rotation, retention, failures ------------------------------------------


def test_size_rotation_and_total_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(dlog, "LOG_MAX_BYTES", 2000)
    h = dlog.BoundedTimedRotatingFileHandler(
        str(tmp_path / "A.log"), when="midnight", backupCount=3, max_bytes=2000
    )
    lg = logging.getLogger("rot-test")
    lg.setLevel(logging.INFO)
    lg.addHandler(h)
    for i in range(400):
        lg.info("x" * 100 + str(i))
    h.close()
    lg.removeHandler(h)
    backups = [n for n in os.listdir(tmp_path) if n.startswith("A.log.")]
    assert 1 <= len(backups) <= 3  # retention count enforced
    assert (tmp_path / "A.log").stat().st_size < 2000 + 400
    # total budget: with a tiny budget even the allowed count shrinks
    dlog.prune_log_backups(str(tmp_path), "A.log", 3, total_budget=1)
    assert not [n for n in os.listdir(tmp_path) if n.startswith("A.log.")]
    assert (tmp_path / "A.log").exists()  # the active file is never removed


def test_unwritable_log_dir_does_not_stop_the_program(tmp_path, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    lg = dlog.get_file_logger(
        "unwritable", logdir=str(blocker / "sub"), filename="D", backup_count=1
    )
    lg.info("still works")  # no handler or a dead one: must not raise
    dg.event("info", "app", "z")


def test_failing_log_write_never_changes_the_operation(logger, monkeypatch):
    for h in logger.handlers:
        monkeypatch.setattr(h, "emit", lambda record: (_ for _ in ()).throw(OSError("disk full")))
    result = []

    def operation():
        dg.event("info", "measure", "measure.stage", "x")
        result.append("done")

    operation()
    assert result == ["done"]


def test_broken_journal_sink_is_dropped_not_fatal(tmp_path):
    j = sj.SessionJournal(str(tmp_path))
    j.sink = lambda kind, data: 1 / 0
    j.begin({"display": "x"})
    j.event("stage", name="measuring")  # must not raise
    assert j.sink is None


# --- correlation ------------------------------------------------------------


def test_concurrent_jobs_are_told_apart_by_job_id(logger, tmp_path):
    journals = []
    for _ in range(2):
        j = sj.SessionJournal(str(tmp_path / "sessions"))
        j.sink = dg.journal_sink_for(j)
        j.begin({"display": "d"})
        journals.append(j)

    def work(j, label):
        for n in range(20):
            j.event("block_done", number=n, label=label)

    ts = [threading.Thread(target=work, args=(j, f"L{i}")) for i, j in enumerate(journals)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    lines = [ln for ln in _log_text(tmp_path).splitlines() if "block_done" in ln]
    assert len(lines) == 40
    for i, j in enumerate(journals):
        mine = [ln for ln in lines if f"job={j.id}" in ln]
        assert len(mine) == 20 and all(f"label=L{i}" in ln for ln in mine)


# --- redaction --------------------------------------------------------------


def test_full_redaction_covers_platform_paths_and_identifiers(monkeypatch):
    monkeypatch.setenv("USER", "cristi")
    text = (
        "/Users/cristi/Library/x C:\\Users\\Maria\\AppData\\y /home/ana/z "
        "/Volumes/MyDisk/f 192.168.1.20 aa:bb:cc:dd:ee:ff "
        "123e4567-e89b-12d3-a456-426614174000 serial: ABC123 api_key=SECRET"
    )
    out = redaction.redact(text)
    for leak in ("cristi", "Maria", "/home/ana", "MyDisk", "192.168", "aa:bb", "123e4567", "ABC123", "SECRET"):
        assert leak not in out, leak


# --- support package --------------------------------------------------------


def _tree(tmp_path):
    logdir = tmp_path / "logs"
    logdir.mkdir()
    (logdir / "DisplayCAL.log").write_text("2026 INFO /Users/cristi/x token=abc\n" * 3)
    (logdir / "crash-abcd.txt").write_text("Fatal Python error\n  File /Users/cristi/a.py\n")
    sroot = tmp_path / "sessions"
    d = sroot / "20261019-101010-aaaaaa"
    (d / "files").mkdir(parents=True)
    (d / "session.json").write_text(json.dumps({"id": "s", "info": {"display": "D"}}))
    (d / "events.jsonl").write_text('{"e":"child_exited","code":1}\n')
    (d / "files" / "chart.ti3").write_text("MEASUREMENTS 1 2 3\n")
    prof = tmp_path / "display.icc"
    prof.write_bytes(b"ICCPROFILE")
    return str(logdir), str(sroot), str(prof)


def test_package_defaults_exclude_measurements_and_profiles(tmp_path, monkeypatch):
    monkeypatch.setenv("USER", "cristi")
    logdir, sroot, prof = _tree(tmp_path)
    cats = dg.plan_package(logdir, sroot, prof)
    defaults = {c.key for c in cats if c.default}
    assert defaults == {"versions", "logs", "sessions", "crashes"}
    dest = str(tmp_path / "out.zip")
    manifest = dg.export_package(dest, defaults, cats)
    with zipfile.ZipFile(dest) as z:  # opens with the standard library alone
        names = z.namelist()
        assert "manifest.json" in names and "README.txt" in names
        assert not [n for n in names if n.endswith((".ti3", ".icc"))]
        blob = b"".join(z.read(n) for n in names).decode("utf-8", "replace")
    assert "cristi" not in blob and "token=abc" not in blob
    assert set(manifest["not_included_unless_chosen"]) >= {"measurements", "profile"}
    assert not os.path.exists(dest + ".part")


def test_optional_attachments_only_when_chosen(tmp_path):
    logdir, sroot, prof = _tree(tmp_path)
    cats = dg.plan_package(logdir, sroot, prof)
    dest = str(tmp_path / "out2.zip")
    dg.export_package(dest, {"versions", "measurements", "profile"}, cats)
    with zipfile.ZipFile(dest) as z:
        names = z.namelist()
    assert "measurements/chart.ti3" in names and "profile/display.icc" in names
    assert not [n for n in names if n.startswith("logs/")]


def test_failed_export_leaves_no_partial_file(tmp_path):
    logdir, sroot, prof = _tree(tmp_path)
    cats = dg.plan_package(logdir, sroot, prof)
    missing = str(tmp_path / "nope" / "out.zip")
    with pytest.raises(OSError):
        dg.export_package(missing, {"logs"}, cats)
    assert not os.path.exists(missing + ".part")


# --- crash / unclean exit ---------------------------------------------------


def test_previous_unclean_run_is_reported(logger, tmp_path):
    (tmp_path / dg.LAST_RUN_FILE).write_text(
        json.dumps({"session": "oldrun01", "started": "t", "clean": False})
    )
    dg._check_previous_run(str(tmp_path))
    text = _log_text(tmp_path)
    assert "app.previous_run_unclean" in text and "oldrun01" in text


def test_unhandled_exception_is_logged_with_traceback(logger, tmp_path, monkeypatch):
    old = sys.excepthook
    try:
        sys.excepthook = lambda *a: None
        dg.install_crash_hooks(str(tmp_path))
        try:
            raise ValueError("boom")
        except ValueError:
            sys.excepthook(*sys.exc_info())
    finally:
        sys.excepthook = old
        dg.mark_clean_exit(str(tmp_path))
    text = _log_text(tmp_path)
    assert "app.unhandled_exception" in text and "ValueError" in text
    last = json.loads((tmp_path / dg.LAST_RUN_FILE).read_text())
    assert last["clean"] is True
