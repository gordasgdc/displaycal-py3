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
from qtpy.QtWidgets import QApplication, QWidget

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
    if mult:
        f = QFont(QApplication.font())
        f.setPointSizeF(f.pointSizeF() * float(mult))
        f.setBold(bool(w.property("_fbold")))
        w.setFont(f)
    minh = w.property("_minh")
    if minh:
        w.setMinimumHeight(scale_px(int(minh)))
    maxc = w.property("_maxchars")
    if maxc:
        w.setMaximumWidth(chars_px(w, int(maxc)))


def set_scaled_font(widget: QWidget, mult: float = 1.0, bold: bool = False) -> None:
    """Give a widget ``mult`` x the application font size (kept in sync)."""
    widget.setProperty("_fmult", mult)
    widget.setProperty("_fbold", bold)
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
