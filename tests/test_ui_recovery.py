"""Start-up recovery dialog and end-of-session notification (offscreen)."""

import os
import time

import pytest

from DisplayCAL import session_journal as sj

pytest.importorskip("qtpy")
from test_ui_main_window import _init_config, qapp  # noqa: E402,F401

from DisplayCAL.ui import notifier  # noqa: E402
from DisplayCAL.ui.recovery_dialog import (  # noqa: E402
    RecoveryDialog,
    fact_text,
    human_bytes,
    human_duration,
)


class _FakeWorker:
    resume_from = None

    def session_fingerprint(self):
        return "fp"


@pytest.fixture
def app(qapp, _init_config):  # noqa: F811
    from DisplayCAL import localization

    localization.init()
    return qapp


def _make_session(root, plan=None, done=()):
    d = os.path.join(root, "s1")
    os.makedirs(d)
    state = {
        "id": "s1",
        "started": time.time() - 3600,
        "last_heartbeat": time.time() - 600,
        "stage": "measuring",
        "progress": {"done": 120, "total": 400},
        "app_pid": 99999999,
        "info": {"display": "Test display"},
        "plan": plan,
        "blocks_done": list(done),
    }
    sj._atomic_json(os.path.join(d, "session.json"), state)
    return d


def test_human_text():
    assert human_duration(90 * 60) == "1 h 30 min"
    assert human_duration(12 * 60) == "12 min"
    assert human_bytes(2048) == "2.0 KB"


def test_dialog_lists_facts_and_continue_for_blocks(app, tmp_path):
    _make_session(
        str(tmp_path), {"blocks": 4, "fingerprint": "fp", "block_size": 250}, [1, 2]
    )
    found = sj.scan_incomplete(str(tmp_path))
    assert len(found) == 1
    w = _FakeWorker()
    dlg = RecoveryDialog(found, w)
    assert "120" in dlg.details.text()
    assert not dlg.continue_btn.isHidden() or dlg.continue_btn.isVisibleTo(dlg)
    dlg._continue()
    assert w.resume_from == found[0].dir


def test_dialog_no_continue_when_conditions_changed(app, tmp_path):
    _make_session(str(tmp_path), {"blocks": 4, "fingerprint": "other"}, [1])
    found = sj.scan_incomplete(str(tmp_path))
    dlg = RecoveryDialog(found, _FakeWorker())
    assert not dlg.continue_btn.isVisibleTo(dlg)


def test_seen_marks_reviewed(app, tmp_path):
    _make_session(str(tmp_path))
    found = sj.scan_incomplete(str(tmp_path))
    dlg = RecoveryDialog(found, _FakeWorker())
    dlg._seen()
    assert sj.scan_incomplete(str(tmp_path)) == []


def test_fact_text_all_keys_translate(app, tmp_path):
    _make_session(str(tmp_path))
    for key, params in sj.scan_incomplete(str(tmp_path))[0].facts:
        assert not fact_text(key, params).startswith("recover.fact."), key


def test_session_message_flood():
    title, text = notifier.session_message("failed", "the measurement engine is repeating the same output without progress")
    assert title and text and "recover" not in text
