"""Tone-curve plot widget (pyqtgraph port of ``wx_lut_viewer.LUTCanvas``).

Draws per-channel input→output curves (calibration vcgt or tone-response) in the
unit square, over a faint grid box and an optional linear reference diagonal.
The point extraction lives in :mod:`DisplayCAL.ui.plot.curve_data`; this widget
only renders.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyqtgraph as pg
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

#: Pen colour per channel name.
CHANNEL_COLORS = {
    "R": QColor(229, 73, 73),
    "G": QColor(73, 200, 73),
    "B": QColor(96, 96, 255),
    "Gray": QColor(204, 204, 204),
}
_LINEAR = QColor(128, 128, 128, 160)
_BACKGROUND = QColor(40, 40, 40)


class CurvePlot(pg.PlotWidget):
    """Plot widget for per-channel tone curves over the unit square.

    Args:
        parent (QWidget | None): Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, background=_BACKGROUND)
        plot_item = self.getPlotItem()
        plot_item.showGrid(x=True, y=True, alpha=0.25)
        plot_item.hideButtons()
        plot_item.setMenuEnabled(False)
        plot_item.setLabels(bottom="Input", left="Output")
        self.setXRange(0, 1, padding=0)
        self.setYRange(0, 1, padding=0)

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
        self.clear()
        if show_linear:
            self.addItem(
                pg.PlotCurveItem(
                    [0.0, 1.0],
                    [0.0, 1.0],
                    pen=pg.mkPen(_LINEAR, width=1, style=Qt.DashLine),
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
                    pen=pg.mkPen(color, width=2),
                    name=name,
                )
            )
        self.setXRange(0, 1, padding=0)
        self.setYRange(0, 1, padding=0)
