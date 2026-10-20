"""Text size: one mechanism for the whole Qt interface (system size x user level).

* The base size is the **system** font size (never below ``MIN_BASE_POINTS``);
  the user adds a level -- Normal, Large, Very large -- that is remembered
  (``ui.text_size``) and applied **live**, so the effect is visible at once.
* The application font is the single source of truth. Widgets that want a
  different size (a heading, a muted note) do not hard-code points: they declare a
  *multiplier* with :func:`set_scaled_font`, and every such widget is
  recomputed when the level changes. Fixed pixel sizes (minimum heights, check
  boxes) are declared with :func:`scale_px` and follow the same level.
* Contrast: :func:`muted_color` returns a secondary-text colour that always
  reaches the WCAG AA ratio (4.5:1) against the window background, in both
  themes, so explanations are never rendered as "disabled" text.
* Nothing here touches the measurement: the patch window is drawn by the
  measurement engine from ``dimensions.measureframe`` (a physical size/position),
  which this module never reads or writes.
"""

from __future__ import annotations

from qtpy.QtCore import QObject, Signal
from qtpy.QtGui import QColor, QFont, QFontDatabase
from qtpy.QtCore import QSize
from qtpy.QtWidgets import QApplication, QAbstractButton, QCheckBox, QComboBox, QLabel, QPushButton, QSizePolicy, QWidget

from DisplayCAL import config

CFG_KEY = "ui.text_size"
#: (key, factor). Keys are stored; labels come from the language files.
LEVELS: tuple[tuple[str, float], ...] = (("normal", 1.0), ("large", 1.25), ("xlarge", 1.5))
DEFAULT_LEVEL = "normal"
#: The system size is the base, but never smaller than this (points).
MIN_BASE_POINTS = 11.0
#: Reading width of a paragraph, in average characters.
READING_CHARS = 78


class _Bus(QObject):
    changed = Signal(float)  # new overall factor


bus = _Bus()
_state = {"level": DEFAULT_LEVEL}


def factor(level: str | None = None) -> float:
    """Scale factor of a level (``1.0`` for unknown keys)."""
    level = level or _state["level"]
    return dict(LEVELS).get(level, 1.0)


def current_level() -> str:
    """The level in force (from the configuration the first time)."""
    return _state["level"]


def stored_level() -> str:
    """The level saved in the configuration (default when missing/invalid)."""
    value = config.getcfg(CFG_KEY)
    return value if value in dict(LEVELS) else DEFAULT_LEVEL


def base_points() -> float:
    """System font size in points, with the comfort floor applied."""
    try:
        size = QFontDatabase.systemFont(QFontDatabase.GeneralFont).pointSizeF()
    except Exception:  # noqa: BLE001 - fall back, never break start-up
        size = 0.0
    return max(float(size) if size > 0 else MIN_BASE_POINTS, MIN_BASE_POINTS)


class _ComboStyleFilter(QObject):
    """macOS: a native pop-up button has a fixed height (about 22 pt), so at a
    larger text size its label is cut off. Above Normal, pop-up buttons use the
    standard Fusion style (it grows with the text, as on Windows); at Normal
    they keep the native look. Scroll bars, buttons and the rest stay native."""

    def eventFilter(self, obj, event):  # noqa: N802, D102
        from qtpy.QtCore import QEvent

        if event.type() == QEvent.Polish and isinstance(obj, QComboBox):
            _style_combo(obj)
        return False


def _style_combo(combo: QComboBox) -> None:
    import sys

    if sys.platform != "darwin":
        return
    want = factor() > 1.0
    if bool(combo.property("_fusion")) == want:
        return
    combo.setProperty("_fusion", want)
    if want:
        from qtpy.QtWidgets import QStyleFactory

        # One style per pop-up button, owned by it: a shared style would be
        # deleted together with the first button that is closed.
        style = QStyleFactory.create("Fusion")
        style.setParent(combo)
        combo.setStyle(style)
    else:
        combo.setStyle(None)


def _match_style_to_size(app: QApplication, f: float) -> None:
    import sys

    if sys.platform != "darwin":
        return
    if "combo_filter" not in _state:
        _state["combo_filter"] = _ComboStyleFilter(app)
        app.installEventFilter(_state["combo_filter"])
    for combo in app.allWidgets():
        if isinstance(combo, QComboBox):
            _style_combo(combo)


def apply(level: str | None = None, persist: bool = False) -> float:
    """Apply a level to the application font and every scaled widget.

    Args:
        level: ``normal`` / ``large`` / ``xlarge``; ``None`` = the stored one.
        persist: Save the level in the configuration.

    Returns:
        The factor applied.
    """
    level = level if level in dict(LEVELS) else stored_level()
    _state["level"] = level
    if persist:
        config.setcfg(CFG_KEY, level)
        try:
            config.writecfg()
        except Exception:  # noqa: BLE001 - a failed save must not undo the preview
            pass
    app = QApplication.instance()
    f = factor(level)
    if app is not None:
        _match_style_to_size(app, f)
        _state["prev_size"] = app.font().pointSizeF()
        font = QFont(app.font())
        font.setPointSizeF(base_points() * f)
        app.setFont(font)
        refresh()
    bus.changed.emit(f)
    return f


def refresh() -> None:
    """Recompute every widget that declared a multiplier or a pixel size."""
    app = QApplication.instance()
    if app is None:
        return
    for w in app.allWidgets():
        _refresh_widget(w)


def _refresh_widget(w: QWidget) -> None:
    mult = w.property("_fmult")
    if not mult and w.styleSheet():
        # A widget with its own style sheet keeps the font it first inherited
        # instead of following the application font: bring it along, but only
        # if it still has the old application size (a deliberate size is kept).
        prev = _state.get("prev_size")
        cur = QApplication.font().pointSizeF()
        if prev and abs(w.font().pointSizeF() - prev) < 0.05 and abs(prev - cur) > 0.05:
            f = QFont(w.font())
            f.setPointSizeF(cur)
            w.setFont(f)
    if mult:
        f = QFont(QApplication.font())
        f.setPointSizeF(f.pointSizeF() * float(mult))
        f.setBold(bool(w.property("_fbold")))
        weight = w.property("_fweight")
        if weight:
            f.setWeight(QFont.Weight(int(weight)))
        w.setFont(f)
    minh = w.property("_minh")
    if minh:
        w.setMinimumHeight(scale_px(int(minh)))
    maxc = w.property("_maxchars")
    if maxc:
        w.setMaximumWidth(chars_px(w, int(maxc)))


def set_scaled_font(
    widget: QWidget, mult: float = 1.0, bold: bool = False, weight: int | None = None
) -> None:
    """Give a widget ``mult`` x the application font size (kept in sync).

    ``weight`` (CSS-style 100..900) overrides ``bold`` for variable fonts.
    """
    widget.setProperty("_fmult", mult)
    widget.setProperty("_fbold", bold)
    widget.setProperty("_fweight", weight)
    _refresh_widget(widget)


def scale_px(px: int) -> int:
    """A pixel size designed for the Normal level, scaled with the text."""
    return max(1, round(px * factor() * (base_points() / MIN_BASE_POINTS)))


def set_min_height(widget: QWidget, px: int) -> None:
    """Minimum height that grows with the text size."""
    widget.setProperty("_minh", px)
    widget.setMinimumHeight(scale_px(px))


def chars_px(widget: QWidget, chars: int) -> int:
    """Width of ``chars`` average characters in the font the widget should have.

    Computed from the application font (times the widget's own multiplier), not
    from ``widget.font()``, which Qt updates only after the change event.
    """
    from qtpy.QtGui import QFontMetrics

    font = QFont(QApplication.font())
    mult = widget.property("_fmult")
    if mult:
        font.setPointSizeF(font.pointSizeF() * float(mult))
    return QFontMetrics(font).averageCharWidth() * chars


def breakable(text: str, minimum: int = 24) -> str:
    """Let a long unbroken token (a file path) wrap: add break points after separators.

    A label wraps only at spaces, so one long path would make a whole dialog
    wider than its window (seen at large text). A zero-width space after each
    separator changes nothing visible but gives the label somewhere to break.
    Tokens containing markup are left alone.
    """
    import re

    def one(m: "re.Match[str]") -> str:
        token = m.group(0)
        if len(token) < minimum or "<" in token or ">" in token:
            return token
        return re.sub(r"([/\\_.:-])", "\\1\u200b", token)

    return re.sub(r"\S+", one, text)


class WrapLabel(QLabel):
    """A wrapping label whose height follows its REAL (width-limited) width.

    A layout asks ``heightForWidth`` with the whole column width, but a label
    limited to a comfortable reading width is then given less: with the plain
    ``QLabel`` the extra lines are counted nowhere and the next control covers
    them (seen on Windows). Clamping to the maximum width keeps both in step.
    """

    def heightForWidth(self, w: int) -> int:  # noqa: N802
        return super().heightForWidth(min(w, self.maximumWidth()))


class _WrapText:
    """Shared by buttons whose text wraps onto several lines (set before ``__init__``)."""

    _PAD_X, _PAD_Y = 24, 14

    def _wrap_init(self, text: str) -> None:
        self._full = text
        QAbstractButton.setText(self, text)
        policy = self.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Preferred)  # not "its text must fit"
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def text(self) -> str:
        return self._full

    def setText(self, text: str) -> None:  # noqa: N802
        self._full = text
        self._rewrap(self.width())

    def _lines(self, width: int) -> list[str]:
        fm = self.fontMetrics()
        room = max(width - self._PAD_X, 40)
        lines: list[str] = []
        cur = ""
        for word in self._full.split():
            trial = f"{cur} {word}".strip()
            if cur and fm.horizontalAdvance(trial) > room:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        lines.append(cur)
        return lines

    def _rewrap(self, width: int) -> None:
        shown = "\n".join(self._lines(width)) if width > 0 else self._full
        if shown != QAbstractButton.text(self):
            QAbstractButton.setText(self, shown)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return len(self._lines(width)) * self.fontMetrics().lineSpacing() + self._PAD_Y

    def sizeHint(self) -> QSize:  # noqa: N802
        fm = self.fontMetrics()
        return QSize(fm.horizontalAdvance(self._full) + self._PAD_X, fm.lineSpacing() + self._PAD_Y)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        fm = self.fontMetrics()
        longest = max((fm.horizontalAdvance(w) for w in self._full.split()), default=0)
        return QSize(longest + self._PAD_X, fm.lineSpacing() + self._PAD_Y)

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        self._rewrap(self.width())
        super().resizeEvent(event)


class WrapPushButton(_WrapText, QPushButton):
    """A flat text button that wraps onto several lines instead of widening the page."""

    def __init__(self, text: str = "") -> None:
        QPushButton.__init__(self)
        self._wrap_init(text)


class WrapCheckBox(_WrapText, QCheckBox):
    """A check box whose (long) text wraps next to the box instead of widening the window."""

    _PAD_X, _PAD_Y = 34, 8

    def __init__(self, text: str = "") -> None:
        QCheckBox.__init__(self)
        self._wrap_init(text)


def limit_reading_width(label: QWidget, chars: int = READING_CHARS) -> None:
    """Keep a paragraph at a comfortable reading width (follows the text size)."""
    label.setProperty("_maxchars", chars)
    label.setMaximumWidth(chars_px(label, chars))


# --- contrast -----------------------------------------------------------------


def _lin(c: int) -> float:
    v = c / 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def luminance(c: QColor) -> float:
    """WCAG relative luminance."""
    return 0.2126 * _lin(c.red()) + 0.7152 * _lin(c.green()) + 0.0722 * _lin(c.blue())


def contrast_ratio(a: QColor, b: QColor) -> float:
    """WCAG contrast ratio of two colours (1..21)."""
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def muted_color(fg: QColor | None = None, bg: QColor | None = None, minimum: float = 4.5) -> QColor:
    """A softer text colour that still meets ``minimum`` contrast on ``bg``.

    Starts from a gentle mix of text and background and moves towards the text
    colour until the ratio is reached (at worst the text colour itself).
    """
    pal = QApplication.palette()
    fg = fg or pal.windowText().color()
    bg = bg or pal.window().color()
    for step in range(0, 21):
        t = 0.62 + step * 0.019
        t = min(t, 1.0)
        c = QColor(
            round(fg.red() * t + bg.red() * (1 - t)),
            round(fg.green() * t + bg.green() * (1 - t)),
            round(fg.blue() * t + bg.blue() * (1 - t)),
        )
        if contrast_ratio(c, bg) >= minimum:
            return c
    return QColor(fg)


def muted_css() -> str:
    """CSS colour of secondary text (WCAG AA against the window colour)."""
    return muted_color().name()


def scrollable_dialog(dialog: QWidget):
    """Lay out a dialog as a scrolling body plus a footer that stays visible.

    At a large text size a dialog can be taller than the screen; the body then
    scrolls while the action buttons stay reachable. Returns
    ``(body_layout, footer_layout)``.
    """
    from qtpy.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout

    outer = QVBoxLayout(dialog)
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    body = QWidget()
    body_lay = QVBoxLayout(body)
    area.setWidget(body)
    outer.addWidget(area, 1)
    footer = QHBoxLayout()
    outer.addLayout(footer)
    return body_lay, footer
