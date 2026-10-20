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
    QPainter,
    QPaintEvent,
    QPen,
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


class HeaderBanner(QWidget):
    """The brand header, drawn as the top of a proof sheet.

    A slug line (mono: name, version, licence), then the symbol, the wordmark
    underlined by the four process colours and the tagline, and last the
    control strip of the proof. It has no photographic artwork and no
    gradient, so it reads the same in light and dark and never competes with
    the settings below it. ``pixmap`` (the legacy wx wordmark bitmap) is kept
    in the signature for compatibility and is no longer drawn.
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

        text_scale.bus.changed.connect(lambda _f: self.update())

    def set_base_height(self, px: int) -> None:
        """Height of the plate. It is brand chrome, so it does not grow with the
        reader's text size: the room goes to the content instead."""
        self._base_height = px
        self.setFixedHeight(px)

    @staticmethod
    def _chrome_size(mult: float) -> float:
        """The plate's type is sized from the system size, not the chosen one."""
        from DisplayCAL.ui import text_scale

        return text_scale.base_points() * mult

    @staticmethod
    def _slug_text() -> str:
        from DisplayCAL import meta

        build = f" [CG.{meta.CG_BUILD}]" if getattr(meta, "CG_BUILD", 0) else ""
        return f"DisplayCAL-CG · {meta.VERSION_STRING}{build}"

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: D102, N802
        from DisplayCAL.ui import design_a

        t = design_a.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = self.rect()
        painter.fillRect(rect, QColor(t.sheet))
        w, h = rect.width(), rect.height()
        pad = 14
        # Slug line.
        slug_font = design_a.mono_font(self._chrome_size(0.72))
        painter.setFont(slug_font)
        slug_h = painter.fontMetrics().height() + 8
        painter.setPen(QColor(t.ink2))
        painter.drawText(
            QRect(pad, 0, w - 2 * pad, slug_h), int(Qt.AlignLeft | Qt.AlignVCenter),
            self._slug_text().upper(),
        )
        painter.drawText(
            QRect(pad, 0, w - 2 * pad, slug_h), int(Qt.AlignRight | Qt.AlignVCenter),
            "GPLV3",
        )
        painter.fillRect(QRect(pad, slug_h - 1, w - 2 * pad, 1), QColor(t.rule))
        # Control strip along the bottom edge.
        strip_h = 10
        strip_top = h - strip_h - 1
        n = len(design_a.STRIP)
        for i, hexcolor in enumerate(design_a.STRIP):
            x0 = pad + round(i * (w - 2 * pad) / n)
            x1 = pad + round((i + 1) * (w - 2 * pad) / n)
            painter.fillRect(x0, strip_top, x1 - x0, strip_h, QColor(hexcolor))
        painter.setPen(QPen(QColor(t.rule), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(pad, strip_top, w - 2 * pad - 1, strip_h - 1)
        # Symbol, wordmark, tagline in the band between the two.
        band_top, band_bottom = slug_h + 4, strip_top - 4
        band_h = max(20, band_bottom - band_top)
        side = min(band_h, 48)
        if not self._icon.isNull():
            icon_rect = QRect(pad, band_top + (band_h - side) // 2, side, side)
            if t.dark:
                # the symbol is black: on the dark sheet it sits on a paper chip
                painter.fillRect(icon_rect, QColor(design_a.LIGHT.sheet))
                icon_rect = icon_rect.adjusted(3, 3, -3, -3)
            painter.drawPixmap(icon_rect, self._icon)
        text_x = pad + side + 10
        title = design_a.sans_font(self._chrome_size(1.75), 800)
        painter.setFont(title)
        fm = painter.fontMetrics()
        word = "DisplayCAL-CG"
        word_w = fm.horizontalAdvance(word)
        base = band_top + (band_h - 4 - fm.height()) // 2 + fm.ascent()
        painter.setPen(QColor(t.ink))
        painter.drawText(text_x, base, word)
        bar_y = base + fm.descent() + 1
        for i, hexcolor in enumerate((design_a.CYAN, design_a.MAGENTA, design_a.YELLOW, t.ink)):
            x0 = text_x + round(i * word_w / 4)
            x1 = text_x + round((i + 1) * word_w / 4)
            painter.fillRect(x0, bar_y, x1 - x0, 3, QColor(hexcolor))
        # Tagline on the right of the wordmark, never wider than what is left.
        tag_x = text_x + word_w + 22
        room = w - pad - tag_x
        if room > 120:
            tag = design_a.sans_font(self._chrome_size(0.95), 400)
            painter.setFont(tag)
            painter.setPen(QColor(t.ink2))
            elided = painter.fontMetrics().elidedText(
                self._tagline, Qt.ElideRight, room
            )
            painter.drawText(
                QRect(tag_x, band_top, room, band_h - 4),
                int(Qt.AlignLeft | Qt.AlignVCenter), elided,
            )
        painter.end()
