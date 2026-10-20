"""Theme helpers for the Qt UI.

Some legacy wx canvases (the LUT viewer, profile-info plots, CCXX plot, the
interactive display-adjustment window) are hard-coded to a fixed dark scheme
(``BGCOLOUR = "#333333"``, ``FGCOLOUR = "#999999"``, ``GRIDCOLOUR =
"#444444"``) regardless of the OS -- but the ordinary wx ``MainFrame`` window
chrome is *not*: it paints with ``wx.SystemSettings.GetColour(wx
.SYS_COLOUR_WINDOW)``, the real OS window-background colour, which on a
Mac in Dark Mode is much darker than ``#333333`` (the raw ``NSColor
.windowBackgroundColor`` query reports ``#171717``, but macOS composites a
vibrancy/tint pass on top of it, so a real on-screen wx window actually
samples as ``#232323`` -- the query alone understates it). The Qt UI keeps
the DisplayCAL look but **selects it from the OS light/dark preference**:
:func:`apply_theme` detects the scheme (:func:`is_dark`) and installs a
matching :class:`QPalette`, tuned to match that real *on-screen* native
window background rather than the plot canvases' brighter fixed grey or the
raw (uncomposited) system colour query. On Windows this also means
switching to the Fusion style, since the native ``windowsvista`` style
ignores custom palette colours for several controls (combo-box popups in
particular); macOS and Linux native styles honour the palette as-is. Plot
colours (:func:`plot_colors`) are then derived from that palette, so the
plots match the surrounding chrome exactly.

The per-datum plot colours (RGB curve pens, gamut-hull vertex colours) are
inherent to the data, not the theme, and stay constant in both schemes.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, NamedTuple

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QApplication, QStyleFactory

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

#: RGB tone-curve pen colours (from ``wx_lut_viewer.LUTCanvas.colors``). These
#: are data colours, identical in light and dark themes.
CHANNEL_COLORS = {
    "R": QColor("#FF0000"),
    "G": QColor("#00FF00"),
    "B": QColor("#0080FF"),
    "Gray": QColor("#CCCCCC"),
}

#: Point size for UI text, matching wx's ``SetMaxFontSize(11)``.
FONT_POINT_SIZE = 11

def _palette_roles(dark: bool) -> dict:
    """Palette roles of direction A («proof sheet»): ink on paper, a black patch
    as the selection, the booth blue as the link/focus colour."""
    from DisplayCAL.ui import design_a

    t = design_a.tokens(dark)
    return {
        QPalette.Window: t.sheet,
        QPalette.WindowText: t.ink,
        QPalette.Base: t.inset,
        QPalette.AlternateBase: t.sheet,
        QPalette.Text: t.ink,
        QPalette.Button: t.inset,
        QPalette.ButtonText: t.ink,
        QPalette.ToolTipBase: t.inset,
        QPalette.ToolTipText: t.ink,
        QPalette.Highlight: t.patch_bg,
        QPalette.HighlightedText: t.patch_ink,
        QPalette.PlaceholderText: t.ink2,
        QPalette.Link: t.focus,
    }


def is_dark(source: QWidget | None = None) -> bool:
    """Return whether the current OS colour scheme is dark.

    Prefers the explicit OS colour-scheme hint (Qt 6.5+); otherwise infers it
    from the window background's lightness.

    Args:
        source (QWidget | None): Widget whose palette to inspect for the
            fallback; defaults to the application palette.

    Returns:
        bool: True if the effective scheme is dark.
    """
    app = QApplication.instance()
    if app is not None:
        color_scheme = getattr(app.styleHints(), "colorScheme", None)
        if callable(color_scheme):
            try:
                scheme = color_scheme()
                if scheme == Qt.ColorScheme.Dark:
                    return True
                if scheme == Qt.ColorScheme.Light:
                    return False
            except (AttributeError, TypeError):
                pass  # older Qt without ColorScheme; fall through
    palette = source.palette() if source is not None else QApplication.palette()
    return palette.color(QPalette.Window).lightness() < 128


def build_palette(dark: bool) -> QPalette:
    """Return the DisplayCAL :class:`QPalette` for the given scheme.

    Args:
        dark (bool): Whether to build the dark (wx-style) palette.

    Returns:
        QPalette: The configured palette.
    """
    from DisplayCAL.ui import design_a

    palette = QPalette()
    for role, hexcolor in _palette_roles(dark).items():
        palette.setColor(role, QColor(hexcolor))
    disabled = QColor(design_a.tokens(dark).off_ink)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, disabled)
    return palette


def apply_theme(app: QApplication) -> None:
    """Apply the DisplayCAL theme (palette + font) to ``app``.

    Selects the dark or light palette from the OS colour scheme and sets the
    base font to wx's 11-point size. On Windows, also switches the style to
    **Fusion**: the native ``windowsvista`` style renders combo-box popups and
    several other controls via the OS's own (always-light, unless the OS is
    told otherwise through undocumented dark-mode APIs) theme engine and
    ignores the application :class:`QPalette` entirely, which left combo boxes
    white in dark mode regardless of the palette set here. Fusion is the only
    built-in style that honours a custom palette consistently, so it is used
    to keep Windows dark mode faithful even though it costs the native
    chevron/corner rendering. macOS and Linux native styles already honour the
    palette and keep their native look. Container backgrounds are painted with
    the palette ``Window`` colour by the windows themselves (via
    ``setAutoFillBackground``), so the themed grey shows through while the
    controls draw over it.

    Args:
        app (QApplication): The application to theme.
    """
    if sys.platform == "win32":
        app.setStyle(QStyleFactory.create("Fusion"))
    from DisplayCAL.ui import design_a

    design_a.load_fonts()
    dark = is_dark()
    app.setPalette(build_palette(dark))
    sans = design_a.family("sans")
    if sans:
        font = app.font()
        font.setFamily(sans)
        app.setFont(font)
    app.setStyleSheet(design_a.global_qss(design_a.tokens(dark)))
    # The base size is the system font (not a fixed 11 points) times the saved
    # "Text size" level; see :mod:`DisplayCAL.ui.text_scale`.
    from DisplayCAL.ui import text_scale

    text_scale.apply()


def label_color(source: QWidget | None = None) -> QColor:
    """Return the grayish colour for secondary text (e.g. table label column).

    Args:
        source (QWidget | None): Widget whose palette to read; defaults to the
            application palette.

    Returns:
        QColor: The ``WindowText`` (grayish) colour.
    """
    palette = source.palette() if source is not None else QApplication.palette()
    return palette.color(QPalette.WindowText)


class PlotColors(NamedTuple):
    """Theme-derived colours for a pyqtgraph plot.

    Attributes:
        background (QColor): Plot canvas background.
        foreground (QColor): Axis lines, ticks and labels.
        grid (QColor): Grid-line colour (same hue as foreground; pyqtgraph
            applies its own alpha).
        linear (QColor): The faint ``y = x`` reference diagonal.
        locus (QColor): High-contrast overlay lines (e.g. colour-temperature
            locus) that need to stand out against the background.
    """

    background: QColor
    foreground: QColor
    grid: QColor
    linear: QColor
    locus: QColor


def _blend(a: QColor, b: QColor, t: float) -> QColor:
    """Return the linear blend ``a*(1-t) + b*t`` of two colours.

    Args:
        a (QColor): The colour at ``t = 0``.
        b (QColor): The colour at ``t = 1``.
        t (float): The blend factor in 0..1.

    Returns:
        QColor: The blended (opaque) colour.
    """
    return QColor(
        round(a.red() * (1 - t) + b.red() * t),
        round(a.green() * (1 - t) + b.green() * t),
        round(a.blue() * (1 - t) + b.blue() * t),
    )


def plot_colors(source: QWidget | None = None) -> PlotColors:
    """Return plot colours derived from the current palette.

    The plot background/foreground are taken from the widget's palette
    (``Window``/``WindowText``) so the plot matches the surrounding themed
    chrome exactly, with the grid and reference lines blended between the two.

    Args:
        source (QWidget | None): Widget whose palette to read; defaults to the
            application palette.

    Returns:
        PlotColors: The background/foreground/grid/linear/locus colours.
    """
    palette = source.palette() if source is not None else QApplication.palette()
    background = palette.color(QPalette.Window)
    foreground = palette.color(QPalette.WindowText)
    grid = _blend(background, foreground, 0.35)
    linear = QColor(foreground)
    linear.setAlpha(150)
    locus = _blend(background, foreground, 0.85)
    locus.setAlpha(220)
    return PlotColors(
        background=background,
        foreground=foreground,
        grid=grid,
        linear=linear,
        locus=locus,
    )
