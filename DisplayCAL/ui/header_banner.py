"""Shared "DisplayCAL" wordmark banner.

Used by :class:`MainWindow`'s header bar and
:class:`~DisplayCAL.ui.about_window.AboutWindow`'s banner. Extracted from
``main_window.py`` (where it was first built for the settings-
tab header bar) so the About dialog can reuse the exact same artwork/gradient
instead of re-deriving it.
"""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QPainter, QPaintEvent, QPixmap
from qtpy.QtWidgets import QWidget

from DisplayCAL import config

#: Logical size (pt) of the wx ``get_header()`` wordmark bitmap.
HEADER_BANNER_SIZE = (222, 64)


def header_banner_pixmap() -> QPixmap:
    """Return the ``theme/header.png`` wordmark, cropped to its banner.

    wx's ``get_header()`` draws the top ``222x64`` (logical) region of this
    artwork, which already bakes in the logo flare, the "DisplayCAL" wordmark
    and the same blue gradient as the surrounding banner. Loads the ``@2x``
    asset when available so it stays crisp on HiDPI displays.
    """
    path = config.get_data_path("theme/header@2x.png") or config.get_data_path(
        "theme/header.png"
    )
    if not path:
        return QPixmap()
    source = QPixmap(path)
    if source.isNull():
        return source
    w, h = HEADER_BANNER_SIZE
    ratio = source.width() / w
    cropped = source.copy(0, 0, round(w * ratio), round(h * ratio))
    cropped.setDevicePixelRatio(ratio)
    return cropped


class HeaderBanner(QWidget):
    """The header banner: gradient background, wordmark bitmap and tagline.

    wx's ``BitmapBackgroundPanelText`` draws its bitmap and label directly in
    one ``paintEvent``. A Qt equivalent built from overlapping sibling widgets
    (an image ``QLabel`` plus a text ``QLabel`` stacked via ``QStackedLayout``)
    turned out to be unreliable -- sibling stacking order in Qt is not simply
    "first added wins" across widget kinds, so painting both explicitly here
    is the direct, dependable option.
    """

    def __init__(
        self, pixmap: QPixmap, tagline: str, inset: int, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._pixmap = pixmap
        self._tagline = tagline
        self._inset = inset
        # Qt only auto-enables style-sheet backgrounds for the literal
        # QWidget class; a subclass with its own paintEvent needs this set
        # explicitly or its "background: qlineargradient(...)" stylesheet
        # never paints.
        self.setAttribute(Qt.WA_StyledBackground, True)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: D102 (Qt override)
        super().paintEvent(event)
        painter = QPainter(self)
        if not self._pixmap.isNull():
            painter.drawPixmap(0, 0, self._pixmap)
        painter.setPen(QColor("white"))
        rect = self.rect().adjusted(self._inset, 0, -12, -10)
        painter.drawText(
            rect, int(Qt.AlignLeft | Qt.AlignBottom | Qt.TextWordWrap), self._tagline
        )
        painter.end()
