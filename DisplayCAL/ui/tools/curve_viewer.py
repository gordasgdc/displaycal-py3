"""Curve viewer — Qt port.

Qt equivalent of :mod:`DisplayCAL.wx_lut_viewer` (the ``curve-viewer`` tool).
Loads an ICC profile and shows its tone curves with
:class:`~DisplayCAL.ui.plot.curve.CurvePlot` in three modes:

* ``vcgt`` — calibration video-card-gamma curves (read from the tag),
* ``trc`` — the ``*TRC`` tone-response tags (read from the tag),
* ``measured`` — the *measured* tone response, computed live through Argyll
  ``xicclu`` with rendering-intent, lookup-direction (forward / inverse, plus
  backward variants for cLUT profiles) and cLUT/matrix controls.

It also loads ``.cal`` calibration files and can show the live video-card LUT
read back from the graphics card ("show actual LUT").
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from qtpy.QtCore import QThread, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import get_data_path, getcfg
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.file_drop import FileDropTarget
from DisplayCAL.ui.plot.curve import CurvePlot
from DisplayCAL.ui.plot.curve_data import (
    CURVE_MODES,
    DIRECTIONS,
    available_curve_modes,
    available_directions,
    extract_curves,
    load_profile_or_cal,
    measured_tone_response,
    read_current_lut,
)
from DisplayCAL.worker import Worker

if TYPE_CHECKING:
    from DisplayCAL.icc_profile import ICCProfile

#: Profile file suffixes accepted for opening / drag-and-drop (``.cal`` is
#: wrapped in a fake profile).
PROFILE_SUFFIXES = (".icc", ".icm", ".cal")

#: Rendering intents offered for the measured tone response.
INTENTS = {
    "relative_colorimetric": "r",
    "absolute_colorimetric": "a",
    "perceptual": "p",
    "saturation": "s",
}

#: Direction code -> human label key (inverse of curve_data.DIRECTIONS).
_DIRECTION_LABELS = {code: key for key, code in DIRECTIONS.items()}


class _MeasuredThread(QThread):
    """Compute the measured tone response off the GUI thread.

    Args:
        profile (ICCProfile): The RGB profile to measure.
        worker (Worker): The worker driving ``xicclu``.
        intent (str): Rendering intent (``a``/``r``/``p``/``s``).
        use_clut (bool): Use the cLUT path when the profile has one.
        direction (str): Lookup direction (``f``/``if``/``b``/``ib``).
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with ``curves`` (dict) or, on failure, an ``Exception``.
    done = Signal(object)

    def __init__(
        self,
        profile: ICCProfile,
        worker: Worker,
        intent: str,
        use_clut: bool,
        direction: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._args = (profile, worker, intent, use_clut, direction)

    def run(self) -> None:
        profile, worker, intent, use_clut, direction = self._args
        try:
            self.done.emit(
                measured_tone_response(
                    profile, worker, intent, use_clut, direction
                )
            )
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            self.done.emit(exception)
        finally:
            worker.wrapup(False)


class _LutReadThread(QThread):
    """Read the live video-card LUT off the GUI thread.

    Args:
        worker (Worker): The worker driving ``dispwin``.
        display_no (int): Argyll display index (1-based).
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with the read-back profile or, on failure, an ``Exception``.
    done = Signal(object)

    def __init__(
        self, worker: Worker, display_no: int, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._display_no = display_no

    def run(self) -> None:
        try:
            self.done.emit(read_current_lut(self._worker, self._display_no))
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            self.done.emit(exception)
        finally:
            self._worker.wrapup(False)


class CurveViewerWindow(BaseWindow):
    """Window showing a profile's calibration / tone-response curves."""

    def __init__(self) -> None:
        super().__init__(
            name="curve-viewer",
            title=lang.getstr("calibration.lut_viewer.title"),
            icon_name=f"{APPNAME}-curve-viewer".lower(),
        )
        self._profile: ICCProfile | None = None  # currently displayed
        self._user_profile: ICCProfile | None = None  # last loaded by the user
        self.worker = Worker()
        self._thread: _MeasuredThread | None = None
        self._read_thread: _LutReadThread | None = None

        self.mode_combo = QComboBox()
        self.mode_combo.currentIndexChanged.connect(self._redraw)

        self.actual_lut_check = QCheckBox(lang.getstr("calibration.show_actual_lut"))
        self.actual_lut_check.toggled.connect(self._on_actual_lut_toggled)

        # Controls shown only for the measured tone response.
        self.intent_label = QLabel(lang.getstr("rendering_intent"))
        self.intent_combo = QComboBox()
        for key in INTENTS:
            self.intent_combo.addItem(lang.getstr(key), INTENTS[key])
        self.intent_combo.currentIndexChanged.connect(self._redraw)
        self.direction_label = QLabel(lang.getstr("direction"))
        self.direction_combo = QComboBox()
        self.direction_combo.currentIndexChanged.connect(self._redraw)
        self.clut_check = QCheckBox(lang.getstr("use_separate_lut_access"))
        self.clut_check.setChecked(True)
        self.clut_check.toggled.connect(self._redraw)

        self.status = QLabel("")
        self.plot = CurvePlot()

        self.setCentralWidget(self._build_central())
        self.resize(820, 720)
        self._update_controls_visibility()

        self.droptarget = FileDropTarget(
            drophandlers=dict.fromkeys(PROFILE_SUFFIXES, self.load_profile),
            parent=self,
        )
        self.droptarget.install_on(self)
        self.init_menubar()

    def _build_central(self) -> QWidget:
        """Assemble the control bar and the curve plot.

        Returns:
            QWidget: The central widget holding the controls and curve plot.
        """
        controls = QHBoxLayout()
        controls.addWidget(QLabel(lang.getstr("mode")))
        controls.addWidget(self.mode_combo)
        controls.addSpacing(12)
        controls.addWidget(self.intent_label)
        controls.addWidget(self.intent_combo)
        controls.addWidget(self.direction_label)
        controls.addWidget(self.direction_combo)
        controls.addWidget(self.clut_check)
        controls.addSpacing(12)
        controls.addWidget(self.actual_lut_check)
        controls.addStretch(1)
        controls.addWidget(self.status)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.addLayout(controls)
        layout.addWidget(self.plot, 1)
        return central

    def _update_controls_visibility(self) -> None:
        """Show intent/direction/CLUT controls only in the measured mode."""
        measured = self.mode_combo.currentData() == "measured"
        has_clut = bool(
            self._profile
            and ("A2B0" in self._profile.tags or "B2A0" in self._profile.tags)
        )
        # Direction is only worth offering when there is more than one.
        multi_direction = measured and self.direction_combo.count() > 1
        self.intent_label.setVisible(measured)
        self.intent_combo.setVisible(measured)
        self.direction_label.setVisible(multi_direction)
        self.direction_combo.setVisible(multi_direction)
        self.clut_check.setVisible(measured and has_clut)

    # -- loading -----------------------------------------------------------

    def load_profile(self, path: str) -> None:
        """Load an ICC profile or ``.cal`` file at ``path`` and show its curves.

        Args:
            path (str): Path to an ``.icc``/``.icm`` profile or ``.cal`` file.
        """
        try:
            profile = load_profile_or_cal(os.path.abspath(path))
        except Exception as exception:  # noqa: BLE001
            self.status.setText(f"{lang.getstr('error')}: {exception}")
            return
        if profile is None:
            self.status.setText(f"{lang.getstr('error.file.open', path)}")
            return
        self._user_profile = profile
        # A freshly loaded profile supersedes any "show actual LUT" view.
        self.actual_lut_check.blockSignals(True)
        self.actual_lut_check.setChecked(False)
        self.actual_lut_check.blockSignals(False)
        self._set_profile(profile)

    def _set_profile(self, profile: ICCProfile) -> None:
        """Display ``profile`` (user-loaded or read-back), repopulating modes.

        Args:
            profile (ICCProfile): The profile to display.
        """
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

        self.direction_combo.blockSignals(True)
        self.direction_combo.clear()
        if profile.colorSpace == b"RGB":
            for code in available_directions(profile):
                self.direction_combo.addItem(
                    lang.getstr(_DIRECTION_LABELS[code]), code
                )
        self.direction_combo.blockSignals(False)

        if not modes:
            self.plot.draw_curves({})
            self.status.setText(lang.getstr("profile.no_vcgt"))
            return
        self._redraw()

    def _on_actual_lut_toggled(self, checked: bool) -> None:
        """Switch between the loaded profile and the live video-card LUT.

        Args:
            checked (bool): Whether the "show actual LUT" box is checked.
        """
        if not checked:
            if self._user_profile is not None:
                self._set_profile(self._user_profile)
            return
        if self._read_thread is not None and self._read_thread.isRunning():
            return
        self.status.setText(lang.getstr("please_wait"))
        self._read_thread = _LutReadThread(
            self.worker, getcfg("display.number") or 1, parent=self
        )
        self._read_thread.done.connect(self._on_lut_read)
        self._read_thread.start()

    def _on_lut_read(self, result: object) -> None:
        """Receive the read-back LUT profile on the GUI thread.

        Args:
            result (object): The read-back profile, or an ``Exception`` on
                failure.
        """
        self._read_thread = None
        if isinstance(result, Exception):
            self.actual_lut_check.blockSignals(True)
            self.actual_lut_check.setChecked(False)
            self.actual_lut_check.blockSignals(False)
            self.status.setText(f"{lang.getstr('error')}: {result}")
            return
        self._set_profile(result)

    def _redraw(self) -> None:
        """Redraw the curves for the selected mode."""
        if self._profile is None or self.mode_combo.count() == 0:
            return
        self._update_controls_visibility()
        mode = self.mode_combo.currentData()
        if mode == "measured":
            self._draw_measured()
            return
        self.plot.draw_curves(extract_curves(self._profile, mode))
        self.status.setText(self._profile.getDescription())

    def _draw_measured(self) -> None:
        """Compute the measured tone response on a worker thread, then draw."""
        if self._thread is not None and self._thread.isRunning():
            return
        self.status.setText(lang.getstr("please_wait"))
        self._thread = _MeasuredThread(
            self._profile,
            self.worker,
            self.intent_combo.currentData(),
            self.clut_check.isChecked(),
            self.direction_combo.currentData() or "f",
            parent=self,
        )
        self._thread.done.connect(self._on_measured_ready)
        self._thread.start()

    def _on_measured_ready(self, result: object) -> None:
        """Receive measured curves on the GUI thread and draw them.

        Args:
            result (object): The measured curves dict, or an ``Exception`` on
                failure.
        """
        self._thread = None
        if isinstance(result, Exception):
            self.plot.draw_curves({})
            self.status.setText(f"{lang.getstr('error')}: {result}")
            return
        self.plot.draw_curves(result)
        self.status.setText(self._profile.getDescription())


def main() -> int:
    """Entry point for the Qt curve viewer.

    Returns:
        int: The Qt application exit code.
    """
    config.initcfg("curve-viewer")
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    window = CurveViewerWindow()
    app.top_window = window
    window.show()
    window.listen()

    profiles = [a for a in sys.argv[1:] if os.path.isfile(a)]
    window.load_profile(profiles[0] if profiles else get_data_path("ref/sRGB.icm"))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
