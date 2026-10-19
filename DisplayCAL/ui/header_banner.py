"""Shared "DisplayCAL" wordmark banner.

Used by :class:`MainWindow`'s header bar and
:class:`~DisplayCAL.ui.about_window.AboutWindow`'s banner. Extracted from
``main_window.py`` (where it was first built for the settings-
tab header bar) so the About dialog can reuse the exact same artwork/gradient
instead of re-deriving it.
"""

from __future__ import annotations

from qtpy.QtCore import QRect, Qt
from qtpy.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QPixmap,
)
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


def brand_icon_pixmap(size: int = 128) -> QPixmap:
    """Return the application icon (the approved symbol) at ``size`` px."""
    path = config.get_data_path(f"theme/icons/{size}x{size}/displaycal.png")
    return QPixmap(path) if path else QPixmap()


#: Spectrum of the symbol's beam, used as a quiet hairline under the header.
BRAND_SPECTRUM = ("#ff5a4d", "#ffb347", "#ffe14d", "#59f07a", "#4dc9ff", "#5a7bff")


class HeaderBanner(QWidget):
    """The brand header: the symbol, the wordmark and the tagline.

    A neutral dark plate with the application symbol, "DisplayCAL" with the
    "-CG" edition mark in the accent colour and a hairline carrying the beam
    spectrum of the symbol. It deliberately has no photographic artwork, so it
    reads cleanly in both light and dark system themes and never competes with
    the settings below it. ``pixmap`` (the legacy wx wordmark bitmap) is kept in
    the signature for compatibility and is no longer drawn.
    """

    def __init__(
        self, pixmap: QPixmap, tagline: str, inset: int, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._tagline = tagline
        self._inset = inset
        self._icon = brand_icon_pixmap(128)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._base_height = 0
        from DisplayCAL.ui import text_scale

        text_scale.bus.changed.connect(lambda _f: self._fit_height())

    def set_base_height(self, px: int) -> None:
        """Height at the Normal text size; grows when the text does."""
        self._base_height = px
        self._fit_height()

    def _fit_height(self) -> None:
        """Wordmark (1.9x) + tagline must fit: never clip at a large text size."""
        if not self._base_height:
            return
        fm = self.fontMetrics()
        need = round(fm.height() * 1.9 * 1.3 + fm.height() * 1.6 + 40)
        self.setFixedHeight(max(self._base_height, need))

    def changeEvent(self, event) -> None:  # noqa: N802, D102
        from qtpy.QtCore import QEvent

        if event.type() == QEvent.FontChange:
            self._fit_height()
        super().changeEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: D102, N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = self.rect()
        grad = QLinearGradient(0, 0, 0, rect.height())
        grad.setColorAt(0, QColor("#1d1e22"))
        grad.setColorAt(1, QColor("#121316"))
        painter.fillRect(rect, grad)
        # Symbol, vertically centred, left-aligned to the bar content below.
        side = min(rect.height() - 8, 72)
        if not self._icon.isNull():
            icon_rect = QRect(14, (rect.height() - side) // 2, side, side)
            painter.drawPixmap(icon_rect, self._icon)
        text_x = max(self._inset, 14 + side + 12)
        title = QFont(self.font())
        title.setPointSizeF(title.pointSizeF() * 1.9)
        title.setBold(True)
        painter.setFont(title)
        fm = painter.fontMetrics()
        baseline = rect.height() // 2 - 2
        painter.setPen(QColor("#f2f3f5"))
        painter.drawText(text_x, baseline, "DisplayCAL")
        painter.setPen(QColor("#ffb347"))
        painter.drawText(text_x + fm.horizontalAdvance("DisplayCAL"), baseline, "-CG")
        tag = QFont(self.font())
        tag.setPointSizeF(tag.pointSizeF() * 0.95)
        painter.setFont(tag)
        painter.setPen(QColor(255, 255, 255, 165))
        painter.drawText(
            QRect(
                text_x,
                baseline + 6,
                rect.width() - text_x - 12,
                painter.fontMetrics().height() + 8,
            ),
            int(Qt.AlignLeft | Qt.AlignTop),
            self._tagline,
        )
        # Beam hairline.
        line = QLinearGradient(0, 0, rect.width(), 0)
        for i, hex_ in enumerate(BRAND_SPECTRUM):
            line.setColorAt(i / (len(BRAND_SPECTRUM) - 1), QColor(hex_))
        painter.setOpacity(0.9)
        painter.fillRect(QRect(0, rect.height() - 2, rect.width(), 2), line)
        painter.end()
