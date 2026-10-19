"""Durable journal of a measurement session (toolkit-neutral, no colour maths).

Purpose: an eight-hour run must leave evidence and data on disk that survive the
application, the ArgyllCMS process or the computer stopping, and the next start
must be able to say *what is known* about where it stopped -- without guessing a
cause.

Layout, under ``<root>/<session-id>/``::

    session.json    current state, rewritten atomically (never half-written)
    events.jsonl    append-only event trail (flushed per event)
    files/          durable copies of measurement files, atomically replaced,
                    previous good copy kept as ``<name>.prev``

Nothing here deletes data. Finishing a session marks it; old sessions are only
removed by an explicit user action.

Facts recorded for the diagnosis (never interpreted as a cause by themselves):
stage and progress, last output/activity time, ArgyllCMS child pid and exit
code, application and child memory (RSS) over time, wall-clock versus monotonic
time (their difference is time the computer spent suspended), free disk space,
and whether the application shut down cleanly.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Callable

SCHEMA = 1
HEARTBEAT_S = 20
#: A gap this much longer than the heartbeat interval counts as "not running".
GAP_FACTOR = 3


def _atomic_json(path: str, data: dict) -> None:
    tmp = f"{path}.tmp-{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def fingerprint(parts: dict[str, object]) -> str:
    """Stable hash of what must be identical for two measurements to combine."""
    blob = json.dumps(parts, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def file_digest(path: str) -> str | None:
    """SHA-256 prefix of a file, or ``None`` if unreadable."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()[:16]


def pid_alive(pid: int) -> bool:
    """Whether a process with this pid exists."""
    if pid <= 0:
        return False
    try:
        import psutil

        return psutil.pid_exists(pid)
    except ImportError:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True


class SessionJournal:
    """Writes the durable state of one session."""

    def __init__(
        self,
        root: str,
        *,
        wall: Callable[[], float] = time.time,
        mono: Callable[[], float] = time.monotonic,
    ) -> None:
        self.root = root
        self._wall = wall
        self._mono = mono
        self.id = ""
        self.dir = ""
        self.state: dict = {}
        self._lock = threading.RLock()
        self._hb: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_wall = 0.0
        self._last_mono = 0.0
        self.write_errors = 0
        #: Optional ``callable(kind, data)``: mirrors every event elsewhere (the
        #: application log), correlated by this journal's session ID.
        self.sink: Callable[[str, dict], None] | None = None

    # -- lifecycle --------------------------------------------------------
    def begin(self, info: dict) -> str:
        """Create the session directory and its first state."""
        self.id = time.strftime("%Y%m%d-%H%M%S", time.localtime(self._wall())) + "-"
        self.id += uuid.uuid4().hex[:6]
        self.dir = os.path.join(self.root, self.id)
        os.makedirs(os.path.join(self.dir, "files"), exist_ok=True)
        now = self._wall()
        self._last_wall, self._last_mono = now, self._mono()
        self.state = {
            "schema": SCHEMA,
            "id": self.id,
            "started": now,
            "app_pid": os.getpid(),
            "info": info,
            "stage": "starting",
            "progress": None,
            "last_activity": now,
            "last_heartbeat": now,
            "slept_seconds": 0.0,
            "child": None,
            "child_exit": None,
            "samples": [],
            "output_bytes": 0,
            "outcome": None,  # None while running; set only by finish()
            "reason": None,
            "clean_exit": False,
            "plan": None,
            "blocks_done": [],
        }
        self._save()
        self.event("begin", info_keys=sorted(info))
        return self.id

    def finish(self, outcome: str, reason: str | None = None) -> None:
        """Mark the session as ended: ``completed``, ``failed`` or ``cancelled``."""
        with self._lock:
            self.stop_heartbeat()
            self.state["outcome"] = outcome
            self.state["reason"] = reason
            self.state["clean_exit"] = True
            self.state["finished"] = self._wall()
            self._save()
            self.event("finish", outcome=outcome, reason=reason)

    # -- facts ------------------------------------------------------------
    def stage(self, name: str, **extra: object) -> None:
        """Record the current stage (calibration, measurement, profiling...)."""
        with self._lock:
            self.state["stage"] = name
            self.state.update(extra)
            self._save()
            self.event("stage", name=name, **extra)

    def set_plan(self, plan: dict) -> None:
        """Record the measurement plan (patches, blocks, fingerprint)."""
        with self._lock:
            self.state["plan"] = plan
            self._save()

    def progress(self, done: int, total: int, label: str = "") -> None:
        """Record progress (kept in memory; persisted with the heartbeat)."""
        with self._lock:
            self.state["progress"] = {"done": done, "total": total, "label": label}

    def activity(self, n_bytes: int = 0) -> None:
        """Note that the engine produced output (cheap; no disk write)."""
        with self._lock:
            self.state["last_activity"] = self._wall()
            self.state["output_bytes"] += n_bytes

    def child_started(self, name: str, args: list[str], pid: int | None) -> None:
        """An ArgyllCMS process started (arguments must already be redacted)."""
        with self._lock:
            self.state["child"] = {
                "name": name,
                "args": args,
                "pid": pid,
                "started": self._wall(),
            }
            self.state["child_exit"] = None
            self._save()
            self.event("child_started", name=name, pid=pid)

    def child_exited(self, retcode: int | None, error: str | None = None) -> None:
        """The ArgyllCMS process ended (``retcode`` may be negative: a signal)."""
        with self._lock:
            self.state["child_exit"] = {
                "code": retcode,
                "error": error,
                "time": self._wall(),
            }
            self._save()
            self.event("child_exited", code=retcode, error=error)

    def block_done(self, number: int, total: int) -> None:
        """A measurement block finished and its data is durably stored."""
        with self._lock:
            if number not in self.state["blocks_done"]:
                self.state["blocks_done"].append(number)
            self.state["progress"] = {"done": number, "total": total, "label": "blocks"}
            self._save()
            self.event("block_done", number=number, total=total)

    def event(self, kind: str, **data: object) -> None:
        """Append an event to the trail (never raises)."""
        try:
            line = json.dumps({"t": self._wall(), "e": kind, **data}, default=str)
            with open(
                os.path.join(self.dir, "events.jsonl"), "a", encoding="utf-8"
            ) as f:
                f.write(line + "\n")
                f.flush()
        except OSError:
            self.write_errors += 1
        if self.sink is not None:
            try:
                self.sink(kind, data)
            except Exception:  # noqa: BLE001 - mirroring must never break a session
                self.sink = None

    # -- durable copies ---------------------------------------------------
    def checkpoint(self, path: str, name: str | None = None) -> bool:
        """Durably copy ``path`` into the session; keep the previous good copy.

        Returns ``False`` (and counts the error) if the copy failed, e.g. disk
        full; the previous copy is then still intact.
        """
        name = name or os.path.basename(path)
        dst = os.path.join(self.dir, "files", name)
        tmp = f"{dst}.tmp-{os.getpid()}"
        try:
            shutil.copyfile(path, tmp)
            with open(tmp, "rb") as f:
                os.fsync(f.fileno())
            if os.path.exists(dst):
                os.replace(dst, f"{dst}.prev")
            os.replace(tmp, dst)
        except OSError as exc:
            self.write_errors += 1
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            self.event("checkpoint_failed", name=name, error=str(exc))
            return False
        return True

    # -- heartbeat --------------------------------------------------------
    def start_heartbeat(
        self,
        sampler: Callable[[], dict] | None = None,
        interval: float = HEARTBEAT_S,
    ) -> None:
        """Record a heartbeat every ``interval`` seconds on a daemon thread."""
        self.stop_heartbeat()
        self._stop.clear()

        def run() -> None:
            while not self._stop.wait(interval):
                self.beat(sampler)

        self._hb = threading.Thread(target=run, name="session-heartbeat", daemon=True)
        self._hb.start()

    def stop_heartbeat(self) -> None:
        """Stop the heartbeat thread."""
        self._stop.set()
        if self._hb is not None and self._hb is not threading.current_thread():
            self._hb.join(timeout=2)
        self._hb = None

    def beat(self, sampler: Callable[[], dict] | None = None) -> None:
        """One heartbeat: time gap evidence, samples, persisted state."""
        with self._lock:
            now, mono = self._wall(), self._mono()
            slept = max(0.0, (now - self._last_wall) - (mono - self._last_mono))
            if slept > 5:
                self.state["slept_seconds"] += slept
                self.event("suspend_gap", seconds=round(slept, 1))
            self._last_wall, self._last_mono = now, mono
            self.state["last_heartbeat"] = now
            if sampler is not None:
                try:
                    sample = sampler()
                except Exception as exc:  # noqa: BLE001 - sampling must never stop a run
                    sample = {"sampler_error": str(exc)}
                sample["t"] = now
                samples = self.state["samples"]
                samples.append(sample)
                if len(samples) > 200:  # keep first, last and a thinned middle
                    del samples[1:-100:2]
            self._save()

    def _save(self) -> None:
        try:
            _atomic_json(os.path.join(self.dir, "session.json"), self.state)
        except OSError as exc:
            self.write_errors += 1
            self.event("state_write_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Startup: find sessions that did not end cleanly.


@dataclass
class IncompleteSession:
    """A session found at start-up that never recorded an outcome."""

    dir: str
    state: dict
    facts: list[tuple[str, dict]] = field(default_factory=list)

    @property
    def id(self) -> str:
        """Session identifier."""
        return self.state.get("id", os.path.basename(self.dir))


def load_state(session_dir: str) -> dict | None:
    """Read a session's state, or ``None`` if unreadable."""
    try:
        with open(os.path.join(session_dir, "session.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def diagnose(state: dict, now: float | None = None) -> list[tuple[str, dict]]:
    """List what is *known* about how the session ended (key, parameters).

    The keys are language keys (``recover.fact.*``); this never states a cause,
    only facts. An empty trail of facts is itself reported (``unknown``).
    """
    now = now if now is not None else time.time()
    facts: list[tuple[str, dict]] = []
    hb = state.get("last_heartbeat") or state.get("started", now)
    facts.append(("recover.fact.last_seen", {"time": hb}))
    prog = state.get("progress")
    if prog:
        facts.append(("recover.fact.progress", dict(prog)))
    facts.append(("recover.fact.stage", {"stage": state.get("stage")}))
    ce = state.get("child_exit")
    if ce:
        facts.append(("recover.fact.child_exit", dict(ce)))
    elif state.get("child"):
        facts.append(("recover.fact.child_no_exit", {"pid": state["child"].get("pid")}))
    if state.get("slept_seconds", 0) > 60:
        facts.append(("recover.fact.slept", {"seconds": state["slept_seconds"]}))
    samples = state.get("samples") or []
    rss = [s["app_rss"] for s in samples if "app_rss" in s]
    if len(rss) >= 2:
        facts.append(
            ("recover.fact.memory", {"first": rss[0], "last": rss[-1], "max": max(rss)})
        )
    free = [s["disk_free"] for s in samples if "disk_free" in s]
    if free:
        facts.append(("recover.fact.disk", {"last_free": free[-1]}))
    if not state.get("clean_exit"):
        facts.append(("recover.fact.no_clean_exit", {}))
    if state.get("outcome") is None and not ce and not samples:
        facts.append(("recover.fact.unknown", {}))
    return facts


def _nothing_measured(state: dict) -> bool:
    """A session that never measured anything (no plan, no progress)."""
    return (
        not state.get("plan")
        and not state.get("progress")
        and not state.get("blocks_done")
        and (state.get("child_exit") is not None or state.get("child") is None)
    )


def scan_incomplete(root: str) -> list[IncompleteSession]:
    """Sessions under ``root`` that never recorded an outcome and are not running."""
    found: list[IncompleteSession] = []
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return found
    for name in names:
        d = os.path.join(root, name)
        state = load_state(d) if os.path.isdir(d) else None
        if not state or state.get("outcome") is not None:
            continue
        if (
            state.get("app_pid")
            and pid_alive(state["app_pid"])
            and state["app_pid"] != os.getpid()
        ):
            continue  # another running instance owns it
        if state.get("app_pid") == os.getpid():
            continue  # this very process
        if _nothing_measured(state):
            continue  # a probe or an aborted start: nothing to recover
        found.append(IncompleteSession(d, state, diagnose(state)))
    return found


def prune_finished(root: str, keep_days: float = 30, now: float | None = None) -> int:
    """Delete journals of sessions that ended (or were reviewed) long ago.

    A session that never recorded an outcome is never touched here: only the
    user decides about it (:func:`mark_reviewed`). Returns the number removed.
    """
    now = now if now is not None else time.time()
    removed = 0
    try:
        names = os.listdir(root)
    except OSError:
        return 0
    for name in names:
        d = os.path.join(root, name)
        state = load_state(d) if os.path.isdir(d) else None
        if not state or state.get("outcome") is None:
            continue
        ended = state.get("reviewed") or state.get("last_heartbeat") or 0
        if now - ended > keep_days * 86400:
            shutil.rmtree(d, ignore_errors=True)
            removed += 1
    return removed


def mark_reviewed(session_dir: str, action: str) -> None:
    """Record the user's decision so the session is not offered again."""
    state = load_state(session_dir)
    if state is None:
        return
    state["outcome"] = f"reviewed:{action}"
    state["reviewed"] = time.time()
    _atomic_json(os.path.join(session_dir, "session.json"), state)


def export_session(session_dir: str, dest: str) -> str:
    """Copy everything recoverable from a session to ``dest`` (never moves it)."""
    target = os.path.join(dest, os.path.basename(session_dir))
    shutil.copytree(session_dir, target, dirs_exist_ok=True)
    return target


def resume_plan(state: dict, current_fingerprint: str) -> dict:
    """What can be continued: only blocks not yet done, only if conditions match.

    Returns ``{"possible": bool, "remaining": [...], "reason": key|None}``. A
    block run cannot be resumed from the middle of a block (ArgyllCMS has no
    such option); the interrupted block is measured again from its start.
    """
    plan = state.get("plan") or {}
    total = plan.get("blocks")
    if not total:
        return {"possible": False, "remaining": [], "reason": "recover.no_blocks"}
    done = set(state.get("blocks_done", []))
    remaining = [n for n in range(1, total + 1) if n not in done]
    if plan.get("fingerprint") != current_fingerprint:
        return {
            "possible": False,
            "remaining": remaining,
            "reason": "recover.conditions_changed",
        }
    return {"possible": bool(remaining), "remaining": remaining, "reason": None}
