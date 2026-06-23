"""Gamut plot widget (pyqtgraph port of ``wx_profile_info.GamutCanvas``).

Renders one or more profile gamuts projected into a chosen colorspace, over the
spectral-locus / optimal-colour outline and an optional colour-temperature
locus. The heavy ``DrawCanvas`` method of the wx original is split here into
small ``_add_*`` helpers, and axes/zoom/pan are delegated to pyqtgraph.

Input data shape (same as the wx canvas):

* ``pcs_data`` — one entry per profile, each a sequence of linear-XYZ triplets
  sampling that profile's gamut surface (primary→secondary edges of ``size``
  segments), with the profile whitepoint as the final triplet.
* ``profiles`` — ``{index: ICCProfile}``, used to special-case named-colour
  profiles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyqtgraph as pg
from qtpy.QtGui import QColor

from DisplayCAL import colormath
from DisplayCAL.ui.plot.colorspaces import COLORSPACES, outline_curves

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qtpy.QtWidgets import QWidget

#: Greys/whites reused from the wx canvas.
_OUTLINE = QColor(102, 102, 102, 153)
_LOCUS = QColor(255, 255, 255, 204)
_COMPARISON = QColor(102, 102, 102, 255)
_COMPARISON_WP = QColor(204, 204, 204, 102)
_BACKGROUND = QColor(40, 40, 40)


def _rgb(xyz: tuple[float, float, float]) -> QColor:
    """Return the display QColor for a linear-XYZ triplet."""
    r, g, b = (max(0, min(255, int(v))) for v in colormath.XYZ2RGB(*xyz, scale=255))
    return QColor(r, g, b)


class GamutPlot(pg.PlotWidget):
    """Plot widget that draws profile gamuts in a chosen 2D projection."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, background=_BACKGROUND)
        self.colorspace = "a*b*"
        self.pcs_data: list[list[tuple[float, float, float]]] = []
        self.profiles: dict[int, object] = {}
        self.size = 40  # segments per primary→secondary edge
        plot_item = self.getPlotItem()
        plot_item.setAspectLocked(True)
        plot_item.showGrid(x=True, y=True, alpha=0.25)
        plot_item.hideButtons()
        plot_item.setMenuEnabled(False)

    def set_data(
        self,
        pcs_data: list[list[tuple[float, float, float]]],
        profiles: dict[int, object] | None = None,
        size: int = 40,
    ) -> None:
        """Set the gamut sample data and (optional) profile map."""
        self.pcs_data = pcs_data
        self.profiles = profiles or {}
        self.size = size

    # -- drawing -----------------------------------------------------------

    def draw_gamut(
        self,
        colorspace: str | None = None,
        whitepoint: int = 1,
        show_outline: bool = True,
    ) -> None:
        """Redraw the whole gamut plot.

        Args:
            colorspace: Projection to use (key of ``COLORSPACES``); keeps the
                current one if omitted.
            whitepoint: Colour-temperature locus to overlay (0=none, 1=daylight,
                2=Planckian).
            show_outline: Whether to draw the spectral-locus / optimal-colour
                boundary.
        """
        if colorspace:
            self.colorspace = colorspace
        cfg = COLORSPACES[self.colorspace]
        self.clear()
        self.getPlotItem().setLabels(bottom=cfg.label_x, left=cfg.label_y)

        if show_outline:
            self._add_outline()
        if whitepoint:
            self._add_locus(whitepoint)

        for index, pcs_triplets in enumerate(self.pcs_data):
            if pcs_triplets and len(pcs_triplets) > 1:
                self._add_profile(index, pcs_triplets)

        self._autorange(cfg.view)

    def _add_curve(
        self,
        points: Sequence[tuple[float, float]],
        color: QColor,
        width: float,
        fill: QColor | None = None,
    ) -> None:
        """Add a polyline (optionally closed/filled) to the plot."""
        if not points:
            return
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        self.addItem(
            pg.PlotCurveItem(
                xs, ys, pen=pg.mkPen(color, width=width), fillLevel=None, brush=fill
            )
        )

    def _add_markers(
        self,
        points: Sequence[tuple[float, float]],
        color: QColor,
        size: float,
        symbol: str,
    ) -> None:
        """Add scatter markers to the plot."""
        if not points:
            return
        self.addItem(
            pg.ScatterPlotItem(
                [p[0] for p in points],
                [p[1] for p in points],
                symbol=symbol,
                size=max(4.0, size * 4.0),
                pen=pg.mkPen(color),
                brush=None,
            )
        )

    def _add_outline(self) -> None:
        """Draw the colorspace boundary curve(s)."""
        for curve in outline_curves(self.colorspace):
            self._add_curve(curve, _OUTLINE, 1.75)

    def _add_locus(self, whitepoint: int) -> None:
        """Draw the daylight (1) or Planckian (2) colour-temperature locus."""
        cfg = COLORSPACES[self.colorspace]
        if whitepoint == 1:
            kelvins = range(4000, 25001, 40)
            xyz = colormath.CIEDCCT2XYZ
        else:
            kelvins = range(1667, 25001, 38)
            xyz = colormath.planckianCT2XYZ
        self._add_curve(
            [cfg.convert(*xyz(k)) for k in kelvins], _LOCUS, 1.5
        )

    def _add_profile(
        self, index: int, pcs_triplets: Sequence[tuple[float, float, float]]
    ) -> None:
        """Draw one profile's gamut hull and whitepoint marker."""
        cfg = COLORSPACES[self.colorspace]
        is_comparison = index == 1
        coords = [cfg.convert(*t) for t in pcs_triplets]
        profile = self.profiles.get(index)

        if _is_named_color(profile):
            for triplet, (x, y) in zip(pcs_triplets, coords):
                self._add_markers([(x, y)], _rgb(triplet), 2, "+")
            return

        # Gamut hull: colour each segment by its vertex colour, except the
        # comparison profile which is drawn as a plain grey outline.
        surface = coords[:-1]
        triplets = pcs_triplets[:-1]
        for start in range(0, len(surface) - 1, self.size):
            edge = surface[start : start + self.size]
            edge_triplets = triplets[start : start + self.size]
            for j in range(len(edge) - 1):
                color = _COMPARISON if is_comparison else _rgb(edge_triplets[j])
                self._add_curve(
                    [edge[j], edge[j + 1]], color, 2 if is_comparison else 3
                )

        # Whitepoint marker.
        wx_, wy = coords[-1]
        if is_comparison:
            self._add_markers([(wx_, wy)], _COMPARISON_WP, 1.5, "x")
        else:
            self._add_markers([(wx_, wy)], _rgb(pcs_triplets[-1]), 2, "+")

    def _autorange(self, view: tuple[float, float, float, float]) -> None:
        """Fit the view to the data, with the configured minimum extent."""
        min_x, min_y, max_x, max_y = view
        for triplets in self.pcs_data:
            cfg = COLORSPACES[self.colorspace]
            for triplet in triplets:
                x, y = cfg.convert(*triplet)
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
        pad_x = (max_x - min_x) / 20.0
        pad_y = (max_y - min_y) / 20.0
        self.setXRange(min_x - pad_x, max_x + pad_x, padding=0)
        self.setYRange(min_y - pad_y, max_y + pad_y, padding=0)


def _is_named_color(profile: object) -> bool:
    """Return True if ``profile`` is a named-colour profile with ncl2 data."""
    return bool(
        profile is not None
        and getattr(profile, "profileClass", None) == b"nmcl"
        and "ncl2" in getattr(profile, "tags", {})
        and getattr(profile, "connectionColorSpace", None) in (b"Lab", b"XYZ")
    )
