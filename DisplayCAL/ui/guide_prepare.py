"""The "Preparation" step of the guided flow.

Left: a short, contextual checklist grouped by decision (monitor, room,
instrument, during the run). Each item shows its essential action in plain
sight; the reasoning and the sources behind it are one click away. Nothing is
ticked for the user. Right: the instrument placement sequence
(:mod:`DisplayCAL.ui.placement_player`) with its static text list.

The optional timer is only a reminder that counts from the moment it is
started; it does not know how long the monitor was already on and never ticks
anything.
"""

from __future__ import annotations

from html import escape

from qtpy.QtCore import Qt, QTimer, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import guide_model as gm
from DisplayCAL import instrument_catalog as ic
from DisplayCAL import localization as lang
from DisplayCAL.guide_sources import SOURCES
from DisplayCAL.ui.guide_widgets import AdaptiveRow, Disclosure, label, m
from DisplayCAL.ui.placement_player import PlacementPlayer


def _tr(key: str, *args: object) -> str:
    return lang.getstr(key, list(args)) if args else lang.getstr(key)


def sources_html(keys: tuple[str, ...]) -> str:
    """Rich text listing the sources (titles link to the documents)."""
    rows = []
    for k in keys:
        s = SOURCES.get(k)
        if s is None:
            continue
        rows.append(
            f'<p style="margin:2px 0">• <a href="{escape(s.url)}">{escape(s.title)}</a>'
            f"<br/>&nbsp;&nbsp;<span>{escape(s.covers)}</span></p>"
        )
    return "".join(rows)


class _ToggleLabel(QLabel):
    """A wrapped title that toggles its checkbox when clicked."""

    def __init__(self, text: str, box: QCheckBox) -> None:
        super().__init__(text)
        self._box = box
        self.setWordWrap(True)
        self.setTextFormat(Qt.PlainText)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, event: object) -> None:  # noqa: N802, D102
        if event.button() == Qt.LeftButton:
            self._box.toggle()
        super().mouseReleaseEvent(event)


class PreparePage(QWidget):
    """Checklist + placement sequence for the preparation step."""

    changed = Signal()

    def __init__(self, prep: gm.PrepState) -> None:
        super().__init__()
        self._prep = prep
        self._goal: str | None = None
        self._ident: ic.Identification | None = None
        self._model: str | None = None
        self._boxes: dict[str, QCheckBox] = {}
        self._timer_left = 0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._timer_tick)
        self._timer_label: QLabel | None = None
        self._timer_btn: QPushButton | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)
        root.addWidget(label(_tr("guide.s3.title"), size=1.6, bold=True))
        root.addWidget(label(_tr("guide.s3.hint"), muted=True))

        self._list_host = QWidget()
        self._list = QVBoxLayout(self._list_host)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(14)

        self.player = PlacementPlayer()
        side = QWidget()
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(8)
        sl.addWidget(label(_tr("guide.pl.title"), size=1.15, bold=True))
        sl.addWidget(self.player)
        self.reduced_note = label(_tr("guide.pl.reduced_note"), size=0.95, muted=True)
        self.reduced_note.setVisible(self.player.reduced_motion)
        sl.addWidget(self.reduced_note)
        self.sequence_note = label("", size=0.95, muted=True)
        sl.addWidget(self.sequence_note)
        self.accessories_label = label("", size=0.95)
        sl.addWidget(self.accessories_label)
        # The same steps as plain text: the accessible, always-visible alternative.
        self.steps_text = label("")
        sl.addWidget(self.steps_text)
        self.steps_sources = QLabel()
        self.steps_sources.setWordWrap(True)
        self.steps_sources.setTextFormat(Qt.RichText)
        self.steps_sources.setOpenExternalLinks(True)
        self.steps_sources.setTextInteractionFlags(Qt.TextBrowserInteraction)
        sl.addWidget(self.steps_sources)
        sl.addStretch(1)
        root.addWidget(AdaptiveRow(self._list_host, side, threshold=880, ratio=(5, 5)))
        self._rebuild()

    # ------------------------------------------------------------ context
    def set_context(
        self,
        goal: str | None,
        ident: ic.Identification | None,
        model: str | None,
    ) -> None:
        """Update what the checklist and the sequence depend on."""
        key = (goal, ident.detected_name if ident else None, model)
        if key == getattr(self, "_ctx", None):
            return
        self._ctx = key
        self._goal, self._ident, self._model = goal, ident, model
        self._rebuild()

    def stop_motion(self) -> None:
        """Stop the animation and any decorative motion (before a measurement)."""
        self.player.stop()

    def on_shown(self) -> None:
        """The page became visible: play the sequence once (never when reduced)."""
        self.player.autoplay_once()

    def timer_running(self) -> bool:
        """Whether the reminder timer is counting."""
        return self._timer.isActive()

    # ---------------------------------------------------------- rebuilding
    def _rebuild(self) -> None:
        seq = ic.resolve_placement(self._ident, self._model)
        items = gm.build_preparation(self._goal, seq.variant)
        self._prep.set_items(items)
        while self._list.count():
            w = self._list.takeAt(0).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._boxes.clear()
        self._timer_label = None
        self._timer_btn = None
        group = None
        for item in items:
            if item.group != group:
                group = item.group
                head = label(
                    _tr(f"guide.prep.group.{group}"), size=0.95, bold=True, muted=True
                )
                self._list.addWidget(head)
            self._list.addWidget(self._make_item(item, seq))
        self._list.addStretch(1)
        self._paint_sequence(seq)
        self.changed.emit()

    def _make_item(self, item: gm.PrepItem, seq: ic.PlacementSequence) -> QWidget:
        box = QWidget()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(3)
        row = QHBoxLayout()
        row.setSpacing(8)
        # The box carries no text of its own (a QCheckBox cannot wrap long
        # text and would force the column wide); the wrapped title next to it
        # toggles it, and the accessible name keeps the full sentence.
        cb = QCheckBox()
        cb.setAccessibleName(_tr(item.title_key))
        cb.setChecked(item.key in self._prep.done)
        cb.toggled.connect(lambda on, k=item.key: self._toggled(k, on))
        self._boxes[item.key] = cb
        title = _ToggleLabel(_tr(item.title_key), cb)
        f = title.font()
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() * 1.12)
        title.setFont(f)
        tag = label(
            _tr("guide.s3.required") if item.required else _tr("guide.s3.recommended"),
            size=0.85,
            muted=not item.required,
            bold=item.required,
            wrap=False,
        )
        row.addWidget(cb, 0, Qt.AlignTop)
        row.addWidget(title, 1)
        row.addWidget(tag, 0, Qt.AlignRight | Qt.AlignTop)
        bl.addLayout(row)
        action = label(_tr(item.action_key), size=1.05)
        action.setContentsMargins(26, 0, 0, 0)
        bl.addWidget(action)
        if item.key == "stabilize":
            bl.addWidget(self._make_timer())
        bl.addWidget(self._make_why(item, seq))
        return box

    def _make_why(self, item: gm.PrepItem, seq: ic.PlacementSequence) -> QWidget:
        body = QWidget()
        wl = QVBoxLayout(body)
        wl.setContentsMargins(26, 2, 0, 0)
        wl.setSpacing(6)
        wl.addWidget(label(_tr(item.detail_key), muted=True))
        if item.key == "stabilize" and seq.variant in gm.VENDOR_WARMUP:
            minutes, _src = gm.VENDOR_WARMUP[seq.variant]
            wl.addWidget(label(_tr("guide.prep.vendor_warmup", minutes), muted=True))
        if item.sources:
            wl.addWidget(
                label(_tr("guide.prep.sources"), size=0.95, bold=True, muted=True)
            )
            src = QLabel(sources_html(item.sources))
            src.setWordWrap(True)
            src.setTextFormat(Qt.RichText)
            src.setOpenExternalLinks(True)
            src.setTextInteractionFlags(Qt.TextBrowserInteraction)
            wl.addWidget(src)
        wrap = QWidget()
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(22, 0, 0, 0)
        outer.addWidget(Disclosure(_tr("guide.prep.why"), body))
        return wrap

    def _make_timer(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(26, 2, 0, 0)
        v.setSpacing(2)
        v.addWidget(label(_tr("guide.prep.timer.label"), size=0.95, muted=True))
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        self._spin = QSpinBox()
        self._spin.setRange(1, 180)
        self._spin.setValue(30)
        self._spin.setSuffix(" " + _tr("guide.prep.timer.minutes"))
        h.addWidget(self._spin)
        self._timer_btn = QPushButton(m(_tr("guide.prep.timer.start")))
        self._timer_btn.clicked.connect(self._toggle_timer)
        h.addWidget(self._timer_btn)
        h.addStretch(1)
        v.addLayout(h)
        self._timer_label = label(_tr("guide.prep.timer.note"), size=0.95, muted=True)
        v.addWidget(self._timer_label)
        return w

    # ------------------------------------------------------------- timer
    def _toggle_timer(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self._timer_btn.setText(m(_tr("guide.prep.timer.start")))
            self._timer_label.setText(_tr("guide.prep.timer.note"))
            return
        self._timer_left = self._spin.value() * 60
        self._timer.start()
        self._timer_btn.setText(m(_tr("guide.prep.timer.stop")))
        self._show_remaining()

    def _show_remaining(self) -> None:
        mm, ss = divmod(self._timer_left, 60)
        self._timer_label.setText(_tr("guide.prep.timer.running", f"{mm:d}:{ss:02d}"))

    def _timer_tick(self) -> None:
        self._timer_left -= 1
        if self._timer_left <= 0:
            self._timer.stop()
            self._timer_btn.setText(m(_tr("guide.prep.timer.start")))
            self._timer_label.setText(_tr("guide.prep.timer.done"))
            return
        self._show_remaining()

    # ------------------------------------------------------------ sequence
    def _paint_sequence(self, seq: ic.PlacementSequence) -> None:
        self.player.set_sequence(list(seq.steps), seq.variant, seq.kind)
        if seq.verified:
            note = _tr("guide.pl.verified_note")
        elif seq.needs_model_choice:
            note = _tr("guide.pl.choose_model")
        else:
            note = _tr("guide.pl.unverified_note")
        self.sequence_note.setText(note)
        acc = seq.accessories
        self.accessories_label.setText(
            _tr(
                "guide.place.accessories", ", ".join(_tr(f"guide.acc.{a}") for a in acc)
            )
            if acc
            else ""
        )
        self.steps_text.setText(
            "\n\n".join(
                f"{i}. {_tr('guide.pl.step.' + s)}\n"
                f"   {_tr('guide.pl.' + seq.variant + '.' + s)}"
                for i, s in enumerate(seq.steps, 1)
            )
        )
        self.steps_sources.setText(sources_html(seq.sources))

    # ------------------------------------------------------------ actions
    def _toggled(self, key: str, on: bool) -> None:
        self._prep.toggle(key, on)
        self.changed.emit()
