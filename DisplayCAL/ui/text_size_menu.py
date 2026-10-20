"""The visible "Text size" control: a menu (Normal / Large / Very large / Reset)."""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtGui import QActionGroup
from qtpy.QtWidgets import QMenu, QToolButton, QWidget

from DisplayCAL import localization as lang
from DisplayCAL.ui import text_scale


def _tr(key: str) -> str:
    return lang.getstr(key)


def populate(menu: QMenu) -> None:
    """Fill ``menu`` with the levels and a reset action; stays in sync with the level."""
    group = QActionGroup(menu)
    group.setExclusive(True)
    actions = {}
    for key, _f in text_scale.LEVELS:
        act = menu.addAction(_tr(f"textsize.{key}"))
        act.setCheckable(True)
        act.setActionGroup(group)
        act.setData(key)
        act.triggered.connect(lambda _c=False, k=key: text_scale.apply(k, persist=True))
        actions[key] = act
    menu.addSeparator()
    reset = menu.addAction(_tr("textsize.reset"))
    reset.triggered.connect(
        lambda: text_scale.apply(text_scale.DEFAULT_LEVEL, persist=True)
    )
    menu.actions_by_level = actions  # type: ignore[attr-defined]

    def sync(_factor: float = 0.0) -> None:
        try:
            for key, act in actions.items():
                act.setChecked(key == text_scale.current_level())
            reset.setEnabled(text_scale.current_level() != text_scale.DEFAULT_LEVEL)
        except RuntimeError:  # the menu was destroyed with its window: stop listening
            text_scale.bus.changed.disconnect(sync)

    text_scale.bus.changed.connect(sync)
    sync()


def make_menu(parent: QWidget | None = None, title: str | None = None) -> QMenu:
    """A ready 'Text size' menu."""
    menu = QMenu(title or _tr("textsize.title"), parent)
    populate(menu)
    return menu


class TextSizeButton(QToolButton):
    """A small always-visible "Aa" button that opens the text-size menu."""

    def __init__(self, parent: QWidget | None = None, on_dark_bar: bool = False) -> None:
        super().__init__(parent)
        self.setText("Aa")
        self.setObjectName("text_size_button")
        self.setToolTip(_tr("textsize.tip"))
        self.setAccessibleName(_tr("textsize.title"))
        self.setPopupMode(QToolButton.InstantPopup)
        self.setCursor(Qt.PointingHandCursor)
        self.setAutoRaise(True)
        self.setMenu(make_menu(self))
        text_scale.set_scaled_font(self, 1.1, bold=True)
        if on_dark_bar:
            # The bar is dark in every appearance: spell out text, fill and outline
            # so the platform's light-mode button never turns it into pale-on-pale.
            self.setStyleSheet(
                "QToolButton { color: #ffffff; background: transparent;"
                " border: 1px solid rgba(255,255,255,0.45); border-radius: 5px;"
                " padding: 2px 8px; }"
                "QToolButton:hover, QToolButton:pressed {"
                " background: rgba(255,255,255,0.18); }"
            )
