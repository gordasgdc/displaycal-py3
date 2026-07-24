"""Gamut-mapping ("Advanced" profile options) window — Qt port.

Qt equivalent of wx's ``GamapFrame`` (``display_cal.py``, ``xrc/gamap.xrc``):
the standalone window opened from the Profiling tab's "Advanced..." button
(``gamap_btn``). It configures CIECAM02 gamut mapping (source profile,
perceptual/saturation intents, source/destination viewing conditions, default
rendering intent) and B2A ("PCS-to-device" table) profile quality (low-quality
vs. hi-res tables, hi-res size, smoothing).

The load-bearing, toolkit-neutral item lists and enable/disable predicates
this window shares with :class:`~DisplayCAL.ui.main_window.MainWindow` (which
needs the same profile-type/B2A predicate for its black-point-compensation
checkbox and 3D LUT gamut-mapping radios) live in the Qt-free
:mod:`DisplayCAL.gamap_settings`.

Reuses :class:`DisplayCAL.ui.measurement_report._FileBrowse` for the source
profile field, the same editable-combo + browse-button stand-in for wx's
``FileBrowseButtonWithHistory`` the Qt 3D LUT / measurement-report windows use.

Two signals let :class:`MainWindow` react to changes the wx window drove
directly through ``self.Parent``:

* :attr:`GamapWindow.profile_settings_changed` — mirrors
  ``MainFrame.profile_settings_changed()`` (marks the calibration-file combo
  entry as changed).
* :attr:`GamapWindow.b2a_quality_changed` — mirrors the
  ``self.Parent.update_bpc()`` / ``self.Parent.lut3d_update_b2a_controls()``
  pair the B2A checkboxes trigger.

Not reproduced: the wx ``lut3dframe`` cross-window resync
(``hasattr(self.Parent, "lut3dframe")``) — the Qt 3D LUT tab is embedded
directly in ``MainWindow`` rather than a separate frame, so
:attr:`b2a_quality_changed` alone covers it.

**Fixed a latent wx bug found while porting:** ``GamapFrame
.gamap_out_viewcond_handler`` only ever called ``setcfg("gamap_out_viewcond",
...)`` from *inside* the nondisplay-viewcond confirmation branch, so picking
any regular (non-warning) destination viewing condition from the dropdown
never persisted to config at all. Fixed at the source (moved the ``setcfg`` /
change-notification out of the nested ``if``) so the still-shipping wx path
gets the fix too; this Qt port's :meth:`GamapWindow._out_viewcond_changed`
implements the corrected behaviour.
"""

from __future__ import annotations

import os

from qtpy.QtCore import Signal
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config
from DisplayCAL import gamap_settings
from DisplayCAL import localization as lang
from DisplayCAL.config import DEFAULTS, get_data_path, getcfg, setcfg
from DisplayCAL.icc_profile import ICCProfile, ICCProfileInvalidError
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.file_drop import FileDropTarget
from DisplayCAL.ui import message_box
from DisplayCAL.ui.measurement_report import _FileBrowse
from DisplayCAL.util_list import natsort_key_factory


def _profile_history() -> list[str]:
    """Return the source-profile drop-down history.

    Returns:
        list[str]: Absolute paths of the bundled reference ICC profiles.
    """
    paths = get_data_path("ref", r"\.(icm|icc)$") or []
    natsort_key = natsort_key_factory()
    return sorted(paths, key=lambda p: natsort_key(os.path.basename(p)))


class GamapWindow(BaseWindow):
    """Gamut-mapping / B2A profile-quality options window.

    Args:
        parent (QWidget | None): Optional parent window (``MainWindow``).
    """

    #: Emitted whenever a control persists a changed value, mirroring wx's
    #: ``MainFrame.profile_settings_changed()`` call.
    profile_settings_changed = Signal()

    #: Emitted whenever the B2A quality controls change, mirroring wx's
    #: ``self.Parent.update_bpc()`` / ``self.Parent.lut3d_update_b2a_controls()``.
    b2a_quality_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent=parent,
            name="gamapframe",
            title=lang.getstr("gamapframe.title"),
            icon_name=APPNAME.lower(),
        )
        self._updating = False

        self._build_ui()
        self._populate_choices()

        droptarget = FileDropTarget(
            {".icc": self._drop_profile, ".icm": self._drop_profile}
        )
        droptarget.install_on(self.gamap_profile_ctrl)

        self.update_controls()
        self.restore_position()

    # -- construction --------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)

        b2a_low_row = QHBoxLayout()
        self.low_quality_b2a_cb = QCheckBox(lang.getstr("profile.quality.b2a.low"))
        self.low_quality_b2a_cb.setToolTip(lang.getstr("profile.quality.b2a.low.info"))
        self.low_quality_b2a_cb.toggled.connect(self._low_quality_b2a_toggled)
        b2a_low_row.addWidget(self.low_quality_b2a_cb)
        b2a_low_row.addStretch(1)
        root.addLayout(b2a_low_row)

        b2a_hires_row = QHBoxLayout()
        self.b2a_hires_cb = QCheckBox(lang.getstr("profile.b2a.hires"))
        self.b2a_hires_cb.toggled.connect(self._b2a_hires_toggled)
        b2a_hires_row.addWidget(self.b2a_hires_cb)
        self.b2a_size_ctrl = QComboBox()
        self.b2a_size_ctrl.currentIndexChanged.connect(self._b2a_size_changed)
        b2a_hires_row.addWidget(self.b2a_size_ctrl)
        self.b2a_smooth_cb = QCheckBox(lang.getstr("profile.b2a.smooth"))
        self.b2a_smooth_cb.toggled.connect(self._b2a_smooth_toggled)
        b2a_hires_row.addWidget(self.b2a_smooth_cb)
        b2a_hires_row.addStretch(1)
        root.addLayout(b2a_hires_row)

        default_intent_row = QHBoxLayout()
        default_intent_row.addWidget(QLabel(lang.getstr("gamap.default_intent")))
        self.gamap_default_intent_ctrl = QComboBox()
        self.gamap_default_intent_ctrl.currentIndexChanged.connect(
            self._default_intent_changed
        )
        default_intent_row.addWidget(self.gamap_default_intent_ctrl, 1)
        root.addLayout(default_intent_row)

        ciecam02_label = QLabel(lang.getstr("gamut_mapping.ciecam02"))
        font = QFont(ciecam02_label.font())
        font.setBold(True)
        ciecam02_label.setFont(font)
        root.addWidget(ciecam02_label)

        gamap_grid = QGridLayout()
        gamap_grid.setColumnStretch(1, 1)
        self.gamap_perceptual_cb = QCheckBox(lang.getstr("gamap.perceptual"))
        self.gamap_perceptual_cb.toggled.connect(self._gamap_perceptual_toggled)
        gamap_grid.addWidget(self.gamap_perceptual_cb, 0, 0)
        self.gamap_perceptual_intent_ctrl = QComboBox()
        self.gamap_perceptual_intent_ctrl.currentIndexChanged.connect(
            self._perceptual_intent_changed
        )
        gamap_grid.addWidget(self.gamap_perceptual_intent_ctrl, 0, 1)
        self.gamap_saturation_cb = QCheckBox(lang.getstr("gamap.saturation"))
        self.gamap_saturation_cb.toggled.connect(self._gamap_saturation_toggled)
        gamap_grid.addWidget(self.gamap_saturation_cb, 1, 0)
        self.gamap_saturation_intent_ctrl = QComboBox()
        self.gamap_saturation_intent_ctrl.currentIndexChanged.connect(
            self._saturation_intent_changed
        )
        gamap_grid.addWidget(self.gamap_saturation_intent_ctrl, 1, 1)
        root.addLayout(gamap_grid)

        profile_row = QHBoxLayout()
        profile_row.addWidget(QLabel(lang.getstr("gamap.profile")))
        self.gamap_profile_ctrl = _FileBrowse(
            dialog_title=lang.getstr("gamap.profile"),
            wildcard=f"{lang.getstr('filetype.icc')} (*.icc *.icm)",
        )
        self.gamap_profile_ctrl.changed.connect(self._gamap_profile_ctrl_changed)
        profile_row.addWidget(self.gamap_profile_ctrl, 1)
        root.addLayout(profile_row)

        viewcond_grid = QGridLayout()
        viewcond_grid.setColumnStretch(1, 1)
        viewcond_grid.addWidget(QLabel(lang.getstr("gamap.src_viewcond")), 0, 0)
        self.gamap_src_viewcond_ctrl = QComboBox()
        self.gamap_src_viewcond_ctrl.currentIndexChanged.connect(
            self._src_viewcond_changed
        )
        viewcond_grid.addWidget(self.gamap_src_viewcond_ctrl, 0, 1)
        viewcond_grid.addWidget(QLabel(lang.getstr("gamap.out_viewcond")), 1, 0)
        self.gamap_out_viewcond_ctrl = QComboBox()
        self.gamap_out_viewcond_ctrl.currentIndexChanged.connect(
            self._out_viewcond_ctrl_changed
        )
        viewcond_grid.addWidget(self.gamap_out_viewcond_ctrl, 1, 1)
        root.addLayout(viewcond_grid)

        self.setCentralWidget(central)

    def _populate_choices(self) -> None:
        argyll_version = getcfg("argyll.version")

        intents = gamap_settings.intent_items(argyll_version)
        for combo in (
            self.gamap_perceptual_intent_ctrl,
            self.gamap_saturation_intent_ctrl,
        ):
            combo.clear()
            for code in intents:
                combo.addItem(lang.getstr(f"gamap.intents.{code}"), code)

        viewconds = gamap_settings.viewcond_items(argyll_version)
        for combo in (self.gamap_src_viewcond_ctrl, self.gamap_out_viewcond_ctrl):
            combo.clear()
            combo.addItem(lang.getstr("none"), None)
            for code in viewconds:
                combo.addItem(lang.getstr(f"gamap.viewconds.{code}"), code)

        self.gamap_default_intent_ctrl.clear()
        for code in gamap_settings.default_intent_items():
            self.gamap_default_intent_ctrl.addItem(
                lang.getstr(f"gamap.intents.{code}"), code
            )

        self.b2a_size_ctrl.clear()
        for size in gamap_settings.b2a_hires_size_items():
            label = lang.getstr("auto") if size == -1 else f"{size}x{size}x{size}"
            self.b2a_size_ctrl.addItem(label, size)

        self.gamap_profile_ctrl.set_history(_profile_history())

    # -- helpers ---------------------------------------------------------

    def _select_by_data(self, combo: QComboBox, value: object, default=None) -> None:
        """Select the item whose data equals ``value`` (or ``default``), silently.

        Args:
            combo (QComboBox): The combo to update.
            value (object): The value to look for among the item data.
            default (object): Fallback value if ``value`` isn't a valid item.
        """
        index = combo.findData(value)
        if index < 0:
            index = combo.findData(default)
        if index >= 0:
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)

    # -- B2A quality -------------------------------------------------------

    def _low_quality_b2a_toggled(self, _checked: bool) -> None:
        if self._updating:
            return
        self._profile_quality_b2a_changed("low_quality")

    def _b2a_hires_toggled(self, _checked: bool) -> None:
        if self._updating:
            return
        self._profile_quality_b2a_changed("hires")

    def _b2a_smooth_toggled(self, _checked: bool) -> None:
        if self._updating:
            return
        self._profile_quality_b2a_changed("smooth")

    def _profile_quality_b2a_changed(self, triggered: str) -> None:
        """Port of ``GamapFrame.profile_quality_b2a_ctrl_handler``.

        Args:
            triggered (str): Which control changed (``"low_quality"``,
                ``"hires"`` or ``"smooth"``), standing in for wx's
                ``event.GetId()`` comparisons.
        """
        if triggered == "low_quality" and self.low_quality_b2a_cb.isChecked():
            self.b2a_hires_cb.setEnabled(False)
        else:
            self.b2a_hires_cb.setEnabled(
                gamap_settings.gamap_enabled(getcfg("profile.type"))
            )
        hires = self.b2a_hires_cb.isChecked()
        self.low_quality_b2a_cb.setEnabled(not hires)
        if hires:
            if triggered == "smooth":
                setcfg("profile.b2a.hires.smooth", int(self.b2a_smooth_cb.isChecked()))
            else:
                self.b2a_smooth_cb.blockSignals(True)
                self.b2a_smooth_cb.setChecked(bool(getcfg("profile.b2a.hires.smooth")))
                self.b2a_smooth_cb.blockSignals(False)
        else:
            self.b2a_smooth_cb.blockSignals(True)
            self.b2a_smooth_cb.setChecked(False)
            self.b2a_smooth_cb.blockSignals(False)
        v = "l" if self.low_quality_b2a_cb.isChecked() else None
        changed = v != getcfg("profile.quality.b2a") or hires != bool(
            getcfg("profile.b2a.hires")
        )
        setcfg("profile.quality.b2a", v)
        setcfg("profile.b2a.hires", int(hires))
        self.b2a_size_ctrl.setEnabled(hires)
        self.b2a_smooth_cb.setEnabled(hires)
        self._gamap_profile_changed()
        if changed:
            self.profile_settings_changed.emit()
        self.b2a_quality_changed.emit()

    def _b2a_size_changed(self, index: int) -> None:
        if self._updating or index < 0:
            return
        v = gamap_settings.b2a_hires_size_items()[index]
        if v != getcfg("profile.b2a.hires.size"):
            self.profile_settings_changed.emit()
        setcfg("profile.b2a.hires.size", v)

    # -- CIECAM02 gamut mapping ---------------------------------------------

    def _gamap_perceptual_toggled(self, checked: bool) -> None:
        if self._updating:
            return
        self._on_gamap_perceptual_changed(checked, user_event=True)

    def _on_gamap_perceptual_changed(self, checked: bool, user_event: bool) -> None:
        if not checked:
            self.gamap_saturation_cb.blockSignals(True)
            self.gamap_saturation_cb.setChecked(False)
            self.gamap_saturation_cb.blockSignals(False)
            self._on_gamap_saturation_changed(False, user_event=False)
        if int(checked) != getcfg("gamap_perceptual"):
            self.profile_settings_changed.emit()
        setcfg("gamap_perceptual", int(checked))
        self._gamap_profile_changed(user_event)

    def _gamap_saturation_toggled(self, checked: bool) -> None:
        if self._updating:
            return
        self._on_gamap_saturation_changed(checked, user_event=True)

    def _on_gamap_saturation_changed(self, checked: bool, user_event: bool) -> None:
        perc_was_checked = self.gamap_perceptual_cb.isChecked()
        if checked:
            self.gamap_perceptual_cb.blockSignals(True)
            self.gamap_perceptual_cb.setChecked(True)
            self.gamap_perceptual_cb.blockSignals(False)
            self._on_gamap_perceptual_changed(True, user_event=False)
        if int(checked) != getcfg("gamap_saturation"):
            self.profile_settings_changed.emit()
        setcfg("gamap_saturation", int(checked))
        self._gamap_profile_changed(user_event and not perc_was_checked)

    def _perceptual_intent_changed(self, index: int) -> None:
        if self._updating or index < 0:
            return
        v = self.gamap_perceptual_intent_ctrl.itemData(index)
        if v != getcfg("gamap_perceptual_intent"):
            self.profile_settings_changed.emit()
        setcfg("gamap_perceptual_intent", v)

    def _saturation_intent_changed(self, index: int) -> None:
        if self._updating or index < 0:
            return
        v = self.gamap_saturation_intent_ctrl.itemData(index)
        if v != getcfg("gamap_saturation_intent"):
            self.profile_settings_changed.emit()
        setcfg("gamap_saturation_intent", v)

    def _default_intent_changed(self, index: int) -> None:
        if self._updating or index < 0:
            return
        v = self.gamap_default_intent_ctrl.itemData(index)
        if v != getcfg("gamap_default_intent"):
            self.profile_settings_changed.emit()
        setcfg("gamap_default_intent", v)

    def _src_viewcond_changed(self, index: int) -> None:
        if self._updating or index < 0:
            return
        v = self.gamap_src_viewcond_ctrl.itemData(index)
        if v != getcfg("gamap_src_viewcond"):
            self.profile_settings_changed.emit()
        setcfg("gamap_src_viewcond", v)

    def _out_viewcond_ctrl_changed(self, index: int) -> None:
        self._out_viewcond_changed(index, user_event=True)

    def _out_viewcond_changed(self, index: int, user_event: bool) -> None:
        """Port of ``GamapFrame.gamap_out_viewcond_handler`` (bug-fixed, see
        module docstring: the confirmation-gated ``setcfg`` now always runs
        when the value actually changes, not only inside the warning branch).
        """
        if self._updating or index < 0:
            return
        new_code = self.gamap_out_viewcond_ctrl.itemData(index)
        cur = getcfg("gamap_out_viewcond")
        if (
            new_code != cur
            and user_event
            and new_code in gamap_settings.VIEWCONDS_OUT_NONDISPLAY
        ):
            label = self.gamap_out_viewcond_ctrl.itemText(index)
            result = message_box.question(
                self,
                APPNAME,
                lang.getstr("warning.gamap.out_viewcond.nondisplay", label),
                QMessageBox.Ok | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if result != QMessageBox.Ok:
                self._select_by_data(self.gamap_out_viewcond_ctrl, cur)
                return
        if new_code != cur:
            setcfg("gamap_out_viewcond", new_code)
            self.profile_settings_changed.emit()

    def _drop_profile(self, path: str) -> None:
        self.gamap_profile_ctrl.set_path(path)
        self._gamap_profile_changed(user_event=True)

    def _gamap_profile_ctrl_changed(self) -> None:
        self._gamap_profile_changed(user_event=True)

    def _gamap_profile_changed(self, user_event: bool = False) -> None:
        """Port of ``GamapFrame.gamap_profile_handler``.

        Args:
            user_event (bool): Whether this is a real user interaction
                (enables the auto-preselect-viewing-condition side effect),
                mirroring wx's truthy-``event`` checks.
        """
        v = self.gamap_profile_ctrl.path()
        p = bool(v) and os.path.exists(v)
        c = self.gamap_perceptual_cb.isChecked() or self.gamap_saturation_cb.isChecked()
        if p and c:
            try:
                profile = ICCProfile(v)
            except (OSError, ICCProfileInvalidError):
                p = False
                message_box.critical(
                    self,
                    lang.getstr("profile.invalid"),
                    lang.getstr("profile.invalid") + "\n" + v,
                )
                self.gamap_profile_ctrl.set_path("")
                v = None
            else:
                src_viewcond = getcfg("gamap_src_viewcond")
                nondisplay = gamap_settings.VIEWCONDS_OUT_NONDISPLAY
                if user_event and (
                    (
                        src_viewcond in (None, *nondisplay)
                        and profile.profileClass in (b"mntr", b"spac")
                    )
                    or (
                        src_viewcond not in nondisplay
                        and profile.profileClass not in (b"mntr", b"spac")
                    )
                ):
                    new_src = "pp" if profile.profileClass == b"prtr" else "mt"
                    self._select_by_data(self.gamap_src_viewcond_ctrl, new_src)
                    self._src_viewcond_changed(
                        self.gamap_src_viewcond_ctrl.currentIndex()
                    )
                    if self.gamap_out_viewcond_ctrl.currentData() is None:
                        current_profile = config.get_current_profile(True)
                        if current_profile:
                            new_out = (
                                "pp"
                                if current_profile.profileClass == b"prtr"
                                else "mt"
                            )
                            self._select_by_data(self.gamap_out_viewcond_ctrl, new_out)
                            self._out_viewcond_changed(
                                self.gamap_out_viewcond_ctrl.currentIndex(),
                                user_event=False,
                            )
        enable_gamap = gamap_settings.gamap_enabled(getcfg("profile.type"))
        self.gamap_perceptual_cb.setEnabled(enable_gamap)
        self.gamap_perceptual_intent_ctrl.setEnabled(
            self.gamap_perceptual_cb.isChecked()
        )
        self.gamap_saturation_cb.setEnabled(enable_gamap)
        self.gamap_saturation_intent_ctrl.setEnabled(
            self.gamap_saturation_cb.isChecked()
        )
        self.gamap_profile_ctrl.setEnabled(c)
        self.gamap_src_viewcond_ctrl.setEnabled(p and c)
        self.gamap_out_viewcond_ctrl.setEnabled(p and c)
        if not ((p and c) or getcfg("profile.b2a.hires")):
            setcfg("gamap_default_intent", "p")
        self._select_by_data(
            self.gamap_default_intent_ctrl, getcfg("gamap_default_intent")
        )
        self.gamap_default_intent_ctrl.setEnabled(
            (p and c) or (bool(getcfg("profile.b2a.hires")) and enable_gamap)
        )
        if v != getcfg("gamap_profile"):
            self.profile_settings_changed.emit()
        setcfg("gamap_profile", v or None)

    # -- bulk refresh --------------------------------------------------

    def update_controls(self) -> None:
        """Push stored config into every control.

        Port of ``GamapFrame.update_controls``.
        """
        with self._guard():
            profile_type = getcfg("profile.type")
            enable_gamap = gamap_settings.gamap_enabled(profile_type)
            b2a_hires = enable_gamap and bool(getcfg("profile.b2a.hires"))
            self.low_quality_b2a_cb.setChecked(
                enable_gamap
                and getcfg("profile.quality.b2a") in ("l", "n")
                and not b2a_hires
            )
            self.low_quality_b2a_cb.setEnabled(enable_gamap and not b2a_hires)
            self.b2a_hires_cb.setChecked(b2a_hires)
            self.b2a_hires_cb.setEnabled(
                enable_gamap and not self.low_quality_b2a_cb.isChecked()
            )
            self._select_by_data(self.b2a_size_ctrl, getcfg("profile.b2a.hires.size"))
            self.b2a_size_ctrl.setEnabled(b2a_hires)
            self.b2a_smooth_cb.setChecked(
                b2a_hires and bool(getcfg("profile.b2a.hires.smooth"))
            )
            self.b2a_smooth_cb.setEnabled(b2a_hires)

            self.gamap_profile_ctrl.set_path(getcfg("gamap_profile"))
            self.gamap_perceptual_cb.setChecked(
                enable_gamap and bool(getcfg("gamap_perceptual"))
            )
            self._select_by_data(
                self.gamap_perceptual_intent_ctrl,
                getcfg("gamap_perceptual_intent"),
                DEFAULTS["gamap_perceptual_intent"],
            )
            self.gamap_saturation_cb.setChecked(
                enable_gamap and bool(getcfg("gamap_saturation"))
            )
            self._select_by_data(
                self.gamap_saturation_intent_ctrl,
                getcfg("gamap_saturation_intent"),
                DEFAULTS["gamap_saturation_intent"],
            )
            self._select_by_data(
                self.gamap_src_viewcond_ctrl,
                getcfg("gamap_src_viewcond"),
                DEFAULTS.get("gamap_src_viewcond"),
            )
            self._select_by_data(
                self.gamap_out_viewcond_ctrl,
                getcfg("gamap_out_viewcond"),
                DEFAULTS.get("gamap_out_viewcond"),
            )
        self._gamap_profile_changed()

    def _guard(self):
        """Return a context manager suppressing re-entrant handlers.

        Returns:
            _GuardContext: Toggles :attr:`_updating` for the ``with`` block.
        """
        return _GuardContext(self)


class _GuardContext:
    """Suppress re-entrant control-change handlers while active.

    See :mod:`DisplayCAL.ui.measurement_report`'s identical helper for why
    this is needed (Qt fires change signals from programmatic ``setValue`` /
    ``setChecked``, wx does not).

    Args:
        window (GamapWindow): The window whose update guard to toggle.
    """

    def __init__(self, window: GamapWindow) -> None:
        self._window = window

    def __enter__(self) -> None:
        self._prev = self._window._updating
        self._window._updating = True

    def __exit__(self, *exc) -> None:
        self._window._updating = self._prev


def main() -> None:
    """Show the gamut-mapping options window standalone, for manual testing."""
    from DisplayCAL.ui.application import Application

    app = Application([])
    window = GamapWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
