"""Bridge DisplayCAL's on-disk theme assets to Qt objects.

The legacy wx code loaded icons through :mod:`DisplayCAL.config` helpers that
returned ``wx.Bitmap`` / ``wx.IconBundle`` objects. Those helpers ultimately
resolve plain PNG files under ``theme/icons/<size>x<size>/<name>.png`` via
:func:`DisplayCAL.config.get_data_path`. Here we reuse that same resolution and
build Qt objects instead, so both UI layers read identical assets during the
transition.
"""

from __future__ import annotations

from qtpy.QtGui import QIcon, QPixmap

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
