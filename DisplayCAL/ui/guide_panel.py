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

from html import escape
from typing import TYPE_CHECKING

from qtpy.QtCore import QEvent, QTimer, QRectF, QSize, Qt, Signal
from qtpy.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap
from qtpy.QtWidgets import (
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

from DisplayCAL import config, support
from DisplayCAL import guide_model as gm
from DisplayCAL import instrument_catalog as ic
from DisplayCAL import localization as lang
from DisplayCAL import measurement_plan as mp
from DisplayCAL import profile_name as profile_name_mod
from DisplayCAL.argyll import check_argyll_bin
from DisplayCAL.config import getcfg, setcfg
from DisplayCAL.ui.guide_prepare import PreparePage
from DisplayCAL.ui.plan_widget import ChartPlanWidget
from DisplayCAL.ui import text_scale
from DisplayCAL.ui.guide_widgets import (
    AdaptiveRow as _AdaptiveRow,
)
from DisplayCAL.ui.guide_widgets import (
    Card as _Card,
)
from DisplayCAL.ui.guide_widgets import (
    Disclosure as _Disclosure,
)
from DisplayCAL.ui.guide_widgets import (
    control_css as _control_css,
)
from DisplayCAL.ui.guide_widgets import (
    css as _css,
)
from DisplayCAL.ui.guide_widgets import (
    label as _label,
)
from DisplayCAL.ui.guide_widgets import (
    m as _m,
)
from DisplayCAL.ui.guide_widgets import (
    tokens as _tokens,
)
from DisplayCAL.ui.support_dialog import SupportInvite, invite_allowed

if TYPE_CHECKING:
    from DisplayCAL.ui.main_window import MainWindow

#: Spectrum used for the beam motif of the app icon (kept subtle in the UI).
_SPECTRUM = ("#ff5a4d", "#ffb347", "#ffe14d", "#59f07a", "#4dc9ff", "#5a7bff")

STEPS = 5

#: ``profile.type`` letter -> suffix of the existing ``profile.type.*`` label key.
_TYPE_KEYS = {
    "g": "gamma_matrix",
    "G": "single_gamma_matrix",
    "s": "shaper_matrix",
    "S": "single_shaper_matrix",
    "x": "lut.xyz",
    "X": "lut_matrix.xyz",
    "l": "lut.lab",
}


def _tr(key: str, *args: object) -> str:
    return lang.getstr(key, list(args)) if args else lang.getstr(key)


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
        self.setMinimumWidth(self._min_width())
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(lang.getstr("guide.title"))

    def _row_h(self) -> int:
        """Row height follows the font, so large text scales instead of clipping."""
        return max(60, int(self.fontMetrics().height() * 3.2))

    def _min_width(self) -> int:
        return max(176, self.fontMetrics().horizontalAdvance("M") * 15)

    def changeEvent(self, event: object) -> None:  # noqa: N802, D102
        if event.type() == QEvent.FontChange:
            self.setMinimumWidth(self._min_width())
            self.updateGeometry()
            self.update()
        super().changeEvent(event)

    def set_state(self, current: int, reached: int) -> None:
        self._current, self._reached = current, reached
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._min_width() + 14, self._row_h() * STEPS + 24)

    def _row_rect(self, i: int) -> QRectF:
        return QRectF(6, 12 + i * self._row_h(), self.width() - 12, self._row_h() - 8)

    def keyPressEvent(self, event: object) -> None:  # noqa: N802
        """Up/Down (or Left/Right) move between the steps already reached."""
        key = event.key()
        delta = {Qt.Key_Up: -1, Qt.Key_Left: -1, Qt.Key_Down: 1, Qt.Key_Right: 1}.get(
            key
        )
        if delta is None:
            super().keyPressEvent(event)
            return
        target = self._current + delta
        if 0 <= target <= self._reached:
            self.step_requested.emit(target)

    def focusInEvent(self, event: object) -> None:  # noqa: N802
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event: object) -> None:  # noqa: N802
        self.update()
        super().focusOutEvent(event)

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
        half = self._row_h() // 2 - 4
        row = self._row_h()
        p.drawLine(int(x), 12 + half, int(x), 12 + (STEPS - 1) * row + half)
        # progressed part of the line in the spectrum
        if self._current > 0:
            grad = QLinearGradient(0, 12 + half, 0, 12 + half + self._current * row)
            for i, hex_ in enumerate(_SPECTRUM):
                grad.setColorAt(i / (len(_SPECTRUM) - 1), QColor(hex_))
            p.setPen(QPen(grad, 2.5))
            p.drawLine(int(x), 12 + half, int(x), 12 + half + self._current * row)
        font = QFont(self.font())
        for i in range(STEPS):
            r = self._row_rect(i)
            cy = r.top() + r.height() / 2
            reached = i <= self._reached
            done = i < self._current
            active = i == self._current
            if active and self.hasFocus():
                p.setPen(QPen(t["accent"], 2))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(r.adjusted(2, 2, -2, -2), 8, 8)
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
            nf.setPointSizeF(font.pointSizeF() * 0.95)
            p.setFont(nf)
            p.drawText(node, Qt.AlignCenter, "✓" if done else str(i + 1))
            tf = QFont(font)
            tf.setBold(active)
            tf.setPointSizeF(font.pointSizeF() * 1.05)
            p.setFont(tf)
            p.setPen(t["text"] if reached else t["muted"])
            p.drawText(
                QRectF(x + 22, r.top(), r.width() - x - 22, r.height()),
                Qt.AlignVCenter | Qt.TextWordWrap,
                lang.getstr(f"guide.step.{i + 1}"),
            )


class GuidePanel(QWidget):
    """The guided-flow panel; one instance lives in the main window's stack."""

    #: Scrolls inside itself and keeps its footer: the window never pins it taller.
    fills_viewport = True

    def __init__(self, window: MainWindow) -> None:
        super().__init__()
        self.window_ref = window
        self._step = 0
        self._reached = 0
        self._prep = gm.PrepState()
        self._goal: str | None = None
        self._model: dict[str, str] = {}
        self._syncing = False
        self.setStyleSheet(_control_css())
        text_scale.bus.changed.connect(lambda _f: self.setStyleSheet(_control_css()))
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
        from DisplayCAL.ui.text_size_menu import TextSizeButton

        self.text_size_btn = TextSizeButton()
        head.addWidget(self.text_size_btn, 0, Qt.AlignTop)
        head.addWidget(self.advanced_btn, 0, Qt.AlignTop)
        root.addLayout(head)

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
            # Reflow first; a bar only appears if a window is narrower than any
            # wording can wrap into, so nothing is ever cut off.
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
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
        lay.addWidget(_label(_tr("guide.s1.title"), size=1.6, bold=True))
        status = QHBoxLayout()
        self.ready_label = _label("", size=1.15, bold=True)
        self.rescan_btn = QPushButton(_m(_tr("guide.s1.rescan")))
        self.rescan_btn.setFlat(True)
        self.rescan_btn.setCursor(Qt.PointingHandCursor)
        self.rescan_btn.clicked.connect(
            self.window_ref.detect_displays_and_ports_btn_handler
        )
        status.addWidget(self.ready_label, 1)
        status.addWidget(self.rescan_btn, 0, Qt.AlignRight)
        lay.addLayout(status)
        self.ready_actions = _label("", size=1.05)
        lay.addWidget(self.ready_actions)

        # Main stage: what to choose (left), where it goes (right).
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(4)
        self.monitor_combo = QComboBox()
        self.instrument_combo = QComboBox()
        self.mode_combo = QComboBox()
        for combo in (self.monitor_combo, self.instrument_combo, self.mode_combo):
            # Long monitor/instrument names are elided, not a reason to widen the page.
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(14)
            text_scale.set_scaled_font(combo, 1.15)
            text_scale.set_min_height(combo, 34)
        ll.addWidget(_label(_tr("guide.s1.monitor"), size=1.05, muted=True))
        ll.addWidget(self.monitor_combo)
        ll.addSpacing(10)
        ll.addWidget(_label(_tr("guide.s1.instrument"), size=1.05, muted=True))
        ll.addWidget(self.instrument_combo)
        # Which commercial model is it? Only asked when the identifier is shared
        # by several products; it changes the physical placement help, never
        # the measurement parameters.
        self.model_box = QWidget()
        mb = QVBoxLayout(self.model_box)
        mb.setContentsMargins(0, 6, 0, 0)
        mb.setSpacing(3)
        mb.addWidget(_label(_tr("guide.s1.model_pick"), size=1.0, muted=True))
        self.model_combo = QComboBox()
        self.model_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.model_combo.setMinimumContentsLength(14)
        text_scale.set_min_height(self.model_combo, 30)
        self.model_combo.currentIndexChanged.connect(self._model_changed)
        mb.addWidget(self.model_combo)
        ll.addWidget(self.model_box)
        self.model_hint = _label("", muted=True)
        ll.addWidget(self.model_hint)
        ll.addSpacing(10)
        # Measurement summary stays visible; the options live in the details.
        self.summary_label = _label("", size=1.05)
        ll.addWidget(self.summary_label)
        self.action_label = _label("", size=1.1, bold=True)
        ll.addSpacing(6)
        ll.addWidget(self.action_label)
        ll.addStretch(1)
        self.monitor_combo.currentIndexChanged.connect(self._monitor_changed)
        self.instrument_combo.currentIndexChanged.connect(self._instrument_changed)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)

        hero = QWidget()
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(4)
        self.illustration = QLabel()
        self.illustration.setAlignment(Qt.AlignCenter)
        # Decorative: it may be cropped in a narrow window but must never be the
        # reason the whole page needs sideways scrolling.
        self.illustration.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        hl.addWidget(self.illustration)
        self.illustration_caption = _label("", size=0.9, muted=True)
        self.illustration_caption.setAlignment(Qt.AlignCenter)
        hl.addWidget(self.illustration_caption)
        lay.addWidget(_AdaptiveRow(left, hero, threshold=720))

        lay.addWidget(_Disclosure(_tr("guide.s1.details"), self._make_details()))

    def _make_details(self) -> QWidget:
        box = QWidget()
        dl = QVBoxLayout(box)
        dl.setContentsMargins(22, 4, 0, 0)
        dl.setSpacing(6)
        dl.addWidget(_label(_tr("guide.s1.mode"), size=1.0, muted=True))
        dl.addWidget(self.mode_combo)
        self.correction_label = _label("", muted=True)
        dl.addWidget(self.correction_label)
        self.lookup_btn = self._make_lookup_button()
        dl.addWidget(self.lookup_btn, 0, Qt.AlignLeft)
        dl.addSpacing(8)
        self.ident_title = _label("", bold=True)
        self.ident_info = _label("", muted=True)
        dl.addWidget(self.ident_title)
        dl.addWidget(self.ident_info)
        return box

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
            text_scale.set_scaled_font(radio, 1.1, bold=True)
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
        # Shown only when the advanced settings were changed after a preset was
        # loaded: the objective is never changed -- or left looking unchanged --
        # in silence.
        self.goal_changed_box = _Card()
        cb = QVBoxLayout(self.goal_changed_box)
        self.goal_changed_label = _label("", size=1.0)
        cb.addWidget(self.goal_changed_label)
        crow = QHBoxLayout()
        self.goal_reapply_btn = QPushButton(_m(_tr("guide.s2.reapply")))
        self.goal_reapply_btn.clicked.connect(self._reapply_goal)
        self.goal_keep_btn = QPushButton(_m(_tr("guide.s2.keep_current")))
        self.goal_keep_btn.clicked.connect(self._keep_current)
        crow.addWidget(self.goal_reapply_btn)
        crow.addWidget(self.goal_keep_btn)
        crow.addStretch(1)
        cb.addLayout(crow)
        self.goal_changed_box.hide()
        lay.addWidget(self.goal_changed_box)

    # page 3 ----------------------------------------------------------------
    def _build_page_prepare(self, lay: QVBoxLayout) -> None:
        self.prepare = PreparePage(self._prep)
        self.prepare.changed.connect(self._prep_changed)
        lay.addWidget(self.prepare)

    def _make_lookup_button(self) -> QPushButton:
        """"Don't know the monitor's technology? Search the model" (both modes)."""
        from DisplayCAL.ui.display_lookup_dialog import lookup_button

        return lookup_button(self, on_goto_correction=self._goto_advanced_correction)

    def _goto_advanced_correction(self) -> None:
        """Open the advanced correction choice (the existing mechanism)."""
        w = self.window_ref
        if hasattr(w, "_focus_correction_choice"):
            w._focus_correction_choice()

    # page 4 ----------------------------------------------------------------
    def _build_page_measure(self, lay: QVBoxLayout) -> None:
        lay.addWidget(_label(_tr("guide.s4.title"), size=1.6, bold=True))
        lay.addWidget(_label(_tr("guide.s4.summary_title"), size=1.1, bold=True))
        self.summary_box = QWidget()
        self.summary_lay = QVBoxLayout(self.summary_box)
        self.summary_lay.setContentsMargins(0, 0, 0, 0)
        self.summary_lay.setSpacing(2)
        lay.addWidget(self.summary_box)
        self.lookup_btn2 = self._make_lookup_button()
        lay.addWidget(self.lookup_btn2, 0, Qt.AlignLeft)
        self._build_plan(lay)
        self.start_blocked = _label("", size=1.05)
        lay.addWidget(self.start_blocked)
        self.start_btn = QPushButton(_m(_tr("guide.s4.start")))
        text_scale.set_min_height(self.start_btn, 44)
        text_scale.set_scaled_font(self.start_btn, 1.15, bold=True)
        self.start_btn.clicked.connect(self._start)
        lay.addWidget(self.start_btn)
        lay.addWidget(_label(_tr("guide.s4.reminder"), size=1.05, bold=True))
        lay.addWidget(_label(_tr("guide.s4.patches"), muted=True))
        stages = QWidget()
        sl = QVBoxLayout(stages)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(4)
        sl.addWidget(_label(_tr("guide.s4.intro"), muted=True))
        for i, key in enumerate(("adjust", "calibrate", "profile", "build"), 1):
            sl.addWidget(_label(f"{i}. {_tr(f'guide.s4.stage.{key}')}"))
        lay.addWidget(_Disclosure(_tr("guide.s4.stages_title"), stages))
        lay.addWidget(
            _Disclosure(
                _tr("guide.s4.interrupt_title"),
                _label(_tr("guide.s4.interrupt"), muted=True),
            )
        )

    # page 5 ----------------------------------------------------------------
    def _build_plan(self, lay: QVBoxLayout) -> None:
        """The measurement plan: what will be measured, how long, how safely."""
        lay.addSpacing(6)
        lay.addWidget(_label(_tr("plan.title"), size=1.1, bold=True))
        self.plan_type = _label("", size=1.05)
        self.plan_type_use = _label("", muted=True)
        for w in (self.plan_type, self.plan_type_use):
            lay.addWidget(w)
        # Chart total, chart chooser, block size, blocks and time: one shared
        # widget (also in the advanced Profiling tab), one configuration.
        self.plan_widget = ChartPlanWidget(self.window_ref)
        self.block_combo = self.plan_widget.block_combo
        lay.addWidget(self.plan_widget)
        # Unattended running: say what is held and what is not.
        # The label wraps (a QCheckBox's own text cannot), so a long translation
        # never forces the page wider; the label toggles the box like its own text.
        self.awake_cb = QCheckBox()
        self.awake_cb.setAccessibleName(_tr("awake.keep"))
        self.awake_cb.setChecked(bool(getcfg("session.keep_awake")))
        self.awake_cb.toggled.connect(lambda on: setcfg("session.keep_awake", int(on)))
        awake_row = QHBoxLayout()
        awake_row.setContentsMargins(0, 0, 0, 0)
        awake_row.addWidget(self.awake_cb, 0, Qt.AlignTop)
        awake_label = _label(_tr("awake.keep"), size=1.0)
        awake_label.setTextInteractionFlags(Qt.NoTextInteraction)
        awake_label.mousePressEvent = lambda _e: self.awake_cb.toggle()
        awake_label.setCursor(Qt.PointingHandCursor)
        awake_row.addWidget(awake_label, 1)
        lay.addLayout(awake_row)
        self.awake_note = _label("", muted=True)
        lay.addWidget(self.awake_note)
        # What each choice means: the four separate topics, expandable.
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(22, 4, 0, 0)
        bl.setSpacing(6)
        bl.addWidget(_label(_tr("plan.three.title"), bold=True))
        bl.addWidget(_label(_tr("plan.three.text"), muted=True))
        for key in ("cal", "prof", "icc", "chart"):
            bl.addWidget(_label(_tr(f"plan.{key}.title"), bold=True))
            bl.addWidget(_label(_tr(f"plan.{key}.text"), muted=True))
            if key == "chart":
                bl.addWidget(_label(_tr("plan.chart.limit"), muted=True))
        for letter in mp.PROFILE_TYPES:
            use, cost = mp.type_keys(letter)
            name = _tr(f"profile.type.{_TYPE_KEYS[letter]}")
            bl.addWidget(_label(f"• {name}: {_tr(use)} {_tr(cost)}", muted=True))
        bl.addWidget(_label(_tr("plan.macos.title"), bold=True))
        bl.addWidget(_label(_tr("plan.macos.text"), muted=True))
        bl.addWidget(_label(_tr("plan.compare.title"), bold=True))
        bl.addWidget(_label(_tr("plan.compare.text"), muted=True))
        bl.addWidget(_label(_tr("plan.blocks.title"), bold=True))
        bl.addWidget(_label(_tr("plan.blocks.text"), muted=True))
        lay.addWidget(_Disclosure(_tr("guide.s4.choices_title"), body))

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
        # Discreet, voluntary and closable for good; shown only once a flow has
        # really finished (profile installed and read back), never during
        # preparation, measurement, installation or after an error.
        self.invite = SupportInvite(support.app_version_line())
        self.invite.setVisible(False)
        lay.addWidget(self.invite)

    # --------------------------------------------------------------- behaviour
    def on_profile_built(self) -> None:
        """A valid profile now exists: open the install-and-verify step."""
        self._reached = max(self._reached, STEPS - 1)
        self.go(STEPS - 1)

    def go(self, step: int) -> None:
        """Show a step if it has been reached."""
        step = max(0, min(STEPS - 1, step))
        if step > self._reached:
            return
        leaving_prep = self._step == 2 and step != 2
        self._step = step
        self.pages.setCurrentIndex(step)
        if leaving_prep:
            self.prepare.stop_motion()
        if step == 2:
            self.prepare.on_shown()
        self.refresh()
        self.relayout_page()

    def relayout_page(self) -> None:
        """Recompute the current page's layout after its content changed.

        Wrapped labels and rows replaced after the first layout pass otherwise
        keep a stale, too small height until the window is resized.
        """
        self._relayout_now()
        QTimer.singleShot(0, self._relayout_now)  # once the page is shown

    def _relayout_now(self) -> None:
        page = self.pages.currentWidget()
        holder = page.widget() if page is not None else None
        if holder is not None and holder.layout() is not None:
            holder.layout().invalidate()
            holder.layout().activate()

    def stop_motion(self) -> None:
        """Stop every decorative animation (called before any measurement)."""
        self.prepare.stop_motion()

    def hideEvent(self, event: object) -> None:  # noqa: N802, D102
        self.stop_motion()
        super().hideEvent(event)

    def _gate_message(self) -> str:
        if self._step == 0 and not self._readiness().ok:
            return _tr(self._readiness().message_key)
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

    def _model_changed(self, index: int) -> None:
        """The user picked their exact model (or "not sure"); placement help only."""
        if self._syncing:
            return
        name = self._selected_instrument_name()
        if not name or index < 0:
            return
        data = self.model_combo.itemData(index)
        if data is None:
            self._model.pop(name, None)
        else:
            self._model[name] = data
        self.refresh()

    def _prep_changed(self) -> None:
        if hasattr(self, "gate_label"):
            self.refresh()

    def _goal_chosen(self, key: str) -> None:
        if self._syncing:
            return
        self._goal = key
        w = self.window_ref
        if key == "current":
            # No preset: the advanced settings stay exactly as they are.
            self._goal_snapshot = None
            self.goal_status.setText(_tr("guide.s2.kept"))
            self.refresh()
            return
        path = gm.preset_path(key, list(w.presets))
        if path:
            w._load_calibration_file(path, silent=True)
            name = _tr(gm.goal_by_key(key).title_key)
            self.goal_status.setText(_tr("guide.s2.applied", name))
            self._goal_snapshot = self._objective_snapshot()
        else:
            self._goal_snapshot = None
            self.goal_status.setText(_tr("guide.s2.not_found"))
        self.refresh()

    # one configuration for both modes ---------------------------------------
    def _objective_snapshot(self) -> dict:
        return {k: getcfg(k) for k in gm.objective_keys(config.DEFAULTS)}

    def goal_changes(self) -> list[str]:
        """Objective settings changed (e.g. in the advanced tabs) since the preset."""
        snap = getattr(self, "_goal_snapshot", None)
        if self._goal in (None, "current") or snap is None:
            return []
        return gm.objective_changes(snap, self._objective_snapshot())

    def _reapply_goal(self) -> None:
        if self._goal and self._goal != "current":
            key = self._goal
            self._goal = None
            self._goal_chosen(key)

    def _keep_current(self) -> None:
        self.goal_buttons["current"].setChecked(True)

    def _paint_goal_changes(self) -> None:
        changed = self.goal_changes()
        self.goal_changed_box.setVisible(bool(changed))
        if changed:
            name = _tr(gm.goal_by_key(self._goal).title_key)
            self.goal_changed_label.setText(_tr("guide.s2.modified", name, len(changed)))

    def _start(self) -> None:
        w = self.window_ref
        if not self._readiness().ok or not self._prep.complete or self._goal is None:
            return
        # Nothing decorative may run while patches are shown.
        self.stop_motion()
        handler = w.guided_primary_action()
        if handler is not None:
            # Stay on this step while the run happens (it can be cancelled);
            # the last step opens once a valid profile has actually been built.
            handler()

    # refresh ----------------------------------------------------------------
    def _selected_instrument_name(self) -> str | None:
        w = self.window_ref
        idx = w.comport_ctrl.currentIndex()
        if 0 <= idx < len(w.worker.instruments):
            return w.worker.instruments[idx]
        return None

    def _chosen_model(self, ident: ic.Identification | None) -> str | None:
        return self._model.get(ident.detected_name) if ident else None

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
        ident = ic.identify(self._selected_instrument_name())
        self._paint_readiness(r)
        self._paint_identification(ident)
        self.prepare.set_context(self._goal, ident, self._chosen_model(ident))
        self._paint_goal_page()
        self._paint_measure_page(r, ident)
        self._paint_finish_page()
        self.back_btn.setEnabled(self._step > 0)
        # Step 4 has its own primary action; there is nothing to "continue" to.
        self.next_btn.setVisible(self._step < STEPS - 2)
        self.next_btn.setEnabled(self._can_advance())
        self.gate_label.setText(self._gate_message())
        self.relayout_page()

    def _paint_readiness(self, r: gm.Readiness) -> None:
        t = _tokens()
        color = {gm.READY: t["ok"], gm.BUSY: t["warn"]}.get(r.status, t["bad"])
        self.ready_label.setText("●  " + _tr(r.message_key))
        self.ready_label.setStyleSheet(f"color:{_css(color)};")
        self.ready_actions.setText("\n".join("• " + _tr(k) for k in r.action_keys))
        self.ready_actions.setVisible(bool(r.action_keys))
        self.rescan_btn.setVisible(True)
        self.action_label.setText(
            _tr("guide.s1.action_ready") if r.ok else _tr("guide.s1.action_fix")
        )

    def _paint_identification(self, ident: ic.Identification | None) -> None:
        self._paint_identification_now(ident)
        # The model question appears/disappears and its text changes: have the
        # page recompute wrapped heights so no line is covered by the next control.
        self.relayout_page()

    def _paint_identification_now(self, ident: ic.Identification | None) -> None:
        w = self.window_ref
        mode = self.mode_combo.currentText()
        self._syncing = True
        try:
            self.model_combo.clear()
            ask_model = bool(ident and ident.family is not None and not ident.certain)
            self.model_box.setVisible(ask_model)
            if ask_model:
                self.model_combo.addItem(_tr("guide.s1.model_choose"), None)
                for cand in ident.candidates:
                    self.model_combo.addItem(cand, cand)
                self.model_combo.addItem(_tr("guide.s1.model_unsure"), "")
                chosen = self._model.get(ident.detected_name)
                idx = self.model_combo.findData(chosen) if chosen is not None else 0
                self.model_combo.setCurrentIndex(max(idx, 0))
        finally:
            self._syncing = False
        if ident is None:
            self.ident_title.setText(_tr("guide.s1.none"))
            self.ident_info.setText("")
            self.model_hint.setText("")
            self.correction_label.setText("")
            self.summary_label.setText("")
            self._paint_illustration(None)
            return
        self.ident_title.setText(_tr("guide.s1.detected_as", ident.detected_name))
        info: list[str] = []
        shared = ic.shared_usb_identity(ident.detected_name)
        if shared:
            info.append(_tr("guide.s1.shared_usb", ", ".join(shared)))
        if ident.family is None:
            info.append(_tr("guide.s1.unknown"))
        self.ident_info.setText("\n".join(info))
        chosen = self._model.get(ident.detected_name)
        if ident.family is not None and not ident.certain:
            if chosen:
                self.model_hint.setText(f"{chosen} — {_tr('guide.state.confirmed')}")
            else:
                self.model_hint.setText(_tr("guide.s1.model_unconfirmed_hint"))
        elif ident.family is None:
            self.model_hint.setText(_tr("guide.s1.unknown_short"))
        else:
            self.model_hint.setText("")
        if ident.family is not None and ident.family.spectral:
            corr_short = _tr("guide.s1.correction_not_needed")
            self.correction_label.setText(_tr("guide.s1.spectro_note"))
        else:
            ccmx = w.colorimeter_correction_matrix_ctrl
            text = (
                ccmx.currentText()
                if ccmx.isEnabled() and ccmx.currentIndex() > 0
                else ""
            )
            corr_short = text or _tr("guide.s1.correction_none_short")
            self.correction_label.setText(
                _tr("guide.s1.correction_set", text)
                if text
                else _tr("guide.s1.correction_none")
            )
        self._correction_short = corr_short
        self.summary_label.setText(_tr("guide.s1.summary", mode or "—", corr_short))
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
                int(340 * dpr), int(234 * dpr), QImage.Format_ARGB32_Premultiplied
            )
            img.fill(Qt.transparent)
            painter = QPainter(img)
            renderer.render(painter)
            painter.end()
            pix = QPixmap.fromImage(img)
            pix.setDevicePixelRatio(dpr)
            self.illustration.setPixmap(pix)
        self.illustration_caption.setText(_tr(f"guide.place.kind.{kind}"))

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
        self._paint_goal_changes()

    def _paint_measure_page(
        self, r: gm.Readiness, ident: ic.Identification | None
    ) -> None:
        w = self.window_ref
        didx = w.display_ctrl.currentIndex()
        monitor = (
            w.worker.displays[didx] if 0 <= didx < len(w.worker.displays) else None
        )
        model = self._chosen_model(ident) or None
        needs_choice = bool(ident and ident.family is not None and not ident.certain)
        goal_title = _tr(gm.goal_by_key(self._goal).title_key) if self._goal else None
        if goal_title and self.goal_changes():
            goal_title += f" — {_tr('guide.goal.modified_suffix')}"
        lines = gm.start_summary(
            monitor=monitor,
            instrument=ident.detected_name if ident else None,
            model=model,
            model_needs_choice=needs_choice,
            correction=getattr(self, "_correction_short", ""),
            goal_title=goal_title,
            prep=self._prep,
            readiness=r,
        )
        while self.summary_lay.count():
            item = self.summary_lay.takeAt(0).widget()
            if item is not None:
                item.setParent(None)
                item.deleteLater()
        t = _tokens()
        colors = {
            gm.DETECTED: t["muted"],
            gm.CONFIRMED: t["ok"],
            gm.UNVERIFIED: t["warn"],
            gm.BLOCKING: t["bad"],
        }
        for ln in lines:
            value = _tr(ln.value) if ln.value.startswith("guide.") else ln.value
            row = QLabel(
                f"<b>{escape(_tr(ln.label_key))}:</b> {escape(value)} "
                f'<span style="color:{_css(colors[ln.state])}">'
                f"· {escape(_tr('guide.state.' + ln.state))}</span>"
            )
            row.setTextFormat(Qt.RichText)
            row.setWordWrap(True)
            self.summary_lay.addWidget(row)
        # Rows were replaced after the first layout pass: have the box and the
        # page recompute their wrapped heights so lines never overlap.
        self.summary_lay.invalidate()
        self._paint_plan()
        self.relayout_page()
        ok = r.ok and self._prep.complete and self._goal is not None
        self.start_btn.setEnabled(ok)
        if ok:
            self.start_blocked.setText("")
        elif not self._prep.complete:
            self.start_blocked.setText(_tr("guide.s4.blocked_prep"))
        else:
            self.start_blocked.setText(_tr("guide.s4.blocked"))

    def _paint_plan(self) -> None:
        w = self.window_ref
        letter = str(getcfg("profile.type"))
        name = _tr(f"profile.type.{_TYPE_KEYS.get(letter, 'shaper_matrix')}")
        use, cost = mp.type_keys(letter if letter in mp.PROFILE_TYPES else "S")
        self.plan_type.setText(
            _tr("plan.type.value", name) + "  " + _tr("plan.type.change")
        )
        self.plan_type_use.setText(_tr(cost))  # what each type means: see the details below
        self.plan_widget.refresh()
        self.awake_note.setText(
            _tr("awake.on" if getcfg("session.keep_awake") else "awake.off")
            + " "
            + _tr("awake.cannot")
        )

    def _paint_finish_page(self) -> None:
        check = getattr(self.window_ref, "last_profile_check", None)
        self.verify_state.setText(_tr(check.message_key) if check else "")
        self.verify_state.setVisible(check is not None)
        finished = bool(check is not None and check.verified)
        self.invite.setVisible(
            finished
            and invite_allowed(support.app_version_line())
            and not getattr(self.window_ref, "_busy", False)
        )
        profile = config.get_display_profile()
        if profile is None:
            self.profile_state.setText(_tr("guide.s5.no_profile"))
        else:
            try:
                desc = profile.getDescription()
            except Exception:  # noqa: BLE001 - description is cosmetic
                desc = getattr(profile, "fileName", "") or ""
            self.profile_state.setText(_tr("guide.s5.current_profile", desc))
