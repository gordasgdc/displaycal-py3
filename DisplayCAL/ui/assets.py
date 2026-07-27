"""Bridge DisplayCAL's on-disk theme assets to Qt objects.

The legacy wx code loaded icons through :mod:`DisplayCAL.config` helpers that
returned ``wx.Bitmap`` / ``wx.IconBundle`` objects. Those helpers ultimately
resolve plain PNG files under ``theme/icons/<size>x<size>/<name>.png`` via
:func:`DisplayCAL.config.get_data_path`. Here we reuse that same resolution and
build Qt objects instead, so both UI layers read identical assets during the
transition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QIcon, QImage, QPainter, QPixmap

from DisplayCAL import config

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

#: Icon sizes shipped under ``theme/icons``. Largest first so ``QIcon`` picks a
#: high-resolution source to downscale from.
THEME_ICON_SIZES = (512, 256, 128, 64, 48, 32, 24, 22, 16)

#: Map a DisplayCAL language code to the ISO 3166-1 alpha-2 country code whose
#: flag represents it in the Language menu. Mirrors wx's hardcoded ``lmap`` in
#: ``display_cal.py`` (English shows the US flag; Ukrainian, Korean and both
#: Chinese variants are mapped to their national flag rather than a literal
#: language code).
LANGUAGE_FLAG_MAP = {"en": "us", "ko": "kr", "ukr": "ua", "zh_hk": "cn", "zh_cn": "cn"}


def get_theme_pixmap(size: int, name: str) -> QPixmap:
    """Return the themed PNG ``name`` at ``size`` as a ``QPixmap``.

    Args:
        size (int): Square icon size (must match a ``theme/icons/<size>x<size>``
            dir).
        name (str): Icon base name without extension.

    Returns:
        QPixmap: The loaded pixmap, or a null ``QPixmap`` if the asset is
        missing.
    """
    path = config.get_data_path(f"theme/icons/{size}x{size}/{name}.png")
    if not path:
        return QPixmap()
    return QPixmap(path)


def pil_to_qpixmap(img: PILImage) -> QPixmap:
    """Convert a Pillow RGBA image to a QPixmap without touching ImageQt.

    Args:
        img (PILImage): A Pillow ``Image`` (any mode; converted to RGBA).

    Returns:
        QPixmap: The converted pixmap, detached from the source buffer.
    """
    img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qimage = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())


def rotate_hue(img: PILImage, fraction: float) -> PILImage:
    """Rotate an RGBA image's hue by ``fraction`` of a full turn.

    Qt/Pillow equivalent of wx ``Image.RotateHue``, whose ``angle`` argument
    is likewise a fraction of 360 degrees. Used both by the progress dialog's
    hue-cycled "processing" animation and by the apply-profiles tray icon's
    busy-animation frames.

    Args:
        img (PILImage): A Pillow RGBA image.
        fraction (float): The hue rotation, as a fraction of 360 degrees.

    Returns:
        PILImage: A new image with the rotated hue.
    """
    from PIL import Image as PILImageModule

    img = img.convert("RGBA")
    r, g, b, a = img.split()
    h, s, v = PILImageModule.merge("RGB", (r, g, b)).convert("HSV").split()
    shift = round(fraction * 255) % 256
    if shift:
        h = h.point(lambda x, shift=shift: (x + shift) % 256)
    rgb = PILImageModule.merge("HSV", (h, s, v)).convert("RGB")
    r2, g2, b2 = rgb.split()
    return PILImageModule.merge("RGBA", (r2, g2, b2, a))


def get_header_icon_pixmap() -> QPixmap:
    """Return the ``theme/headericon.png`` donation-dialog icon as a ``QPixmap``.

    Mirrors wx's ``get_bitmap("theme/headericon")`` (used by
    ``display_cal.donation_message``): loads the ``@2x`` asset when available
    so it stays crisp on HiDPI displays, otherwise the plain PNG at its
    native size (no forced resize, matching wx's behaviour at standard DPI).
    """
    path = config.get_data_path("theme/headericon@2x.png")
    if path:
        pixmap = QPixmap(path)
        pixmap.setDevicePixelRatio(2.0)
        return pixmap
    path = config.get_data_path("theme/headericon.png")
    if not path:
        return QPixmap()
    return QPixmap(path)


def _is_grayscale(pixmap: QPixmap) -> bool:
    """Return whether every opaque pixel of ``pixmap`` is a shade of gray."""
    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() < 10:
                continue
            if (
                abs(color.red() - color.green()) > 6
                or abs(color.green() - color.blue()) > 6
            ):
                return False
    return True


#: Icons that are grayscale (so they'd otherwise pass :func:`_is_grayscale`)
#: but whose color *is* their meaning rather than an incidental glyph shade,
#: e.g. the white-level/black-level "Measure" buttons' swatch icons. Auto-
#: inverting these for dark mode would flatten the black swatch to light
#: gray, making it look like the white-level button instead.
_NEVER_RECOLOR = {"palette-white", "palette-black"}


def get_themed_pixmap(size: int, name: str, dark: bool) -> QPixmap:
    """Return ``name`` recolored for the current theme, mirroring wx.

    wx auto-inverts monochrome glyph icons (``info``, ``document-open``,
    ``web``, ``stock_refresh``, ...) to a light color when the app background
    is dark, since the plain PNGs are gray glyphs designed for a light
    background and are nearly invisible on the dark scheme; multi-color icons
    (like the tab glyphs) are left untouched either way, same as wx. Icons in
    :data:`_NEVER_RECOLOR` are also left untouched despite being grayscale,
    since their color is semantic rather than a legibility-only glyph shade.

    Args:
        size (int): Square icon size (see :func:`get_theme_pixmap`).
        name (str): Icon base name without extension.
        dark (bool): Whether the active theme is dark (see
            :func:`DisplayCAL.ui.theme.is_dark`).

    Returns:
        QPixmap: The (possibly recolored) pixmap, or a null ``QPixmap`` if the
        asset is missing.
    """
    pixmap = get_theme_pixmap(size, name)
    if (
        pixmap.isNull()
        or not dark
        or name in _NEVER_RECOLOR
        or not _is_grayscale(pixmap)
    ):
        return pixmap
    tinted = QPixmap(pixmap.size())
    tinted.setDevicePixelRatio(pixmap.devicePixelRatio())
    tinted.fill(Qt.transparent)
    painter = QPainter(tinted)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor("#cccccc"))
    painter.end()
    return tinted


def get_language_flag_pixmap(lcode: str) -> QPixmap:
    """Return the small national-flag ``QPixmap`` for language ``lcode``.

    Flags live under ``theme/icons/flags/<cc>.png``, extracted once from wx's
    ``wx.lib.art.flagart`` catalog so the Qt UI doesn't need a runtime ``wx``
    import (wx is being phased out) for a purely cosmetic Language-menu icon.

    Args:
        lcode (str): DisplayCAL language code (e.g. ``"de"``, ``"zh_cn"``).

    Returns:
        QPixmap: The flag pixmap, or a null ``QPixmap`` if ``lcode`` has no
        matching asset.
    """
    country_code = LANGUAGE_FLAG_MAP.get(lcode, lcode)
    path = config.get_data_path(f"theme/icons/flags/{country_code}.png")
    if not path:
        return QPixmap()
    return QPixmap(path)


def get_theme_icon(name: str, sizes: tuple[int, ...] = THEME_ICON_SIZES) -> QIcon:
    """Return a multi-resolution ``QIcon`` for the themed icon ``name``.

    Mirrors :func:`DisplayCAL.config.get_icon_bundle` but returns a ``QIcon``.

    Args:
        name (str): Icon base name without extension.
        sizes (tuple[int, ...]): Candidate sizes to look up; missing ones are
            skipped.

    Returns:
        QIcon: A ``QIcon`` containing every size that was found (possibly empty).
    """
    icon = QIcon()
    for size in sizes:
        pixmap = get_theme_pixmap(size, name)
        if not pixmap.isNull():
            icon.addPixmap(pixmap)
    return icon
