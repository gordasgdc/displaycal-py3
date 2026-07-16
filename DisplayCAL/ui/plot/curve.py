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
        self._hidden: set[str] = set()
        self._show_linear = True
        self._x_range = (0.0, 1.0)
        self._y_range = (0.0, 1.0)
        self._x_label = "Input"
        self._y_label = "Output"
        self._ready = True
        self._apply_theme()

    def set_channel_hidden(self, name: str, hidden: bool) -> None:
        """Show or hide a single channel curve without recomputing its data.

        Lets a channel-toggle checkbox filter the already-drawn curves (e.g. the
        measured tone response, which is expensive to recompute).

        Args:
            name (str): Channel name (``"R"``/``"G"``/``"B"`` …).
            hidden (bool): Whether to hide the channel.
        """
        if hidden:
            self._hidden.add(name)
        else:
            self._hidden.discard(name)
        self.draw_curves(
            self._channels,
            self._show_linear,
            self._x_range,
            self._y_range,
            self._x_label,
            self._y_label,
        )

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
            self.draw_curves(
                self._channels,
                self._show_linear,
                self._x_range,
                self._y_range,
                self._x_label,
                self._y_label,
            )

    # -- drawing -----------------------------------------------------------

    def draw_curves(
        self,
        channels: dict[str, list[tuple[float, float]]],
        show_linear: bool = True,
        x_range: tuple[float, float] = (0.0, 1.0),
        y_range: tuple[float, float] = (0.0, 1.0),
        x_label: str = "Input",
        y_label: str = "Output",
    ) -> None:
        """Draw the given per-channel curves.

        Args:
            channels (dict[str, list[tuple[float, float]]]):
                ``{channel_name: [(x, y), ...]}`` in the axis units below.
            show_linear (bool): Whether to draw the linear reference diagonal.
            x_range (tuple[float, float]): X-axis ``(min, max)``.
            y_range (tuple[float, float]): Y-axis ``(min, max)``.
            x_label (str): X-axis label.
            y_label (str): Y-axis label.
        """
        self._channels = channels
        self._show_linear = show_linear
        self._x_range = x_range
        self._y_range = y_range
        self._x_label = x_label
        self._y_label = y_label
        colors = plot_colors(self)
        self.clear()
        self.getPlotItem().setLabels(bottom=x_label, left=y_label)
        if show_linear:
            self.addItem(
                pg.PlotCurveItem(
                    [x_range[0], x_range[1]],
                    [y_range[0], y_range[1]],
                    pen=pg.mkPen(colors.linear, width=1, style=Qt.DashLine),
                )
            )
        for name, points in channels.items():
            if not points or name in self._hidden:
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
        self.setXRange(*x_range, padding=0)
        self.setYRange(*y_range, padding=0)
