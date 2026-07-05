"""Base top-level window for the Qt UI.

Successor to the essentials of :class:`DisplayCAL.wx_windows.BaseFrame`. The
huge wx base class also carried the scripting/IPC socket server and a pile of
layout workarounds; those are intentionally *not* reproduced here. The IPC
server is binding-agnostic and will move to its own mixin when a window that
needs it is ported (see ``DisplayCAL/ui/README.md``).

What this provides:

* themed window icon loading,
* optional window-position persistence via :mod:`DisplayCAL.config`, matching
  the legacy ``position.<name>.x`` / ``position.<name>.y`` keys,
* a minimal File menu (with a Quit item except on macOS, where Qt moves it to
  the application menu automatically).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QMainWindow, QWidget

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.ui.assets import get_theme_icon
from DisplayCAL.ui.scripting import ScriptingHostMixin

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent


class BaseWindow(ScriptingHostMixin, QMainWindow):
    """Common base class for DisplayCAL's Qt top-level windows.

    Args:
        parent (QWidget | None): Optional parent widget.
        name (str): Object name, also used as the ``position.<name>`` config
            prefix for geometry persistence. Empty disables persistence.
        title (str): Window title.
        icon_name (str): Themed icon base name (under ``theme/icons``) for the
            window and taskbar icon.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        name: str = "",
        title: str = "",
        icon_name: str = "",
    ) -> None:
        super().__init__(parent)
        # Force explicit painting of the palette ``Window`` colour. On macOS,
        # the native style otherwise fills top-level windows with the OS's own
        # (light) window background material instead of our themed palette,
        # which is how the dark scheme ends up visibly lighter than wx's
        # hard-coded ``#333333`` (see ``DisplayCAL.ui.theme``).
        self.setAutoFillBackground(True)
        if name:
            self.setObjectName(name)
        if title:
            self.setWindowTitle(title)
        if icon_name:
            icon = get_theme_icon(icon_name)
            if not icon.isNull():
                self.setWindowIcon(icon)
        self._config_name = name

    # -- geometry persistence ----------------------------------------------

    @property
    def _pos_prefix(self) -> str:
        """Config key prefix for this window's saved position.

        Returns:
            str: The ``position.<name>`` (or bare ``position``) config key
            prefix.
        """
        return f"position.{self._config_name}" if self._config_name else "position"

    def restore_position(self) -> bool:
        """Restore the window position from config if one is stored.

        Returns:
            bool: True if a stored position was applied, False otherwise.
        """
        x = config.getcfg(f"{self._pos_prefix}.x", False)
        y = config.getcfg(f"{self._pos_prefix}.y", False)
        if x is None or y is None:
            return False
        self.move(int(x), int(y))
        return True

    def save_position(self) -> None:
        """Persist the current window position to config."""
        if not self._config_name:
            return
        pos = self.pos()
        config.setcfg(f"{self._pos_prefix}.x", pos.x())
        config.setcfg(f"{self._pos_prefix}.y", pos.y())

    # -- menu --------------------------------------------------------------

    def init_menubar(self) -> None:
        """Create a minimal File menu with a Quit action."""
        file_menu = self.menuBar().addMenu(f"&{lang.getstr('menu.file')}")
        quit_action = file_menu.addAction(lang.getstr("menuitem.quit"))
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)

    # -- lifecycle ---------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Persist position before closing.

        Args:
            event (QCloseEvent): The Qt close event.
        """
        self.stop_listening()
        self.save_position()
        super().closeEvent(event)
