"""Fix-profile-associations dialog -- Qt port.

Qt counterpart of
:class:`DisplayCAL.profile_loader.FixProfileAssociationsDialog`: shown before
enabling "Automatically fix profile associations", it lists the
display -> profile associations :class:`~DisplayCAL.profile_loader.ProfileLoader`
would take over (a workaround for a Windows ``GetICMProfile`` bug that always
returns the first child device's profile regardless of which one is active),
so the user can double check the current associations before confirming.

Windows-only, like its wx counterpart: the underlying enumeration
(``ProfileLoader._set_display_profiles``/``_can_fix_profile_associations``)
only ever produces data on ``sys.platform == "win32"`` --
``ProfileLoader.monitors`` (which it reads) is itself win32-only. See
:mod:`DisplayCAL.ui.tools.apply_profiles` for where the tray's "Fix profile
associations" menu item wires this dialog up, and
:mod:`DisplayCAL.ui.tools.profile_associations` for the sibling checkbox that
does the same.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QCloseEvent, QColor, QIcon
from qtpy.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import localization as lang
from DisplayCAL.colord import device_id_from_edid
from DisplayCAL.icc_profile import DictType, ICCProfile, ICCProfileInvalidError
from DisplayCAL.ui.assets import get_theme_pixmap

if TYPE_CHECKING:
    from DisplayCAL.ui.tools.apply_profiles import QtProfileLoader

#: Text colour used (matching wx's ``SetItemTextColour``) for a row whose
#: profile's ``MAPPING_device_id`` meta tag doesn't match the display it is
#: currently associated with.
_MISMATCH_COLOR = QColor("#FF8000")


class FixProfileAssociationsDialog(QDialog):
    """Show the display -> profile associations that would be "fixed".

    Args:
        pl (QtProfileLoader): The profile loader instance.
        parent: Optional parent widget.
    """

    def __init__(self, pl: QtProfileLoader, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pl = pl

        self.setWindowTitle(pl.get_title())
        self.setWindowIcon(QIcon(get_theme_pixmap(32, "display")))

        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(
            [lang.getstr("display"), lang.getstr("profile")]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.setColumnWidth(0, 200)
        self.table.setMinimumSize(640, 125)

        icon_label = QLabel()
        icon_label.setPixmap(get_theme_pixmap(32, "dialog-warning"))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        message_label = QLabel(
            lang.getstr("profile_loader.fix_profile_associations_warning")
        )
        message_label.setWordWrap(True)
        message_row = QHBoxLayout()
        message_row.addWidget(icon_label, 0)
        message_row.addWidget(message_label, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            lang.getstr("profile_loader.fix_profile_associations")
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            lang.getstr("cancel")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table, 1)
        layout.addLayout(message_row)
        layout.addWidget(buttons)
        self.resize(640, 400)

        self.update()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.update)
        self._refresh_timer.start(1000)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Stop the refresh timer before closing.

        Args:
            event (QCloseEvent): The close event.
        """
        self._refresh_timer.stop()
        super().closeEvent(event)

    def update(self, event: object = None) -> None:
        """Refresh the display/profile association table.

        Args:
            event: Truthy if this refresh should raise the window to get the
                user's attention (matching the wx dialog's
                ``RequestUserAttention`` behaviour when triggered by a
                display-configuration-changed event). Unused otherwise.
        """
        self.pl._set_display_profiles(dry_run=True)
        self.table.setRowCount(0)
        for display_edid, profile, desc in self.pl.devices2profiles.values():
            row = self.table.rowCount()
            self.table.insertRow(row)
            display = display_edid[0].replace(
                "[PRIMARY]", lang.getstr("display.primary")
            )
            display_item = QTableWidgetItem(display)
            desc_item = QTableWidgetItem(desc)
            if profile and self._mapping_mismatched(profile, display_edid):
                display_item.setForeground(_MISMATCH_COLOR)
                desc_item.setForeground(_MISMATCH_COLOR)
            self.table.setItem(row, 0, display_item)
            self.table.setItem(row, 1, desc_item)
        if event and not self.isActiveWindow():
            self.raise_()
            self.activateWindow()

    @staticmethod
    def _mapping_mismatched(profile: str, display_edid: tuple) -> bool:
        """Check whether ``profile``'s device-id mapping matches ``display_edid``.

        Args:
            profile (str): The profile filename.
            display_edid (tuple): The ``(display, edid)`` pair from
                ``ProfileLoader.devices2profiles``.

        Returns:
            bool: True if the profile's ``MAPPING_device_id`` meta tag does
                not match the display it is currently associated with.
        """
        try:
            icc = ICCProfile(profile)
        except (OSError, ICCProfileInvalidError):
            return False
        if not isinstance(icc.tags.get("meta"), DictType):
            return False
        id1 = device_id_from_edid(display_edid[1], quirk=True)
        id2 = device_id_from_edid(display_edid[1], quirk=False)
        return icc.tags.meta.getvalue("MAPPING_device_id") not in (id1, id2)
