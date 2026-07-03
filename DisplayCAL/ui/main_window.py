"""DisplayCAL main window — Qt port (Stage 3 shell).

The wx main window is ``display_cal.MainFrame``: ~19,700 lines and 352 methods
driving the whole application. Porting it happens in vertical, independently
shippable slices (see ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md``, Stage 3+). This
module is the **shell** those slices grow into:

* the top-level ``MainWindow(BaseWindow)`` window, its menubar and geometry
  persistence (inherited from :class:`~DisplayCAL.ui.base_window.BaseWindow`),
* a tab bar of exclusive toggle buttons switching a :class:`QStackedWidget` of
  settings panels (the wx custom ``TabButton`` / show-hide-panel mechanism),
* the **Display & Instrument** settings tab, fully wired to ``config`` and the
  binding-agnostic :class:`~DisplayCAL.worker.Worker` display/port enumeration,
* the calibrate / profile action-button bar (present but disabled; the actions
  are wired in Stage 4 against the Stage-2 :mod:`DisplayCAL.ui.measurement_flow`
  engine).

The remaining settings tabs (calibration, profiling, 3D LUT) are scaffolded as
empty panels here and populated by later slices. The window is opt-in behind
``DISPLAYCAL_UI=qt`` / ``--qt`` (wired in :mod:`DisplayCAL.main`), so it never
displaces the still-shipping wx main window.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import getcfg, setcfg
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.assets import get_theme_pixmap
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.measurement_flow import MeasurementFlow, observer_items
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


class MainWindow(BaseWindow):
    """DisplayCAL's Qt main window (shell + Display & Instrument tab)."""

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

        self._build_ui()
        self.init_menubar()
        self.setup_language()

        self.worker.enumerate_displays_and_ports(silent=True)
        self.update_controls()

    # -- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        """Assemble the header, tab bar, stacked settings panels and buttons."""
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_tabbar())

        self.stack = QStackedWidget()
        self._panels["display_instrument"] = self._build_display_instrument_tab()
        for key, _icon, label_key in _TABS[1:]:
            self._panels[key] = self._build_placeholder_tab(label_key)
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

    def _build_placeholder_tab(self, label_key: str) -> QWidget:
        """Build a scaffolded (empty) settings panel for a later slice.

        Args:
            label_key (str): Localization key naming the tab.

        Returns:
            QWidget: The placeholder panel.
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        label = QLabel(lang.getstr(label_key))
        label.setAlignment(Qt.AlignCenter)
        label.setEnabled(False)
        layout.addStretch(1)
        layout.addWidget(label)
        layout.addStretch(1)
        return panel

    def _build_button_bar(self) -> QWidget:
        """Build the calibrate / profile action-button row.

        The buttons are present but disabled in this slice; Stage 4 wires them
        to the pending measurement functions via :attr:`flow`.
        """
        bar = QWidget()
        bar.setObjectName("buttonpanel")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 8, 16, 12)
        row.setSpacing(8)
        row.addStretch(1)

        self.calibrate_btn = QPushButton(lang.getstr("button.calibrate"))
        self.calibrate_and_profile_btn = QPushButton(
            lang.getstr("button.calibrate_and_profile")
        )
        self.profile_btn = QPushButton(lang.getstr("button.profile"))
        for button in (
            self.calibrate_btn,
            self.calibrate_and_profile_btn,
            self.profile_btn,
        ):
            # Actions land in Stage 4; keep them visible but inert for now.
            button.setEnabled(False)
            button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            row.addWidget(button)
        return bar

    # -- population --------------------------------------------------------

    def update_controls(self) -> None:
        """Repopulate every control from the current worker/config state."""
        self._updating = True
        try:
            self.update_displays()
            self.update_comports()
            self.update_observers()
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

    # -- handlers ----------------------------------------------------------

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

    def _select_tab(self, key: str) -> None:
        """Show the settings panel for ``key`` and check its tab button.

        Args:
            key (str): The tab identifier (see :data:`_TABS`).
        """
        self.stack.setCurrentWidget(self._panels[key])
        button = self._tab_buttons[key]
        if not button.isChecked():
            button.setChecked(True)

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
