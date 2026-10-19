# ruff: noqa: ANN001, ANN201, C901, SIM105, E501  (Worker-style signatures; one long method)
"""Session safety for the Worker: journal, evidence, sleep prevention, blocks.

Mixed into :class:`DisplayCAL.worker.Worker`. It wraps the existing command
execution instead of replacing it: a measurement session starts with the first
measuring ArgyllCMS command and ends in ``wrapup``; while it runs, a heartbeat
records the facts needed to understand a stop (see
:mod:`DisplayCAL.session_journal`).

It also guards against a runaway engine: ArgyllCMS can print the same line
forever when its input is gone (observed: 4 GB in seconds with ``dispread`` and
a closed input). An unbounded log or memory buffer is a plausible way for an
application to die during a long run, so a flood is detected, recorded and the
process is stopped with a clear message instead of being logged without limit.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import tempfile
import time

from DisplayCAL import (
    config,
    keep_awake,
    measured_speed,
    measurement_blocks,
    measurement_plan,
    session_journal,
)
from DisplayCAL import localization as lang
from DisplayCAL.config import getcfg
from DisplayCAL import diagnostics
from DisplayCAL.support import redact
from DisplayCAL.worker_base import Error

_PATCH_RE = re.compile(r"patch (\d+) of (\d+)", re.I)
MEASURING = ("dispcal", "dispread", "spotread", "chartread", "ccxxmake", "i1d3ccss")
#: Identical consecutive writes before the process is considered to be looping.
FLOOD_LINES = 100_000
#: Hard cap on the engine output counted per session (bytes).
FLOOD_BYTES = 512 * 1024 * 1024


class SessionMixin:
    """Journal, heartbeat, sleep prevention and flood guard for a Worker."""

    session_journal: session_journal.SessionJournal | None = None
    _awake: keep_awake.KeepAwake | None = None
    #: Optional ``callable(outcome, reason)`` invoked when a session ends.
    on_session_end = None
    _flood_last = None
    _flood_count = 0
    _flood_reported = False
    _ckpt_mtimes: dict | None = None
    #: ``(patches done before this block, total patches)`` while measuring blocks.
    _block_ctx: tuple[int, int] | None = None
    #: Directory of an earlier, unfinished session whose finished blocks are reused.
    resume_from: str | None = None

    # -- durable work directory -------------------------------------------
    def create_tempdir(self):  # noqa: D102 - same contract as WorkerBase
        """Create the working directory under the application data, not /tmp.

        System temporary folders are cleaned by the operating system and are
        not where a user would look after a stop; measurements written there
        were the only copy of a long run.
        """
        if self.tempdir and os.path.isdir(self.tempdir):
            return self.tempdir
        root = os.path.join(config.DATA_HOME, "work")
        try:
            os.makedirs(root, exist_ok=True)
            self.tempdir = tempfile.mkdtemp(prefix=f"{config.APPNAME}-", dir=root)
        except OSError:
            self.tempdir = None
            return super().create_tempdir()
        return self.tempdir

    # -- session lifecycle -------------------------------------------------
    def _session_root(self) -> str:
        return os.path.join(config.DATA_HOME, "sessions")

    def _session_info(self) -> dict:
        from DisplayCAL import meta

        cc = getcfg("colorimeter_correction_matrix_file", False) or ""
        cc_path = cc.split(":", 1)[-1] if ":" in cc else cc
        chart = getcfg("testchart.file", False) or ""
        return {
            "app": f"{meta.VERSION_STRING}-cg.{meta.CG_BUILD}",
            "argyll": ".".join(str(v) for v in getattr(self, "argyll_version", [])),
            "display_no": getcfg("display.number"),
            "display": getattr(self, "get_display_name", lambda *a: "")(),
            "instrument_no": getcfg("comport.number"),
            "measurement_mode": getcfg("measurement_mode"),
            "correction": os.path.basename(cc_path),
            "correction_digest": session_journal.file_digest(cc_path)
            if cc_path
            else None,
            "testchart": os.path.basename(chart),
            "profile_type": getcfg("profile.type"),
            "profile_name": getcfg("profile.name.expanded") or getcfg("profile.name"),
        }

    def session_fingerprint(self) -> str:
        """Hash of the conditions that must match for blocks to be combined."""
        info = self._session_info()
        keys = (
            "display_no",
            "display",
            "instrument_no",
            "measurement_mode",
            "correction_digest",
            "argyll",
            "profile_type",
        )
        return session_journal.fingerprint({k: info.get(k) for k in keys})

    def session_begin(self) -> None:
        """Start the journal, heartbeat and sleep prevention (idempotent)."""
        if self.session_journal is not None:
            return
        try:
            j = session_journal.SessionJournal(self._session_root())
            j.sink = diagnostics.journal_sink_for(j)
            j.begin(self._session_info())
        except OSError:
            return  # a journal problem must never stop a measurement
        self.session_journal = j
        self._flood_last, self._flood_count, self._flood_reported = None, 0, False
        self._ckpt_mtimes = {}
        j.start_heartbeat(self._session_sample)
        if getcfg("session.keep_awake"):
            self._awake = keep_awake.KeepAwake()
            status = self._awake.acquire()
            j.event(
                "keep_awake",
                active=status.active,
                method=status.method,
                error=status.error,
            )

    def session_end(self, outcome: str, reason: str | None = None) -> None:
        """End the session: record the outcome, release sleep prevention."""
        j = self.session_journal
        if j is None:
            return
        self._session_checkpoint()
        j.finish(outcome, reason)
        if self._awake is not None:
            self._awake.release()
            self._awake = None
        self.session_journal = None
        cb = self.on_session_end
        if cb is not None:
            try:
                cb(outcome, reason)
            except Exception:  # noqa: BLE001 - a UI callback must not break cleanup
                pass

    def session_awake_status(self):
        """The current sleep-prevention status, or ``None`` outside a session."""
        return self._awake.status if self._awake is not None else None

    # -- evidence ----------------------------------------------------------
    def _session_sample(self) -> dict:
        sample: dict = {}
        try:
            import psutil

            sample["app_rss"] = psutil.Process().memory_info().rss
            child = getattr(self, "subprocess", None)
            pid = getattr(child, "pid", None)
            if pid:
                try:
                    cp = psutil.Process(pid)
                    sample["child_rss"] = cp.memory_info().rss
                    sample["child_status"] = cp.status()
                except psutil.Error:
                    sample["child_status"] = "gone"
        except ImportError:
            pass
        j = self.session_journal
        if j is not None:
            try:
                sample["disk_free"] = shutil.disk_usage(j.dir).free
            except OSError:
                pass
        self._session_checkpoint()
        return sample

    def _session_checkpoint(self) -> None:
        """Durably copy measurement files that changed since the last time."""
        j, d = self.session_journal, self.tempdir
        if j is None or not d or not os.path.isdir(d) or self._ckpt_mtimes is None:
            return
        try:
            names = os.listdir(d)
        except OSError:
            return
        for name in names:
            if not name.lower().endswith(
                (".ti1", ".ti3", ".cal", ".icc", ".icm", ".log")
            ):
                continue
            path = os.path.join(d, name)
            try:
                mt = os.stat(path).st_mtime
            except OSError:
                continue
            if self._ckpt_mtimes.get(name) != mt and j.checkpoint(path):
                self._ckpt_mtimes[name] = mt

    def _session_output(self, txt: str) -> bool:
        """Note engine output; return ``True`` if it must be dropped (flood)."""
        j = self.session_journal
        if j is None:
            return False
        n = len(txt)
        j.activity(n)
        m = _PATCH_RE.search(txt)
        if m:
            done = int(m.group(1))
            total = int(m.group(2))
            ctx = self._block_ctx
            if ctx:
                done, total = done + ctx[0], ctx[1]
            j.progress(done, total, "patches")
        if txt == self._flood_last:
            self._flood_count += 1
        else:
            self._flood_last, self._flood_count = txt, 0
        over_bytes = j.state["output_bytes"] > FLOOD_BYTES
        if self._flood_count >= FLOOD_LINES or over_bytes:
            if not self._flood_reported:
                self._flood_reported = True
                j.event(
                    "output_flood",
                    repeats=self._flood_count,
                    bytes=j.state["output_bytes"],
                )
                self.log(
                    "Error - the measurement engine is repeating the same output without "
                    "end; it was stopped to protect your data and disk."
                )
                self.subprocess_abort = True
            return True
        return False

    # -- command wrapper ---------------------------------------------------
    def exec_cmd(self, cmd, args=None, *a, **kw):
        """Run a command; measuring commands are journaled (see module doc)."""
        name = os.path.splitext(os.path.basename(str(cmd)))[0]
        # ``-?`` / ``-??`` only print the usage text (capability probes at
        # start-up): not a measurement, so no session and no sleep prevention.
        probe = any(str(a).startswith("-?") for a in (args or []))
        measuring = name in MEASURING and not probe
        if measuring:
            self.session_begin()
        j = self.session_journal
        if measuring and j is not None:
            j.stage(name)
            j.child_started(name, [redact(str(x)) for x in (args or [])], None)
        t0 = time.time()
        try:
            result = self._exec_cmd_impl(cmd, args, *a, **kw)
        except BaseException as exc:
            if measuring and j is not None:
                j.child_exited(getattr(self, "retcode", None), error=repr(exc))
            raise
        if measuring and j is not None:
            err = result if isinstance(result, Exception) else None
            j.child_exited(
                getattr(self, "retcode", None), error=str(err) if err else None
            )
            j.event(
                "child_result",
                ok=bool(result) and err is None,
                seconds=round(time.time() - t0, 1),
            )
        return result

    # -- measurement in blocks -----------------------------------------------
    def blocks_supported(self) -> tuple[bool, str]:
        """Whether this instrument can be measured in consecutive blocks.

        Instruments that must be calibrated on a reference tile or dark cap
        (Argyll ``sensor_cal``) would ask for that between blocks, so they run
        as a single block. Returns ``(ok, language key explaining a "no")``.
        """
        from DisplayCAL.argyll_instruments import (
            get_canonical_instrument_name,
            instruments,
        )

        try:
            name = get_canonical_instrument_name(self.get_instrument_name())
        except Exception:  # noqa: BLE001
            return False, "blocks.no_instrument"
        entry = instruments.get(name)
        if entry is None:
            return False, "blocks.unknown_instrument"
        if entry.get("sensor_cal") is False or entry.get("skip_sensor_cal"):
            return True, ""
        return False, "blocks.needs_calibration"

    def measure_main(self, cmd, args2, args):
        """Run the profiling measurement; in blocks when configured and safe.

        Without blocks this is exactly one ``exec_cmd`` call, as before.
        """
        size = int(getcfg("measurement.block_size") or 0)
        base = args[-1]
        ti1 = f"{base}.ti1"
        ok, _why = self.blocks_supported()
        if size <= 0 or not ok or not os.path.isfile(ti1):
            return self._single_run(cmd, args2, ti1)
        reused: dict[int, str] = {}
        if self.resume_from:
            outcome = self._resume_prepare(ti1, size)
            if isinstance(outcome, Exception):
                return outcome
            reused = outcome
        try:
            table = measurement_blocks.read_table(ti1)
            # The same function the plan on screen uses, so what was shown is
            # what runs.
            if not measurement_plan.make_plan(len(table.rows), size).split:
                return self._single_run(cmd, args2, ti1)
            blocks = measurement_blocks.split_ti1(ti1, os.path.basename(base), size)
        except measurement_blocks.CGATSError as exc:
            self.log(f"Blocks not used: {exc}")
            return self.exec_cmd(cmd, args2)
        self.session_begin()
        j = self.session_journal
        total = len(table.rows)
        if j is not None:
            j.set_plan(
                {
                    "blocks": len(blocks),
                    "patches": total,
                    "block_size": size,
                    "fingerprint": self.session_fingerprint(),
                    "chart_digest": session_journal.file_digest(ti1),
                }
            )
            j.checkpoint(ti1, "chart.full.ti1")
            for name in self._session_extra_files():
                j.checkpoint(name)
        shown = measurement_plan.make_plan(total, size)
        self.log(
            f"Measuring {total} patches in {shown.blocks} blocks of at most "
            f"{shown.per_block} (+1 repeated white each; {shown.readings} readings)."
        )
        parts: list[str] = []
        done_before = 0
        for blk in blocks:
            if getattr(self, "subprocess_abort", False) or getattr(
                self, "thread_abort", False
            ):
                return None  # cancelled by the user: finished blocks stay stored
            if blk.number in reused:  # finished earlier: reuse, do not measure again
                ti3 = f"{blk.base}.ti3"
                shutil.copyfile(reused[blk.number], ti3)
                if measurement_blocks.block_ti3_valid(ti3, len(blk.row_indices)):
                    parts.append(ti3)
                    done_before += len(blk.row_indices)
                    if j is not None:
                        j.checkpoint(ti3)
                        j.block_done(blk.number, len(blocks))
                    continue
                os.unlink(ti3)  # damaged copy: measure this block again
            blk_args = list(args2[:-1])
            if blk.number > 1 or reused:
                blk_args += [
                    "-N",
                    "-Yp",
                ]  # no new instrument calibration/placement wait
            blk_args.append(blk.base)
            self._block_ctx = (done_before, total)
            if j is not None:
                j.stage("measuring", block=blk.number, blocks=len(blocks))
            started = time.monotonic()
            result = self.exec_cmd(cmd, blk_args)
            self._block_ctx = None
            if isinstance(result, Exception) or not result:
                return result  # earlier blocks remain on disk and in the journal
            self._note_speed(len(blk.row_indices), time.monotonic() - started)
            ti3 = f"{blk.base}.ti3"
            if not measurement_blocks.block_ti3_valid(ti3, len(blk.row_indices)):
                return Error(f"Block {blk.number} produced an incomplete result file.")
            if j is not None:
                j.checkpoint(ti3)
                j.checkpoint(f"{blk.base}.ti1")
                j.block_done(blk.number, len(blocks))
            parts.append(ti3)
            done_before += len(blk.row_indices)
        try:
            measurement_blocks.merge_ti3(parts, ti1, f"{base}.ti3")
        except measurement_blocks.CGATSError as exc:
            return Error(f"The blocks could not be combined: {exc}")
        for blk in blocks:  # the durable copies stay in the session journal
            for ext in (".ti1", ".ti3"):
                try:
                    os.unlink(f"{blk.base}{ext}")
                except OSError:
                    pass
        return True

    def _single_run(self, cmd, args2, ti1):
        """One ``exec_cmd`` over the whole chart, timed for the speed history."""
        started = time.monotonic()
        result = self.exec_cmd(cmd, args2)
        if result is True or (result and not isinstance(result, Exception)):
            try:
                rows = len(measurement_blocks.read_table(ti1).rows)
            except (OSError, measurement_blocks.CGATSError):
                rows = 0
            self._note_speed(rows, time.monotonic() - started)
        return result

    def _note_speed(self, readings: int, seconds: float) -> None:
        """Keep how long a finished piece really took (a hint for the estimate)."""
        try:
            measured_speed.record(self.get_instrument_name(), readings, seconds)
        except Exception as exc:  # noqa: BLE001 - never disturb a measurement
            self.log(f"Speed history not updated: {exc}")

    def _session_extra_files(self) -> list[str]:
        """Calibration/settings files in the work directory worth keeping."""
        d = self.tempdir
        if not d or not os.path.isdir(d):
            return []
        return [
            os.path.join(d, n)
            for n in os.listdir(d)
            if n.lower().endswith((".cal", ".ccmx", ".ccss"))
        ]

    def _resume_prepare(self, ti1: str, size: int):
        """Check an earlier session may be continued; return ``{block: ti3 path}``.

        Refuses (returns an ``Error``) unless the monitor, instrument, mode,
        correction, engine version and profile type are the same as in the
        session, and its stored chart and plan are intact: blocks measured under
        different conditions must never be combined silently.
        """
        sd = self.resume_from
        state = session_journal.load_state(sd) if sd else None
        plan = (state or {}).get("plan") or {}
        if not plan.get("blocks"):
            return Error(lang.getstr("recover.no_blocks"))
        if plan.get("fingerprint") != self.session_fingerprint():
            return Error(lang.getstr("recover.conditions_changed"))
        if plan.get("block_size") != size:
            return Error(lang.getstr("recover.conditions_changed"))
        saved = os.path.join(sd, "files", "chart.full.ti1")
        if session_journal.file_digest(saved) != plan.get("chart_digest"):
            return Error(lang.getstr("recover.no_blocks"))
        shutil.copyfile(saved, ti1)  # the very chart the blocks were planned on
        reused = {}
        for n in state.get("blocks_done", []):
            hits = glob.glob(os.path.join(glob.escape(sd), "files", f"*.blk{n:04d}.ti3"))
            if hits:
                reused[n] = hits[0]
        self.log(f"Continuing an earlier session: {len(reused)} finished blocks are reused.")
        session_journal.mark_reviewed(sd, "resumed")
        self.resume_from = None
        return reused
