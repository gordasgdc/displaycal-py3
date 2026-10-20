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
    """Colour tokens of the proof-sheet system (follow light/dark)."""
    from DisplayCAL.ui import design_a

    pal = QApplication.palette()
    dark = pal.window().color().lightness() < 128
    d = design_a.tokens(dark)
    ink = QColor(d.ink)
    return {
        "window": QColor(d.sheet),
        "text": ink,
        "muted": QColor(d.ink2),
        "plate": QColor(d.inset),
        "line": QColor(ink.red(), ink.green(), ink.blue(), 56),
        # Actions and the current step are ink; colour is kept for data and state.
        "accent": ink,
        "ink": ink,
        "focus": QColor(d.focus),
        "patch_bg": QColor(d.patch_bg),
        "patch_ink": QColor(d.patch_ink),
        "ok": QColor(d.ok),
        "warn": QColor(d.warn),
        "bad": QColor(d.bad),
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
            f"QFrame#guideCard{{background:{css(t['plate'])};"
            f"border:1px solid {css(t['line'])};border-radius:0;}}"
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
    """Page-level style sheet of the guided flow.

    Buttons, fields, menus, radio buttons and ticks all come from the
    application style sheet (:func:`DisplayCAL.ui.design_a.global_qss`).
    """
    return ""


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


def section_head(text: str) -> QWidget:
    """A section of a page: its name as a slug over a hairline."""
    from DisplayCAL.ui import design_a

    box = QWidget()
    col = QVBoxLayout(box)
    col.setContentsMargins(0, 6, 0, 0)
    col.setSpacing(4)
    col.addWidget(slug(text, strong=True, size=0.9))
    col.addWidget(design_a.Rule(1, hair=True))
    return box


def slug(text: str = "", strong: bool = False, size: float = 0.82) -> QLabel:
    """A small upper-case label in the proof's mono face (a field's name)."""
    from DisplayCAL.ui import design_a

    lab = text_scale.WrapLabel(text.upper())
    lab.setWordWrap(True)
    lab.setTextFormat(Qt.PlainText)
    lab.setAccessibleName(text)
    text_scale.set_scaled_font(lab, size, bold=True)
    mono = design_a.family("mono")
    if mono:
        lab.setProperty("_ffamily", mono)
    f = lab.font()
    f.setFamily(mono or f.family())
    f.setLetterSpacing(f.SpacingType.PercentageSpacing, 105)
    lab.setFont(f)
    lab.setStyleSheet(f"color:{css(tokens()['text' if strong else 'muted'])};")
    return lab


def page_head(number: int, title: str) -> QWidget:
    """The head of a step's page: a large numeral, the title, then an ink rule."""
    from DisplayCAL.ui import design_a

    box = QWidget()
    col = QVBoxLayout(box)
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(8)
    row = QHBoxLayout()
    row.setSpacing(14)
    num = text_scale.WrapLabel(f"{number:02d}")
    num.setWordWrap(False)
    text_scale.set_scaled_font(num, 2.9, weight=800)
    name = label(title, size=1.7, wrap=True)
    text_scale.set_scaled_font(name, 1.7, weight=800)
    row.addWidget(num, 0, Qt.AlignBottom)
    row.addWidget(name, 1, Qt.AlignBottom | Qt.AlignLeft)
    col.addLayout(row)
    col.addWidget(design_a.Rule(2))
    return box


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
