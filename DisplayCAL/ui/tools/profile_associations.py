"""Profile associations dialog -- Qt port.

Qt counterpart of :class:`DisplayCAL.profile_loader.ProfileAssociationsDialog`:
lets the user manage the ordered list of ICC profiles Windows Color System
associates with a display (add/remove/set-default, per-user vs system-wide
scope via "use my settings"), refreshing live off a 1s timer the same way the
wx dialog polls the registry.

Windows-only, like its wx counterpart: the underlying WCS/registry APIs this
dialog drives (:func:`DisplayCAL.icc_profile._winreg_get_display_profiles`,
:func:`DisplayCAL.util_win.per_user_profiles_isenabled`/
:func:`~DisplayCAL.util_win.enable_per_user_profiles`) have no cross-platform
equivalent -- ``ProfileLoader.monitors`` (the display list this dialog reads)
is itself only ever populated on ``sys.platform == "win32"``. The Qt tray only
wires its "Profile associations" menu item up to this dialog on Windows; see
:mod:`DisplayCAL.ui.tools.apply_profiles`.

The "fix profile associations" checkbox mirrors the tray menu item of the
same name (see :mod:`DisplayCAL.ui.tools.apply_profiles`): both drive
:meth:`QtProfileLoader._toggle_fix_profile_associations`, which pops up
:class:`~DisplayCAL.ui.tools.fix_profile_associations.FixProfileAssociationsDialog`
for confirmation. It stays disabled whenever
``ProfileLoader._can_fix_profile_associations()`` is False, which in practice
means always off Windows (no child display devices are ever enumerated
there).
"""

from __future__ import annotations

import os
import sys
import traceback
from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import QRect, Qt, QTimer
from qtpy.QtGui import QCloseEvent, QIcon, QKeyEvent, QMouseEvent
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import localization as lang
from DisplayCAL.config import ICCPROFILES, getcfg
from DisplayCAL.icc_profile import (
    ICCProfile,
    ICCProfileInvalidError,
    set_display_profile,
    unset_display_profile,
)
from DisplayCAL.profile_loader import get_profile_desc
from DisplayCAL.ui import message_box
from DisplayCAL.ui.assets import get_theme_pixmap
from DisplayCAL.util_list import natsort_key_factory
from DisplayCAL.util_os import is_superuser, safe_glob

if sys.platform == "win32":
    from DisplayCAL.icc_profile import _winreg_get_display_profiles
    from DisplayCAL.util_win import (
        USE_REGISTRY,
        enable_per_user_profiles,
        get_first_display_device,
        per_user_profiles_isenabled,
    )

if TYPE_CHECKING:
    from DisplayCAL.ui.tools.apply_profiles import QtProfileLoader


class _CheckedEvent:
    """Duck-types wx's ``event.IsChecked()`` for ``ProfileLoader`` methods.

    ``ProfileLoader._toggle_fix_profile_associations`` (inherited unchanged
    from the wx code) reads its ``event`` argument's ``IsChecked()`` -- this
    lets the Qt dialog call it without a real wx event.
    """

    def __init__(self, checked: bool) -> None:
        self._checked = checked

    def IsChecked(self) -> bool:  # noqa: N802
        return self._checked


class _DisplayIdentificationOverlay(QWidget):
    """Frameless, click-to-dismiss overlay labelling a display.

    Qt port of wx's ``DisplayIdentificationFrame``. Positioned from the same
    ``moninfo["Monitor"]`` rect the win32 enumeration already provides, so no
    ``QScreen`` matching is needed.

    Args:
        display (str): The display description to show.
        rect (QRect): Where to place the overlay, in virtual-desktop pixels.
    """

    def __init__(self, display: str, rect: QRect) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setWindowOpacity(240 / 255)
        self.setGeometry(rect)

        outer = QWidget(self)
        outer.setStyleSheet("background-color: #303030;")
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(outer)

        border = max(1, round(rect.width() / 12.0 / 40))
        inner = QWidget(outer)
        inner.setStyleSheet("background-color: #0078d7;")
        outer_layout_inner = QVBoxLayout(outer)
        outer_layout_inner.setContentsMargins(border, border, border, border)
        outer_layout_inner.addWidget(inner)

        display_parts = display.split("@", 1)
        if len(display_parts) > 1:
            info = display_parts[1].split(" - ", 1)
            display_parts[1] = "@" + " ".join(info[:1])
            if info[1:]:
                display_parts.append(" ".join(info[1:]))
        label = QLabel("\n".join(display_parts), inner)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            f"color: #ffffff; font-size: {max(8, round(rect.width() / 12.0 / 16))}pt;"
        )
        inner_layout = QVBoxLayout(inner)
        inner_layout.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.close_timer = QTimer(self)
        self.close_timer.setSingleShot(True)
        self.close_timer.timeout.connect(self.close)
        self.close_timer.start(3000)
        self.show()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Close the overlay on any click.

        Args:
            event (QMouseEvent): The mouse event (unused).
        """
        self.close()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Close the overlay on Escape.

        Args:
            event (QKeyEvent): The key event.
        """
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


class ProfileAssociationsDialog(QDialog):
    """Manage the list of ICC profiles associated with a display.

    Args:
        pl (QtProfileLoader): The profile loader instance to manage
            associations for.
    """

    def __init__(self, pl: QtProfileLoader) -> None:
        super().__init__(None)
        self.pl = pl
        self.monitors: list = []
        self.profiles: list[str] = []
        self.current_user = False
        self._identification_overlays: dict = {}
        self._profile_info_window = None

        self.setWindowTitle(lang.getstr("profile_associations"))
        self.setWindowIcon(QIcon(get_theme_pixmap(32, "display")))

        self.display_combo = QComboBox()
        self.display_combo.setEnabled(False)
        self.identify_btn = QPushButton(lang.getstr("displays.identify"))
        self.identify_btn.setEnabled(False)
        self.identify_btn.clicked.connect(self.identify_displays)

        display_row = QHBoxLayout()
        display_row.addWidget(self.display_combo, 1)
        display_row.addWidget(self.identify_btn)

        settings_row = None
        self.use_my_settings_cb = None
        self.warn_icon = None
        self.warn_label = None
        if sys.platform == "win32":
            self.use_my_settings_cb = QCheckBox(
                lang.getstr("profile_associations.use_my_settings")
            )
            self.use_my_settings_cb.setEnabled(False)
            self.use_my_settings_cb.toggled.connect(self.use_my_settings)
            self.warn_icon = QLabel()
            self.warn_icon.setPixmap(get_theme_pixmap(16, "dialog-warning"))
            self.warn_label = QLabel(
                lang.getstr("profile_associations.changing_system_defaults.warning")
            )
            self.warn_icon.hide()
            self.warn_label.hide()
            settings_row = QHBoxLayout()
            settings_row.addWidget(self.use_my_settings_cb)
            settings_row.addSpacing(12)
            settings_row.addWidget(self.warn_icon)
            settings_row.addWidget(self.warn_label, 1)

        self.profiles_table = QTableWidget(0, 2)
        self.profiles_table.setHorizontalHeaderLabels(
            [lang.getstr("description"), lang.getstr("filename")]
        )
        self.profiles_table.verticalHeader().setVisible(False)
        self.profiles_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.profiles_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.profiles_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.profiles_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.profiles_table.setColumnWidth(1, 210)
        self.profiles_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.profiles_table.doubleClicked.connect(lambda _i: self.set_as_default())
        self.profiles_table.setMinimumSize(640, 220)

        self.fix_profile_associations_cb = QCheckBox(
            lang.getstr("profile_loader.fix_profile_associations")
        )
        self.fix_profile_associations_cb.setChecked(
            bool(getcfg("profile_loader.fix_profile_associations"))
        )
        self.fix_profile_associations_cb.setEnabled(False)
        self.fix_profile_associations_cb.toggled.connect(
            self._on_fix_profile_associations_toggled
        )

        self.add_btn = QPushButton(lang.getstr("add"))
        self.add_btn.clicked.connect(self.add_profile)
        self.remove_btn = QPushButton(lang.getstr("remove"))
        self.remove_btn.clicked.connect(self.remove_profile)
        self.profile_info_btn = QPushButton(lang.getstr("profile.info"))
        self.profile_info_btn.clicked.connect(self.show_profile_info)
        self.set_as_default_btn = QPushButton(lang.getstr("set_as_default"))
        self.set_as_default_btn.clicked.connect(self.set_as_default)
        self.close_btn = QPushButton(lang.getstr("close"))
        self.close_btn.setDefault(True)
        self.close_btn.clicked.connect(self.accept)
        self.disable_btns()
        self.add_btn.setEnabled(False)

        button_row = QHBoxLayout()
        button_row.addWidget(self.add_btn)
        button_row.addWidget(self.remove_btn)
        button_row.addWidget(self.profile_info_btn)
        button_row.addStretch(1)
        button_row.addWidget(self.set_as_default_btn)
        button_row.addWidget(self.close_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(display_row)
        if settings_row is not None:
            layout.addLayout(settings_row)
        layout.addWidget(self.profiles_table, 1)
        layout.addWidget(self.fix_profile_associations_cb)
        layout.addLayout(button_row)
        self.resize(700, 420)

        self.display_combo.currentIndexChanged.connect(self._on_display_changed)
        self.update()

        self.update_profiles_timer = QTimer(self)
        self.update_profiles_timer.timeout.connect(
            lambda: self.update_profiles(timer=True)
        )
        self.update_profiles_timer.start(1000)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Stop the refresh timer and close any identification overlays.

        Args:
            event (QCloseEvent): The close event.
        """
        self.update_profiles_timer.stop()
        for overlay in list(self._identification_overlays.values()):
            if overlay is not None:
                overlay.close()
        self._identification_overlays.clear()
        super().closeEvent(event)

    # -- selection / enable state -----------------------------------------

    def _on_selection_changed(self) -> None:
        has_selection = bool(self.profiles_table.selectedItems())
        row = self.profiles_table.currentRow()
        self.remove_btn.setEnabled(has_selection)
        self.profile_info_btn.setEnabled(has_selection)
        self.set_as_default_btn.setEnabled(has_selection and row > 0)

    def _on_display_changed(self, _index: int) -> None:
        self.update_profiles()

    def disable_btns(self) -> None:
        """Disable the buttons that require a profile-list selection."""
        self.remove_btn.setEnabled(False)
        self.profile_info_btn.setEnabled(False)
        self.set_as_default_btn.setEnabled(False)

    def _on_fix_profile_associations_toggled(self, checked: bool) -> None:
        """Confirm and apply a change to the "fix profile associations" setting.

        Args:
            checked (bool): The new checked state requested by the user.
        """
        result = self.pl._toggle_fix_profile_associations(_CheckedEvent(checked), self)
        self.fix_profile_associations_cb.blockSignals(True)
        self.fix_profile_associations_cb.setChecked(result)
        self.fix_profile_associations_cb.blockSignals(False)
        if result == checked:
            self.update_profiles(next_=True)

    def _update_auth_icons(self, auth_needed: bool) -> None:
        icon = (
            self.style().standardIcon(QStyle.StandardPixmap.SP_VistaShield)
            if auth_needed
            else QIcon()
        )
        for button in (self.add_btn, self.remove_btn, self.set_as_default_btn):
            button.setProperty("authNeeded", auth_needed)
            button.setIcon(icon)

    # -- refresh -------------------------------------------------------------

    def update(self) -> None:
        """Refresh the display list and profile-list enable states."""
        self.monitors = list(self.pl.monitors)
        self.display_combo.blockSignals(True)
        self.display_combo.clear()
        self.display_combo.addItems(
            [
                entry[0].replace("[PRIMARY]", lang.getstr("display.primary"))
                for entry in self.monitors
            ]
        )
        if self.monitors:
            self.display_combo.setCurrentIndex(0)
        self.display_combo.blockSignals(False)
        self.display_combo.setEnabled(bool(self.monitors))
        self.identify_btn.setEnabled(bool(self.monitors))
        self.add_btn.setEnabled(bool(self.monitors))
        can_fix = self.pl._can_fix_profile_associations()
        self.fix_profile_associations_cb.setEnabled(can_fix)
        if can_fix:
            self.fix_profile_associations_cb.blockSignals(True)
            self.fix_profile_associations_cb.setChecked(
                bool(getcfg("profile_loader.fix_profile_associations"))
            )
            self.fix_profile_associations_cb.blockSignals(False)
        self.update_profiles()

    def update_profiles(
        self,
        monitor: tuple | None = None,
        next_: bool = False,
        timer: bool = False,
    ) -> None:
        """Refresh the profile list for the selected (or given) monitor.

        Args:
            monitor (tuple | None): A ``(display, edid, moninfo, device)``
                tuple to use instead of the currently selected display.
            next_ (bool): Whether to proceed to the next step after a change.
            timer (bool): Whether this call originates from the refresh timer.
        """
        if not monitor:
            dindex = self.display_combo.currentIndex()
            if -1 < dindex < len(self.monitors):
                monitor = self.monitors[dindex]
            else:
                return
        _display, _edid, _moninfo, device = monitor
        if not device:
            return
        if self.use_my_settings_cb is not None:
            current_user = per_user_profiles_isenabled(devicekey=device.DeviceKey)
            scope_changed = current_user != self.current_user
            if scope_changed:
                self.current_user = current_user
                self.use_my_settings_cb.blockSignals(True)
                self.use_my_settings_cb.setChecked(current_user)
                self.use_my_settings_cb.blockSignals(False)
            self.use_my_settings_cb.setEnabled(True)
            superuser = is_superuser()
            warn = not current_user and superuser
            if warn != self.warn_label.isVisible():
                self.warn_icon.setVisible(warn)
                self.warn_label.setVisible(warn)
            auth_needed = not (current_user or superuser)
            self._update_auth_icons(auth_needed)
        else:
            current_user = False
            scope_changed = False
        monkey = device.DeviceKey.split("\\")[-2:]
        profiles = _winreg_get_display_profiles(monkey, current_user)
        profiles.reverse()
        profiles_changed = profiles != self.profiles
        if profiles_changed:
            self.profiles = profiles
            self.disable_btns()
            self.profiles_table.setRowCount(0)
            for i, profile in enumerate(self.profiles):
                description = get_profile_desc(profile, False)
                if i == 0:
                    # First profile is always default
                    description += " ({})".format(lang.getstr("default"))
                row = self.profiles_table.rowCount()
                self.profiles_table.insertRow(row)
                self.profiles_table.setItem(row, 0, QTableWidgetItem(description))
                self.profiles_table.setItem(row, 1, QTableWidgetItem(profile))
        if scope_changed or (profiles_changed and (next_ or timer)):
            QTimer.singleShot(0, self._next)

    def _next(self) -> None:
        with self.pl.lock:
            self.pl._next = True

    # -- actions ---------------------------------------------------------

    def identify_displays(self) -> None:
        """Briefly show an overlay labelling each display."""
        for display, overlay in list(self._identification_overlays.items()):
            if overlay is None or not overlay.isVisible():
                self._identification_overlays.pop(display, None)
        for display, _edid, moninfo, _device in self.monitors:
            overlay = self._identification_overlays.get(display)
            if overlay:
                overlay.close_timer.start(3000)
            else:
                m_left, m_top, m_right, m_bottom = moninfo["Monitor"]
                m_width = abs(m_right - m_left)
                m_height = abs(m_bottom - m_top)
                rect = QRect(
                    int(m_left + m_width / 4),
                    int(m_top + m_height / 4),
                    int(m_width / 2),
                    int(m_height / 2),
                )
                display_desc = display.replace(
                    "[PRIMARY]", lang.getstr("display.primary")
                )
                self._identification_overlays[display] = _DisplayIdentificationOverlay(
                    display_desc, rect
                )

    def show_profile_info(self) -> None:
        """Open the profile-information window for the selected profile."""
        row = self.profiles_table.currentRow()
        if row < 0:
            QApplication.beep()
            return
        profile_path = self.profiles[row]
        try:
            ICCProfile(profile_path)
        except (OSError, ICCProfileInvalidError):
            message_box.critical(
                self,
                self.pl.get_title(),
                lang.getstr("profile.invalid") + "\n" + profile_path,
            )
            return

        from DisplayCAL.ui.tools.profile_info import ProfileInfoWindow

        if self._profile_info_window is None:
            self._profile_info_window = ProfileInfoWindow()
        window = self._profile_info_window
        window.load_profile(profile_path)
        if window.isMinimized():
            window.showNormal()
        else:
            window.show()
        window.raise_()
        window.activateWindow()

    def disable_btns_and_bell_if_none_selected(self) -> int:
        """Beep if no profile row is selected.

        Returns:
            int: The selected row index, or -1 if none is selected.
        """
        row = self.profiles_table.currentRow()
        if row < 0:
            QApplication.beep()
        return row

    def add_profile(self) -> None:
        """Add a profile to the selected display."""
        if self.add_btn.property("authNeeded"):
            if self.pl.elevate():
                self.close()
            return
        profiles = []
        for pth in safe_glob(os.path.join(ICCPROFILES[0], "*.ic[cm]")) + safe_glob(
            os.path.join(ICCPROFILES[0], "*.cdmp")
        ):
            try:
                profile = ICCProfile(pth)
            except ICCProfileInvalidError as exception:
                print(f"{pth}:", exception)
                traceback.print_exc()
                continue
            except OSError as exception:
                print(exception)
                continue
            if profile.profileClass == b"mntr":
                profiles.append((profile.getDescription(), os.path.basename(pth)))
        natsort_key = natsort_key_factory()
        profiles.sort(key=lambda item: natsort_key(item[0]))

        dlg = QDialog(self)
        dlg.setWindowTitle(lang.getstr("add"))
        table = QTableWidget(len(profiles), 2, dlg)
        table.setHorizontalHeaderLabels(
            [lang.getstr("description"), lang.getstr("filename")]
        )
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(1, 210)
        for i, (desc, profile) in enumerate(profiles):
            table.setItem(i, 0, QTableWidgetItem(desc))
            table.setItem(i, 1, QTableWidgetItem(profile))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(False)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        table.itemSelectionChanged.connect(
            lambda: ok_button.setEnabled(bool(table.selectedItems()))
        )
        table.doubleClicked.connect(lambda _i: table.selectedItems() and dlg.accept())

        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(lang.getstr("profile.choose")))
        layout.addWidget(table)
        layout.addWidget(buttons)
        dlg.resize(700, 500)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            row = table.currentRow()
            if row > -1:
                self.set_profile(profiles[row][1])
            else:
                QApplication.beep()

    def remove_profile(self) -> None:
        """Remove the selected profile from the monitor."""
        if self.remove_btn.property("authNeeded"):
            if self.pl.elevate():
                self.close()
            return
        row = self.disable_btns_and_bell_if_none_selected()
        if row > -1:
            self.set_profile(self.profiles[row], unset=True)

    def set_as_default(self) -> None:
        """Set the selected profile as the default for the monitor."""
        if self.set_as_default_btn.property("authNeeded"):
            if self.pl.elevate():
                self.close()
            return
        row = self.disable_btns_and_bell_if_none_selected()
        if row > -1:
            self.set_profile(self.profiles[row])

    def set_profile(self, profile: str, unset: bool = False) -> None:
        """Set or unset the display profile for the selected monitor.

        Args:
            profile (str): The profile name to set (or unset).
            unset (bool): Whether to unset the profile instead of setting it.
        """
        fn = unset_display_profile if unset else set_display_profile
        self._update_configuration(fn, profile)

    def _update_configuration(self, fn: Callable, arg0: object) -> None:
        dindex = self.display_combo.currentIndex()
        if not (-1 < dindex < len(self.monitors)):
            QApplication.beep()
            return
        _display, _edid, moninfo, device = self.monitors[dindex]
        device0 = get_first_display_device(moninfo["Device"])
        if device0 and device:
            self._update_device(fn, arg0, device.DeviceKey)
            if (
                getcfg("profile_loader.fix_profile_associations")
                and device.DeviceKey != device0.DeviceKey
                and self.pl._can_fix_profile_associations()
            ):
                self._update_device(fn, arg0, device0.DeviceKey)
            self.update_profiles(monitor=self.monitors[dindex], next_=True)
        else:
            QApplication.beep()

    def _update_device(
        self, fn: Callable, arg0: object, devicekey: str, show_error: bool = True
    ) -> None:
        if (
            not USE_REGISTRY
            and fn is enable_per_user_profiles
            and not per_user_profiles_isenabled(devicekey=devicekey)
        ):
            # We need to re-associate per-user profiles to the display,
            # otherwise the associations will be lost after enabling
            # per-user if a system default profile was set (but only if we
            # call WcsSetUsePerUserProfiles instead of setting the underlying
            # registry value directly)
            monkey = devicekey.split("\\")[-2:]
            profiles = _winreg_get_display_profiles(monkey, True)
        else:
            profiles = []
        try:
            fn(arg0, devicekey=devicekey)
        except Exception as exception:
            print(
                f"{fn.__name__}({arg0!r}, devicekey={devicekey!r}):",
                exception,
            )
            if show_error:
                message_box.critical(self, self.pl.get_title(), str(exception))
        for profile_name in profiles:
            set_display_profile(profile_name, devicekey=devicekey)

    def use_my_settings(self, checked: bool) -> None:
        """Enable or disable per-user profiles.

        Args:
            checked (bool): Whether per-user profiles should be enabled.
        """
        self._update_configuration(enable_per_user_profiles, checked)
