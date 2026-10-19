"""\"Don't know your monitor's technology? Search the model\".

Reuses the detected model of the monitor (correctable by the user) and offers
only lookups that really exist (see :mod:`DisplayCAL.display_lookup`). The
application itself makes no network request: the browser opens the site, and
a failure to open it never blocks anything nor produces a recommendation.

It also explains four things that are easy to confuse -- panel technology,
light-emitting technology, measurement mode and correction -- next to the
upstream explanation of monitor technologies, and says plainly that what a
specification page shows is not a validated correction.
"""

from __future__ import annotations

from collections.abc import Callable
from html import escape

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config
from DisplayCAL import display_lookup as dl
from DisplayCAL import localization as lang
from DisplayCAL.ui.support_dialog import open_url
from DisplayCAL.ui.tooltip_window import info_text_html


def _tr(key: str, *args: object) -> str:
    return lang.getstr(key, list(args)) if args else lang.getstr(key)


def _wrap(text: str, rich: bool = False, muted: bool = False) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setTextFormat(Qt.RichText if rich else Qt.PlainText)
    lab.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
    lab.setOpenExternalLinks(False)
    if muted:
        from DisplayCAL.ui.settings_sections import muted_css

        lab.setStyleSheet(f"color: {muted_css()};")
    return lab


def current_display_entry() -> str:
    """The selected display as Argyll lists it (with geometry), or ``""``."""
    try:
        return config.get_display_name(include_geometry=True)
    except Exception:  # noqa: BLE001 - lookup is a convenience, never a blocker
        return ""


class DisplayLookupDialog(QDialog):
    """Model lookup, explanations and the caution about corrections."""

    def __init__(
        self,
        parent: QWidget | None = None,
        entry: str | None = None,
        on_goto_correction: Callable[[], None] | None = None,
        platform: str | None = None,
        hw_model: str | None | bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(_tr("lookup.title"))
        self._goto = on_goto_correction
        self._model0 = dl.detect(
            current_display_entry() if entry is None else entry, platform, hw_model
        )
        self.model = self._model0
        self.opened: list[str] = []  # URLs handed to the browser (tests)
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        lay = QVBoxLayout(body)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        lay.addWidget(_wrap(_tr("lookup.intro")))
        lay.addWidget(_wrap("<b>" + escape(_tr("lookup.model.title")) + "</b>", True))
        self.kind_label = _wrap("")
        lay.addWidget(self.kind_label)
        lay.addWidget(_wrap(_tr("lookup.model.edit"), muted=True))
        self.model_edit = QLineEdit(self._model0.name)
        self.model_edit.textChanged.connect(self._model_edited)
        lay.addWidget(self.model_edit)

        lay.addWidget(_wrap("<b>" + escape(_tr("lookup.go.title")) + "</b>", True))
        self.actions_box = QVBoxLayout()
        lay.addLayout(self.actions_box)
        self.status = _wrap("")
        lay.addWidget(self.status)
        lay.addWidget(_wrap(_tr("lookup.offline"), muted=True))

        lay.addWidget(_wrap("<b>" + escape(_tr("lookup.concepts.title")) + "</b>", True))
        for key in ("panel", "emissive", "mode", "correction"):
            lay.addWidget(_wrap(_tr(f"lookup.concept.{key}"), True))
        src = QPushButton(_tr("lookup.src_link"))
        src.setFlat(True)
        src.clicked.connect(lambda: self._open(dl.ARGYLL_CCXXMAKE_DOC, None))
        lay.addWidget(src, 0, Qt.AlignLeft)

        lay.addWidget(_wrap("<b>" + escape(_tr("lookup.upstream.title")) + "</b>", True))
        lay.addWidget(_wrap(info_text_html("info.display_tech"), True))
        lay.addWidget(_wrap(_tr("lookup.upstream.source"), muted=True))

        lay.addWidget(_wrap("<b>" + escape(_tr("lookup.caution.title")) + "</b>", True))
        lay.addWidget(_wrap(_tr("lookup.caution")))
        row = QHBoxLayout()
        self.goto_btn = QPushButton(_tr("lookup.goto_correction"))
        self.goto_btn.setVisible(on_goto_correction is not None)
        self.goto_btn.clicked.connect(self._goto_clicked)
        row.addWidget(self.goto_btn)
        row.addStretch(1)
        close = QPushButton(_tr("lookup.close"))
        close.clicked.connect(self.accept)
        row.addWidget(close)
        outer.addLayout(row)
        self.resize(660, 700)
        self._refresh()

    # -- model ----------------------------------------------------------------
    def _model_edited(self, text: str) -> None:
        if text.strip() == self._model0.name:
            self.model = self._model0
        else:
            self.model = dl.corrected(self._model0, text)
        self._refresh()

    def _refresh(self) -> None:
        m = self.model
        if m.kind == dl.APPLE_BUILTIN:
            text = (
                _tr("lookup.model.builtin", m.mac_model_id)
                if m.mac_model_id
                else _tr("lookup.model.builtin_noid")
            )
        elif m.kind == dl.EXTERNAL:
            text = _tr("lookup.model.external")
        else:
            text = _tr("lookup.model.unknown")
        self.kind_label.setText(text)
        while self.actions_box.count():
            item = self.actions_box.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.action_buttons: list[QPushButton] = []
        for act in dl.actions(m):
            label = (
                _tr(act.key, m.mac_model_id)
                if act.key == "lookup.act.everymac_id"
                else _tr(act.key)
            )
            btn = QPushButton(label)
            btn.clicked.connect(lambda _=False, a=act: self._open(a.url, a.copy_text, a))
            self.actions_box.addWidget(btn, 0, Qt.AlignLeft)
            self.action_buttons.append(btn)
            if act.note_key:
                self.actions_box.addWidget(_wrap(_tr(act.note_key), muted=True))

    # -- actions ---------------------------------------------------------------
    def _open(self, url: str, copy_text: str | None, action: dl.LookupAction | None = None) -> None:
        """Copy the model (when the action says so) and open the site."""
        messages = []
        if copy_text:
            QApplication.clipboard().setText(copy_text)
            messages.append(_tr("lookup.copied", copy_text))
        ok = open_url(url)
        self.opened.append(url)
        if not ok:
            messages.append(_tr("lookup.open_failed", url))
        self.status.setText("\n".join(messages))

    def _goto_clicked(self) -> None:
        if self._goto is not None:
            self.accept()
            self._goto()


def lookup_button(
    parent: QWidget,
    on_goto_correction: Callable[[], None] | None = None,
    entry_getter: Callable[[], str] | None = None,
) -> QPushButton:
    """The visible entry point: a flat button that opens the lookup dialog."""
    btn = QPushButton(_tr("lookup.link"))
    btn.setFlat(True)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet("QPushButton { text-align: left; text-decoration: underline; }")
    btn.setObjectName("display_lookup_button")

    def open_dialog() -> None:
        DisplayLookupDialog(
            btn.window(),
            entry=entry_getter() if entry_getter else None,
            on_goto_correction=on_goto_correction,
        ).exec()

    btn.clicked.connect(open_dialog)
    return btn
