"""Testchart editor — Qt port (Stage 1: core editor).

Qt equivalent of :mod:`DisplayCAL.wx_testchart_editor` (the ``testchart-editor``
tool). It builds and edits Argyll TI1 test charts: a grid of RGB patches plus
the ``targen`` parameter controls that drive their generation (white / black /
single-channel / gray / multi-dimensional / full-spread patch counts, the
point-distribution algorithm and its adaption / angle / gamma / neutral-axis and
dark-region emphasis).

Generation runs Argyll ``targen`` via :meth:`DisplayCAL.worker.Worker.prepare_targen`
(entirely config-driven and binding-agnostic) on a :class:`QThread`, reading the
resulting ``temp.ti1`` back as a :class:`~DisplayCAL.cgats.CGATS` object. Loading
reads a ``.ti1`` / ``.ti3`` / ``.cgats`` / ``.txt`` (or an ICC's embedded chart)
and reconstructs the control values from the chart's keywords, on a background
thread. Charts save as ``.ti1`` (``bytes(cgats)``).

This is **Stage 1** of the port. Deliberately deferred to later stages (and to
the not-yet-ported main window for its parent integration): multi-format
**export**, the **3D view/export**, **saturation sweeps**, **TI3 / CSV / image**
patch import, the 23-way **patch reordering**, and the **precondition-profile /
CIE filter** controls. The per-parameter reconstruction of hand-authored charts
that carry no ``targen`` keywords is also approximate for now.
"""

from __future__ import annotations

import math
import os
import sys
from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import Qt, QThread, Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import argyll_rgb2xyz, config
from DisplayCAL import localization as lang
from DisplayCAL.argyll import check_set_argyll_bin
from DisplayCAL.argyll_cgats import ti3_to_ti1, verify_cgats
from DisplayCAL.cgats import CGATS, CGATSError, CGATSKeyError
from DisplayCAL.config import (
    DEFAULTS,
    get_data_path,
    get_total_patches,
    get_verified_path,
    getcfg,
    setcfg,
)
from DisplayCAL.icc_profile import ICCProfile
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.file_drop import FileDropTarget
from DisplayCAL.util_dict import swap_dict_keys_values
from DisplayCAL.util_os import waccess
from DisplayCAL.worker import Error, Worker, check_file_isfile

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent

#: File suffixes accepted for loading (drag-and-drop / open).
LOAD_SUFFIXES = (".ti1", ".ti3", ".cgats", ".txt", ".icc", ".icm")

#: Fullspread-algorithm TI1 keyword → targen algo code, for load reconstruction.
FULLSPREAD_KEYWORD_TO_ALGO = {
    "ERROR_OPTIMISED_PATCHES": "",
    "IFP_PATCHES": "t",
    "INC_FAR_PATCHES": "t",
    "OFPS_PATCHES": "",
    "RANDOM_DEVICE_PATCHES": "r",
    "RANDOM_PATCHES": "r",
    "RANDOM_PERCEPTUAL_PATCHES": "R",
    "SIMPLEX_DEVICE_PATCHES": "i",
    "SIMPLEX_PERCEPTUAL_PATCHES": "I",
    "SPACEFILING_RANDOM_PATCHES": "q",
    "SPACEFILLING_RANDOM_PATCHES": "q",
}


class _GenerateThread(QThread):
    """Run testchart generation off the GUI thread.

    Args:
        window (TestchartEditorWindow): The owning window (provides ``tc_create``).
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with the generated :class:`CGATS`, or an ``Exception`` on failure.
    done = Signal(object)

    def __init__(
        self, window: TestchartEditorWindow, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._window = window

    def run(self) -> None:
        try:
            result = self._window.tc_create()
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            result = exception
        self.done.emit(result)


class _LoadThread(QThread):
    """Read and interpret a testchart file off the GUI thread.

    Args:
        window (TestchartEditorWindow): The owning window (provides ``tc_load_worker``).
        path (str): The chart file to read.
        parent (QWidget | None): Optional Qt parent.
    """

    #: Emitted with the reconstructed parameter tuple, or an ``Exception``.
    done = Signal(object)

    def __init__(
        self, window: TestchartEditorWindow, path: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._path = path

    def run(self) -> None:
        try:
            result = self._window.tc_load_worker(self._path)
        except Exception as exception:  # noqa: BLE001  (report on GUI thread)
            result = exception
        self.done.emit(result)


class TestchartEditorWindow(BaseWindow):
    """Standalone testchart editor window (Stage 1 core)."""

    #: Grid columns holding editable device values.
    _RGB_COLUMNS = ("R %", "G %", "B %")

    def __init__(self) -> None:
        super().__init__(
            name="tcgen",
            title=lang.getstr("testchart.edit"),
            icon_name=f"{APPNAME}-testchart-editor".lower(),
        )
        self.worker = Worker()
        self.worker.set_argyll_version("targen")
        self.argyll_version = self.worker.argyll_version
        self.cfg = "testchart.file"
        self.ti1: CGATS | None = None
        self.tc_amount = 0
        self._loading = False
        self._gen_thread: _GenerateThread | None = None
        self._load_thread: _LoadThread | None = None

        self.tc_algos_ab = {
            "": lang.getstr("tc.ofp"),
            "t": lang.getstr("tc.t"),
            "r": lang.getstr("tc.r"),
            "R": lang.getstr("tc.R"),
            "q": lang.getstr("tc.q"),
            "i": lang.getstr("tc.i"),
            "I": lang.getstr("tc.I"),
        }
        if self.argyll_version >= [1, 1, 0]:
            self.tc_algos_ab["Q"] = lang.getstr("tc.Q")
        self.tc_algos_ba = swap_dict_keys_values(self.tc_algos_ab)

        self._build_ui()

        self.droptarget = FileDropTarget(
            drophandlers=dict.fromkeys(LOAD_SUFFIXES, self.load_file), parent=self
        )
        self.droptarget.install_on(self)
        self.init_menubar()
        self.resize(760, 640)

        self.tc_update_controls()
        self.tc_check()

    # -- construction ------------------------------------------------------

    def _build_ui(self) -> None:
        """Build the parameter controls, buttons and patch grid."""
        central = QWidget(self)
        root = QVBoxLayout(central)

        params = QGridLayout()
        params.setHorizontalSpacing(8)
        root.addLayout(params)
        row = 0

        self.tc_white_patches = self._spin(0, 9999)
        params.addWidget(QLabel(lang.getstr("tc.white")), row, 0)
        params.addWidget(self.tc_white_patches, row, 1)
        self.tc_single_channel_patches = self._spin(0, 256)
        params.addWidget(QLabel(lang.getstr("tc.single")), row, 2)
        single_cell = QHBoxLayout()
        single_cell.addWidget(self.tc_single_channel_patches)
        single_cell.addWidget(QLabel(lang.getstr("tc.single.perchannel")))
        single_cell.addStretch(1)
        params.addLayout(single_cell, row, 3)
        row += 1

        self.tc_black_patches: QSpinBox | None = None
        if self.argyll_version >= [1, 6]:
            self.tc_black_patches = self._spin(0, 9999)
            params.addWidget(QLabel(lang.getstr("tc.black")), row, 0)
            params.addWidget(self.tc_black_patches, row, 1)
        self.tc_gray_patches = self._spin(0, 256)
        params.addWidget(QLabel(lang.getstr("tc.gray")), row, 2)
        params.addWidget(self.tc_gray_patches, row, 3)
        row += 1

        self.tc_multi_steps = self._spin(0, 21)
        params.addWidget(QLabel(lang.getstr("tc.multidim")), row, 0)
        multi_cell = QHBoxLayout()
        multi_cell.addWidget(self.tc_multi_steps)
        self.tc_multi_bcc_cb: QCheckBox | None = None
        if self.argyll_version >= [1, 6, 0]:
            self.tc_multi_bcc_cb = QCheckBox(lang.getstr("centered"))
            self.tc_multi_bcc_cb.toggled.connect(self._on_multi_bcc)
            multi_cell.addWidget(self.tc_multi_bcc_cb)
        self.tc_multi_patches = QLabel("")
        multi_cell.addWidget(self.tc_multi_patches)
        multi_cell.addStretch(1)
        params.addLayout(multi_cell, row, 1, 1, 3)
        row += 1

        self.tc_fullspread_patches = self._spin(0, 9999)
        params.addWidget(QLabel(lang.getstr("tc.fullspread")), row, 0)
        params.addWidget(self.tc_fullspread_patches, row, 1)
        algos = sorted(self.tc_algos_ab.values())
        self.tc_algo = QComboBox()
        self.tc_algo.addItems(algos)
        self.tc_algo.currentIndexChanged.connect(self._on_algo)
        params.addWidget(QLabel(lang.getstr("tc.algo")), row, 2)
        params.addWidget(self.tc_algo, row, 3)
        row += 1

        self.tc_adaption_slider, self.tc_adaption_intctrl = self._slider_spin(
            0, 100, self._on_adaption
        )
        params.addWidget(QLabel(lang.getstr("tc.adaption")), row, 0)
        params.addLayout(
            self._pair_layout(self.tc_adaption_slider, self.tc_adaption_intctrl, "%"),
            row,
            1,
            1,
            3,
        )
        row += 1

        self.tc_angle_slider, self.tc_angle_intctrl = self._slider_spin(
            0, 5000, self._on_angle
        )
        params.addWidget(QLabel(lang.getstr("tc.angle")), row, 0)
        params.addLayout(
            self._pair_layout(self.tc_angle_slider, self.tc_angle_intctrl), row, 1, 1, 3
        )
        row += 1

        self.tc_gamma_floatctrl = QDoubleSpinBox()
        self.tc_gamma_floatctrl.setRange(0.0, 9.9)
        self.tc_gamma_floatctrl.setSingleStep(0.05)
        self.tc_gamma_floatctrl.setDecimals(2)
        self.tc_gamma_floatctrl.valueChanged.connect(self._save_and_check)
        params.addWidget(QLabel(lang.getstr("trc.gamma")), row, 0)
        params.addWidget(self.tc_gamma_floatctrl, row, 1)
        row += 1

        self.tc_neutral_axis_emphasis_slider: QSlider | None = None
        self.tc_neutral_axis_emphasis_intctrl: QSpinBox | None = None
        if self.argyll_version >= [1, 3, 3]:
            (
                self.tc_neutral_axis_emphasis_slider,
                self.tc_neutral_axis_emphasis_intctrl,
            ) = self._slider_spin(0, 100, self._on_neutral_axis_emphasis)
            params.addWidget(
                QLabel(lang.getstr("tc.neutral_axis_emphasis")), row, 0
            )
            params.addLayout(
                self._pair_layout(
                    self.tc_neutral_axis_emphasis_slider,
                    self.tc_neutral_axis_emphasis_intctrl,
                    "%",
                ),
                row,
                1,
                1,
                3,
            )
            row += 1

        self.tc_dark_emphasis_slider: QSlider | None = None
        self.tc_dark_emphasis_intctrl: QSpinBox | None = None
        if self.argyll_version >= [1, 6, 2]:
            (
                self.tc_dark_emphasis_slider,
                self.tc_dark_emphasis_intctrl,
            ) = self._slider_spin(0, 100, self._on_dark_emphasis)
            params.addWidget(QLabel(lang.getstr("tc.dark_emphasis")), row, 0)
            params.addLayout(
                self._pair_layout(
                    self.tc_dark_emphasis_slider, self.tc_dark_emphasis_intctrl, "%"
                ),
                row,
                1,
                1,
                3,
            )
            row += 1

        # Patch-count spinners share one plain handler (recount + persist).
        for spin in (
            self.tc_white_patches,
            self.tc_single_channel_patches,
            self.tc_gray_patches,
            self.tc_multi_steps,
            self.tc_fullspread_patches,
        ):
            spin.valueChanged.connect(self._on_patch_count)
        if self.tc_black_patches is not None:
            self.tc_black_patches.valueChanged.connect(self._on_patch_count)

        # Buttons.
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.preview_btn = QPushButton(lang.getstr("testchart.create"))
        self.preview_btn.clicked.connect(self.tc_generate)
        self.save_btn = QPushButton(lang.getstr("save"))
        self.save_btn.clicked.connect(self.tc_save)
        self.save_as_btn = QPushButton(lang.getstr("save_as"))
        self.save_as_btn.clicked.connect(lambda: self.tc_save_as())
        self.clear_btn = QPushButton(lang.getstr("testchart.discard"))
        self.clear_btn.clicked.connect(self.tc_clear)
        for button in (
            self.preview_btn,
            self.save_btn,
            self.save_as_btn,
            self.clear_btn,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        root.addLayout(buttons)

        # Grid.
        self.grid = QTableWidget(0, len(self._RGB_COLUMNS) + 1)
        self.grid.setHorizontalHeaderLabels([*self._RGB_COLUMNS, ""])
        self.grid.verticalHeader().setDefaultAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.grid.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.grid.setShowGrid(False)
        header = self.grid.horizontalHeader()
        for col in range(len(self._RGB_COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.Stretch)
        header.setSectionResizeMode(len(self._RGB_COLUMNS), QHeaderView.Fixed)
        self.grid.setColumnWidth(len(self._RGB_COLUMNS), 44)
        self.grid.itemChanged.connect(self._on_cell_changed)
        self.grid.itemSelectionChanged.connect(self.tc_set_default_status)
        root.addWidget(self.grid, 1)

        self.setCentralWidget(central)
        self.setStatusBar(self.statusBar())

    def _spin(self, minimum: int, maximum: int) -> QSpinBox:
        """Return a range-bounded integer spin box.

        Args:
            minimum (int): Minimum value.
            maximum (int): Maximum value.

        Returns:
            QSpinBox: The configured spin box.
        """
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setAlignment(Qt.AlignRight)
        return spin

    def _slider_spin(
        self, minimum: int, maximum: int, on_change: Callable[[], None]
    ) -> tuple[QSlider, QSpinBox]:
        """Return a linked (slider, spin) pair sharing a value range.

        Args:
            minimum (int): Minimum value.
            maximum (int): Maximum value.
            on_change (Callable): Slot invoked (with no useful arg) on any change.

        Returns:
            tuple[QSlider, QSpinBox]: The linked controls.
        """
        slider = QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setAlignment(Qt.AlignRight)
        slider.valueChanged.connect(
            lambda v: self._sync_pair(slider, spin, v, on_change)
        )
        spin.valueChanged.connect(
            lambda v: self._sync_pair(spin, slider, v, on_change)
        )
        return slider, spin

    def _sync_pair(
        self,
        source: QWidget,
        target: QWidget,
        value: int,
        on_change: Callable[[], None],
    ) -> None:
        """Mirror ``value`` from ``source`` onto ``target`` and fire ``on_change``.

        Args:
            source (QWidget): The control that changed.
            target (QWidget): The paired control to update.
            value (int): The new value.
            on_change (Callable): Slot to invoke after syncing.
        """
        if target.value() != value:
            target.blockSignals(True)
            target.setValue(value)
            target.blockSignals(False)
        if not self._loading:
            on_change()

    @staticmethod
    def _pair_layout(slider: QSlider, spin: QSpinBox, suffix: str = "") -> QHBoxLayout:
        """Return a horizontal layout holding a slider, spin and optional suffix.

        Args:
            slider (QSlider): The slider.
            spin (QSpinBox): The spin box.
            suffix (str): Optional trailing label (e.g. ``"%"``).

        Returns:
            QHBoxLayout: The assembled layout.
        """
        layout = QHBoxLayout()
        layout.addWidget(slider, 1)
        layout.addWidget(spin)
        if suffix:
            layout.addWidget(QLabel(suffix))
        return layout

    # -- config sync -------------------------------------------------------

    def tc_update_controls(self) -> None:
        """Load every control's value from the current configuration."""
        self._loading = True
        try:
            self.tc_algo.setCurrentText(
                self.tc_algos_ab.get(
                    getcfg("tc_algo"), self.tc_algos_ab.get(DEFAULTS["tc_algo"])
                )
            )
            self.tc_white_patches.setValue(getcfg("tc_white_patches"))
            if self.tc_black_patches is not None:
                self.tc_black_patches.setValue(getcfg("tc_black_patches"))
            self.tc_single_channel_patches.setValue(
                getcfg("tc_single_channel_patches")
            )
            self.tc_gray_patches.setValue(getcfg("tc_gray_patches"))
            if getcfg("tc_multi_bcc_steps"):
                setcfg("tc_multi_bcc", 1)
                self.tc_multi_steps.setValue(getcfg("tc_multi_bcc_steps"))
            else:
                setcfg("tc_multi_bcc", 0)
                self.tc_multi_steps.setValue(getcfg("tc_multi_steps"))
            if self.tc_multi_bcc_cb is not None:
                self.tc_multi_bcc_cb.setChecked(bool(getcfg("tc_multi_bcc")))
            self.tc_fullspread_patches.setValue(getcfg("tc_fullspread_patches"))
            self.tc_angle_intctrl.setValue(int(getcfg("tc_angle") * 10000))
            self.tc_adaption_intctrl.setValue(int(getcfg("tc_adaption") * 100))
            self.tc_gamma_floatctrl.setValue(getcfg("tc_gamma"))
            if self.tc_neutral_axis_emphasis_intctrl is not None:
                self.tc_neutral_axis_emphasis_intctrl.setValue(
                    int(getcfg("tc_neutral_axis_emphasis") * 100)
                )
            if self.tc_dark_emphasis_intctrl is not None:
                self.tc_dark_emphasis_intctrl.setValue(
                    int(getcfg("tc_dark_emphasis") * 100)
                )
        finally:
            self._loading = False
        self._update_multi_patches_label()
        self._update_enabled_states()

    def tc_save_cfg(self) -> None:
        """Persist the core control values to configuration."""
        setcfg("tc_white_patches", self.tc_white_patches.value())
        if self.tc_black_patches is not None:
            setcfg("tc_black_patches", self.tc_black_patches.value())
        setcfg("tc_single_channel_patches", self.tc_single_channel_patches.value())
        setcfg("tc_gray_patches", self.tc_gray_patches.value())
        if self.tc_multi_bcc_cb is not None and self.tc_multi_bcc_cb.isChecked():
            setcfg("tc_multi_bcc", 1)
            setcfg("tc_multi_bcc_steps", self.tc_multi_steps.value())
            setcfg("tc_multi_steps", 0)
        else:
            setcfg("tc_multi_bcc", 0)
            setcfg("tc_multi_bcc_steps", 0)
            setcfg("tc_multi_steps", self.tc_multi_steps.value())
        setcfg("tc_fullspread_patches", self.tc_fullspread_patches.value())
        tc_algo = self.tc_algos_ba[self.tc_algo.currentText()]
        setcfg("tc_algo", tc_algo)
        setcfg("tc_angle", self.tc_angle_intctrl.value() / 10000.0)
        setcfg("tc_adaption", self.tc_adaption_intctrl.value() / 100.0)
        setcfg("tc_gamma", self.tc_gamma_floatctrl.value())
        if self.tc_neutral_axis_emphasis_intctrl is not None:
            setcfg(
                "tc_neutral_axis_emphasis",
                self.tc_neutral_axis_emphasis_intctrl.value() / 100.0,
            )
        if self.tc_dark_emphasis_intctrl is not None:
            setcfg(
                "tc_dark_emphasis", self.tc_dark_emphasis_intctrl.value() / 100.0
            )

    def writecfg(self) -> None:
        """Write the testchart-editor configuration to disk."""
        config.writecfg(
            module="testchart-editor",
            options=(
                "3d_format",
                "last_ti1_path",
                "last_testchart_export_path",
                "last_vrml_path",
                "position.tcgen",
                "size.tcgen",
                "tc.",
                "tc_",
            ),
        )

    # -- control handlers --------------------------------------------------

    def _save_and_check(self, *_args) -> None:
        """Persist config and refresh derived state (buttons, status, labels)."""
        if self._loading:
            return
        self.tc_save_cfg()
        self._update_multi_patches_label()
        self.tc_check()

    def _on_patch_count(self, *_args) -> None:
        """React to any patch-count spin change."""
        self._save_and_check()

    def _on_multi_bcc(self, *_args) -> None:
        """React to the body-centered-cubic multi-dim toggle."""
        self._save_and_check()

    def _on_algo(self, *_args) -> None:
        """React to an algorithm change (re-enable dependent controls)."""
        self._save_and_check()

    def _on_adaption(self) -> None:
        """React to an adaption change."""
        self._save_and_check()

    def _on_angle(self) -> None:
        """React to an angle change."""
        self._save_and_check()

    def _on_neutral_axis_emphasis(self) -> None:
        """React to a neutral-axis-emphasis change."""
        self._save_and_check()

    def _on_dark_emphasis(self) -> None:
        """React to a dark-region-emphasis change."""
        self._save_and_check()

    def _update_multi_patches_label(self) -> None:
        """Show the patch count implied by the multi-dimensional steps."""
        steps = self.tc_multi_steps.value()
        count = int(math.pow(steps, 3)) if steps > 1 else 0
        self.tc_multi_patches.setText(str(count) if count else "")

    def _update_enabled_states(self) -> None:
        """Enable/disable the algorithm-dependent controls (matches wx)."""
        algo_enable = self.tc_fullspread_patches.value() > 0
        self.tc_algo.setEnabled(algo_enable)
        algo = self.tc_algos_ba.get(self.tc_algo.currentText(), "")
        self.tc_adaption_slider.setEnabled(algo_enable and algo == "")
        self.tc_adaption_intctrl.setEnabled(algo_enable and algo == "")
        self.tc_angle_slider.setEnabled(algo_enable and algo in ("i", "I"))
        self.tc_angle_intctrl.setEnabled(algo_enable and algo in ("i", "I"))
        precond_enable = algo in ("I", "Q", "R", "t") or (
            algo == "" and self.tc_adaption_intctrl.value() > 0
        )
        if self.tc_neutral_axis_emphasis_slider is not None:
            self.tc_neutral_axis_emphasis_slider.setEnabled(
                algo_enable and precond_enable
            )
            self.tc_neutral_axis_emphasis_intctrl.setEnabled(
                algo_enable and precond_enable
            )
        if self.tc_dark_emphasis_slider is not None:
            dark_enable = self.argyll_version >= [1, 6, 3] or (
                precond_enable
                and bool(int(getcfg("tc_precond")))
                and bool(getcfg("tc_precond_profile"))
            )
            self.tc_dark_emphasis_slider.setEnabled(dark_enable)
            self.tc_dark_emphasis_intctrl.setEnabled(dark_enable)

    # -- patch counting ----------------------------------------------------

    def tc_get_total_patches(
        self,
        white_patches: int | None = None,
        black_patches: int | None = None,
        single_channel_patches: int | None = None,
        gray_patches: int | None = None,
        multi_steps: int | None = None,
        multi_bcc_steps: int | None = None,
        fullspread_patches: int | None = None,
    ) -> int:
        """Return the total patch count for the given (or current) parameters.

        Args:
            white_patches (int | None): White patch count.
            black_patches (int | None): Black patch count.
            single_channel_patches (int | None): Single-channel patch count.
            gray_patches (int | None): Gray patch count.
            multi_steps (int | None): Multi-dimensional steps.
            multi_bcc_steps (int | None): Body-centered-cubic multi-dim steps.
            fullspread_patches (int | None): Full-spread patch count.

        Returns:
            int: The total number of patches.
        """
        if self.ti1 is not None and [
            white_patches,
            black_patches,
            single_channel_patches,
            gray_patches,
            multi_steps,
            multi_bcc_steps,
            fullspread_patches,
        ] == [None] * 7:
            return self.ti1.queryv1("NUMBER_OF_SETS")
        if white_patches is None:
            white_patches = self.tc_white_patches.value()
        if black_patches is None:
            black_patches = (
                self.tc_black_patches.value()
                if self.tc_black_patches is not None
                else 0
            )
        if single_channel_patches is None:
            single_channel_patches = self.tc_single_channel_patches.value()
        if gray_patches is None:
            gray_patches = self.tc_gray_patches.value()
        if (
            gray_patches == 0
            and (single_channel_patches > 0 or black_patches > 0)
            and white_patches > 0
        ):
            gray_patches = 2
        if multi_steps is None:
            multi_steps = self.tc_multi_steps.value()
        if (
            multi_bcc_steps is None
            and getcfg("tc_multi_bcc")
            and self.argyll_version >= [1, 6]
        ):
            multi_bcc_steps = self.tc_multi_steps.value()
        if fullspread_patches is None:
            fullspread_patches = self.tc_fullspread_patches.value()
        return get_total_patches(
            white_patches,
            black_patches,
            single_channel_patches,
            gray_patches,
            multi_steps,
            multi_bcc_steps,
            fullspread_patches,
        )

    def tc_get_black_patches(self) -> int:
        """Return the effective number of black patches.

        Returns:
            int: The black patch count after gray/multi adjustments.
        """
        black_patches = (
            self.tc_black_patches.value() if self.tc_black_patches is not None else 0
        )
        single = self.tc_single_channel_patches.value()
        gray = self.tc_gray_patches.value()
        if gray == 0 and single > 0 and black_patches > 0:
            gray = 2
        if self.tc_multi_steps.value() > 1 or gray > 1:
            black_patches -= 1
        return max(0, black_patches)

    def tc_get_white_patches(self) -> int:
        """Return the effective number of white patches.

        Returns:
            int: The white patch count after gray/multi adjustments.
        """
        white = self.tc_white_patches.value()
        single = self.tc_single_channel_patches.value()
        gray = self.tc_gray_patches.value()
        if gray == 0 and single > 0 and white > 0:
            gray = 2
        if self.tc_multi_steps.value() > 1 or gray > 1:
            white -= 1
        return max(0, white)

    # -- state -------------------------------------------------------------

    def tc_check(self) -> None:
        """Enable/disable buttons and refresh the status line for the state."""
        self.tc_amount = self.tc_get_total_patches(self.tc_white_patches.value())
        can_create = (
            self.tc_amount
            - max(0, self.tc_get_white_patches())
            - max(0, self.tc_get_black_patches())
            >= 8
        )
        self.preview_btn.setEnabled(can_create)
        self.clear_btn.setEnabled(self.ti1 is not None)
        self.save_as_btn.setEnabled(self.ti1 is not None)
        self.tc_save_check()
        self.tc_set_default_status()

    def tc_save_check(self) -> None:
        """Enable the Save button only for a modified, user-owned chart."""
        ti1 = self.ti1
        enabled = bool(
            ti1 is not None
            and ti1.modified
            and ti1.filename
            and os.path.exists(ti1.filename)
            and get_data_path(os.path.join("ref", os.path.basename(ti1.filename)))
            != ti1.filename
            and get_data_path(os.path.join("ti1", os.path.basename(ti1.filename)))
            != ti1.filename
        )
        self.save_btn.setEnabled(enabled)

    def tc_set_default_status(self) -> None:
        """Show the total (and selected) patch count in the status bar."""
        if not self.tc_amount:
            self.statusBar().clearMessage()
            return
        text = f"{lang.getstr('tc.patches.total')}: {self.tc_amount}"
        rows = {index.row() for index in self.grid.selectionModel().selectedRows()}
        if rows:
            text += f" / {lang.getstr('tc.patches.selected')}: {len(rows)}"
        self.statusBar().showMessage(text)

    # -- colour label ------------------------------------------------------

    def _get_color_label(self, sample: object) -> tuple[QColor, str, QColor | None]:
        """Return the swatch colour, marker text and text colour for a sample.

        Ports ``wx_testchart_editor.tc_getcolorlabel``: classifies each patch
        (white/black/neutral, primaries and secondaries plus their light
        variants) and picks a legible label colour.

        Args:
            sample: A CGATS sample with ``RGB_R``/``RGB_G``/``RGB_B`` (0..100).

        Returns:
            tuple[QColor, str, QColor | None]: Background colour, label text and
            optional text colour.
        """
        r, g, b = sample.RGB_R, sample.RGB_G, sample.RGB_B
        color = QColor(
            round(r / 100.0 * 255), round(g / 100.0 * 255), round(b / 100.0 * 255)
        )
        white = QColor(255, 255, 255)
        black = QColor(0, 0, 0)
        if r == g == b:  # neutral / black / white
            label_color = white if r < 50 else black
            text = "K" if r <= 50 else ("W" if r == 100 else "k")
        elif (g == 0 and b == 0) or (r == 100 and g == b):  # red
            label_color = black if r > 75 else white
            text = "r" if r == 100 and g > 0 else "R"
        elif (r == 0 and b == 0) or (g == 100 and r == b):  # green
            label_color = black if g > 75 else white
            text = "g" if g == 100 and r > 0 else "G"
        elif (r == 0 and g == 0) or (b == 100 and r == g):  # blue
            label_color = black if r > 25 else white
            text = "b" if b == 100 and r > 0 else "B"
        elif (r == 0 or b == 100) and g == b:  # cyan
            label_color = black if g > 75 else white
            text = "c" if g == 100 and r > 0 else "C"
        elif (g == 0 or r == 100) and r == b:  # magenta
            label_color = black if r > 75 else white
            text = "m" if r == 100 and g > 0 else "M"
        elif (b == 0 or g == 100) and r == g:  # yellow
            label_color = black if g > 75 else white
            text = "y" if b > 0 else "Y"
        else:
            return color, "", None
        return color, text, label_color

    # -- grid --------------------------------------------------------------

    def _populate_grid(self) -> None:
        """Fill the grid from ``self.ti1`` (RGB columns + swatch)."""
        self.grid.blockSignals(True)
        self.grid.clearContents()
        data = self.ti1.queryv1("DATA")
        count = self.ti1.queryv1("NUMBER_OF_SETS")
        self.grid.setRowCount(count)
        for row in range(count):
            sample = data[row]
            for col, label in enumerate(("RGB_R", "RGB_G", "RGB_B")):
                item = QTableWidgetItem(self._fmt(sample[label]))
                item.setTextAlignment(Qt.AlignCenter)
                self.grid.setItem(row, col, item)
            self._set_swatch(row, sample)
        self.grid.blockSignals(False)
        self.tc_amount = count
        self.tc_set_default_status()

    def _set_swatch(self, row: int, sample: object) -> None:
        """Set the swatch cell's colour and marker text for ``row``.

        Args:
            row (int): The grid row.
            sample: The CGATS sample for that row.
        """
        color, text, text_color = self._get_color_label(sample)
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setBackground(color)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        if text_color is not None:
            item.setForeground(text_color)
        self.grid.setItem(row, len(self._RGB_COLUMNS), item)

    @staticmethod
    def _fmt(value: float) -> str:
        """Format a 0..100 device value for display.

        Args:
            value (float): The device value.

        Returns:
            str: A trimmed decimal string (integers shown without a point).
        """
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return text or "0"

    def _on_cell_changed(self, item: QTableWidgetItem) -> None:
        """Apply an edited RGB cell back to the chart and recolour the swatch.

        Args:
            item (QTableWidgetItem): The edited grid item.
        """
        if self.ti1 is None or item.column() >= len(self._RGB_COLUMNS):
            return
        try:
            value = max(0.0, min(float(item.text()), 100.0))
        except ValueError:
            return
        data = self.ti1.queryv1("DATA")
        sample = data[item.row()]
        label = ("RGB_R", "RGB_G", "RGB_B")[item.column()]
        sample[label] = value
        self.ti1.setmodified(True)
        self.grid.blockSignals(True)
        item.setText(self._fmt(value))
        self._set_swatch(item.row(), sample)
        self.grid.blockSignals(False)
        self.tc_save_check()

    # -- generation --------------------------------------------------------

    def tc_generate(self) -> None:
        """Generate a new testchart via Argyll ``targen`` (off-thread)."""
        if self._gen_thread is not None and self._gen_thread.isRunning():
            return
        if not check_set_argyll_bin():
            QMessageBox.warning(
                self, self.windowTitle(), lang.getstr("argyll.dir.invalid", "")
            )
            return
        self.tc_save_cfg()
        self.writecfg()
        self.worker.interactive = False
        self.preview_btn.setEnabled(False)
        self.statusBar().showMessage(lang.getstr("testchart.create"))
        self._gen_thread = _GenerateThread(self, parent=self)
        self._gen_thread.done.connect(self._on_generated)
        self._gen_thread.start()

    def tc_create(self) -> CGATS | Exception:
        """Run ``targen`` and return the resulting chart (off the GUI thread).

        Returns:
            CGATS | Exception: The generated chart, or the raised error.
        """
        cmd, args = self.worker.prepare_targen()
        if isinstance(cmd, Exception):
            return cmd
        result = self.worker.exec_cmd(
            cmd, args, low_contrast=False, skip_scripts=True, silent=False
        )
        if isinstance(result, Exception):
            self.worker.wrapup(False)
            return result
        if not result:
            self.worker.wrapup(False)
            return Error("".join(self.worker.errors) or "targen failed")
        path = os.path.join(self.worker.tempdir, "temp.ti1")
        checked = check_file_isfile(path, silent=False)
        if isinstance(checked, Exception):
            self.worker.wrapup(False)
            return checked
        try:
            chart = CGATS(path)
            chart.filename = None
        except Exception as exception:  # noqa: BLE001
            self.worker.wrapup(False)
            return Error(f"Error - testchart file could not be read: {exception!s} ")
        self.worker.wrapup(False)
        return chart

    def _on_generated(self, result: object) -> None:
        """Receive a generated chart on the GUI thread and display it.

        Args:
            result (object): The generated ``CGATS`` or an ``Exception``.
        """
        self._gen_thread = None
        self.preview_btn.setEnabled(True)
        if isinstance(result, Exception):
            QMessageBox.critical(self, self.windowTitle(), str(result))
            self.tc_check()
            return
        self.ti1 = result
        self._populate_grid()
        self.tc_check()

    # -- loading -----------------------------------------------------------

    def load_file(self, path: str) -> None:
        """Load a testchart file at ``path`` (off-thread).

        Args:
            path (str): Path to a ``.ti1``/``.ti3``/``.cgats``/``.txt`` or ICC file.
        """
        if self._load_thread is not None and self._load_thread.isRunning():
            return
        self.statusBar().showMessage(lang.getstr("testchart.read"))
        self._load_thread = _LoadThread(self, os.path.abspath(path), parent=self)
        self._load_thread.done.connect(self._on_loaded)
        self._load_thread.start()

    def tc_load_worker(self, path: str) -> tuple | Exception:
        """Read ``path`` into ``self.ti1`` and reconstruct its parameters.

        Args:
            path (str): The chart file to read.

        Returns:
            tuple | Exception: ``(white, black, single, gray, multi, multi_bcc,
            fullspread, gamma, dark_emphasis)`` or the raised error.
        """
        filename, ext = os.path.splitext(path)
        try:
            if ext.lower() in (".icc", ".icm"):
                profile = ICCProfile(path)
                ti1 = CGATS(
                    ti3_to_ti1(
                        profile.tags.get("CIED", "") or profile.tags.get("targ", "")
                    )
                )
                ti1.filename = filename + ".ti1"
            elif ext.lower() == ".ti3":
                with open(path, "rb") as handle:
                    ti1 = CGATS(ti3_to_ti1(handle.read()))
                ti1.filename = filename + ".ti1"
            else:
                ti1 = CGATS(path)
                ti1.filename = path
            ti1.fix_device_values_scaling()
            try:
                ti1_1 = verify_cgats(ti1, ("RGB_R", "RGB_B", "RGB_G"))
            except CGATSError as exception:
                msg = {
                    CGATSKeyError: lang.getstr(
                        "error.testchart.missing_fields",
                        (path, "RGB_R, RGB_G, RGB_B"),
                    )
                }.get(
                    exception.__class__,
                    lang.getstr("error.testchart.invalid", path)
                    + "\n"
                    + lang.getstr(str(exception)),
                )
                return Error(msg)
            try:
                verify_cgats(ti1, ("XYZ_X", "XYZ_Y", "XYZ_Z"))
            except CGATSKeyError:
                data = ti1_1.queryv1("DATA")
                data.parent.DATA_FORMAT.add_data(("XYZ_X", "XYZ_Y", "XYZ_Z"))
                for sample in data.values():
                    xyz = argyll_rgb2xyz.rgb2xyz(
                        *[sample["RGB_" + channel] / 100.0 for channel in "RGB"]
                    )
                    for i, component in enumerate("XYZ"):
                        sample["XYZ_" + component] = xyz[i] * 100
            else:
                if ext.lower() not in (".ti1", ".ti2") and ti1_1:
                    ti1_1.add_keyword("ACCURATE_EXPECTED_VALUES", "true")
            ti1.root.setmodified(False)
            self.ti1 = ti1
        except Exception as exception:  # noqa: BLE001
            return Error(
                "{}\n\n{}".format(lang.getstr("error.testchart.read", path), exception)
            )
        return self._reconstruct_params()

    def _reconstruct_params(self) -> tuple:
        """Derive control values from the loaded chart's keywords.

        Charts carrying targen keywords restore exactly; keyword-less charts fall
        back to counting white/black patches (full parity for the latter is a
        later stage).

        Returns:
            tuple: ``(white, black, single, gray, multi, multi_bcc, fullspread,
            gamma, dark_emphasis)``.
        """
        ti1 = self.ti1
        white = ti1.queryv1("WHITE_COLOR_PATCHES")
        black = ti1.queryv1("BLACK_COLOR_PATCHES")
        single = ti1.queryv1("SINGLE_DIM_STEPS")
        gray = ti1.queryv1("COMP_GREY_STEPS")
        multi_bcc = ti1.queryv1("MULTI_DIM_BCC_STEPS") or 0
        multi = ti1.queryv1("MULTI_DIM_STEPS") or multi_bcc
        gamma = ti1.queryv1("EXTRA_DEV_POW") or 1.0
        dark_emphasis = ((ti1.queryv1("DARK_REGION_EMPHASIS") or 1.0) - 1.0) / 3.0
        if None in (white, single, gray, multi):
            # Keyword-less chart: count only the unambiguous white/black patches.
            white = len(ti1[0].queryi({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100}))
            black = len(ti1[0].queryi({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0}))
            single = single or 0
            gray = gray or 0
            multi = multi or 0
        return white, black, single, gray, multi, multi_bcc, None, gamma, dark_emphasis

    def _on_loaded(self, result: object) -> None:
        """Apply a loaded chart's parameters and display it (GUI thread).

        Args:
            result (object): The parameter tuple or an ``Exception``.
        """
        self._load_thread = None
        if isinstance(result, Exception):
            self.statusBar().clearMessage()
            QMessageBox.critical(self, self.windowTitle(), str(result))
            return
        (white, black, single, gray, multi, multi_bcc, _fs, gamma, dark) = result
        algo = None
        for keyword, code in FULLSPREAD_KEYWORD_TO_ALGO.items():
            value = self.ti1.queryv1(keyword)
            if value is not None and value > 0:
                algo = code
                break
        if white is not None:
            setcfg("tc_white_patches", white)
        if black is not None:
            setcfg("tc_black_patches", black)
        if single is not None:
            setcfg("tc_single_channel_patches", single)
        if gray is not None:
            setcfg("tc_gray_patches", gray)
        if multi is not None:
            setcfg("tc_multi_steps", multi)
        setcfg("tc_multi_bcc_steps", multi_bcc)
        setcfg(
            "tc_fullspread_patches",
            self.ti1.queryv1("NUMBER_OF_SETS")
            - self.tc_get_total_patches(
                white, black, single, gray, multi, multi_bcc, 0
            ),
        )
        if gamma is not None:
            setcfg("tc_gamma", gamma)
        if dark is not None:
            setcfg("tc_dark_emphasis", dark)
        if algo is not None:
            setcfg("tc_algo", algo)
        self.writecfg()
        self.tc_update_controls()
        self.setWindowTitle(
            f"{lang.getstr('testchart.edit').rstrip('.')}: "
            f"{os.path.basename(self.ti1.filename)}"
        )
        self._populate_grid()
        self.tc_check()

    # -- save / clear ------------------------------------------------------

    def tc_save(self) -> None:
        """Save the chart to its current filename."""
        if self.ti1 is not None and self.ti1.filename:
            self.tc_save_as(self.ti1.filename)

    def tc_save_as(self, path: str | None = None) -> bool:
        """Save the chart as a ``.ti1`` file.

        Args:
            path (str | None): Target path; prompts with a dialog when ``None``.

        Returns:
            bool: ``True`` if the chart was written.
        """
        if self.ti1 is None:
            return False
        if path is None:
            default_dir = get_verified_path("last_ti1_path")[0]
            if self.ti1.filename:
                if os.path.isfile(self.ti1.filename):
                    default_dir = os.path.dirname(self.ti1.filename)
                default_file = os.path.basename(self.ti1.filename)
            else:
                default_file = os.path.basename(DEFAULTS["last_ti1_path"])
            path, _ = QFileDialog.getSaveFileName(
                self,
                lang.getstr("save_as"),
                os.path.join(default_dir, default_file),
                f"{lang.getstr('filetype.ti1')} (*.ti1)",
            )
            if not path:
                return False
            if os.path.splitext(path)[1].lower() != ".ti1":
                path += ".ti1"
        if not waccess(path, os.W_OK):
            QMessageBox.critical(
                self, self.windowTitle(), lang.getstr("error.access_denied.write", path)
            )
            return False
        setcfg("last_ti1_path", path)
        try:
            with open(path, "wb") as handle:
                handle.write(bytes(self.ti1))
        except Exception as exception:  # noqa: BLE001
            QMessageBox.critical(
                self,
                self.windowTitle(),
                f"Error - testchart could not be saved: {exception!s}",
            )
            return False
        self.ti1.filename = path
        self.ti1.root.setmodified(False)
        self.setWindowTitle(
            f"{lang.getstr('testchart.edit').rstrip('.')}: {os.path.basename(path)}"
        )
        self.save_btn.setEnabled(False)
        return True

    def tc_clear(self) -> None:
        """Discard the current chart and reset the editor."""
        self.grid.blockSignals(True)
        self.grid.clearContents()
        self.grid.setRowCount(0)
        self.grid.blockSignals(False)
        self.ti1 = None
        self.tc_amount = 0
        self.setWindowTitle(lang.getstr("testchart.edit"))
        self.tc_update_controls()
        self.tc_check()

    # -- scripting ---------------------------------------------------------

    def get_commands(self) -> list:
        """Return the scripting commands this window understands.

        Returns:
            list: The common commands plus this tool's file-opening commands.
        """
        return [
            *self.get_common_commands(),
            "testchart-editor [filename]",
            "load <filename>",
        ]

    def process_data(self, data: list) -> str:
        """Handle this tool's scripting commands.

        Args:
            data (list): The split command line.

        Returns:
            str: ``"ok"``, ``"fail"`` or ``"invalid"``.
        """
        return self.open_files_command(data, "testchart-editor")

    # -- lifecycle ---------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        """Persist configuration before closing.

        Args:
            event (QCloseEvent): The Qt close event.
        """
        self.tc_save_cfg()
        self.writecfg()
        super().closeEvent(event)


def main() -> int:
    """Entry point for the Qt testchart editor.

    Returns:
        int: The Qt application exit code.
    """
    config.initcfg("testchart-editor")
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    window = TestchartEditorWindow()
    app.top_window = window
    window.show()
    window.listen()

    charts = [a for a in sys.argv[1:] if os.path.isfile(a)]
    if charts:
        window.load_file(charts[0])
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
