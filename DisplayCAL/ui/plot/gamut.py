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
from DisplayCAL.ui.theme import plot_colors

if TYPE_CHECKING:
    from collections.abc import Sequence

    from qtpy.QtCore import QEvent
    from qtpy.QtWidgets import QWidget

#: Neutral greys reused from the wx canvas; legible in both light and dark
#: themes (the spectral-locus outline and comparison-profile hull/whitepoint).
#: The colour-temperature locus and canvas/axis colours instead come from
#: :func:`DisplayCAL.ui.theme.plot_colors` so they follow the OS theme.
_OUTLINE = QColor(102, 102, 102, 153)
_COMPARISON = QColor(102, 102, 102, 255)
_COMPARISON_WP = QColor(204, 204, 204, 102)


def _rgb(xyz: tuple[float, float, float]) -> QColor:
    """Return the display QColor for a linear-XYZ triplet.

    Args:
        xyz (tuple[float, float, float]): A linear-XYZ triplet.

    Returns:
        QColor: The corresponding (clamped 0..255) display colour.
    """
    r, g, b = (max(0, min(255, int(v))) for v in colormath.XYZ2RGB(*xyz, scale=255))
    return QColor(r, g, b)


class GamutPlot(pg.PlotWidget):
    """Plot widget that draws profile gamuts in a chosen 2D projection.

    Args:
        parent (QWidget | None): Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        # Guards changeEvent, which pyqtgraph's base __init__ can trigger
        # (via setBackgroundRole) before the plot item exists.
        self._ready = False
        super().__init__(parent)
        self.colorspace = "a*b*"
        self.pcs_data: list[list[tuple[float, float, float]]] = []
        self.profiles: dict[int, object] = {}
        # Segments per primary→secondary edge. NB: not named ``size`` because
        # that would shadow ``QWidget.size()``.
        self.segment_size = 40
        # Remembered draw parameters, so a live OS theme change can redraw.
        self._whitepoint = 1
        self._show_outline = True
        plot_item = self.getPlotItem()
        plot_item.setAspectLocked(True)
        plot_item.showGrid(x=True, y=True, alpha=0.25)
        plot_item.hideButtons()
        plot_item.setMenuEnabled(False)
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
            if self.pcs_data:
                self.draw_gamut(whitepoint=self._whitepoint,
                                show_outline=self._show_outline)

    def set_data(
        self,
        pcs_data: list[list[tuple[float, float, float]]],
        profiles: dict[int, object] | None = None,
        size: int = 40,
    ) -> None:
        """Set the gamut sample data and (optional) profile map.

        Args:
            pcs_data (list[list[tuple[float, float, float]]]): Per-profile lists
                of linear-XYZ gamut-surface samples.
            profiles (dict[int, object] | None): Optional ``{index: ICCProfile}``
                map (for named-colour special-casing).
            size (int): Segments per primary→secondary edge.
        """
        self.pcs_data = pcs_data
        self.profiles = profiles or {}
        self.segment_size = size

    # -- drawing -----------------------------------------------------------

    def draw_gamut(
        self,
        colorspace: str | None = None,
        whitepoint: int = 1,
        show_outline: bool = True,
    ) -> None:
        """Redraw the whole gamut plot.

        Args:
            colorspace (str | None): Projection to use (key of ``COLORSPACES``);
                keeps the current one if omitted.
            whitepoint (int): Colour-temperature locus to overlay (0=none,
                1=daylight, 2=Planckian).
            show_outline (bool): Whether to draw the spectral-locus /
                optimal-colour boundary.
        """
        if colorspace:
            self.colorspace = colorspace
        self._whitepoint = whitepoint
        self._show_outline = show_outline
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
        """Add a polyline (optionally closed/filled) to the plot.

        Args:
            points (Sequence[tuple[float, float]]): The polyline vertices.
            color (QColor): The pen colour.
            width (float): The pen width.
            fill (QColor | None): Optional fill brush colour.
        """
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
        """Add scatter markers to the plot.

        Args:
            points (Sequence[tuple[float, float]]): The marker positions.
            color (QColor): The marker pen colour.
            size (float): The relative marker size.
            symbol (str): The pyqtgraph marker symbol (e.g. ``"+"``, ``"x"``).
        """
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
        """Draw the daylight (1) or Planckian (2) colour-temperature locus.

        Args:
            whitepoint (int): 1 for the daylight locus, 2 for the Planckian one.
        """
        cfg = COLORSPACES[self.colorspace]
        if whitepoint == 1:
            kelvins = range(4000, 25001, 40)
            xyz = colormath.CIEDCCT2XYZ
        else:
            kelvins = range(1667, 25001, 38)
            xyz = colormath.planckianCT2XYZ
        self._add_curve(
            [cfg.convert(*xyz(k)) for k in kelvins], plot_colors(self).locus, 1.5
        )

    def _add_profile(
        self, index: int, pcs_triplets: Sequence[tuple[float, float, float]]
    ) -> None:
        """Draw one profile's gamut hull and whitepoint marker.

        Args:
            index (int): Index of the profile in ``pcs_data`` (1 = comparison).
            pcs_triplets (Sequence[tuple[float, float, float]]): The profile's
                linear-XYZ gamut-surface samples, whitepoint last.
        """
        cfg = COLORSPACES[self.colorspace]
        is_comparison = index == 1
        coords = [cfg.convert(*t) for t in pcs_triplets]
        profile = self.profiles.get(index)

        if _is_named_color(profile):
            for triplet, (x, y) in zip(pcs_triplets, coords):
                self._add_markers([(x, y)], _rgb(triplet), 2, "+")
            return

        # Gamut hull: colour each segment by its vertex colour, except the
        # comparison profile which is drawn as a plain grey outline. The
        # comparison outline also only draws every other segment (0,1),
        # (2,3), (4,5)... matching wx's manual dashing, since a real dash
        # pen would need to be re-cut on every zoom/pan to keep a constant
        # on-screen dash length.
        surface = coords[:-1]
        triplets = pcs_triplets[:-1]
        for start in range(0, len(surface) - 1, self.segment_size):
            edge = surface[start : start + self.segment_size]
            edge_triplets = triplets[start : start + self.segment_size]
            for j in range(len(edge) - 1):
                if is_comparison:
                    if j % 2:
                        continue
                    self._add_curve([edge[j], edge[j + 1]], _COMPARISON, 2)
                else:
                    self._add_curve(
                        [edge[j], edge[j + 1]], _rgb(edge_triplets[j]), 3
                    )

        # Whitepoint marker.
        wx_, wy = coords[-1]
        if is_comparison:
            self._add_markers([(wx_, wy)], _COMPARISON_WP, 1.5, "x")
        else:
            self._add_markers([(wx_, wy)], _rgb(pcs_triplets[-1]), 2, "+")

    def _autorange(self, view: tuple[float, float, float, float]) -> None:
        """Fit the view to the data, with the configured minimum extent.

        Args:
            view (tuple[float, float, float, float]): The minimum
                ``(min_x, min_y, max_x, max_y)`` extent to include.
        """
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
    """Return True if ``profile`` is a named-colour profile with ncl2 data.

    Args:
        profile (object): The profile to test (may be ``None``).

    Returns:
        bool: True if it is a named-colour (nmcl) profile with ncl2 data.
    """
    return bool(
        profile is not None
        and getattr(profile, "profileClass", None) == b"nmcl"
        and "ncl2" in getattr(profile, "tags", {})
        and getattr(profile, "connectionColorSpace", None) in (b"Lab", b"XYZ")
    )
