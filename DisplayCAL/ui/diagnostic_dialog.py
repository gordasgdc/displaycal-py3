"""Help -> Diagnostic and support: logs, versions and the support package.

Everything is local. The package is a ZIP the user creates, can open and read,
saves where they choose, and sends (or not) by their own decision; the
application uploads nothing and asks for no account.
"""

from __future__ import annotations

import os
import time

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config, diagnostics, support
from DisplayCAL import localization as lang
from DisplayCAL import log as dlog
from DisplayCAL.ui.recovery_dialog import human_bytes
from DisplayCAL.ui.support_dialog import open_url
from DisplayCAL.util_os import launch_file


def _tr(key: str, *args: object) -> str:
    return lang.getstr(key, list(args)) if args else lang.getstr(key)


def _wrap(text: str, muted: bool = False) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
    if muted:
        lab.setEnabled(False)
    return lab


class ExportDialog(QDialog):
    """Show what the package will contain, let the user choose, then save."""

    def __init__(
        self,
        worker: object | None = None,
        parent: QWidget | None = None,
        categories: list[diagnostics.Category] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_tr("diag.export.title"))
        self._worker = worker
        self._cats = categories if categories is not None else self._plan()
        self.saved_path: str | None = None
        lay = QVBoxLayout(self)
        lay.addWidget(_wrap(_tr("diag.export.intro")))
        self.boxes: dict[str, QCheckBox] = {}
        lay.addWidget(_wrap("<b>" + _tr("diag.export.included") + "</b>"))
        for cat in self._cats:
            if not cat.optional:
                self._add_category(lay, cat)
        opt = [c for c in self._cats if c.optional]
        if opt:
            lay.addWidget(_wrap("<b>" + _tr("diag.export.optional") + "</b>"))
            lay.addWidget(_wrap(_tr("diag.export.optional_note"), muted=True))
            for cat in opt:
                self._add_category(lay, cat)
        self.redact_cb = QCheckBox(_tr("diag.export.redact"))
        self.redact_cb.setChecked(True)
        self.redact_cb.toggled.connect(self._redact_toggled)
        lay.addWidget(self.redact_cb)
        lay.addWidget(_wrap(_tr("diag.export.never"), muted=True))
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(_tr("cancel"))
        cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton(_tr("diag.export.save"))
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(self.save_btn)
        lay.addLayout(row)
        self.resize(640, 560)

    def _plan(self) -> list[diagnostics.Category]:
        profile = None
        try:
            p = config.get_display_profile()
            profile = getattr(p, "fileName", None)
        except Exception:  # noqa: BLE001 - the profile is optional
            profile = None
        return diagnostics.plan_package(display_profile=profile)

    def _add_category(self, lay: QVBoxLayout, cat: diagnostics.Category) -> None:
        count = len(cat.files)
        available = cat.key == "versions" or count > 0
        size = f" — {count} · {human_bytes(cat.size)}" if cat.files else ""
        if not available:
            size = f" — {_tr('diag.cat.none')}"
        box = QCheckBox(_tr(f"diag.cat.{cat.key}") + size)
        box.setChecked(cat.default and available)
        box.setEnabled(available)
        self.boxes[cat.key] = box
        lay.addWidget(box)
        lay.addWidget(_wrap(_tr(f"diag.cat.{cat.key}.desc"), muted=True))

    def selected(self) -> set[str]:
        """Keys of the categories the user ticked."""
        return {k for k, b in self.boxes.items() if b.isChecked()}

    def _redact_toggled(self, on: bool) -> None:
        if on:
            return
        answer = QMessageBox.warning(
            self,
            _tr("diag.export.title"),
            _tr("diag.export.redact_off"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            self.redact_cb.setChecked(True)

    def default_name(self) -> str:
        """Suggested file name (the version is part of the name)."""
        from DisplayCAL.meta import VERSION_STRING

        stamp = time.strftime("%Y%m%d-%H%M")
        return f"DisplayCAL-CG-diagnostic-{VERSION_STRING}-{stamp}.zip"

    def export_to(self, dest: str) -> dict:
        """Write the package to ``dest`` with the current choices."""
        readme = _tr("diag.package_readme") + "\n\n---\n\n"
        manifest = diagnostics.export_package(
            dest,
            self.selected(),
            self._cats,
            self._worker,
            redact_text=self.redact_cb.isChecked(),
            readme=readme + diagnostics._default_readme(
                {"text_redacted": self.redact_cb.isChecked()}
            ),
        )
        self.saved_path = dest
        return manifest

    def _save(self) -> None:
        dest, _ = QFileDialog.getSaveFileName(
            self,
            _tr("diag.export.save"),
            os.path.join(os.path.expanduser("~"), self.default_name()),
            "ZIP (*.zip)",
        )
        if not dest:
            return
        if not dest.lower().endswith(".zip"):
            dest += ".zip"
        try:
            self.export_to(dest)
        except OSError as exc:
            QMessageBox.critical(
                self, _tr("diag.export.title"), _tr("diag.export.failed", str(exc))
            )
            return
        self.accept()


class DiagnosticDialog(QDialog):
    """Logs folder, versions, session ID, temporary debug and the export."""

    def __init__(self, worker: object | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(_tr("diag.title"))
        self._worker = worker
        lay = QVBoxLayout(self)
        lay.addWidget(_wrap(_tr("diag.intro")))
        lay.addWidget(_wrap("<b>" + _tr("diag.versions") + "</b>"))
        self.versions = QPlainTextEdit(diagnostics.versions_text(worker, redacted=False))
        self.versions.setReadOnly(True)
        self.versions.setMinimumHeight(170)
        lay.addWidget(self.versions)
        row = QHBoxLayout()
        self.copy_versions_btn = QPushButton(_tr("diag.copy_versions"))
        self.copy_versions_btn.clicked.connect(self._copy_versions)
        self.copy_id_btn = QPushButton(_tr("diag.copy_id", dlog.APP_SESSION_ID))
        self.copy_id_btn.clicked.connect(self._copy_id)
        row.addWidget(self.copy_versions_btn)
        row.addWidget(self.copy_id_btn)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(_wrap(_tr("diag.logs_where", dlog._LOGDIR or config.LOGDIR), True))
        row2 = QHBoxLayout()
        self.open_logs_btn = QPushButton(_tr("diag.open_logs"))
        self.open_logs_btn.clicked.connect(self.open_logs)
        self.export_btn = QPushButton(_tr("diag.export_btn"))
        self.export_btn.clicked.connect(self.export)
        row2.addWidget(self.open_logs_btn)
        row2.addWidget(self.export_btn)
        row2.addStretch(1)
        lay.addLayout(row2)
        self.debug_cb = QCheckBox(_tr("diag.debug", diagnostics.DEBUG_MINUTES))
        self.debug_cb.setChecked(diagnostics.debug_enabled())
        self.debug_cb.toggled.connect(diagnostics.set_debug)
        lay.addWidget(self.debug_cb)
        lay.addWidget(_wrap("<b>" + _tr("diag.send_title") + "</b>"))
        lay.addWidget(_wrap(_tr("diag.send_how")))
        row3 = QHBoxLayout()
        self.issue_btn = QPushButton(_tr("diag.open_issue"))
        self.issue_btn.clicked.connect(lambda: open_url(support.ISSUES_NEW_URL))
        row3.addWidget(self.issue_btn)
        row3.addStretch(1)
        close = QPushButton(_tr("ok"))
        close.clicked.connect(self.accept)
        row3.addWidget(close)
        lay.addLayout(row3)
        self.resize(640, 640)

    def _copy_versions(self) -> None:
        QApplication.clipboard().setText(self.versions.toPlainText())

    def _copy_id(self) -> None:
        QApplication.clipboard().setText(dlog.APP_SESSION_ID)

    def open_logs(self) -> None:
        """Show the log folder in the file manager."""
        path = dlog._LOGDIR or config.LOGDIR
        os.makedirs(path, exist_ok=True)
        launch_file(path)

    def export(self) -> str | None:
        """Run the export flow; returns the saved path or ``None``."""
        dlg = ExportDialog(self._worker, self)
        if dlg.exec() and dlg.saved_path:
            self._after_export(dlg.saved_path)
            return dlg.saved_path
        return None

    def _after_export(self, path: str) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(_tr("diag.title"))
        box.setText(_tr("diag.export.done", path) + "\n\n" + _tr("diag.send_how"))
        show = box.addButton(_tr("diag.show_folder"), QMessageBox.ActionRole)
        issue = box.addButton(_tr("diag.open_issue"), QMessageBox.ActionRole)
        box.addButton(_tr("ok"), QMessageBox.AcceptRole)
        box.exec()
        if box.clickedButton() is show:
            launch_file(os.path.dirname(path))
        elif box.clickedButton() is issue:
            open_url(support.ISSUES_NEW_URL)
