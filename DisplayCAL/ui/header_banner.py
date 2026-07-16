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

#: Logical origin/size (pt) of the flare-graphic continuation wx draws as
#: ``MainFrame.header_btm`` (``display_cal.py``'s ``y, w, h = 64, 80, 120``),
#: the region of ``theme/header.png`` immediately below :data:`HEADER_BANNER_SIZE`.
HEADER_CONTINUATION_ORIGIN = (0, 64)
HEADER_CONTINUATION_SIZE = (80, 120)


def _crop_header_asset(origin: tuple[int, int], size: tuple[int, int]) -> QPixmap:
    """Return a logical ``origin``/``size`` region of ``theme/header.png``.

    Loads the ``@2x`` asset when available so it stays crisp on HiDPI
    displays; the crop rectangle is scaled by the asset's actual density
    relative to :data:`HEADER_BANNER_SIZE`'s nominal width.
    """
    path = config.get_data_path("theme/header@2x.png") or config.get_data_path(
        "theme/header.png"
    )
    if not path:
        return QPixmap()
    source = QPixmap(path)
    if source.isNull():
        return source
    ratio = source.width() / HEADER_BANNER_SIZE[0]
    x, y = (round(v * ratio) for v in origin)
    w, h = (round(v * ratio) for v in size)
    cropped = source.copy(x, y, w, h)
    cropped.setDevicePixelRatio(ratio)
    return cropped


def header_banner_pixmap() -> QPixmap:
    """Return the ``theme/header.png`` wordmark, cropped to its banner.

    wx's ``get_header()`` draws the top ``222x64`` (logical) region of this
    artwork, which already bakes in the logo flare, the "DisplayCAL" wordmark
    and the same blue gradient as the surrounding banner. Loads the ``@2x``
    asset when available so it stays crisp on HiDPI displays.
    """
    return _crop_header_asset((0, 0), HEADER_BANNER_SIZE)


def header_continuation_pixmap() -> QPixmap:
    """Return the flare-graphic continuation below the banner crop.

    wx's ``MainFrame`` doesn't stop at the ``222x64`` banner: it overlays a
    second bitmap (``self.header_btm``), the next ``80x120`` (logical) strip
    of ``theme/header.png``, as the top-left background of the functional
    "current file" bar beneath the banner -- continuing the flare/circles
    artwork instead of cutting it off. Qt's port originally omitted this,
    leaving the graphic looking clipped at the bottom compared to wx.
    """
    return _crop_header_asset(HEADER_CONTINUATION_ORIGIN, HEADER_CONTINUATION_SIZE)


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
