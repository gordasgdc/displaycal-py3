"""Curve viewer — Qt port.

Qt equivalent of the directly-plottable curve modes of
:mod:`DisplayCAL.wx_lut_viewer` (the ``curve-viewer`` tool). Loads an ICC
profile and shows its calibration (``vcgt``) and/or tone-response (``*TRC``)
curves with :class:`~DisplayCAL.ui.plot.curve.CurvePlot`.

Deferred from the wx frame (see ``DisplayCAL/ui/README.md``): the "actual"
measured tone-response computed through Argyll ``xicclu`` with rendering-intent
and direction controls, reading the live video-card LUT, and curve smoothing.
"""

from __future__ import annotations

import os
import sys

from qtpy.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import get_data_path
from DisplayCAL.icc_profile import ICCProfile
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.file_drop import FileDropTarget
from DisplayCAL.ui.plot.curve import CurvePlot
from DisplayCAL.ui.plot.curve_data import (
    CURVE_MODES,
    available_curve_modes,
    extract_curves,
)

#: Profile file suffixes accepted for opening / drag-and-drop.
PROFILE_SUFFIXES = (".icc", ".icm")


class CurveViewerWindow(BaseWindow):
    """Window showing a profile's calibration / tone-response curves."""

    def __init__(self) -> None:
        super().__init__(
            name="curve-viewer",
            title=lang.getstr("calibration.lut_viewer.title"),
            icon_name=f"{APPNAME}-curve-viewer".lower(),
        )
        self._profile: ICCProfile | None = None

        self.mode_combo = QComboBox()
        self.mode_combo.currentIndexChanged.connect(self._redraw)
        self.status = QLabel("")
        self.plot = CurvePlot()

        self.setCentralWidget(self._build_central())
        self.resize(820, 720)

        self.droptarget = FileDropTarget(
            drophandlers=dict.fromkeys(PROFILE_SUFFIXES, self.load_profile),
            parent=self,
        )
        self.droptarget.install_on(self)
        self.init_menubar()

    def _build_central(self) -> QWidget:
        """Assemble the control bar and the curve plot."""
        controls = QHBoxLayout()
        controls.addWidget(QLabel(lang.getstr("mode")))
        controls.addWidget(self.mode_combo)
        controls.addStretch(1)
        controls.addWidget(self.status)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.addLayout(controls)
        layout.addWidget(self.plot, 1)
        return central

    # -- loading -----------------------------------------------------------

    def load_profile(self, path: str) -> None:
        """Load the profile at ``path`` and show its available curves."""
        try:
            profile = ICCProfile(path)
        except Exception as exception:  # noqa: BLE001
            self.status.setText(f"{lang.getstr('error')}: {exception}")
            return
        self._profile = profile
        self.setWindowTitle(
            f"{lang.getstr('calibration.lut_viewer.title')} — "
            f"{profile.getDescription()}"
        )

        modes = available_curve_modes(profile)
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        for mode in modes:
            self.mode_combo.addItem(lang.getstr(CURVE_MODES[mode]), mode)
        self.mode_combo.blockSignals(False)

        if not modes:
            self.plot.draw_curves({})
            self.status.setText(lang.getstr("profile.no_vcgt"))
            return
        self._redraw()

    def _redraw(self) -> None:
        """Redraw the curves for the selected mode."""
        if self._profile is None or self.mode_combo.count() == 0:
            return
        mode = self.mode_combo.currentData()
        curves = extract_curves(self._profile, mode)
        self.plot.draw_curves(curves)
        self.status.setText(self._profile.getDescription())


def main() -> int:
    """Entry point for the Qt curve viewer."""
    config.initcfg("curve-viewer")
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    window = CurveViewerWindow()
    app.top_window = window
    window.show()

    profiles = [a for a in sys.argv[1:] if os.path.isfile(a)]
    window.load_profile(profiles[0] if profiles else get_data_path("ref/sRGB.icm"))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
