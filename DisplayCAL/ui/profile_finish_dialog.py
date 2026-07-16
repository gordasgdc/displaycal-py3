"""Post-calibration/profiling completion dialog — Qt port.

Qt equivalent of the ``ConfirmDialog`` :meth:`DisplayCAL.display_cal.MainFrame.
profile_finish` builds after a successful ``colprof``/``dispcal`` run: the
bold-labelled gamut coverage/volume grid, the calibration-preview and
show-profile-info checkboxes, and (for the plain profile-install offer, not
the 3D LUT one) the profile-load-on-login checkbox(es) and install-scope
radio buttons.

Deliberately dropped versus wx, matching the intentional cuts already
documented in :mod:`DisplayCAL.ui.profile_install_window`: the share-profile
button (dead code upstream, icc.opensuse.org has been down since #194) and
the "show LUT" checkbox (toggles a curve-viewer window with no Qt port).
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import localization as lang
from DisplayCAL import profile_install as pi
from DisplayCAL.config import getcfg, setcfg
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui.assets import get_theme_pixmap
from DisplayCAL.util_os import is_superuser, which

if sys.platform == "win32":
    from DisplayCAL import util_win

if TYPE_CHECKING:
    from DisplayCAL.worker import Worker


def _bold(label: QLabel) -> QLabel:
    """Return ``label`` with its font weight set to bold, in place."""
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    return label


class ProfileFinishDialog(QDialog):
    """Completion dialog offered after a profile (or 3D LUT) finishes building.

    Args:
        parent (QWidget | None): The main window.
        message (str): The heading message (completion text plus any
            self-check summary and install prompt), already composed by the
            caller.
        cinfo (list[str]): Gamut-coverage summary lines (one per reference
            gamut), or empty to omit that column.
        vinfo (list[str]): Gamut-volume summary lines, or empty to omit.
        ok_label (str): Accept button text (e.g. "Install profile").
        cancel_label (str): Reject button text.
        installable (bool): Whether to show the profile-load-on-login
            checkbox(es) and install-scope radio buttons (the plain
            profile-install offer); False for the 3D-LUT offer.
        preview_enabled (bool): Whether to show the calibration-preview
            checkbox (the profile has a ``vcgt`` tag and the platform
            supports loading/clearing calibration).
        show_profile_info_checked (bool): Initial state of the "show profile
            info" checkbox (mirrors whether that window is already shown).
        worker (Worker): The worker driving this run, used to resolve the
            install-scope options.
    """

    #: Emitted with the new checked state whenever the calibration-preview
    #: checkbox is toggled (only present when ``preview_enabled``).
    preview_toggled = Signal(bool)

    #: Emitted with the new checked state whenever the show-profile-info
    #: checkbox is toggled.
    show_profile_info_toggled = Signal(bool)

    def __init__(
        self,
        parent: QWidget | None,
        *,
        message: str,
        cinfo: list[str],
        vinfo: list[str],
        ok_label: str,
        cancel_label: str,
        installable: bool,
        preview_enabled: bool,
        show_profile_info_checked: bool,
        worker: Worker,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(APPNAME)
        # Window-modal (not the exec()-implied application-modal default):
        # the "Show Profile Information" checkbox opens a separate top-level
        # ProfileInfoWindow that the user must be able to interact with while
        # this dialog is still open. Application-modal would block input to
        # every other window in the app, including that one.
        self.setWindowModality(Qt.WindowModal)
        self._scope_buttons: dict[str, QRadioButton] = {}
        self.load_on_login_check: QCheckBox | None = None
        self.load_by_os_check: QCheckBox | None = None
        self.preview_check: QCheckBox | None = None

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(get_theme_pixmap(32, f"{APPNAME}-profile-info".lower()))
        header.addWidget(icon_label, 0, Qt.AlignTop)
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        header.addWidget(message_label, 1)
        layout.addLayout(header)

        if cinfo or vinfo:
            layout.addLayout(self._build_gamut_grid(cinfo, vinfo))

        if preview_enabled:
            self.preview_check = QCheckBox(lang.getstr("calibration.preview"))
            self.preview_check.setChecked(True)
            self.preview_check.toggled.connect(self.preview_toggled)
            layout.addWidget(self.preview_check)

        self.show_profile_info_check = QCheckBox(lang.getstr("profile.info.show"))
        self.show_profile_info_check.setChecked(show_profile_info_checked)
        self.show_profile_info_check.toggled.connect(self.show_profile_info_toggled)
        layout.addWidget(self.show_profile_info_check)

        if installable:
            layout.addWidget(self._build_load_on_login_controls())
            scope_box = self._build_scope_controls(worker)
            if scope_box is not None:
                layout.addWidget(scope_box)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_button = QPushButton(cancel_label)
        cancel_button.clicked.connect(self.reject)
        button_row.addWidget(cancel_button)
        ok_button = QPushButton(ok_label)
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        button_row.addWidget(ok_button)
        layout.addLayout(button_row)

    # -- gamut grid -----------------------------------------------------------

    @staticmethod
    def _build_gamut_grid(cinfo: list[str], vinfo: list[str]) -> QGridLayout:
        """Build the bold-labelled 2-column gamut coverage/volume grid.

        Args:
            cinfo (list[str]): Gamut-coverage summary lines, or empty.
            vinfo (list[str]): Gamut-volume summary lines, or empty.

        Returns:
            QGridLayout: The populated grid (only the columns with data).
        """
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        col = 0
        if cinfo:
            grid.addWidget(_bold(QLabel(lang.getstr("gamut.coverage"))), 0, col)
            grid.addWidget(QLabel("\n".join(cinfo)), 1, col)
            col += 1
        if vinfo:
            grid.addWidget(_bold(QLabel(lang.getstr("gamut.volume"))), 0, col)
            grid.addWidget(QLabel("\n".join(vinfo)), 1, col)
        return grid

    # -- load on login / install scope ----------------------------------------

    def _build_load_on_login_controls(self) -> QWidget:
        """Build the profile-load-on-login checkbox(es).

        Returns:
            QWidget: A container widget with the checkbox(es) stacked.
        """
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        os_cal = (
            sys.platform == "win32"
            and sys.getwindowsversion() >= (6, 1)
            and util_win.calibration_management_isenabled()
        )
        self.load_on_login_check = QCheckBox(
            pi.get_profile_load_on_login_label(os_cal)
        )
        self.load_on_login_check.setChecked(
            bool(getcfg("profile.load_on_login")) or os_cal
        )
        self.load_on_login_check.toggled.connect(self._load_on_login_changed)
        vbox.addWidget(self.load_on_login_check)
        if sys.platform == "win32" and sys.getwindowsversion() >= (6, 1):
            self.load_by_os_check = QCheckBox(
                lang.getstr("profile.load_on_login.handled_by_os")
            )
            self.load_by_os_check.setChecked(os_cal)
            self.load_by_os_check.setEnabled(
                is_superuser() and self.load_on_login_check.isChecked()
            )
            self.load_on_login_check.setEnabled(
                is_superuser() or not util_win.calibration_management_isenabled()
            )
            self.load_by_os_check.toggled.connect(self._load_by_os_changed)
            vbox.addWidget(self.load_by_os_check)
        return container

    def _load_on_login_changed(self, checked: bool) -> None:
        """Persist the profile-load-on-login checkbox state.

        Args:
            checked (bool): The new checkbox state.
        """
        setcfg("profile.load_on_login", int(checked))
        if self.load_by_os_check is not None:
            self.load_by_os_check.setEnabled(is_superuser() and checked)
            if not checked and self.load_by_os_check.isChecked() and is_superuser():
                self.load_by_os_check.setChecked(False)

    def _load_by_os_changed(self, checked: bool) -> None:
        """Toggle Windows OS-handled calibration management.

        Args:
            checked (bool): The new checkbox state.
        """
        if not is_superuser():
            return
        try:
            util_win.enable_calibration_management(checked)
        except Exception as exception:  # noqa: BLE001  (best-effort, matches wx)
            print(f"util_win.enable_calibration_management({checked}): {exception}")
            return
        self.load_on_login_check.setText(pi.get_profile_load_on_login_label(checked))

    def _build_scope_controls(self, worker: Worker) -> QGroupBox | None:
        """Build the install-scope radio-button group, if any scope is offered.

        Args:
            worker (Worker): The worker driving this run.

        Returns:
            QGroupBox | None: The populated group box, or ``None`` when only
            the (implicit) user scope is available -- in which case
            ``profile.install_scope`` is forced to ``"u"``.
        """
        is_superuser_or_sudo = sys.platform != "win32" and (
            is_superuser() or bool(which("sudo"))
        )
        windows_version = (
            tuple(sys.getwindowsversion()) if sys.platform == "win32" else None
        )
        scope_options = pi.resolve_install_scope_options(
            argyll_version=worker.argyll_version,
            is_superuser_or_sudo=is_superuser_or_sudo,
            windows_version=windows_version,
            network_profiles_dir_exists=(
                sys.platform == "darwin"
                and os.path.isdir("/Network/Library/ColorSync/Profiles")
            ),
        )
        if not scope_options:
            setcfg("profile.install_scope", "u")
            return None
        box = QGroupBox()
        vbox = QVBoxLayout(box)
        group = QButtonGroup(self)
        labels = {
            "u": "profile.install_user",
            "l": "profile.install_local_system",
            "n": "profile.install_network",
        }
        for code in scope_options:
            button = QRadioButton(lang.getstr(labels[code]))
            button.setChecked(getcfg("profile.install_scope") == code)
            button.toggled.connect(self._make_scope_handler(code))
            group.addButton(button)
            vbox.addWidget(button)
            self._scope_buttons[code] = button
        if not any(button.isChecked() for button in self._scope_buttons.values()):
            self._scope_buttons["u"].setChecked(True)
        return box

    def _make_scope_handler(self, code: str) -> Callable[[bool], None]:
        """Return a toggled-signal handler that persists scope ``code``."""

        def handler(checked: bool) -> None:
            if checked:
                setcfg("profile.install_scope", code)

        return handler

    # -- accessors --------------------------------------------------------

    @property
    def install_scope(self) -> str:
        """The currently selected install scope (``"u"``/``"l"``/``"n"``)."""
        return getcfg("profile.install_scope")

    @property
    def load_on_login_checked(self) -> bool:
        """Whether the profile-load-on-login checkbox is checked."""
        return bool(self.load_on_login_check and self.load_on_login_check.isChecked())
