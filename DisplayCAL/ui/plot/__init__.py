"""Qt plotting layer for DisplayCAL, built on pyqtgraph.

This is the Qt replacement for the vendored ``wx_enhanced_plot`` engine (a copy
of ``wx.lib.plot``) and the canvases built on it (``LUTCanvas``, ``GamutCanvas``,
the ccxx plot). pyqtgraph provides the axes, grid, zoom/pan and item rendering;
the modules here only carry the DisplayCAL-specific colorimetry and the data →
plot-item translation.
"""

from __future__ import annotations
