"""Diagnostics for the user and for support (local only, nothing is sent).

Builds on what already exists instead of a parallel mechanism:

* the application log (:mod:`DisplayCAL.log`) -- now bounded, with an ISO time,
  a level and the run's session ID on every line;
* the session journal (:mod:`DisplayCAL.session_journal`) -- its events are
  mirrored into that log under the journal's own session ID, so a measurement
  can be followed across both;
* the redactor (:mod:`DisplayCAL.redaction`, shared with the feedback dialog).

This module adds structured events, crash/unclean-exit evidence, the versions
report and the export of a support package: a ZIP the user creates, inspects
and sends by their own decision. Measurements, ICC profiles and system crash
reports are included only when the user chooses them; memory dumps never.
"""

from __future__ import annotations

import atexit
import contextlib
import faulthandler
import hashlib
import importlib.metadata
import json
import logging
import os
import platform
import sys
import threading
import time
import traceback
import zipfile
from dataclasses import dataclass, field

from DisplayCAL import log as dlog
from DisplayCAL.redaction import redact

#: Stable file names kept in the log directory.
LAST_RUN_FILE = "last_run.json"
CRASH_PREFIX = "crash-"
MAX_CRASH_FILES = 5
#: Per-file and total caps for what goes into a package.
LOG_TAIL_BYTES = 2 * 1024 * 1024
MAX_LOG_FILES = 4
MAX_SESSIONS = 3
DEBUG_MINUTES = 60

_LEVELS = {
    "trace": 5,
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}
logging.addLevelName(5, "TRACE")

_crash_file = None
_debug_timer: threading.Timer | None = None


# --------------------------------------------------------------------------
# Structured events


def event(
    level: str,
    subsystem: str,
    event_id: str,
    message: str = "",
    job: str | None = None,
    **fields: object,
) -> None:
    """Write one structured event to the application log (never raises).

    Args:
        level: ``trace`` .. ``critical``.
        subsystem: Short area name (``startup``, ``instrument``, ``argyll``,
            ``measure``, ``update``, ``deps``, ``app``).
        event_id: Stable identifier (``measure.block_done``), searchable by support.
        message: Short human text.
        job: Correlation ID of a job (the session journal ID for a measurement).
        **fields: Safe context as ``key=value`` pairs.
    """
    try:
        logger = dlog.LOGGER
        if logger is None:
            return
        parts = [f"event={event_id}", f"subsystem={subsystem}"]
        if job:
            parts.append(f"job={job}")
        parts += [f"{k}={_short(v)}" for k, v in fields.items()]
        text = " ".join(parts) + (f" | {message}" if message else "")
        logger.log(_LEVELS.get(level, logging.INFO), text)
    except Exception:  # noqa: BLE001 - diagnostics must never change an outcome
        return


def log_environment(worker: object | None = None) -> None:
    """Log the versions and dependency state once (start-up evidence)."""
    fields = {
        label.lower().replace(" ", "_"): value
        for label, value in versions_report(worker)
        if label != "ArgyllCMS folder"
    }
    event("info", "deps", "deps.report", **fields)


def _short(value: object, limit: int = 200) -> str:
    text = str(value).replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


def journal_sink_for(journal: object):
    """Mirror a session journal's events into the log under the journal's ID.

    The ID is read when each event is written (the journal assigns it in
    ``begin``, after the sink is installed).
    """

    def sink(kind: str, data: dict) -> None:
        job_id = getattr(journal, "id", "") or None
        level = "error" if kind in ("flood", "state_write_failed") else "info"
        reserved = {"level", "subsystem", "event_id", "message", "job"}
        safe = {(f"{k}_" if k in reserved else k): v for k, v in data.items()}
        event(level, "measure", f"measure.{kind}", job=job_id, **safe)

    return sink


# --------------------------------------------------------------------------
# Crash and unclean-exit evidence


def install_crash_hooks(logdir: str | None = None) -> None:
    """Record Python-level crashes and detect that the previous run ended badly.

    * unhandled exceptions (main and other threads) are logged with the
      traceback, then passed on to the previous handler;
    * ``faulthandler`` writes native crash tracebacks to a per-run file in the
      log directory (removed again at a clean exit if empty);
    * ``last_run.json`` says whether the previous run ended cleanly.
    """
    logdir = logdir or dlog._LOGDIR
    if not logdir:
        return
    with contextlib.suppress(OSError):
        os.makedirs(logdir, exist_ok=True)
    _check_previous_run(logdir)

    previous = sys.excepthook

    def hook(etype, value, tb) -> None:
        event(
            "critical",
            "app",
            "app.unhandled_exception",
            error=etype.__name__,
            message_text=_short(value),
        )
        _log_traceback("".join(traceback.format_exception(etype, value, tb)))
        previous(etype, value, tb)

    sys.excepthook = hook
    prev_thread = threading.excepthook

    def thread_hook(args) -> None:
        event(
            "critical",
            "app",
            "app.unhandled_thread_exception",
            thread=getattr(args.thread, "name", "?"),
            error=args.exc_type.__name__,
        )
        _log_traceback(
            "".join(
                traceback.format_exception(
                    args.exc_type, args.exc_value, args.exc_traceback
                )
            )
        )
        prev_thread(args)

    threading.excepthook = thread_hook

    global _crash_file
    try:
        path = os.path.join(logdir, f"{CRASH_PREFIX}{dlog.APP_SESSION_ID}.txt")
        _crash_file = open(path, "w", encoding="utf-8")  # noqa: SIM115 - kept open
        faulthandler.enable(file=_crash_file, all_threads=True)
    except OSError:
        _crash_file = None
    _prune_crash_files(logdir)
    _write_last_run(logdir, clean=False)
    atexit.register(mark_clean_exit, logdir)


def _log_traceback(text: str) -> None:
    logger = dlog.LOGGER
    if logger is None:
        return
    for line in text.rstrip().splitlines():
        logger.error("  " + line)


def _check_previous_run(logdir: str) -> None:
    path = os.path.join(logdir, LAST_RUN_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            prev = json.load(f)
    except (OSError, ValueError):
        return
    if prev.get("clean") is False:
        event(
            "warning",
            "app",
            "app.previous_run_unclean",
            "the previous run did not record a normal shutdown",
            previous_session=prev.get("session"),
            previous_started=prev.get("started"),
        )


_STARTED = time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _write_last_run(logdir: str, clean: bool) -> None:
    from DisplayCAL.session_journal import _atomic_json

    with contextlib.suppress(Exception):
        _atomic_json(
            os.path.join(logdir, LAST_RUN_FILE),
            {
                "session": dlog.APP_SESSION_ID,
                "started": _STARTED,
                "clean": clean,
            },
        )


def mark_clean_exit(logdir: str | None = None) -> None:
    """Record a normal shutdown (called at exit and before a fast exit)."""
    logdir = logdir or dlog._LOGDIR
    if not logdir:
        return
    event("info", "app", "app.exit", "normal shutdown")
    _write_last_run(logdir, clean=True)
    global _crash_file
    if _crash_file is not None:
        path = _crash_file.name
        with contextlib.suppress(Exception):
            faulthandler.disable()
            _crash_file.close()
            if os.path.getsize(path) == 0:
                os.remove(path)
        _crash_file = None


def _prune_crash_files(logdir: str) -> None:
    try:
        names = sorted(
            n
            for n in os.listdir(logdir)
            if n.startswith(CRASH_PREFIX) and n.endswith(".txt")
        )
    except OSError:
        return
    stale = []
    for n in names:
        p = os.path.join(logdir, n)
        if n != f"{CRASH_PREFIX}{dlog.APP_SESSION_ID}.txt" and (
            os.path.getsize(p) == 0 if os.path.exists(p) else False
        ):
            stale.append(p)
    for p in stale:
        with contextlib.suppress(OSError):
            os.remove(p)
    names = [n for n in names if os.path.join(logdir, n) not in stale]
    for n in names[: max(0, len(names) - MAX_CRASH_FILES)]:
        with contextlib.suppress(OSError):
            os.remove(os.path.join(logdir, n))


# --------------------------------------------------------------------------
# Temporary debug


def set_debug(enabled: bool) -> None:
    """Switch detailed logging on for this run only; it switches itself off.

    Never persisted: the next start is back to ``info``. A timer turns it off
    after :data:`DEBUG_MINUTES` minutes.
    """
    global _debug_timer
    logger = dlog.LOGGER
    if logger is None:
        return
    if _debug_timer is not None:
        _debug_timer.cancel()
        _debug_timer = None
    logger.setLevel(logging.DEBUG if enabled else dlog.LOGLEVEL)
    event("info", "app", "app.debug_on" if enabled else "app.debug_off")
    if enabled:
        _debug_timer = threading.Timer(DEBUG_MINUTES * 60, set_debug, args=(False,))
        _debug_timer.daemon = True
        _debug_timer.start()


def debug_enabled() -> bool:
    """Whether detailed logging is currently on."""
    return bool(dlog.LOGGER and dlog.LOGGER.level <= logging.DEBUG)


# --------------------------------------------------------------------------
# Versions


def _pkg_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "—"


def versions_report(worker: object | None = None) -> list[tuple[str, str]]:
    """Application, system and relevant dependency versions as (label, value)."""
    from DisplayCAL import support
    from DisplayCAL.meta import VERSION_STRING

    rows: list[tuple[str, str]] = [
        ("Application", support.app_version_line()),
        ("Version", VERSION_STRING),
        ("Platform", support.platform_line()),
        ("Python", platform.python_version()),
        ("Run session ID", dlog.APP_SESSION_ID),
    ]
    try:
        from qtpy import QtCore

        rows.append(("Qt", QtCore.qVersion()))
    except ImportError:
        pass
    for pkg in ("PySide6", "qtpy", "numpy", "Pillow", "PyYAML"):
        version = _pkg_version(pkg)
        if version == "—" and pkg == "PyYAML":
            with contextlib.suppress(Exception):
                import yaml

                version = getattr(yaml, "__version__", "—")
        rows.append((pkg, version))
    try:
        from DisplayCAL import argyll

        found = argyll.check_argyll_bin()
        rows.append(("ArgyllCMS found", "yes" if found else "no"))
        if found:
            rows.append(
                (
                    "ArgyllCMS version",
                    ".".join(
                        str(n)
                        for n in argyll.get_argyll_version("dispcal", silent=True)
                    ),
                )
            )
            rows.append(("ArgyllCMS folder", str(argyll.get_argyll_util("dispcal") or "")))
    except Exception as exc:  # noqa: BLE001
        rows.append(("ArgyllCMS", f"could not be checked ({type(exc).__name__})"))
    if worker is not None:
        with contextlib.suppress(Exception):
            rows.append(("Displays", str(len(getattr(worker, "displays", [])))))
            rows.append(
                (
                    "Instruments",
                    ", ".join(getattr(worker, "instruments", []) or []) or "none",
                )
            )
    return rows


def versions_text(worker: object | None = None, redacted: bool = True) -> str:
    """The versions report as text."""
    text = "\n".join(f"{k}: {v}" for k, v in versions_report(worker))
    return redact(text) if redacted else text


# --------------------------------------------------------------------------
# Support package


@dataclass
class Category:
    """One kind of content that may go into the package."""

    key: str
    default: bool
    optional: bool  # needs an explicit choice and explanation
    files: list[str] = field(default_factory=list)

    @property
    def size(self) -> int:
        """Total size in bytes of the files (before redaction)."""
        total = 0
        for p in self.files:
            with contextlib.suppress(OSError):
                total += os.path.getsize(p)
        return total


def _newest(paths: list[str], count: int) -> list[str]:
    return sorted(paths, key=lambda p: os.path.getmtime(p), reverse=True)[:count]


def plan_package(
    logdir: str | None = None,
    sessions_root: str | None = None,
    display_profile: str | None = None,
) -> list[Category]:
    """What could go into a package, with the default choice for each category."""
    from DisplayCAL import config

    logdir = logdir or dlog._LOGDIR or config.LOGDIR
    sessions_root = sessions_root or os.path.join(config.DATA_HOME, "sessions")
    logs: list[str] = []
    crashes: list[str] = []
    with contextlib.suppress(OSError):
        for n in os.listdir(logdir):
            p = os.path.join(logdir, n)
            if n.startswith(CRASH_PREFIX) and os.path.getsize(p) > 0:
                crashes.append(p)
            elif ".log" in n and os.path.isfile(p):
                logs.append(p)
    sessions: list[str] = []
    measurements: list[str] = []
    with contextlib.suppress(OSError):
        dirs = [
            os.path.join(sessions_root, n)
            for n in os.listdir(sessions_root)
            if os.path.isdir(os.path.join(sessions_root, n))
        ]
        for d in _newest(dirs, MAX_SESSIONS):
            for n in ("session.json", "events.jsonl"):
                if os.path.isfile(os.path.join(d, n)):
                    sessions.append(os.path.join(d, n))
            files_dir = os.path.join(d, "files")
            if os.path.isdir(files_dir):
                measurements += [
                    os.path.join(files_dir, n)
                    for n in os.listdir(files_dir)
                    if n.endswith((".ti1", ".ti3", ".ti2"))
                ]
    system_reports: list[str] = []
    if sys.platform == "darwin":
        rep = os.path.expanduser("~/Library/Logs/DiagnosticReports")
        with contextlib.suppress(OSError):
            system_reports = _newest(
                [
                    os.path.join(rep, n)
                    for n in os.listdir(rep)
                    if n.lower().startswith(("displaycal", "python"))
                ],
                3,
            )
    return [
        Category("versions", True, False, []),
        Category("logs", True, False, _newest(logs, MAX_LOG_FILES)),
        Category("sessions", True, False, sessions),
        Category("crashes", True, False, crashes),
        Category("measurements", False, True, measurements),
        Category("profile", False, True, [display_profile] if display_profile else []),
        Category("system_reports", False, True, system_reports),
    ]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_text_tail(path: str, limit: int) -> str:
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - limit))
        data = f.read()
    text = data.decode("utf-8", "replace")
    if size > limit:
        text = f"[… earlier part of the file omitted: {size - limit} bytes …]\n" + text
    return text


def export_package(
    dest: str,
    selected: set[str],
    categories: list[Category] | None = None,
    worker: object | None = None,
    redact_text: bool = True,
    readme: str = "",
) -> dict:
    """Create the support ZIP at ``dest`` and return its manifest.

    Only categories in ``selected`` are included, and only the ones that exist.
    Text is redacted unless ``redact_text`` is False. The ZIP is written to a
    temporary name and renamed, so an interrupted export leaves no broken file.
    """
    from DisplayCAL import support

    categories = categories if categories is not None else plan_package()
    entries: list[dict] = []
    tmp = dest + ".part"

    def clean(text: str) -> str:
        return redact(text) if redact_text else text

    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:

            def add(name: str, data: bytes, category: str) -> None:
                z.writestr(name, data)
                entries.append(
                    {
                        "file": name,
                        "category": category,
                        "bytes": len(data),
                        "sha256": _sha256(data),
                    }
                )

            if "versions" in selected:
                add(
                    "environment.txt",
                    versions_text(worker, redact_text).encode("utf-8"),
                    "versions",
                )
            for cat in categories:
                if cat.key not in selected:
                    continue
                for p in cat.files:
                    base = os.path.basename(p)
                    try:
                        if cat.key in ("logs", "crashes"):
                            add(
                                f"{cat.key}/{base}",
                                clean(_read_text_tail(p, LOG_TAIL_BYTES)).encode(),
                                cat.key,
                            )
                        elif cat.key == "sessions":
                            sid = os.path.basename(os.path.dirname(p))
                            add(
                                f"sessions/{sid}/{base}",
                                clean(_read_text_tail(p, LOG_TAIL_BYTES)).encode(),
                                cat.key,
                            )
                        elif cat.key == "system_reports":
                            add(
                                f"system_reports/{base}",
                                clean(_read_text_tail(p, LOG_TAIL_BYTES)).encode(),
                                cat.key,
                            )
                        elif cat.key in ("measurements", "profile"):
                            with open(p, "rb") as f:
                                add(f"{cat.key}/{base}", f.read(), cat.key)
                    except OSError as exc:
                        entries.append(
                            {"file": base, "category": cat.key, "error": type(exc).__name__}
                        )
            manifest = {
                "format": 1,
                "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "application": support.app_version_line(),
                "platform": support.platform_line(),
                "run_session_id": dlog.APP_SESSION_ID,
                "text_redacted": redact_text,
                "included_categories": sorted(selected),
                "never_included": [
                    "memory dumps",
                    "personal files",
                    "passwords, tokens, keys",
                ],
                "not_included_unless_chosen": [
                    c.key for c in categories if c.optional and c.key not in selected
                ],
                "files": entries,
            }
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
            z.writestr("README.txt", readme or _default_readme(manifest))
        os.replace(tmp, dest)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise
    event("info", "app", "app.diagnostic_exported", files=len(entries), redacted=redact_text)
    return manifest


def _default_readme(manifest: dict) -> str:
    return (
        "DisplayCAL-CG diagnostic package\n"
        "================================\n"
        "Created by the application on the user's computer and saved where the user chose.\n"
        "Nothing was uploaded. Open it with any ZIP tool; every file is plain text\n"
        "except the optional attachments (measurement files, ICC profile).\n\n"
        "manifest.json    what is inside, sizes, checksums, and what was left out\n"
        "environment.txt  application, system and dependency versions\n"
        "logs/            application log (rotated); lines: time, level, [run id], message\n"
        "sessions/<id>/   measurement session journal: session.json (state) and\n"
        "                 events.jsonl (stages, ArgyllCMS process start/exit, progress)\n"
        "crashes/         native crash tracebacks, if any\n\n"
        f"Text redacted: {manifest['text_redacted']} (user name, home paths, e-mail, tokens,\n"
        "network and hardware identifiers removed).\n"
    )
