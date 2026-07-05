"""Bridge DisplayCAL's on-disk theme assets to Qt objects.

The legacy wx code loaded icons through :mod:`DisplayCAL.config` helpers that
returned ``wx.Bitmap`` / ``wx.IconBundle`` objects. Those helpers ultimately
resolve plain PNG files under ``theme/icons/<size>x<size>/<name>.png`` via
:func:`DisplayCAL.config.get_data_path`. Here we reuse that same resolution and
build Qt objects instead, so both UI layers read identical assets during the
transition.
"""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QIcon, QImage, QPainter, QPixmap

from DisplayCAL import config

#: Icon sizes shipped under ``theme/icons``. Largest first so ``QIcon`` picks a
#: high-resolution source to downscale from.
THEME_ICON_SIZES = (512, 256, 128, 64, 48, 32, 24, 22, 16)


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


def _is_grayscale(pixmap: QPixmap) -> bool:
    """Return whether every opaque pixel of ``pixmap`` is a shade of gray."""
    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() < 10:
                continue
            if abs(color.red() - color.green()) > 6 or abs(
                color.green() - color.blue()
            ) > 6:
                return False
    return True


def get_themed_pixmap(size: int, name: str, dark: bool) -> QPixmap:
    """Return ``name`` recolored for the current theme, mirroring wx.

    wx auto-inverts monochrome glyph icons (``info``, ``document-open``,
    ``web``, ``stock_refresh``, ...) to a light color when the app background
    is dark, since the plain PNGs are gray glyphs designed for a light
    background and are nearly invisible on the dark scheme; multi-color icons
    (like the tab glyphs) are left untouched either way, same as wx.

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
    if pixmap.isNull() or not dark or not _is_grayscale(pixmap):
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
