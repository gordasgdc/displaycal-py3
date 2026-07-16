"""CCMX/CCSS plot widget (pyqtgraph port of ``wx_ccxx_plot.CCXXPlot``).

Renders the two views the wx original toggles between: the "ccxx" view
(spectral power-distribution curves for a CCSS, or a matrix "flower" plot of
colorimeter-simulated vs. reference colour patches for a CCMX), and a CIE
1931 2-degree xy chromaticity plot with comparison RGB gamut triangles. All
colorimetry/data prep lives in :mod:`DisplayCAL.ui.plot.ccxx_data`; this
widget only translates already-resolved points into pyqtgraph items.

Interactive zoom/pan is pyqtgraph's own (wheel to zoom, drag to pan) rather
than the wx original's hand-rolled wheel/key handlers, and is disabled for
the (static) CCMX flower plot exactly like the wx original disabled drag for
it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyqtgraph as pg
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

from DisplayCAL import colormath
from DisplayCAL.ui.plot.ccxx_data import COMPARISON_GAMUTS, comparison_gamut_triangle
from DisplayCAL.ui.theme import plot_colors

if TYPE_CHECKING:
    from qtpy.QtCore import QEvent
    from qtpy.QtWidgets import QWidget

    from DisplayCAL.ui.plot.ccxx_data import CCXXPlotData

#: Neutral greys reused from the wx canvas for the CIE outline/comparison
#: gamuts; legible in both light and dark themes.
_OUTLINE = QColor(102, 102, 102, 153)
_COMPARISON = QColor(102, 102, 102, 255)

_DASH_STYLES = {
    "solid": Qt.SolidLine,
    "dash": Qt.DashLine,
    "dashdot": Qt.DashDotLine,
    "dot": Qt.DotLine,
}


class CCXXPlotWidget(pg.PlotWidget):
    """Plot widget for a CCMX/CCSS correction's "ccxx" and CIE xy views.

    Args:
        parent (QWidget | None): Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        # Guards changeEvent, which pyqtgraph's base __init__ can trigger
        # (via setBackgroundRole) before the plot item exists.
        self._ready = False
        super().__init__(parent)
        plot_item = self.getPlotItem()
        plot_item.hideButtons()
        plot_item.setMenuEnabled(False)
        self._data: CCXXPlotData | None = None
        self._mode = "ccxx"
        self._ready = True
        self._apply_theme()

    # -- theming -----------------------------------------------------------

    def _apply_theme(self) -> None:
        """Recolour the canvas and axes from the current OS theme."""
        colors = plot_colors(self)
        self.setBackground(colors.background)
        plot_item = self.getPlotItem()
        for name in ("left", "bottom", "right", "top"):
            axis = plot_item.getAxis(name)
            axis.setPen(colors.foreground)
            axis.setTextPen(colors.foreground)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt override)
        """Re-theme and redraw when the application palette changes.

        Args:
            event (QEvent): The Qt change event.
        """
        from qtpy.QtCore import QEvent

        super().changeEvent(event)
        if not self._ready:
            return
        if event.type() in (
            QEvent.PaletteChange,
            QEvent.ApplicationPaletteChange,
            QEvent.ThemeChange,
        ):
            self._apply_theme()
            if self._data is not None:
                self._redraw()

    # -- drawing -------------------------------------------------------

    def set_data(self, data: CCXXPlotData) -> None:
        """Set the plot data to draw (call :meth:`draw_ccxx` or :meth:`draw_cie` next).

        Args:
            data (CCXXPlotData): The precomputed plot data.
        """
        self._data = data

    def draw_ccxx(self) -> None:
        """Draw the spectral (CCSS) or matrix "flower" (CCMX) plot."""
        self._mode = "ccxx"
        self._redraw()

    def draw_cie(self) -> None:
        """Draw the CIE 1931 2-degree xy chromaticity plot."""
        self._mode = "cie"
        self._redraw()

    def _redraw(self) -> None:
        """Clear the canvas and redraw the current mode."""
        self.clear()
        plot_item = self.getPlotItem()
        if plot_item.legend is not None:
            plot_item.legend.scene().removeItem(plot_item.legend)
            plot_item.legend = None
        if self._mode == "cie":
            self._draw_cie()
        else:
            self._draw_ccxx()

    def _draw_ccxx(self) -> None:
        """Draw the "ccxx" view (spectral curves or matrix flower plot)."""
        data = self._data
        plot_item = self.getPlotItem()
        plot_item.setAspectLocked(not data.is_ccss)
        self.setMouseEnabled(x=data.is_ccss, y=data.is_ccss)
        for curve in data.curves:
            color = QColor(*curve.color)
            xs = [p[0] for p in curve.points]
            ys = [p[1] for p in curve.points]
            if curve.marker:
                self.addItem(
                    pg.ScatterPlotItem(
                        xs,
                        ys,
                        symbol=curve.marker,
                        size=max(4.0, curve.size),
                        pen=pg.mkPen(color),
                        brush=pg.mkBrush(color),
                    )
                )
            else:
                self.addItem(pg.PlotCurveItem(xs, ys, pen=pg.mkPen(color, width=1)))
        self.setXRange(*data.axis_x, padding=0)
        self.setYRange(*data.axis_y, padding=0)

    def _draw_cie(self) -> None:
        """Draw the CIE 1931 xy view with comparison gamuts and legend."""
        data = self._data
        plot_item = self.getPlotItem()
        plot_item.setAspectLocked(True)
        self.setMouseEnabled(x=True, y=True)
        legend = plot_item.addLegend(offset=(-10, 10))

        locus = [*colormath.cie1931_2_xy, colormath.cie1931_2_xy[0]]
        self.addItem(
            pg.PlotCurveItem(
                [p[0] for p in locus],
                [p[1] for p in locus],
                pen=pg.mkPen(_OUTLINE, width=1.75),
            )
        )

        for rgb_space, dash in COMPARISON_GAMUTS:
            triangle = comparison_gamut_triangle(rgb_space)
            item = pg.PlotCurveItem(
                [p[0] for p in triangle],
                [p[1] for p in triangle],
                pen=pg.mkPen(_COMPARISON, width=2, style=_DASH_STYLES[dash]),
            )
            self.addItem(item)
            legend.addItem(item, rgb_space.replace(" (1998)", ""))

        for point in data.points:
            x, y = colormath.XYZ2xyY(*point.xyz)[:2]
            color = QColor(*point.color)
            item = pg.ScatterPlotItem(
                [x], [y], symbol="+", size=8, pen=pg.mkPen(color, width=1.75)
            )
            self.addItem(item)
            legend.addItem(item, "{:.4f} x {:.4f} y".format(x, y))

        self.setXRange(0, 1, padding=0)
        self.setYRange(0, 1, padding=0)
