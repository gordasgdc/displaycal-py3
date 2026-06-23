"""Profile information / gamut viewer — Qt port.

Qt equivalent of the gamut-viewer core of :mod:`DisplayCAL.wx_profile_info`. It
loads an ICC profile, computes its gamut surface through Argyll's ``xicclu``
(off the GUI thread) and shows it in a :class:`~DisplayCAL.ui.plot.gamut.GamutPlot`
alongside a profile-information panel, with colorspace and white-point controls.

Not yet ported from the wx frame (tracked in ``DisplayCAL/ui/README.md``):
the tone-response-curve view (inherited from ``LUTFrame``), profile comparison
(second profile overlay), rendering-intent/direction controls and 3D/VRML export.
"""

from __future__ import annotations

import os
import sys

from qtpy.QtCore import Qt, QThread, Signal
from qtpy.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSplitter,
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
from DisplayCAL.ui.plot.colorspaces import COLORSPACES
from DisplayCAL.ui.plot.gamut import GamutPlot
from DisplayCAL.ui.plot.gamut_data import compute_profile_gamut, is_supported
from DisplayCAL.worker import Worker

#: Profile file suffixes accepted for opening / drag-and-drop.
PROFILE_SUFFIXES = (".icc", ".icm")

#: White-point locus options: label -> draw_gamut code.
WHITEPOINTS = {"Daylight (CIE 1931)": 1, "Black body (Planckian)": 2, "None": 0}


class _GamutThread(QThread):
    """Compute a profile's gamut samples off the GUI thread."""

    #: Emitted with ``(triplets, profile)`` or, on failure, ``(exception, None)``.
    done = Signal(object, object)

    def __init__(
        self, profile: ICCProfile, worker: Worker, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._profile = profile
        self._worker = worker

    def run(self) -> None:
        try:
            triplets = compute_profile_gamut(self._profile, self._worker)
            self.done.emit(triplets, self._profile)
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            self.done.emit(exception, None)
        finally:
            self._worker.wrapup(False)


class ProfileInfoWindow(BaseWindow):
    """Window showing a profile's gamut plus its information."""

    def __init__(self) -> None:
        super().__init__(
            name="profile-info",
            title=lang.getstr("profile.info"),
            icon_name=f"{APPNAME}-profile-info".lower(),
        )
        self.worker = Worker()
        self._thread: _GamutThread | None = None
        self._triplets: list[list[float]] = []
        self._profile: ICCProfile | None = None

        self.colorspace_combo = QComboBox()
        self.colorspace_combo.addItems(list(COLORSPACES))
        self.colorspace_combo.setCurrentText("a*b*")
        self.colorspace_combo.currentTextChanged.connect(self._redraw)

        self.whitepoint_combo = QComboBox()
        self.whitepoint_combo.addItems(list(WHITEPOINTS))
        self.whitepoint_combo.currentTextChanged.connect(self._redraw)

        self.plot = GamutPlot()
        self.info = QPlainTextEdit()
        self.info.setReadOnly(True)
        self.info.setMinimumWidth(260)

        self.setCentralWidget(self._build_central())
        self.resize(1000, 720)

        self.droptarget = FileDropTarget(
            drophandlers=dict.fromkeys(PROFILE_SUFFIXES, self.load_profile),
            parent=self,
        )
        self.droptarget.install_on(self)
        self.init_menubar()

    def _build_central(self) -> QWidget:
        """Assemble the control bar, info panel and gamut plot."""
        controls = QHBoxLayout()
        controls.addWidget(QLabel(lang.getstr("colorspace")))
        controls.addWidget(self.colorspace_combo)
        controls.addSpacing(12)
        controls.addWidget(QLabel(lang.getstr("whitepoint")))
        controls.addWidget(self.whitepoint_combo)
        controls.addStretch(1)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.info)
        splitter.addWidget(self.plot)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.addLayout(controls)
        layout.addWidget(splitter, 1)
        return central

    # -- loading -----------------------------------------------------------

    def load_profile(self, path: str) -> None:
        """Load the profile at ``path`` and start computing its gamut."""
        if self._thread is not None and self._thread.isRunning():
            return
        try:
            profile = ICCProfile(path)
        except Exception as exception:  # noqa: BLE001
            self.info.setPlainText(f"{lang.getstr('error')}: {exception}")
            return
        self._show_info(profile, computing=True)
        if not is_supported(profile):
            self.info.appendPlainText("\n" + lang.getstr("profile.unsupported"))
            return
        self.setWindowTitle(
            f"{lang.getstr('profile.info')} — {profile.getDescription()}"
        )
        self._thread = _GamutThread(profile, self.worker, parent=self)
        self._thread.done.connect(self._on_gamut_ready)
        self._thread.start()

    def _on_gamut_ready(self, result: object, profile: object) -> None:
        """Receive computed gamut data on the GUI thread and draw it."""
        self._thread = None
        if isinstance(result, Exception):
            self.info.appendPlainText(f"\n{lang.getstr('error')}: {result}")
            return
        self._triplets = result
        self._profile = profile
        self.plot.set_data([result], profiles={0: profile})
        self._show_info(profile, computing=False)
        self._redraw()

    # -- view --------------------------------------------------------------

    def _redraw(self) -> None:
        """Redraw the gamut for the current control selections."""
        if not self._triplets:
            return
        self.plot.draw_gamut(
            colorspace=self.colorspace_combo.currentText(),
            whitepoint=WHITEPOINTS[self.whitepoint_combo.currentText()],
        )

    def _show_info(self, profile: ICCProfile, computing: bool) -> None:
        """Populate the information panel from ``profile``."""
        lines = [
            profile.getDescription(),
            "",
            f"{lang.getstr('colorspace')}: {profile.colorSpace.decode()}",
            f"PCS: {profile.connectionColorSpace.decode()}",
            f"{lang.getstr('profile.class')}: {profile.profileClass.decode()}",
            f"{lang.getstr('version')}: {profile.version}",
            f"{lang.getstr('tags')}: {', '.join(sorted(profile.tags))}",
        ]
        if computing:
            lines += ["", lang.getstr("please_wait")]
        self.info.setPlainText("\n".join(lines))


def main() -> int:
    """Entry point for the Qt profile information viewer."""
    config.initcfg("profile-info")
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    window = ProfileInfoWindow()
    app.top_window = window
    window.show()

    profiles = [a for a in sys.argv[1:] if os.path.isfile(a)]
    window.load_profile(profiles[0] if profiles else get_data_path("ref/sRGB.icm"))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
