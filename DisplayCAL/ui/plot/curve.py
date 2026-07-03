"""Tone-curve plot widget (pyqtgraph port of ``wx_lut_viewer.LUTCanvas``).

Draws per-channel input→output curves (calibration vcgt or tone-response) in the
unit square, over a faint grid box and an optional linear reference diagonal.
The point extraction lives in :mod:`DisplayCAL.ui.plot.curve_data`; this widget
only renders.

Background / grid / axis colours follow the OS light/dark theme (see
:mod:`DisplayCAL.ui.theme`); the per-channel pen colours are data colours and
stay constant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyqtgraph as pg
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

from DisplayCAL.ui.theme import CHANNEL_COLORS, plot_colors

if TYPE_CHECKING:
    from qtpy.QtCore import QEvent
    from qtpy.QtWidgets import QWidget


class CurvePlot(pg.PlotWidget):
    """Plot widget for per-channel tone curves over the unit square.

    Args:
        parent (QWidget | None): Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        # Guards changeEvent, which pyqtgraph's base __init__ can trigger
        # (via setBackgroundRole) before the plot item exists.
        self._ready = False
        super().__init__(parent)
        plot_item = self.getPlotItem()
        plot_item.showGrid(x=True, y=True, alpha=0.25)
        plot_item.hideButtons()
        plot_item.setMenuEnabled(False)
        plot_item.setLabels(bottom="Input", left="Output")
        self.setXRange(0, 1, padding=0)
        self.setYRange(0, 1, padding=0)
        self._channels: dict[str, list[tuple[float, float]]] = {}
        self._show_linear = True
        self._ready = True
        self._apply_theme()

    # -- theming -----------------------------------------------------------

    def _apply_theme(self) -> None:
        """Recolour the canvas, axes and grid from the current OS theme."""
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
            self.draw_curves(self._channels, self._show_linear)

    # -- drawing -----------------------------------------------------------

    def draw_curves(
        self,
        channels: dict[str, list[tuple[float, float]]],
        show_linear: bool = True,
    ) -> None:
        """Draw the given per-channel curves.

        Args:
            channels (dict[str, list[tuple[float, float]]]):
                ``{channel_name: [(x, y), ...]}`` with values in 0..1.
            show_linear (bool): Whether to draw the linear (y=x) reference
                diagonal.
        """
        self._channels = channels
        self._show_linear = show_linear
        colors = plot_colors(self)
        self.clear()
        if show_linear:
            self.addItem(
                pg.PlotCurveItem(
                    [0.0, 1.0],
                    [0.0, 1.0],
                    pen=pg.mkPen(colors.linear, width=1, style=Qt.DashLine),
                )
            )
        for name, points in channels.items():
            if not points:
                continue
            color = CHANNEL_COLORS.get(name, CHANNEL_COLORS["Gray"])
            self.addItem(
                pg.PlotCurveItem(
                    [p[0] for p in points],
                    [p[1] for p in points],
                    pen=pg.mkPen(QColor(color), width=2),
                    name=name,
                )
            )
        self.setXRange(0, 1, padding=0)
        self.setYRange(0, 1, padding=0)
