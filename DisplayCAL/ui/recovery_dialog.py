"""Start-up offer for measurement sessions that never recorded an end.

It lists what is *known* (facts from the session journal), never a guessed
cause, and offers only what can really be done: look at the state, export the
valid stored data, show the folder, and -- only for sessions measured in blocks
and only when the conditions are the same -- continue with the remaining blocks.
"""

from __future__ import annotations

import os
import time
from html import escape

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import localization as lang
from DisplayCAL import session_journal as sj
from DisplayCAL.config import setcfg
from DisplayCAL.ui import text_scale
from DisplayCAL.util_os import launch_file


def _tr(key: str, *args: object) -> str:
    return lang.getstr(key, list(args)) if args else lang.getstr(key)


def human_duration(seconds: float) -> str:
    """``5 h 12 min`` / ``12 min`` text."""
    minutes = round(seconds / 60)
    h, m = divmod(minutes, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def human_bytes(n: float) -> str:
    """Short size text."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def fact_text(key: str, p: dict) -> str:
    """Translate one journal fact (key + parameters) to a sentence."""
    if key == "recover.fact.last_seen":
        return _tr(key, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p["time"])))
    if key == "recover.fact.progress":
        return _tr(key, p.get("done"), p.get("total"))
    if key == "recover.fact.stage":
        return _tr(key, p.get("stage"))
    if key == "recover.fact.child_exit":
        return _tr(key, p.get("code"))
    if key == "recover.fact.child_no_exit":
        return _tr(key)
    if key == "recover.fact.slept":
        return _tr(key, human_duration(p["seconds"]))
    if key == "recover.fact.memory":
        return _tr(key, human_bytes(p["first"]), human_bytes(p["last"]), human_bytes(p["max"]))
    if key == "recover.fact.disk":
        return _tr(key, human_bytes(p["last_free"]))
    return _tr(key)


class RecoveryDialog(QDialog):
    """Review unfinished sessions; export, open or continue."""

    def __init__(
        self,
        sessions: list[sj.IncompleteSession],
        worker: object,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_tr("recover.title"))
        self._sessions = sessions
        self._worker = worker
        self.exported_to: str | None = None
        lay, footer = text_scale.scrollable_dialog(self)
        self.intro = QLabel(_tr("recover.intro", f"{len(sessions)} {_tr('recover.sessions')}"))
        self.intro.setWordWrap(True)
        lay.addWidget(self.intro)
        self.listing = QListWidget()
        for s in sessions:
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(s.state.get("started", 0)))
            item = QListWidgetItem(f"{when}  ·  {s.state.get('info', {}).get('display', '')}")
            item.setData(Qt.UserRole, s.dir)
            self.listing.addItem(item)
        self.listing.currentRowChanged.connect(self._show)
        lay.addWidget(self.listing)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.RichText)
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.details, 1)
        row = QHBoxLayout()
        self.export_btn = QPushButton(_tr("recover.export"))
        self.folder_btn = QPushButton(_tr("recover.open_folder"))
        self.continue_btn = QPushButton()
        self.export_btn.clicked.connect(self._export)
        self.folder_btn.clicked.connect(self._folder)
        self.continue_btn.clicked.connect(self._continue)
        for b in (self.export_btn, self.folder_btn, self.continue_btn):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        row2 = footer
        row2.addStretch(1)
        self.later_btn = QPushButton(_tr("recover.dismiss"))
        self.seen_btn = QPushButton(_tr("recover.discard"))
        self.later_btn.clicked.connect(self.reject)
        self.seen_btn.clicked.connect(self._seen)
        row2.addWidget(self.later_btn)
        row2.addWidget(self.seen_btn)
        self.resize(680, 560)
        self.listing.setCurrentRow(0)

    # -- helpers --------------------------------------------------------
    def _current(self) -> sj.IncompleteSession | None:
        i = self.listing.currentRow()
        return self._sessions[i] if 0 <= i < len(self._sessions) else None

    def _show(self, _row: int) -> None:
        s = self._current()
        if s is None:
            return
        lines = [escape(fact_text(k, p)) for k, p in s.facts]
        plan = sj.resume_plan(s.state, self._worker.session_fingerprint())
        total = (s.state.get("plan") or {}).get("blocks")
        if total:
            lines.append(escape(_tr("recover.blocks_done", len(s.state.get("blocks_done", [])), total)))
        if plan["possible"]:
            lines.append("<b>" + escape(_tr("recover.can_continue", ", ".join(map(str, plan["remaining"])))) + "</b>")
            lines.append(escape(_tr("recover.conditions_note")))
        elif plan["reason"]:
            lines.append(escape(_tr(plan["reason"])))
        self.details.setText("<br/>".join("• " + ln if not ln.startswith("<b>") else ln for ln in lines))
        self.continue_btn.setVisible(plan["possible"])
        if plan["possible"]:
            self.continue_btn.setText(_tr("recover.continue_btn"))

    # -- actions --------------------------------------------------------
    def _export(self) -> None:
        s = self._current()
        if s is None:
            return
        dest = QFileDialog.getExistingDirectory(self, _tr("recover.export"), os.path.expanduser("~"))
        if dest:
            self.exported_to = sj.export_session(s.dir, dest)
            self.details.setText(escape(_tr("recover.exported", self.exported_to)))

    def _folder(self) -> None:
        s = self._current()
        if s is not None:
            launch_file(s.dir)

    def _continue(self) -> None:
        """Arrange for the next profiling run to reuse the finished blocks."""
        s = self._current()
        if s is None:
            return
        plan = (s.state.get("plan") or {})
        self._worker.resume_from = s.dir
        setcfg("measurement.block_size", int(plan.get("block_size", 0)))
        self.accept()

    def _seen(self) -> None:
        for s in self._sessions:
            sj.mark_reviewed(s.dir, "seen")
        self.accept()
