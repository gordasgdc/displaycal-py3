"""Guided calibration panel (first tab of the Qt main window).

A five-step journey -- monitor & instrument, goal, preparation, measure,
install & verify -- layered on top of the existing Qt main window. It does not
duplicate engine logic: it mirrors the window's own display / instrument /
mode controls, loads one of the bundled presets for the chosen goal, and
starts the same measurement action the action buttons do. All advanced
settings stay reachable in the other tabs.

The decisions (readiness, goal suggestion, preparation gating, concept text)
live in :mod:`DisplayCAL.guide_model`; instrument identification lives in
:mod:`DisplayCAL.instrument_catalog`. This module is the view.

The measurement patch window is a separate window and is untouched: nothing
here draws over, scales or filters the patches.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import QRectF, QSize, Qt, Signal
from qtpy.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap
from qtpy.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config
from DisplayCAL import guide_model as gm
from DisplayCAL import instrument_catalog as ic
from DisplayCAL import localization as lang
from DisplayCAL.argyll import check_argyll_bin
from DisplayCAL.config import getcfg

if TYPE_CHECKING:
    from DisplayCAL.ui.main_window import MainWindow

#: Spectrum used for the beam motif of the app icon (kept subtle in the UI).
_SPECTRUM = ("#ff5a4d", "#ffb347", "#ffe14d", "#59f07a", "#4dc9ff", "#5a7bff")

STEPS = 5


def _tr(key: str, *args: object) -> str:
    return lang.getstr(key, list(args)) if args else lang.getstr(key)


def _tokens() -> dict[str, QColor]:
    """Colour tokens derived from the active palette (follows light/dark)."""
    pal = QApplication.palette()
    window = pal.window().color()
    text = pal.windowText().color()
    dark = window.lightness() < 128
    plate = QColor(window)
    plate = plate.lighter(118) if dark else plate.darker(104)
    return {
        "window": window,
        "text": text,
        "muted": QColor(text.red(), text.green(), text.blue(), 150),
        "plate": plate,
        "line": QColor(text.red(), text.green(), text.blue(), 40),
        "accent": QColor("#ffb347") if dark else QColor("#b86e00"),
        "ok": QColor("#4cc38a") if dark else QColor("#18794e"),
        "warn": QColor("#ffb347") if dark else QColor("#b86e00"),
        "bad": QColor("#ff6b6b") if dark else QColor("#c62828"),
    }


def _m(text: str) -> str:
    """Escape ``&`` so Qt buttons do not swallow it as a mnemonic marker."""
    return text.replace("&", "&&")


def _css(c: QColor) -> str:
    return f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha() / 255:.2f})"


class _SpectrumLine(QWidget):
    """A thin beam line (the icon's spectrum), used as a quiet header accent."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(3)

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        grad = QLinearGradient(0, 0, self.width(), 0)
        for i, hex_ in enumerate(_SPECTRUM):
            grad.setColorAt(i / (len(_SPECTRUM) - 1), QColor(hex_))
        painter.setOpacity(0.85)
        painter.fillRect(self.rect(), grad)


class _Rail(QWidget):
    """Vertical journey rail: numbered nodes joined by a line."""

    step_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current = 0
        self._reached = 0
        self.setMinimumWidth(176)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)

    def set_state(self, current: int, reached: int) -> None:
        self._current, self._reached = current, reached
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(190, 60 * STEPS + 24)

    def _row_rect(self, i: int) -> QRectF:
        return QRectF(6, 12 + i * 60, self.width() - 12, 52)

    def mousePressEvent(self, event: object) -> None:  # noqa: N802
        pos = event.position() if hasattr(event, "position") else event.pos()
        for i in range(STEPS):
            if self._row_rect(i).contains(pos) and i <= self._reached:
                self.step_requested.emit(i)
                return

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        t = _tokens()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        x = 24.0
        p.setPen(QPen(t["line"], 2))
        p.drawLine(int(x), 12 + 26, int(x), 12 + (STEPS - 1) * 60 + 26)
        # progressed part of the line in the spectrum
        if self._current > 0:
            grad = QLinearGradient(0, 38, 0, 38 + self._current * 60)
            for i, hex_ in enumerate(_SPECTRUM):
                grad.setColorAt(i / (len(_SPECTRUM) - 1), QColor(hex_))
            p.setPen(QPen(grad, 2.5))
            p.drawLine(int(x), 38, int(x), 38 + self._current * 60)
        font = QFont(self.font())
        for i in range(STEPS):
            r = self._row_rect(i)
            cy = r.top() + 26
            reached = i <= self._reached
            done = i < self._current
            active = i == self._current
            node = QRectF(x - 11, cy - 11, 22, 22)
            p.setPen(Qt.NoPen)
            if active:
                p.setBrush(t["accent"])
            elif done:
                p.setBrush(t["ok"])
            else:
                p.setBrush(t["plate"])
            p.drawEllipse(node)
            if not (active or done):
                p.setPen(QPen(t["line"], 1.5))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(node)
            p.setPen(t["window"] if (active or done) else t["muted"])
            nf = QFont(font)
            nf.setBold(True)
            nf.setPointSizeF(font.pointSizeF() * 0.9)
            p.setFont(nf)
            p.drawText(node, Qt.AlignCenter, "✓" if done else str(i + 1))
            tf = QFont(font)
            tf.setBold(active)
            tf.setPointSizeF(font.pointSizeF() * 1.05)
            p.setFont(tf)
            p.setPen(t["text"] if reached else t["muted"])
            p.drawText(
                QRectF(x + 22, r.top(), r.width() - x - 22, 52),
                Qt.AlignVCenter | Qt.TextWordWrap,
                lang.getstr(f"guide.step.{i + 1}"),
            )


class _Card(QFrame):
    """A quiet bordered plate."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("guideCard")
        self.setFrameShape(QFrame.NoFrame)
        self.restyle()

    def restyle(self) -> None:
        t = _tokens()
        self.setStyleSheet(
            f"QFrame#guideCard{{background:{_css(t['plate'])};"
            f"border:1px solid {_css(t['line'])};border-radius:12px;}}"
        )


def _label(
    text: str = "",
    *,
    size: float = 1.0,
    bold: bool = False,
    muted: bool = False,
    wrap: bool = True,
) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(wrap)
    f = lab.font()
    f.setPointSizeF(f.pointSizeF() * size)
    f.setBold(bold)
    lab.setFont(f)
    lab.setTextFormat(Qt.PlainText)
    if muted:
        lab.setStyleSheet(f"color:{_css(_tokens()['muted'])};")
    return lab


class _AdaptiveRow(QWidget):
    """Two blocks side by side; stacked when the window is narrow."""

    def __init__(self, first: QWidget, second: QWidget, threshold: int = 700) -> None:
        super().__init__()
        self._threshold = threshold
        self._box = QHBoxLayout(self)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(16)
        self._box.addWidget(first, 3)
        self._box.addWidget(second, 2)
        self._stacked = False

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        narrow = self.width() < self._threshold
        if narrow != self._stacked:
            self._stacked = narrow
            self._box.setDirection(
                QHBoxLayout.TopToBottom if narrow else QHBoxLayout.LeftToRight
            )
        super().resizeEvent(event)


class GuidePanel(QWidget):
    """The guided-flow panel; one instance lives in the main window's stack."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__()
        self.window_ref = window
        self._step = 0
        self._reached = 0
        self._prep = gm.PrepState()
        self._goal: str | None = None
        self._model: dict[str, str] = {}
        self._syncing = False
        self._build()
        self.refresh()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(10)

        head = QHBoxLayout()
        title_box = QVBoxLayout()
        self.title = _label(_tr("guide.title"), size=1.7, bold=True, wrap=False)
        self.subtitle = _label(_tr("guide.subtitle"), muted=True)
        title_box.addWidget(self.title)
        title_box.addWidget(self.subtitle)
        head.addLayout(title_box, 1)
        self.advanced_btn = QPushButton(_m(_tr("guide.advanced")))
        self.advanced_btn.setFlat(True)
        self.advanced_btn.setCursor(Qt.PointingHandCursor)
        self.advanced_btn.clicked.connect(
            lambda: self.window_ref._select_tab("display_instrument")
        )
        head.addWidget(self.advanced_btn, 0, Qt.AlignTop)
        root.addLayout(head)
        root.addWidget(_SpectrumLine())

        body = QHBoxLayout()
        body.setSpacing(18)
        self.rail = _Rail()
        self.rail.step_requested.connect(self.go)
        body.addWidget(self.rail, 0)

        self.pages = QStackedWidget()
        self._page_builders = (
            self._build_page_devices,
            self._build_page_goal,
            self._build_page_prepare,
            self._build_page_measure,
            self._build_page_finish,
        )
        for builder in self._page_builders:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            holder = QWidget()
            lay = QVBoxLayout(holder)
            lay.setContentsMargins(0, 0, 6, 0)
            lay.setSpacing(12)
            builder(lay)
            lay.addStretch(1)
            scroll.setWidget(holder)
            self.pages.addWidget(scroll)
        body.addWidget(self.pages, 1)
        root.addLayout(body, 1)

        nav = QHBoxLayout()
        self.back_btn = QPushButton(_tr("guide.back"))
        self.back_btn.clicked.connect(lambda: self.go(self._step - 1))
        self.next_btn = QPushButton(_tr("guide.next"))
        self.next_btn.setDefault(True)
        self.next_btn.clicked.connect(self._next)
        self.gate_label = _label("", muted=True)
        nav.addWidget(self.back_btn)
        nav.addWidget(self.gate_label, 1, Qt.AlignVCenter)
        nav.addWidget(self.next_btn)
        root.addLayout(nav)

    # page 1 ----------------------------------------------------------------
    def _build_page_devices(self, lay: QVBoxLayout) -> None:
        lay.addWidget(_label(_tr("guide.s1.title"), size=1.3, bold=True))
        self.ready_card = _Card()
        rl = QVBoxLayout(self.ready_card)
        rl.setContentsMargins(14, 10, 14, 10)
        self.ready_label = _label("", bold=True)
        self.ready_actions = _label("")
        self.rescan_btn = QPushButton(_m(_tr("guide.s1.rescan")))
        self.rescan_btn.clicked.connect(
            self.window_ref.detect_displays_and_ports_btn_handler
        )
        rl.addWidget(self.ready_label)
        rl.addWidget(self.ready_actions)
        rl.addWidget(self.rescan_btn, 0, Qt.AlignLeft)
        lay.addWidget(self.ready_card)

        controls = _Card()
        cl = QVBoxLayout(controls)
        cl.setContentsMargins(14, 12, 14, 12)
        cl.setSpacing(6)
        self.monitor_combo = QComboBox()
        self.instrument_combo = QComboBox()
        self.mode_combo = QComboBox()
        for caption, combo in (
            (_tr("guide.s1.monitor"), self.monitor_combo),
            (_tr("guide.s1.instrument"), self.instrument_combo),
            (_tr("guide.s1.mode"), self.mode_combo),
        ):
            cl.addWidget(_label(caption, muted=True))
            cl.addWidget(combo)
        self.monitor_combo.currentIndexChanged.connect(self._monitor_changed)
        self.instrument_combo.currentIndexChanged.connect(self._instrument_changed)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.correction_label = _label("", muted=True)
        cl.addWidget(self.correction_label)

        self.ident_card = _Card()
        il = QVBoxLayout(self.ident_card)
        il.setContentsMargins(14, 12, 14, 12)
        il.setSpacing(6)
        self.ident_title = _label("", bold=True)
        self.ident_info = _label("", muted=True)
        self.candidates_box = QVBoxLayout()
        self.candidates_group = QButtonGroup(self)
        il.addWidget(self.ident_title)
        il.addWidget(self.ident_info)
        il.addLayout(self.candidates_box)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(12)
        ll.addWidget(controls)
        ll.addWidget(self.ident_card)

        self.place_card = self._make_place_card()
        lay.addWidget(_AdaptiveRow(left, self.place_card))

    def _make_place_card(self) -> QWidget:
        card = _Card()
        pl = QVBoxLayout(card)
        pl.setContentsMargins(14, 12, 14, 12)
        pl.setSpacing(6)
        pl.addWidget(_label(_tr("guide.place.title"), bold=True))
        self.illustration = QLabel()
        self.illustration.setAlignment(Qt.AlignCenter)
        pl.addWidget(self.illustration)
        pl.addWidget(_label(_tr("guide.illustration_note"), size=0.85, muted=True))
        self.accessories_label = _label("", muted=True)
        pl.addWidget(self.accessories_label)
        self.place_steps = _label("")
        pl.addWidget(self.place_steps)
        pl.addStretch(1)
        return card

    # page 2 ----------------------------------------------------------------
    def _build_page_goal(self, lay: QVBoxLayout) -> None:
        lay.addWidget(_label(_tr("guide.s2.title"), size=1.3, bold=True))
        lay.addWidget(_label(_tr("guide.s2.hint"), muted=True))
        self.builtin_note = _label(_tr("guide.s2.builtin_note"), muted=True)
        lay.addWidget(self.builtin_note)
        self.goal_group = QButtonGroup(self)
        self.goal_buttons: dict[str, QRadioButton] = {}
        self.goal_badges: dict[str, QLabel] = {}
        for goal in gm.GOALS:
            card = _Card()
            gl = QVBoxLayout(card)
            gl.setContentsMargins(14, 10, 14, 10)
            gl.setSpacing(2)
            row = QHBoxLayout()
            radio = QRadioButton(_m(_tr(goal.title_key)))
            f = radio.font()
            f.setBold(True)
            f.setPointSizeF(f.pointSizeF() * 1.1)
            radio.setFont(f)
            radio.toggled.connect(lambda on, k=goal.key: on and self._goal_chosen(k))
            self.goal_group.addButton(radio)
            self.goal_buttons[goal.key] = radio
            badge = _label(_tr("guide.s2.suggested"), size=0.85, bold=True)
            badge.setStyleSheet(f"color:{_css(_tokens()['accent'])};")
            badge.hide()
            self.goal_badges[goal.key] = badge
            row.addWidget(radio, 1)
            row.addWidget(badge, 0)
            gl.addLayout(row)
            info = _label(_tr(goal.summary_key), muted=True)
            info.setContentsMargins(24, 0, 0, 0)
            gl.addWidget(info)
            lay.addWidget(card)
        self.goal_status = _label("", muted=True)
        lay.addWidget(self.goal_status)

    # page 3 ----------------------------------------------------------------
    def _build_page_prepare(self, lay: QVBoxLayout) -> None:
        lay.addWidget(_label(_tr("guide.s3.title"), size=1.3, bold=True))
        lay.addWidget(_label(_tr("guide.s3.hint"), muted=True))
        self.prep_boxes: dict[str, QCheckBox] = {}
        for item in gm.PREPARATION:
            card = _Card()
            pl = QVBoxLayout(card)
            pl.setContentsMargins(14, 10, 14, 10)
            pl.setSpacing(2)
            cb = QCheckBox(_m(_tr(item.title_key)))
            f = cb.font()
            f.setBold(True)
            cb.setFont(f)
            cb.toggled.connect(lambda on, k=item.key: self._prep_toggled(k, on))
            self.prep_boxes[item.key] = cb
            tag = _label(
                _tr("guide.s3.required")
                if item.required
                else _tr("guide.s3.recommended"),
                size=0.8,
                bold=item.required,
                muted=not item.required,
            )
            row = QHBoxLayout()
            row.addWidget(cb, 1)
            row.addWidget(tag, 0)
            pl.addLayout(row)
            det = _label(_tr(item.detail_key), muted=True)
            det.setContentsMargins(24, 0, 0, 0)
            pl.addWidget(det)
            lay.addWidget(card)

    # page 4 ----------------------------------------------------------------
    def _build_page_measure(self, lay: QVBoxLayout) -> None:
        lay.addWidget(_label(_tr("guide.s4.title"), size=1.3, bold=True))
        lay.addWidget(_label(_tr("guide.s4.intro"), muted=True))
        card = _Card()
        sl = QVBoxLayout(card)
        sl.setContentsMargins(14, 12, 14, 12)
        sl.setSpacing(8)
        for i, key in enumerate(("adjust", "calibrate", "profile", "build"), 1):
            row = QHBoxLayout()
            n = _label(str(i), bold=True, wrap=False)
            n.setFixedWidth(18)
            row.addWidget(n, 0, Qt.AlignTop)
            row.addWidget(_label(_tr(f"guide.s4.stage.{key}")), 1)
            sl.addLayout(row)
        lay.addWidget(card)
        lay.addWidget(_label(_tr("guide.s4.patches"), muted=True))
        self.target_label = _label("")
        self.profile_name_label = _label("", muted=True)
        lay.addWidget(self.target_label)
        lay.addWidget(self.profile_name_label)
        self.start_btn = QPushButton(_m(_tr("guide.s4.start")))
        self.start_btn.setMinimumHeight(40)
        f = self.start_btn.font()
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() * 1.1)
        self.start_btn.setFont(f)
        self.start_btn.clicked.connect(self._start)
        lay.addWidget(self.start_btn)
        self.start_blocked = _label("", muted=True)
        lay.addWidget(self.start_blocked)

    # page 5 ----------------------------------------------------------------
    def _build_page_finish(self, lay: QVBoxLayout) -> None:
        lay.addWidget(_label(_tr("guide.s5.title"), size=1.3, bold=True))
        lay.addWidget(_label(_tr("guide.s5.intro"), muted=True))
        self.profile_state = _label("", bold=True)
        lay.addWidget(self.profile_state)
        self.verify_state = _label("")
        lay.addWidget(self.verify_state)
        row = QHBoxLayout()
        verify = QPushButton(_m(_tr("guide.s5.verify")))
        verify.clicked.connect(lambda: self.window_ref._select_tab("verification"))
        row.addWidget(verify)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(_label(_tr("guide.s5.what_is"), bold=True))
        for title_key, info_key in gm.CONCEPTS:
            card = _Card()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 8, 14, 8)
            cl.setSpacing(1)
            cl.addWidget(_label(_tr(title_key), bold=True))
            cl.addWidget(_label(_tr(info_key), muted=True))
            lay.addWidget(card)
        lay.addWidget(_label(_tr("guide.s5.limits"), bold=True))
        for key in gm.LIMITS:
            lay.addWidget(_label("• " + _tr(key), muted=True))

    # --------------------------------------------------------------- behaviour
    def go(self, step: int) -> None:
        """Show a step if it has been reached."""
        step = max(0, min(STEPS - 1, step))
        if step > self._reached:
            return
        self._step = step
        self.pages.setCurrentIndex(step)
        self.refresh()

    def _gate_message(self) -> str:
        if self._step == 0 and not self._readiness().ok:
            return _tr(self._readiness().message_key)
        if self._step == 1 and self._goal is None:
            return ""
        if self._step == 2 and not self._prep.complete:
            return _tr("guide.s3.missing")
        return ""

    def _can_advance(self) -> bool:
        if self._step == 0:
            return self._readiness().ok
        if self._step == 1:
            return self._goal is not None
        if self._step == 2:
            return self._prep.complete
        return self._step < STEPS - 1

    def _next(self) -> None:
        if not self._can_advance():
            return
        self._reached = max(self._reached, self._step + 1)
        self.go(self._step + 1)

    def _readiness(self) -> gm.Readiness:
        w = self.window_ref
        return gm.compute_readiness(
            argyll_found=bool(check_argyll_bin()),
            displays=list(w.worker.displays),
            instruments=list(w.worker.instruments),
            busy=bool(getattr(w, "_busy", False)),
            scan_failed=getattr(w, "_rescan_error", None) is not None,
        )

    # mirrored controls --------------------------------------------------------
    @staticmethod
    def _mirror(src: QComboBox, dst: QComboBox) -> None:
        dst.blockSignals(True)
        dst.clear()
        for i in range(src.count()):
            dst.addItem(src.itemText(i))
        dst.setCurrentIndex(src.currentIndex())
        dst.setEnabled(src.isEnabled() and src.count() > 0)
        dst.blockSignals(False)

    def _monitor_changed(self, index: int) -> None:
        if not self._syncing and index >= 0:
            self.window_ref.display_ctrl.setCurrentIndex(index)
            self.refresh()

    def _instrument_changed(self, index: int) -> None:
        if not self._syncing and index >= 0:
            self.window_ref.comport_ctrl.setCurrentIndex(index)
            self.refresh()

    def _mode_changed(self, index: int) -> None:
        if not self._syncing and index >= 0:
            self.window_ref.measurement_mode_ctrl.setCurrentIndex(index)
            self.refresh()

    def _prep_toggled(self, key: str, on: bool) -> None:
        self._prep.toggle(key, on)
        self.refresh()

    def _goal_chosen(self, key: str) -> None:
        if self._syncing:
            return
        self._goal = key
        w = self.window_ref
        path = gm.preset_path(key, list(w.presets))
        if path:
            w._load_calibration_file(path, silent=True)
            name = _tr(gm.goal_by_key(key).title_key)
            self.goal_status.setText(_tr("guide.s2.applied", name))
        else:
            self.goal_status.setText(_tr("guide.s2.not_found"))
        self.refresh()

    def _start(self) -> None:
        w = self.window_ref
        if not self._readiness().ok:
            return
        handler = w.guided_primary_action()
        if handler is not None:
            self._reached = max(self._reached, 4)
            handler()
            self.go(4)

    # refresh ----------------------------------------------------------------
    def refresh(self) -> None:
        """Re-read the window state and update every part of the panel."""
        w = self.window_ref
        self._syncing = True
        try:
            self._mirror(w.display_ctrl, self.monitor_combo)
            self._mirror(w.comport_ctrl, self.instrument_combo)
            self._mirror(w.measurement_mode_ctrl, self.mode_combo)
        finally:
            self._syncing = False
        self.rail.set_state(self._step, self._reached)
        r = self._readiness()
        self._paint_readiness(r)
        self._paint_identification()
        self._paint_goal_page()
        self._paint_measure_page(r)
        self._paint_finish_page()
        self.back_btn.setEnabled(self._step > 0)
        # Step 4 has its own primary action; there is nothing to "continue" to.
        self.next_btn.setVisible(self._step < STEPS - 2)
        self.next_btn.setEnabled(self._can_advance())
        self.gate_label.setText(self._gate_message())

    def _paint_readiness(self, r: gm.Readiness) -> None:
        t = _tokens()
        color = {gm.READY: t["ok"], gm.BUSY: t["warn"]}.get(r.status, t["bad"])
        self.ready_label.setText(_tr(r.message_key))
        self.ready_label.setStyleSheet(f"color:{_css(color)};")
        self.ready_actions.setText("\n".join("• " + _tr(k) for k in r.action_keys))
        self.ready_actions.setVisible(bool(r.action_keys))
        self.rescan_btn.setVisible(not r.ok)

    def _selected_instrument_name(self) -> str | None:
        w = self.window_ref
        idx = w.comport_ctrl.currentIndex()
        if 0 <= idx < len(w.worker.instruments):
            return w.worker.instruments[idx]
        return None

    def _paint_identification(self) -> None:
        name = self._selected_instrument_name()
        ident = ic.identify(name)
        # reset candidate radios
        for b in list(self.candidates_group.buttons()):
            self.candidates_group.removeButton(b)
            b.setParent(None)
            b.deleteLater()
        w = self.window_ref
        if ident is None:
            self.ident_title.setText(_tr("guide.s1.none"))
            self.ident_info.setText("")
            self._paint_illustration(None)
            self.correction_label.setText("")
            return
        self.ident_title.setText(_tr("guide.s1.detected_as", ident.detected_name))
        info: list[str] = []
        shared = ic.shared_usb_identity(ident.detected_name)
        if shared:
            info.append(_tr("guide.s1.shared_usb", ", ".join(shared)))
        if ident.family is None:
            info.append(_tr("guide.s1.unknown"))
        elif not ident.certain:
            info.append(_tr("guide.s1.confirm_model"))
        self.ident_info.setText("\n".join(info))
        if ident.family is not None and not ident.certain:
            chosen = self._model.get(ident.detected_name)
            for cand in ident.candidates:
                rb = QRadioButton(_m(cand))
                rb.setChecked(cand == chosen)
                rb.toggled.connect(
                    lambda on, c=cand, n=ident.detected_name: (
                        on and self._model.__setitem__(n, c)
                    )
                )
                self.candidates_group.addButton(rb)
                self.candidates_box.addWidget(rb)
        # correction status
        if ident.family is not None and ident.family.spectral:
            self.correction_label.setText(_tr("guide.s1.spectro_note"))
        else:
            ccmx = w.colorimeter_correction_matrix_ctrl
            text = (
                ccmx.currentText()
                if ccmx.isEnabled() and ccmx.currentIndex() > 0
                else ""
            )
            self.correction_label.setText(
                _tr("guide.s1.correction_set", text)
                if text
                else _tr("guide.s1.correction_none")
            )
        self._paint_illustration(ident)

    def _paint_illustration(self, ident: ic.Identification | None) -> None:
        kind = ident.family.kind if ident and ident.family else ic.KIND_OTHER
        path = config.get_data_path(f"theme/instruments/{kind}.svg")
        if path:
            from qtpy.QtGui import QImage
            from qtpy.QtSvg import QSvgRenderer

            renderer = QSvgRenderer(path)
            dpr = self.devicePixelRatioF()
            img = QImage(
                int(300 * dpr), int(206 * dpr), QImage.Format_ARGB32_Premultiplied
            )
            img.fill(Qt.transparent)
            painter = QPainter(img)
            renderer.render(painter)
            painter.end()
            pix = QPixmap.fromImage(img)
            pix.setDevicePixelRatio(dpr)
            self.illustration.setPixmap(pix)
        fam = ident.family if ident else None
        acc = fam.accessories if fam else ()
        self.accessories_label.setText(
            _tr(
                "guide.place.accessories", ", ".join(_tr(f"guide.acc.{a}") for a in acc)
            )
            if acc
            else ""
        )
        steps = ic.placement_steps(
            kind, needs_reference_tile=bool(fam and fam.needs_reference_tile)
        )
        self.place_steps.setText(
            "\n".join(f"{i}. {_tr(k)}" for i, k in enumerate(steps, 1))
        )

    def _paint_goal_page(self) -> None:
        w = self.window_ref
        idx = w.display_ctrl.currentIndex()
        dname = w.worker.displays[idx] if 0 <= idx < len(w.worker.displays) else None
        suggested = gm.suggest_goal(dname)
        self.builtin_note.setVisible(suggested is not None)
        for key, badge in self.goal_badges.items():
            badge.setVisible(key == suggested)
        self._syncing = True
        try:
            for key, rb in self.goal_buttons.items():
                rb.setChecked(key == self._goal)
        finally:
            self._syncing = False

    def _paint_measure_page(self, r: gm.Readiness) -> None:
        target = (
            _tr(gm.goal_by_key(self._goal).title_key)
            if self._goal
            else _tr("guide.s2.title")
        )
        self.target_label.setText(_tr("guide.s4.settings_summary", target))
        self.profile_name_label.setText(
            _tr(
                "guide.s4.profile_name",
                str(getcfg("profile.name.expanded") or getcfg("profile.name")),
            )
        )
        ok = r.ok and self._prep.complete and self._goal is not None
        self.start_btn.setEnabled(ok)
        self.start_blocked.setText("" if ok else _tr("guide.s4.blocked"))

    def _paint_finish_page(self) -> None:
        check = getattr(self.window_ref, "last_profile_check", None)
        self.verify_state.setText(_tr(check.message_key) if check else "")
        self.verify_state.setVisible(check is not None)
        profile = config.get_display_profile()
        if profile is None:
            self.profile_state.setText(_tr("guide.s5.no_profile"))
        else:
            try:
                desc = profile.getDescription()
            except Exception:  # noqa: BLE001 - description is cosmetic
                desc = getattr(profile, "fileName", "") or ""
            self.profile_state.setText(_tr("guide.s5.current_profile", desc))
