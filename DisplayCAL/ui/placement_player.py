"""Controllable placement sequence: how to put the instrument on the screen.

A short, calm sequence (one scene per physical step) with play/pause, manual
previous/next, and an always-visible static list of the same steps as the
accessible alternative. It honours the system's reduced-motion preference (no
autoplay, no easing: steps are shown as finished frames) and is *decorative
only*: it lives on the preparation page, is stopped before any measurement
and never touches the measurement (patch) window.

Scenes are drawn with ``QPainter`` from the instrument variant and the step id,
so there are no external animation assets to ship.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from qtpy.QtCore import QPointF, QRectF, Qt, QTimer
from qtpy.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from qtpy.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import instrument_catalog as ic
from DisplayCAL.ui import text_scale
from DisplayCAL import localization as lang
from DisplayCAL.ui.motion import prefers_reduced_motion

ANIM_MS = 2200
HOLD_MS = 1300
TICK_MS = 33


class Timeline:
    """Pure playback state of the sequence (testable without Qt)."""

    def __init__(self, n_steps: int, reduced: bool = False) -> None:
        self.n = max(1, n_steps)
        self.reduced = reduced
        self.step = 0
        self.t = 1.0 if reduced else 0.0
        self.playing = False
        self._elapsed = 0

    def set_steps(self, n_steps: int) -> None:
        """Change the number of steps (instrument changed); restart at step 0."""
        self.n = max(1, n_steps)
        self.goto(0)
        self.pause()

    def play(self) -> None:
        """Start (or resume) playback; from the end, restart at the first step."""
        if self.step >= self.n - 1 and self.t >= 1.0:
            self.step, self.t, self._elapsed = 0, (1.0 if self.reduced else 0.0), 0
        self.playing = True

    def pause(self) -> None:
        """Stop advancing; the current frame stays."""
        self.playing = False

    def goto(self, step: int) -> None:
        """Show a step as a finished frame (manual stepping pauses playback)."""
        self.step = max(0, min(self.n - 1, step))
        self.t = 1.0
        self._elapsed = 0
        self.playing = False

    def next(self) -> None:
        """Go to the next step."""
        self.goto(self.step + 1)

    def prev(self) -> None:
        """Go to the previous step."""
        self.goto(self.step - 1)

    def tick(self, dt_ms: int) -> bool:
        """Advance playback by ``dt_ms``; return whether the frame changed."""
        if not self.playing:
            return False
        self._elapsed += dt_ms
        before = (self.step, self.t)
        if self.reduced:
            if self._elapsed >= ANIM_MS + HOLD_MS:
                self._advance()
        else:
            self.t = min(1.0, self._elapsed / ANIM_MS)
            if self._elapsed >= ANIM_MS + HOLD_MS:
                self._advance()
        return (self.step, self.t) != before

    def _advance(self) -> None:
        self._elapsed = 0
        if self.step < self.n - 1:
            self.step += 1
            self.t = 1.0 if self.reduced else 0.0
        else:
            self.t = 1.0
            self.playing = False


def _ease(t: float) -> float:
    return t * t * (3 - 2 * t)


@dataclass
class _Colors:
    screen_top: QColor
    screen_bottom: QColor
    bezel: QColor
    device: QColor
    device_edge: QColor
    lens: QColor
    accent: QColor
    spot: QColor
    cable: QColor


def _colors(dark: bool) -> _Colors:
    return _Colors(
        QColor("#2b2d33"),
        QColor("#15161a"),
        QColor("#474a52") if dark else QColor("#3a3d44"),
        QColor("#34363c"),
        QColor("#9a9da6"),
        QColor("#10131c"),
        QColor("#d4147a"),
        QColor(125, 127, 133, 150),
        QColor("#80838c"),
    )


# Logical scene size; the widget scales it to fit.
W, H = 380.0, 250.0
SCREEN = QRectF(52, 26, 276, 148)
SPOT = QPointF(190, 100)


def _draw_monitor(p: QPainter, c: _Colors, tilt: float = 0.0) -> None:
    p.save()
    p.setPen(Qt.NoPen)
    # stand
    p.setBrush(c.bezel)
    stand = QPainterPath()
    stand.moveTo(172, 174)
    stand.lineTo(208, 174)
    stand.lineTo(216, 206)
    stand.lineTo(164, 206)
    stand.closeSubpath()
    p.drawPath(stand)
    p.drawRoundedRect(QRectF(132, 204, 116, 9), 4, 4)
    # body (tilt squeezes the panel a little to suggest leaning back)
    squeeze = 1.0 - 0.07 * tilt
    body = QRectF(
        SCREEN.x() - 10,
        SCREEN.y() - 8 + 14 * tilt,
        SCREEN.width() + 20,
        (SCREEN.height() + 16) * squeeze,
    )
    p.setBrush(c.bezel)
    p.drawRoundedRect(body, 11, 11)
    glass = body.adjusted(8, 8, -8, -8)
    grad = QLinearGradient(glass.topLeft(), glass.bottomLeft())
    grad.setColorAt(0, c.screen_top)
    grad.setColorAt(1, c.screen_bottom)
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(glass, 6, 6)
    p.restore()


def _draw_spot(p: QPainter, c: _Colors, highlight: float = 0.0) -> None:
    p.save()
    r = QRectF(SPOT.x() - 31, SPOT.y() - 31, 62, 62)
    p.setBrush(c.spot)
    p.setPen(QPen(c.accent, 2) if highlight > 0.01 else Qt.NoPen)
    if highlight > 0.01:
        pen = QPen(
            QColor(
                c.accent.red(), c.accent.green(), c.accent.blue(), int(220 * highlight)
            ),
            2,
        )
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
    p.drawRoundedRect(r, 3, 3)
    p.restore()


def _draw_puck(
    p: QPainter,
    c: _Colors,
    centre: QPointF,
    radius: float,
    *,
    square: bool = False,
    lens_visible: bool = True,
    foam: bool = False,
    x_scale: float = 1.0,
    shadow: float = 0.0,
) -> None:
    p.save()
    p.translate(centre)
    p.scale(x_scale, 1.0)
    if shadow > 0:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, int(90 * shadow)))
        p.drawEllipse(
            QPointF(0, radius * 0.18 * (1 + shadow)), radius * 1.05, radius * 1.05
        )
    body = QRectF(-radius, -radius, 2 * radius, 2 * radius)
    grad = QRadialGradient(QPointF(-radius * 0.3, -radius * 0.35), radius * 1.6)
    grad.setColorAt(0, QColor("#6b6e76"))
    grad.setColorAt(0.5, c.device)
    grad.setColorAt(1, QColor("#16171a"))
    p.setBrush(QBrush(grad))
    p.setPen(QPen(c.device_edge, 1.5))
    if square:
        p.drawRoundedRect(body, radius * 0.5, radius * 0.5)
    else:
        p.drawEllipse(body)
    if foam:
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#d8d9dd"), 2.2))
        p.drawEllipse(QPointF(0, 0), radius * 0.74, radius * 0.74)
    if lens_visible:
        p.setPen(QPen(QColor("#4e5159"), 2))
        p.setBrush(c.lens)
        p.drawEllipse(QPointF(0, 0), radius * 0.46, radius * 0.46)
        lens = QRadialGradient(QPointF(-radius * 0.1, -radius * 0.15), radius * 0.4)
        lens.setColorAt(0, QColor("#6d7fb8"))
        lens.setColorAt(1, QColor("#07080b"))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(lens))
        p.drawEllipse(QPointF(0, 0), radius * 0.34, radius * 0.34)
    else:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 20))
        p.drawEllipse(QPointF(0, 0), radius * 0.5, radius * 0.5)
    p.restore()


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _draw_cable(
    p: QPainter, c: _Colors, start: QPointF, progress: float, weight: bool
) -> None:
    """Cable from the device up and over the top edge to a weight behind."""
    top = SCREEN.y() - 8
    pts = [start, QPointF(start.x(), top - 4), QPointF(start.x() + 18, top - 12)]
    total = sum(math.dist((a.x(), a.y()), (b.x(), b.y())) for a, b in zip(pts, pts[1:]))
    target = total * progress
    p.save()
    p.setPen(QPen(c.cable, 3, Qt.SolidLine, Qt.RoundCap))
    drawn = 0.0
    last = pts[0]
    for a, b in zip(pts, pts[1:]):
        seg = math.dist((a.x(), a.y()), (b.x(), b.y()))
        if drawn + seg <= target:
            p.drawLine(a, b)
            last = b
            drawn += seg
        else:
            f = (target - drawn) / seg if seg else 0
            last = QPointF(_lerp(a.x(), b.x(), f), _lerp(a.y(), b.y(), f))
            p.drawLine(a, last)
            break
    if weight and progress > 0.6:
        w = (progress - 0.6) / 0.4
        p.setPen(QPen(QColor("#0d0e10"), 1))
        p.setBrush(QColor("#4a4d55"))
        p.drawRoundedRect(
            QRectF(last.x() - 9, last.y() - 6 + 10 * (1 - w) * -1, 18, 14), 3, 3
        )
    p.restore()


def draw_scene(  # noqa: PLR0917
    p: QPainter,
    step: str,
    t: float,
    variant: str,
    kind: str,
    dark: bool,
) -> None:
    """Paint one frame of the sequence into the logical 380x250 scene."""
    c = _colors(dark)
    e = _ease(t)
    square = kind in (ic.KIND_SPECTRO_PUCK,)
    radius = 24.0
    if step == "calibrate":
        # device on a reference tile / base, lower left
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#d8d9dd"))
        p.drawRoundedRect(QRectF(120, 160, 140, 36), 6, 6)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawEllipse(QPointF(190, 200), 70, 7)
        p.restore()
        _draw_puck(
            p, c, QPointF(190, _lerp(120, 146, e)), radius, square=square, shadow=0.4
        )
        return
    if step == "tilt":
        # side view: the display leans back a few degrees, the unit stays put
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 50))
        p.drawEllipse(QPointF(190, 214), 120, 8)
        p.restore()
        angle = _lerp(0, 6, e)
        p.save()
        p.translate(150, 206)
        p.rotate(angle)
        p.setPen(Qt.NoPen)
        p.setBrush(c.bezel)
        p.drawRoundedRect(QRectF(-8, -170, 16, 170), 4, 4)
        p.setBrush(c.screen_bottom)
        p.drawRoundedRect(QRectF(4, -166, 6, 160), 2, 2)
        p.setBrush(c.device)
        p.setPen(QPen(c.device_edge, 1.5))
        p.drawRoundedRect(QRectF(10, -110, 16, 38), 5, 5)
        p.restore()
        p.save()
        p.setPen(QPen(c.accent, 2, Qt.DashLine))
        p.drawArc(QRectF(100, 110, 100, 100), 90 * 16, int(-angle * 16))
        p.restore()
        return

    tilt = 0.0
    _draw_monitor(p, c, tilt)
    _draw_spot(p, c, highlight=(e if step == "position" else 0.0))

    if step == "face":
        # the unit turns over to show which side faces the screen
        scale = abs(math.cos(math.pi * e))
        showing_lens = e > 0.5
        _draw_puck(
            p,
            c,
            QPointF(190, 112),
            30,
            square=square,
            lens_visible=showing_lens,
            foam=(variant == "i1d3" and showing_lens),
            x_scale=max(0.06, scale),
            shadow=0.3,
        )
        return
    if step == "diffuser":
        # ambient diffuser arm swings from over the optics to the rear position
        _draw_puck(p, c, QPointF(190, 112), 30, foam=True, shadow=0.3)
        p.save()
        p.translate(190, 112)
        p.rotate(_lerp(0, -150, e))
        p.setPen(QPen(QColor("#0d0e10"), 1))
        p.setBrush(QColor("#7b7e87"))
        p.drawRoundedRect(QRectF(-8, -30, 16, 52), 7, 7)
        p.restore()
        return
    if step == "cover":
        _draw_puck(p, c, QPointF(190, 112), 28, foam=False, shadow=0.3)
        p.save()
        p.setPen(QPen(QColor("#0d0e10"), 1))
        p.setBrush(QColor(110, 113, 122, int(255 * (1 - 0.6 * e))))
        cx = _lerp(190, 280, e)
        cy = _lerp(112, 58, e)
        p.drawEllipse(QPointF(cx, cy), 26 - 8 * e, 26 - 8 * e)
        p.restore()
        return
    if step == "cable":
        _draw_puck(p, c, QPointF(190, 100), 24, foam=(variant == "i1d3"), shadow=0.2)
        _draw_cable(p, c, QPointF(190, 78), e, weight=(variant == "i1d3"))
        return
    if step == "contact":
        s = _lerp(1.35, 1.0, e)
        _draw_puck(
            p,
            c,
            QPointF(190, 100),
            24 * s,
            square=square,
            foam=(variant == "i1d3"),
            shadow=_lerp(1.0, 0.15, e),
        )
        return
    if step == "position":
        x = _lerp(262, SPOT.x(), e)
        y = _lerp(128, SPOT.y(), e)
        _draw_puck(
            p, c, QPointF(x, y), 24, square=square, foam=(variant == "i1d3"), shadow=0.2
        )
        return
    # unknown step id: just the device on the spot
    _draw_puck(p, c, SPOT, 24, square=square, shadow=0.2)


class _Canvas(QWidget):
    """Paints the current scene; scales the logical scene to the widget."""

    def __init__(self) -> None:
        super().__init__()
        self.step = "face"
        self.t = 1.0
        self.variant = "generic"
        self.kind = ic.KIND_COLORIMETER
        self.setMinimumSize(240, 158)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, w: int) -> int:  # noqa: N802
        return int(w * H / W)

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        from DisplayCAL.ui import design_a

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # A figure is a print on its own paper: the same in light and dark.
        card = QColor(design_a.tokens().inset)
        edge = QColor(design_a.tokens().ink)
        edge.setAlpha(40)
        p.setPen(QPen(edge, 1))
        p.setBrush(card)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)
        scale = min(self.width() / W, self.height() / H)
        p.save()
        p.translate((self.width() - W * scale) / 2, (self.height() - H * scale) / 2)
        p.scale(scale, scale)
        draw_scene(p, self.step, self.t, self.variant, self.kind, False)
        p.restore()
        p.setClipping(False)


class PlacementPlayer(QWidget):
    """Canvas + controls + the static, always-visible list of the steps."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._reduced = prefers_reduced_motion()
        self._steps: list[str] = list(ic.GENERIC_STEPS)
        self._variant = "generic"
        self._timeline = Timeline(len(self._steps), self._reduced)
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._on_tick)
        self._started_once = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        self.canvas = _Canvas()
        root.addWidget(self.canvas)

        self.caption = QLabel()
        self.caption.setWordWrap(True)
        self.caption.setTextFormat(Qt.PlainText)
        text_scale.set_scaled_font(self.caption, 1.1, bold=True)
        root.addWidget(self.caption)

        controls = QHBoxLayout()
        self.prev_btn = QPushButton("◀")
        self.play_btn = QPushButton()
        self.next_btn = QPushButton("▶")
        for b in (self.prev_btn, self.play_btn, self.next_btn):
            b.setCursor(Qt.PointingHandCursor)
            b.setAutoDefault(False)
        self.prev_btn.setAccessibleName(lang.getstr("guide.pl.prev"))
        self.next_btn.setAccessibleName(lang.getstr("guide.pl.next"))
        self.prev_btn.clicked.connect(self._prev)
        self.next_btn.clicked.connect(self._next)
        self.play_btn.clicked.connect(self._toggle)
        self.counter = QLabel()
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.next_btn)
        controls.addWidget(self.counter, 1, Qt.AlignRight)
        root.addLayout(controls)
        self._render()

    # --- public ---------------------------------------------------------
    @property
    def reduced_motion(self) -> bool:
        """Whether the system asked for reduced motion."""
        return self._reduced

    def is_playing(self) -> bool:
        """Whether the sequence is currently advancing."""
        return self._timeline.playing

    def set_sequence(self, steps: list[str], variant: str, kind: str) -> None:
        """Show another instrument's steps (resets to the first, paused)."""
        self._steps = list(steps) or list(ic.GENERIC_STEPS)
        self._variant = variant
        self.canvas.variant = variant
        self.canvas.kind = kind
        self._timeline.set_steps(len(self._steps))
        self._timer.stop()
        self._render()

    def autoplay_once(self) -> None:
        """Start the sequence the first time the page is shown (never when reduced)."""
        if self._started_once or self._reduced:
            return
        self._started_once = True
        self._timeline.goto(0)
        self._timeline.t = 0.0
        self._timeline.play()
        self._timer.start()
        self._render()

    def stop(self) -> None:
        """Stop all motion (leaving the page, or before any measurement)."""
        self._timeline.pause()
        try:
            self._timer.stop()
        except RuntimeError:  # Qt already destroyed it (window closing)
            return
        self._render()

    # --- internals ------------------------------------------------------
    def _step_id(self) -> str:
        return self._steps[min(self._timeline.step, len(self._steps) - 1)]

    def _render(self) -> None:
        try:
            self._render_now()
        except RuntimeError:
            # Qt already destroyed the labels (window closing): nothing to draw.
            self._timer.stop()

    def _render_now(self) -> None:
        tl = self._timeline
        step = self._step_id()
        self.canvas.step = step
        self.canvas.t = tl.t
        self.canvas.update()
        title = lang.getstr(f"guide.pl.step.{step}")
        self.caption.setText(f"{tl.step + 1}. {title}")
        self.counter.setText(f"{tl.step + 1} / {tl.n}")
        self.prev_btn.setEnabled(tl.step > 0)
        self.next_btn.setEnabled(tl.step < tl.n - 1)
        self.play_btn.setText(
            lang.getstr("guide.pl.pause" if tl.playing else "guide.pl.play")
        )
        self.canvas.setAccessibleName(title)
        self.canvas.setAccessibleDescription(lang.getstr("guide.pl.canvas_desc"))

    def _on_tick(self) -> None:
        if self._timeline.tick(TICK_MS):
            self._render()
        if not self._timeline.playing:
            self._timer.stop()
            self._render()

    def _toggle(self) -> None:
        if self._timeline.playing:
            self.stop()
        else:
            self._timeline.play()
            self._timer.start()
            self._render()

    def _prev(self) -> None:
        self._timer.stop()
        self._timeline.prev()
        self._render()

    def _next(self) -> None:
        self._timer.stop()
        self._timeline.next()
        self._render()

    def keyPressEvent(self, event: object) -> None:  # noqa: N802, D102
        key = event.key()
        if key == Qt.Key_Left:
            self._prev()
        elif key == Qt.Key_Right:
            self._next()
        elif key == Qt.Key_Space:
            self._toggle()
        else:
            super().keyPressEvent(event)
