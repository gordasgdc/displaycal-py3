"""DisplayCAL main window — Qt port (Stage 3).

The wx main window is ``display_cal.MainFrame``: ~19,700 lines and 352 methods
driving the whole application. Porting it happens in vertical, independently
shippable slices (see ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``, Stage 3+). This
module is the **shell** those slices grow into plus the four settings tabs:

* the top-level ``MainWindow(BaseWindow)`` window, its menubar and geometry
  persistence (inherited from :class:`~DisplayCAL.ui.base_window.BaseWindow`),
* a tab bar of exclusive toggle buttons switching a :class:`QStackedWidget` of
  settings panels (the wx custom ``TabButton`` / show-hide-panel mechanism),
* the **Display & Instrument** tab, wired to ``config`` and the binding-agnostic
  :class:`~DisplayCAL.worker.Worker` display/port enumeration,
* the **Calibration**, **Profiling** and **3D LUT** tabs, whose config-backed
  settings controls are wired to ``config`` through an ``_updating`` re-entrancy
  guard (so repopulation never clobbers the stored selection),
* the calibrate / calibrate&profile / profile action-button bar, wired against
  the Stage-2 :mod:`DisplayCAL.ui.measurement_flow` engine: each button stages a
  :class:`MeasurementAction` and presents the measurement area (call-pending /
  in-process measure frame / measure-frame subprocess on a :class:`QThread`),
  emitting :attr:`MainWindow.measurement_requested` once the user commits.

The ``get_*`` settings getters deferred from Stage 0 land here as the Qt controls
that back them (whitepoint / TRC / luminance / quality) are built: they read
control state, mirroring the wx ``MainFrame`` getters, and are exercised through
the pure marshalling helpers at module scope.

Deferred to later slices (Pile 2 / Stage 5): the worker-driven Argyll execution
behind :attr:`MainWindow.measurement_requested` (the progress dialog and
interactive display-adjustment window), the pattern-generator setup dialogs
(Prisma / madTPG / Resolve), the pre-flight confirmation / overwrite dialogs, the
visual-editor / ambient-measure buttons, the gamap and testchart-editor /
file-picker launch buttons, profile-name token expansion, the advanced-option
show/hide gating, the estimated-measurement-time readouts and the
black-point-rate advanced control.

The window is opt-in behind ``DISPLAYCAL_UI=qt`` / ``--qt`` (wired in
:mod:`DisplayCAL.main`), so it never displaces the still-shipping wx main window.
"""

from __future__ import annotations

import contextlib
import enum
import os
import sys
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, QThread, QTimer, Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import DEFAULTS, getcfg, setcfg, writecfg
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.assets import get_theme_pixmap
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.measure_frame import MeasureFrame
from DisplayCAL.ui.measurement_flow import (
    MeasurementFlow,
    PresentationMode,
    build_measureframe_command,
    interpret_measureframe_result,
    observer_items,
    run_measureframe_subprocess,
)
from DisplayCAL.util_decimal import stripzeros
from DisplayCAL.worker import Worker

if TYPE_CHECKING:
    from qtpy.QtGui import QShowEvent


#: The settings tabs, in order: ``(config-ish key, icon name, label key)``.
_TABS = (
    ("display_instrument", "display-instrument", "display"),
    ("calibration", "calibration", "calibration"),
    ("profiling", "profiling", "profiling"),
    ("lut3d", "3dlut", "3dlut"),
)

#: Calibration quality letters, ordered so ``index + 1`` is the wx slider value
#: (``MainFrame.quality_ab`` = ``{1: "v", 2: "l", 3: "m", 4: "h", 5: "u"}``).
CALIBRATION_QUALITY_LEVELS = ("v", "l", "m", "h", "u")

#: Profile quality letters, ordered so ``index + 1`` is the wx slider value
#: (``get_profile_quality`` = ``quality_ab[value + 1]``, i.e. ``l/m/h/u``).
PROFILE_QUALITY_LEVELS = ("l", "m", "h", "u")

#: quality letter -> ``calibration.speed.<x>`` suffix (speed is inverse quality).
_CALIBRATION_SPEED_LABELS = {
    "v": "veryhigh",
    "l": "high",
    "m": "medium",
    "h": "low",
    "u": "verylow",
}

#: quality letter -> ``calibration.quality.<x>`` suffix (for the profile slider).
_PROFILE_QUALITY_LABELS = {"l": "low", "m": "medium", "h": "high", "u": "ultra"}

#: Profile types for modern Argyll (>= 1.1.0 RC4), matching the wx ordering in
#: ``update_profile_type_ctrl_items``: ``(config value, label key)``.
PROFILE_TYPES = (
    ("X", "profile.type.lut_matrix.xyz"),
    ("x", "profile.type.lut.xyz"),
    ("l", "profile.type.lut.lab"),
    ("s", "profile.type.shaper_matrix"),
    ("S", "profile.type.single_shaper_matrix"),
    ("g", "profile.type.gamma_matrix"),
    ("G", "profile.type.single_gamma_matrix"),
)

#: Calibration TRC selector entries, in display order (row index == combo row).
_TRC_ITEMS = (
    "as_measured",
    "Gamma 2.2",
    "trc.lstar",
    "trc.rec709",
    "trc.rec1886",
    "trc.smpte240m",
    "trc.srgb",
    "custom",
)
#: TRC rows whose value comes from the gamma text field.
_TRC_TEXT_ROWS = (1, 4, 7)
#: TRC rows that map straight to a fixed config value.
_TRC_FIXED = {2: "l", 3: "709", 5: "240", 6: "s"}


class MeasurementAction(enum.Enum):
    """Which measurement workflow an action button triggers.

    Mirrors the wx button handlers (``calibrate_btn_handler`` etc.). The engine
    stages one of these as the pending measurement; the worker-driven Argyll run
    behind it lands in a later slice (see :meth:`MainWindow._drive_measurement`).
    """

    #: Calibrate only (``MainFrame.just_calibrate``).
    CALIBRATE = "calibrate"
    #: Calibrate then characterize (``MainFrame.calibrate_and_profile``).
    CALIBRATE_AND_PROFILE = "calibrate_and_profile"
    #: Characterize only (``MainFrame.just_measure`` / ``just_profile``).
    PROFILE = "profile"


class _MeasureframeSubprocessThread(QThread):
    """Run the measure-frame subprocess off the UI thread.

    The Qt equivalent of the wx ``delayedresult`` producer around
    ``MainFrame.measureframe_subprocess``: it blocks in
    :func:`~DisplayCAL.ui.measurement_flow.run_measureframe_subprocess` on a
    worker thread and reports the ``(returncode, stderr)`` back to the window via
    :attr:`finished_with_result`.
    """

    #: Emitted with the subprocess ``(returncode, stderr)`` when it exits.
    finished_with_result = Signal(int, str)

    def __init__(
        self, args: list[str], env: dict[str, str], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._args = args
        self._env = env
        #: The live subprocess, kept so the caller can terminate it.
        self.process = None

    def run(self) -> None:  # noqa: D102 (QThread override)
        returncode, stderr = run_measureframe_subprocess(
            self._args, self._env, on_start=self._store_process
        )
        self.finished_with_result.emit(returncode, stderr)

    def _store_process(self, process: object) -> None:
        self.process = process


def _as_float(value: object) -> float | None:
    """Best-effort float coercion (``None`` when not numeric)."""
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def display_items(displays: list[str]) -> list[str]:
    """Localize raw worker display names for the display selector.

    Mirrors the marshalling in ``MainFrame.update_displays``: the ``[PRIMARY]``
    marker becomes the localized ``display.primary`` suffix and each name is run
    through :func:`localization.getstr` (names are themselves lookup keys).

    Args:
        displays (list[str]): ``worker.displays`` entries.

    Returns:
        list[str]: Display labels for the combo box.
    """
    items = []
    for name in displays:
        label = name.replace("[PRIMARY]", lang.getstr("display.primary"))
        items.append(lang.getstr(label))
    return items


def instrument_items(instruments: list[str]) -> list[str]:
    """Localize raw worker instrument names for the instrument selector.

    Mirrors ``MainFrame.update_comports``: each instrument name maps to an
    ``instrument.<slug>`` localization key, falling back to the raw name.

    Args:
        instruments (list[str]): ``worker.instruments`` entries.

    Returns:
        list[str]: Instrument labels for the combo box.
    """
    items = []
    for instrument in instruments:
        slug = instrument.lower().replace(" ", "_").replace(",", "")
        items.append(lang.getstr(f"instrument.{slug}", default=instrument))
    return items


def calibration_quality_to_slider(quality: str) -> int:
    """Return the calibration-quality slider value for a config letter.

    Args:
        quality (str): One of :data:`CALIBRATION_QUALITY_LEVELS`.

    Returns:
        int: The 1-based slider value (falls back to the config default).
    """
    levels = CALIBRATION_QUALITY_LEVELS
    if quality in levels:
        return levels.index(quality) + 1
    return levels.index(DEFAULTS["calibration.quality"]) + 1


def slider_to_calibration_quality(value: int) -> str:
    """Return the calibration-quality config letter for a slider value."""
    index = min(max(value, 1), len(CALIBRATION_QUALITY_LEVELS)) - 1
    return CALIBRATION_QUALITY_LEVELS[index]


def profile_quality_to_slider(quality: str) -> int:
    """Return the profile-quality slider value for a config letter."""
    levels = PROFILE_QUALITY_LEVELS
    if quality in levels:
        return levels.index(quality) + 1
    return levels.index(DEFAULTS["profile.quality"]) + 1


def slider_to_profile_quality(value: int) -> str:
    """Return the profile-quality config letter for a slider value."""
    index = min(max(value, 1), len(PROFILE_QUALITY_LEVELS)) - 1
    return PROFILE_QUALITY_LEVELS[index]


def trc_value_from_selection(index: int, text: str) -> str:
    """Return the ``trc`` config value for a TRC combo row + gamma text.

    Mirrors ``MainFrame.get_trc``.

    Args:
        index (int): The selected TRC combo row.
        text (str): The gamma text-field contents.

    Returns:
        str: The ``trc`` config value ("" = as-measured).
    """
    if index in _TRC_TEXT_ROWS:
        return str(stripzeros(text.replace(",", "."))) if text.strip() else ""
    return _TRC_FIXED.get(index, "")


def trc_selection_from_config(
    trc: object, trc_type: str, black_output_offset: object
) -> tuple[int, str, int]:
    """Return the TRC combo state for the stored config.

    Mirrors the reverse mapping in ``MainFrame.update_calibration_file_ctrl``.

    Args:
        trc (object): The stored ``trc`` value (str or number).
        trc_type (str): The stored ``trc.type`` ("g" or "G").
        black_output_offset (object): The stored ``calibration.black_output_offset``.

    Returns:
        tuple[int, str, int]: ``(combo row, gamma text, type combo row)``.
    """
    fixed_ba = {"l": 2, "709": 3, "240": 5, "s": 6}
    if trc in fixed_ba:
        return fixed_ba[trc], "", 0
    trc_num = _as_float(trc)
    boo = _as_float(black_output_offset)
    if trc_num == 2.4 and trc_type == "G" and boo == 0:
        return 4, str(trc), 1
    type_row = 1 if trc_type == "G" else 0
    if trc:
        if trc_num == 2.2 and trc_type == "g" and boo == 1:
            return 1, str(trc), type_row
        return 7, str(trc), type_row
    return 0, "", type_row


def lut3d_format_items() -> list[tuple[str, str]]:
    """Return ``(config value, label)`` pairs for the 3D LUT file formats."""
    return [
        (fmt, lang.getstr(f"3dlut.format.{fmt}"))
        for fmt in config.VALID_VALUES["3dlut.format"]
    ]


def lut3d_rendering_intent_items() -> list[tuple[str, str]]:
    """Return ``(config value, label)`` pairs for the 3D LUT rendering intents."""
    return [
        (ri, lang.getstr(f"gamap.intents.{ri}"))
        for ri in config.VALID_VALUES["3dlut.rendering_intent"]
    ]


def lut3d_size_items() -> list[tuple[int, str]]:
    """Return ``(config value, label)`` pairs for the 3D LUT sizes."""
    return [
        (size, f"{size}x{size}x{size}")
        for size in config.VALID_VALUES["3dlut.size"]
    ]


def lut3d_bitdepth_items() -> list[tuple[int, str]]:
    """Return ``(config value, label)`` pairs for the 3D LUT bit depths."""
    return [(bit, str(bit)) for bit in config.VALID_VALUES["3dlut.bitdepth.input"]]


class MainWindow(BaseWindow):
    """DisplayCAL's Qt main window (shell + all four settings tabs)."""

    #: Emitted (with a :class:`MeasurementAction`) once the user has committed to
    #: a run and the measurement area has been presented. The worker-driven
    #: Argyll execution layer connects this in a later slice; see
    #: :meth:`_drive_measurement`.
    measurement_requested = Signal(object)

    #: Delay before a staged measurement driver runs, letting the display settle
    #: (the wx ``call_pending_function`` 100 ms ``CallLater``).
    _pending_delay_ms = 100

    def __init__(self) -> None:
        super().__init__(
            name="mainframe",
            title=APPNAME,
            icon_name=APPNAME.lower(),
        )
        self.worker = Worker()
        self.flow = MeasurementFlow()
        #: Guards config-writing handlers while controls are repopulated.
        self._updating = False
        self._position_restored = False
        self._tab_buttons: dict[str, QToolButton] = {}
        self._panels: dict[str, QWidget] = {}
        #: config key -> (combo, [values]) for the generic value-combo binder.
        self._value_combos: dict[str, tuple[QComboBox, list]] = {}
        #: config key -> checkbox for the generic checkbox binder.
        self._value_checks: dict[str, QCheckBox] = {}
        #: The child measure frame, created lazily on first SHOW_FRAME run.
        self.measureframe: MeasureFrame | None = None
        #: The live measure-frame subprocess thread, if any.
        self._measureframe_thread: _MeasureframeSubprocessThread | None = None

        self._build_ui()
        self.init_menubar()
        self.setup_language()

        self.worker.enumerate_displays_and_ports(silent=True)
        self.update_controls()

    # -- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        """Assemble the tab bar, stacked settings panels and action buttons."""
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_tabbar())

        self.stack = QStackedWidget()
        self._panels["display_instrument"] = self._build_display_instrument_tab()
        self._panels["calibration"] = self._build_calibration_tab()
        self._panels["profiling"] = self._build_profiling_tab()
        self._panels["lut3d"] = self._build_lut3d_tab()
        for key, _icon, _label in _TABS:
            self.stack.addWidget(self._panels[key])
        layout.addWidget(self.stack, 1)

        layout.addWidget(self._build_button_bar())

        self.setCentralWidget(central)
        self._select_tab("display_instrument")

    def _build_tabbar(self) -> QWidget:
        """Build the exclusive toggle-button tab bar."""
        bar = QWidget()
        bar.setObjectName("tabpanel")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 8, 16, 8)
        row.setSpacing(24)

        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        for key, icon_name, label_key in _TABS:
            button = QToolButton()
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            pixmap = get_theme_pixmap(32, icon_name)
            if not pixmap.isNull():
                button.setIcon(pixmap)
            button.setText(lang.getstr(label_key))
            button.clicked.connect(lambda _checked, k=key: self._select_tab(k))
            self._tab_group.addButton(button)
            self._tab_buttons[key] = button
            row.addWidget(button)
        row.addStretch(1)
        return bar

    def _build_display_instrument_tab(self) -> QWidget:
        """Build the Display & Instrument settings panel."""
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        display_box = QGroupBox(lang.getstr("display"))
        display_form = QFormLayout(display_box)
        self.display_ctrl = QComboBox()
        self.display_ctrl.currentIndexChanged.connect(self.display_ctrl_handler)
        display_form.addRow(lang.getstr("display"), self.display_ctrl)
        outer.addWidget(display_box)

        instrument_box = QGroupBox(lang.getstr("instrument"))
        instrument_form = QFormLayout(instrument_box)
        self.comport_ctrl = QComboBox()
        self.comport_ctrl.currentIndexChanged.connect(self.comport_ctrl_handler)
        instrument_form.addRow(lang.getstr("instrument"), self.comport_ctrl)
        self.observer_ctrl = QComboBox()
        self.observer_ctrl.currentIndexChanged.connect(self.observer_ctrl_handler)
        instrument_form.addRow(lang.getstr("observer"), self.observer_ctrl)
        outer.addWidget(instrument_box)

        outer.addStretch(1)
        return panel

    def _build_calibration_tab(self) -> QWidget:
        """Build the Calibration settings panel."""
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        toggles = QHBoxLayout()
        self.interactive_adjustment_cb = QCheckBox(
            lang.getstr("calibration.interactive_display_adjustment")
        )
        self._add_check(
            self.interactive_adjustment_cb,
            "calibration.interactive_display_adjustment",
        )
        self.calibration_update_cb = QCheckBox(lang.getstr("calibration.update"))
        self._add_check(self.calibration_update_cb, "calibration.update")
        toggles.addWidget(self.interactive_adjustment_cb)
        toggles.addWidget(self.calibration_update_cb)
        toggles.addStretch(1)
        outer.addLayout(toggles)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Whitepoint: mode + colortemp / x,y fields.
        self.whitepoint_ctrl = QComboBox()
        self.whitepoint_ctrl.addItems(
            [
                lang.getstr("native"),
                lang.getstr("whitepoint.colortemp"),
                lang.getstr("whitepoint.xy"),
            ]
        )
        self.whitepoint_ctrl.currentIndexChanged.connect(self._whitepoint_changed)
        self.whitepoint_colortemp_ctrl = QSpinBox()
        self.whitepoint_colortemp_ctrl.setRange(1000, 15000)
        self.whitepoint_colortemp_ctrl.setSingleStep(50)
        self.whitepoint_colortemp_ctrl.setSuffix(" K")
        self.whitepoint_colortemp_ctrl.valueChanged.connect(self._whitepoint_changed)
        self.whitepoint_x_ctrl = QDoubleSpinBox()
        self.whitepoint_x_ctrl.setRange(-1.0, 1.0)
        self.whitepoint_x_ctrl.setDecimals(4)
        self.whitepoint_x_ctrl.setSingleStep(0.0001)
        self.whitepoint_x_ctrl.setPrefix("x ")
        self.whitepoint_x_ctrl.valueChanged.connect(self._whitepoint_changed)
        self.whitepoint_y_ctrl = QDoubleSpinBox()
        self.whitepoint_y_ctrl.setRange(-1.0, 1.0)
        self.whitepoint_y_ctrl.setDecimals(4)
        self.whitepoint_y_ctrl.setSingleStep(0.0001)
        self.whitepoint_y_ctrl.setPrefix("y ")
        self.whitepoint_y_ctrl.valueChanged.connect(self._whitepoint_changed)
        whitepoint_row = QHBoxLayout()
        whitepoint_row.addWidget(self.whitepoint_ctrl)
        whitepoint_row.addWidget(self.whitepoint_colortemp_ctrl)
        whitepoint_row.addWidget(self.whitepoint_x_ctrl)
        whitepoint_row.addWidget(self.whitepoint_y_ctrl)
        whitepoint_row.addStretch(1)
        form.addRow(lang.getstr("whitepoint"), self._wrap(whitepoint_row))

        # White level (luminance).
        self.luminance_ctrl = QComboBox()
        self.luminance_ctrl.addItems(
            [lang.getstr("as_measured"), lang.getstr("custom")]
        )
        self.luminance_ctrl.currentIndexChanged.connect(self._luminance_changed)
        self.luminance_textctrl = QDoubleSpinBox()
        self.luminance_textctrl.setRange(20.0, 100000.0)
        self.luminance_textctrl.setDecimals(2)
        self.luminance_textctrl.setSuffix(" cd/m²")
        self.luminance_textctrl.valueChanged.connect(self._luminance_changed)
        luminance_row = QHBoxLayout()
        luminance_row.addWidget(self.luminance_ctrl)
        luminance_row.addWidget(self.luminance_textctrl)
        luminance_row.addStretch(1)
        form.addRow(lang.getstr("calibration.luminance"), self._wrap(luminance_row))

        # Black level (black luminance).
        self.black_luminance_ctrl = QComboBox()
        self.black_luminance_ctrl.addItems(
            [lang.getstr("as_measured"), lang.getstr("custom")]
        )
        self.black_luminance_ctrl.currentIndexChanged.connect(
            self._black_luminance_changed
        )
        self.black_luminance_textctrl = QDoubleSpinBox()
        self.black_luminance_textctrl.setRange(0.0001, 10.0)
        self.black_luminance_textctrl.setDecimals(4)
        self.black_luminance_textctrl.setSuffix(" cd/m²")
        self.black_luminance_textctrl.valueChanged.connect(
            self._black_luminance_changed
        )
        black_luminance_row = QHBoxLayout()
        black_luminance_row.addWidget(self.black_luminance_ctrl)
        black_luminance_row.addWidget(self.black_luminance_textctrl)
        black_luminance_row.addStretch(1)
        form.addRow(
            lang.getstr("calibration.black_luminance"),
            self._wrap(black_luminance_row),
        )

        # Tone response curve.
        self.trc_ctrl = QComboBox()
        self.trc_ctrl.addItems(self._trc_labels())
        self.trc_ctrl.currentIndexChanged.connect(self._trc_changed)
        self.trc_textctrl = QLineEdit()
        self.trc_textctrl.setMaximumWidth(80)
        self.trc_textctrl.editingFinished.connect(self._trc_changed)
        self.trc_type_ctrl = QComboBox()
        self.trc_type_ctrl.addItems(
            [lang.getstr("trc.type.relative"), lang.getstr("trc.type.absolute")]
        )
        self.trc_type_ctrl.currentIndexChanged.connect(self._trc_changed)
        trc_row = QHBoxLayout()
        trc_row.addWidget(self.trc_ctrl)
        trc_row.addWidget(self.trc_textctrl)
        trc_row.addWidget(self.trc_type_ctrl)
        trc_row.addStretch(1)
        form.addRow(lang.getstr("trc"), self._wrap(trc_row))

        # Black output offset (0-100 %).
        self.black_output_offset_ctrl = QSlider(Qt.Horizontal)
        self.black_output_offset_ctrl.setRange(0, 100)
        self.black_output_offset_ctrl.valueChanged.connect(
            self._black_output_offset_changed
        )
        form.addRow(
            lang.getstr("calibration.black_output_offset"),
            self.black_output_offset_ctrl,
        )

        # Black point correction (0-100 %).
        self.black_point_correction_ctrl = QSlider(Qt.Horizontal)
        self.black_point_correction_ctrl.setRange(0, 100)
        self.black_point_correction_ctrl.valueChanged.connect(
            self._black_point_correction_changed
        )
        form.addRow(
            lang.getstr("calibration.black_point_correction"),
            self.black_point_correction_ctrl,
        )

        # Ambient light level adjustment.
        self.ambient_adjust_cb = QCheckBox(
            lang.getstr("calibration.ambient_viewcond_adjust")
        )
        self._add_check(
            self.ambient_adjust_cb, "calibration.ambient_viewcond_adjust"
        )
        self.ambient_adjust_textctrl = QDoubleSpinBox()
        self.ambient_adjust_textctrl.setRange(0.0, 999999.0)
        self.ambient_adjust_textctrl.setDecimals(2)
        self.ambient_adjust_textctrl.setSuffix(" Lux")
        self.ambient_adjust_textctrl.valueChanged.connect(self._ambient_lux_changed)
        ambient_row = QHBoxLayout()
        ambient_row.addWidget(self.ambient_adjust_cb)
        ambient_row.addWidget(self.ambient_adjust_textctrl)
        ambient_row.addStretch(1)
        form.addRow("", self._wrap(ambient_row))

        # Calibration quality / speed.
        self.calibration_quality_ctrl = QSlider(Qt.Horizontal)
        self.calibration_quality_ctrl.setRange(1, len(CALIBRATION_QUALITY_LEVELS))
        self.calibration_quality_ctrl.valueChanged.connect(
            self._calibration_quality_changed
        )
        self.calibration_quality_info = QLabel()
        quality_row = QHBoxLayout()
        quality_row.addWidget(self.calibration_quality_ctrl)
        quality_row.addWidget(self.calibration_quality_info)
        quality_row.addStretch(1)
        form.addRow(lang.getstr("calibration.speed"), self._wrap(quality_row))

        outer.addLayout(form)
        outer.addStretch(1)
        return panel

    def _build_profiling_tab(self) -> QWidget:
        """Build the Profiling settings panel."""
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.profile_type_ctrl = QComboBox()
        self._add_value_combo(self.profile_type_ctrl, "profile.type", PROFILE_TYPES)
        self.black_point_compensation_cb = QCheckBox(
            lang.getstr("black_point_compensation")
        )
        self._add_check(
            self.black_point_compensation_cb, "profile.black_point_compensation"
        )
        type_row = QHBoxLayout()
        type_row.addWidget(self.profile_type_ctrl)
        type_row.addWidget(self.black_point_compensation_cb)
        type_row.addStretch(1)
        form.addRow(lang.getstr("profile.type"), self._wrap(type_row))

        self.profile_quality_ctrl = QSlider(Qt.Horizontal)
        self.profile_quality_ctrl.setRange(1, len(PROFILE_QUALITY_LEVELS))
        self.profile_quality_ctrl.valueChanged.connect(self._profile_quality_changed)
        self.profile_quality_info = QLabel()
        quality_row = QHBoxLayout()
        quality_row.addWidget(self.profile_quality_ctrl)
        quality_row.addWidget(self.profile_quality_info)
        quality_row.addStretch(1)
        form.addRow(lang.getstr("profile.quality"), self._wrap(quality_row))

        self.profile_name_textctrl = QLineEdit()
        self.profile_name_textctrl.editingFinished.connect(self._profile_name_changed)
        form.addRow(lang.getstr("profile.name"), self.profile_name_textctrl)

        outer.addLayout(form)
        outer.addStretch(1)
        return panel

    def _build_lut3d_tab(self) -> QWidget:
        """Build the 3D LUT settings panel."""
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        self.lut3d_create_cb = QCheckBox(lang.getstr("3dlut.create_after_profiling"))
        self._add_check(self.lut3d_create_cb, "3dlut.create")
        outer.addWidget(self.lut3d_create_cb)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.lut3d_format_ctrl = QComboBox()
        self._add_value_combo(
            self.lut3d_format_ctrl, "3dlut.format", lut3d_format_items()
        )
        form.addRow(lang.getstr("3dlut.format"), self.lut3d_format_ctrl)

        self.lut3d_size_ctrl = QComboBox()
        self._add_value_combo(
            self.lut3d_size_ctrl, "3dlut.size", lut3d_size_items(), cast=int
        )
        form.addRow(lang.getstr("3dlut.size"), self.lut3d_size_ctrl)

        self.lut3d_bitdepth_input_ctrl = QComboBox()
        self._add_value_combo(
            self.lut3d_bitdepth_input_ctrl,
            "3dlut.bitdepth.input",
            lut3d_bitdepth_items(),
            cast=int,
        )
        form.addRow(lang.getstr("3dlut.bitdepth.input"), self.lut3d_bitdepth_input_ctrl)

        self.lut3d_bitdepth_output_ctrl = QComboBox()
        self._add_value_combo(
            self.lut3d_bitdepth_output_ctrl,
            "3dlut.bitdepth.output",
            lut3d_bitdepth_items(),
            cast=int,
        )
        form.addRow(
            lang.getstr("3dlut.bitdepth.output"), self.lut3d_bitdepth_output_ctrl
        )

        self.lut3d_rendering_intent_ctrl = QComboBox()
        self._add_value_combo(
            self.lut3d_rendering_intent_ctrl,
            "3dlut.rendering_intent",
            lut3d_rendering_intent_items(),
        )
        form.addRow(
            lang.getstr("rendering_intent"), self.lut3d_rendering_intent_ctrl
        )

        self.lut3d_apply_trc_cb = QCheckBox(
            f"{lang.getstr('apply')} {lang.getstr('trc')}"
        )
        self._add_check(self.lut3d_apply_trc_cb, "3dlut.apply_trc")
        form.addRow("", self.lut3d_apply_trc_cb)

        self.lut3d_apply_black_offset_cb = QCheckBox(
            lang.getstr("apply_black_output_offset")
        )
        self._add_check(self.lut3d_apply_black_offset_cb, "3dlut.apply_black_offset")
        form.addRow("", self.lut3d_apply_black_offset_cb)

        outer.addLayout(form)
        outer.addStretch(1)
        return panel

    def _build_button_bar(self) -> QWidget:
        """Build the calibrate / profile action-button row.

        The buttons stage a :class:`MeasurementAction` through :attr:`flow` and
        present the measurement area (see :meth:`begin_measurement`).
        """
        bar = QWidget()
        bar.setObjectName("buttonpanel")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 8, 16, 12)
        row.setSpacing(8)
        row.addStretch(1)

        self.calibrate_btn = QPushButton(lang.getstr("button.calibrate"))
        self.calibrate_btn.clicked.connect(self.calibrate_btn_handler)
        self.calibrate_and_profile_btn = QPushButton(
            lang.getstr("button.calibrate_and_profile")
        )
        self.calibrate_and_profile_btn.clicked.connect(
            self.calibrate_and_profile_btn_handler
        )
        self.profile_btn = QPushButton(lang.getstr("button.profile"))
        self.profile_btn.clicked.connect(self.profile_btn_handler)
        for button in (
            self.calibrate_btn,
            self.calibrate_and_profile_btn,
            self.profile_btn,
        ):
            button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            row.addWidget(button)
        return bar

    # -- small construction helpers ---------------------------------------

    @staticmethod
    def _wrap(inner: QHBoxLayout) -> QWidget:
        """Wrap a layout in a widget so it can be a ``QFormLayout`` field."""
        holder = QWidget()
        inner.setContentsMargins(0, 0, 0, 0)
        holder.setLayout(inner)
        return holder

    def _trc_labels(self) -> list[str]:
        """Return the localized TRC combo labels (``Gamma 2.2`` stays literal)."""
        return [
            item if item == "Gamma 2.2" else lang.getstr(item) for item in _TRC_ITEMS
        ]

    def _add_check(self, checkbox: QCheckBox, config_key: str) -> None:
        """Register a checkbox as an int (0/1) config binding."""
        self._value_checks[config_key] = checkbox
        checkbox.toggled.connect(
            lambda checked, k=config_key: self._check_handler(k, checked)
        )

    def _add_value_combo(
        self, combo: QComboBox, config_key: str, items: list, cast: type = str
    ) -> None:
        """Register a combo of ``(value, label)`` items as a config binding."""
        values = [value for value, _label in items]
        combo.addItems([label for _value, label in items])
        self._value_combos[config_key] = (combo, values)
        combo.currentIndexChanged.connect(
            lambda index, k=config_key, c=cast: self._value_combo_handler(k, index, c)
        )

    # -- population --------------------------------------------------------

    def update_controls(self) -> None:
        """Repopulate every control from the current worker/config state."""
        self._updating = True
        try:
            self.update_displays()
            self.update_comports()
            self.update_observers()
            self.update_calibration_controls()
            self.update_profile_controls()
            self.update_lut3d_controls()
        finally:
            self._updating = False

    def update_displays(self) -> None:
        """Populate the display selector from ``worker.displays``."""
        self.display_ctrl.clear()
        self.display_ctrl.addItems(display_items(self.worker.displays))
        self.display_ctrl.setEnabled(bool(self.worker.displays))
        if self.worker.displays:
            index = min(
                max(0, len(self.worker.displays) - 1),
                max(0, getcfg("display.number") - 1),
            )
            self.display_ctrl.setCurrentIndex(index)

    def update_comports(self) -> None:
        """Populate the instrument selector from ``worker.instruments``."""
        self.comport_ctrl.clear()
        self.comport_ctrl.addItems(instrument_items(self.worker.instruments))
        self.comport_ctrl.setEnabled(bool(self.worker.instruments))
        if self.worker.instruments:
            index = min(
                max(0, len(self.worker.instruments) - 1),
                max(0, int(getcfg("comport.number")) - 1),
            )
            self.comport_ctrl.setCurrentIndex(index)

    def update_observers(self) -> None:
        """Populate the observer selector from the Argyll-supported observers."""
        self._observers = observer_items()
        keys = list(self._observers)
        self.observer_ctrl.clear()
        self.observer_ctrl.addItems([self._observers[k] for k in keys])
        current = getcfg("observer")
        if current in keys:
            self.observer_ctrl.setCurrentIndex(keys.index(current))

    def update_calibration_controls(self) -> None:
        """Push stored calibration config into the Calibration tab controls."""
        self._sync_check("calibration.interactive_display_adjustment")
        self._sync_check("calibration.update")

        self.whitepoint_colortemp_ctrl.setValue(
            int(_as_float(getcfg("whitepoint.colortemp")) or 6500)
        )
        self.whitepoint_x_ctrl.setValue(round(getcfg("whitepoint.x"), 4))
        self.whitepoint_y_ctrl.setValue(round(getcfg("whitepoint.y"), 4))
        self.whitepoint_ctrl.setCurrentIndex(self._whitepoint_mode_from_config())
        self._apply_whitepoint_mode()

        self.luminance_ctrl.setCurrentIndex(
            1 if getcfg("calibration.luminance", False) else 0
        )
        self.luminance_textctrl.setValue(
            _as_float(getcfg("calibration.luminance")) or 120.0
        )
        self.black_luminance_ctrl.setCurrentIndex(
            1 if getcfg("calibration.black_luminance", False) else 0
        )
        self.black_luminance_textctrl.setValue(
            _as_float(getcfg("calibration.black_luminance")) or 0.0001
        )
        self._apply_luminance_mode()

        row, text, type_row = trc_selection_from_config(
            getcfg("trc"),
            getcfg("trc.type"),
            getcfg("calibration.black_output_offset"),
        )
        self.trc_ctrl.setCurrentIndex(row)
        self.trc_textctrl.setText(text)
        self.trc_type_ctrl.setCurrentIndex(type_row)
        self._apply_trc_mode()

        self.black_output_offset_ctrl.setValue(
            round(_as_float(getcfg("calibration.black_output_offset")) * 100)
        )
        self.black_point_correction_ctrl.setValue(
            round(_as_float(getcfg("calibration.black_point_correction")) * 100)
        )

        self._sync_check("calibration.ambient_viewcond_adjust")
        self.ambient_adjust_textctrl.setValue(
            _as_float(getcfg("calibration.ambient_viewcond_adjust.lux")) or 0.0
        )

        quality = calibration_quality_to_slider(getcfg("calibration.quality"))
        self.calibration_quality_ctrl.setValue(quality)
        self._update_calibration_quality_label()

    def update_profile_controls(self) -> None:
        """Push stored profile config into the Profiling tab controls."""
        self._sync_value_combo("profile.type", cast=str)
        self._sync_check("profile.black_point_compensation")
        self.profile_quality_ctrl.setValue(
            profile_quality_to_slider(getcfg("profile.quality"))
        )
        self._update_profile_quality_label()
        self.profile_name_textctrl.setText(str(getcfg("profile.name")))

    def update_lut3d_controls(self) -> None:
        """Push stored 3D LUT config into the 3D LUT tab controls."""
        self._sync_check("3dlut.create")
        self._sync_value_combo("3dlut.format", cast=str)
        self._sync_value_combo("3dlut.size", cast=int)
        self._sync_value_combo("3dlut.bitdepth.input", cast=int)
        self._sync_value_combo("3dlut.bitdepth.output", cast=int)
        self._sync_value_combo("3dlut.rendering_intent", cast=str)
        self._sync_check("3dlut.apply_trc")
        self._sync_check("3dlut.apply_black_offset")

    def _sync_check(self, config_key: str) -> None:
        """Set a bound checkbox from the stored int config value."""
        self._value_checks[config_key].setChecked(bool(int(getcfg(config_key))))

    def _sync_value_combo(self, config_key: str, cast: type = str) -> None:
        """Select the bound combo row matching the stored config value."""
        combo, values = self._value_combos[config_key]
        current = getcfg(config_key)
        with contextlib.suppress(TypeError, ValueError):
            current = cast(current)
        if current in values:
            combo.setCurrentIndex(values.index(current))

    # -- Display & Instrument handlers ------------------------------------

    def display_ctrl_handler(self, index: int) -> None:
        """Persist the selected display number.

        Args:
            index (int): The newly selected combo index.
        """
        if self._updating or index < 0:
            return
        setcfg("display.number", index + 1)

    def comport_ctrl_handler(self, index: int) -> None:
        """Persist the selected instrument (comport) number.

        Args:
            index (int): The newly selected combo index.
        """
        if self._updating or index < 0:
            return
        setcfg("comport.number", index + 1)

    def observer_ctrl_handler(self, index: int) -> None:
        """Persist the selected standard observer.

        Args:
            index (int): The newly selected combo index.
        """
        if self._updating or index < 0:
            return
        keys = list(self._observers)
        if index < len(keys):
            setcfg("observer", keys[index])

    # -- generic binder handlers ------------------------------------------

    def _check_handler(self, config_key: str, checked: bool) -> None:
        """Persist a bound checkbox as an int (0/1)."""
        if self._updating:
            return
        setcfg(config_key, 1 if checked else 0)

    def _value_combo_handler(self, config_key: str, index: int, cast: type) -> None:
        """Persist a bound value-combo selection."""
        if self._updating or index < 0:
            return
        _combo, values = self._value_combos[config_key]
        if index < len(values):
            setcfg(config_key, cast(values[index]))

    # -- Calibration handlers ---------------------------------------------

    def _whitepoint_mode_from_config(self) -> int:
        """Return the whitepoint combo row implied by stored config (0/1/2)."""
        if getcfg("whitepoint.colortemp", False):
            return 1
        if getcfg("whitepoint.x", False) and getcfg("whitepoint.y", False):
            return 2
        return 0

    def _apply_whitepoint_mode(self) -> None:
        """Enable only the whitepoint fields relevant to the current mode."""
        mode = self.whitepoint_ctrl.currentIndex()
        self.whitepoint_colortemp_ctrl.setVisible(mode == 1)
        self.whitepoint_x_ctrl.setVisible(mode == 2)
        self.whitepoint_y_ctrl.setVisible(mode == 2)

    def _whitepoint_changed(self, *_args: object) -> None:
        """Persist the whitepoint mode + value to config."""
        self._apply_whitepoint_mode()
        if self._updating:
            return
        mode = self.whitepoint_ctrl.currentIndex()
        if mode == 1:
            setcfg("whitepoint.colortemp", self.whitepoint_colortemp_ctrl.value())
            setcfg("whitepoint.x", None)
            setcfg("whitepoint.y", None)
        elif mode == 2:
            setcfg("whitepoint.colortemp", None)
            setcfg("whitepoint.x", round(self.whitepoint_x_ctrl.value(), 4))
            setcfg("whitepoint.y", round(self.whitepoint_y_ctrl.value(), 4))
        else:
            setcfg("whitepoint.colortemp", None)
            setcfg("whitepoint.x", None)
            setcfg("whitepoint.y", None)

    def _apply_luminance_mode(self) -> None:
        """Show the luminance / black-luminance value fields only when custom."""
        self.luminance_textctrl.setVisible(self.luminance_ctrl.currentIndex() == 1)
        self.black_luminance_textctrl.setVisible(
            self.black_luminance_ctrl.currentIndex() == 1
        )

    def _luminance_changed(self, *_args: object) -> None:
        """Persist the white-level (luminance) mode + value."""
        self._apply_luminance_mode()
        if self._updating:
            return
        if self.luminance_ctrl.currentIndex() == 1:
            setcfg("calibration.luminance", self.luminance_textctrl.value())
        else:
            setcfg("calibration.luminance", None)

    def _black_luminance_changed(self, *_args: object) -> None:
        """Persist the black-level (black luminance) mode + value."""
        self._apply_luminance_mode()
        if self._updating:
            return
        if self.black_luminance_ctrl.currentIndex() == 1:
            setcfg("calibration.black_luminance", self.black_luminance_textctrl.value())
        else:
            setcfg("calibration.black_luminance", None)

    def _apply_trc_mode(self) -> None:
        """Enable the gamma text / type fields only for text-driven TRC rows."""
        is_text = self.trc_ctrl.currentIndex() in _TRC_TEXT_ROWS
        self.trc_textctrl.setVisible(is_text)
        self.trc_type_ctrl.setVisible(is_text)

    def _trc_changed(self, *_args: object) -> None:
        """Persist the tone-response-curve selection to ``trc`` / ``trc.type``."""
        self._apply_trc_mode()
        if self._updating:
            return
        index = self.trc_ctrl.currentIndex()
        setcfg("trc", trc_value_from_selection(index, self.trc_textctrl.text()))
        if index in _TRC_FIXED:
            setcfg("trc.type", "g")
        else:
            setcfg("trc.type", "G" if self.trc_type_ctrl.currentIndex() == 1 else "g")

    def _black_output_offset_changed(self, value: int) -> None:
        """Persist the black output offset (slider 0-100 -> 0.0-1.0)."""
        if self._updating:
            return
        setcfg("calibration.black_output_offset", value / 100.0)

    def _black_point_correction_changed(self, value: int) -> None:
        """Persist the black point correction (slider 0-100 -> 0.0-1.0)."""
        if self._updating:
            return
        setcfg("calibration.black_point_correction", value / 100.0)

    def _ambient_lux_changed(self, value: float) -> None:
        """Persist the ambient light level (Lux)."""
        if self._updating:
            return
        setcfg("calibration.ambient_viewcond_adjust.lux", value)

    def _calibration_quality_changed(self, value: int) -> None:
        """Persist the calibration quality and refresh its label."""
        self._update_calibration_quality_label()
        if self._updating:
            return
        setcfg("calibration.quality", slider_to_calibration_quality(value))

    def _update_calibration_quality_label(self) -> None:
        """Set the calibration speed label from the current slider value."""
        quality = slider_to_calibration_quality(self.calibration_quality_ctrl.value())
        self.calibration_quality_info.setText(
            lang.getstr(f"calibration.speed.{_CALIBRATION_SPEED_LABELS[quality]}")
        )

    # -- Profiling handlers -----------------------------------------------

    def _profile_quality_changed(self, value: int) -> None:
        """Persist the profile quality and refresh its label."""
        self._update_profile_quality_label()
        if self._updating:
            return
        setcfg("profile.quality", slider_to_profile_quality(value))

    def _update_profile_quality_label(self) -> None:
        """Set the profile quality label from the current slider value."""
        quality = slider_to_profile_quality(self.profile_quality_ctrl.value())
        self.profile_quality_info.setText(
            lang.getstr(f"calibration.quality.{_PROFILE_QUALITY_LABELS[quality]}")
        )

    def _profile_name_changed(self) -> None:
        """Persist the profile name template."""
        if self._updating:
            return
        setcfg("profile.name", self.profile_name_textctrl.text())

    # -- tab switching -----------------------------------------------------

    def _select_tab(self, key: str) -> None:
        """Show the settings panel for ``key`` and check its tab button.

        Args:
            key (str): The tab identifier (see :data:`_TABS`).
        """
        self.stack.setCurrentWidget(self._panels[key])
        button = self._tab_buttons[key]
        if not button.isChecked():
            button.setChecked(True)

    # -- measurement actions (Stage 4) ------------------------------------

    def calibrate_btn_handler(self) -> None:
        """Stage a calibration run and present the measurement area."""
        self.begin_measurement(MeasurementAction.CALIBRATE)

    def calibrate_and_profile_btn_handler(self) -> None:
        """Stage a combined calibrate + characterize run."""
        self.begin_measurement(MeasurementAction.CALIBRATE_AND_PROFILE)

    def profile_btn_handler(self) -> None:
        """Stage a characterization (profiling) run."""
        self.begin_measurement(MeasurementAction.PROFILE)

    def begin_measurement(
        self, action: MeasurementAction, *, wrapup: bool = True
    ) -> None:
        """Qt port of ``MainFrame.setup_measurement``.

        Persists config, stages the driver for ``action`` through :attr:`flow`
        and dispatches on the toolkit-neutral presentation decision:

        * :attr:`~PresentationMode.CALL_PENDING` — run the driver directly
          (virtual display / dry run),
        * :attr:`~PresentationMode.SHOW_FRAME` — show the in-process measure
          frame and route its Measure button to the driver,
        * :attr:`~PresentationMode.SUBPROCESS` — run the measure frame as a
          separate process and act on its exit code.

        The pattern-generator setup dialogs the wx path runs first (Prisma /
        madTPG / Resolve) are Pile-2 glue rebuilt in a later slice.

        Args:
            action (MeasurementAction): Which workflow to run.
            wrapup (bool): Whether the caller should wrap up the worker before
                presenting (passed through on the plan).
        """
        writecfg()
        plan = self.flow.plan_measurement(
            self._drive_measurement,
            action,
            use_patternwindow=getattr(self.worker, "_use_patternwindow", False),
            wrapup=wrapup,
        )
        if plan.mode is PresentationMode.CALL_PENDING:
            self.call_pending_function()
        elif plan.mode is PresentationMode.SHOW_FRAME:
            self._present_measureframe()
        else:
            self._start_measureframe_subprocess()

    def call_pending_function(self) -> None:
        """Qt port of ``MainFrame.call_pending_function``.

        Hides the measure frame (or blanks it under the pattern window), then
        runs the staged driver after a short delay so the display can settle.
        """
        writecfg()
        if self.measureframe is not None and self.measureframe.isVisible():
            if getattr(self.worker, "_use_patternwindow", False):
                self.measureframe.show_controls(False)
            else:
                self.measureframe.hide()
        self._defer(self._run_pending_function)

    def _defer(self, callback: object) -> None:
        """Run ``callback`` after :attr:`_pending_delay_ms` (overridable in tests)."""
        QTimer.singleShot(self._pending_delay_ms, callback)

    def _run_pending_function(self) -> None:
        """Pop and invoke the staged measurement driver."""
        func, args, kwargs = self.flow.take_pending_function()
        if func is not None:
            func(*args, **kwargs)

    def _present_measureframe(self) -> None:
        """Show the measure frame and route its Measure button to the flow."""
        self._ensure_measureframe()
        self.measureframe.show_controls(True)
        self.measureframe.show()
        self.measureframe.raise_()

    def _ensure_measureframe(self) -> None:
        """Create the child measure frame once, wiring its Measure signal."""
        if self.measureframe is None:
            self.measureframe = MeasureFrame(self)
            self.measureframe.measure_requested.connect(self.call_pending_function)

    def _start_measureframe_subprocess(self) -> None:
        """Run the measure frame as a subprocess on a worker thread."""
        args = build_measureframe_command()
        env = os.environ.copy()
        self._measureframe_thread = _MeasureframeSubprocessThread(args, env, self)
        self._measureframe_thread.finished_with_result.connect(
            self._on_measureframe_finished
        )
        self._measureframe_thread.start()

    def _on_measureframe_finished(self, returncode: int, stderr: str) -> None:
        """Qt port of ``MainFrame.measureframe_consumer``.

        Args:
            returncode (int): The measure-frame subprocess exit code.
            stderr (str): The subprocess stderr (only used on failure).
        """
        result = interpret_measureframe_result(returncode, stderr)
        if result.config_changed:
            # The subprocess may have rewritten geometry / display config.
            config.initcfg()
            self.update_controls()
        if result.should_call_pending:
            self.call_pending_function()
            return
        self._restore_after_measurement()
        if result.error_message:
            QMessageBox.critical(self, APPNAME, result.error_message)

    def _drive_measurement(self, action: MeasurementAction) -> None:
        """Run the staged Argyll measurement for ``action``.

        Emits :attr:`measurement_requested` and restores the main window. The
        worker-driven Argyll execution (the progress dialog and interactive
        display-adjustment window that ``worker.Worker.start`` drives in wx) is a
        wx-heavy path rebuilt in a later slice; exposing the committed run as a
        signal lets that layer connect without this window depending on it.

        Args:
            action (MeasurementAction): The workflow the user committed to.
        """
        self._restore_after_measurement()
        self.measurement_requested.emit(action)

    def _restore_after_measurement(self) -> None:
        """Re-show the main window after the measurement area closes."""
        self.show()
        self.raise_()

    # -- misc --------------------------------------------------------------

    def setup_language(self) -> None:
        """Apply localized text. Labels are set at build time; kept for parity.

        The window is rebuilt (not retranslated live) on language change, so this
        is a no-op hook matching the other Qt windows' ``setup_language``.
        """

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        """Restore the saved position the first time the window is shown.

        Geometry restoration is done here (not in ``__init__``) so it applies
        after the window has a native handle, and only once so a later show
        event never snaps a user-moved window back.

        Args:
            event (QShowEvent): The Qt show event.
        """
        super().showEvent(event)
        if not self._position_restored:
            self._position_restored = True
            self.restore_position()


def main() -> int:
    """Run the Qt main window.

    Returns:
        int: The Qt application exit code.
    """
    config.initcfg()
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    window = MainWindow()
    app.top_window = window
    window.show()
    window.listen()
    app.process_argv()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
