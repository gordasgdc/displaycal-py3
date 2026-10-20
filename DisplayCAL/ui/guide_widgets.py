"""Small shared widgets and tokens of the guided flow (no behaviour of their own)."""

from __future__ import annotations

from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QApplication,
    QBoxLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config
from DisplayCAL.ui import text_scale


def tokens() -> dict[str, QColor]:
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
        # Secondary text is never "disabled" grey: it keeps WCAG AA contrast.
        "muted": text_scale.muted_color(text, window),
        "plate": plate,
        "line": QColor(text.red(), text.green(), text.blue(), 40),
        "accent": QColor("#ffb347") if dark else QColor("#b86e00"),
        "ok": QColor("#4cc38a") if dark else QColor("#18794e"),
        "warn": QColor("#ffb347") if dark else QColor("#b86e00"),
        "bad": QColor("#ff6b6b") if dark else QColor("#c62828"),
    }


def m(text: str) -> str:
    """Escape ``&`` so Qt buttons do not swallow it as a mnemonic marker."""
    return text.replace("&", "&&")


def css(c: QColor) -> str:
    """Return a CSS ``rgba()`` string for a colour."""
    return f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha() / 255:.2f})"


class Card(QFrame):
    """A soft tinted plate (no outline): grouping by tone, not by frame."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("guideCard")
        self.setFrameShape(QFrame.NoFrame)
        self.restyle()

    def restyle(self) -> None:
        """Re-apply the plate colours (theme change)."""
        t = tokens()
        self.setStyleSheet(
            f"QFrame#guideCard{{background:{css(t['plate'])};border:none;"
            "border-radius:12px;}"
        )


class Disclosure(QWidget):
    """A "Details" toggle that reveals secondary content (collapsed by default)."""

    def __init__(self, title: str, content: QWidget) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.button = QToolButton()
        self.button.setText(m(title))
        self.button.setCheckable(True)
        self.button.setArrowType(Qt.RightArrow)
        self.button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.button.setAutoRaise(True)
        self.button.setCursor(Qt.PointingHandCursor)
        text_scale.set_scaled_font(self.button, 1.05)
        self.content = content
        self.content.setVisible(False)
        self.button.toggled.connect(self._toggled)
        lay.addWidget(self.button, 0, Qt.AlignLeft)
        lay.addWidget(self.content)

    def _toggled(self, on: bool) -> None:
        self.button.setArrowType(Qt.DownArrow if on else Qt.RightArrow)
        self.content.setVisible(on)


def control_css() -> str:
    """Indicator styling that stays visible in light and dark themes."""
    t = tokens()
    ring = css(QColor(t["text"].red(), t["text"].green(), t["text"].blue(), 190))
    acc = css(t["accent"])
    check = config.get_data_path("theme/guide/check.svg")
    check_image = (
        f'image:url("{check.replace(chr(92), "/")}");' if isinstance(check, str) else ""
    )
    px = text_scale.scale_px(16)
    dark = t["window"].lightness() < 128
    fill, ink = ("#ffb347", "#1b1c20") if dark else ("#8f5600", "#ffffff")
    hover = "#ffc36b" if dark else "#a46300"
    off = css(t["plate"])
    off_ink = css(t["muted"])
    pad = text_scale.scale_px(10)
    return (
        # The one primary action of a page: filled, high contrast, same shape
        # everywhere; every other button stays quiet.
        f'QPushButton[primary="true"]{{background:{fill};color:{ink};border:none;'
        f"border-radius:7px;padding:{text_scale.scale_px(6)}px {pad * 2}px;}}"
        f'QPushButton[primary="true"]:hover{{background:{hover};}}'
        f'QPushButton[primary="true"]:pressed{{background:{fill};}}'
        f'QPushButton[primary="true"]:focus{{border:2px solid {ink};}}'
        f'QPushButton[primary="true"]:disabled{{background:{off};color:{off_ink};}}'
        f"QRadioButton::indicator{{width:{px}px;height:{px}px;border-radius:{px // 2 + 1}px;"
        f"border:2px solid {ring};background:transparent;}}"
        f"QRadioButton::indicator:checked{{border:2px solid {acc};"
        f"background:qradialgradient(cx:.5,cy:.5,radius:.5,fx:.5,fy:.5,"
        f"stop:0 {acc},stop:.55 {acc},stop:.6 transparent,stop:1 transparent);}}"
        f"QCheckBox::indicator{{width:{px}px;height:{px}px;border-radius:4px;"
        f"border:2px solid {ring};background:transparent;}}"
        f"QCheckBox::indicator:checked{{border:2px solid {acc};background:{acc};"
        f"{check_image}}}"
    )


def label(
    text: str = "",
    *,
    size: float = 1.0,
    bold: bool = False,
    muted: bool = False,
    wrap: bool = True,
) -> QLabel:
    """Return a word-wrapped plain-text label with optional size/weight/tone."""
    lab = text_scale.WrapLabel(text)
    lab.setWordWrap(wrap)
    text_scale.set_scaled_font(lab, size, bold)
    lab.setTextFormat(Qt.PlainText)
    if wrap:
        text_scale.limit_reading_width(lab)
    if muted:
        lab.setStyleSheet(f"color:{css(tokens()['muted'])};")
    return lab


class AdaptiveRow(QWidget):
    """Two blocks side by side; stacked when the window is narrow."""

    def __init__(
        self,
        first: QWidget,
        second: QWidget,
        threshold: int = 700,
        ratio: tuple[int, int] = (3, 2),
    ) -> None:
        super().__init__()
        self._threshold = threshold
        self._box = QHBoxLayout(self)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(16)
        self._box.addWidget(first, ratio[0])
        self._box.addWidget(second, ratio[1])
        self._stacked = False

    def resizeEvent(self, event: object) -> None:  # noqa: N802, D102
        narrow = self.width() < self._threshold
        if narrow != self._stacked:
            self._stacked = narrow
            self._box.setDirection(
                QHBoxLayout.TopToBottom if narrow else QHBoxLayout.LeftToRight
            )
        super().resizeEvent(event)


class WrapRow(QWidget):
    """Two widgets side by side, one above the other when they do not fit.

    At large text sizes the pair is wider than a modest window; instead of
    pushing the whole page wider (and cutting it off) the second one moves
    below the first.
    """

    def __init__(
        self, first: QWidget, second: QWidget, grow_second: bool = False, left: bool = False
    ) -> None:
        super().__init__()
        self._first, self._second = first, second
        self._box = QBoxLayout(QBoxLayout.LeftToRight, self)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(8)
        self._box.addWidget(first, 0, Qt.AlignLeft | Qt.AlignVCenter)
        if grow_second:
            self._box.addWidget(second, 1)
        elif left:
            self._box.addWidget(second, 0, Qt.AlignLeft | Qt.AlignVCenter)
            self._box.addStretch(1)
        else:
            self._box.addStretch(1)
            self._box.addWidget(second, 0, Qt.AlignLeft | Qt.AlignVCenter)
        self._stacked = False

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        widest = max(
            self._first.minimumSizeHint().width(), self._second.minimumSizeHint().width()
        )
        return QSize(widest, super().minimumSizeHint().height())

    def reflow(self) -> None:
        need = self._first.sizeHint().width() + self._second.sizeHint().width() + 8
        narrow = self.width() > 0 and need > self.width()
        if narrow != self._stacked:
            self._stacked = narrow
            self._box.setDirection(
                QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight
            )
            self._box.invalidate()

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        self.reflow()
        super().resizeEvent(event)
