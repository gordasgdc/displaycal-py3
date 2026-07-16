"""CCMX/CCSS plot window — Qt port of ``wx_ccxx_plot.CCXXPlot``.

Shows a colorimeter-correction's spectral power-distribution curves (CCSS) or
matrix "flower" plot (CCMX), computed by
:func:`DisplayCAL.ui.plot.ccxx_data.compute_ccxx_plot_data` and rendered by
:class:`DisplayCAL.ui.plot.ccxx.CCXXPlotWidget`. CCSS corrections additionally
get a toggle button switching to a CIE 1931 xy chromaticity view, matching the
wx original's ``toggle_btn``.

Deliberately dropped versus the wx original: the hand-rolled mouse-wheel/
+/- key zoom handlers (pyqtgraph's own wheel-zoom/drag-pan already cover this,
see :mod:`DisplayCAL.ui.plot.ccxx`) and the forced near-black canvas colours
(the plot instead follows the OS light/dark theme, matching every other
:mod:`DisplayCAL.ui.plot` widget).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from DisplayCAL import localization as lang
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.plot.ccxx import CCXXPlotWidget
from DisplayCAL.ui.plot.ccxx_data import compute_ccxx_plot_data

if TYPE_CHECKING:
    from DisplayCAL.cgats import CGATS
    from DisplayCAL.worker import Worker


class CCXXPlotWindow(BaseWindow):
    """Window showing a CCMX/CCSS correction's spectral or matrix plot.

    Args:
        cgats (CGATS): A CCMX/CCSS CGATS instance.
        worker (Worker | None): Worker used to run Argyll's ``spec2cie`` when
            ``cgats`` is a CCSS (spectral) correction.
    """

    def __init__(self, cgats: CGATS, worker: Worker | None = None) -> None:
        super().__init__(
            name="ccxx-plot",
            title=lang.getstr("please_wait"),
            icon_name=f"{APPNAME}-ccxx-plot".lower(),
        )
        data = compute_ccxx_plot_data(cgats, worker)
        self.setWindowTitle(data.title)
        self._mode = "ccxx"

        central = QWidget()
        layout = QVBoxLayout(central)

        self.plot = CCXXPlotWidget()
        self.plot.set_data(data)

        self.toggle_btn: QPushButton | None = None
        if data.is_ccss:
            self.toggle_btn = QPushButton(lang.getstr("spectral"))
            self.toggle_btn.clicked.connect(self._toggle)
            layout.addWidget(self.toggle_btn)

        layout.addWidget(self.plot, 1)

        self.label = QLabel(data.x_label)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        self.setCentralWidget(central)
        self.resize(513, 557) if data.is_ccss else self.resize(400, 440)

        self.plot.draw_ccxx()

    def _toggle(self) -> None:
        """Switch between the spectral/matrix plot and the CIE xy plot."""
        if self._mode == "ccxx":
            self._mode = "cie"
            self.plot.draw_cie()
            self.toggle_btn.setText(lang.getstr("whitepoint.xy"))
        else:
            self._mode = "ccxx"
            self.plot.draw_ccxx()
            self.toggle_btn.setText(lang.getstr("spectral"))
