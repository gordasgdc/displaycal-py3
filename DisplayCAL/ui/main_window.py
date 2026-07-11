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
(Prisma / madTPG / Resolve), the visual-editor / ambient-measure buttons, and
the black-point-rate advanced control. Actually creating a 3D LUT
(:meth:`MainWindow.lut3d_create_btn_handler`, hidden behind the calibrate/
profile buttons whenever the 3D LUT tab is active with manual creation) now
runs ``worker.create_3dlut`` through the same
:class:`~DisplayCAL.ui.worker_runner.WorkerRunController` the other action
buttons use; see :mod:`DisplayCAL.lut3d_settings`'s module docstring for what
isn't reproduced there. On success (:meth:`MainWindow._on_lut3d_create_finished`)
it now also offers to install/copy the result
(:meth:`MainWindow._offer_install_3dlut` / :meth:`_install_3dlut`, a port of
wx's ``profile_finish`` re-entry from ``lut3d_create_consumer``), and
``3dlut.create`` now really does auto-chain LUT creation after a profiling
run instead of only hiding the manual button
(:meth:`MainWindow._chain_3dlut_after_profile`, called from
:meth:`_on_profile_build_finished`), with :meth:`MainWindow._check_lut3d_bpc`
(a port of ``MainFrame.lut3d_check_bpc``) warning if profile black-point
compensation is on at the same time. The madVR/Prisma **API** install branch
still isn't reproduced -- it needs the unported ``setup_patterngenerator``
connection dialogs -- so it shows a not-yet-available notice; only the
generic copy-to-path and ReShade-folder-detection destinations actually
install. The measurement-report settings live in the embedded **Verification**
tab (:class:`~DisplayCAL.ui.measurement_report.ReportPanel`, matching wx's
5th tab, ``display_cal.py:2450-2458``), whose "edit chart" button reuses the
already-ported :mod:`DisplayCAL.ui.tools.testchart_editor`; the shared
action-bar Measure button (:meth:`MainWindow.measurement_report_btn_handler`,
matching wx's ``buttonpanel``-level ``measurement_report_btn`` rather than a
per-tab one) runs the full chart/profile resolution, worker-driven
measurement and HTML report generation via
:mod:`DisplayCAL.measurement_report` (:meth:`MainWindow._on_report_measure_requested`
onward).
The pre-flight confirmation / overwrite dialogs (:meth:`MainWindow._check_overwrite`
/ :meth:`MainWindow._check_show_macos_bugs_warning` / :meth:`MainWindow
._current_cal_choice` / :meth:`MainWindow._fast_matrix_shaper_choice`, backed by
:mod:`DisplayCAL.preflight_checks`) now run ahead of every action button; not
reproduced there: the ``silent=True`` auto-retry call path (no auto-retry flow
exists in this port yet).
``show_advanced_options`` itself is wired (an Options-menu checkbox gating every
other row it controls that this port does have, including the whitepoint
colour-temperature-locus row (Calibration tab, via
:meth:`MainWindow._apply_whitepoint_mode`), the profile-type row's gamap
button, and the testchart-patch-sequence row), see
:meth:`MainWindow._update_advanced_options_visibility`. Profile-name token
expansion and the testchart chooser / patch-count / estimated-measurement-time
controls are wired via the toolkit-neutral :mod:`DisplayCAL.profile_name`
helpers, and the 3D LUT tab's TRC/HDR/content-colorspace/gamut-mapping/encoding
controls via :mod:`DisplayCAL.lut3d_settings`. The Tools menu carries the
colorimeter-correction import/upload actions
(:mod:`DisplayCAL.ui.colorimeter_correction_io`'s ``ImportController`` /
``UploadController``); the rest of wx's larger ``menu.tools`` isn't reproduced.

The Profiling tab's "Advanced..." (gamap) button opens the ported
:class:`~DisplayCAL.ui.gamap_window.GamapWindow` (:meth:`MainWindow
._gamap_btn_handler`), a singleton reused across opens. Its ``profile_settings_changed`` /
``b2a_quality_changed`` signals drive :meth:`MainWindow
._mark_profile_settings_changed` and :meth:`MainWindow._update_bpc` /
:meth:`MainWindow._update_lut3d_b2a_controls` respectively, replacing wx's
direct ``self.Parent`` attribute access. :meth:`MainWindow._update_bpc` (the
black-point-compensation checkbox's enable/checked state, a port of
``MainFrame.update_bpc``) is also called from :meth:`update_profile_controls`
and :meth:`_profile_type_ctrl_changed` — a real pre-existing gap before this
session, since Stage 3 never wired it at all.

The Help menu (:meth:`MainWindow._build_help_menu`) mirrors wx's
``menu.help`` in full: readme/license, website/support/bug-report, the
"check for updates" pair, and an About dialog
(:class:`DisplayCAL.ui.about_window.AboutWindow`).
:meth:`MainWindow.run_post_launch_checks` (called
by :mod:`DisplayCAL.ui.startup` once the window is shown) is the Qt port of
wx's ``StartupFrame.setup_frame_finish`` tail: a silent update check
(:mod:`DisplayCAL.ui.update_check_window`) chaining into the instrument-setup
/ donation-nag check (:mod:`DisplayCAL.instrument_setup`) when nothing needs
updating. The colorimeter-correction import prompt reuses the same
``ImportController`` the Tools menu does; the Spyder2 firmware-enable wizard
(:mod:`DisplayCAL.ui.spyder2_enable`'s ``Spyder2EnableController``) runs when
:mod:`DisplayCAL.instrument_setup` detects a Spyder2 that needs its firmware
enabled, and :meth:`MainWindow._on_spyder2_enable_finished` re-runs the whole
instrument-setup check afterward when
``InstrumentSetupNeeds.recheck_after_spyder2`` says other imports are still
pending, mirroring wx's ``enable_spyder2_consumer`` recursion into
``check_instrument_setup``.

The window is opt-in behind ``DISPLAYCAL_UI=qt`` / ``--qt`` (wired in
:mod:`DisplayCAL.main`), so it never displaces the still-shipping wx main window.
"""

from __future__ import annotations

import contextlib
import enum
import os
import platform
import re
import sys
from decimal import Decimal
from hashlib import md5
from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import QSize, Qt, QThread, QTimer, Signal
from qtpy.QtGui import QAction, QColor, QPainter, QPixmap
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QApplication,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import (
    calibration_file,
    colorimeter_correction,
    config,
    create_profile,
    gamap_settings,
    instrument_setup,
    lut3d_settings,
    preflight_checks,
    profile_finish,
)
from DisplayCAL import measurement_report as measurement_report_pipeline
from DisplayCAL import localization as lang
from DisplayCAL import profile_name as profile_name_mod
from DisplayCAL.argyll import (
    check_set_argyll_bin,
    get_argyll_util,
    make_argyll_compatible_path,
)
from DisplayCAL.cgats import CGATS, CGATSError
from DisplayCAL.colorimeter_correction import ColorimeterCorrectionCatalog
from DisplayCAL.config import (
    DEFAULTS,
    PROFILE_EXT,
    get_data_path,
    get_verified_path,
    getcfg,
    setcfg,
    setcfg_cond,
    writecfg,
)
from DisplayCAL.icc_profile import (
    CurveType,
    ICCProfile,
    ICCProfileInvalidError,
    LUT16Type,
    TextType,
    VideoCardGammaType,
)
from DisplayCAL.meta import DEVELOPMENT_HOME_PAGE, DOMAIN
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.meta import VERSION_STRING
from DisplayCAL.options import TEST
from DisplayCAL.ui.about_window import AboutWindow
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.assets import get_theme_pixmap, get_themed_pixmap
from DisplayCAL.ui.theme import is_dark
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.ccxx_plot_window import CCXXPlotWindow
from DisplayCAL.ui.colorimeter_correction_io import (
    ImportController,
    UploadController,
    WebCheckController,
)
from DisplayCAL.ui.colorimeter_correction_window import CreateCorrectionWindow
from DisplayCAL.ui.display_adjustment_window import DisplayAdjustmentWindow
from DisplayCAL.ui.gamap_window import GamapWindow
from DisplayCAL.ui.header_banner import (
    HEADER_BANNER_SIZE,
    HeaderBanner,
    header_banner_pixmap,
)
from DisplayCAL.ui.measure_frame import MeasureFrame
from DisplayCAL.ui.measurement_flow import (
    MeasurementFlow,
    PresentationMode,
    build_measureframe_command,
    interpret_measureframe_result,
    observer_items,
    run_measureframe_subprocess,
)
from DisplayCAL.ui.measurement_report import ReportPanel
from DisplayCAL.ui.measurement_sanity_dialog import MeasurementSanityDialog
from DisplayCAL.ui.patterngenerator_setup import Lut3DAPIInstallController
from DisplayCAL.ui.profile_install_window import InstallProfileWindow
from DisplayCAL.ui.progress_dialog import ProgressDialog
from DisplayCAL.ui.spyder2_enable import Spyder2EnableController
from DisplayCAL.ui.tooltip_window import TooltipWindow
from DisplayCAL.ui.tools.lut3d import LUT3DWindow
from DisplayCAL.ui.tools.profile_info import ProfileInfoWindow
from DisplayCAL.ui.tools.synth_profile import SynthICCWindow
from DisplayCAL.ui.tools.testchart_editor import TestchartEditorWindow
from DisplayCAL.ui.update_check_window import UpdateCheckController
from DisplayCAL.ui.worker_runner import AdjustmentController, WorkerRunController
from DisplayCAL.util_decimal import stripzeros
from DisplayCAL.util_dict import dict_sort
from DisplayCAL.util_os import get_program_file, launch_file, waccess
from DisplayCAL.worker import (
    Worker,
    check_file_isfile,
    get_options_from_cal,
    get_options_from_profile,
    parse_argument_string,
)

if TYPE_CHECKING:
    from qtpy.QtGui import QPaintEvent, QShowEvent


#: The settings tabs, in order: ``(config-ish key, icon name, label key)``.
_TABS = (
    ("display_instrument", "display-instrument", "display-instrument"),
    ("calibration", "calibration", "calibration"),
    ("profiling", "profiling", "profiling"),
    ("lut3d", "3dlut", "3dlut"),
    ("verification", "dialog-ok", "verification"),
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

#: ``(config value, label key)`` pairs for the ``profile_type_ctrl`` combo, in
#: wx's ``update_profile_type_ctrl_items`` order. ``ProfileType`` (see
#: :mod:`DisplayCAL.profile_name`) is the source of truth; re-exported here
#: under its established name for this module's combo-building code and
#: ``tests/test_ui_main_window.py``.
PROFILE_TYPES = profile_name_mod.PROFILE_TYPES
ProfileType = profile_name_mod.ProfileType

#: Profile types whose gamut can be usefully remapped (enables ``gamap_btn``);
#: black point compensation also defaults off the first time one is selected.
_GAMUT_MAPPABLE_PROFILE_TYPES = (
    ProfileType.LAB_LUT,
    ProfileType.XYZ_LUT,
    ProfileType.XYZ_LUT_MATRIX,
)
#: Curve+matrix profile types; black point compensation defaults on the first
#: time one is selected.
_CURVE_MATRIX_PROFILE_TYPES = (
    ProfileType.SHAPER_MATRIX,
    ProfileType.SINGLE_SHAPER_MATRIX,
)
#: Gamma-only profile types: Argyll only supports one profile-quality level
#: for these, so the quality slider is locked to "high".
_GAMMA_ONLY_PROFILE_TYPES = (
    ProfileType.GAMMA_MATRIX,
    ProfileType.SINGLE_GAMMA_MATRIX,
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


class _SessionArchiveThread(QThread):
    """Run :func:`~DisplayCAL.calibration_file.create_session_archive` off-thread.

    The Qt equivalent of wx's ``worker.start(create_session_archive_consumer,
    create_session_archive_producer, ...)`` pair (same one-shot-behind-a-
    progress-dialog pattern as :class:`~DisplayCAL.ui.profile_install_window
    ._InstallThread`).
    """

    #: Emitted with the archive result (``True``, or an ``Exception``).
    done = Signal(object)

    def __init__(
        self,
        request: calibration_file.SessionArchiveRequest,
        exec_cmd: object,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._request = request
        self._exec_cmd = exec_cmd

    def run(self) -> None:  # noqa: D102 (QThread override)
        result = calibration_file.create_session_archive(self._request, self._exec_cmd)
        self.done.emit(result)


class _SessionArchiveImportThread(QThread):
    """Run :func:`~DisplayCAL.calibration_file.import_session_archive` off-thread.

    The Qt equivalent of wx's ``worker.start(import_session_archive_consumer,
    import_session_archive_producer, ...)`` pair.
    """

    #: Emitted with the extraction result (a storage path, or an ``Exception``).
    done = Signal(object)

    def __init__(
        self,
        request: calibration_file.SessionArchiveImportRequest,
        exec_cmd: object,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._request = request
        self._exec_cmd = exec_cmd

    def run(self) -> None:  # noqa: D102 (QThread override)
        result = calibration_file.import_session_archive(self._request, self._exec_cmd)
        self.done.emit(result)


#: Sentinel returned by :meth:`MainWindow._current_cal_choice` when the user
#: cancels, distinguishable from its other possible results (``None``,
#: ``False``, or a ``.cal`` path) -- the Qt stand-in for wx's ``wx.ID_CANCEL``.
CAL_CHOICE_CANCELLED = object()


class _CalChoiceDialog(QDialog):
    """Qt port of the checkbox dialog ``MainFrame.current_cal_choice`` builds.

    Presents the "embed calibration" / "use linear instead" checkboxes
    described by a :class:`~DisplayCAL.preflight_checks.CalChoiceInfo`, mirroring
    wx's ``embed_cal_ctrl_handler`` (the reset checkbox is only enabled -- and
    forced back on when disabled -- while embed is checked).
    """

    def __init__(
        self, info: preflight_checks.CalChoiceInfo, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(APPNAME)
        layout = QVBoxLayout(self)
        label = QLabel(
            lang.getstr(
                info.msg_key,
                os.path.basename(info.cal_path) if info.cal_path else None,
            )
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        self._reset_cal_cb: QCheckBox | None = None
        if info.show_reset_checkbox:
            self._reset_cal_cb = QCheckBox(
                lang.getstr("calibration.use_linear_instead")
            )
            layout.addWidget(self._reset_cal_cb)

        self._embed_cal_cb = QCheckBox(lang.getstr("calibration.embed"))
        self._embed_cal_cb.setChecked(info.show_reset_checkbox)
        if self._reset_cal_cb is not None:
            self._reset_cal_cb.setEnabled(self._embed_cal_cb.isChecked())
            self._embed_cal_cb.toggled.connect(self._embed_cal_toggled)
        layout.addWidget(self._embed_cal_cb)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(lang.getstr("continue"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _embed_cal_toggled(self, checked: bool) -> None:
        self._reset_cal_cb.setEnabled(checked)
        if not checked:
            self._reset_cal_cb.setChecked(True)

    def embed_cal(self) -> bool:
        return self._embed_cal_cb.isChecked()

    def reset_cal(self) -> bool:
        return bool(self._reset_cal_cb and self._reset_cal_cb.isChecked())


class _DeleteConfirmationDialog(QDialog):
    """Qt port of the checkbox dialog ``MainFrame.display_delete_confirmation`` builds.

    Lets the user individually toggle which of the calibration's related
    files get deleted alongside it, mirroring wx's per-file
    ``wx.CheckBox`` list (``delete_calibration_related_handler``), all
    pre-checked. A scroll area stands in for wx's ``ScrolledPanel`` so a long
    file list doesn't grow the dialog unboundedly.
    """

    def __init__(self, related_files: dict[str, bool], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(APPNAME)
        layout = QVBoxLayout(self)
        label = QLabel(lang.getstr("dialog.confirm_delete"))
        label.setWordWrap(True)
        layout.addWidget(label)

        self._checks: dict[str, QCheckBox] = {}
        if related_files:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setMaximumHeight(320)
            container = QWidget()
            container_layout = QVBoxLayout(container)
            for related_file, checked in related_files.items():
                cb = QCheckBox(related_file)
                cb.setChecked(checked)
                self._checks[related_file] = cb
                container_layout.addWidget(cb)
            container_layout.addStretch(1)
            scroll.setWidget(container)
            layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(lang.getstr("delete"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def related_files(self) -> dict[str, bool]:
        return {name: cb.isChecked() for name, cb in self._checks.items()}


class _DonationDialog(QDialog):
    """Qt port of ``display_cal.donation_message``.

    Shown by :meth:`MainWindow._show_donation_message_if_needed` once no
    instrument setup is pending, mirroring wx's post-``check_instrument_setup``
    call to ``check_donation`` -> ``donation_message``. Accepting opens the
    donation page and permanently clears ``show_donation_message``;
    declining persists the "do not show again" checkbox instead.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(lang.getstr("welcome"))
        layout = QVBoxLayout(self)

        header = QLabel(lang.getstr("donation_header"), self)
        font = header.font()
        font.setPointSize(font.pointSize() + 4)
        header.setFont(font)
        layout.addWidget(header)

        message = QLabel(lang.getstr("donation_message"), self)
        message.setWordWrap(True)
        layout.addWidget(message)

        self._do_not_show_again_cb = QCheckBox(
            lang.getstr("dialog.do_not_show_again"), self
        )
        layout.addWidget(self._do_not_show_again_cb)

        buttons = QDialogButtonBox(self)
        contribute_button = buttons.addButton(
            lang.getstr("contribute"), QDialogButtonBox.AcceptRole
        )
        contribute_button.setDefault(True)
        buttons.addButton(lang.getstr("not_now"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:  # noqa: D102 (Qt override)
        launch_file(f"https://{DOMAIN}/#donate")
        setcfg("show_donation_message", 0)
        super().accept()

    def reject(self) -> None:  # noqa: D102 (Qt override)
        setcfg(
            "show_donation_message",
            int(not self._do_not_show_again_cb.isChecked()),
        )
        super().reject()


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


def lut3d_format_items(argyll_version: str = "0.0.0") -> list[tuple[str, str]]:
    """Return ``(config value, label)`` pairs for the 3D LUT file formats.

    Mirrors ``LUT3DMixin.lut3d_setup_language``: madVR is only offered with
    Argyll 1.6+.
    """
    return [
        (fmt, lang.getstr(f"3dlut.format.{fmt}"))
        for fmt in config.VALID_VALUES["3dlut.format"]
        if fmt != "madVR" or argyll_version >= "1.6"
    ]


def lut3d_rendering_intent_items(argyll_version: str = "0.0.0") -> list[tuple[str, str]]:
    """Return ``(config value, label)`` pairs for the 3D LUT rendering intents.

    Mirrors ``LUT3DMixin.lut3d_setup_language``: "Perceptual, LUT proof"
    (``"lp"``) needs Argyll 1.8.3+.
    """
    return [
        (ri, lang.getstr(f"gamap.intents.{ri}"))
        for ri in config.VALID_VALUES["3dlut.rendering_intent"]
        if ri != "lp" or argyll_version >= "1.8.3"
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


def lut3d_content_colorspace_items() -> list[str]:
    """Return the content-colorspace combo labels (named spaces + "custom")."""
    return [*lut3d_settings.CONTENT_COLORSPACE_NAMES, lang.getstr("custom")]


def lut3d_encoding_items(codes: list[str]) -> list[tuple[str, str]]:
    """Return ``(config value, label)`` pairs for a list of encoding codes."""
    return [(code, lang.getstr(f"3dlut.encoding.type_{code}")) for code in codes]


class MainWindow(BaseWindow):
    """DisplayCAL's Qt main window (shell + all four settings tabs)."""

    #: Emitted (with a :class:`MeasurementAction`) once the user has committed to
    #: a run and the measurement area has been presented. Connected internally to
    #: :meth:`_on_measurement_requested`, which drives the Argyll worker through a
    #: :class:`~DisplayCAL.ui.worker_runner.WorkerRunController`; the signal stays
    #: public so other layers (and tests) can observe committed runs.
    measurement_requested = Signal(object)

    #: Delay before a staged measurement driver runs, letting the display settle
    #: (the wx ``call_pending_function`` 100 ms ``CallLater``).
    _pending_delay_ms = 100

    def __init__(self, worker: Worker | None = None) -> None:
        """Construct the main window.

        Args:
            worker (Worker | None): A pre-enumerated worker to adopt (e.g. from
                :class:`~DisplayCAL.ui.startup.StartupController`), skipping the
                synchronous ``enumerate_displays_and_ports`` call below. When
                omitted, a fresh ``Worker`` is created and enumerated in place
                (used by tests and standalone ``main()``).
        """
        super().__init__(
            name="mainframe",
            title=f"{APPNAME} {VERSION_STRING}",
            icon_name=APPNAME.lower(),
        )
        adopted_worker = worker is not None
        self.worker = worker if worker is not None else Worker()
        self.flow = MeasurementFlow()
        #: Guards config-writing handlers while controls are repopulated.
        self._updating = False
        #: Set right before an internal (non-user) ``profile_type_ctrl``
        #: change, so :meth:`_profile_type_ctrl_changed` can skip the
        #: CCXX-testchart-recommendation dialog for it -- mirrors wx passing
        #: ``event=None`` to ``profile_type_ctrl_handler`` from
        #: ``testchart_patches_amount_ctrl_handler``.
        self._profile_type_change_is_synthetic = False
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
        #: The Qt progress dialog / worker driver, created lazily on first run.
        self._progress_dialog: ProgressDialog | None = None
        self._run_controller: WorkerRunController | None = None
        #: The interactive-adjustment window / driver, created lazily on first
        #: interactive calibration run.
        self._adjustment_window: DisplayAdjustmentWindow | None = None
        self._adjustment_controller: AdjustmentController | None = None
        #: The ``current_cal_choice()`` result for the pending ``PROFILE`` run,
        #: set by :meth:`profile_btn_handler` and consumed by
        #: :meth:`_run_profile_measurement`.
        self._pending_apply_calibration: bool | str | None = True
        #: instrument type -> {combo index: mode code} / {mode code: index},
        #: refreshed each time :meth:`update_measurement_mode_ctrl` repopulates
        #: the measurement-mode combo (mirrors wx's ``measurement_modes_ab``
        #: / ``measurement_modes_ba``).
        self._measurement_modes_ab: dict[str, dict[int, str]] = {}
        self._measurement_modes_ba: dict[str, dict[str, int]] = {}
        #: Persistent CCMX/CCSS disk-scan cache for the correction-matrix combo.
        self._ccmx_catalog = ColorimeterCorrectionCatalog()
        self._ccxx_web_controller: WebCheckController | None = None
        self._ccxx_create_window: CreateCorrectionWindow | None = None
        #: Open CCXXPlotWindow instances keyed by md5(bytes(cgats)), mirroring
        #: wx's ``ccxx_plot_windows`` (re-showing an already-open plot instead
        #: of recomputing/reopening it).
        self._ccxx_plot_windows: dict[bytes, CCXXPlotWindow] = {}
        self._ccxx_import_controller: ImportController | None = None
        self._ccxx_upload_controller: UploadController | None = None
        self._update_check_controller: UpdateCheckController | None = None
        #: The colorimeter-correction import run from the post-launch
        #: instrument-setup check (distinct from :attr:`_ccxx_import_controller`,
        #: the Tools-menu-triggered one, so their ``finished`` handlers can stay
        #: independent -- this one chains into the donation-message check).
        self._instrument_setup_import_controller: ImportController | None = None
        self._spyder2_enable_controller: Spyder2EnableController | None = None
        #: Recent calibrations/profiles (index 0 is always "", the "new
        #: settings" choice) and bundled presets, mirroring wx's
        #: ``MainFrame.recent_cals`` / ``.presets``.
        self.recent_cals, self.presets = calibration_file.build_recent_calibrations()
        self._install_profile_window: InstallProfileWindow | None = None
        self._profile_info_window: ProfileInfoWindow | None = None
        self._archive_thread: _SessionArchiveThread | None = None
        self._archive_progress: QProgressDialog | None = None
        #: Testchart combo paths, parallel to its display names (populated by
        #: :meth:`_set_testcharts`; empty until then, mirroring wx's
        #: ``self.testcharts``, so the first :meth:`_set_testchart` call
        #: always triggers an initial population).
        self._testchart_paths: list[str] = []
        self._current_testchart_path: str | None = None
        self._testchart_editor_window: TestchartEditorWindow | None = None
        self._synthicc_window: SynthICCWindow | None = None
        self._lut3d_window: LUT3DWindow | None = None
        self._about_window: AboutWindow | None = None
        self._lut3d_api_install_controller: Lut3DAPIInstallController | None = None
        #: Staged by :meth:`_on_report_measure_requested`, consumed by
        #: :meth:`_run_report_measurement` / :meth:`_on_report_measurement_finished`
        #: (the report flow doesn't fit :class:`MeasurementAction`, so it can't
        #: thread this through the pending-function args like ``begin_measurement``
        #: does).
        self._pending_report_context: measurement_report_pipeline.ReportContext | None = (
            None
        )
        self._pending_report_save_path: str | None = None
        self._pending_report_ti1_path: str | None = None
        #: Whether the pending report run is a self-check (Alt+Measure) --
        #: set by :meth:`_on_report_measure_requested`, read by
        #: :meth:`_on_report_measurement_finished`.
        self._pending_report_self_check: bool = False
        #: The profile :meth:`_offer_profile_hires_b2a` is regenerating B2A
        #: tables for, consumed by :meth:`_on_profile_hires_b2a_finished`.
        self._pending_hires_b2a_profile: ICCProfile | None = None
        self._gamap_window: GamapWindow | None = None
        #: 3D LUT input-colorspace combo: description -> profile path,
        #: mirroring wx's ``MainFrame.input_profiles`` (populated once from
        #: the bundled reference profiles, see ``_lut3d_init_input_profiles``).
        self.input_profiles: dict[str, str] = {}
        #: The 3D LUT's own path, mirroring wx's ``self.lut3d_path`` -- kept
        #: current by :meth:`_apply_lut3d_path`.
        self.lut3d_path: str | None = None

        self._build_ui()
        self.init_menubar()
        self._build_file_menu()
        self._build_options_menu()
        self._build_tools_menu()
        self._build_help_menu()
        self.setup_language()
        # Run the committed Argyll measurement when a run is requested.
        self.measurement_requested.connect(self._on_measurement_requested)

        if not adopted_worker:
            self.worker.enumerate_displays_and_ports(silent=True)
        self._lut3d_init_input_profiles()
        self.update_controls()
        self._apply_initial_geometry()

    # -- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        """Assemble the tab bar, stacked settings panels and action buttons."""
        central = QWidget()
        central.setAutoFillBackground(True)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header_widget = self._build_header()
        self._tabbar_widget = self._build_tabbar()
        layout.addWidget(self._header_widget)
        layout.addWidget(self._tabbar_widget)

        self.stack = QStackedWidget()
        self._panels["display_instrument"] = self._build_display_instrument_tab()
        self._panels["calibration"] = self._build_calibration_tab()
        self._panels["profiling"] = self._build_profiling_tab()
        self._panels["lut3d"] = self._build_lut3d_tab()
        self._panels["verification"] = self._build_verification_tab()
        for key, _icon, _label in _TABS:
            self.stack.addWidget(self._panels[key])

        # wx wraps the equivalent tab content in a scrolled window
        # (``calpanel``, ``wxHSCROLL|wxVSCROLL``) since the per-tab info
        # panels below can make a tab taller than the window.
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.NoFrame)
        self._scroll_area.setWidget(self.stack)
        layout.addWidget(self._scroll_area, 1)

        self._button_bar_widget = self._build_button_bar()
        layout.addWidget(self._button_bar_widget)

        self.setCentralWidget(central)
        self._select_tab("display_instrument")

    def _apply_initial_geometry(self) -> None:
        """Size the window to fit the active tab without scrolling.

        Mirrors wx's ``MainFrame.set_size(True, True)`` startup call: rather
        than a fixed default size, wx sums the chrome (header/tab bar/button
        bar) and the currently selected panel's natural size, then clamps to
        the screen. The window is centered afterwards (see :meth:`showEvent`)
        when no saved position exists, matching wx's ``self.Center()``.
        """
        chrome_height = (
            self._header_widget.sizeHint().height()
            + self._tabbar_widget.sizeHint().height()
            + self._button_bar_widget.sizeHint().height()
        )
        content = self.stack.currentWidget().sizeHint()
        width = max(
            self._header_widget.sizeHint().width(),
            self._tabbar_widget.sizeHint().width(),
            self._button_bar_widget.sizeHint().width(),
            max(panel.sizeHint().width() for panel in self._panels.values()),
        )
        height = chrome_height + content.height()
        screen = self.screen() if self.windowHandle() else QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(width, available.width())
            height = min(height, available.height())
        self.resize(width, height)

    def _center_on_screen(self) -> None:
        """Center the window on its screen (wx's ``self.Center()`` fallback)."""
        screen = self.screen() if self.windowHandle() else QApplication.primaryScreen()
        if screen is None:
            return
        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def _build_file_menu(self) -> None:
        """Fill in the rest of the shared File menu (``mainmenu.xrc``'s ``menu.file``).

        The base File menu (just "Quit") is built by
        :meth:`~DisplayCAL.ui.base_window.BaseWindow.init_menubar`. This adds
        every other item in xrc order, ahead of :attr:`_file_menu_end_separator`:
        ``calibration.load``, ``testchart.set``, ``testchart.edit``,
        ``profile.set_save_path``, a separator, ``create_profile``,
        ``create_profile_from_edid``, ``install_display_profile``,
        ``profile.share``, ``profile.info``. Most of these just expose an
        already-ported handler (the same one a header-bar/tab icon button
        calls) as a menu action; only ``create_profile_from_edid`` and
        ``install_display_profile`` (a picked-profile install, distinct from
        :meth:`install_profile_btn_handler`'s current-profile shortcut) are new
        here, plus ``profile.share``, which mirrors wx's own already-disabled
        stub (see :meth:`_profile_share_action_handler`).
        """
        load_cal_action = QAction(lang.getstr("calibration.load"), self)
        load_cal_action.setShortcut("Ctrl+O")
        load_cal_action.triggered.connect(self.load_cal_btn_handler)
        self._file_menu.insertAction(self._file_menu_end_separator, load_cal_action)

        testchart_set_action = QAction(lang.getstr("testchart.set"), self)
        testchart_set_action.triggered.connect(self._testchart_btn_handler)
        self._file_menu.insertAction(self._file_menu_end_separator, testchart_set_action)

        testchart_edit_action = QAction(lang.getstr("testchart.edit"), self)
        testchart_edit_action.triggered.connect(self._create_testchart_btn_handler)
        self._file_menu.insertAction(
            self._file_menu_end_separator, testchart_edit_action
        )

        profile_save_path_action = QAction(lang.getstr("profile.set_save_path"), self)
        profile_save_path_action.triggered.connect(
            self._profile_save_path_btn_handler
        )
        self._file_menu.insertAction(
            self._file_menu_end_separator, profile_save_path_action
        )

        self._file_menu.insertSeparator(self._file_menu_end_separator)

        create_profile_action = QAction(lang.getstr("create_profile"), self)
        create_profile_action.triggered.connect(self._create_profile_action_handler)
        self._file_menu.insertAction(self._file_menu_end_separator, create_profile_action)

        create_profile_from_edid_action = QAction(
            lang.getstr("create_profile_from_edid"), self
        )
        create_profile_from_edid_action.triggered.connect(
            self._create_profile_from_edid_action_handler
        )
        self._file_menu.insertAction(
            self._file_menu_end_separator, create_profile_from_edid_action
        )

        install_display_profile_action = QAction(
            lang.getstr("install_display_profile"), self
        )
        install_display_profile_action.triggered.connect(
            self._select_install_profile_action_handler
        )
        self._file_menu.insertAction(
            self._file_menu_end_separator, install_display_profile_action
        )

        profile_share_action = QAction(lang.getstr("profile.share"), self)
        profile_share_action.triggered.connect(self._profile_share_action_handler)
        self._file_menu.insertAction(
            self._file_menu_end_separator, profile_share_action
        )

        profile_info_action = QAction(lang.getstr("profile.info"), self)
        profile_info_action.triggered.connect(self.profile_info_btn_handler)
        self._file_menu.insertAction(self._file_menu_end_separator, profile_info_action)

    def _create_profile_action_handler(self) -> None:
        """File menu "Create profile from measurement data..." handler.

        Qt port of ``create_profile_handler`` when reached with no explicit
        path, i.e. always, from this menu action: lets the user pick one or
        more ``.ti3``/ICC-profile source files (Argyll's ``average`` utility
        merges more than one into a single chart) and runs them through
        :meth:`_run_create_profile`.
        """
        if not check_set_argyll_bin():
            return
        if self._check_show_macos_bugs_warning(cal=False) is False:
            return
        default_dir, default_file = get_verified_path("last_ti3_path")
        paths, _filter = QFileDialog.getOpenFileNames(
            self,
            lang.getstr("create_profile"),
            os.path.join(default_dir, default_file or ""),
            f"{lang.getstr('filetype.icc_ti3')} (*.icc *.icm *.ti3)",
        )
        if not paths:
            return
        self._run_create_profile(paths)

    def _run_create_profile(
        self, paths: list[str], skip_ti3_check: bool = False
    ) -> None:
        """Build a profile from one or more measurement files.

        Qt port of the bulk of ``create_profile_handler``: collects/validates
        every source file via :mod:`DisplayCAL.create_profile`, averages more
        than one into a single chart, resolves the dispcal/targen options and
        display name/manufacturer the ``colprof`` run needs, then runs
        ``worker.create_profile`` through the same
        :class:`~DisplayCAL.ui.worker_runner.WorkerRunController` /
        :meth:`_on_profile_build_finished` pair
        :meth:`_build_profile_from_measurement` uses -- matching wx's own
        reuse of a single shared ``profile_finish`` consumer for both flows.

        Args:
            paths: The source ``.ti3``/ICC-profile paths, already picked (by
                the File-menu action's open dialog, or a single re-generated
                temp profile from :meth:`_measurement_file_check_action_handler`).
            skip_ti3_check: Skip the suspicious-patch sanity review. Used by
                :meth:`_measurement_file_check_action_handler`'s regenerate
                branch, which already ran that review itself.
        """
        collected: list[create_profile.CollectedMeasurement] = []
        for path in paths:
            if not os.path.exists(path):
                QMessageBox.critical(self, APPNAME, lang.getstr("file.missing", path))
                return
            try:
                item = create_profile.load_measurement_lines(path)
            except create_profile.CreateProfileError as exception:
                QMessageBox.critical(self, APPNAME, str(exception))
                return
            if not create_profile.has_calibration_curves(
                item.ti3_lines
            ) and not self._confirm_ti3_no_cal_info():
                return
            collected.append(item)
        if not collected:
            return

        source_filename, source_ext = create_profile.resolve_source_naming(
            [item.path for item in collected]
        )
        first_path = collected[0].path
        is_tmp = create_profile.is_temp_path(self.worker, first_path)
        if is_tmp:
            default_dir, default_file = get_verified_path("last_ti3_path")
        else:
            default_dir, default_file = os.path.split(first_path)
            setcfg("last_ti3_path", first_path)

        save_path, _filter = QFileDialog.getSaveFileName(
            self,
            lang.getstr("save_as"),
            os.path.join(default_dir, os.path.basename(source_filename) + PROFILE_EXT),
            f"{lang.getstr('filetype.icc')} (*{PROFILE_EXT})",
        )
        if not save_path:
            return
        save_dir, save_name = os.path.split(save_path)
        profile_save_path = os.path.join(save_dir, make_argyll_compatible_path(save_name))

        if not waccess(profile_save_path, os.W_OK):
            QMessageBox.critical(
                self,
                APPNAME,
                lang.getstr("error.access_denied.write", profile_save_path),
            )
            return
        _stem, ext = os.path.splitext(profile_save_path)
        if ext.lower() not in (".icc", ".icm"):
            profile_save_path += PROFILE_EXT
            if os.path.exists(
                profile_save_path
            ) and not self._confirm_overwrite_profile(profile_save_path):
                return

        setcfg("last_cal_or_icc_path", profile_save_path)
        setcfg("last_icc_path", profile_save_path)
        profile_name = os.path.basename(os.path.splitext(profile_save_path)[0])

        tmp_working_dir = self.worker.create_tempdir()
        if isinstance(tmp_working_dir, Exception):
            self.worker.wrapup(False)
            QMessageBox.critical(self, APPNAME, str(tmp_working_dir))
            return
        ti3_tmp_path = os.path.join(
            tmp_working_dir, make_argyll_compatible_path(f"{profile_name}.ti3")
        )

        source_path = first_path
        if len(collected) > 1:
            try:
                create_profile.merge_measurement_files(
                    self.worker, collected, tmp_working_dir, ti3_tmp_path
                )
            except create_profile.CreateProfileError as exception:
                self.worker.wrapup(False)
                QMessageBox.critical(self, APPNAME, str(exception))
                return
            source_path = ti3_tmp_path

        try:
            inputs = create_profile.resolve_profile_creation_inputs(
                source_path, source_ext, ti3_tmp_path, collected[-1].profile, is_tmp
            )
        except create_profile.CreateProfileError as exception:
            self.worker.wrapup(False)
            QMessageBox.critical(self, APPNAME, str(exception))
            return

        self.worker.options_dispcal = inputs.options_dispcal
        self.worker.options_targen = inputs.options_targen
        setcfg("calibration.file.previous", None)

        if not skip_ti3_check:
            proceed, _removed = self._check_measurement_sanity(inputs.ti3)
            if not proceed:
                self.worker.wrapup(False)
                return

        self.worker.interactive = False
        controller = self._ensure_run_controller()
        controller.run(
            self.worker.create_profile,
            self._on_profile_build_finished,
            wkwargs={
                "dst_path": profile_save_path,
                "display_name": inputs.display_name,
                "display_manufacturer": inputs.display_manufacturer,
                "tags": collected[-1].tags,
            },
            progress_msg=lang.getstr("create_profile"),
            pauseable=False,
        )

    def _confirm_ti3_no_cal_info(self) -> bool:
        """Confirm proceeding with a chart that has no calibration curves.

        Qt port of the 2-button ``ConfirmDialog`` in ``create_profile_handler``
        (one per collected file lacking a ``CAL`` section).
        """
        box = QMessageBox(self)
        box.setWindowTitle(APPNAME)
        box.setIcon(QMessageBox.Warning)
        box.setText(lang.getstr("dialog.ti3_no_cal_info"))
        ok_button = box.addButton(lang.getstr("continue"), QMessageBox.AcceptRole)
        box.addButton(lang.getstr("cancel"), QMessageBox.RejectRole)
        box.exec_()
        return box.clickedButton() is ok_button

    def _confirm_overwrite_profile(self, path: str) -> bool:
        """Confirm overwriting a profile path derived after appending an extension.

        Qt port of the second ``ConfirmDialog`` in ``create_profile_handler``,
        shown only when the save dialog's own overwrite prompt couldn't have
        caught it (the user-typed path had no ``.icc``/``.icm`` extension, so
        :data:`~DisplayCAL.config.PROFILE_EXT` was appended afterwards).
        """
        box = QMessageBox(self)
        box.setWindowTitle(APPNAME)
        box.setIcon(QMessageBox.Warning)
        box.setText(lang.getstr("dialog.confirm_overwrite", path))
        ok_button = box.addButton(lang.getstr("overwrite"), QMessageBox.AcceptRole)
        box.addButton(lang.getstr("cancel"), QMessageBox.RejectRole)
        box.exec_()
        return box.clickedButton() is ok_button

    def _create_profile_from_edid_action_handler(self) -> None:
        """File menu "Create profile from EDID..." handler.

        Qt port of ``create_profile_from_edid``: builds an ICC profile purely
        from the current display's EDID data (no measurement), then --
        matching wx -- optionally calculates its gamut view before handing
        off to :meth:`_on_profile_build_finished`.
        """
        edid = self.worker.get_display_edid()
        default_file = (
            edid.get("monitor_name", edid.get("ascii", str(edid["product_id"])))
            + PROFILE_EXT
        )
        default_dir = get_verified_path(
            None, os.path.join(getcfg("profile.save_path"), default_file)
        )[0]
        path, _filter = QFileDialog.getSaveFileName(
            self,
            lang.getstr("save_as"),
            os.path.join(default_dir, default_file),
            f"{lang.getstr('filetype.icc')} (*{PROFILE_EXT})",
        )
        if not path:
            return
        dirname, basename = os.path.split(path)
        profile_save_path = os.path.join(
            dirname, make_argyll_compatible_path(basename)
        )
        if not waccess(profile_save_path, os.W_OK):
            QMessageBox.critical(
                self,
                APPNAME,
                lang.getstr("error.access_denied.write", profile_save_path),
            )
            return
        profile = ICCProfile.from_edid(edid)
        try:
            profile.write(profile_save_path)
        except Exception as exception:
            QMessageBox.critical(self, APPNAME, str(exception))
            return
        if getcfg("profile.create_gamut_views"):
            controller = self._ensure_run_controller()
            controller.run(
                self.worker.calculate_gamut,
                lambda result: self._create_profile_from_edid_finish(
                    result, profile
                ),
                wargs=(profile_save_path,),
                progress_msg=lang.getstr("gamut.view.create"),
                pauseable=False,
            )
        else:
            self._create_profile_from_edid_finish(True, profile)

    def _create_profile_from_edid_finish(
        self, result: object, profile: ICCProfile
    ) -> None:
        """Finish creating a profile from EDID data.

        Qt port of ``create_profile_from_edid_finish``: on a successful gamut
        calculation, bakes its result plus the license/device-ID metadata into
        the profile before the final write; then hands off to
        :meth:`_on_profile_build_finished` like the measurement-driven paths
        do, dropping wx's separate install-offer dialog in favour of that
        shared one.
        """
        if isinstance(result, Exception):
            QMessageBox.critical(self, APPNAME, str(result))
            return
        if not result:
            return
        if isinstance(result, tuple):
            profile.set_gamut_metadata(result[0], result[1])
            prefix = profile.tags.meta.getvalue("prefix", b"", None)
            if isinstance(prefix, bytes):
                prefix = prefix.decode("utf-8")
            prefixes = prefix.split(",")
            profile.tags.meta["License"] = getcfg("profile.license")
            device_id = self.worker.get_device_id(quirk=False)
            if device_id:
                profile.tags.meta["MAPPING_device_id"] = device_id
                prefixes.append("MAPPING_")
                profile.tags.meta["prefix"] = ",".join(prefixes)
            profile.calculate_id()
        try:
            profile.write()
        except Exception as exception:
            QMessageBox.critical(self, APPNAME, str(exception))
            return
        self._on_profile_build_finished(profile.filename)

    def _select_install_profile_action_handler(self) -> None:
        """File menu "Install display profile..." handler.

        Qt port of ``select_install_profile_handler``: lets the user pick an
        arbitrary ICC profile file to install, unlike
        :meth:`install_profile_btn_handler`'s current-profile shortcut.
        """
        default_dir, default_file = get_verified_path("last_icc_path")
        path, _filter = QFileDialog.getOpenFileName(
            self,
            lang.getstr("install_display_profile"),
            os.path.join(default_dir, default_file or ""),
            f"{lang.getstr('filetype.icc')} (*.icc *.icm)",
        )
        if not path:
            return
        setcfg("last_icc_path", path)
        setcfg("last_cal_or_icc_path", path)
        if self._install_profile_window is None:
            self._install_profile_window = InstallProfileWindow()
        self._install_profile_window.load_profile(path)
        self._install_profile_window.show()
        self._install_profile_window.raise_()
        self._install_profile_window.activateWindow()

    def _profile_share_action_handler(self) -> None:
        """File menu "Upload profile..." handler.

        wx's own ``profile_share_handler`` is already unconditionally disabled
        (icc.opensuse.org, the profile-sharing service it used, has been down
        since #194) -- this mirrors that same notice rather than porting the
        large, permanently-unreachable body below it.
        """
        QMessageBox.critical(
            self,
            APPNAME,
            "icc.opensuse.org is not working anymore\n"
            "This functionality is temporarily disabled.",
        )

    def _build_options_menu(self) -> None:
        """Add an Options menu with the "show advanced options" toggle.

        Toolkit-neutral scope note: wx's ``menu.options`` also carries the
        startup-sound/splash/fancy-progress/3D-LUT-tab-visibility toggles and
        a whole "advanced" submenu of debug switches (``use_separate_lut_access``,
        ``enable_argyll_debug``, ``extra_args``, etc., see ``mainmenu.xrc``);
        none of that is reproduced here, only ``show_advanced_options`` itself,
        since it's the one setting that gates the visibility of controls this
        window already has.
        """
        options_menu = self.menuBar().addMenu(f"&{lang.getstr('menu.options')}")
        self.show_advanced_options_action = options_menu.addAction(
            lang.getstr("show_advanced_options")
        )
        self.show_advanced_options_action.setCheckable(True)
        self.show_advanced_options_action.setChecked(
            bool(getcfg("show_advanced_options"))
        )
        self.show_advanced_options_action.toggled.connect(
            self._show_advanced_options_toggled
        )

    def _build_tools_menu(self) -> None:
        """Add a Tools menu with the colorimeter-correction and Advanced actions.

        Toolkit-neutral scope note: wx's ``menu.tools`` is a large menu (display
        detection, video-card-gamma-table reset, instrument-driver install,
        reports, advanced debug tools, ...); only the colorimeter-correction
        import/upload entries and part of the ``menu.tools.advanced`` submenu
        are reproduced here. The other three entries of wx's
        ``colorimeter_correction_matrix_file`` submenu are already reachable
        elsewhere on this window: "choose" is the CCMX/CCSS combo on the
        Display & Instrument tab, "web check" is
        :meth:`colorimeter_correction_web_btn_handler` (same tab), and "create"
        is :meth:`colorimeter_correction_create_btn_handler` (same tab).

        All six entries of ``menu.tools.advanced`` are now reproduced:
        "synthicc.create" (:meth:`_synthicc_create_action_handler`, a
        cross-link to the already-ported standalone tool,
        ``ui/tools/synth_profile.py``), plus one entry with no wx
        precedent -- the standalone 3D LUT maker
        (:meth:`_lut3d_window_action_handler`, cross-linking
        ``ui/tools/lut3d.py``'s ``LUT3DWindow``, which wx only ever exposed
        as its own console-script app, never from a menu) -- "profile.b2a.hires"
        (:meth:`_profile_hires_b2a_action_handler`), "measure.testchart"
        (:meth:`_measure_testchart_action_handler`), "specplot.run"
        (:meth:`_specplot_action_handler`), "measurement_file.check_sanity"
        (:meth:`_measurement_file_check_action_handler`), and
        "measurement_file.check_sanity.auto"
        (:meth:`_measurement_file_check_auto_toggled`).

        Of wx's ``instrument`` submenu, only "enable_spyder2" is reproduced
        (:meth:`_enable_spyder2`, backed by
        :mod:`DisplayCAL.ui.spyder2_enable`); the Argyll instrument
        configuration-file / driver install-uninstall entries and
        "calibrate_instrument" are not (they need the still-unported
        driver-installer / `oeminst` plumbing wx's own handlers wrap).
        """
        tools_menu = self.menuBar().addMenu(f"&{lang.getstr('menu.tools')}")
        ccxx_menu = tools_menu.addMenu(
            lang.getstr("colorimeter_correction_matrix_file")
        )
        import_action = ccxx_menu.addAction(
            lang.getstr("colorimeter_correction.import")
        )
        import_action.triggered.connect(self._ccxx_import_action_handler)
        upload_action = ccxx_menu.addAction(
            lang.getstr("colorimeter_correction.upload")
        )
        upload_action.triggered.connect(self._ccxx_upload_action_handler)

        instrument_menu = tools_menu.addMenu(lang.getstr("instrument"))
        self.enable_spyder2_action = instrument_menu.addAction(
            lang.getstr("enable_spyder2")
        )
        self.enable_spyder2_action.setCheckable(True)
        self.enable_spyder2_action.triggered.connect(
            lambda: self._enable_spyder2(recheck=False)
        )
        self._update_spyder2_menu_state()

        advanced_menu = tools_menu.addMenu(lang.getstr("advanced"))
        synthicc_action = advanced_menu.addAction(lang.getstr("synthicc.create"))
        synthicc_action.triggered.connect(self._synthicc_create_action_handler)
        lut3d_action = advanced_menu.addAction(lang.getstr("3dlut.frame.title"))
        lut3d_action.triggered.connect(self._lut3d_window_action_handler)
        advanced_menu.addSeparator()
        hires_b2a_action = advanced_menu.addAction(lang.getstr("profile.b2a.hires"))
        hires_b2a_action.triggered.connect(self._profile_hires_b2a_action_handler)
        advanced_menu.addSeparator()
        measure_testchart_action = advanced_menu.addAction(
            lang.getstr("measure.testchart")
        )
        measure_testchart_action.triggered.connect(
            self._measure_testchart_action_handler
        )
        specplot_action = advanced_menu.addAction(lang.getstr("specplot.run"))
        specplot_action.triggered.connect(self._specplot_action_handler)
        check_sanity_action = advanced_menu.addAction(
            lang.getstr("measurement_file.check_sanity")
        )
        check_sanity_action.triggered.connect(
            self._measurement_file_check_action_handler
        )
        self.measurement_file_check_auto_action = advanced_menu.addAction(
            lang.getstr("measurement_file.check_sanity.auto")
        )
        self.measurement_file_check_auto_action.setCheckable(True)
        self.measurement_file_check_auto_action.setChecked(
            bool(getcfg("ti3.check_sanity.auto"))
        )
        self.measurement_file_check_auto_action.toggled.connect(
            self._measurement_file_check_auto_toggled
        )

    def _ccxx_import_action_handler(self) -> None:
        """Auto-discover and import colorimeter corrections from disk."""
        controller = ImportController(self.worker, self)
        controller.finished.connect(self._on_ccxx_import_finished)
        self._ccxx_import_controller = controller
        controller.run()

    def _on_ccxx_import_finished(self) -> None:
        self._ccxx_import_controller = None
        self.update_colorimeter_correction_matrix_ctrl_items(force=True)

    def _ccxx_upload_action_handler(self) -> None:
        """Upload a CCMX/CCSS correction file to the online database."""
        controller = UploadController(self.worker, self)
        controller.finished.connect(self._on_ccxx_upload_finished)
        self._ccxx_upload_controller = controller
        controller.run()

    def _on_ccxx_upload_finished(self) -> None:
        self._ccxx_upload_controller = None

    def _build_help_menu(self) -> None:
        """Add a Help menu matching wx's ``menu.help`` (``mainmenu.xrc``).

        Order mirrors wx's actual menu (readme/license, separator, website/
        support/bug-report, separator, the update-check pair, then About --
        wx appends its About item last too, except on macOS where
        ``QAction.AboutRole`` relocates it into the app menu automatically,
        same as wx's ``SetMacAboutMenuItemId``).
        """
        help_menu = self._help_menu = self.menuBar().addMenu(
            f"&{lang.getstr('menu.help')}"
        )

        readme_path = (
            get_data_path("README-fr.html") if lang.getcode() == "fr" else None
        ) or get_data_path("README.html")
        readme_action = help_menu.addAction(lang.getstr("readme"))
        readme_action.setEnabled(isinstance(readme_path, str))
        readme_action.triggered.connect(
            lambda: launch_file(readme_path) if readme_path else None
        )

        license_path = get_data_path("LICENSE.txt")
        license_enabled = isinstance(license_path, str) or os.path.isfile(
            "/usr/share/common-licenses/GPL-3"
        )
        license_path = license_path or "/usr/share/common-licenses/GPL-3"
        license_action = help_menu.addAction(lang.getstr("license"))
        license_action.setEnabled(license_enabled)
        license_action.triggered.connect(lambda: launch_file(license_path))

        help_menu.addSeparator()
        website_action = help_menu.addAction(lang.getstr("go_to_website"))
        website_action.triggered.connect(
            lambda: launch_file(f"https://{DOMAIN}/")
        )
        support_action = help_menu.addAction(lang.getstr("help_support"))
        support_action.triggered.connect(
            lambda: launch_file(f"{DEVELOPMENT_HOME_PAGE}/issues")
        )
        bug_report_action = help_menu.addAction(lang.getstr("bug_report"))
        bug_report_action.triggered.connect(
            lambda: launch_file(f"{DEVELOPMENT_HOME_PAGE}/issues")
        )

        help_menu.addSeparator()
        self.update_check_action = help_menu.addAction(lang.getstr("update_check"))
        self.update_check_action.triggered.connect(
            self._check_for_updates_action_handler
        )
        self.update_check_onstartup_action = help_menu.addAction(
            lang.getstr("update_check.onstartup")
        )
        self.update_check_onstartup_action.setCheckable(True)
        self.update_check_onstartup_action.setChecked(bool(getcfg("update_check")))
        self.update_check_onstartup_action.toggled.connect(
            self._update_check_onstartup_toggled
        )

        help_menu.addSeparator()
        about_action = help_menu.addAction(lang.getstr("menu.about"))
        about_action.setMenuRole(QAction.AboutRole)
        about_action.triggered.connect(self._about_action_handler)

    def _about_action_handler(self) -> None:
        """Show the "About DisplayCAL" dialog, reusing it if already open."""
        if self._about_window is None:
            self._about_window = AboutWindow(self.worker, self)
        self._about_window.show()
        self._about_window.raise_()
        self._about_window.activateWindow()

    def _update_check_onstartup_toggled(self, checked: bool) -> None:
        setcfg("update_check", int(checked))

    def _check_for_updates_action_handler(self) -> None:
        """Manually check for DisplayCAL/ArgyllCMS updates (Help menu)."""
        self._run_update_check(silent=False)

    def _run_update_check(self, silent: bool) -> None:
        controller = UpdateCheckController(self.worker, self)
        controller.finished.connect(
            lambda found: self._on_update_check_finished(found, silent)
        )
        self._update_check_controller = controller
        controller.run(silent=silent)

    def _on_update_check_finished(self, found: bool, silent: bool) -> None:
        self._update_check_controller = None
        self.update_check_onstartup_action.setChecked(bool(getcfg("update_check")))
        if silent and not found:
            self._run_instrument_setup_and_donation_check()

    def run_post_launch_checks(self) -> None:
        """Silently check for updates, then instrument setup / donation nag.

        Qt port of the tail of wx's ``StartupFrame.setup_frame_finish``: once
        the main window is shown, either kick off a silent update check
        (chaining into the instrument-setup / donation check when it finds
        nothing) or go straight to the instrument-setup / donation check,
        depending on the persisted ``update_check`` setting. Called by
        :mod:`DisplayCAL.ui.startup` once :class:`MainWindow` is shown; not
        called by this module's own standalone ``main()`` so that manually
        exercising the window during development doesn't nag about updates.
        """
        if getcfg("update_check"):
            self._run_update_check(silent=True)
        else:
            self._run_instrument_setup_and_donation_check()

    def _run_instrument_setup_and_donation_check(self) -> None:
        """Qt port of ``MainFrame.check_instrument_setup``'s dispatch."""
        needs = instrument_setup.resolve_instrument_setup_needs(
            self.worker, self._ccmx_catalog.instruments.values()
        )
        if needs.needs_spyder2_enable:
            self._enable_spyder2(recheck=needs.recheck_after_spyder2)
            return
        if needs.needs_correction_import:
            controller = ImportController(self.worker, self)
            controller.finished.connect(self._on_instrument_setup_import_finished)
            self._instrument_setup_import_controller = controller
            controller.run()
            return
        self._show_donation_message_if_needed()

    def _on_instrument_setup_import_finished(self) -> None:
        self._instrument_setup_import_controller = None
        self.update_colorimeter_correction_matrix_ctrl_items(force=True)
        self._show_donation_message_if_needed()

    def _enable_spyder2(self, recheck: bool = False) -> None:
        """Run the Spyder2 firmware-enable wizard (Tools menu / instrument setup).

        Args:
            recheck: whether the caller wants a follow-up step run once the
                wizard completes (port of wx's ``enable_spyder2_handler``
                ``check_instrument_setup`` bool: True when other
                colorimeter-correction imports are also pending). Only set
                from the automatic instrument-setup check; the Tools-menu
                action passes False, matching wx's own menu handler (called
                with no callafter).
        """
        controller = Spyder2EnableController(self.worker, self)
        controller.finished.connect(
            lambda attempted: self._on_spyder2_enable_finished(attempted, recheck)
        )
        self._spyder2_enable_controller = controller
        controller.run()

    def _on_spyder2_enable_finished(self, attempted: bool, recheck: bool) -> None:
        self._spyder2_enable_controller = None
        self._update_spyder2_menu_state()
        if attempted:
            # A full attempt (success or failure) ran through the async
            # producer/consumer, matching wx's ``enable_spyder2_consumer``:
            # re-run the whole check from scratch if other imports are
            # pending (which may show this same wizard again, e.g. after a
            # failed attempt -- faithful to wx, not a bug), else go straight
            # to the donation nag.
            if recheck:
                self._run_instrument_setup_and_donation_check()
            else:
                self._show_donation_message_if_needed()
            return
        # The dialog/file-picker was cancelled before anything ran -- wx's
        # synchronous fall-through in ``check_instrument_setup`` (the async
        # worker call was never dispatched) skips re-checking Spyder2 itself
        # and goes straight to whatever comes after it.
        if recheck:
            controller = ImportController(self.worker, self)
            controller.finished.connect(self._on_instrument_setup_import_finished)
            self._instrument_setup_import_controller = controller
            controller.run()
        else:
            self._show_donation_message_if_needed()

    def _update_spyder2_menu_state(self) -> None:
        """Port of wx's ``menuitem_enable_spyder2`` enable/check refresh."""
        spyd2en = bool(get_argyll_util("spyd2en"))
        self.enable_spyder2_action.setEnabled(spyd2en)
        self.enable_spyder2_action.setChecked(
            spyd2en and self.worker.spyder2_firmware_exists()
        )

    def _show_donation_message_if_needed(self) -> None:
        if instrument_setup.should_show_donation_message():
            _DonationDialog(self).exec_()

    def _show_advanced_options_toggled(self, checked: bool) -> None:
        """Persist the ``show_advanced_options`` flag and refresh gated rows."""
        if self._updating:
            return
        setcfg("show_advanced_options", int(checked))
        self._update_advanced_options_visibility()

    def _update_advanced_options_visibility(self) -> None:
        """Show or hide every control gated behind ``show_advanced_options``.

        Mirrors wx's ``MainFrame.show_advanced_options_handler`` and the
        ``show_display_delay_ctrls`` / ``show_ffp_ctrls`` /
        ``show_output_levels_ctrls`` helpers it calls, plus the 3D LUT tab's
        ``LUT3DMixin.lut3d_show_trc_controls`` / ``MainFrame.lut3d_show_controls``
        gating (the gamut-mapping-mode / apply-cal-on-create rows, and the
        TRC/HDR block's ``show_advanced_options``-gated rows, both driven by
        :meth:`_apply_lut3d_visibility`), and the whitepoint colour-temperature
        locus row (Calibration tab, gated via :meth:`_apply_whitepoint_mode`).
        The gamap button (part of the profile-type row) and the
        testchart-patch-sequence row are gated below.
        """
        show_advanced = bool(getcfg("show_advanced_options"))
        self.show_advanced_options_action.setChecked(show_advanced)

        self._apply_whitepoint_mode()
        self._profiling_form.setRowVisible(
            self._profile_type_row_widget, show_advanced
        )
        self._testchart_patch_sequence_row_gate()
        self._calibration_form.setRowVisible(
            self._black_luminance_row_widget, show_advanced
        )

        not_untethered = config.get_display_name(None, True) != "Untethered"
        self._delay_form.setRowVisible(
            self._override_delay_row_widget, show_advanced and not_untethered
        )
        self._delay_form.setRowVisible(
            self._override_settle_row_widget,
            show_advanced
            and not_untethered
            and getcfg("argyll.version") >= "1.7",
        )

        display_name = config.get_display_name(None, True)
        ffp_visible = show_advanced and (
            (
                display_name == "Prisma"
                and not DEFAULTS["patterngenerator.prisma.argyll"]
            )
            or display_name == "Resolve"
            or (
                display_name == "madVR"
                and (
                    sys.platform != "win32"
                    or not getcfg("madtpg.native")
                    or bool(self.worker.argyll_virtual_display)
                )
            )
        )
        self._ffp_row_widget.setVisible(ffp_visible)

        self._output_levels_row_widget.setVisible(
            show_advanced and display_name not in ("madVR", "Untethered")
        )

        self._apply_trc_mode()
        self._update_observer_visibility()
        self._apply_lut3d_visibility()

    def _update_observer_visibility(self) -> None:
        """Show the observer row per wx's ``MainFrame.show_observer_ctrl``."""
        show = bool(
            (getcfg("calibration.interactive_display_adjustment") or getcfg("trc"))
            and getcfg("show_advanced_options")
            and self.worker.instrument_can_use_nondefault_observer()
        )
        self._calibration_form.setRowVisible(self.observer_ctrl, show)

    #: wx's ``get_header(x=80)`` tagline inset, which is also where the "D" of
    #: the "DisplayCAL" wordmark starts in ``theme/header.png``; the
    #: "Settings" bar below lines its label up with the same x so the two
    #: rows read as one column, matching wx.
    _HEADER_LOGO_INSET = 80

    def _build_header(self) -> QWidget:
        """Build the calibration/profile-file banner atop the tab bar.

        Mirrors ``main.xrc``'s ``headerbordertop`` (green strip) + ``header``
        (logo/tagline banner) + ``headerpanel`` (the functional current-file
        bar: label, ``calibration_file_ctrl`` selector, and the info / load /
        archive / delete / install-profile buttons) stack. The wordmark reuses
        wx's own ``theme/header.png`` artwork (cropped to its logical banner
        region) instead of a separately-assembled icon+text label, the banner
        strip carries the same top-to-bottom blue gradient baked into that
        artwork, and the bar's icon buttons are recolored white to mirror wx's
        on-the-fly "-inverted" bitmaps (they sit on a permanently dark blue
        bar regardless of the app's light/dark theme).
        """
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        strip = QWidget()
        strip.setFixedHeight(6)
        strip.setStyleSheet("background-color: #66CC00;")
        outer.addWidget(strip)

        # wx overlays the tagline directly on the banner bitmap (``get_header``,
        # white text near the bottom, starting at the same x as the "D" in the
        # wordmark); ``HeaderBanner`` paints both explicitly for the same
        # effect instead of layering two widgets.
        banner = HeaderBanner(
            header_banner_pixmap(),
            lang.getstr("header"),
            self._HEADER_LOGO_INSET,
        )
        banner.setFixedHeight(HEADER_BANNER_SIZE[1])
        # Matches the actual gradient sampled from ``theme/header@2x.png``: it
        # reaches its final blue by the vertical midpoint and stays flat below
        # that (a plain 2-stop linear gradient over-darkens the top half).
        banner.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            " stop:0 #093d75, stop:0.5 #0e59a9, stop:1 #0e59a9);"
        )
        outer.addWidget(banner)

        bar = QWidget()
        bar.setObjectName("headerpanel")
        # Scoped to the object name (not a bare "QWidget { ... }" rule) so the
        # background doesn't cascade into descendants: any style sheet on a
        # widget forces Qt to draw its children (like the combo box below) via
        # the CSS style engine instead of the native one, losing the native
        # chevron / popup chrome the rest of the app's combo boxes keep.
        bar.setStyleSheet("QWidget#headerpanel { background-color: #0e59a9; }")
        bar_row = QHBoxLayout(bar)
        bar_row.setContentsMargins(self._HEADER_LOGO_INSET, 8, 16, 8)
        bar_row.setSpacing(8)

        file_label = QLabel(lang.getstr("calibration.file"))
        file_label.setStyleSheet("color: white;")
        bar_row.addWidget(file_label)

        self.calibration_file_ctrl = QComboBox()
        self.calibration_file_ctrl.setMinimumWidth(220)
        self.calibration_file_ctrl.currentIndexChanged.connect(
            self.calibration_file_ctrl_handler
        )
        bar_row.addWidget(self.calibration_file_ctrl, 1)

        self.profile_info_btn = self._header_tool_button(
            "info", "profile.info", self.profile_info_btn_handler
        )
        bar_row.addWidget(self.profile_info_btn)

        self.calibration_file_btn = self._header_tool_button(
            "document-open", "calibration.load", self.load_cal_btn_handler
        )
        bar_row.addWidget(self.calibration_file_btn)

        self.create_session_archive_btn = self._header_tool_button(
            "package-x-generic",
            "archive.create",
            self.create_session_archive_handler,
        )
        bar_row.addWidget(self.create_session_archive_btn)

        self.delete_calibration_btn = self._header_tool_button(
            "edit-delete", "delete", self.delete_calibration_handler
        )
        bar_row.addWidget(self.delete_calibration_btn)

        self.install_profile_btn = self._header_tool_button(
            "install", "profile.install", self.install_profile_btn_handler
        )
        bar_row.addWidget(self.install_profile_btn)

        outer.addWidget(bar)
        return container

    @staticmethod
    def _header_icon_pixmap(size: int, name: str) -> QPixmap:
        """Recolor a themed icon white, mirroring wx's "-inverted" bitmaps.

        The header bar's icon buttons sit on a permanently dark blue banner,
        so (like wx) they always use the white variant regardless of the
        app's light/dark theme.
        """
        pixmap = get_theme_pixmap(size, name)
        if pixmap.isNull():
            return pixmap
        white = QPixmap(pixmap.size())
        white.setDevicePixelRatio(pixmap.devicePixelRatio())
        white.fill(Qt.transparent)
        painter = QPainter(white)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(white.rect(), QColor("white"))
        painter.end()
        return white

    def _pixmap(self, size: int, name: str) -> QPixmap:
        """Return a themed icon pixmap for the app's current light/dark scheme.

        Unlike :meth:`_header_icon_pixmap` (always white, for the permanently
        dark blue header banner), this recolors monochrome glyphs only when
        the app is in its dark scheme, matching wx's on-the-fly inversion.
        """
        return get_themed_pixmap(size, name, is_dark(self))

    @classmethod
    def _header_tool_button(
        cls, icon_name: str, tooltip_key: str, slot: Callable[[], None]
    ) -> QToolButton:
        """Build one of the header bar's plain icon buttons."""
        button = QToolButton()
        pixmap = cls._header_icon_pixmap(16, icon_name)
        if not pixmap.isNull():
            button.setIcon(pixmap)
        button.setToolTip(lang.getstr(tooltip_key))
        button.setAutoRaise(True)
        button.clicked.connect(lambda _checked=False: slot())
        return button

    #: wx has no boxed frame around the Display tab's "Display"/"Instrument"
    #: sections, just a bold section-title label (see ``display_box_label`` /
    #: ``instrument_box_label`` in ``main.xrc``); drop the native QGroupBox
    #: border/frame but keep its bold title, to match.
    _FLAT_GROUPBOX_STYLE = (
        "QGroupBox {"
        " border: none;"
        " margin-top: 1.5ex;"
        " font-weight: bold;"
        "}"
        "QGroupBox::title {"
        " subcontrol-origin: margin;"
        " left: 0px;"
        " padding: 0 0 4px 0;"
        "}"
    )

    #: Flat look for the tab bar's toggle buttons (wx's ``platebtn.PlateButton``
    #: idle state has no visible background; only a soft highlight distinguishes
    #: the checked/hovered button, instead of Qt's native checked-button chrome).
    _TAB_BUTTON_STYLE = (
        "QToolButton {"
        " border: none;"
        " background: transparent;"
        " padding: 4px 10px;"
        "}"
        "QToolButton:checked {"
        " background: rgba(128, 128, 128, 60);"
        " border-radius: 4px;"
        "}"
        "QToolButton:hover:!checked {"
        " background: rgba(128, 128, 128, 30);"
        " border-radius: 4px;"
        "}"
    )

    def _build_tabbar(self) -> QWidget:
        """Build the exclusive toggle-button tab bar."""
        bar = QWidget()
        bar.setObjectName("tabpanel")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 8, 16, 8)
        row.setSpacing(24)

        # wx centers the tab buttons (equal stretch spacers on both sides of
        # the button row); match that instead of left-aligning them.
        row.addStretch(1)
        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        for key, icon_name, label_key in _TABS:
            button = QToolButton()
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.setIconSize(QSize(32, 32))
            button.setStyleSheet(self._TAB_BUTTON_STYLE)
            pixmap = self._pixmap(32, icon_name)
            if not pixmap.isNull():
                button.setIcon(pixmap)
            button.setText(lang.getstr(label_key))
            # ``toggled`` (not ``clicked``): macOS accessibility clients (incl.
            # VoiceOver, and the ``AXPress`` action used by automated UI
            # testing) toggle a checkable ``QToolButton``'s state directly
            # without necessarily emitting ``clicked``, which would otherwise
            # leave the tab visually checked but the stack not switched.
            button.toggled.connect(
                lambda checked, k=key: self._select_tab(k) if checked else None
            )
            self._tab_group.addButton(button)
            self._tab_buttons[key] = button
            row.addWidget(button)
        row.addStretch(1)
        return bar

    @staticmethod
    def _info_text_html(label_key: str) -> str:
        """Convert a wx ``StaticFancyText`` markup string to Qt rich text.

        wx's markup (``<font weight='bold'>...</font>``, blank-line
        paragraph breaks) isn't valid Qt rich text; translate it rather
        than re-authoring the (long, translated) ``info.*`` strings.
        """
        text = lang.getstr(label_key)
        text = text.replace("<font weight='bold'>", "<b>").replace(
            "</font>", "</b>"
        )
        paragraphs = text.split("\n\n")
        return "".join(
            f"<p style='margin:0 0 8px 0'>{paragraph.replace(chr(10), '<br>')}</p>"
            for paragraph in paragraphs
        )

    @staticmethod
    def _build_settings_header(label_key: str) -> QLabel:
        """Build the bold "<Tab> settings" heading wx shows atop a tab.

        Matches ``main.xrc``'s ``calibration_settings_label`` /
        ``profile_settings_label`` / ``lut3d_settings_label`` (and
        ``report.xrc``'s ``mr_settings_label``), bolded in code by wx's
        ``init_controls`` (``display_cal.py:3551-3563``) rather than in the
        xrc itself. The Display & Instrument tab has no such header in wx
        either, so it doesn't call this.
        """
        label = QLabel(lang.getstr(label_key))
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        return label

    def _build_info_panel(
        self, *rows: tuple[str, str], extra: QWidget | None = None
    ) -> QWidget:
        """Build a wx ``*_settings_info_panel`` equivalent.

        Each row is an ``(icon_name, label_key)`` pair, rendered as a
        32x32 themed icon beside word-wrapped rich text, matching wx's
        white-background info panels (dialog-information/clock icon plus
        a ``StaticFancyText``) shown at the bottom of each settings tab.
        ``extra``, if given, is appended below the rows indented to align
        under the text column (matching wx appending extra controls, e.g.
        ``display_tech_info_show_btn``, straight to the panel's sizer).
        """
        panel = QWidget()
        # wx's info panels don't set an explicit background either (they
        # inherit the app's BGCOLOUR/FGCOLOUR like everything else); only the
        # separator above them (wx's ``shadow-bordertop.png``) is distinct.
        panel.setStyleSheet("border-top: 1px solid palette(mid);")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(1, 1)
        for row_index, (icon_name, label_key) in enumerate(rows):
            icon_label = QLabel()
            pixmap = self._pixmap(32, icon_name)
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap)
            icon_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
            grid.addWidget(icon_label, row_index, 0)
            text_label = QLabel(self._info_text_html(label_key))
            text_label.setTextFormat(Qt.RichText)
            text_label.setWordWrap(True)
            text_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            grid.addWidget(text_label, row_index, 1)
        # Keep icon/text rows packed at the top; push leftover vertical
        # space (from the ``outer.addWidget(panel, 1)`` stretch factor at
        # each tab's call site) into a trailing spacer row instead.
        grid.setRowStretch(len(rows), 1)
        outer.addLayout(grid)
        if extra is not None:
            extra_row = QHBoxLayout()
            extra_row.setContentsMargins(32 + 12, 0, 0, 0)
            extra_row.addWidget(extra)
            extra_row.addStretch(1)
            outer.addLayout(extra_row)
        return panel

    def _build_display_instrument_tab(self) -> QWidget:
        """Build the Display & Instrument settings panel."""
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        columns = QHBoxLayout()

        display_box = QGroupBox(lang.getstr("display"))
        display_box.setStyleSheet(self._FLAT_GROUPBOX_STYLE)
        display_outer = QVBoxLayout(display_box)
        display_row = QHBoxLayout()
        display_form = QFormLayout()
        self.display_ctrl = QComboBox()
        self.display_ctrl.currentIndexChanged.connect(self.display_ctrl_handler)
        display_form.addRow(lang.getstr("display"), self.display_ctrl)
        self.display_lut_ctrl = QComboBox()
        self.display_lut_ctrl.currentIndexChanged.connect(
            self.display_lut_ctrl_handler
        )
        display_form.addRow(lang.getstr("lut_access"), self.display_lut_ctrl)
        self._display_lut_form = display_form
        display_row.addLayout(display_form, 1)

        self.display_lut_link_ctrl = QToolButton()
        self.display_lut_link_ctrl.setCheckable(True)
        self.display_lut_link_ctrl.setAutoRaise(True)
        self.display_lut_link_ctrl.setToolTip(lang.getstr("display_lut.link"))
        self.display_lut_link_ctrl.toggled.connect(
            self.display_lut_link_ctrl_handler
        )
        display_row.addWidget(self.display_lut_link_ctrl)

        self.detect_displays_and_ports_btn = QToolButton()
        self.detect_displays_and_ports_btn.setAutoRaise(True)
        self.detect_displays_and_ports_btn.setToolTip(
            lang.getstr("detect_displays_and_ports")
        )
        refresh_pixmap = self._pixmap(16, "stock_refresh")
        if not refresh_pixmap.isNull():
            self.detect_displays_and_ports_btn.setIcon(refresh_pixmap)
        self.detect_displays_and_ports_btn.clicked.connect(
            self.detect_displays_and_ports_btn_handler
        )
        display_row.addWidget(self.detect_displays_and_ports_btn)
        display_outer.addLayout(display_row)

        self.whitelevel_drift_compensation_cb = QCheckBox(
            lang.getstr("drift_compensation.whitelevel")
        )
        self.whitelevel_drift_compensation_cb.setToolTip(
            lang.getstr("drift_compensation.whitelevel.info")
        )
        self._add_check(
            self.whitelevel_drift_compensation_cb, "drift_compensation.whitelevel"
        )
        display_outer.addWidget(self.whitelevel_drift_compensation_cb)
        columns.addWidget(display_box, 1)

        instrument_box = QGroupBox(lang.getstr("instrument"))
        instrument_box.setStyleSheet(self._FLAT_GROUPBOX_STYLE)
        instrument_outer = QVBoxLayout(instrument_box)
        instrument_form = QFormLayout()
        self.comport_ctrl = QComboBox()
        self.comport_ctrl.currentIndexChanged.connect(self.comport_ctrl_handler)
        instrument_form.addRow(lang.getstr("instrument"), self.comport_ctrl)
        self.measurement_mode_ctrl = QComboBox()
        self.measurement_mode_ctrl.currentIndexChanged.connect(
            self.measurement_mode_ctrl_handler
        )
        instrument_form.addRow(
            lang.getstr("measurement_mode"), self.measurement_mode_ctrl
        )
        instrument_outer.addLayout(instrument_form)

        self.blacklevel_drift_compensation_cb = QCheckBox(
            lang.getstr("drift_compensation.blacklevel")
        )
        self.blacklevel_drift_compensation_cb.setToolTip(
            lang.getstr("drift_compensation.blacklevel.info")
        )
        self._add_check(
            self.blacklevel_drift_compensation_cb, "drift_compensation.blacklevel"
        )
        instrument_outer.addWidget(self.blacklevel_drift_compensation_cb)
        columns.addWidget(instrument_box, 1)

        outer.addLayout(columns)

        # Display update delay / settle time overrides.
        delay_form = QFormLayout()
        self._delay_form = delay_form
        override_delay_row = QHBoxLayout()
        self.override_min_display_update_delay_ms_cb = QCheckBox(
            lang.getstr("measure.override_min_display_update_delay_ms")
        )
        self.override_min_display_update_delay_ms_cb.toggled.connect(
            self._display_delay_override_toggled
        )
        override_delay_row.addWidget(self.override_min_display_update_delay_ms_cb)
        self.min_display_update_delay_ms_ctrl = QSpinBox()
        min_val, max_val = config.VALID_RANGES["measure.min_display_update_delay_ms"]
        self.min_display_update_delay_ms_ctrl.setRange(min_val, max_val)
        self.min_display_update_delay_ms_ctrl.valueChanged.connect(
            self._min_display_update_delay_ms_changed
        )
        override_delay_row.addWidget(self.min_display_update_delay_ms_ctrl)
        self.min_display_update_delay_ms_label = QLabel("ms")
        override_delay_row.addWidget(self.min_display_update_delay_ms_label)
        override_delay_row.addStretch(1)
        self._override_delay_row_widget = self._wrap(override_delay_row)
        delay_form.addRow("", self._override_delay_row_widget)

        override_settle_row = QHBoxLayout()
        self.override_display_settle_time_mult_cb = QCheckBox(
            lang.getstr("measure.override_display_settle_time_mult")
        )
        self.override_display_settle_time_mult_cb.toggled.connect(
            self._display_settle_time_mult_override_toggled
        )
        override_settle_row.addWidget(self.override_display_settle_time_mult_cb)
        self.display_settle_time_mult_ctrl = QDoubleSpinBox()
        min_val, max_val = config.VALID_RANGES["measure.display_settle_time_mult"]
        self.display_settle_time_mult_ctrl.setDecimals(6)
        self.display_settle_time_mult_ctrl.setSingleStep(min_val)
        self.display_settle_time_mult_ctrl.setRange(min_val, max_val)
        self.display_settle_time_mult_ctrl.valueChanged.connect(
            self._display_settle_time_mult_changed
        )
        override_settle_row.addWidget(self.display_settle_time_mult_ctrl)
        override_settle_row.addStretch(1)
        self._override_settle_row_widget = self._wrap(override_settle_row)
        delay_form.addRow("", self._override_settle_row_widget)
        outer.addLayout(delay_form)

        # Flash-field-pattern insertion.
        ffp_row = QHBoxLayout()
        self.ffp_insertion_cb = QCheckBox(lang.getstr("ffp_insertion"))
        self.ffp_insertion_cb.toggled.connect(self._ffp_insertion_toggled)
        ffp_row.addWidget(self.ffp_insertion_cb)
        ffp_row.addWidget(QLabel(lang.getstr("interval")))
        self.ffp_insertion_interval_ctrl = QDoubleSpinBox()
        min_val, max_val = config.VALID_RANGES[
            "patterngenerator.ffp_insertion.interval"
        ]
        self.ffp_insertion_interval_ctrl.setDecimals(1)
        self.ffp_insertion_interval_ctrl.setSingleStep(0.1)
        self.ffp_insertion_interval_ctrl.setRange(min_val, max_val)
        self.ffp_insertion_interval_ctrl.valueChanged.connect(
            self._ffp_insertion_interval_changed
        )
        ffp_row.addWidget(self.ffp_insertion_interval_ctrl)
        ffp_row.addWidget(QLabel("s"))
        ffp_row.addWidget(QLabel(lang.getstr("duration")))
        self.ffp_insertion_duration_ctrl = QDoubleSpinBox()
        min_val, max_val = config.VALID_RANGES[
            "patterngenerator.ffp_insertion.duration"
        ]
        self.ffp_insertion_duration_ctrl.setDecimals(1)
        self.ffp_insertion_duration_ctrl.setSingleStep(0.1)
        self.ffp_insertion_duration_ctrl.setRange(min_val, max_val)
        self.ffp_insertion_duration_ctrl.valueChanged.connect(
            self._ffp_insertion_duration_changed
        )
        ffp_row.addWidget(self.ffp_insertion_duration_ctrl)
        ffp_row.addWidget(QLabel("s"))
        ffp_row.addWidget(QLabel(lang.getstr("level")))
        self.ffp_insertion_level_ctrl = QSpinBox()
        self.ffp_insertion_level_ctrl.setRange(0, 100)
        self.ffp_insertion_level_ctrl.valueChanged.connect(
            self._ffp_insertion_level_changed
        )
        ffp_row.addWidget(self.ffp_insertion_level_ctrl)
        ffp_row.addWidget(QLabel("%"))
        ffp_row.addStretch(1)
        self._ffp_row_widget = self._wrap(ffp_row)
        outer.addWidget(self._ffp_row_widget)

        # Output levels (pattern-generator video-level detection).
        output_levels_row = QHBoxLayout()
        output_levels_row.addWidget(QLabel(lang.getstr("output_levels")))
        self.output_levels_auto = QRadioButton(lang.getstr("auto"))
        self.output_levels_full_range = QRadioButton(
            lang.getstr("3dlut.encoding.type_n")
        )
        self.output_levels_limited_range = QRadioButton(
            lang.getstr("3dlut.encoding.type_t")
        )
        self._output_levels_group = QButtonGroup(self)
        for button in (
            self.output_levels_auto,
            self.output_levels_full_range,
            self.output_levels_limited_range,
        ):
            self._output_levels_group.addButton(button)
            output_levels_row.addWidget(button)
        self._output_levels_group.buttonToggled.connect(
            self._output_levels_changed
        )
        output_levels_row.addStretch(1)
        self._output_levels_row_widget = self._wrap(output_levels_row)
        outer.addWidget(self._output_levels_row_widget)

        # Colorimeter-correction-matrix (CCMX/CCSS) row.
        ccmx_row = QHBoxLayout()
        self.colorimeter_correction_matrix_label = QLabel(
            lang.getstr("colorimeter_correction_matrix_file")
        )
        ccmx_row.addWidget(self.colorimeter_correction_matrix_label)
        self.colorimeter_correction_matrix_ctrl = QComboBox()
        self.colorimeter_correction_matrix_ctrl.currentIndexChanged.connect(
            self.colorimeter_correction_matrix_ctrl_handler
        )
        ccmx_row.addWidget(self.colorimeter_correction_matrix_ctrl, 1)
        self.colorimeter_correction_info_btn = QToolButton()
        self.colorimeter_correction_info_btn.setAutoRaise(True)
        self.colorimeter_correction_info_btn.setToolTip(
            lang.getstr("colorimeter_correction.info")
        )
        info_pixmap = self._pixmap(16, "info")
        if not info_pixmap.isNull():
            self.colorimeter_correction_info_btn.setIcon(info_pixmap)
        self.colorimeter_correction_info_btn.clicked.connect(
            self.colorimeter_correction_info_btn_handler
        )
        ccmx_row.addWidget(self.colorimeter_correction_info_btn)
        self.colorimeter_correction_matrix_btn = QToolButton()
        self.colorimeter_correction_matrix_btn.setAutoRaise(True)
        self.colorimeter_correction_matrix_btn.setToolTip(
            lang.getstr("colorimeter_correction_matrix_file.choose")
        )
        open_pixmap = self._pixmap(16, "document-open")
        if not open_pixmap.isNull():
            self.colorimeter_correction_matrix_btn.setIcon(open_pixmap)
        self.colorimeter_correction_matrix_btn.clicked.connect(
            self.colorimeter_correction_matrix_btn_handler
        )
        ccmx_row.addWidget(self.colorimeter_correction_matrix_btn)
        self.colorimeter_correction_web_btn = QToolButton()
        self.colorimeter_correction_web_btn.setAutoRaise(True)
        self.colorimeter_correction_web_btn.setToolTip(
            lang.getstr("colorimeter_correction.web_check")
        )
        web_pixmap = self._pixmap(16, "web")
        if not web_pixmap.isNull():
            self.colorimeter_correction_web_btn.setIcon(web_pixmap)
        self.colorimeter_correction_web_btn.clicked.connect(
            self.colorimeter_correction_web_btn_handler
        )
        ccmx_row.addWidget(self.colorimeter_correction_web_btn)
        self.colorimeter_correction_create_btn = QToolButton()
        self.colorimeter_correction_create_btn.setAutoRaise(True)
        self.colorimeter_correction_create_btn.setToolTip(
            lang.getstr("colorimeter_correction.create")
        )
        create_pixmap = self._pixmap(16, "list-add")
        if not create_pixmap.isNull():
            self.colorimeter_correction_create_btn.setIcon(create_pixmap)
        self.colorimeter_correction_create_btn.clicked.connect(
            self.colorimeter_correction_create_btn_handler
        )
        ccmx_row.addWidget(self.colorimeter_correction_create_btn)
        outer.addLayout(ccmx_row)

        self.display_tech_info_show_btn = QToolButton()
        self.display_tech_info_show_btn.setAutoRaise(True)
        self.display_tech_info_show_btn.setToolButtonStyle(
            Qt.ToolButtonTextBesideIcon
        )
        display_tech_pixmap = self._pixmap(16, "info")
        if not display_tech_pixmap.isNull():
            self.display_tech_info_show_btn.setIcon(display_tech_pixmap)
        self.display_tech_info_show_btn.setText(
            lang.getstr("info.display_tech.show")
        )
        self.display_tech_info_show_btn.clicked.connect(
            self._display_tech_info_show_btn_handler
        )

        outer.addWidget(
            self._build_info_panel(
                ("clock", "info.display_instrument.warmup"),
                ("dialog-information", "info.display_instrument"),
                extra=self.display_tech_info_show_btn,
            ),
            1,
        )
        return panel

    def _display_tech_info_show_btn_handler(self) -> None:
        """Show (or raise) the display-technology info popup."""
        if getattr(self, "_display_tech_info_window", None) is None:
            self._display_tech_info_window = TooltipWindow(
                self,
                lang.getstr("display.tech"),
                self._info_text_html("info.display_tech"),
                bitmap=self._pixmap(32, "dialog-information"),
                links=[
                    (
                        lang.getstr(
                            "info.display_tech.linklabel.displayspecifications.com"
                        ),
                        "https://www.displayspecifications.com/",
                    ),
                    (
                        lang.getstr("info.display_tech.linklabel.everymac.com"),
                        "https://everymac.com/",
                    ),
                ],
            )
        self._display_tech_info_window.show_and_raise()

    def _build_calibration_tab(self) -> QWidget:
        """Build the Calibration settings panel."""
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        outer.addWidget(self._build_settings_header("calibration.settings"))

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
        self._calibration_form = form

        # Observer (wx places this at the top of the Calibration tab, right
        # after the two toggles, not on the Display & Instrument tab).
        self.observer_ctrl = QComboBox()
        self.observer_ctrl.currentIndexChanged.connect(self.observer_ctrl_handler)
        form.addRow(lang.getstr("observer"), self.observer_ctrl)

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
        self.whitepoint_colortemp_locus_label = QLabel(lang.getstr("reference"))
        self.whitepoint_colortemp_locus_ctrl = QComboBox()
        self.whitepoint_colortemp_locus_ctrl.addItems(
            [
                lang.getstr("whitepoint.colortemp.locus.daylight"),
                lang.getstr("whitepoint.colortemp.locus.blackbody"),
            ]
        )
        self.whitepoint_colortemp_locus_ctrl.currentIndexChanged.connect(
            self._whitepoint_locus_changed
        )
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
        whitepoint_row.addWidget(self.whitepoint_colortemp_locus_label)
        whitepoint_row.addWidget(self.whitepoint_colortemp_locus_ctrl)
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
        self._black_luminance_row_widget = self._wrap(black_luminance_row)
        form.addRow(
            lang.getstr("calibration.black_luminance"),
            self._black_luminance_row_widget,
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
        self._ambient_row_widget = self._wrap(ambient_row)
        form.addRow("", self._ambient_row_widget)

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
        self._quality_row_widget = self._wrap(quality_row)
        form.addRow(lang.getstr("calibration.speed"), self._quality_row_widget)

        self.cal_meas_time = QLabel()
        form.addRow("", self.cal_meas_time)

        outer.addLayout(form)
        outer.addWidget(
            self._build_info_panel(
                ("dialog-information", "info.calibration_settings")
            ),
            1,
        )
        return panel

    def _build_profiling_tab(self) -> QWidget:
        """Build the Profiling settings panel."""
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        outer.addWidget(self._build_settings_header("profile.settings"))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._profiling_form = form

        self.profile_type_ctrl = QComboBox()
        self.profile_type_ctrl.addItems(
            [lang.getstr(label_key) for _value, label_key in PROFILE_TYPES]
        )
        self._value_combos["profile.type"] = (
            self.profile_type_ctrl,
            [value for value, _label_key in PROFILE_TYPES],
        )
        self.profile_type_ctrl.currentIndexChanged.connect(
            self._profile_type_ctrl_changed
        )
        self.gamap_btn = self._tool_button(
            "applications-system", "profile.advanced_gamap", self._gamap_btn_handler
        )
        self.black_point_compensation_cb = QCheckBox(
            lang.getstr("black_point_compensation")
        )
        self._add_check(
            self.black_point_compensation_cb, "profile.black_point_compensation"
        )
        type_row = QHBoxLayout()
        type_row.addWidget(self.profile_type_ctrl)
        type_row.addWidget(self.gamap_btn)
        type_row.addWidget(self.black_point_compensation_cb)
        type_row.addStretch(1)
        self._profile_type_row_widget = self._wrap(type_row)
        form.addRow(lang.getstr("profile.type"), self._profile_type_row_widget)

        self.profile_quality_ctrl = QSlider(Qt.Horizontal)
        self.profile_quality_ctrl.setRange(1, len(PROFILE_QUALITY_LEVELS))
        self.profile_quality_ctrl.valueChanged.connect(self._profile_quality_changed)
        self.profile_quality_info = QLabel()
        quality_row = QHBoxLayout()
        quality_row.addWidget(self.profile_quality_ctrl)
        quality_row.addWidget(self.profile_quality_info)
        quality_row.addStretch(1)
        form.addRow(lang.getstr("profile.quality"), self._wrap(quality_row))

        # Testchart chooser.
        self.testchart_ctrl = QComboBox()
        self.testchart_ctrl.currentIndexChanged.connect(self._testchart_ctrl_changed)
        self.testchart_btn = self._tool_button(
            "document-open", "testchart.set", self._testchart_btn_handler
        )
        self.create_testchart_btn = self._tool_button(
            "rgbsquares", "testchart.edit", self._create_testchart_btn_handler
        )
        testchart_row = QHBoxLayout()
        testchart_row.addWidget(self.testchart_ctrl, 1)
        testchart_row.addWidget(self.testchart_btn)
        testchart_row.addWidget(self.create_testchart_btn)
        form.addRow(lang.getstr("testchart.file"), self._wrap(testchart_row))

        # Patch count: computed amount (fixed testcharts) or an auto-optimize
        # slider (only shown when testchart.file == "auto").
        self.testchart_patches_amount = QLabel("0")
        self.testchart_patches_amount.setToolTip(lang.getstr("testchart.info"))
        self.testchart_patches_amount_ctrl = QSlider(Qt.Horizontal)
        self.testchart_patches_amount_ctrl.setRange(
            config.VALID_VALUES["testchart.auto_optimize"][1],
            config.VALID_VALUES["testchart.auto_optimize"][-1],
        )
        self.testchart_patches_amount_ctrl.valueChanged.connect(
            self._testchart_patches_amount_changed
        )
        patches_row = QHBoxLayout()
        patches_row.addWidget(self.testchart_patches_amount_ctrl)
        patches_row.addWidget(self.testchart_patches_amount)
        patches_row.addStretch(1)
        self._patches_row_widget = self._wrap(patches_row)
        form.addRow(
            lang.getstr("testchart.patches_amount"), self._patches_row_widget
        )

        # Patch sequence (gated by show_advanced_options, like wx).
        self.testchart_patch_sequence_ctrl = QComboBox()
        self._add_value_combo(
            self.testchart_patch_sequence_ctrl,
            "testchart.patch_sequence",
            [
                (value, lang.getstr(f"testchart.{value}"))
                for value in config.VALID_VALUES["testchart.patch_sequence"]
            ],
        )
        form.addRow(
            lang.getstr("testchart.patch_sequence"), self.testchart_patch_sequence_ctrl
        )

        self.testchart_meas_time = QLabel()
        form.addRow("", self.testchart_meas_time)

        self.profile_name_textctrl = QLineEdit()
        self.profile_name_textctrl.editingFinished.connect(self._profile_name_changed)
        self.profile_name_info_btn = self._tool_button(
            "question", "profile.name.placeholders", self._profile_name_info_btn_handler
        )
        self.profile_save_path_btn = self._tool_button(
            "document-open",
            "profile.set_save_path",
            self._profile_save_path_btn_handler,
        )
        profile_name_row = QHBoxLayout()
        profile_name_row.addWidget(self.profile_name_textctrl, 1)
        profile_name_row.addWidget(self.profile_name_info_btn)
        profile_name_row.addWidget(self.profile_save_path_btn)
        form.addRow(lang.getstr("profile.name"), self._wrap(profile_name_row))

        self.profile_name_label = QLabel("?")
        self.profile_name_label.setWordWrap(True)
        form.addRow("", self.profile_name_label)

        outer.addLayout(form)
        outer.addWidget(
            self._build_info_panel(
                ("dialog-information", "info.profile_settings")
            ),
            1,
        )
        return panel

    def _build_lut3d_tab(self) -> QWidget:
        """Build the 3D LUT settings panel.

        Follows ``main.xrc``'s ``lut3d_settings_panel`` control set/order (see
        ``DisplayCAL/lut3d_settings.py``'s module docstring for what's
        deliberately not reproduced). Units that wx renders as a trailing
        ``cd/m²``/``%`` static text next to a numeric field are folded into
        that field's ``QDoubleSpinBox``/``QSpinBox`` suffix instead (matching
        this port's existing Calibration-tab luminance fields), so most rows
        map one-to-one to a single visibility flag from
        :func:`DisplayCAL.lut3d_settings.compute_trc_visibility`.
        """
        panel = QWidget()
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        outer.addWidget(self._build_settings_header("3dlut.settings"))

        self.lut3d_create_cb = QCheckBox(lang.getstr("3dlut.create_after_profiling"))
        self._add_check(self.lut3d_create_cb, "3dlut.create")
        outer.addWidget(self.lut3d_create_cb)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._lut3d_form = form

        # Input colorspace.
        self.lut3d_input_profile_ctrl = QComboBox()
        self.lut3d_input_profile_ctrl.currentIndexChanged.connect(
            self._lut3d_input_profile_changed
        )
        form.addRow(
            lang.getstr("3dlut.input.colorspace"), self.lut3d_input_profile_ctrl
        )

        # TRC row: mode + gamma + gamma type + HDR peak luminance, one line
        # (mirrors wx grouping all four under a single "trc" label).
        self.lut3d_trc_ctrl = QComboBox()
        self.lut3d_trc_ctrl.addItems(
            [
                "Gamma 2.2",
                lang.getstr("trc.rec1886"),
                lang.getstr("trc.smpte2084.hardclip"),
                lang.getstr("trc.smpte2084.rolloffclip"),
                lang.getstr("trc.hlg"),
                lang.getstr("custom"),
            ]
        )
        self.lut3d_trc_ctrl.currentIndexChanged.connect(self._lut3d_trc_ctrl_changed)
        self.lut3d_trc_gamma_label = QLabel(lang.getstr("trc.gamma"))
        self.lut3d_trc_gamma_ctrl = QComboBox()
        self.lut3d_trc_gamma_ctrl.setEditable(True)
        self.lut3d_trc_gamma_ctrl.addItems(["2.2", "2.4"])
        self.lut3d_trc_gamma_ctrl.setMaximumWidth(80)
        self.lut3d_trc_gamma_ctrl.lineEdit().editingFinished.connect(
            self._lut3d_trc_gamma_changed
        )
        self.lut3d_trc_gamma_ctrl.activated.connect(
            lambda _i: self._lut3d_trc_gamma_changed()
        )
        self.lut3d_trc_gamma_type_ctrl = QComboBox()
        self.lut3d_trc_gamma_type_ctrl.addItems(
            [lang.getstr("trc.type.relative"), lang.getstr("trc.type.absolute")]
        )
        self.lut3d_trc_gamma_type_ctrl.currentIndexChanged.connect(
            self._lut3d_trc_gamma_type_changed
        )
        self.lut3d_hdr_peak_luminance_label = QLabel(
            lang.getstr("display_peak_luminance")
        )
        self.lut3d_hdr_peak_luminance_ctrl = QDoubleSpinBox()
        self.lut3d_hdr_peak_luminance_ctrl.setRange(100, 10000)
        self.lut3d_hdr_peak_luminance_ctrl.setDecimals(0)
        self.lut3d_hdr_peak_luminance_ctrl.setSuffix(" cd/m²")
        self.lut3d_hdr_peak_luminance_ctrl.setMaximumWidth(110)
        self.lut3d_hdr_peak_luminance_ctrl.valueChanged.connect(
            self._lut3d_hdr_peak_luminance_changed
        )
        trc_row = QHBoxLayout()
        for widget in (
            self.lut3d_trc_ctrl,
            self.lut3d_trc_gamma_label,
            self.lut3d_trc_gamma_ctrl,
            self.lut3d_trc_gamma_type_ctrl,
            self.lut3d_hdr_peak_luminance_label,
            self.lut3d_hdr_peak_luminance_ctrl,
        ):
            trc_row.addWidget(widget)
        trc_row.addStretch(1)
        form.addRow(lang.getstr("trc"), self._wrap(trc_row))

        # HDR preserve luminance/saturation (a single slider trades off
        # between the two, mirroring wx's linked lum%/sat% readouts).
        self.lut3d_hdr_sat_ctrl = QSlider(Qt.Horizontal)
        self.lut3d_hdr_sat_ctrl.setRange(0, 100)
        self.lut3d_hdr_sat_ctrl.valueChanged.connect(self._lut3d_hdr_sat_changed)
        self.lut3d_hdr_sat_lum_val = QLabel()
        self.lut3d_hdr_sat_sat_val = QLabel()
        sat_row = QHBoxLayout()
        sat_row.addWidget(QLabel(lang.getstr("preserve_luminance")))
        sat_row.addWidget(self.lut3d_hdr_sat_lum_val)
        sat_row.addWidget(self.lut3d_hdr_sat_ctrl)
        sat_row.addWidget(self.lut3d_hdr_sat_sat_val)
        sat_row.addWidget(QLabel(lang.getstr("preserve_saturation")))
        sat_row.addStretch(1)
        self._lut3d_hdr_sat_row_widget = self._wrap(sat_row)
        form.addRow("", self._lut3d_hdr_sat_row_widget)

        # HDR preserve hue.
        self.lut3d_hdr_hue_ctrl = QSlider(Qt.Horizontal)
        self.lut3d_hdr_hue_ctrl.setRange(0, 100)
        self.lut3d_hdr_hue_intctrl = QSpinBox()
        self.lut3d_hdr_hue_intctrl.setRange(0, 100)
        self.lut3d_hdr_hue_intctrl.setSuffix("%")
        self.lut3d_hdr_hue_ctrl.valueChanged.connect(self._lut3d_hdr_hue_slider_changed)
        self.lut3d_hdr_hue_intctrl.valueChanged.connect(
            self._lut3d_hdr_hue_intctrl_changed
        )
        hue_row = QHBoxLayout()
        hue_row.addWidget(self.lut3d_hdr_hue_ctrl)
        hue_row.addWidget(self.lut3d_hdr_hue_intctrl)
        hue_row.addStretch(1)
        self._lut3d_hdr_hue_row_widget = self._wrap(hue_row)
        form.addRow(lang.getstr("preserve_hue"), self._lut3d_hdr_hue_row_widget)

        # HDR mastering display black/peak luminance.
        self.lut3d_hdr_minmll_ctrl = QDoubleSpinBox()
        self.lut3d_hdr_minmll_ctrl.setRange(0.0, 0.1)
        self.lut3d_hdr_minmll_ctrl.setDecimals(4)
        self.lut3d_hdr_minmll_ctrl.setSingleStep(0.0001)
        self.lut3d_hdr_minmll_ctrl.setSuffix(" cd/m²")
        self.lut3d_hdr_minmll_ctrl.valueChanged.connect(
            self._lut3d_hdr_minmll_changed
        )
        form.addRow(
            lang.getstr("mastering_display_black_luminance"),
            self.lut3d_hdr_minmll_ctrl,
        )

        self.lut3d_hdr_maxmll_ctrl = QDoubleSpinBox()
        self.lut3d_hdr_maxmll_ctrl.setRange(100, 10000)
        self.lut3d_hdr_maxmll_ctrl.setDecimals(0)
        self.lut3d_hdr_maxmll_ctrl.setSuffix(" cd/m²")
        self.lut3d_hdr_maxmll_ctrl.valueChanged.connect(
            self._lut3d_hdr_maxmll_changed
        )
        self.lut3d_hdr_maxmll_alt_clip_cb = QCheckBox(lang.getstr("adjust_rolloff"))
        self.lut3d_hdr_maxmll_alt_clip_cb.toggled.connect(
            self._lut3d_hdr_maxmll_alt_clip_changed
        )
        maxmll_row = QHBoxLayout()
        maxmll_row.addWidget(self.lut3d_hdr_maxmll_ctrl)
        maxmll_row.addWidget(self.lut3d_hdr_maxmll_alt_clip_cb)
        maxmll_row.addStretch(1)
        self._lut3d_hdr_maxmll_row_widget = self._wrap(maxmll_row)
        form.addRow(
            lang.getstr("mastering_display_peak_luminance"),
            self._lut3d_hdr_maxmll_row_widget,
        )

        # HDR roll-off diffuse-white preview (read-only, live-computed).
        self.lut3d_hdr_diffuse_white_txt = QLabel()
        self._lut3d_hdr_diffuse_white_row_widget = self.lut3d_hdr_diffuse_white_txt
        form.addRow(
            lang.getstr("3dlut.hdr.rolloff.diffuse_white"),
            self.lut3d_hdr_diffuse_white_txt,
        )

        # HDR (HLG) ambient viewing-condition luminance + system gamma.
        self.lut3d_hdr_ambient_luminance_ctrl = QDoubleSpinBox()
        self.lut3d_hdr_ambient_luminance_ctrl.setRange(0.01, 10000)
        self.lut3d_hdr_ambient_luminance_ctrl.setDecimals(2)
        self.lut3d_hdr_ambient_luminance_ctrl.setSuffix(" cd/m²")
        self.lut3d_hdr_ambient_luminance_ctrl.valueChanged.connect(
            self._lut3d_hdr_ambient_luminance_changed
        )
        form.addRow(
            lang.getstr("calibration.ambient_viewcond_adjust"),
            self.lut3d_hdr_ambient_luminance_ctrl,
        )

        self.lut3d_hdr_system_gamma_txt = QLabel()
        form.addRow(
            lang.getstr("3dlut.hdr.system_gamma"), self.lut3d_hdr_system_gamma_txt
        )

        # Content colorspace (only meaningful for SMPTE 2084 roll-off / HLG).
        self.lut3d_content_colorspace_ctrl = QComboBox()
        self.lut3d_content_colorspace_ctrl.addItems(lut3d_content_colorspace_items())
        self.lut3d_content_colorspace_ctrl.currentIndexChanged.connect(
            self._lut3d_content_colorspace_changed
        )
        form.addRow(
            lang.getstr("3dlut.content.colorspace"),
            self.lut3d_content_colorspace_ctrl,
        )

        primaries_grid = QGridLayout()
        primaries_grid.setHorizontalSpacing(8)
        self._lut3d_content_colorspace_xy_ctrls = {}
        for row, (color, label_key) in enumerate(
            (("white", "white"), ("red", "red"), ("green", "green"), ("blue", "blue"))
        ):
            primaries_grid.addWidget(QLabel(lang.getstr(label_key)), row, 0)
            for col_offset, coord in enumerate("xy"):
                spin = QDoubleSpinBox()
                spin.setRange(-1.0, 1.0)
                spin.setDecimals(4)
                spin.setSingleStep(0.0001)
                spin.setPrefix(f"{coord} ")
                spin.valueChanged.connect(
                    self._make_lut3d_content_colorspace_xy_handler(color, coord)
                )
                self._lut3d_content_colorspace_xy_ctrls[(color, coord)] = spin
                primaries_grid.addWidget(spin, row, 1 + col_offset)
        primaries_holder = QWidget()
        primaries_holder.setLayout(primaries_grid)
        self._lut3d_content_colorspace_xy_row_widget = primaries_holder
        form.addRow("", primaries_holder)

        # Black output offset (0-100 %).
        self.lut3d_trc_black_output_offset_ctrl = QSlider(Qt.Horizontal)
        self.lut3d_trc_black_output_offset_ctrl.setRange(0, 100)
        self.lut3d_trc_black_output_offset_intctrl = QSpinBox()
        self.lut3d_trc_black_output_offset_intctrl.setRange(0, 100)
        self.lut3d_trc_black_output_offset_intctrl.setSuffix("%")
        self.lut3d_trc_black_output_offset_ctrl.valueChanged.connect(
            self._lut3d_black_output_offset_slider_changed
        )
        self.lut3d_trc_black_output_offset_intctrl.valueChanged.connect(
            self._lut3d_black_output_offset_intctrl_changed
        )
        boo_row = QHBoxLayout()
        boo_row.addWidget(self.lut3d_trc_black_output_offset_ctrl)
        boo_row.addWidget(self.lut3d_trc_black_output_offset_intctrl)
        boo_row.addStretch(1)
        self._lut3d_black_output_offset_row_widget = self._wrap(boo_row)
        form.addRow(
            lang.getstr("calibration.black_output_offset"),
            self._lut3d_black_output_offset_row_widget,
        )

        # Apply calibration (only meaningful with show_advanced_options, like
        # the gamut-mapping-mode row below).
        self.lut3d_apply_cal_cb = QCheckBox(lang.getstr("apply_cal"))
        self.lut3d_apply_cal_cb.toggled.connect(self._lut3d_apply_cal_changed)
        form.addRow("", self.lut3d_apply_cal_cb)

        self.gamut_mapping_inverse_a2b = QRadioButton(
            lang.getstr("gamut_mapping.mode.inverse_a2b")
        )
        self.gamut_mapping_b2a = QRadioButton(lang.getstr("gamut_mapping.mode.b2a"))
        self._gamut_mapping_group = QButtonGroup(self)
        self._gamut_mapping_group.addButton(self.gamut_mapping_inverse_a2b)
        self._gamut_mapping_group.addButton(self.gamut_mapping_b2a)
        self.gamut_mapping_inverse_a2b.toggled.connect(
            self._lut3d_gamut_mapping_mode_changed
        )
        gamut_row = QHBoxLayout()
        gamut_row.addWidget(self.gamut_mapping_inverse_a2b)
        gamut_row.addWidget(self.gamut_mapping_b2a)
        gamut_row.addStretch(1)
        self._lut3d_gamut_mapping_row_widget = self._wrap(gamut_row)
        form.addRow(
            lang.getstr("gamut_mapping.mode"), self._lut3d_gamut_mapping_row_widget
        )

        self.lut3d_rendering_intent_ctrl = QComboBox()
        self._add_value_combo(
            self.lut3d_rendering_intent_ctrl,
            "3dlut.rendering_intent",
            lut3d_rendering_intent_items(getcfg("argyll.version")),
        )
        form.addRow(
            lang.getstr("rendering_intent"), self.lut3d_rendering_intent_ctrl
        )

        # Format + (madVR-only) HDR display sub-mode.
        self.lut3d_format_ctrl = QComboBox()
        format_items = lut3d_format_items(getcfg("argyll.version"))
        #: ``lut3d_format_ctrl`` row index -> config value (built once, like
        #: wx's ``lut3d_formats_ab``; the Argyll-version-gated item set
        #: doesn't change during a session).
        self._lut3d_format_values = [value for value, _label in format_items]
        self.lut3d_format_ctrl.addItems([label for _value, label in format_items])
        self.lut3d_format_ctrl.currentIndexChanged.connect(
            self._lut3d_format_ctrl_changed
        )
        self.lut3d_hdr_display_ctrl = QComboBox()
        self.lut3d_hdr_display_ctrl.addItems(
            [
                lang.getstr(item)
                for item in ("3dlut.format.madVR.hdr_to_sdr", "3dlut.format.madVR.hdr")
            ]
        )
        self.lut3d_hdr_display_ctrl.currentIndexChanged.connect(
            self._lut3d_hdr_display_changed
        )
        format_row = QHBoxLayout()
        format_row.addWidget(self.lut3d_format_ctrl)
        format_row.addWidget(self.lut3d_hdr_display_ctrl)
        format_row.addStretch(1)
        form.addRow(lang.getstr("3dlut.format"), self._wrap(format_row))

        #: ``encoding_input_ctrl`` / ``encoding_output_ctrl`` row index ->
        #: config value, rebuilt on every format change by
        #: :meth:`_lut3d_update_encoding_controls`.
        self._lut3d_encoding_input_values: list[str] = []
        self._lut3d_encoding_output_values: list[str] = []

        self.encoding_input_ctrl = QComboBox()
        self.encoding_input_ctrl.currentIndexChanged.connect(
            self._lut3d_encoding_input_changed
        )
        form.addRow(lang.getstr("3dlut.encoding.input"), self.encoding_input_ctrl)

        self.encoding_output_ctrl = QComboBox()
        self.encoding_output_ctrl.currentIndexChanged.connect(
            self._lut3d_encoding_output_changed
        )
        form.addRow(lang.getstr("3dlut.encoding.output"), self.encoding_output_ctrl)

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

        outer.addLayout(form)
        outer.addWidget(
            self._build_info_panel(
                ("dialog-information", "info.3dlut_settings")
            ),
            1,
        )
        return panel

    def _build_verification_tab(self) -> QWidget:
        """Build the Verification (measurement-report settings) tab.

        Embeds :class:`~DisplayCAL.ui.measurement_report.ReportPanel` directly,
        matching wx's 5th tab (``display_cal.py:2450-2458``, the same
        ``report.xrc`` panel ``MainFrame`` loads as ``mr_settings_panel``) --
        found missing entirely in the 2026-07-11 live wx-vs-Qt comparison
        (see ``MAINFRAME_PORT_PLAN.md``). The panel is built without its own
        Measure button (``show_measure_button=False``); the shared
        action-bar button (:meth:`measurement_report_btn_handler`) is the
        actual trigger, matching wx's ``buttonpanel``-level
        ``measurement_report_btn`` rather than a per-tab one.
        """
        self._report_panel = ReportPanel(
            self, show_measure_button=False, worker=self.worker
        )
        self._report_panel.edit_chart_requested.connect(self._open_testchart_editor)
        return self._report_panel

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
        # QPushButton (unlike QLabel) treats "&" as a mnemonic marker and
        # swallows it; the label is "Calibrate & profile" (a literal "and"),
        # so escape it to "&&" to render the ampersand, mirroring wx's own
        # ``label.replace("&", "&&")`` for its button labels.
        self.calibrate_and_profile_btn = QPushButton(
            lang.getstr("button.calibrate_and_profile").replace("&", "&&")
        )
        self.calibrate_and_profile_btn.clicked.connect(
            self.calibrate_and_profile_btn_handler
        )
        self.profile_btn = QPushButton(lang.getstr("button.profile"))
        self.profile_btn.clicked.connect(self.profile_btn_handler)
        self.lut3d_create_btn = QPushButton(lang.getstr("3dlut.create"))
        self.lut3d_create_btn.clicked.connect(self.lut3d_create_btn_handler)
        self.measurement_report_btn = QPushButton(lang.getstr("measurement_report"))
        self.measurement_report_btn.clicked.connect(self.measurement_report_btn_handler)
        for button in (
            self.calibrate_btn,
            self.calibrate_and_profile_btn,
            self.profile_btn,
            self.lut3d_create_btn,
            self.measurement_report_btn,
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

    def _tool_button(
        self, icon_name: str, tooltip_key: str, handler: Callable[[], None]
    ) -> QToolButton:
        """Build a flat 16px icon button, mirroring wx's ``wxBitmapButton`` rows."""
        button = QToolButton()
        button.setAutoRaise(True)
        button.setToolTip(lang.getstr(tooltip_key))
        pixmap = self._pixmap(16, icon_name)
        if not pixmap.isNull():
            button.setIcon(pixmap)
        button.clicked.connect(handler)
        return button

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
            self.update_calibration_file_ctrl()
            self.update_displays()
            self.update_comports()
            self.update_observers()
            self.update_display_instrument_controls()
            self.update_calibration_controls()
            self.update_profile_controls()
            self.update_lut3d_controls()
            self._update_advanced_options_visibility()
        finally:
            self._updating = False
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        """Show exactly one calibrate/profile/3D-LUT-create/report action button.

        Mirrors ``MainFrame.update_main_controls``: wx shows "Calibrate &
        Profile" by default, falling back to "Calibrate only" or "Profile
        only" depending on the interactive-adjustment / TRC / "update
        existing calibration" state, never more than one at once, and hides
        all three whenever the 3D LUT tab is active with manual creation
        (``lut3d_create_btn`` shown instead) or the Verification tab is
        active (``measurement_report_btn`` shown instead, matching wx's
        ``mr_btn_show = self.mr_settings_panel.IsShown()``).
        """
        update_cal = self.calibration_update_cb.isChecked()
        update_profile = update_cal and config.is_profile()
        enable_cal = not config.is_uncalibratable_display() and (
            self.interactive_adjustment_cb.isChecked()
            or self.trc_ctrl.currentIndex() > 0
        )
        lut3d_create_show = self.stack.currentWidget() is self._panels.get(
            "lut3d"
        ) and not getcfg("3dlut.create")
        mr_btn_show = self.stack.currentWidget() is self._panels.get("verification")
        calibrate_and_profile_show = (
            not lut3d_create_show
            and not mr_btn_show
            and enable_cal
            and not update_profile
        )
        calibrate_show = (
            not lut3d_create_show
            and not mr_btn_show
            and enable_cal
            and not calibrate_and_profile_show
        )
        profile_show = (
            not lut3d_create_show
            and not mr_btn_show
            and not calibrate_and_profile_show
            and not update_cal
        )

        has_devices = bool(self.worker.displays) and bool(self.worker.instruments)
        not_ccxx = not config.is_ccxx_testchart()

        self.calibrate_btn.setVisible(calibrate_show)
        self.calibrate_btn.setEnabled(calibrate_show and not_ccxx and has_devices)
        self.calibrate_and_profile_btn.setVisible(calibrate_and_profile_show)
        self.calibrate_and_profile_btn.setEnabled(
            calibrate_and_profile_show and not_ccxx and has_devices
        )
        self.profile_btn.setVisible(profile_show)
        self.profile_btn.setEnabled(profile_show and has_devices)
        self.lut3d_create_btn.setVisible(lut3d_create_show)
        self.lut3d_create_btn.setEnabled(
            config.is_profile() and getcfg("calibration.file", False) not in self.presets
        )
        self.measurement_report_btn.setVisible(mr_btn_show)
        self._update_measurement_report_btn_enabled()

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

    def update_display_instrument_controls(self) -> None:
        """Push stored display/instrument config into their Qt controls."""
        self._sync_check("drift_compensation.whitelevel")
        self._sync_check("drift_compensation.blacklevel")

        self.update_display_lut_ctrl()
        self.update_measurement_mode_ctrl()
        self.update_colorimeter_correction_matrix_ctrl()

        override_delay = bool(
            int(getcfg("measure.override_min_display_update_delay_ms"))
        )
        self.override_min_display_update_delay_ms_cb.setChecked(override_delay)
        self.min_display_update_delay_ms_ctrl.setValue(
            int(getcfg("measure.min_display_update_delay_ms"))
        )
        self.min_display_update_delay_ms_ctrl.setEnabled(override_delay)
        self.min_display_update_delay_ms_label.setEnabled(override_delay)

        override_settle = bool(
            int(getcfg("measure.override_display_settle_time_mult"))
        )
        self.override_display_settle_time_mult_cb.setChecked(override_settle)
        self.display_settle_time_mult_ctrl.setValue(
            _as_float(getcfg("measure.display_settle_time_mult")) or 1.0
        )
        self.display_settle_time_mult_ctrl.setEnabled(override_settle)

        self.ffp_insertion_cb.setChecked(
            bool(int(getcfg("patterngenerator.ffp_insertion")))
        )
        self.ffp_insertion_interval_ctrl.setValue(
            _as_float(getcfg("patterngenerator.ffp_insertion.interval")) or 0.0
        )
        self.ffp_insertion_duration_ctrl.setValue(
            _as_float(getcfg("patterngenerator.ffp_insertion.duration")) or 0.0
        )
        self.ffp_insertion_level_ctrl.setValue(
            round(
                (_as_float(getcfg("patterngenerator.ffp_insertion.level")) or 0.0)
                * 100
            )
        )

        if getcfg("patterngenerator.detect_video_levels"):
            self.output_levels_auto.setChecked(True)
        elif getcfg("patterngenerator.use_video_levels"):
            self.output_levels_limited_range.setChecked(True)
        else:
            self.output_levels_full_range.setChecked(True)

    def update_display_lut_ctrl(self) -> None:
        """Populate the display-LUT selector and sync the link toggle.

        Mirrors wx's ``display_lut_link_ctrl_handler`` population half: the
        LUT selector only lists displays the worker reports independent LUT
        access for (``worker.lut_access``); when linked, its selection always
        follows ``display_ctrl`` rather than the stored ``display_lut.number``.

        Mirrors wx's ``update_scrollbars``/``display_lut_link_ctrl_handler``
        row-visibility: the whole selector + link button are hidden unless the
        worker reports (or the user has forced) separate LUT access, matching
        wx's ``display_lut_sizer.Show(..., use_lut_ctrl)``. Also matches wx in
        only ever considering this on Linux (``sys.platform not in ("darwin",
        "win32")``, ignoring the ``-t``/``--test`` dev override), since macOS
        and Windows never need separate video-card vs. LUT-capable display
        selection.
        """
        use_lut_ctrl = (sys.platform not in ("darwin", "win32") or TEST) and (
            self.worker.has_separate_lut_access()
            or bool(getcfg("use_separate_lut_access"))
        )
        self._display_lut_form.setRowVisible(self.display_lut_ctrl, use_lut_ctrl)
        self.display_lut_link_ctrl.setVisible(use_lut_ctrl)
        if not use_lut_ctrl:
            setcfg("display_lut.link", 1)
            return
        names = display_items(self.worker.displays)
        lut_access = self.worker.lut_access
        lut_items = [
            name
            for i, name in enumerate(names)
            if i < len(lut_access) and lut_access[i]
        ]
        self.display_lut_ctrl.clear()
        self.display_lut_ctrl.addItems(lut_items)

        linked = bool(int(getcfg("display_lut.link")))
        self.display_lut_link_ctrl.setChecked(linked)
        self._apply_display_lut_link_icon(linked)

        target = None
        if linked:
            target = self.display_ctrl.currentText()
        else:
            number = getcfg("display_lut.number")
            if 0 < number <= len(names):
                target = names[number - 1]
        index = (
            lut_items.index(target)
            if target in lut_items
            else (0 if lut_items else -1)
        )
        self.display_lut_ctrl.setCurrentIndex(index)
        self.display_lut_ctrl.setEnabled(not linked and bool(lut_items))

    def update_calibration_controls(self) -> None:
        """Push stored calibration config into the Calibration tab controls."""
        self._sync_check("calibration.interactive_display_adjustment")
        self._sync_check("calibration.update")

        self.whitepoint_colortemp_ctrl.setValue(
            int(_as_float(getcfg("whitepoint.colortemp")) or 6500)
        )
        self.whitepoint_x_ctrl.setValue(round(getcfg("whitepoint.x"), 4))
        self.whitepoint_y_ctrl.setValue(round(getcfg("whitepoint.y"), 4))
        self.whitepoint_colortemp_locus_ctrl.setCurrentIndex(
            1 if getcfg("whitepoint.colortemp.locus") == "T" else 0
        )
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
        self._update_cal_meas_time()

    def update_profile_controls(self) -> None:
        """Push stored profile config into the Profiling tab controls."""
        self._sync_value_combo("profile.type", cast=str)
        self._update_bpc()
        profile_type = self.get_profile_type()
        self.gamap_btn.setEnabled(profile_type in _GAMUT_MAPPABLE_PROFILE_TYPES)
        self.profile_quality_ctrl.setEnabled(
            profile_type not in _GAMMA_ONLY_PROFILE_TYPES
        )
        self.profile_quality_ctrl.setValue(
            profile_quality_to_slider(getcfg("profile.quality"))
        )
        self._update_profile_quality_label()
        self.profile_name_textctrl.setText(str(getcfg("profile.name")))
        self._sync_value_combo("testchart.patch_sequence", cast=str)
        self._testchart_patch_sequence_row_gate()
        self._set_testchart(getcfg("testchart.file"))

    def _update_bpc(self, enable_profile: bool = True) -> None:
        """Sync the black-point-compensation checkbox's value/enabled state.

        Port of ``MainFrame.update_bpc``. Called from
        :meth:`update_profile_controls`, from :meth:`_profile_type_ctrl_changed`,
        and whenever the gamut-mapping window's B2A quality controls change
        (:meth:`_on_gamap_b2a_quality_changed`).

        Args:
            enable_profile (bool): Extra caller-supplied gate wx exposes as
                ``update_bpc(enable_profile=...)``, used by its macOS
                shaper-profile warning dialog (not ported, so always ``True``
                here).
        """
        enable_bpc = gamap_settings.compute_bpc_enabled(
            self.get_profile_type(),
            bool(getcfg("profile.b2a.hires")),
            getcfg("profile.quality.b2a"),
            enable_profile,
        )
        if not enable_bpc:
            setcfg("profile.black_point_compensation", 0)
        self.black_point_compensation_cb.setEnabled(enable_bpc)
        self.black_point_compensation_cb.setChecked(
            enable_bpc and bool(int(getcfg("profile.black_point_compensation")))
        )

    def update_lut3d_controls(self) -> None:
        """Push stored 3D LUT config into the 3D LUT tab controls.

        Toolkit-neutral port of ``MainFrame.lut3d_update_controls`` +
        ``LUT3DMixin.lut3d_update_shared_controls`` / ``lut3d_update_trc_controls``,
        specialized for this Qt port (see ``DisplayCAL/lut3d_settings.py``'s
        module docstring for what's deliberately not reproduced). Wrapped in
        its own re-entrancy guard (mirroring
        :meth:`update_colorimeter_correction_matrix_ctrl_items`) so any 3D LUT
        handler can call it directly for a full re-sync after an
        interdependent config change, without needing to route through
        :meth:`update_controls`.
        """
        was_updating = self._updating
        self._updating = True
        try:
            self._sync_check("3dlut.create")

            lut3d_input_profile = getcfg("3dlut.input.profile")
            if lut3d_input_profile not in self.input_profiles.values():
                if not lut3d_input_profile or not os.path.isfile(lut3d_input_profile):
                    lut3d_input_profile = DEFAULTS["3dlut.input.profile"]
                    setcfg("3dlut.input.profile", lut3d_input_profile)
                else:
                    try:
                        profile = ICCProfile(lut3d_input_profile)
                    except (OSError, ICCProfileInvalidError) as exception:
                        print(f"{lut3d_input_profile}:", exception)
                    else:
                        desc = self._lut3d_profile_description(profile)
                        self.input_profiles[desc] = lut3d_input_profile
                        self.lut3d_input_profile_ctrl.addItem(desc)
            paths = list(self.input_profiles.values())
            if lut3d_input_profile in paths:
                self.lut3d_input_profile_ctrl.setCurrentIndex(
                    paths.index(lut3d_input_profile)
                )
            self.lut3d_input_profile_ctrl.setToolTip(lut3d_input_profile)

            trc = str(getcfg("3dlut.trc"))
            trc_gamma_type = str(getcfg("3dlut.trc_gamma_type"))
            trc_output_offset = getcfg("3dlut.trc_output_offset")
            trc_gamma = getcfg("3dlut.trc_gamma")
            index, corrected_trc = lut3d_settings.resolve_trc_selection(
                trc, trc_gamma_type, trc_output_offset, trc_gamma
            )
            if corrected_trc != trc:
                setcfg("3dlut.trc", corrected_trc)
                trc = corrected_trc
            self.lut3d_trc_ctrl.setCurrentIndex(index)
            self.lut3d_trc_gamma_ctrl.setCurrentText(str(trc_gamma))
            self.lut3d_trc_gamma_type_ctrl.setCurrentIndex(
                lut3d_settings.TRC_GAMMA_TYPE_BA.get(trc_gamma_type, 0)
            )
            outoffset = int(round(float(trc_output_offset) * 100))
            self.lut3d_trc_black_output_offset_ctrl.setValue(outoffset)
            self.lut3d_trc_black_output_offset_intctrl.setValue(outoffset)

            target_peak = getcfg("3dlut.hdr_peak_luminance")
            maxmll = getcfg("3dlut.hdr_maxmll")
            # Don't allow maxmll < target peak: technically unrestricted, but
            # practically nonsensical (mirrors wx's identical clamp).
            if maxmll < target_peak:
                maxmll = target_peak
                setcfg("3dlut.hdr_maxmll", maxmll)
            self.lut3d_hdr_maxmll_ctrl.setMinimum(target_peak)
            self.lut3d_hdr_peak_luminance_ctrl.setValue(target_peak)
            self.lut3d_hdr_minmll_ctrl.setValue(getcfg("3dlut.hdr_minmll"))
            self.lut3d_hdr_maxmll_ctrl.setValue(maxmll)
            self.lut3d_hdr_maxmll_alt_clip_cb.setChecked(
                not bool(getcfg("3dlut.hdr_maxmll_alt_clip"))
            )
            self._update_lut3d_diffuse_white()
            self.lut3d_hdr_ambient_luminance_ctrl.setValue(
                getcfg("3dlut.hdr_ambient_luminance")
            )
            self._update_lut3d_system_gamma()

            colors_xy = {
                f"3dlut.content.colorspace.{color}.{coord}": getcfg(
                    f"3dlut.content.colorspace.{color}.{coord}"
                )
                for color in ("white", "red", "green", "blue")
                for coord in "xy"
            }
            for (color, coord), spin in self._lut3d_content_colorspace_xy_ctrls.items():
                spin.setValue(colors_xy[f"3dlut.content.colorspace.{color}.{coord}"])
            cc_index = lut3d_settings.resolve_content_colorspace_selection(colors_xy)
            self.lut3d_content_colorspace_ctrl.setCurrentIndex(cc_index)

            self.lut3d_hdr_sat_ctrl.setValue(round(getcfg("3dlut.hdr_sat") * 100))
            self._update_lut3d_sat_val()
            hue = round(getcfg("3dlut.hdr_hue") * 100)
            self.lut3d_hdr_hue_ctrl.setValue(hue)
            self.lut3d_hdr_hue_intctrl.setValue(hue)

            self._update_lut3d_apply_cal_control()
            self._update_lut3d_b2a_controls()

            self._sync_value_combo("3dlut.rendering_intent", cast=str)
            self._sync_lut3d_format_ctrl()
            self.lut3d_hdr_display_ctrl.setCurrentIndex(int(getcfg("3dlut.hdr_display")))
            self._sync_value_combo("3dlut.size", cast=int)
            self._sync_value_combo("3dlut.bitdepth.input", cast=int)
            self._sync_value_combo("3dlut.bitdepth.output", cast=int)

            self._apply_lut3d_visibility()
        finally:
            self._updating = was_updating

    @staticmethod
    def _lut3d_profile_description(profile: ICCProfile) -> str:
        """Return a 3D LUT input-profile combo description for ``profile``.

        Mirrors the description cleanup in ``MainFrame.lut3d_init_input_profiles``
        / ``lut3d_update_controls``.
        """
        desc = profile.getDescription()
        return re.sub(
            r"\s*(?:color profile|primaries with \S+ transfer function)$", "", desc
        )

    def _lut3d_init_input_profiles(self) -> None:
        """Populate the input-colorspace combo from the bundled reference profiles.

        Mirrors ``MainFrame.lut3d_init_input_profiles``. Called once from
        :meth:`__init__`; per-update selection sync happens in
        :meth:`update_lut3d_controls`.
        """
        self.input_profiles = {}
        for profile_filename in (
            "ACES.icm",
            "ACEScg.icm",
            "DCDM X'Y'Z'.icm",
            "Rec709.icm",
            "Rec2020.icm",
            "EBU3213_PAL.icm",
            "SMPTE_RP145_NTSC.icm",
            "SMPTE431_P3.icm",
            "SMPTE431_P3_D65.icm",
            getcfg("3dlut.input.profile"),
        ):
            if not profile_filename:
                continue
            path = (
                profile_filename
                if os.path.isabs(profile_filename)
                else config.get_data_path("ref/" + profile_filename)
            )
            if not path:
                continue
            try:
                profile = ICCProfile(path)
            except (OSError, ICCProfileInvalidError) as exception:
                print(f"{path}:", exception)
                continue
            if path not in self.input_profiles.values():
                self.input_profiles[self._lut3d_profile_description(profile)] = path
        self.input_profiles = dict_sort(self.input_profiles)
        self.lut3d_input_profile_ctrl.clear()
        self.lut3d_input_profile_ctrl.addItems(list(self.input_profiles.keys()))

    def _sync_lut3d_format_ctrl(self) -> None:
        """Select the format combo row matching stored config, then cascade."""
        file_format = getcfg("3dlut.format")
        if file_format not in self._lut3d_format_values:
            # madVR unavailable on this Argyll version -> fall back like wx.
            file_format = DEFAULTS["3dlut.format"]
        if file_format in self._lut3d_format_values:
            self.lut3d_format_ctrl.setCurrentIndex(
                self._lut3d_format_values.index(file_format)
            )
        self._lut3d_update_encoding_controls()
        self.lut3d_size_ctrl.setEnabled(file_format not in ("eeColor", "madVR"))
        bitdepth_input_visible, bitdepth_output_visible = (
            lut3d_settings.lut3d_bitdepth_controls_visible(file_format)
        )
        self._lut3d_form.setRowVisible(
            self.lut3d_bitdepth_input_ctrl, bitdepth_input_visible
        )
        self._lut3d_form.setRowVisible(
            self.lut3d_bitdepth_output_ctrl, bitdepth_output_visible
        )

    def _lut3d_update_encoding_controls(self) -> None:
        """Rebuild the encoding input/output combos for the current format.

        Mirrors ``LUT3DMixin.lut3d_setup_encoding_ctrl`` +
        ``lut3d_update_encoding_controls``.
        """
        file_format = getcfg("3dlut.format")
        argyll_version = getcfg("argyll.version")
        input_codes, output_codes = lut3d_settings.lut3d_encoding_codes(
            file_format, argyll_version
        )
        self._lut3d_encoding_input_values = input_codes
        self._lut3d_encoding_output_values = output_codes

        self.encoding_input_ctrl.blockSignals(True)
        self.encoding_input_ctrl.clear()
        self.encoding_input_ctrl.addItems(
            [label for _code, label in lut3d_encoding_items(input_codes)]
        )
        input_value = getcfg("3dlut.encoding.input")
        if input_value in input_codes:
            self.encoding_input_ctrl.setCurrentIndex(input_codes.index(input_value))
        self.encoding_input_ctrl.blockSignals(False)
        self.encoding_input_ctrl.setEnabled(len(input_codes) > 1)

        self.encoding_output_ctrl.blockSignals(True)
        self.encoding_output_ctrl.clear()
        self.encoding_output_ctrl.addItems(
            [label for _code, label in lut3d_encoding_items(output_codes)]
        )
        output_value = getcfg("3dlut.encoding.output")
        if output_value in output_codes:
            self.encoding_output_ctrl.setCurrentIndex(
                output_codes.index(output_value)
            )
        self.encoding_output_ctrl.blockSignals(False)
        self.encoding_output_ctrl.setEnabled(file_format not in ("dcl", "madVR"))

    def _update_lut3d_diffuse_white(self) -> None:
        """Refresh the HDR roll-off diffuse-white readout."""
        value, below_reference = lut3d_settings.diffuse_white_cdm2(
            getcfg("3dlut.hdr_peak_luminance"),
            getcfg("3dlut.hdr_minmll"),
            getcfg("3dlut.hdr_maxmll"),
            getcfg("3dlut.hdr_maxmll_alt_clip"),
        )
        color = "#CC0000" if below_reference else "#008000"
        self.lut3d_hdr_diffuse_white_txt.setText(f"{value:.2f} cd/m²")
        self.lut3d_hdr_diffuse_white_txt.setStyleSheet(f"color: {color};")

    def _update_lut3d_system_gamma(self) -> None:
        """Refresh the HLG system-gamma readout."""
        gamma = lut3d_settings.hlg_system_gamma(getcfg("3dlut.hdr_ambient_luminance"))
        self.lut3d_hdr_system_gamma_txt.setText(str(stripzeros(f"{gamma:.4f}")))

    def _update_lut3d_sat_val(self) -> None:
        """Refresh the preserve-luminance/-saturation percentage readouts."""
        v = getcfg("3dlut.hdr_sat") * 100
        self.lut3d_hdr_sat_lum_val.setText(f"{100 - v}%")
        self.lut3d_hdr_sat_sat_val.setText(f"{v}%")

    def _update_lut3d_apply_cal_control(self) -> None:
        """Sync the "Apply calibration" checkbox's value/enabled state.

        Mirrors ``MainFrame.lut3d_update_apply_cal_control``.
        """
        lut3d_create = bool(getcfg("3dlut.create"))
        profile = not lut3d_create and config.get_current_profile(True)
        enable_apply_cal = bool(
            lut3d_create
            or (profile and isinstance(profile.tags.get("vcgt"), VideoCardGammaType))
        )
        self.lut3d_apply_cal_cb.setChecked(
            enable_apply_cal and bool(getcfg("3dlut.output.profile.apply_cal"))
        )
        self.lut3d_apply_cal_cb.setEnabled(enable_apply_cal)

    def _update_lut3d_b2a_controls(self) -> None:
        """Sync the gamut-mapping-mode radios' value/enabled state.

        Mirrors ``MainFrame.lut3d_update_b2a_controls``.
        """
        if getcfg("3dlut.create"):
            allow_b2a_gamap = getcfg("profile.type") in ("l", "x", "X") and getcfg(
                "profile.b2a.hires"
            )
        else:
            profile = config.get_current_profile(True)
            allow_b2a_gamap = bool(
                profile
                and "B2A0" in profile.tags
                and isinstance(profile.tags.B2A0, LUT16Type)
                and profile.tags.B2A0.clut_grid_steps >= 17
            )
        self.gamut_mapping_b2a.setEnabled(bool(allow_b2a_gamap))
        if not allow_b2a_gamap:
            setcfg("3dlut.gamap.use_b2a", 0)
        self.gamut_mapping_inverse_a2b.setChecked(not getcfg("3dlut.gamap.use_b2a"))
        self.gamut_mapping_b2a.setChecked(bool(getcfg("3dlut.gamap.use_b2a")))

    def _apply_lut3d_visibility(self) -> None:
        """Show/hide 3D LUT tab rows for the current config.

        Mirrors ``LUT3DMixin.lut3d_show_trc_controls`` / ``lut3d_show_encoding_controls``
        and ``MainFrame.lut3d_show_controls``, via
        :func:`DisplayCAL.lut3d_settings.compute_trc_visibility`.
        """
        argyll_version = getcfg("argyll.version")
        cc_is_custom = self.lut3d_content_colorspace_ctrl.currentIndex() == len(
            lut3d_settings.CONTENT_COLORSPACE_NAMES
        )
        v = lut3d_settings.compute_trc_visibility(
            trc=str(getcfg("3dlut.trc")),
            trc_format=getcfg("3dlut.format"),
            argyll_version=argyll_version,
            show_advanced_options=bool(getcfg("show_advanced_options")),
            lut3d_create=bool(getcfg("3dlut.create")),
            hdr_maxmll=getcfg("3dlut.hdr_maxmll"),
            content_colorspace_is_custom=cc_is_custom,
        )
        self.lut3d_trc_ctrl.setVisible(v.trc_row)
        self.lut3d_trc_gamma_label.setVisible(v.trc_gamma)
        self.lut3d_trc_gamma_ctrl.setVisible(v.trc_gamma)
        self.lut3d_trc_gamma_type_ctrl.setVisible(v.trc_gamma_type)
        self.lut3d_hdr_peak_luminance_label.setVisible(v.hdr_peak_luminance)
        self.lut3d_hdr_peak_luminance_ctrl.setVisible(v.hdr_peak_luminance)
        self._lut3d_form.setRowVisible(self._lut3d_hdr_sat_row_widget, v.hdr_sat_hue)
        self._lut3d_form.setRowVisible(self._lut3d_hdr_hue_row_widget, v.hdr_sat_hue)
        self._lut3d_form.setRowVisible(self.lut3d_hdr_minmll_ctrl, v.hdr_minmll)
        self._lut3d_form.setRowVisible(
            self._lut3d_hdr_maxmll_row_widget, v.hdr_maxmll
        )
        self.lut3d_hdr_maxmll_alt_clip_cb.setVisible(v.hdr_maxmll_alt_clip)
        self._lut3d_form.setRowVisible(
            self._lut3d_hdr_diffuse_white_row_widget, v.hdr_diffuse_white
        )
        self._lut3d_form.setRowVisible(
            self.lut3d_hdr_ambient_luminance_ctrl, v.hdr_ambient_luminance
        )
        self._lut3d_form.setRowVisible(
            self.lut3d_hdr_system_gamma_txt, v.hdr_system_gamma
        )
        self._lut3d_form.setRowVisible(
            self.lut3d_content_colorspace_ctrl, v.content_colorspace
        )
        self._lut3d_form.setRowVisible(
            self._lut3d_content_colorspace_xy_row_widget, v.content_colorspace_xy
        )
        self._lut3d_form.setRowVisible(
            self._lut3d_black_output_offset_row_widget, v.black_output_offset
        )
        self.lut3d_hdr_display_ctrl.setVisible(v.hdr_display)

        show_advanced = bool(getcfg("show_advanced_options"))
        self._lut3d_form.setRowVisible(self.lut3d_apply_cal_cb, show_advanced)
        self._lut3d_form.setRowVisible(
            self._lut3d_gamut_mapping_row_widget, show_advanced
        )

        encoding_visible = lut3d_settings.lut3d_encoding_controls_visible(
            argyll_version
        )
        self._lut3d_form.setRowVisible(self.encoding_input_ctrl, encoding_visible)
        self._lut3d_form.setRowVisible(self.encoding_output_ctrl, encoding_visible)

    # -- 3D LUT handlers ----------------------------------------------------

    def _lut3d_input_profile_changed(self, index: int) -> None:
        """Persist the selected 3D LUT input-colorspace profile.

        Mirrors ``MainFrame.lut3d_input_colorspace_handler``.
        """
        if self._updating or index < 0:
            return
        paths = list(self.input_profiles.values())
        if index >= len(paths):
            return
        path = paths[index]
        setcfg("3dlut.input.profile", path)
        try:
            profile = ICCProfile(path)
        except (OSError, ICCProfileInvalidError):
            profile = None
        if (
            profile
            and "rTRC" in profile.tags
            and "gTRC" in profile.tags
            and "bTRC" in profile.tags
            and profile.tags.rTRC == profile.tags.gTRC == profile.tags.bTRC
            and isinstance(profile.tags.rTRC, CurveType)
        ):
            tf = profile.tags.rTRC.get_transfer_function(outoffset=1.0)
            changed = setcfg_cond(
                tf[0][0].startswith("Gamma"), "3dlut.trc_gamma", round(tf[0][1], 2), True
            )
            if changed:
                self.update_lut3d_controls()
        self.lut3d_input_profile_ctrl.setToolTip(path)

    def _lut3d_trc_ctrl_changed(self, index: int) -> None:
        """Apply the TRC combo's implied config, then re-sync everything.

        Mirrors ``LUT3DMixin.lut3d_trc_ctrl_handler`` (minus the custom-gamma
        focus/select-all UI action, which has no config-visible effect).
        """
        if self._updating or index < 0:
            return
        for key, value in lut3d_settings.trc_selection_side_effects(index).items():
            setcfg(key, value)
        self.update_lut3d_controls()

    def _lut3d_trc_gamma_changed(self) -> None:
        """Validate and persist a hand-edited custom-gamma value."""
        if self._updating:
            return
        text = self.lut3d_trc_gamma_ctrl.currentText()
        low, high = config.VALID_RANGES["3dlut.trc_gamma"]
        try:
            value = float(text.replace(",", "."))
            if not low <= value <= high:
                raise ValueError
        except ValueError:
            QApplication.beep()
            self.lut3d_trc_gamma_ctrl.setCurrentText(str(getcfg("3dlut.trc_gamma")))
            return
        if str(value) != text:
            self.lut3d_trc_gamma_ctrl.setCurrentText(str(value))
        if value != getcfg("3dlut.trc_gamma"):
            setcfg("3dlut.trc_gamma", value)
            self.update_lut3d_controls()

    def _lut3d_trc_gamma_type_changed(self, index: int) -> None:
        if self._updating or index < 0:
            return
        value = lut3d_settings.TRC_GAMMA_TYPE_AB.get(index, "b")
        if value != getcfg("3dlut.trc_gamma_type"):
            setcfg("3dlut.trc_gamma_type", value)
            self.update_lut3d_controls()

    def _lut3d_hdr_peak_luminance_changed(self, value: float) -> None:
        if self._updating:
            return
        if getcfg("3dlut.hdr_maxmll") < value:
            setcfg("3dlut.hdr_maxmll", value)
        setcfg("3dlut.hdr_peak_luminance", value)
        self.update_lut3d_controls()

    def _lut3d_hdr_minmll_changed(self, value: float) -> None:
        if self._updating:
            return
        setcfg("3dlut.hdr_minmll", value)
        self.update_lut3d_controls()

    def _lut3d_hdr_maxmll_changed(self, value: float) -> None:
        if self._updating:
            return
        setcfg("3dlut.hdr_maxmll", value)
        self.update_lut3d_controls()

    def _lut3d_hdr_maxmll_alt_clip_changed(self, checked: bool) -> None:
        if self._updating:
            return
        setcfg("3dlut.hdr_maxmll_alt_clip", int(not checked))
        self.update_lut3d_controls()

    def _lut3d_hdr_ambient_luminance_changed(self, value: float) -> None:
        if self._updating:
            return
        setcfg("3dlut.hdr_ambient_luminance", value)
        self._update_lut3d_system_gamma()

    def _lut3d_hdr_sat_changed(self, value: int) -> None:
        if self._updating:
            return
        setcfg("3dlut.hdr_sat", value / 100.0)
        self._update_lut3d_sat_val()

    def _commit_lut3d_hdr_hue(self, value: int) -> None:
        v = value / 100.0
        if v != getcfg("3dlut.hdr_hue"):
            setcfg("3dlut.hdr_hue", v)

    def _lut3d_hdr_hue_slider_changed(self, value: int) -> None:
        if self._updating:
            return
        self.lut3d_hdr_hue_intctrl.setValue(value)
        self._commit_lut3d_hdr_hue(value)

    def _lut3d_hdr_hue_intctrl_changed(self, value: int) -> None:
        if self._updating:
            return
        self.lut3d_hdr_hue_ctrl.setValue(value)
        self._commit_lut3d_hdr_hue(value)

    def _commit_lut3d_black_output_offset(self, value: int) -> None:
        v = value / 100.0
        if v != getcfg("3dlut.trc_output_offset"):
            setcfg("3dlut.trc_output_offset", v)
            self.update_lut3d_controls()

    def _lut3d_black_output_offset_slider_changed(self, value: int) -> None:
        if self._updating:
            return
        self.lut3d_trc_black_output_offset_intctrl.setValue(value)
        self._commit_lut3d_black_output_offset(value)

    def _lut3d_black_output_offset_intctrl_changed(self, value: int) -> None:
        if self._updating:
            return
        self.lut3d_trc_black_output_offset_ctrl.setValue(value)
        self._commit_lut3d_black_output_offset(value)

    def _lut3d_content_colorspace_changed(self, index: int) -> None:
        if self._updating or index < 0:
            return
        if index < len(lut3d_settings.CONTENT_COLORSPACE_NAMES):
            name = lut3d_settings.CONTENT_COLORSPACE_NAMES[index]
            for key, value in lut3d_settings.content_colorspace_xy(name).items():
                setcfg(key, value)
        self.update_lut3d_controls()

    def _make_lut3d_content_colorspace_xy_handler(
        self, color: str, coord: str
    ) -> Callable[[float], None]:
        """Return a value-changed handler bound to one primaries-editor spin box."""

        def handler(value: float) -> None:
            if self._updating:
                return
            setcfg(f"3dlut.content.colorspace.{color}.{coord}", value)
            self.update_lut3d_controls()

        return handler

    def _lut3d_apply_cal_changed(self, checked: bool) -> None:
        if self._updating:
            return
        setcfg("3dlut.output.profile.apply_cal", int(checked))

    def _lut3d_gamut_mapping_mode_changed(self, checked: bool) -> None:
        """Handle ``gamut_mapping_inverse_a2b``'s ``toggled`` signal.

        The two radios are mutually exclusive (:class:`QButtonGroup`), so
        ``checked`` alone (inverse-A2B selected vs. B2A selected) is enough.
        """
        if self._updating:
            return
        setcfg("3dlut.gamap.use_b2a", 0 if checked else 1)

    def _lut3d_format_ctrl_changed(self, index: int) -> None:
        """Apply the format combo's cascading config side effects.

        Mirrors ``LUT3DMixin.lut3d_format_ctrl_handler``.
        """
        if self._updating or index < 0 or index >= len(self._lut3d_format_values):
            return
        old_format = getcfg("3dlut.format")
        new_format = self._lut3d_format_values[index]
        cfg_snapshot = {
            key: getcfg(key)
            for key in (
                "3dlut.encoding.input",
                "3dlut.encoding.output",
                "3dlut.encoding.input.backup",
                "3dlut.encoding.output.backup",
                "3dlut.size",
                "3dlut.size.backup",
                "3dlut.bitdepth.output",
            )
        }
        updates = lut3d_settings.lut3d_format_side_effects(
            old_format, new_format, cfg_snapshot
        )
        for key, value in updates.items():
            setcfg(key, value)
        self.update_lut3d_controls()

    def _lut3d_hdr_display_changed(self, index: int) -> None:
        """Handle the madVR HDR/HDR-to-SDR sub-mode combo.

        Mirrors ``LUT3DMixin.lut3d_hdr_display_handler``: turning HDR mode on
        shows a one-time informational confirmation (there is no cancel path,
        the dialog just needs to be acknowledged).
        """
        if self._updating or index < 0:
            return
        if index and not getcfg("3dlut.hdr_display"):
            QMessageBox.information(
                self, APPNAME, lang.getstr("3dlut.format.madVR.hdr.confirm")
            )
        setcfg("3dlut.hdr_display", index)

    def _lut3d_encoding_input_changed(self, index: int) -> None:
        if (
            self._updating
            or index < 0
            or index >= len(self._lut3d_encoding_input_values)
        ):
            return
        setcfg("3dlut.encoding.input", self._lut3d_encoding_input_values[index])
        self._lut3d_update_encoding_controls()

    def _lut3d_encoding_output_changed(self, index: int) -> None:
        if (
            self._updating
            or index < 0
            or index >= len(self._lut3d_encoding_output_values)
        ):
            return
        encoding = self._lut3d_encoding_output_values[index]
        if getcfg("3dlut.format") == "madVR" and encoding != "t":
            result = QMessageBox.question(
                self,
                APPNAME,
                lang.getstr(
                    "3dlut.encoding.output.warning.madvr",
                    lang.getstr("device.name.placeholder"),
                ),
                QMessageBox.Ok | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if result != QMessageBox.Ok:
                self._lut3d_update_encoding_controls()
                return
        setcfg("3dlut.encoding.output", encoding)
        self._lut3d_update_encoding_controls()

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

        Mirrors wx's ``display_ctrl_handler``, which re-runs
        ``display_lut_link_ctrl_handler`` whenever the LUT link row is
        shown, so a linked ``display_lut_ctrl`` keeps following the newly
        selected display.

        Args:
            index (int): The newly selected combo index.
        """
        if self._updating or index < 0:
            return
        setcfg("display.number", index + 1)
        if self.display_lut_link_ctrl.isVisibleTo(self):
            self.display_lut_link_ctrl_handler(self.display_lut_link_ctrl.isChecked())

    def comport_ctrl_handler(self, index: int) -> None:
        """Persist the selected instrument (comport) number.

        Mirrors wx's ``comport_ctrl_handler``: a new instrument changes which
        measurement modes and CCMX/CCSS corrections are available, so both
        get rebuilt for it.

        Args:
            index (int): The newly selected combo index.
        """
        if self._updating or index < 0:
            return
        setcfg("comport.number", index + 1)
        self.update_measurement_mode_ctrl()
        self.update_colorimeter_correction_matrix_ctrl()

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

    def display_lut_ctrl_handler(self, index: int) -> None:
        """Persist the selected display-LUT number.

        Args:
            index (int): The newly selected combo index.
        """
        if self._updating or index < 0:
            return
        name = self.display_lut_ctrl.itemText(index)
        names = display_items(self.worker.displays)
        if name in names:
            setcfg("display_lut.number", names.index(name) + 1)

    def display_lut_link_ctrl_handler(self, checked: bool) -> None:
        """Toggle whether the display-LUT selection follows ``display_ctrl``.

        Mirrors wx's ``display_lut_link_ctrl_handler``: when linked, the LUT
        selector always tracks the selected display; when unlinked, it can be
        set independently.

        Args:
            checked (bool): Whether the link toggle is now checked (linked).
        """
        self._apply_display_lut_link_icon(checked)
        self.display_lut_ctrl.setEnabled(
            not checked and self.display_lut_ctrl.count() > 0
        )
        if checked:
            index = self.display_lut_ctrl.findText(self.display_ctrl.currentText())
            if index >= 0:
                self.display_lut_ctrl.setCurrentIndex(index)
        if self._updating:
            return
        setcfg("display_lut.link", int(checked))

    def _apply_display_lut_link_icon(self, linked: bool) -> None:
        """Swap the link-toggle icon to reflect the current link state."""
        pixmap = self._pixmap(16, "stock_lock" if linked else "stock_lock-open")
        if not pixmap.isNull():
            self.display_lut_link_ctrl.setIcon(pixmap)

    def detect_displays_and_ports_btn_handler(self) -> None:
        """Re-enumerate displays/instruments and refresh every bound control.

        A synchronous simplification of wx's ``check_update_controls`` (which
        drives the same worker call through a progress dialog on a background
        thread); the full worker-driven Argyll execution path is a later
        slice (see the module docstring).
        """
        self.worker.enumerate_displays_and_ports(silent=True)
        self.update_controls()

    def get_measurement_mode(self) -> str | None:
        """Return the mode code for the currently selected combo entry.

        Toolkit-neutral equivalent of wx's ``MainFrame.get_measurement_mode``.
        """
        instrument_type = colorimeter_correction.get_instrument_type(self.worker)
        return self._measurement_modes_ab.get(instrument_type, {}).get(
            self.measurement_mode_ctrl.currentIndex()
        )

    # -- Settings getters (Stage 0 deferral, mirroring wx's ``MainFrame`` getters) --

    def get_profile_type(self) -> str:
        """Return the profile type letter for the current combo selection."""
        _combo, values = self._value_combos["profile.type"]
        index = self.profile_type_ctrl.currentIndex()
        if 0 <= index < len(values):
            return values[index]
        return getcfg("profile.type")

    def get_whitepoint(self) -> str | None:
        """Return the whitepoint as a Kelvin/xy string, or ``None`` for native."""
        mode = self.whitepoint_ctrl.currentIndex()
        if mode == 1:
            return str(stripzeros(self.whitepoint_colortemp_ctrl.value()))
        if mode == 2:
            x = round(self.whitepoint_x_ctrl.value(), 4)
            y = round(self.whitepoint_y_ctrl.value(), 4)
            return f"{stripzeros(x)},{stripzeros(y)}"
        return None

    def get_whitepoint_locus(self) -> str:
        """Return the whitepoint locus ("t" daylight / "T" blackbody/Planckian).

        Mirrors wx's ``get_whitepoint_locus``.
        """
        index = self.whitepoint_colortemp_locus_ctrl.currentIndex()
        return "T" if index == 1 else "t"

    def get_luminance(self) -> str | None:
        """Return the custom white luminance, or ``None`` for native/default."""
        if self.luminance_ctrl.currentIndex() == 0:
            return None
        return str(stripzeros(self.luminance_textctrl.value()))

    def get_black_luminance(self) -> str | None:
        """Return the custom black luminance, or ``None`` for native/default."""
        if self.black_luminance_ctrl.currentIndex() == 0:
            return None
        return str(stripzeros(self.black_luminance_textctrl.value()))

    def get_ambient(self) -> str | None:
        """Return the ambient light level in lux, or ``None`` if disabled."""
        if self.ambient_adjust_cb.isChecked():
            return str(stripzeros(self.ambient_adjust_textctrl.value()))
        return None

    def get_black_output_offset(self) -> str:
        """Return the black output offset as a 0-1 decimal string."""
        return str(Decimal(self.black_output_offset_ctrl.value()) / 100)

    def get_black_point_correction(self) -> str:
        """Return the black point correction as a 0-1 decimal string."""
        return str(Decimal(self.black_point_correction_ctrl.value()) / 100)

    def get_trc(self) -> str:
        """Return the ``trc`` config value for the current TRC combo state."""
        return trc_value_from_selection(
            self.trc_ctrl.currentIndex(), self.trc_textctrl.text()
        )

    def get_trc_type(self) -> str:
        """Return "G" (absolute) or "g" (relative) for the TRC type combo."""
        return "G" if self.trc_type_ctrl.currentIndex() == 1 else "g"

    def get_calibration_quality(self) -> str:
        """Return the calibration quality letter for the current slider value."""
        return slider_to_calibration_quality(self.calibration_quality_ctrl.value())

    def measurement_mode_ctrl_handler(self, index: int) -> None:
        """Persist the selected measurement mode.

        Mirrors wx's ``measurement_mode_ctrl_handler``, minus the old-Argyll
        "projector/adaptive mode unavailable" fallback dialogs (those only
        applied to Argyll versions far older than anything this Qt port
        targets).

        Args:
            index (int): The newly selected combo index.
        """
        if self._updating or index < 0:
            return
        code = self.get_measurement_mode()
        instrument_features = self.worker.get_instrument_features()
        if (
            code
            and self.worker.get_instrument_name() in ("ColorHug", "ColorHug2")
            and "p" in code
        ):
            # ColorHug projector mode is just a correction matrix; avoid
            # setting ColorMunki projector mode.
            code = code.replace("p", "")
        setcfg(
            "measurement_mode",
            (code.replace("V", "").replace("H", "") if code else None) or None,
        )
        if instrument_features.get("adaptive_mode"):
            setcfg("measurement_mode.adaptive", 1 if code and "V" in code else 0)
        if instrument_features.get("highres_mode"):
            setcfg("measurement_mode.highres", 1 if code and "H" in code else 0)
        setcfg("measurement_mode.projector", 1 if code and "p" in code else None)
        self.update_colorimeter_correction_matrix_ctrl()

    def update_measurement_mode_ctrl(self) -> None:
        """Populate the measurement-mode combo for the current instrument.

        Toolkit-neutral port of wx's ``update_measurement_modes`` via
        :func:`colorimeter_correction.compute_measurement_modes`.
        """
        instrument_name = self.worker.get_instrument_name()
        instrument_type = colorimeter_correction.get_instrument_type(self.worker)
        result = colorimeter_correction.compute_measurement_modes(
            self.worker, instrument_name, instrument_type
        )
        self._measurement_modes_ab = result.measurement_modes_ab
        self._measurement_modes_ba = result.measurement_modes_ba
        modes = result.measurement_modes[instrument_type]
        was_updating = self._updating
        self._updating = True
        try:
            self.measurement_mode_ctrl.clear()
            self.measurement_mode_ctrl.addItems(modes)
            if modes:
                index = min(
                    self._measurement_modes_ba[instrument_type].get(
                        result.measurement_mode, 1
                    ),
                    len(modes) - 1,
                )
                self.measurement_mode_ctrl.setCurrentIndex(index)
        finally:
            self._updating = was_updating
        mode = self.get_measurement_mode() or "l"
        setcfg("measurement_mode", mode if mode == "auto" else mode[0])
        self.measurement_mode_ctrl.setEnabled(
            bool(self.worker.instruments) and bool(modes)
        )

    def update_colorimeter_correction_matrix_ctrl(self) -> None:
        """Show or hide the CCMX/CCSS row, then refresh its items.

        Toolkit-neutral port of wx's
        ``update_colorimeter_correction_matrix_ctrl``.
        """
        show_control = (
            self.worker.instrument_can_use_ccxx(False)
            and not config.is_ccxx_testchart()
            and getcfg("measurement_mode") != "auto"
        )
        for widget in (
            self.colorimeter_correction_matrix_label,
            self.colorimeter_correction_matrix_ctrl,
            self.colorimeter_correction_info_btn,
            self.colorimeter_correction_matrix_btn,
            self.colorimeter_correction_web_btn,
            self.colorimeter_correction_create_btn,
        ):
            widget.setVisible(show_control)
        self.update_colorimeter_correction_matrix_ctrl_items()

    def update_colorimeter_correction_matrix_ctrl_items(
        self,
        force: bool = False,
        warn_on_mismatch: bool = False,
        update_measurement_mode: bool = True,
    ) -> colorimeter_correction.ColorimeterCorrectionSelection:
        """Refresh the CCMX/CCSS combo's items and selection.

        Toolkit-neutral port of wx's
        ``update_colorimeter_correction_matrix_ctrl_items`` via
        :func:`colorimeter_correction.resolve_colorimeter_correction_selection`.
        Malformed-file trashing is not reproduced; see that function's
        docstring for the full list of deliberate simplifications.

        Args:
            force: Re-scan the Argyll data dirs even if already cached.
            warn_on_mismatch: Show a dialog (instead of only printing) when
                the configured CCMX doesn't match the current instrument.
            update_measurement_mode: If True, a CCMX/CCSS-implied
                measurement mode always overrides the current one.
        """
        result = colorimeter_correction.resolve_colorimeter_correction_selection(
            self._ccmx_catalog,
            self.worker,
            current_selection_index=self.colorimeter_correction_matrix_ctrl.currentIndex(),
            force=force,
            warn_on_mismatch=warn_on_mismatch,
            update_measurement_mode=update_measurement_mode,
        )
        was_updating = self._updating
        self._updating = True
        try:
            self.colorimeter_correction_matrix_ctrl.clear()
            self.colorimeter_correction_matrix_ctrl.addItems(result.items)
            self.colorimeter_correction_matrix_ctrl.setCurrentIndex(result.index)
        finally:
            self._updating = was_updating
        self.colorimeter_correction_matrix_ctrl.setToolTip(result.tooltip)
        self.colorimeter_correction_info_btn.setEnabled(result.use_ccmx)
        if result.observer_recognized:
            self.update_observers()
            self.observer_ctrl.setEnabled(False)
        else:
            self.observer_ctrl.setEnabled(True)
        if result.measurement_mode is not None:
            self.update_measurement_mode_ctrl()
        self._update_observer_visibility()
        if result.mismatch_warning:
            QMessageBox.warning(
                self,
                lang.getstr("colorimeter_correction_matrix_file"),
                result.mismatch_warning,
            )
        return result

    def colorimeter_correction_matrix_ctrl_handler(self, index: int) -> None:
        """Persist the selected CCMX/CCSS correction (or None/Auto).

        Args:
            index (int): The newly selected combo index.
        """
        if self._updating or index < 0:
            return
        if index == 0:
            ccmx = ["", ""]
        elif index == 1:
            ccmx = ["AUTO", ""]
        else:
            path_index = index - 2
            if path_index >= len(self._ccmx_catalog.item_paths):
                return
            ccmx = ["", self._ccmx_catalog.item_paths[path_index]]
        setcfg("colorimeter_correction_matrix_file", ":".join(ccmx))
        self.update_colorimeter_correction_matrix_ctrl_items()

    def colorimeter_correction_matrix_btn_handler(self) -> None:
        """Browse for a CCMX/CCSS file and select it."""
        ccmx = getcfg("colorimeter_correction_matrix_file").split(":", 1)
        default_dir, default_file = config.get_verified_path(
            None, ccmx[-1] if ccmx else ""
        )
        path, _filter = QFileDialog.getOpenFileName(
            self,
            lang.getstr("colorimeter_correction_matrix_file.choose"),
            default_dir if default_file else config.get_argyll_data_dir(),
            f"{lang.getstr('filetype.ccmx')} (*.ccmx *.ccss)",
        )
        if not path:
            return
        if (
            getcfg("colorimeter_correction_matrix_file").split(":")[0] != "AUTO"
            or path not in (self._ccmx_catalog.cached_paths or [])
        ):
            setcfg("colorimeter_correction_matrix_file", ":" + path)
        self.update_colorimeter_correction_matrix_ctrl_items(warn_on_mismatch=True)

    def colorimeter_correction_web_btn_handler(self) -> None:
        """Check the online colorimeter-correction database."""
        controller = WebCheckController(self.worker, self)
        controller.finished.connect(self._on_ccxx_web_check_finished)
        self._ccxx_web_controller = controller
        controller.run()

    def _on_ccxx_web_check_finished(self) -> None:
        self._ccxx_web_controller = None
        self.update_colorimeter_correction_matrix_ctrl_items(force=True)

    def colorimeter_correction_create_btn_handler(self) -> None:
        """Launch the standalone CCMX/CCSS creation window."""
        window = CreateCorrectionWindow()
        window.show()
        self._ccxx_create_window = window

    def colorimeter_correction_info_btn_handler(self) -> None:
        """Plot the selected CCMX/CCSS's spectra or matrix."""
        ccmx = getcfg("colorimeter_correction_matrix_file").split(":", 1)
        if len(ccmx) < 2 or not os.path.isfile(ccmx[1]):
            return
        try:
            cgats = CGATS(ccmx[1])
        except CGATSError as exception:
            QMessageBox.critical(
                self, lang.getstr("colorimeter_correction.info"), str(exception)
            )
            return
        if 0 not in cgats:
            return

        key = md5(bytes(cgats)).digest()  # noqa: S324
        window = self._ccxx_plot_windows.get(key)
        if window is None:
            try:
                window = CCXXPlotWindow(cgats, self.worker)
            except Exception as exception:  # noqa: BLE001 (report on GUI thread)
                QMessageBox.critical(
                    self, lang.getstr("colorimeter_correction.info"), str(exception)
                )
                return
            self._ccxx_plot_windows[key] = window
        window.show()
        window.raise_()
        window.activateWindow()

    def _display_delay_override_toggled(self, checked: bool) -> None:
        """Enable the delay spinbox and persist the override flag."""
        self.min_display_update_delay_ms_ctrl.setEnabled(checked)
        self.min_display_update_delay_ms_label.setEnabled(checked)
        if self._updating:
            return
        setcfg("measure.override_min_display_update_delay_ms", int(checked))

    def _min_display_update_delay_ms_changed(self, value: int) -> None:
        """Persist the minimum display-update delay override value."""
        if self._updating:
            return
        setcfg("measure.min_display_update_delay_ms", value)

    def _display_settle_time_mult_override_toggled(self, checked: bool) -> None:
        """Enable the settle-time-multiplier spinbox and persist the flag."""
        self.display_settle_time_mult_ctrl.setEnabled(checked)
        if self._updating:
            return
        setcfg("measure.override_display_settle_time_mult", int(checked))

    def _display_settle_time_mult_changed(self, value: float) -> None:
        """Persist the display-settle-time-multiplier override value."""
        if self._updating:
            return
        setcfg("measure.display_settle_time_mult", value)

    def _ffp_insertion_toggled(self, checked: bool) -> None:
        """Persist whether flash-field-pattern insertion is enabled."""
        if self._updating:
            return
        setcfg("patterngenerator.ffp_insertion", int(checked))

    def _ffp_insertion_interval_changed(self, value: float) -> None:
        """Persist the flash-field-pattern insertion interval (seconds)."""
        if self._updating:
            return
        setcfg("patterngenerator.ffp_insertion.interval", value)

    def _ffp_insertion_duration_changed(self, value: float) -> None:
        """Persist the flash-field-pattern insertion duration (seconds)."""
        if self._updating:
            return
        setcfg("patterngenerator.ffp_insertion.duration", value)

    def _ffp_insertion_level_changed(self, value: int) -> None:
        """Persist the flash-field-pattern insertion level (0-100 % -> 0-1)."""
        if self._updating:
            return
        setcfg("patterngenerator.ffp_insertion.level", value / 100.0)

    def _output_levels_changed(self, _button: QRadioButton, checked: bool) -> None:
        """Persist the output-levels radio selection (auto / full / limited)."""
        if self._updating or not checked:
            return
        setcfg(
            "patterngenerator.detect_video_levels",
            int(self.output_levels_auto.isChecked()),
        )
        setcfg(
            "patterngenerator.use_video_levels",
            int(self.output_levels_limited_range.isChecked()),
        )

    # -- generic binder handlers ------------------------------------------

    def _check_handler(self, config_key: str, checked: bool) -> None:
        """Persist a bound checkbox as an int (0/1)."""
        if self._updating:
            return
        setcfg(config_key, 1 if checked else 0)
        self._update_action_buttons()
        self._update_observer_visibility()
        if config_key in ("profile.black_point_compensation", "3dlut.create"):
            self._check_lut3d_bpc()

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
        locus_visible = mode in (0, 1) and bool(getcfg("show_advanced_options"))
        self.whitepoint_colortemp_locus_label.setVisible(locus_visible)
        self.whitepoint_colortemp_locus_ctrl.setVisible(locus_visible)

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

    def _whitepoint_locus_changed(self, *_args: object) -> None:
        """Persist the whitepoint colour-temperature locus ("t"/"T") to config.

        Mirrors wx's ``whitepoint_colortemp_locus_ctrl_handler``.
        """
        if self._updating:
            return
        v = self.get_whitepoint_locus()
        if v != getcfg("whitepoint.colortemp.locus"):
            setcfg("whitepoint.colortemp.locus", v)

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
        """Show the TRC-selection-dependent rows, per wx's ``show_trc_controls``.

        Several rows below the TRC combo are gated on a mix of the selected
        row and ``show_advanced_options`` (custom-gamma row 7 always shows
        them; rows 1/4, the "typed gamma" ones, only show them when advanced
        options are on): the gamma text/type fields, the ambient-adjustment
        row, and the black-output-offset / black-point-correction sliders.
        The calibration-speed row is simpler, tracking only whether a TRC is
        selected at all (row 0, "as measured", hides it) regardless of
        advanced options.

        Not reproduced (see the wx ``black_point_correction_auto_handler``
        this doubles as): the "auto" black-point-correction checkbox and its
        rate sub-controls, which this Qt port doesn't have yet, so
        ``black_point_correction_ctrl`` is always treated as the manual
        (non-auto) case.
        """
        show_advanced = bool(getcfg("show_advanced_options"))
        index = self.trc_ctrl.currentIndex()

        is_text = index == 7 or (index in (1, 4) and show_advanced)
        self.trc_textctrl.setVisible(is_text)
        self.trc_type_ctrl.setVisible(is_text)

        self._calibration_form.setRowVisible(
            self._ambient_row_widget,
            index in (3, 5) or (index > 0 and show_advanced),
        )
        self._calibration_form.setRowVisible(
            self.black_output_offset_ctrl,
            index == 7 or (index > 0 and show_advanced),
        )
        self._calibration_form.setRowVisible(
            self.black_point_correction_ctrl, index > 0 and show_advanced
        )
        self._calibration_form.setRowVisible(self._quality_row_widget, index > 0)

    def _trc_changed(self, *_args: object) -> None:
        """Persist the tone-response-curve selection to ``trc`` / ``trc.type``."""
        self._apply_trc_mode()
        self._update_action_buttons()
        self._update_observer_visibility()
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
        """Persist the calibration quality and refresh its labels."""
        self._update_calibration_quality_label()
        self._update_cal_meas_time()
        if self._updating:
            return
        setcfg("calibration.quality", slider_to_calibration_quality(value))

    def _update_calibration_quality_label(self) -> None:
        """Set the calibration speed label from the current slider value."""
        quality = slider_to_calibration_quality(self.calibration_quality_ctrl.value())
        self.calibration_quality_info.setText(
            lang.getstr(f"calibration.speed.{_CALIBRATION_SPEED_LABELS[quality]}")
        )

    def _update_cal_meas_time(self) -> None:
        """Refresh the Calibration tab's estimated-measurement-time label.

        Qt port of ``MainFrame.update_estimated_measurement_time("cal")``,
        found missing entirely in the 2026-07-11 live wx-vs-Qt comparison
        (see ``MAINFRAME_PORT_PLAN.md``); the Profiling tab's equivalent
        (:meth:`_update_testchart_meas_time`) was already wired in Session 9.
        """
        quality = slider_to_calibration_quality(self.calibration_quality_ctrl.value())
        patches = profile_name_mod.calibration_measurement_patches(
            self.worker, quality
        )
        estimate = profile_name_mod.estimate_measurement_time(
            self.worker, patches, which="cal"
        )
        self.cal_meas_time.setText(estimate.label())
        self.cal_meas_time.setStyleSheet(
            "color: #FF3300;"
            if estimate.hours is not None and estimate.hours > 7
            else "color: #F07F00;" if estimate.is_long() else ""
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
        """Sanitize + persist the profile name template and refresh the preview."""
        if self._updating:
            return
        value = self.profile_name_textctrl.text()
        if not profile_name_mod.is_valid_profile_name(value) or len(value) > 80:
            QApplication.beep()
            self.profile_name_textctrl.setText(
                profile_name_mod.sanitize_profile_name(value)
            )
        setcfg("profile.name", self.profile_name_textctrl.text())
        self.update_profile_name()

    def _profile_type_ctrl_changed(self, index: int) -> None:
        """Apply the side effects wx's ``profile_type_ctrl_handler`` performs.

        Enables :attr:`gamap_btn` only for LUT profile types, nudges black
        point compensation to the type's usual default the first time a type
        category is entered, locks profile quality to "high" for the two
        gamma-only types (Argyll only supports one quality level for those),
        resets the testchart to the new type's default
        (``set_default_testchart``), and -- only for a genuine user click,
        not the internal re-entry from :meth:`_apply_testchart_patches_amount`
        -- offers the CCXX-testchart-recommendation confirm dialog
        (``check_testchart_patches_amount``).
        """
        is_user_event = not self._profile_type_change_is_synthetic
        self._profile_type_change_is_synthetic = False
        if self._updating or index < 0:
            return
        _combo, values = self._value_combos["profile.type"]
        if index >= len(values):
            return
        new_type = values[index]
        old_type = getcfg("profile.type")

        self.gamap_btn.setEnabled(new_type in _GAMUT_MAPPABLE_PROFILE_TYPES)
        if new_type in _GAMUT_MAPPABLE_PROFILE_TYPES:
            if old_type not in _GAMUT_MAPPABLE_PROFILE_TYPES:
                setcfg("profile.black_point_compensation", 0)
        elif new_type in _CURVE_MATRIX_PROFILE_TYPES:
            if old_type not in _CURVE_MATRIX_PROFILE_TYPES:
                setcfg("profile.black_point_compensation", 1)
        else:
            setcfg("profile.black_point_compensation", 0)
        self._update_bpc()

        gamma_only = new_type in _GAMMA_ONLY_PROFILE_TYPES
        self.profile_quality_ctrl.setEnabled(not gamma_only)
        if gamma_only:
            self.profile_quality_ctrl.setValue(3)

        # wx's ``proftype_changed``: true when entering the LUT category or
        # the shaper/gamma category from outside it (not on same-category or
        # quality-only changes).
        curve_or_gamma = _CURVE_MATRIX_PROFILE_TYPES + _GAMMA_ONLY_PROFILE_TYPES
        proftype_changed = (
            new_type in _GAMUT_MAPPABLE_PROFILE_TYPES
            and old_type not in _GAMUT_MAPPABLE_PROFILE_TYPES
        ) or (new_type in curve_or_gamma and old_type not in curve_or_gamma)

        if new_type != old_type:
            self._mark_profile_settings_changed()
        setcfg("profile.type", new_type)
        self._apply_default_testchart(force=proftype_changed)
        self.update_profile_name()
        if is_user_event:
            self._check_testchart_patches_amount()

    def _apply_default_testchart(self, force: bool) -> None:
        """Reset the testchart to the current profile type's default.

        Port of ``MainFrame.set_default_testchart``: applies
        :func:`profile_name.resolve_default_testchart`'s decision. Not
        reproduced: the missing-``.ti1`` alert dialog (silently logged
        instead, matching how unreachable this branch is in practice --
        every ``TESTCHART_DEFAULTS`` entry currently resolves to ``"auto"``).
        """
        resolution = profile_name_mod.resolve_default_testchart(
            getcfg("testchart.file"),
            getcfg("profile.type"),
            slider_to_profile_quality(self.profile_quality_ctrl.value()),
            force=force,
        )
        if resolution.corrected_file:
            setcfg("testchart.file", resolution.corrected_file)
        if resolution.missing_ti1:
            print(lang.getstr("error.testchart.missing", resolution.missing_ti1))
        elif resolution.testchart_path:
            self._set_testchart(resolution.testchart_path)

    def _check_testchart_patches_amount(self) -> None:
        """Offer to bump the patch count if the selected testchart is thin.

        Port of ``MainFrame.check_testchart_patches_amount``: the confirm
        dialog and ``profile_quality_ctrl`` enable/disable bracketing it stay
        here; the recommended-count math is
        :func:`profile_name.testchart_recommendation_auto_optimize`.
        """
        auto = profile_name_mod.testchart_recommendation_auto_optimize(
            getcfg("profile.type"),
            slider_to_profile_quality(self.profile_quality_ctrl.value()),
            int(self.testchart_patches_amount.text() or 0),
            config.is_ccxx_testchart(),
        )
        if auto is None:
            return
        self.profile_quality_ctrl.setEnabled(False)
        try:
            accepted = (
                QMessageBox.question(
                    self,
                    APPNAME,
                    lang.getstr("profile.testchart_recommendation"),
                    QMessageBox.Ok | QMessageBox.Cancel,
                )
                == QMessageBox.Ok
            )
        finally:
            self.profile_quality_ctrl.setEnabled(
                not getcfg("profile.update")
                and getcfg("profile.type") not in _GAMMA_ONLY_PROFILE_TYPES
            )
        if not accepted:
            return
        setcfg("testchart.auto_optimize", auto)
        self._set_testchart("auto")

    # -- Testchart handlers -------------------------------------------------

    def _gamap_btn_handler(self) -> None:
        """Open the gamut mapping options window.

        Mirrors wx's ``self.gamapframe`` singleton: reuses a single window
        instance, raising it if already open.
        """
        window = self._gamap_window
        if window is None:
            window = GamapWindow(self)
            window.profile_settings_changed.connect(self._mark_profile_settings_changed)
            window.b2a_quality_changed.connect(self._on_gamap_b2a_quality_changed)
            self._gamap_window = window
        window.update_controls()
        window.show()
        window.raise_()
        window.activateWindow()

    def _on_gamap_b2a_quality_changed(self) -> None:
        """React to the gamut-mapping window's B2A quality controls changing.

        Mirrors wx's ``self.Parent.update_bpc()`` / ``self.Parent
        .lut3d_update_b2a_controls()`` pair, called from ``GamapFrame
        .profile_quality_b2a_ctrl_handler``.
        """
        self._update_bpc()
        self._update_lut3d_b2a_controls()

    def _create_testchart_btn_handler(self) -> None:
        """Open the testchart editor."""
        self._open_testchart_editor()

    def _open_testchart_editor(self) -> None:
        """Show the testchart editor, (re)loading the configured testchart.

        Mirrors wx's ``create_testchart_btn_handler``: reuses a single window
        instance across calls, only reloading when the configured
        ``testchart.file`` differs from what the editor currently holds (or on
        first open).
        """
        path = getcfg("testchart.file")
        window = self._testchart_editor_window
        first_open = window is None
        if first_open:
            window = TestchartEditorWindow()
            self._testchart_editor_window = window
        if path != "auto" and (
            first_open or window.ti1 is None or window.ti1.filename != path
        ):
            window.load_file(path)
        window.show()
        window.raise_()
        window.activateWindow()

    def measurement_report_btn_handler(self) -> None:
        """Run the Verification tab's current settings as a measurement report.

        Qt port of ``MainFrame.measurement_report_handler``'s entry point.
        This is the shared action-bar button (matching wx's ``buttonpanel``
        ``measurement_report_btn``, not a button local to the tab), so it can
        be pressed regardless of which tab is currently active -- exactly
        like the Calibrate/Profile/Create-3D-LUT buttons it sits beside. Its
        bool argument to :meth:`_on_report_measure_requested` mirrors wx's
        ``wx.GetKeyState(wx.WXK_ALT)`` read: holding Alt while clicking
        requests a self-check report instead of a real measurement.
        """
        self_check_report = bool(QApplication.keyboardModifiers() & Qt.AltModifier)
        self._on_report_measure_requested(self_check_report)

    def _update_measurement_report_btn_enabled(self) -> None:
        """Sync the action-bar Measure button with the Verification tab's state.

        Qt equivalent of the standalone ``ReportPanel``'s own button tracking
        :meth:`~DisplayCAL.ui.measurement_report.ReportPanel.can_measure`;
        the embedded tab has no button of its own to enable/disable (see
        :meth:`_build_verification_tab`), so the shared action-bar one does.
        """
        self.measurement_report_btn.setEnabled(self._report_panel.can_measure())

    def _report_measurement_done(self) -> None:
        """Re-enable the Measure button after a cancel/error."""
        self.measurement_report_btn.setEnabled(True)

    def _report_display_name(self) -> str:
        """The current display's label, stripped of the primary-display suffix."""
        return self.display_ctrl.currentText().replace(
            f" {lang.getstr('display.primary')}", ""
        )

    def _on_report_measure_requested(self, self_check_report: bool = False) -> None:
        """Handle the Verification tab's Measure action.

        Qt port of ``MainFrame.measurement_report_handler``: resolves the
        chart/profile/simulation setup via
        :func:`~DisplayCAL.measurement_report.resolve_report_context`, refuses
        to proceed (offering to regenerate instead) if the resolved profile's
        B2A table is low-resolution, asks where to save the report, confirms
        overwrite, then either looks the chart up directly through the
        display profile (``self_check_report``, held Alt while clicking
        Measure) or stages a real measurement through the same
        measurement-presentation engine :meth:`begin_measurement` uses for the
        calibrate/profile buttons (generalized here as
        :meth:`_begin_report_measurement` since the report flow isn't one of
        the :class:`MeasurementAction` cases).

        Args:
            self_check_report: ``True`` when Alt was held at click time (see
                :meth:`measurement_report_btn_handler`).
        """
        if not check_set_argyll_bin():
            self._report_measurement_done()
            return
        try:
            context = measurement_report_pipeline.resolve_report_context(
                self.worker, VERSION_STRING, self._report_display_name()
            )
        except measurement_report_pipeline.ReportSetupError as exception:
            QMessageBox.critical(self, APPNAME, str(exception))
            self._report_measurement_done()
            return

        if measurement_report_pipeline.profile_b2a_is_lowres(context.profile):
            self._offer_profile_hires_b2a(context.profile)
            self._report_measurement_done()
            return

        default_dir, _default_file = get_verified_path(
            None, os.path.join(getcfg("profile.save_path"), context.default_file)
        )
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            lang.getstr("save_as"),
            os.path.join(default_dir, context.default_file),
            f"{lang.getstr('filetype.html')} (*.html *.htm)",
        )
        if not path:
            self._report_measurement_done()
            return
        path = make_argyll_compatible_path(path)
        if not waccess(path, os.W_OK):
            QMessageBox.critical(
                self, APPNAME, lang.getstr("error.access_denied.write", path)
            )
            self._report_measurement_done()
            return
        save_path = f"{os.path.splitext(path)[0]}.html"
        setcfg("last_filedialog_path", save_path)
        if os.path.exists(save_path):
            answer = QMessageBox.warning(
                self,
                APPNAME,
                lang.getstr("dialog.confirm_overwrite", save_path),
                QMessageBox.Ok | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if answer != QMessageBox.Ok:
                self._report_measurement_done()
                return

        self._pending_report_context = context
        self._pending_report_save_path = save_path
        self._pending_report_self_check = self_check_report and bool(context.oprof)
        if self._pending_report_self_check:
            self._run_report_self_check()
        else:
            self._begin_report_measurement()

    def _offer_profile_hires_b2a(self, profile: ICCProfile) -> None:
        """Offer to regenerate a profile's low-resolution B2A tables.

        Qt port of ``check_profile_b2a_hires``: the profile is never allowed
        to proceed to the report (or, via :meth:`_on_profile_build_finished`,
        the install offer) with a sub-17-step Argyll-generated B2A table --
        this only offers to fix that up as an async side effect via
        ``worker.update_profile_B2A``; the caller always aborts its own flow
        regardless of the user's answer here.

        Args:
            profile: The profile whose B2A tables are low-resolution.
        """
        answer = QMessageBox.question(
            self,
            APPNAME,
            lang.getstr("profile.b2a.lowres.warning"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        self._pending_hires_b2a_profile = profile
        controller = self._ensure_run_controller()
        controller.run(
            self.worker.update_profile_B2A,
            self._on_profile_hires_b2a_finished,
            wargs=(profile,),
            wkwargs={"clutres": getcfg("profile.b2a.hires.size")},
            progress_msg=lang.getstr("profile.b2a.hires"),
            pauseable=False,
        )

    def _on_profile_hires_b2a_finished(self, result: object) -> None:
        """Save the regenerated profile and offer to install it.

        Qt port of ``profile_hires_b2a_consumer`` (minus the "let the user
        re-pick an arbitrary profile" dialog, since this Qt port only reaches
        here from the measurement-report flow's already-resolved profile).

        Args:
            result: ``True``/a truthy value on success, ``False`` when the
                run did not complete, or an ``Exception`` on failure.
        """
        profile = self._pending_hires_b2a_profile
        if isinstance(result, Exception):
            QMessageBox.critical(self, APPNAME, str(result))
            return
        if not result:
            QMessageBox.information(
                self, APPNAME, lang.getstr("error.profile.file_not_created")
            )
            return
        profile_save_path = profile.filename
        if not profile_save_path or not os.path.isfile(profile_save_path):
            default_dir, default_file = os.path.split(profile_save_path or "")
            path, _filter = QFileDialog.getSaveFileName(
                self,
                lang.getstr("save_as"),
                os.path.join(default_dir, default_file),
                f"{lang.getstr('filetype.icc')} (*.icc *.icm)",
            )
            if not path:
                return
            filename, ext = os.path.splitext(path)
            if ext.lower() not in (".icc", ".icm"):
                path += PROFILE_EXT
            profile.setDescription(os.path.basename(filename))
            profile_save_path = path
        if not waccess(profile_save_path, os.W_OK):
            QMessageBox.critical(
                self,
                APPNAME,
                lang.getstr("error.access_denied.write", profile_save_path),
            )
            return
        profile.calculate_id()
        profile.write(profile_save_path)
        if self._install_profile_window is None:
            self._install_profile_window = InstallProfileWindow()
        self._install_profile_window.load_profile(profile_save_path)
        self._install_profile_window.show()
        self._install_profile_window.raise_()
        self._install_profile_window.activateWindow()

    def _synthicc_create_action_handler(self) -> None:
        """Open the synthetic ICC creator (Tools > Advanced menu).

        Qt port of ``synthicc_create_handler``: reuses a single
        :class:`~DisplayCAL.ui.tools.synth_profile.SynthICCWindow` instance
        across opens, matching wx's ``self.synthiccframe`` singleton.
        """
        window = self._synthicc_window
        if window is None:
            window = SynthICCWindow()
            self._synthicc_window = window
        window.show()
        window.raise_()
        window.activateWindow()

    def _lut3d_window_action_handler(self) -> None:
        """Open the standalone 3D LUT maker (Tools > Advanced menu).

        Unlike this menu's other entries, wx has no matching menu item for
        this -- ``LUT3DFrame`` was only ever reachable as its own console-
        script application (``displaycal-3dlut-maker``). This is a new
        cross-link (not a port) to the already-complete standalone
        :class:`~DisplayCAL.ui.tools.lut3d.LUT3DWindow`, following the same
        singleton pattern as :meth:`_synthicc_create_action_handler`.
        """
        window = self._lut3d_window
        if window is None:
            window = LUT3DWindow()
            self._lut3d_window = window
        window.show()
        window.raise_()
        window.activateWindow()

    def _profile_hires_b2a_action_handler(self) -> None:
        """Standalone "Regenerate hires B2A tables..." tool (Tools > Advanced menu).

        Qt port of ``profile_hires_b2a_handler`` when reached with no profile
        argument -- i.e. always, from this menu action; the automatic
        low-res-detected call site (``check_profile_b2a_hires``) is
        :meth:`_offer_profile_hires_b2a`. Lets the user pick an arbitrary
        profile via :meth:`_select_profile_for_hires_b2a`, validates it has
        an ``LUT16Type`` A2B table in an XYZ/Lab PCS, then regenerates its
        B2A tables via ``worker.update_profile_B2A``, reusing
        :meth:`_on_profile_hires_b2a_finished` for the save/install offer.
        """
        profile = self._select_profile_for_hires_b2a()
        if profile is None:
            return
        if not ("A2B0" in profile.tags or "A2B1" in profile.tags):
            QMessageBox.critical(
                self,
                APPNAME,
                lang.getstr(
                    "profile.required_tags_missing",
                    f"A2B0 {lang.getstr('or')} A2B1",
                ),
            )
            return
        if ("A2B0" in profile.tags and not isinstance(profile.tags.A2B0, LUT16Type)) or (
            "A2B1" in profile.tags and not isinstance(profile.tags.A2B1, LUT16Type)
        ):
            QMessageBox.critical(
                self,
                APPNAME,
                lang.getstr("profile.required_tags_missing", "LUT16Type"),
            )
            return
        if profile.connectionColorSpace not in (b"XYZ", b"Lab"):
            QMessageBox.critical(
                self,
                APPNAME,
                lang.getstr(
                    "profile.unsupported",
                    (
                        profile.connectionColorSpace.decode("utf-8"),
                        profile.connectionColorSpace.decode("utf-8"),
                    ),
                ),
            )
            return
        self._pending_hires_b2a_profile = profile
        controller = self._ensure_run_controller()
        controller.run(
            self.worker.update_profile_B2A,
            self._on_profile_hires_b2a_finished,
            wargs=(profile,),
            wkwargs={"clutres": getcfg("profile.b2a.hires.size")},
            progress_msg=lang.getstr("profile.b2a.hires"),
            pauseable=False,
        )

    def _select_profile_for_hires_b2a(self) -> ICCProfile | None:
        """Pick a profile for :meth:`_profile_hires_b2a_action_handler`.

        Simplified Qt port of ``select_profile(ignore_current_profile=False)``:
        offers the current display/output profile first (if any) via a
        3-button choice (current / browse / cancel, matching
        :meth:`_fast_matrix_shaper_choice`'s pattern for a custom-labelled
        3-button ``QMessageBox``), falling back straight to a file browse
        when there is no current profile.

        Returns:
            The selected profile, or ``None`` if the user cancelled or the
            chosen file could not be parsed.
        """
        profile = config.get_current_profile(True)
        if profile:
            box = QMessageBox(self)
            box.setWindowTitle(lang.getstr("profile.b2a.hires"))
            box.setIcon(QMessageBox.Question)
            box.setText(lang.getstr("profile.choose"))
            current_button = box.addButton(
                lang.getstr("profile.current"), QMessageBox.AcceptRole
            )
            browse_button = box.addButton(
                lang.getstr("browse"), QMessageBox.ActionRole
            )
            box.addButton(lang.getstr("cancel"), QMessageBox.RejectRole)
            box.exec_()
            clicked = box.clickedButton()
            if clicked is current_button:
                return profile
            if clicked is not browse_button:
                return None
        default_dir, default_file = get_verified_path("last_icc_path")
        path, _filter = QFileDialog.getOpenFileName(
            self,
            lang.getstr("profile.choose"),
            os.path.join(default_dir, default_file or ""),
            f"{lang.getstr('filetype.icc')} (*.icc *.icm)",
        )
        if not path:
            return None
        try:
            return ICCProfile(path)
        except (OSError, ICCProfileInvalidError) as exception:
            QMessageBox.critical(self, APPNAME, str(exception))
            return None

    def _specplot_action_handler(self) -> None:
        """Run Argyll ``specplot`` on a user-picked file (Tools > Advanced menu).

        Qt port of ``MainFrame.specplot_handler``.
        """
        if not check_set_argyll_bin():
            return
        default_dir, default_file = get_verified_path("last_specplot_path")
        path, _filter = QFileDialog.getOpenFileName(
            self,
            lang.getstr("specplot.choose"),
            os.path.join(default_dir, default_file or ""),
            f"{lang.getstr('filetype.any')} (*.*)",
        )
        if not path:
            return
        setcfg("last_specplot_path", path)
        cmd = get_argyll_util("specplot")
        if not cmd:
            QMessageBox.critical(
                self, APPNAME, lang.getstr("argyll.util.not_found", "specplot")
            )
            return
        args = ["-v"]
        if getcfg("extra_args.specplot").strip():
            args += parse_argument_string(getcfg("extra_args.specplot"))
        args.append(path)
        self.worker.interactive = False
        controller = self._ensure_run_controller()
        controller.run(
            self.worker.exec_cmd,
            self._on_specplot_finished,
            wargs=(cmd, args),
            wkwargs={"skip_scripts": True},
            progress_msg=lang.getstr("specplot.run"),
            pauseable=False,
        )

    def _on_specplot_finished(self, result: object) -> None:
        """Qt port of ``MainFrame.specplot_consumer``."""
        if isinstance(result, Exception):
            QMessageBox.critical(self, APPNAME, str(result))
        self.worker.wrapup(False)
        self.show()

    def _measure_testchart_action_handler(self) -> None:
        """Standalone "Measure testchart..." tool (Tools > Advanced menu).

        Qt port of ``MainFrame.measure_handler``: runs a characterization
        measurement pass without building a profile afterward, unlike the
        Profiling tab's "Profile" button (:meth:`profile_btn_handler`, which
        chains into :meth:`_build_profile_from_measurement`'s ``colprof``
        stage). Used either as a plain "capture a TI3 for this testchart"
        tool, or -- when the configured testchart is a CCXX reference/
        colorimeter chart -- to gather the raw measurement a colorimeter-
        correction matrix is built from.

        Not reproduced: wx chains a successful CCXX measurement started
        *from* the correction-creation dialog (``comport.number.backup`` is
        set) back into ``create_colorimeter_correction_handler`` with the
        new TI3 paths pre-filled. The Qt ``CreateCorrectionWindow`` doesn't
        have a matching "measure now" entry point that would set that
        backup, so the chain is unreachable here too --
        :meth:`_restore_measurement_mode_and_testchart` is still ported
        (a cheap no-op today) so a future session wiring that entry point
        doesn't also have to add this half.
        """
        if not self._setup_ccxx_measurement():
            self._restore_measurement_mode_and_testchart()
            return
        if not check_set_argyll_bin() or not self._check_overwrite(".ti3"):
            self._restore_measurement_mode_and_testchart()
            return
        if config.is_ccxx_testchart():
            apply_calibration = config.get_data_path("linear.cal")
        else:
            apply_calibration = self._current_cal_choice()
        if apply_calibration is CAL_CHOICE_CANCELLED:
            self._restore_measurement_mode_and_testchart()
            return
        self._pending_apply_calibration = apply_calibration
        self._begin_testchart_measurement()

    def _setup_ccxx_measurement(self) -> bool:
        """Qt port of ``MainFrame.setup_ccxx_measurement``.

        A no-op (returns ``True``) unless the configured testchart is a CCXX
        reference/colorimeter chart. Ensures ``profile.save_path`` is set
        (prompting via :meth:`_profile_save_path_btn_handler` if empty) and
        is writable, then stages ``measurement.save_path`` /
        ``measurement.name.expanded`` for the upcoming measurement.

        Unlike wx (which ignores this method's implicit success/failure and
        proceeds to measure regardless), :meth:`_measure_testchart_action_handler`
        bails out when this returns ``False`` -- proceeding with a stale or
        unset ``measurement.name.expanded`` would only fail later in a more
        confusing way.

        Returns:
            ``False`` if the save-path picker was cancelled or the resolved
            path isn't writable (an error dialog is shown in that case);
            ``True`` otherwise (including the non-CCXX no-op case).
        """
        if not config.is_ccxx_testchart():
            return True
        path = getcfg("profile.save_path")
        if not path:
            self._profile_save_path_btn_handler()
            path = getcfg("profile.save_path")
        if not path:
            return False
        if not waccess(path, os.W_OK):
            QMessageBox.critical(
                self, APPNAME, lang.getstr("error.access_denied.write", path)
            )
            return False
        setcfg("measurement.save_path", path)
        setcfg(
            "measurement.name.expanded",
            measurement_report_pipeline.compute_ccxx_measurement_basename(
                self.worker
            ),
        )
        return True

    def _begin_testchart_measurement(self) -> None:
        """Stage the standalone testchart measurement and present the measure area.

        Qt port of the ``setup_measurement(self.just_measure, ...)`` call at
        the end of ``measure_handler``, generalized from
        :meth:`begin_measurement` (which is keyed on :class:`MeasurementAction`)
        the same way :meth:`_begin_report_measurement` is.
        """
        writecfg()
        plan = self.flow.plan_measurement(
            self._drive_testchart_measurement,
            use_patternwindow=getattr(self.worker, "_use_patternwindow", False),
        )
        if plan.mode is PresentationMode.CALL_PENDING:
            self.call_pending_function()
        elif plan.mode is PresentationMode.SHOW_FRAME:
            self._present_measureframe()
        else:
            self._start_measureframe_subprocess()

    def _drive_testchart_measurement(self) -> None:
        """Restore the main window and run the staged testchart measurement."""
        self._restore_after_measurement()
        self._run_measure_testchart()

    def _run_measure_testchart(self) -> None:
        """Qt port of ``MainFrame.just_measure`` (the non-auto-measure path)."""
        self.worker.dispread_after_dispcal = False
        self.worker.interactive = config.get_display_name() == "Untethered"
        setcfg("calibration.file.previous", None)
        apply_calibration = self._pending_apply_calibration
        self._pending_apply_calibration = True
        controller = self._ensure_run_controller()
        controller.run(
            self.worker.measure,
            self._on_measure_testchart_finished,
            wkwargs={"apply_calibration": apply_calibration},
            progress_msg=lang.getstr("measuring.characterization"),
            pauseable=True,
        )

    def _on_measure_testchart_finished(self, result: object) -> None:
        """Qt port of ``MainFrame.just_measure_finish``.

        Unlike :meth:`_on_measurement_finished` (the "Profile" button's
        finish handler), this never builds an ICC profile: it just reviews
        and copies the measured TI3, then either records it as a
        colorimeter-correction source (CCXX testchart) or offers to open the
        containing folder.
        """
        if not isinstance(result, Exception) and result:
            result = self._check_copy_ti3()
        self.worker.wrapup(copy=False, remove=True)
        self.show()
        self.raise_()
        if isinstance(result, Exception):
            QMessageBox.critical(self, APPNAME, str(result))
        elif result and config.is_ccxx_testchart():
            self._record_ccxx_measurement_paths()
        elif result:
            self._offer_open_measurement_folder()
        self._restore_measurement_mode_and_testchart()

    def _check_copy_ti3(self) -> bool | Exception:
        """Qt port of ``MainFrame.check_copy_ti3``: review then copy the TI3.

        Used by :meth:`_on_measure_testchart_finished`. Deliberately not
        (yet) unified with :meth:`_build_profile_from_measurement`'s inline
        equivalent, which tolerates a falsy (non-exception) copy result
        differently -- that method still proceeds to the ``colprof`` stage
        either way, while this method's caller does not.
        """
        ti3_path = measurement_report_pipeline.resolve_working_ti3_path(self.worker)
        if ti3_path:
            try:
                ti3 = CGATS(ti3_path)
            except (OSError, CGATSError) as exception:
                return exception
            proceed, _removed_items = self._check_measurement_sanity(ti3)
            if not proceed:
                return False
        return self.worker.wrapup(copy=True, remove=False, ext_filter=[".ti3"])

    def _record_ccxx_measurement_paths(self) -> None:
        """Record the just-measured CCXX TI3 for correction-matrix creation.

        Qt port of the ``is_ccxx_testchart()`` branch of
        ``just_measure_finish`` (minus the ``comport.number.backup`` chain,
        see :meth:`_measure_testchart_action_handler`'s docstring).
        """
        ti3_path = os.path.join(
            getcfg("measurement.save_path"),
            getcfg("measurement.name.expanded"),
            getcfg("measurement.name.expanded") + ".ti3",
        )
        try:
            cgats = CGATS(ti3_path)
        except (OSError, CGATSError) as exception:
            QMessageBox.critical(self, APPNAME, str(exception))
            return
        if cgats.queryv1("INSTRUMENT_TYPE_SPECTRAL") == b"YES":
            setcfg("last_reference_ti3_path", cgats.filename)
        else:
            setcfg("last_colorimeter_ti3_path", cgats.filename)

    def _offer_open_measurement_folder(self) -> None:
        """Qt port of ``MainFrame.just_measure_show_result``."""
        path = os.path.join(
            getcfg("profile.save_path"),
            getcfg("profile.name.expanded"),
            getcfg("profile.name.expanded") + ".ti3",
        )
        answer = QMessageBox.question(
            self,
            APPNAME,
            lang.getstr("measurements.complete"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            launch_file(os.path.dirname(path))

    def _restore_measurement_mode_and_testchart(self) -> None:
        """Qt port of ``MainFrame.restore_measurement_mode`` + ``restore_testchart``.

        Currently a no-op in practice: the backup keys these restore
        (``measurement_mode.backup`` etc.) are only ever set by the
        correction-creation dialog's "measure now" flow, which isn't wired
        up in this port yet (see :meth:`_measure_testchart_action_handler`).
        """
        if getcfg("measurement_mode.backup", False):
            setcfg("measurement_mode", getcfg("measurement_mode.backup"))
            setcfg("measurement_mode.backup", None)
            if getcfg("comport.number.backup", False):
                setcfg("comport.number", getcfg("comport.number.backup"))
                setcfg("comport.number.backup", None)
                self.update_comports()
            else:
                self.update_measurement_mode_ctrl()
        if getcfg("observer.backup", False):
            setcfg("observer", getcfg("observer.backup"))
            setcfg("observer.backup", None)
        if getcfg("testchart.file.backup", False):
            self._set_testchart(getcfg("testchart.file.backup"))
            setcfg("testchart.file.backup", None)

    def _measurement_file_check_action_handler(self) -> None:
        """Standalone "Check measurement file..." tool (Tools > Advanced menu).

        Qt port of ``measurement_file_check_handler``: lets the user pick an
        arbitrary ``.ti3`` file or an ICC profile with an embedded TI3 chart
        and runs it through the same suspicious-patch review
        :meth:`_check_measurement_sanity` uses for a live measurement,
        forced (``force=True``, bypassing the ``ti3.check_sanity.auto`` gate,
        matching wx passing ``True`` at this one call site). A plain ``.ti3``
        file is then saved back to a user-chosen location.

        A checked embedded-TI3 chart instead offers to regenerate the profile
        it came from (wx's ``profile`` branch): the updated chart is
        re-embedded into a temp copy of the source profile, which is then run
        through :meth:`_run_create_profile` with ``skip_ti3_check=True``
        (matching wx's ``create_profile_handler(None, tmp_path, True)``
        re-entry) -- the same "create profile from existing measurements"
        pipeline the File menu's ``create_profile`` action uses.
        """
        default_dir, default_file = get_verified_path("last_ti3_path")
        path, _filter = QFileDialog.getOpenFileName(
            self,
            lang.getstr("measurement_file.choose"),
            os.path.join(default_dir, default_file or ""),
            f"{lang.getstr('filetype.icc_ti3')} (*.icc *.icm *.ti3)",
        )
        if not path:
            return
        if not os.path.exists(path):
            QMessageBox.critical(self, APPNAME, lang.getstr("file.missing", path))
            return
        try:
            loaded = measurement_report_pipeline.load_measurement_file(path)
        except measurement_report_pipeline.MeasurementFileError as exception:
            QMessageBox.critical(self, APPNAME, str(exception))
            return
        setcfg("last_ti3_path", path)
        ti3 = loaded.ti3
        proceed, _removed_items = self._check_measurement_sanity(ti3, force=True)
        if not proceed:
            return
        if not ti3.modified:
            QMessageBox.information(self, APPNAME, lang.getstr("errors.none_found"))
            return

        if loaded.profile is not None:
            answer = QMessageBox.question(
                self,
                APPNAME,
                lang.getstr("profile.confirm_regeneration"),
                QMessageBox.Ok | QMessageBox.Cancel,
                QMessageBox.Ok,
            )
            if answer != QMessageBox.Ok:
                return
            self.worker.wrapup(False)
            tmp_working_dir = self.worker.create_tempdir()
            if isinstance(tmp_working_dir, Exception):
                QMessageBox.critical(self, APPNAME, str(tmp_working_dir))
                return
            tag_data = measurement_report_pipeline.build_regenerated_profile_tag_data(
                ti3
            )
            loaded.profile.tags.targ = TextType(tag_data, b"targ")
            loaded.profile.tags.DevD = loaded.profile.tags.CIED = loaded.profile.tags.targ
            tmp_path = os.path.join(tmp_working_dir, os.path.basename(path))
            loaded.profile.write(tmp_path)
            self._run_create_profile([tmp_path], skip_ti3_check=True)
            return

        save_path, _filter = QFileDialog.getSaveFileName(
            self,
            lang.getstr("save_as"),
            os.path.join(os.path.dirname(path), os.path.basename(path)),
            f"{lang.getstr('filetype.ti3')} (*.ti3)",
        )
        if not save_path:
            return
        if not waccess(save_path, os.W_OK):
            QMessageBox.critical(
                self, APPNAME, lang.getstr("error.access_denied.write", save_path)
            )
            return
        try:
            ti3.write(save_path)
        except OSError as exception:
            QMessageBox.critical(self, APPNAME, str(exception))

    def _measurement_file_check_auto_toggled(self, checked: bool) -> None:
        """Persist the "check automatically" toggle (Tools > Advanced menu).

        Qt port of ``measurement_file_check_auto_handler``: warns once (via a
        confirm dialog) before turning the automatic check on, since from
        then on it silently reviews every measurement/report TI3; turning it
        back off needs no confirmation.
        """
        if checked and not getcfg("ti3.check_sanity.auto"):
            answer = QMessageBox.question(
                self,
                APPNAME,
                lang.getstr("measurement_file.check_sanity.auto.warning"),
                QMessageBox.Ok | QMessageBox.Cancel,
                QMessageBox.Ok,
            )
            if answer != QMessageBox.Ok:
                self.measurement_file_check_auto_action.blockSignals(True)
                self.measurement_file_check_auto_action.setChecked(False)
                self.measurement_file_check_auto_action.blockSignals(False)
                return
        setcfg("ti3.check_sanity.auto", int(checked))

    def _check_measurement_sanity(
        self, ti3: CGATS, force: bool = False
    ) -> tuple[bool, list]:
        """Review/apply suspicious-patch edits before a TI3 is used further.

        Qt port of ``measurement_file_check_confirm``: shows
        :class:`~DisplayCAL.ui.measurement_sanity_dialog.MeasurementSanityDialog`
        only when :func:`~DisplayCAL.measurement_report.resolve_sanity_check`
        finds something suspicious, applies the user's edits/removals, and
        writes the (possibly modified) TI3 back to disk.

        Args:
            ti3: The measured TI3 (or the whole CGATS document containing it).
            force: Skip the ``ti3.check_sanity.auto`` gate. Used directly by
                :meth:`_measurement_file_check_action_handler` (the
                standalone "check measurement file" tool).

        Returns:
            ``(proceed, removed_items)``: ``proceed`` is ``False`` only if
            the user cancelled the review dialog. ``removed_items`` lists the
            CGATS items removed (empty when nothing was removed or no review
            was needed).
        """
        sanity_ctx = measurement_report_pipeline.resolve_sanity_check(ti3, force=force)
        if sanity_ctx is None:
            return True, []
        title = (
            os.path.basename(ti3.filename)
            if ti3.filename
            else lang.getstr("measurement_file.check_sanity")
        )
        dialog = MeasurementSanityDialog(self, title, sanity_ctx, force=force)
        if dialog.exec() != QDialog.Accepted:
            return False, []
        removed_items = measurement_report_pipeline.apply_sanity_check_result(
            sanity_ctx, dialog.removed_row_indexes(), dialog.mods()
        )
        if ti3.modified and ti3.filename and os.path.exists(ti3.filename) and not force:
            try:
                ti3.write()
            except OSError as exception:
                QMessageBox.critical(self, APPNAME, str(exception))
                return False, []
        return True, removed_items

    def _run_report_self_check(self) -> None:
        """Look the chart up through the display profile instead of measuring.

        Qt port of ``measurement_report_handler``'s ``self_check_report and
        oprof`` branch: no instrument is involved, so this runs synchronously
        (no progress dialog / worker thread) via
        :func:`~DisplayCAL.measurement_report.perform_self_check_lookup`, then
        feeds the result into :meth:`_on_report_measurement_finished` exactly
        like a real measurement would.
        """
        context = self._pending_report_context
        try:
            ti3_path, oprof = measurement_report_pipeline.perform_self_check_lookup(
                self.worker,
                context.ti1,
                context.oprof,
                context.devlink,
                self._pending_report_save_path,
            )
        except Exception as exception:
            QMessageBox.critical(self, APPNAME, str(exception))
            self._report_measurement_done()
            return
        context.oprof = oprof
        self._pending_report_ti1_path = f"{os.path.splitext(ti3_path)[0]}.ti1"
        self._on_report_measurement_finished(True)

    def _begin_report_measurement(self) -> None:
        """Stage the report measurement and present the measurement area.

        Qt port of the ``setup_measurement`` call at the end of
        ``measurement_report_handler``, generalized from
        :meth:`begin_measurement` (which is keyed on :class:`MeasurementAction`)
        since the report flow doesn't fit that enum.
        """
        writecfg()
        plan = self.flow.plan_measurement(
            self._drive_report_measurement,
            use_patternwindow=getattr(self.worker, "_use_patternwindow", False),
        )
        if plan.mode is PresentationMode.CALL_PENDING:
            self.call_pending_function()
        elif plan.mode is PresentationMode.SHOW_FRAME:
            self._present_measureframe()
        else:
            self._start_measureframe_subprocess()

    def _drive_report_measurement(self) -> None:
        """Restore the main window and run the staged report measurement."""
        self._restore_after_measurement()
        self._run_report_measurement()

    def _run_report_measurement(self) -> None:
        """Stage TI1/cal files and run ``measure_ti1``.

        Qt port of ``MainFrame.measurement_report`` (the part before
        ``worker.start``).
        """
        context = self._pending_report_context
        self.worker.dispread_after_dispcal = False
        self.worker.interactive = config.get_display_name() == "Untethered"
        try:
            ti1_path, cal_path = measurement_report_pipeline.stage_measurement_files(
                self.worker,
                self._pending_report_save_path,
                context.ti1,
                context.oprof,
                context.profile,
                context.use_sim_as_output,
                context.devlink,
            )
        except Exception as exception:
            QMessageBox.critical(self, APPNAME, str(exception))
            self.worker.wrapup(False)
            self._report_measurement_done()
            return
        self._pending_report_ti1_path = ti1_path
        controller = self._ensure_run_controller()
        controller.run(
            self.worker.measure_ti1,
            self._on_report_measurement_finished,
            wargs=(ti1_path, cal_path, context.colormanaged),
            progress_msg=lang.getstr("measurement_report"),
            pauseable=True,
        )

    def _on_report_measurement_finished(self, result: object) -> None:
        """Process a completed report measurement and write the HTML report.

        Qt port of ``MainFrame.measurement_report_consumer``: the sanity-check
        review (see :meth:`_check_measurement_sanity`) runs first, then the
        numeric TI3 processing and ``placeholders2data`` assembly, which live
        in :func:`~DisplayCAL.measurement_report.finalize_measurement_report`.

        Args:
            result (object): ``True`` on success, ``False`` / ``None`` when
                the run did not complete, or an ``Exception`` on failure.
        """
        self.show()
        self.raise_()
        self._report_measurement_done()
        if isinstance(result, Exception):
            QMessageBox.critical(self, APPNAME, str(result))
            self.worker.wrapup(result)
            return
        if not result:
            self.worker.wrapup(False)
            return
        context = self._pending_report_context
        ti3_path = os.path.splitext(self._pending_report_ti1_path)[0] + ".ti3"
        try:
            ti3_measured = CGATS(ti3_path)[0]
        except (OSError, CGATSError) as exception:
            QMessageBox.critical(self, APPNAME, str(exception))
            self.worker.wrapup(exception)
            return
        proceed, removed_items = self._check_measurement_sanity(ti3_measured)
        if not proceed:
            self.worker.wrapup(False)
            return
        try:
            measurement_report_pipeline.finalize_measurement_report(
                worker=self.worker,
                ti3_path=ti3_path,
                profile=context.profile,
                sim_profile=context.sim_profile,
                intent=context.intent,
                sim_intent=context.sim_intent,
                devlink=context.devlink,
                ti3_ref=context.ti3_ref,
                sim_ti3=context.sim_ti3,
                save_path=self._pending_report_save_path,
                chart=context.chart,
                gray=context.gray,
                apply_trc=context.apply_trc,
                use_sim=context.use_sim,
                use_sim_as_output=context.use_sim_as_output,
                oprof=context.oprof,
                instrument_name=self.comport_ctrl.currentText(),
                measurement_mode_name=self.measurement_mode_ctrl.currentText(),
                display_name=self._report_display_name(),
                observers=self._observers,
                version_string=VERSION_STRING,
                pack_js=bool(getcfg("report.pack_js")),
                self_check_report=self._pending_report_self_check,
                removed_items=removed_items,
            )
        except Exception as exception:
            QMessageBox.critical(self, APPNAME, str(exception))

    def _testchart_ctrl_changed(self, index: int) -> None:
        """Load the newly selected testchart."""
        if self._updating or index < 0 or index >= len(self._testchart_paths):
            return
        self._set_testchart(self._testchart_paths[index])

    def _testchart_btn_handler(self) -> None:
        """Browse for a testchart/profile file and load it as the testchart."""
        default_dir, default_file = get_verified_path("testchart.file")
        path, _filter = QFileDialog.getOpenFileName(
            self,
            lang.getstr("dialog.set_testchart"),
            os.path.join(default_dir, default_file),
            f"{lang.getstr('filetype.icc_ti1_ti3')} (*.icc *.icm *.ti1 *.ti3)",
        )
        if not path:
            return
        if not os.path.exists(path):
            QMessageBox.critical(
                self, self.windowTitle(), lang.getstr("file.missing", path)
            )
            return
        if os.path.splitext(path)[-1].lower() in (".icc", ".icm"):
            try:
                profile = ICCProfile(path)
            except (OSError, ICCProfileInvalidError):
                QMessageBox.critical(
                    self,
                    self.windowTitle(),
                    lang.getstr("profile.invalid") + "\n" + path,
                )
                return
            if not profile_name_mod.icc_profile_has_embedded_ti3(profile):
                QMessageBox.critical(
                    self,
                    self.windowTitle(),
                    lang.getstr("profile.no_embedded_ti3") + "\n" + path,
                )
                return
        self._set_testchart(path)
        writecfg()
        self._mark_profile_settings_changed()

    def _set_testcharts(self, path: str | None = None) -> None:
        """Repopulate ``testchart_ctrl`` from the given (or configured) path."""
        current = self.testchart_ctrl.currentIndex()
        names, self._testchart_paths = profile_name_mod.get_testchart_names(path)
        self.testchart_ctrl.blockSignals(True)
        self.testchart_ctrl.clear()
        self.testchart_ctrl.addItems(names)
        if 0 <= current < self.testchart_ctrl.count():
            self.testchart_ctrl.setCurrentIndex(current)
        self.testchart_ctrl.blockSignals(False)

    def _set_testchart(self, path: str | None = None) -> None:
        """Load ``path`` (or the configured testchart) as the active testchart.

        Mirrors wx's ``MainFrame.set_testchart``. Not reproduced (see
        ``profile_name.py``'s module docstring): the Untethered-display
        "auto" warning dialog, and the testchart-editor live-refresh
        (``TestchartEditor`` isn't ported).
        """
        if path is None:
            path = getcfg("testchart.file")
        filename, ext = os.path.splitext(path)
        ti1_path = f"{filename}.ti1"
        if (
            ext.lower() in (".icc", ".icm")
            and getcfg("testchart.patch_sequence")
            != "optimize_display_response_delay"
            and os.path.isfile(ti1_path)
        ):
            path = ti1_path

        self.create_testchart_btn.setEnabled(
            path != "auto" and not getcfg("profile.update")
        )
        self._profiling_form.setRowVisible(self._patches_row_widget, path == "auto")

        if path == "auto":
            if path != getcfg("testchart.file"):
                self._mark_profile_settings_changed()
            setcfg("testchart.file", path)
            if path not in self._testchart_paths:
                self._set_testcharts(path)
            self.testchart_ctrl.blockSignals(True)
            self.testchart_ctrl.setCurrentIndex(0)
            self.testchart_ctrl.setToolTip("")
            self.testchart_ctrl.blockSignals(False)
            self.worker.options_targen = ["-d3"]
            auto = int(getcfg("testchart.auto_optimize") or 7)
            self.testchart_patches_amount_ctrl.blockSignals(True)
            self.testchart_patches_amount_ctrl.setValue(auto)
            self.testchart_patches_amount_ctrl.blockSignals(False)
            self._apply_testchart_patches_amount(auto, from_user_event=False)
            self._current_testchart_path = path
        else:
            self._set_testchart_from_path(path)

        self.update_colorimeter_correction_matrix_ctrl()
        self.update_profile_name()

    def _set_testchart_from_path(self, path: str) -> None:
        """Load, validate and select a fixed (non-"auto") testchart file."""
        result = check_file_isfile(path)
        if isinstance(result, Exception):
            QMessageBox.critical(self, self.windowTitle(), str(result))
            self._set_testchart("auto")
            return
        if getattr(self, "_current_testchart_path", None) == path:
            return
        try:
            ti1 = profile_name_mod.load_testchart_from_file(path)
        except Exception as exception:
            QMessageBox.critical(
                self,
                self.windowTitle(),
                lang.getstr("error.testchart.read", path) + "\n\n" + str(exception),
            )
            self._set_testchart("auto")
            return
        if path != getcfg("calibration.file", False):
            self._mark_profile_settings_changed()
        setcfg("testchart.file", path)
        if path not in self._testchart_paths:
            self._set_testcharts(path)
        index = calibration_file.index_fallback_ignorecase(
            self._testchart_paths, path
        )
        self.testchart_ctrl.blockSignals(True)
        self.testchart_ctrl.setCurrentIndex(max(index, 0))
        self.testchart_ctrl.setToolTip(path)
        self.testchart_ctrl.blockSignals(False)
        color_rep = ti1.queryv1("COLOR_REP")
        if color_rep and color_rep[:3] == "RGB":
            self.worker.options_targen = ["-d3"]
        self.testchart_patches_amount.setText(str(ti1.queryv1("NUMBER_OF_SETS")))
        self._current_testchart_path = path
        self._update_testchart_meas_time()

    def _testchart_patches_amount_changed(self, value: int) -> None:
        """Persist the auto-optimize slider value and refresh derived state."""
        if self._updating:
            return
        setcfg("testchart.auto_optimize", value)
        self._mark_profile_settings_changed()
        self._apply_testchart_patches_amount(value, from_user_event=True)

    def _apply_testchart_patches_amount(
        self, auto: int, from_user_event: bool
    ) -> None:
        """Recompute the patch count and (on user changes) nudge profile type.

        Port of ``testchart_patches_amount_ctrl_handler``'s non-dialog body.
        wx re-enters ``profile_type_ctrl_handler(None)`` here (``event=None``),
        which still resets the default testchart but skips the CCXX
        recommendation dialog; ``_profile_type_change_is_synthetic`` gets
        ``_profile_type_ctrl_changed`` the same treatment for both ways this
        can reach it below.
        """
        if from_user_event:
            old_type = getcfg("profile.type")
            suggested = profile_name_mod.suggested_profile_type_for_auto(
                auto, old_type, bool(getcfg("3dlut.create"))
            )
            if suggested and suggested != old_type:
                _combo, values = self._value_combos["profile.type"]
                index = values.index(suggested)
                self._profile_type_change_is_synthetic = True
                if self.profile_type_ctrl.currentIndex() == index:
                    # The combo already displays the suggested type (config
                    # was changed directly, bypassing the combo) -- Qt won't
                    # emit ``currentIndexChanged`` for a same-index set, so
                    # apply the side effects directly instead of relying on
                    # the signal.
                    self._profile_type_ctrl_changed(index)
                else:
                    self.profile_type_ctrl.setCurrentIndex(index)
        patches_amount = profile_name_mod.testchart_patches_amount_for_auto(auto)
        self.testchart_patches_amount.setText(str(patches_amount))
        self._update_testchart_meas_time()
        self.update_profile_name()

    def _testchart_patch_sequence_row_gate(self) -> None:
        """Gate the patch-sequence row behind ``show_advanced_options``."""
        self._profiling_form.setRowVisible(
            self.testchart_patch_sequence_ctrl, bool(getcfg("show_advanced_options"))
        )

    def _update_testchart_meas_time(self) -> None:
        """Refresh the estimated-measurement-time label, per wx's coloring rule."""
        patches = int(self.testchart_patches_amount.text() or 0)
        estimate = profile_name_mod.estimate_measurement_time(self.worker, patches)
        self.testchart_meas_time.setText(estimate.label())
        self.testchart_meas_time.setStyleSheet(
            "color: #FF3300;"
            if estimate.hours is not None and estimate.hours > 7
            else "color: #F07F00;" if estimate.is_long() else ""
        )

    def _profile_name_info_btn_handler(self) -> None:
        """Show the profile-name placeholder legend."""
        QMessageBox.information(
            self,
            lang.getstr("profile.name"),
            profile_name_mod.profile_name_placeholders(),
        )

    def _profile_save_path_btn_handler(self) -> None:
        """Choose the directory profiles/calibrations are saved under."""
        default_path = os.path.join(*get_verified_path("profile.save_path"))
        profile_name = getcfg("profile.name.expanded")
        path = QFileDialog.getExistingDirectory(
            self,
            lang.getstr("dialog.set_profile_save_path", profile_name),
            default_path,
        )
        if not path:
            return
        profile_save_dir = os.path.join(path, profile_name)
        if not os.path.isdir(profile_save_dir):
            os.makedirs(profile_save_dir, exist_ok=True)
        if not os.access(os.path.dirname(profile_save_dir), os.W_OK):
            QMessageBox.critical(
                self,
                self.windowTitle(),
                lang.getstr("error.access_denied.write", path),
            )
            return
        with contextlib.suppress(OSError):
            os.rmdir(profile_save_dir)
        setcfg("profile.save_path", path)
        self.update_profile_name()

    def _mark_profile_settings_changed(self) -> None:
        """Mark settings as changed, prefixing the current file combo entry.

        Port of ``MainFrame.profile_settings_changed``.
        """
        if self._updating:
            return
        setcfg("settings.changed", 1)
        if self.calibration_file_ctrl.currentText().startswith("*"):
            return
        index = self.calibration_file_ctrl.currentIndex()
        if index > 0:
            self.calibration_file_ctrl.blockSignals(True)
            self.calibration_file_ctrl.setItemText(
                index, "* " + self.calibration_file_ctrl.itemText(index)
            )
            self.calibration_file_ctrl.blockSignals(False)

    def update_profile_name(self) -> None:
        """Recompute the expanded profile-name preview from current settings.

        Faithful port of ``MainFrame.update_profile_name`` /
        ``create_profile_name``, built on the toolkit-neutral
        :mod:`DisplayCAL.profile_name` helpers.
        """
        if not hasattr(self, "profile_name_label"):
            return
        ctx = self._profile_name_context()
        profile_name = profile_name_mod.expand_profile_name(
            self.profile_name_textctrl.text(), ctx
        )
        if not profile_name_mod.is_valid_profile_name(profile_name):
            self.profile_name_textctrl.setText(str(getcfg("profile.name")))
            profile_name = profile_name_mod.expand_profile_name(
                self.profile_name_textctrl.text(), self._profile_name_context()
            )
            if not profile_name_mod.is_valid_profile_name(profile_name):
                self.profile_name_textctrl.setText(str(DEFAULTS.get("profile.name", "")))
                profile_name = profile_name_mod.expand_profile_name(
                    self.profile_name_textctrl.text(), self._profile_name_context()
                )
        profile_name = make_argyll_compatible_path(profile_name)
        if profile_name != self.profile_name_label.text():
            setcfg("profile.name", self.profile_name_textctrl.text())
            self.profile_name_label.setToolTip(profile_name)
            self.profile_name_label.setText(profile_name.replace("&", "&&"))
            setcfg("profile.name.expanded", profile_name)

    def _profile_name_context(self) -> profile_name_mod.ProfileNameContext:
        """Resolve the current widget/worker state into a :class:`ProfileNameContext`."""
        edid = self.worker.get_display_edid() if self.worker.displays else {}
        do_cal = bool(
            self.interactive_adjustment_cb.isChecked() or self.get_trc()
        )
        return profile_name_mod.ProfileNameContext(
            computer_name=platform.node() or None,
            display_win32_short=self.worker.get_display_name_short(False, False)
            if self.worker.displays
            else None,
            display_win32=self.worker.get_display_name(True, False)
            if self.worker.displays
            else None,
            display_short=self.worker.get_display_name_short(False, True)
            if self.worker.displays
            else None,
            display=self.worker.get_display_name(True, True)
            if self.worker.displays
            else None,
            edid=edid,
            is_virtual_display=config.is_virtual_display(),
            display_number=getcfg("display.number"),
            instrument=self.comport_ctrl.currentText() or None,
            measurement_mode=self.get_measurement_mode(),
            trc=self.get_trc(),
            trc_type=self.get_trc_type(),
            do_cal=do_cal,
            whitepoint=self.get_whitepoint(),
            whitepoint_locus=self.get_whitepoint_locus(),
            luminance=self.get_luminance(),
            black_luminance=self.get_black_luminance(),
            ambient=self.get_ambient(),
            black_output_offset=self.get_black_output_offset(),
            black_point_correction=self.get_black_point_correction(),
            black_point_correction_auto=False,
            black_point_rate=None,
            calibration_quality=self.get_calibration_quality(),
            profile_quality=str(getcfg("profile.quality")),
            profile_type=self.get_profile_type(),
            testchart_patches_amount=self.testchart_patches_amount.text() or "0",
        )

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
        self._update_action_buttons()

    # -- measurement actions (Stage 4) ------------------------------------

    def calibrate_btn_handler(self) -> None:
        """Run the pre-flight checks, then stage a calibration run.

        Qt port of ``calibrate_btn_handler``'s guard chain: macOS-bugs
        warning, the fast-matrix-shaper/profile-update choice dialog (see
        :meth:`_fast_matrix_shaper_choice`), and overwrite confirmation for
        the ``.cal`` file, plus for ``PROFILE_EXT`` when the choice (or an
        existing ``profile.update``) will also build a profile.
        """
        self.worker.dispcal_create_fast_matrix_shaper = False
        if self._check_show_macos_bugs_warning(profile=False) is False:
            return
        info = preflight_checks.resolve_fast_matrix_shaper_choice_info()
        if info.show_dialog:
            choice = self._fast_matrix_shaper_choice(info)
            if choice is None:
                return
            preflight_checks.apply_fast_matrix_shaper_choice(info, choice)
            self.worker.dispcal_create_fast_matrix_shaper = choice
        if not check_set_argyll_bin():
            return
        if not self._check_overwrite(".cal"):
            return
        if getcfg("profile.update") or self.worker.dispcal_create_fast_matrix_shaper:
            if not self._check_overwrite(PROFILE_EXT):
                return
        self.begin_measurement(MeasurementAction.CALIBRATE)

    def _fast_matrix_shaper_choice(
        self, info: preflight_checks.FastMatrixShaperChoiceInfo
    ) -> bool | None:
        """Qt port of the 3-button ``ConfirmDialog`` in ``calibrate_btn_handler``.

        Args:
            info: The :class:`~DisplayCAL.preflight_checks.FastMatrixShaperChoiceInfo`
                describing which message/button labels to show.

        Returns:
            ``True`` if the affirmative ("update profile" / "create fast
            matrix shaper") button was clicked, ``False`` for the plain
            "Calibrate" button (wx's ``alt``), or ``None`` if cancelled.
        """
        box = QMessageBox(self)
        box.setWindowTitle(APPNAME)
        box.setIcon(QMessageBox.Question)
        box.setText(lang.getstr(info.msg_key))
        ok_button = box.addButton(lang.getstr(info.ok_key), QMessageBox.AcceptRole)
        calibrate_button = box.addButton(
            lang.getstr("button.calibrate"), QMessageBox.ActionRole
        )
        box.addButton(lang.getstr("cancel"), QMessageBox.RejectRole)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is ok_button:
            return True
        if clicked is calibrate_button:
            return False
        return None

    def calibrate_and_profile_btn_handler(self) -> None:
        """Run the pre-flight checks, then stage a combined calibrate+profile run.

        Qt port of ``calibrate_and_profile_btn_handler``'s guard chain.
        """
        if self._check_show_macos_bugs_warning() is False:
            return
        if not check_set_argyll_bin():
            return
        if not self._check_overwrite(".cal"):
            return
        if not self._check_overwrite(".ti3"):
            return
        if not self._check_overwrite(PROFILE_EXT):
            return
        self.begin_measurement(MeasurementAction.CALIBRATE_AND_PROFILE)

    def profile_btn_handler(self) -> None:
        """Run the pre-flight checks, then stage a characterization run.

        Qt port of ``profile_btn_handler``'s guard chain, including
        ``current_cal_choice()`` -- its result is stashed in
        :attr:`_pending_apply_calibration` for :meth:`_run_profile_measurement`
        to pick up once the run actually starts (mirrors wx threading the same
        value through ``setup_measurement(self.just_profile, apply_calibration)``).
        Always runs the (non-silent) confirmation dialog: the ``silent=True``
        wx call path only fires from an auto-retry event this Qt port doesn't
        have yet.
        """
        if self._check_show_macos_bugs_warning(cal=False) is False:
            return
        if not check_set_argyll_bin():
            return
        if not self._check_overwrite(".ti3"):
            return
        if not self._check_overwrite(PROFILE_EXT):
            return
        apply_calibration = self._current_cal_choice()
        if apply_calibration is CAL_CHOICE_CANCELLED:
            return
        self._pending_apply_calibration = apply_calibration
        self.begin_measurement(MeasurementAction.PROFILE)

    def lut3d_create_btn_handler(self) -> None:
        """Build a 3D LUT from the 3D LUT tab's current settings.

        Qt port of the ``MainFrame``-embedded half of
        ``LUT3DMixin.lut3d_create_handler`` (``not isinstance(self,
        LUT3DFrame)``): the input profile comes straight from
        ``3dlut.input.profile`` and the output profile is the current
        calibration/profile selection (:func:`config.get_current_profile`) --
        this port has no abstract-profile picker or standalone input/output
        combos like the standalone 3D LUT maker (:mod:`DisplayCAL.ui.tools.lut3d`)
        does. wx never shows a save dialog for this button (only the standalone
        maker does): the path comes from ``Worker.lut3d_get_filename`` and any
        existing file at that path is confirmed via the same overwrite dialog
        the other action buttons use. Runs ``worker.create_3dlut`` through the
        shared :class:`~DisplayCAL.ui.worker_runner.WorkerRunController`. On
        success, :meth:`_on_lut3d_create_finished` offers to install the
        result, mirroring wx's success path chaining into ``profile_finish``.
        """
        if not check_set_argyll_bin():
            return
        profile_in_path = getcfg("3dlut.input.profile")
        if not profile_in_path or not os.path.isfile(profile_in_path):
            QMessageBox.critical(
                self,
                APPNAME,
                lang.getstr("error.profile.file_missing", profile_in_path),
            )
            return
        try:
            profile_in = ICCProfile(profile_in_path)
        except (OSError, ICCProfileInvalidError):
            QMessageBox.critical(
                self,
                APPNAME,
                lang.getstr("profile.invalid") + "\n" + profile_in_path,
            )
            return
        profile_out = config.get_current_profile()
        if not profile_out:
            QMessageBox.critical(
                self,
                APPNAME,
                lang.getstr("profile.invalid")
                + "\n"
                + str(getcfg("calibration.file", False)),
            )
            return
        if profile_in.is_same(profile_out, force_calculation=True) and QMessageBox.question(
            self,
            APPNAME,
            lang.getstr("error.source_dest_same"),
            QMessageBox.Ok | QMessageBox.Cancel,
        ) != QMessageBox.Ok:
            return

        path = self.worker.lut3d_get_filename()
        if not waccess(path, os.W_OK):
            QMessageBox.critical(
                self, APPNAME, lang.getstr("error.access_denied.write", path)
            )
            return
        if os.path.isfile(path) and QMessageBox.warning(
            self,
            APPNAME,
            lang.getstr("dialog.confirm_overwrite", path),
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Cancel,
        ) != QMessageBox.Ok:
            return

        apply_cal = bool(
            isinstance(profile_out.tags.get("vcgt"), VideoCardGammaType)
            and getcfg("3dlut.output.profile.apply_cal")
        )
        colors_xy = {
            f"3dlut.content.colorspace.{color}.{coord}": getcfg(
                f"3dlut.content.colorspace.{color}.{coord}"
            )
            for color in ("white", "red", "green", "blue")
            for coord in "xy"
        }
        kwargs = {
            "apply_cal": apply_cal,
            "intent": getcfg("3dlut.rendering_intent"),
            "file_format": getcfg("3dlut.format"),
            "size": getcfg("3dlut.size"),
            "input_bits": getcfg("3dlut.bitdepth.input"),
            "output_bits": getcfg("3dlut.bitdepth.output"),
            "input_encoding": getcfg("3dlut.encoding.input"),
            "output_encoding": getcfg("3dlut.encoding.output"),
            "trc_gamma": lut3d_settings.resolve_create_trc_gamma(
                apply_trc=bool(getcfg("3dlut.apply_trc")),
                trc=getcfg("3dlut.trc"),
                trc_gamma=getcfg("3dlut.trc_gamma"),
            ),
            "trc_gamma_type": getcfg("3dlut.trc_gamma_type"),
            "trc_output_offset": getcfg("3dlut.trc_output_offset"),
            "apply_black_offset": getcfg("3dlut.apply_black_offset"),
            "use_b2a": getcfg("3dlut.gamap.use_b2a"),
            "white_cdm2": getcfg("3dlut.hdr_peak_luminance"),
            "minmll": getcfg("3dlut.hdr_minmll"),
            "maxmll": getcfg("3dlut.hdr_maxmll"),
            "use_alternate_master_white_clip": getcfg("3dlut.hdr_maxmll_alt_clip"),
            "hdr_sat": getcfg("3dlut.hdr_sat"),
            "hdr_hue": getcfg("3dlut.hdr_hue"),
            "ambient_cdm2": getcfg("3dlut.hdr_ambient_luminance"),
            "content_rgb_space": lut3d_settings.content_rgb_space_for_creation(
                colors_xy
            ),
            "hdr_display": getcfg("3dlut.hdr_display"),
            "XYZwp": lut3d_settings.resolve_creation_whitepoint(
                getcfg("3dlut.whitepoint.x", False),
                getcfg("3dlut.whitepoint.y", False),
            ),
        }
        controller = self._ensure_run_controller()
        controller.run(
            self.worker.create_3dlut,
            self._on_lut3d_create_finished,
            wargs=(ICCProfile(profile_in.filename), path, None, profile_out),
            wkwargs=kwargs,
            progress_msg=lang.getstr("3dlut.create"),
            pauseable=False,
        )

    def _on_lut3d_create_finished(self, result: object) -> None:
        """Report the outcome of ``create_3dlut`` and offer to install it.

        Qt port of ``LUT3DMixin.lut3d_create_consumer``: on an ``Exception``,
        shows it; on a falsy non-exception result (incomplete/cancelled), wx
        does nothing further and so does this port; on success, offers to
        install/copy the 3D LUT via :meth:`_offer_install_3dlut`. wx picks the
        offer's message from whether ``3dlut.create`` is checked at
        completion time, not from which caller triggered creation (the manual
        button or the :meth:`_on_profile_build_finished` auto-chain both funnel
        through here), so this port does the same.
        """
        self.worker.wrapup(False)
        if isinstance(result, Exception):
            QMessageBox.critical(self, APPNAME, str(result))
            return
        if not result:
            return
        message = (
            lang.getstr("calibration_profiling.complete")
            if getcfg("3dlut.create")
            else ""
        )
        self._offer_install_3dlut(message)

    def _offer_install_3dlut(self, message: str = "") -> None:
        """Offer to install/copy a just-created 3D LUT, then route to it.

        Qt port of the 3D-LUT branch of ``MainFrame.profile_finish`` (taken
        once ``self.lut3d_path`` exists on disk): the OK-button label mirrors
        wx's install/save distinction, and accepting routes to whichever
        destination ``3dlut.format`` implies (see :meth:`_install_3dlut`).
        Dropped versus wx: the share-profile button and the calibration-
        preview / show-LUT / show-profile-info checkboxes (same cuts
        :meth:`_on_profile_build_finished` already makes for the plain
        profile-install offer).

        Args:
            message: Heading for the offer, or ``""`` to fall back to
                ``lang.getstr("profiling.complete")`` (wx's fallback for this
                non-``installable`` branch).
        """
        lut3d_path = self.worker.lut3d_get_filename()
        if not os.path.isfile(lut3d_path):
            return
        file_format = getcfg("3dlut.format")
        is_prisma = config.check_3dlut_format("Prisma")
        ok_key = (
            "3dlut.install"
            if file_format in ("madVR", "ReShade") or is_prisma
            else "3dlut.save_as"
        )
        text = message or lang.getstr("profiling.complete")
        try:
            built = profile_finish.validate_built_profile(getcfg("calibration.file"))
        except (
            profile_finish.ProfileFinishInvalidError,
            profile_finish.ProfileFinishNotDisplayError,
            OSError,
        ):
            pass
        else:
            extra = profile_finish.format_completion_extra(built.profile)
            if extra:
                text = f"{text}\n\n{extra}"
        box = QMessageBox(self)
        box.setWindowTitle(APPNAME)
        box.setIcon(QMessageBox.Question)
        box.setText(text)
        install_button = box.addButton(lang.getstr(ok_key), QMessageBox.AcceptRole)
        box.addButton(lang.getstr("cancel"), QMessageBox.RejectRole)
        box.exec_()
        if box.clickedButton() is not install_button:
            return
        self._install_3dlut(lut3d_path, file_format, is_prisma)

    def _install_3dlut(self, lut3d_path: str, file_format: str, is_prisma: bool) -> None:
        """Route an accepted 3D LUT install offer to its destination.

        Qt port of ``profile_finish_action``'s ``install_3dlut_api`` branch
        (``display_cal.py:12504-12556``). madVR (via ``madtpg``) and Prisma
        (its HTTP REST API) both install through ``Worker.install_3dlut``,
        which is already toolkit-neutral; reaching that point needs the
        madVR/Prisma connection dialogs ported in
        :mod:`DisplayCAL.ui.patterngenerator_setup`
        (:class:`~DisplayCAL.ui.patterngenerator_setup.Lut3DAPIInstallController`).
        Every other format copies the file to a user-chosen location
        (:meth:`lut3d_settings.install_via_copy`, which also detects and
        patches a ReShade install).

        Args:
            lut3d_path: Path to the already-created 3D LUT file.
            file_format: ``3dlut.format`` at creation time.
            is_prisma: Whether ``3dlut.format``/size/bitdepth currently match
                Prisma's fixed requirements (:func:`config.check_3dlut_format`).
        """
        madtpg = getattr(self.worker, "madtpg", None)
        install_via_api = (
            file_format == "madVR"
            and (
                not getcfg("3dlut.trc").startswith("smpte2084")
                or hasattr(madtpg, "load_hdr_3dlut_file")
            )
        ) or is_prisma
        if install_via_api:
            controller = Lut3DAPIInstallController(
                self.worker, lut3d_path, is_prisma, self
            )
            controller.finished.connect(self._on_lut3d_api_install_finished)
            self._lut3d_api_install_controller = controller
            controller.run()
            return
        dst_path = self._prompt_3dlut_copy_destination(file_format, lut3d_path)
        if not dst_path:
            return
        try:
            written = lut3d_settings.install_via_copy(
                file_format,
                getcfg("3dlut.size"),
                getcfg("3dlut.bitdepth.output"),
                lut3d_path,
                dst_path,
            )
        except OSError as exception:
            QMessageBox.critical(self, APPNAME, str(exception))
            return
        setcfg("last_3dlut_path", written[0])

    def _on_lut3d_api_install_finished(self) -> None:
        """Release the finished :class:`Lut3DAPIInstallController`."""
        self._lut3d_api_install_controller = None

    def _prompt_3dlut_copy_destination(self, file_format: str, lut3d_path: str) -> str:
        """Prompt for the 3D LUT copy destination, per ``3dlut.format``.

        Qt port of the save-dialog half of ``LUT3DMixin.lut3d_create_handler``
        (``wx_lut_3d_frame.py:812-846``): a folder picker for ``ReShade``
        (the fixed ``ColorLookupTable.png`` filename is appended, matching
        wx), otherwise a save-file dialog with the format's usual extension.
        Overwrite confirmation reuses :meth:`_check_overwrite`.

        Args:
            file_format: ``3dlut.format`` at creation time.
            lut3d_path: The just-created 3D LUT's own path (used for the
                default filename).

        Returns:
            The chosen path, or ``""`` if the user cancelled.
        """
        default_dir, _default_file = get_verified_path("last_3dlut_path")
        if file_format == "ReShade":
            directory = QFileDialog.getExistingDirectory(
                self, lang.getstr("3dlut.install"), default_dir
            )
            if not directory:
                return ""
            return os.path.join(directory.rstrip(os.path.sep), "ColorLookupTable.png")
        ext = {"eeColor": "txt", "madVR": "3dlut", "icc": PROFILE_EXT[1:]}.get(
            file_format, file_format.lower()
        )
        default_file = os.path.splitext(os.path.basename(lut3d_path))[0] + "." + ext
        path, _filter = QFileDialog.getSaveFileName(
            self,
            lang.getstr("3dlut.save_as"),
            os.path.join(default_dir, default_file),
            f"*.{ext}",
        )
        if not path:
            return ""
        if os.path.splitext(path)[1][1:].lower() != ext.lower():
            path += f".{ext}"
        if os.path.isfile(path) and not self._check_overwrite(filename=path):
            return ""
        return path

    def _check_lut3d_bpc(self) -> None:
        """Warn when profile BPC and automatic 3D LUT creation are both on.

        Qt port of ``MainFrame.lut3d_check_bpc`` (``display_cal.py:6404-6417``):
        wx calls this unconditionally from both the black-point-compensation
        and ``3dlut.create`` checkbox handlers, and the warning itself is a
        no-op unless *both* are currently checked, so :meth:`_check_handler`
        does the same. Accepting turns BPC back off (compensated black points
        confuse 3D LUT profiling, which expects the profile's uncompensated
        response); declining leaves both settings as chosen.
        """
        if not (getcfg("3dlut.create") and getcfg("profile.black_point_compensation")):
            return
        box = QMessageBox(self)
        box.setWindowTitle(APPNAME)
        box.setIcon(QMessageBox.Warning)
        box.setText(lang.getstr("black_point_compensation.3dlut.warning"))
        turn_off_button = box.addButton(
            lang.getstr("turn_off"), QMessageBox.AcceptRole
        )
        box.addButton(lang.getstr("setting.keep_current"), QMessageBox.RejectRole)
        box.exec_()
        if box.clickedButton() is turn_off_button:
            setcfg("profile.black_point_compensation", 0)
            self._update_bpc()

    def _check_overwrite(self, ext: str = "", filename: str | None = None) -> bool:
        """Qt port of ``MainFrame.check_overwrite``.

        Args:
            ext: The file extension to use if no filename is provided.
            filename: The name of the file to check.

        Returns:
            ``True`` if the file does not exist or the user confirms overwrite.
        """
        dst_file = preflight_checks.resolve_overwrite_path(ext, filename)
        if not os.path.exists(dst_file):
            return True
        answer = QMessageBox.warning(
            self,
            APPNAME,
            lang.getstr("warning.already_exists", os.path.basename(dst_file)),
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        return answer == QMessageBox.Ok

    def _check_show_macos_bugs_warning(
        self, cal: bool = True, profile: bool = True
    ) -> bool | None:
        """Qt port of ``MainFrame.check_show_macos_bugs_warning``.

        Args:
            cal: Whether to check for calibration-related bugs.
            profile: Whether to check for profile-related bugs.

        Returns:
            ``False`` if the user cancelled, else ``None`` (proceed).
        """
        if not preflight_checks.macos_bugs_warning_applicable():
            return None
        if cal and preflight_checks.should_warn_calibration_bugs():
            answer = QMessageBox.warning(
                self,
                APPNAME,
                lang.getstr("macos.bugs.cal.warning"),
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.No,
            )
            if answer == QMessageBox.Cancel:
                return False
            if answer == QMessageBox.Yes:
                self.black_luminance_ctrl.setCurrentIndex(0)
                setcfg("calibration.black_point_correction.auto", 0)
                self.black_point_correction_ctrl.setValue(0)
        if not profile or not preflight_checks.should_warn_profile_bugs():
            return None
        answer = QMessageBox.warning(
            self,
            APPNAME,
            lang.getstr("macos.bugs.profile.warning"),
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.No,
        )
        if answer == QMessageBox.Cancel:
            return False
        if answer == QMessageBox.Yes:
            setcfg("profile.type", "S")
            setcfg("profile.black_point_compensation", 1)
            self.update_profile_controls()
        return None

    def _current_cal_choice(self, silent: bool = False) -> bool | str | None | object:
        """Qt port of ``MainFrame.current_cal_choice``.

        Args:
            silent: If ``True``, skip the confirmation dialog and use its
                default answer (matches wx's ``silent`` kwarg).

        Returns:
            ``None`` to embed the current (live) calibration, ``False`` for
            none, a ``.cal`` file path, or :data:`CAL_CHOICE_CANCELLED`.
        """
        if config.is_uncalibratable_display():
            return False
        cal = getcfg("calibration.file", False)
        if cal and os.path.splitext(cal)[1].lower() in (".icc", ".icm"):
            self.worker.options_dispcal = []
        try:
            info = preflight_checks.resolve_cal_choice_info(self.worker)
        except preflight_checks.CalChoiceProfileInvalidError:
            QMessageBox.critical(
                self, APPNAME, f"{lang.getstr('profile.invalid')}\n{cal}"
            )
            return CAL_CHOICE_CANCELLED
        if silent:
            embed_cal, reset_cal = info.show_reset_checkbox, False
        else:
            dialog = _CalChoiceDialog(info, self)
            if dialog.exec_() != QDialog.Accepted:
                return CAL_CHOICE_CANCELLED
            embed_cal, reset_cal = dialog.embed_cal(), dialog.reset_cal()
        outcome = preflight_checks.compute_cal_choice_result(info, embed_cal, reset_cal)
        if outcome.reset_video_lut:
            self._reset_video_lut()
        if outcome.options_dispcal:
            self.worker.options_dispcal = outcome.options_dispcal
        return outcome.apply_calibration

    def _reset_video_lut(self) -> bool | Exception:
        """Reset the video card gamma table to linear.

        Qt port of ``MainFrame.reset_cal``, minus the embedded curve-viewer
        preview refresh (``lut_viewer_load_lut``) -- the Qt main window
        doesn't have one yet -- and the success/failure ``InfoDialog`` (runs
        silently, matching a background operation rather than a user-facing
        "reset calibration" button).
        """
        if not check_set_argyll_bin():
            return False
        cmd, args = self.worker.prepare_dispwin(cal=False)
        if isinstance(cmd, Exception):
            return cmd
        if cmd is None:
            return False
        return self.worker.exec_cmd(
            cmd,
            args,
            capture_output=True,
            low_contrast=False,
            skip_scripts=True,
            silent=True,
        )

    def _load_cal(self, cal: str | None = None, silent: bool = True) -> bool | Exception:
        """Load a calibration onto the video card gamma table.

        Qt port of ``MainFrame.load_cal``, minus the curve-viewer preview
        refresh (``lut_viewer_load_lut``, no Qt equivalent yet) and the
        success/failure ``InfoDialog`` pair -- same silent-background pattern
        as :meth:`_reset_video_lut`. Mirrors wx's ``calibration.autoload``
        gate: when that config is off and no explicit ``cal`` is given, wx
        skips the actual video-LUT load entirely (it only exists to refresh
        the curve-viewer preview) and reports success regardless.

        Args:
            cal: Path to the ``.cal``/ICC profile to load; defaults to
                ``calibration.file``.
            silent: Passed through to ``worker.exec_cmd``.

        Returns:
            ``True`` on success (including the no-op autoload-off case),
            ``False`` if there was nothing to load, or an ``Exception`` on
            failure.
        """
        load_vcgt = bool(getcfg("calibration.autoload") or cal)
        if not cal:
            cal = getcfg("calibration.file", False)
        if not cal or not check_set_argyll_bin():
            return False
        if not load_vcgt:
            return True
        cmd, args = self.worker.prepare_dispwin(cal, None, False)
        if isinstance(cmd, Exception):
            return cmd
        if cmd is None:
            return False
        return self.worker.exec_cmd(
            cmd,
            args,
            capture_output=True,
            low_contrast=False,
            skip_scripts=True,
            silent=silent,
        )

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

        Restores the main window and emits :attr:`measurement_requested`, which
        is connected to :meth:`_on_measurement_requested` to actually run the
        worker. Emitting through the signal (rather than calling the runner
        directly) keeps the committed run observable by other layers and tests.

        Args:
            action (MeasurementAction): The workflow the user committed to.
        """
        self._restore_after_measurement()
        self.measurement_requested.emit(action)

    def _restore_after_measurement(self) -> None:
        """Re-show the main window after the measurement area closes."""
        self.show()
        self.raise_()

    # -- worker execution (Stage 5) ---------------------------------------

    def _on_measurement_requested(self, action: MeasurementAction) -> None:
        """Drive the Argyll worker for a committed measurement ``action``.

        The characterization (profile) path runs non-interactively through the
        Qt :class:`~DisplayCAL.ui.worker_runner.WorkerRunController`. The
        calibration paths run ``dispcal`` through the interactive
        :class:`~DisplayCAL.ui.worker_runner.AdjustmentController` (or the
        non-interactive progress dialog when interactive adjustment is off).

        Args:
            action (MeasurementAction): The workflow the user committed to.
        """
        if action is MeasurementAction.PROFILE:
            self._run_profile_measurement()
            return
        self._run_calibration_measurement(action)

    def _ensure_run_controller(self) -> WorkerRunController:
        """Create the progress dialog / worker driver once, on first run."""
        if self._run_controller is None:
            self._progress_dialog = ProgressDialog(self, pauseable=True)
            self._run_controller = WorkerRunController(
                self.worker, self._progress_dialog, self
            )
        return self._run_controller

    def _run_profile_measurement(self) -> None:
        """Run the characterization measurement (Qt port of ``just_profile``).

        Mirrors the non-interactive setup ``MainFrame.just_profile`` does before
        ``worker.start_measurement`` and runs ``worker.measure`` through the Qt
        controller, passing :attr:`_pending_apply_calibration` (the
        ``current_cal_choice()`` result :meth:`profile_btn_handler` stashed
        there; defaults to ``True`` for callers that skip that pre-flight step,
        e.g. direct test invocation). On success, chains into
        :meth:`_build_profile_from_measurement` (the ``colprof`` stage
        ``just_profile_finish`` chains into).
        """
        self.worker.dispread_after_dispcal = False
        self.worker.interactive = config.get_display_name() == "Untethered"
        setcfg("calibration.file.previous", None)
        apply_calibration = self._pending_apply_calibration
        self._pending_apply_calibration = True
        controller = self._ensure_run_controller()
        controller.run(
            self.worker.measure,
            self._on_measurement_finished,
            wkwargs={"apply_calibration": apply_calibration},
            progress_msg=lang.getstr("measuring.characterization"),
            pauseable=True,
        )

    def _on_measurement_finished(self, result: object) -> None:
        """Report the outcome of a characterization run on the GUI thread.

        Ports the error / incomplete branches of ``just_profile_finish``; on
        success, chains into :meth:`_build_profile_from_measurement` (the
        ``colprof`` stage).

        Args:
            result (object): ``True`` on success, ``False`` / ``None`` when the
                run did not complete, or an ``Exception`` on failure.
        """
        if isinstance(result, Exception):
            QMessageBox.critical(self, APPNAME, str(result))
            return
        if not result:
            if not getcfg("dry_run"):
                QMessageBox.information(
                    self, APPNAME, lang.getstr("profiling.incomplete")
                )
            return
        self.worker.log(f"{APPNAME}: Characterization measurements complete")
        self._build_profile_from_measurement()

    def _build_profile_from_measurement(self) -> None:
        """Run the ``colprof`` stage to build a profile from the measurement.

        Qt port of ``check_copy_ti3`` + ``start_profile_worker``: reviews the
        just-measured working TI3 for suspicious patches (see
        :meth:`_check_measurement_sanity`), copies it into the profile save
        location, refreshes ``self.lut3d_path`` for the profile about to be
        built (:meth:`_apply_lut3d_path`, matching ``start_profile_worker``'s
        own ``self.lut3d_set_path(path, set_mr_sim_profile=False)`` call),
        then runs ``worker.create_profile`` through the same
        :class:`WorkerRunController` used for the measurement itself.
        """
        ti3_path = measurement_report_pipeline.resolve_working_ti3_path(self.worker)
        if ti3_path:
            try:
                ti3 = CGATS(ti3_path)
            except (OSError, CGATSError) as exception:
                QMessageBox.critical(self, APPNAME, str(exception))
                return
            proceed, _removed_items = self._check_measurement_sanity(ti3)
            if not proceed:
                return
        result = self.worker.wrapup(copy=True, remove=False, ext_filter=[".ti3"])
        if isinstance(result, Exception):
            QMessageBox.critical(self, APPNAME, str(result))
            return
        self._apply_lut3d_path(
            profile_finish.resolve_profile_path(), set_mr_sim_profile=False
        )
        controller = self._ensure_run_controller()
        controller.run(
            self.worker.create_profile,
            self._on_profile_build_finished,
            wkwargs={"tags": True},
            progress_msg=lang.getstr("create_profile"),
            pauseable=False,
        )

    def _on_profile_build_finished(
        self, result: object, success_msg: str = ""
    ) -> None:
        """Report the outcome of the ``colprof`` run and offer to install it.

        Ports the validation branches of ``profile_finish`` via
        :mod:`DisplayCAL.profile_finish`. The elaborate install-offer dialog
        (share-profile button, calibration-preview / show-LUT / show-profile-info
        checkboxes) is dropped in favour of a plain yes/no confirm that reuses
        the already-ported :class:`InstallProfileWindow` for the actual install
        step. When ``3dlut.create`` is checked, this instead chains into
        :meth:`_chain_3dlut_after_profile` -- matching wx, which never offers
        to install the *profile* in that case, only the 3D LUT.

        Args:
            result (object): The built profile's path on success, ``False`` /
                ``None`` when the run did not complete, or an ``Exception`` on
                failure.
            success_msg (str): Heading for the completion message. Defaults to
                ``lang.getstr("profiling.complete")`` (the plain ``colprof``
                completion); :meth:`_on_calibration_finished` passes
                ``"calibration.complete"`` for the fast-matrix-shaper/
                ``profile.update`` auto-profile chain, matching wx's two
                ``profile_finish`` call sites.
        """
        if isinstance(result, Exception):
            QMessageBox.critical(self, APPNAME, str(result))
            return
        if not result:
            if not getcfg("dry_run"):
                QMessageBox.information(
                    self, APPNAME, lang.getstr("profiling.incomplete")
                )
            return
        profile_path = result
        try:
            built = profile_finish.validate_built_profile(profile_path)
        except profile_finish.ProfileFinishInvalidError as exception:
            QMessageBox.critical(self, APPNAME, str(exception))
            return
        except profile_finish.ProfileFinishNotDisplayError:
            QMessageBox.information(self, APPNAME, lang.getstr("profiling.complete"))
            return
        if profile_finish.sync_calibration_file_config(profile_path):
            self.update_calibration_file_ctrl()
        self.worker.log(f"{APPNAME}: Profile created: {profile_path}")
        self._apply_lut3d_path()
        if getcfg("3dlut.create"):
            self._chain_3dlut_after_profile()
            return
        message = success_msg or lang.getstr("profiling.complete")
        extra = profile_finish.format_completion_extra(built.profile)
        if extra:
            message = f"{message}\n\n{extra}"
        prompt = lang.getstr(
            "dialog.install_profile",
            (os.path.basename(profile_path), self.display_ctrl.currentText()),
        )
        answer = QMessageBox.question(
            self,
            APPNAME,
            f"{message}\n\n{prompt}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            self.install_profile_btn_handler()

    def _apply_lut3d_path(
        self, path: str | None = None, set_mr_sim_profile: bool = True
    ) -> None:
        """Refresh ``self.lut3d_path`` and its dependent measurement-report profiles.

        Qt port of ``MainFrame.lut3d_set_path`` via
        :func:`~DisplayCAL.lut3d_settings.resolve_lut3d_path_info`: derives
        the 3D LUT's own path plus the devicelink/simulation profiles the
        Verification tab defaults to, applying any changes via ``setcfg`` and
        refreshing that tab's controls (wx's ``self.mr_update_controls()``,
        reachable directly since ``MainFrame`` itself inherits ``ReportFrame``;
        this port's :class:`~DisplayCAL.ui.measurement_report.ReportPanel` is
        composed instead of inherited, so it's called on :attr:`_report_panel`).
        """
        info = lut3d_settings.resolve_lut3d_path_info(
            self.worker,
            path,
            set_mr_sim_profile=set_mr_sim_profile,
            current_devlink_profile=getcfg("measurement_report.devlink_profile"),
            current_simulation_profile=getcfg("measurement_report.simulation_profile"),
            tab_enabled=bool(getcfg("3dlut.tab.enable")),
            trc=getcfg("3dlut.trc"),
            whitepoint_x=getcfg("3dlut.whitepoint.x", False),
            input_profile=getcfg("3dlut.input.profile"),
        )
        self.lut3d_path = info.lut3d_path
        if info.devlink_changed:
            setcfg("measurement_report.devlink_profile", info.devlink_profile)
        if info.simulation_profile:
            setcfg("measurement_report.simulation_profile", info.simulation_profile)
        if info.mr_option_changed:
            self._report_panel.mr_update_controls()
            self._update_measurement_report_btn_enabled()

    def _chain_3dlut_after_profile(self) -> None:
        """Auto-create (or offer to install) the 3D LUT after profiling.

        Qt port of the ``install_3dlut and getcfg("3dlut.create") and not
        os.path.isfile(self.lut3d_path)`` branch at the top of
        ``MainFrame.profile_finish`` (``display_cal.py:12151-12160``),
        reached from :meth:`_on_profile_build_finished` whenever
        ``3dlut.create`` is checked, right after :meth:`_apply_lut3d_path` has
        refreshed ``self.lut3d_path``. If the LUT file already exists (e.g. a
        prior run already built one at this exact path) this shows the
        install offer directly; otherwise it creates the LUT first via
        :meth:`lut3d_create_btn_handler`, which chains into the offer itself
        through :meth:`_on_lut3d_create_finished` once creation succeeds.
        """
        if os.path.isfile(self.lut3d_path):
            self._offer_install_3dlut(lang.getstr("calibration_profiling.complete"))
        else:
            self.lut3d_create_btn_handler()

    def _ensure_adjustment_controller(self) -> AdjustmentController:
        """Create the interactive-adjustment window / driver once, on first run."""
        if self._adjustment_controller is None:
            self._adjustment_window = DisplayAdjustmentWindow(self)
            self._adjustment_controller = AdjustmentController(
                self.worker, self._adjustment_window, self
            )
        else:
            # Re-apply mode-dependent setup for the committed config.
            self._adjustment_window.setup()
        return self._adjustment_controller

    def _run_calibration_measurement(self, action: MeasurementAction) -> None:
        """Run ``dispcal`` for a calibration ``action`` (Qt port of ``just_calibrate``).

        Ports the non-interactive setup ``MainFrame.just_calibrate`` /
        ``calibrate_and_profile`` do before ``worker.start_calibration``: when
        interactive display adjustment is enabled (and this is not a calibration
        update) the run drives the interactive
        :class:`~DisplayCAL.ui.display_adjustment_window.DisplayAdjustmentWindow`;
        otherwise it runs non-interactively over the progress dialog. On a
        successful calibration the characterization measurement is chained; for
        ``CALIBRATE_AND_PROFILE`` that in turn builds the profile (the
        ``colprof`` stage, see :meth:`_build_profile_from_measurement`).

        Args:
            action (MeasurementAction): ``CALIBRATE`` or ``CALIBRATE_AND_PROFILE``.
        """
        both = action is MeasurementAction.CALIBRATE_AND_PROFILE
        setcfg("calibration.continue_next", 1 if both else 0)
        if both:
            self.worker.dispcal_create_fast_matrix_shaper = False
            self.worker.dispread_after_dispcal = True
        interactive = bool(
            getcfg("calibration.interactive_display_adjustment")
        ) and not getcfg("calibration.update")
        remove = not both

        def consumer(result: object) -> None:
            self._on_calibration_finished(action, result)

        if interactive:
            controller = self._ensure_adjustment_controller()
            controller.run(consumer, remove=remove)
            return
        self.worker.interactive = False
        controller = self._ensure_run_controller()
        controller.run(
            self.worker.calibrate,
            consumer,
            wkwargs={"remove": remove},
            progress_msg=lang.getstr("calibration"),
            pauseable=True,
        )

    def _on_calibration_finished(
        self, action: MeasurementAction, result: object
    ) -> None:
        """Report a calibration outcome, chaining the profile run if requested.

        Ports ``just_calibrate_finish``. For a ``calibrate & profile`` run the
        characterization measurement (and, on its success, the ``colprof``
        build) is started; this is ``calibrate_and_profile_finish``'s
        unconditional chain, not ``just_calibrate_finish``'s
        ``profile.update``-gated one. For a calibrate-only run:
        :meth:`update_calibration_file_ctrl` always refreshes the combo, then
        either the fast-matrix-shaper/``profile.update`` profile (already
        built by ``dispcal`` itself, see :meth:`calibrate_btn_handler`) is
        validated and offered for install via :meth:`_on_profile_build_finished`,
        or -- the plain calibrate case -- the new calibration is loaded onto
        the video card gamma table (:meth:`_load_cal`) and a completion notice
        is shown. Not reproduced: the ``log.autoshow`` info-log-window toggle
        (no Qt equivalent yet).

        Args:
            action (MeasurementAction): The calibration workflow that finished.
            result (object): ``True`` on success, ``False`` / ``None`` when the
                run did not complete, or an ``Exception`` on failure.
        """
        self.worker.interactive = False
        if isinstance(result, Exception):
            QMessageBox.critical(self, APPNAME, str(result))
            return
        if not result:
            if not getcfg("dry_run"):
                QMessageBox.information(
                    self, APPNAME, lang.getstr("calibration.incomplete")
                )
            return
        self.worker.log(f"{APPNAME}: Calibration complete")
        if action is MeasurementAction.CALIBRATE_AND_PROFILE:
            self._run_profile_measurement()
            return
        self.update_calibration_file_ctrl()
        if getcfg("profile.update") or self.worker.dispcal_create_fast_matrix_shaper:
            self._on_profile_build_finished(
                profile_finish.resolve_profile_path(),
                success_msg=lang.getstr("calibration.complete"),
            )
        elif getcfg("trc"):
            self._load_cal(silent=True)
            QMessageBox.information(
                self, APPNAME, lang.getstr("calibration.complete")
            )

    # -- calibration/profile-file header bar --------------------------------

    def update_calibration_file_ctrl(self) -> None:
        """Repopulate ``calibration_file_ctrl`` from ``calibration.file``.

        Mirrors wx's ``update_calibration_file_ctrl``: adds a newly-loaded
        file to the recent list (persisting it to the ``recent_cals`` config
        option), or drops it and falls back to "new settings" if it has gone
        missing from disk. Simplified versus wx's incremental ``Freeze`` +
        item patching: rebuilds the whole combo from ``self.recent_cals``
        each time, which is cheap at this list's size.
        """
        cal = getcfg("calibration.file", False)
        selection = calibration_file.resolve_calibration_selection(
            cal, self.recent_cals
        )
        if selection.cal and selection.is_new_recent:
            self.recent_cals.append(selection.cal)
            unpreseted = calibration_file.get_unpreseted_recent_calibrations(
                self.recent_cals, self.presets
            )
            setcfg("recent_cals", os.pathsep.join(unpreseted))
        elif selection.missing:
            self.recent_cals.remove(cal)
        if not selection.cal:
            setcfg("calibration.file", None)
            setcfg("calibration.update", 0)

        self.calibration_file_ctrl.blockSignals(True)
        self.calibration_file_ctrl.clear()
        self.calibration_file_ctrl.addItem(lang.getstr("settings.new"))
        for recent_cal in self.recent_cals[1:]:
            self.calibration_file_ctrl.addItem(
                lang.getstr(os.path.basename(recent_cal))
            )
        if selection.cal:
            idx = calibration_file.index_fallback_ignorecase(
                self.recent_cals, selection.cal
            )
            self.calibration_file_ctrl.setCurrentIndex(max(idx, 0))
            self.calibration_file_ctrl.setToolTip(selection.cal)
        else:
            self.calibration_file_ctrl.setCurrentIndex(0)
            self.calibration_file_ctrl.setToolTip("")
        self.calibration_file_ctrl.blockSignals(False)

        has_cal = bool(selection.cal) and selection.cal not in self.presets
        self.create_session_archive_btn.setEnabled(has_cal)
        self.delete_calibration_btn.setEnabled(has_cal)
        has_profile = bool(selection.profile_path) and selection.profile_exists
        self.profile_info_btn.setEnabled(has_profile)
        self.install_profile_btn.setEnabled(has_profile)

    def calibration_file_ctrl_handler(self, index: int) -> None:
        """Load the recent calibration/profile picked in the header combo.

        Mirrors wx's handler for ``sel > 0``; selecting index 0 ("new
        settings") just clears the stored file (wx's cross-frame
        ``lut3dframe``/``reportframe`` resync on that path is a no-op here,
        those tool windows aren't ported).
        """
        if self._updating or index <= 0 or index >= len(self.recent_cals):
            return
        self._load_calibration_file(self.recent_cals[index])

    def load_cal_btn_handler(self) -> None:
        """Prompt for a calibration/profile file and load it."""
        default_dir, default_file = get_verified_path("last_cal_or_icc_path")
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            lang.getstr("calibration.load_from_cal_or_profile"),
            f"{default_dir}/{default_file}" if default_file else default_dir,
            f"{lang.getstr('filetype.cal_icc')} (*.cal *.icc *.icm)",
        )
        if not path:
            return
        setcfg("last_cal_or_icc_path", path)
        self._load_calibration_file(path)

    def _load_calibration_file(self, path: str, silent: bool = False) -> None:
        """Load calibration/profile settings from ``path``.

        Faithful port of the "modern" branch of wx's ``load_cal_handler``
        (files with ``ARGYLL_DISPCAL_ARGS`` / ``ARGYLL_COLPROF_ARGS``
        sections, i.e. anything DisplayCAL itself wrote) via
        :mod:`DisplayCAL.calibration_file`. Compressed session archives
        (``.7z``/``.zip``/``.tgz``/``.tar.gz``) are extracted first via
        :meth:`_import_session_archive`, which recurses back into this
        method with the extracted file's path. Loading an ICC profile also
        tries to auto-match its embedded EDID/instrument metadata against the
        currently enumerated displays/instruments
        (:func:`~DisplayCAL.calibration_file.match_display_and_instrument`);
        unlike wx's immediate ``get_set_display()``/``update_comports()``
        calls, the match is just applied via ``setcfg`` here since
        :meth:`update_controls` (called below regardless) already
        repopulates both selectors from config. A ``.cal`` file with no
        ``ARGYLL_DISPCAL_ARGS`` section (an Argyll release old enough to
        predate it) falls back to :meth:`_load_legacy_cal`. Right after the
        config-mapper block, :meth:`_apply_lut3d_path` refreshes
        ``self.lut3d_path`` and the measurement-report devlink/simulation
        profile options, matching wx's ``self.lut3d_set_path()`` call at the
        same point (``display_cal.py:19643``).
        """
        if not path or not os.path.exists(path):
            return
        ext = os.path.splitext(path)[-1]
        if ext.lower() in calibration_file.COMPRESSED_FILE_EXTENSIONS:
            self._import_session_archive(path)
            return

        try:
            profile, ti3_lines = calibration_file.parse_calibration_file(path)
        except calibration_file.CalibrationFileError as exception:
            QMessageBox.critical(self, self.windowTitle(), str(exception))
            return

        is_preset = path in self.presets
        is_3dlut_preset = is_preset and os.path.basename(path).startswith("video_")
        is_profile = ext.lower() in calibration_file.ICCPROFILE_FILE_EXTENSIONS
        display_match = False
        instrument_match = False
        has_instrument_id = False
        if is_profile:
            calibration_file.apply_icc_profile_load_defaults(path, is_preset)
            options_dispcal, options_colprof = get_options_from_profile(profile)
            match = calibration_file.match_display_and_instrument(
                profile, self.worker
            )
            display_match = match.display_index is not None
            instrument_match = match.instrument_match
            has_instrument_id = match.has_instrument_id
            if match.display_index is not None and match.display_changed:
                setcfg("display.number", match.display_index + 1)
            if match.reenable_3dlut_tab:
                setcfg("3dlut.tab.enable", 1)
                setcfg("3dlut.tab.enable.backup", 1)
            if match.instrument_index is not None:
                setcfg("comport.number", match.instrument_index + 1)
        else:
            try:
                options_dispcal, options_colprof = get_options_from_cal(path)
            except (OSError, CGATSError):
                QMessageBox.critical(
                    self,
                    self.windowTitle(),
                    f"{lang.getstr('calibration.file.invalid')}\n{path}",
                )
                return

        if not options_dispcal and not options_colprof:
            if is_profile:
                if not silent:
                    QMessageBox.information(
                        self,
                        self.windowTitle(),
                        f"{lang.getstr('no_settings')}\n{path}",
                    )
                return
            self._load_legacy_cal(path, ti3_lines, silent=silent)
            return

        calibration_file.apply_calibration_options(options_dispcal, options_colprof)
        setcfg("calibration.file", path)
        if b"CTI3" in ti3_lines:
            setcfg("testchart.file", path)
        calibration_file.apply_profile_b2a_flags_from_ti3(
            ti3_lines, is_preset, is_3dlut_preset
        )
        simset = calibration_file.apply_lut3d_config_mapper(
            ti3_lines,
            path,
            is_preset,
            is_3dlut_preset,
            display_match,
            instrument_match,
            has_instrument_id,
        )
        self._apply_lut3d_path()
        calibration_file.apply_lut3d_display_overrides(simset)
        writecfg()
        self.update_controls()
        if is_profile or options_dispcal:
            self._apply_vcgt(path, silent=True)

    def _load_legacy_cal(
        self, path: str, ti3_lines: list[bytes], silent: bool = False
    ) -> None:
        """Load a pre-``ARGYLL_DISPCAL_ARGS`` ``.cal`` file (old Argyll releases).

        Faithful port of the tail of wx's ``load_cal_handler`` via
        :func:`~DisplayCAL.calibration_file.parse_legacy_cal`; see that
        function's docstring for the latent bytes/str bug it fixes along the
        way. Applying the video LUT (:meth:`_apply_vcgt`) always runs on
        success, matching wx's unconditional ``load_cal(silent=True)`` (this
        port has no ``load_vcgt=False`` caller).
        """
        calibration_file.restore_defaults(
            include=(
                "calibration",
                "profile.update",
                "measure.override_min_display_update_delay_ms",
                "measure.min_display_update_delay_ms",
                "measure.override_display_settle_time_mult",
                "measure.display_settle_time_mult",
                "trc",
                "whitepoint",
            ),
            exclude=(
                "calibration.black_point_correction_choice.show",
                "calibration.update",
                "trc.should_use_viewcond_adjust.show_msg",
            ),
        )
        legacy = calibration_file.parse_legacy_cal(ti3_lines, self.worker)
        if legacy.invalid:
            QMessageBox.critical(
                self,
                self.windowTitle(),
                f"{lang.getstr('calibration.file.invalid')}\n{path}",
            )
            return

        setcfg("last_cal_path", path)
        setcfg("calibration.file", path)
        if b"CTI3" in ti3_lines:
            setcfg("testchart.file", path)
        writecfg()
        self.update_controls()
        self._apply_vcgt(path, silent=True)
        if not silent and not legacy.settings:
            QMessageBox.information(
                self,
                self.windowTitle(),
                f"{lang.getstr('no_settings')}\n{path}",
            )

    def _apply_vcgt(self, path: str, silent: bool = True) -> None:
        """Load ``path``'s calibration curve onto the display's video LUT.

        Synchronous simplification of wx's ``load_cal``/``install_cal``
        (which only shows a progress dialog when not silent; the header
        combo/button paths always call this silently, like wx's own
        ``load_cal_handler`` does).
        """
        if config.is_virtual_display():
            return
        cmd, args = self.worker.prepare_dispwin(path, None, False)
        if isinstance(cmd, Exception):
            return
        self.worker.exec_cmd(
            cmd,
            args,
            capture_output=True,
            low_contrast=False,
            skip_scripts=True,
            silent=silent,
            title=lang.getstr("calibration.load_from_cal_or_profile"),
        )

    def _import_session_archive(self, path: str) -> None:
        """Extract a compressed session archive and load the file inside it.

        Faithful port of ``import_session_archive`` via
        :mod:`DisplayCAL.calibration_file`, running the extraction on a
        background thread behind an indeterminate progress dialog (the same
        pattern as :meth:`create_session_archive_handler`).
        """
        filename, ext = os.path.splitext(path)
        basename = os.path.basename(filename)
        if not self._check_overwrite(filename=basename):
            return
        tempdir = self.worker.create_tempdir()
        if isinstance(tempdir, Exception):
            QMessageBox.critical(self, self.windowTitle(), str(tempdir))
            return
        sevenzip = get_program_file("7z", "7-zip") if ext.lower() == ".7z" else None
        request = calibration_file.SessionArchiveImportRequest(
            path=path, basename=basename, ext=ext, tempdir=tempdir, sevenzip=sevenzip
        )
        self._archive_import_progress = QProgressDialog(
            lang.getstr("archive.import"), "", 0, 0, self
        )
        self._archive_import_progress.setWindowTitle(self.windowTitle())
        self._archive_import_progress.setCancelButton(None)
        self._archive_import_progress.show()
        self._archive_import_thread = _SessionArchiveImportThread(
            request, self.worker.exec_cmd, parent=self
        )
        self._archive_import_thread.done.connect(self._on_session_archive_import_done)
        self._archive_import_thread.start()

    def _on_session_archive_import_done(self, result: object) -> None:
        self._archive_import_thread = None
        if self._archive_import_progress is not None:
            self._archive_import_progress.close()
            self._archive_import_progress = None
        if not result or isinstance(result, Exception):
            message = str(result) if isinstance(result, Exception) else lang.getstr(
                "error"
            )
            QMessageBox.critical(self, self.windowTitle(), message)
            self.worker.wrapup(False)
            return
        self.worker.wrapup(dst_path=result)
        self._load_calibration_file(result)

    def profile_info_btn_handler(self) -> None:
        """Show profile info for the currently selected calibration/profile."""
        cal = getcfg("calibration.file", False)
        selection = calibration_file.resolve_calibration_selection(
            cal, self.recent_cals
        )
        if not (selection.profile_path and selection.profile_exists):
            return
        if self._profile_info_window is None:
            self._profile_info_window = ProfileInfoWindow()
        self._profile_info_window.load_profile(selection.profile_path)
        self._profile_info_window.show()
        self._profile_info_window.raise_()
        self._profile_info_window.activateWindow()

    def install_profile_btn_handler(self) -> None:
        """Open the profile-install window, pre-loaded with the current profile."""
        cal = getcfg("calibration.file", False)
        selection = calibration_file.resolve_calibration_selection(
            cal, self.recent_cals
        )
        if self._install_profile_window is None:
            self._install_profile_window = InstallProfileWindow()
        if selection.profile_path and selection.profile_exists:
            self._install_profile_window.load_profile(selection.profile_path)
        self._install_profile_window.show()
        self._install_profile_window.raise_()
        self._install_profile_window.activateWindow()

    def create_session_archive_handler(self) -> None:
        """Archive the current calibration/profile session to a 7z/zip/tgz file.

        Faithful port of ``create_session_archive_handler`` via
        :mod:`DisplayCAL.calibration_file`, running the archive creation on a
        background thread behind an indeterminate progress dialog (the same
        pattern as :class:`~DisplayCAL.ui.profile_install_window.InstallProfileWindow`).
        """
        cal = getcfg("calibration.file", False)
        if not cal:
            return
        path_name = os.path.splitext(cal)[0]
        sevenzip = get_program_file("7z", "7-zip")
        file_format = "7z" if sevenzip else "zip"
        default_dir, _default_file = get_verified_path("last_archive_save_path")
        archive_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            lang.getstr("archive.create"),
            os.path.join(default_dir, f"{os.path.basename(path_name)}.{file_format}"),
            self._archive_filter(sevenzip),
        )
        if not archive_path:
            return
        if sevenzip and "*.7z" not in selected_filter:
            sevenzip = None
        setcfg("last_archive_save_path", archive_path)

        filenames, dirfilenames, dirname = calibration_file.session_archive_filenames(
            cal
        )
        has_3dlut, lut3d_ext = calibration_file.session_archive_has_3dlut_files(
            filenames, config.VALID_VALUES["3dlut.format"]
        )
        exclude_ext = None
        if has_3dlut:
            result = QMessageBox.question(
                self,
                self.windowTitle(),
                lang.getstr("archive.include_3dluts"),
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.No,
            )
            if result == QMessageBox.Cancel:
                return
            if result == QMessageBox.No:
                exclude_ext = lut3d_ext

        request = calibration_file.SessionArchiveRequest(
            dirname=dirname,
            dirfilenames=dirfilenames,
            filenames=filenames,
            archive_path=archive_path,
            exclude_ext=exclude_ext,
            sevenzip=sevenzip,
        )
        self._run_session_archive(request)

    @staticmethod
    def _archive_filter(sevenzip: str | None) -> str:
        """Build the ``QFileDialog`` save-filter string for the archive format."""
        parts = []
        if sevenzip:
            parts.append(f"{lang.getstr('filetype.7z')} (*.7z)")
        parts.append(f"{lang.getstr('filetype.zip')} (*.zip)")
        parts.append(f"{lang.getstr('filetype.tgz')} (*.tgz)")
        return ";;".join(parts)

    def _run_session_archive(
        self, request: calibration_file.SessionArchiveRequest
    ) -> None:
        self._archive_progress = QProgressDialog(
            lang.getstr("archive.create"), "", 0, 0, self
        )
        self._archive_progress.setWindowTitle(self.windowTitle())
        self._archive_progress.setCancelButton(None)
        self._archive_progress.show()
        self._archive_thread = _SessionArchiveThread(
            request, self.worker.exec_cmd, parent=self
        )
        self._archive_thread.done.connect(self._on_session_archive_done)
        self._archive_thread.start()

    def _on_session_archive_done(self, result: object) -> None:
        self._archive_thread = None
        if self._archive_progress is not None:
            self._archive_progress.close()
            self._archive_progress = None
        if not result or isinstance(result, Exception):
            message = str(result) if isinstance(result, Exception) else lang.getstr(
                "error"
            )
            QMessageBox.critical(self, self.windowTitle(), message)

    def delete_calibration_handler(self) -> None:
        """Delete the current calibration/profile and its related files.

        Faithful port of ``delete_calibration_handler`` via
        :mod:`DisplayCAL.calibration_file`, including wx's
        individually-toggleable per-file checkbox list
        (:class:`_DeleteConfirmationDialog`, the Qt stand-in for
        ``display_delete_confirmation``/``delete_calibration_related_handler``).
        """
        cal = getcfg("calibration.file", False)
        if not cal or not os.path.exists(cal):
            return
        try:
            dircontents = os.listdir(os.path.dirname(cal))
        except OSError as exception:
            QMessageBox.critical(self, self.windowTitle(), str(exception))
            return
        related_files = calibration_file.related_files_for(cal, dircontents)
        dialog = _DeleteConfirmationDialog(related_files, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        related_files = dialog.related_files()
        _deleted, orphaned = calibration_file.delete_related_files(cal, related_files)
        if orphaned:
            trashcan_key = {
                "darwin": "trashcan.mac",
                "win32": "trashcan.windows",
            }.get(sys.platform, "trashcan.linux")
            QMessageBox.critical(
                self,
                self.windowTitle(),
                lang.getstr("error.deletion", lang.getstr(trashcan_key))
                + "\n\n"
                + "\n".join(os.path.basename(path) for path in orphaned),
            )
        setcfg("settings.changed", 1)
        self.update_controls()

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
            if not self.restore_position():
                self._center_on_screen()


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
