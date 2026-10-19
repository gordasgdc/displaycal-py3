"""Voluntary support and feedback UI (Help/About and the end of a finished flow).

Two plain actions, never conditions for anything:

* *Give a star on GitHub* -- only opens the repository page in the browser.
* *Send feedback* -- a small dialog (type, description, version and platform
  shown before sending, optional redacted diagnostic with preview) that opens a
  pre-filled new-issue page in the browser. The application itself sends
  nothing, asks for no GitHub login and keeps no token.

The GitHub mark is the official, unaltered Invertocat (black or white variant,
whichever contrasts with the current theme), shown next to the text label.
No effects are applied to it. See ``docs/BRAND_ASSETS.md``.
"""

from __future__ import annotations

import contextlib
import webbrowser
from html import escape

from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QIcon, QImage, QPainter, QPixmap
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config, support
from DisplayCAL import localization as lang
from DisplayCAL.config import getcfg, setcfg
from DisplayCAL.ui import text_scale


def _tr(key: str) -> str:
    return lang.getstr(key)


def open_url(url: str) -> bool:
    """Open a URL in the user's browser (the user acts there)."""
    try:
        return bool(webbrowser.open(url))
    except webbrowser.Error:
        return False


def github_icon(size: int = 18) -> QIcon:
    """The official, unaltered GitHub mark in the variant that contrasts best."""
    dark = QApplication.palette().window().color().lightness() < 128
    name = "white" if dark else "black"
    path = config.get_data_path(f"theme/brands/github-invertocat-{name}.svg")
    if not path:
        return QIcon()
    from qtpy.QtSvg import QSvgRenderer

    dpr = 2.0
    img = QImage(int(size * dpr), int(size * dpr), QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    painter = QPainter(img)
    QSvgRenderer(path).render(painter)
    painter.end()
    pix = QPixmap.fromImage(img)
    pix.setDevicePixelRatio(dpr)
    return QIcon(pix)


def star_clicked() -> None:
    """Open the repository page; the user decides about the star in the browser."""
    open_url(support.REPO_URL)


class _TextDialog(QDialog):
    def __init__(self, title: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        lay = QVBoxLayout(self)
        box = QPlainTextEdit(text)
        box.setReadOnly(True)
        lay.addWidget(box)
        close = QPushButton(_tr("ok"))
        close.clicked.connect(self.accept)
        lay.addWidget(close, 0, Qt.AlignRight)
        self.resize(640, 420)


class FeedbackDialog(QDialog):
    """Simple feedback form that opens a pre-filled GitHub issue in the browser."""

    def __init__(
        self, parent: QWidget | None = None, log_path: str | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_tr("support.feedback.title"))
        self._log_path = log_path or self._default_log()
        self.opened_url: str | None = None
        lay, buttons = text_scale.scrollable_dialog(self)
        lay.addWidget(self._wrap(_tr("support.feedback.intro")))

        form = QFormLayout()
        self.kind = QComboBox()
        for k in support.KINDS:
            self.kind.addItem(_tr(f"support.kind.{k}"), k)
        form.addRow(_tr("support.feedback.type"), self.kind)
        lay.addLayout(form)
        lay.addWidget(QLabel(_tr("support.feedback.description")))
        self.description = QPlainTextEdit()
        text_scale.set_min_height(self.description, 120)
        lay.addWidget(self.description)

        # What will be included, visible before anything leaves the machine.
        self.info = QLabel(
            f"{escape(_tr('support.feedback.included'))}<br/>"
            f"• {escape(support.app_version_line())}<br/>"
            f"• {escape(support.platform_line())}"
        )
        self.info.setTextFormat(Qt.RichText)
        lay.addWidget(self.info)

        diag = QHBoxLayout()
        self.diag_cb = text_scale.WrapCheckBox(_tr("support.feedback.diagnostic"))
        self.diag_cb.setChecked(False)  # never on by default
        self.preview_btn = QPushButton(_tr("support.feedback.preview"))
        self.preview_btn.clicked.connect(self._preview)
        diag.addWidget(self.diag_cb, 1)
        diag.addWidget(self.preview_btn)
        lay.addLayout(diag)
        lay.addWidget(self._wrap(_tr("support.feedback.note"), muted=True))

        buttons.addStretch(1)
        cancel = QPushButton(_tr("cancel"))
        cancel.clicked.connect(self.reject)
        self.send_btn = QPushButton(_tr("support.feedback.open"))
        self.send_btn.setDefault(True)
        self.send_btn.clicked.connect(self._open)
        buttons.addWidget(cancel)
        buttons.addWidget(self.send_btn)
        self.resize(600, 560)

    @staticmethod
    def _wrap(text: str, muted: bool = False) -> QLabel:
        lab = QLabel(text_scale.breakable(text))
        lab.setWordWrap(True)
        if muted:
            from DisplayCAL.ui.settings_sections import muted_css

            lab.setStyleSheet(f"color: {muted_css()};")
        return lab

    @staticmethod
    def _default_log() -> str | None:
        import os

        path = os.path.join(config.LOGDIR, "DisplayCAL.log")
        return path if os.path.isfile(path) else None

    def diagnostic_text(self) -> str:
        """The redacted diagnostic that would be included."""
        return support.collect_diagnostic(self._log_path)

    def _preview(self) -> None:
        _TextDialog(
            _tr("support.feedback.preview"), self.diagnostic_text(), self
        ).exec()

    def _open(self) -> None:
        diag = self.diagnostic_text() if self.diag_cb.isChecked() else None
        url, _cut = support.build_issue_url(
            self.kind.currentData(), self.description.toPlainText(), diag
        )
        self.opened_url = url
        open_url(url)
        self.accept()


class SupportActions(QWidget):
    """The two actions: star (with the GitHub mark) and feedback."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.question = QLabel(_tr("support.star.question"))
        self.question.setWordWrap(True)
        lay.addWidget(self.question)
        row = QHBoxLayout()
        self.star_btn = QPushButton(_tr("support.star.button"))
        self.star_btn.setIcon(github_icon(18))
        self.star_btn.setIconSize(QSize(18, 18))
        self.star_btn.setAccessibleName(_tr("support.star.button"))
        self.star_btn.clicked.connect(star_clicked)
        self.feedback_btn = QPushButton(_tr("support.feedback.button"))
        self.feedback_btn.clicked.connect(self.open_feedback)
        row.addWidget(self.star_btn)
        row.addWidget(self.feedback_btn)
        row.addStretch(1)
        lay.addLayout(row)
        credits_label = QLabel(
            _tr("support.credits")
            .replace("%(fork)s", f'<a href="{support.REPO_URL}">DisplayCAL-CG</a>')
            .replace(
                "%(upstream)s", f'<a href="{support.UPSTREAM_URL}">displaycal-py3</a>'
            )
            .replace("%(original)s", f'<a href="{support.ORIGINAL_URL}">DisplayCAL</a>')
            .replace("%(argyll)s", f'<a href="{support.ARGYLL_URL}">ArgyllCMS</a>')
        )
        credits_label.setTextFormat(Qt.RichText)
        credits_label.setWordWrap(True)
        credits_label.setOpenExternalLinks(True)
        self.credits = credits_label
        lay.addWidget(credits_label)

    def open_feedback(self) -> None:
        """Show the feedback dialog."""
        FeedbackDialog(self.window()).exec()


def invite_allowed(app_version: str) -> bool:
    """Whether the discreet end-of-flow invitation may be shown at all."""
    if not getcfg("support.invite"):
        return False
    return getcfg("support.dismissed_version") != app_version


class SupportInvite(QFrame):
    """Discreet invitation for the end of a finished flow; closable for good."""

    closed = Signal()

    def __init__(self, app_version: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._version = app_version
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        self.actions = SupportActions()
        lay.addWidget(self.actions)
        row = QHBoxLayout()
        self.close_btn = QPushButton(_tr("support.invite.close"))
        self.close_btn.setFlat(True)
        self.never_btn = QPushButton(_tr("support.invite.never"))
        self.never_btn.setFlat(True)
        self.close_btn.clicked.connect(self._close)
        self.never_btn.clicked.connect(self._never)
        row.addStretch(1)
        row.addWidget(self.close_btn)
        row.addWidget(self.never_btn)
        lay.addLayout(row)

    def _close(self) -> None:
        setcfg("support.dismissed_version", self._version)
        self._persist()
        self.setVisible(False)
        self.closed.emit()

    def _never(self) -> None:
        setcfg("support.invite", 0)
        self._persist()
        self.setVisible(False)
        self.closed.emit()

    @staticmethod
    def _persist() -> None:
        with contextlib.suppress(
            Exception
        ):  # a failed save must never disturb the flow
            config.writecfg()
