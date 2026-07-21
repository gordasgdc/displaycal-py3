"""Visual whitepoint editor — Qt port.

Qt equivalent of :mod:`DisplayCAL.wx_visual_whitepoint_editor` (itself derived
from ``wx.lib.agw.cubecolourdialog``). It lets you pick a neutral white
*visually*: an HSV colour wheel plus two brightness bars (foreground patch and
surrounding background) feed a large colour patch you judge by eye, with RGB /
HSV spin boxes for fine tuning. A "measurement area" section sizes and positions
that patch on the screen. The chosen RGB, background brightness and patch
geometry persist to :mod:`DisplayCAL.config` (the same
``whitepoint.visual_editor.*`` / ``dimensions.measureframe.whitepoint.visual_editor``
keys the wx tool used).

While open, :class:`_ProfileManager` clears the calibration on the display the
window sits on (installing a temporary sRGB profile via Argyll ``dispwin``) and
restores it on close or when the window moves to another display, so the patch
is judged against the *uncalibrated* panel; it also seeds the initial whitepoint
from the display profile's ``vcgt``. This is inert when no Argyll displays are
enumerated (e.g. headless).

The embedded **Measure** button emits :attr:`VisualWhitepointEditorWindow
.measure_requested`, driven by :class:`DisplayCAL.ui.main_window.MainWindow`
(see ``_visual_whitepoint_editor_measure_handler``), mirroring how wx's button
called back into the parent's ``ambient_measure_handler``.

When a network **pattern generator** (madVR, Prisma, Resolve, Web @
localhost, Chromecast) is configured, :meth:`VisualWhitepointEditorWindow
.set_patterngenerator` is called by :class:`~DisplayCAL.ui.main_window
.MainWindow` after connecting (see :mod:`DisplayCAL.ui.patterngenerator_setup`).
The local background/patch area is then hidden and :class:`_PatternGeneratorStreamer`
streams the current colour and measurement-area geometry to it on a
background thread, debounced with a ``threading.Event`` -- a direct port of
wx's ``update_patterngenerator`` thread (``wx_visual_whitepoint_editor.py``
lines 116-138, 2401-2426), since the network client's own ``send()`` call can
block on I/O and must not run on the GUI thread.
The custom wx spinners/sliders are replaced by native Qt widgets; wx's
AUI-managed pin/float pane has no docking-framework equivalent under Qt, so
:meth:`VisualWhitepointEditorWindow.float_panel`/``dock_panel`` instead detach
the controls panel into a plain top-level :class:`_FloatingControlsWindow`
and re-embed it, toggled via the header row's pin button.
"""

from __future__ import annotations

import colorsys
import os
import re
import sys
import threading
from math import atan2, cos, pi, sin, sqrt
from time import sleep
from typing import TYPE_CHECKING, Callable, ClassVar

from qtpy.QtCore import QObject, QPoint, QRect, Qt, Signal
from qtpy.QtGui import QColor, QIcon, QImage, QLinearGradient, QPainter, QPen, QPixmap
from qtpy.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import (
    DEFAULTS,
    FS_ENC,
    PROFILE_EXT,
    get_argyll_display_number,
    get_data_path,
    get_display_name,
    getcfg,
    setcfg,
)
from DisplayCAL.icc_profile import (
    ICCProfile,
    ICCProfileInvalidError,
    VideoCardGammaType,
    WcsProfilesTagType,
    get_display_profile,
)
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.assets import get_theme_pixmap
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.util_str import safe_asciize
from DisplayCAL.worker import Worker, get_argyll_util

if TYPE_CHECKING:
    from qtpy.QtGui import (
        QCloseEvent,
        QKeyEvent,
        QMouseEvent,
        QPaintEvent,
        QResizeEvent,
        QScreen,
        QShowEvent,
        QWheelEvent,
    )

try:
    from DisplayCAL import real_display_size_mm
except ImportError:  # pragma: no cover - optional native helper
    real_display_size_mm = None

try:
    from DisplayCAL.chromecast_pattern_generator import ChromeCastPatternGenerator
except ImportError:  # pragma: no cover - optional dependency
    ChromeCastPatternGenerator = None

#: Colour attribute names in spin-box order (RGB then HSV).
COLOUR_ATTRIBUTES = ("r", "g", "b", "h", "s", "v")
#: Maximum value per attribute, matching ``COLOUR_ATTRIBUTES``.
COLOUR_MAX_VALUES = (255, 255, 255, 359, 255, 255)

#: Colour-wheel bitmap dimming factor (wx ``AdjustChannels(0.8, ...)``).
WHEEL_DIM = 0.8
#: Inset (px) trimmed from the wheel radius when mapping saturation (wx ``s(12)``).
WHEEL_INSET = 12
#: Marker colours: dark border and bright centre (wx ``(34, 34, 34)`` / light grey).
_MARK_DARK = QColor(34, 34, 34)
_MARK_BRIGHT = QColor(211, 211, 211)


def rad2deg(x: float) -> float:
    """Convert radians to degrees.

    Args:
        x (float): Angle in radians.

    Returns:
        float: Angle in degrees.
    """
    return 180.0 * x / pi


def deg2rad(x: float) -> float:
    """Convert degrees to radians.

    Args:
        x (float): Angle in degrees.

    Returns:
        float: Angle in radians.
    """
    return x * pi / 180.0


def distance(pt1: QPoint, pt2: QPoint) -> float:
    """Return the (rounded) distance between two points.

    Args:
        pt1 (QPoint): First point.
        pt2 (QPoint): Second point.

    Returns:
        float: The Euclidean distance, rounded to the nearest integer.
    """
    return round(sqrt((pt1.x() - pt2.x()) ** 2.0 + (pt1.y() - pt2.y()) ** 2.0))


def angle_from_point(pt: QPoint, center: QPoint) -> float:
    """Return the angle between the x-axis and the line ``center`` → ``pt``.

    Args:
        pt (QPoint): The target point.
        center (QPoint): The centre point.

    Returns:
        float: The angle in radians (0 if ``pt`` equals ``center``).
    """
    y = -1 * (pt.y() - center.y())
    x = pt.x() - center.x()
    if x == 0 and y == 0:
        return 0.0
    return atan2(y, x)


class Colour:
    """An RGB colour with in-place HSV conversion.

    Mirrors ``wx_visual_whitepoint_editor.Colour`` (the cubecolourdialog
    algorithm) but is toolkit-agnostic: it stores plain ``r``/``g``/``b`` and
    ``h``/``s``/``v`` integers and exposes :meth:`to_qcolor`.

    Args:
        r (int): Red component (0..255).
        g (int): Green component (0..255).
        b (int): Blue component (0..255).
        alpha (int): Alpha component (0..255).
    """

    def __init__(self, r: int, g: int, b: int, alpha: int = 255) -> None:
        self.r = r
        self.g = g
        self.b = b
        self._alpha = alpha
        self.h = 0
        self.s = 0
        self.v = 0
        self.to_hsv()

    def to_rgb(self) -> None:
        """Recompute ``r``/``g``/``b`` from the current ``h``/``s``/``v``."""
        max_val = self.v
        delta = (max_val * self.s) / 255.0
        min_val = max_val - delta
        hue = float(self.h)

        if self.h > 300 or self.h <= 60:
            self.r = max_val
            if self.h > 300:
                self.g = round(min_val)
                hue = (hue - 360.0) / 60.0
                self.b = round(-(hue * delta - min_val))
            else:
                self.b = round(min_val)
                hue = hue / 60.0
                self.g = round(hue * delta + min_val)
        elif 60 < self.h < 180:
            self.g = round(max_val)
            if self.h < 120:
                self.b = round(min_val)
                hue = (hue / 60.0 - 2.0) * delta
                self.r = round(min_val - hue)
            else:
                self.r = round(min_val)
                hue = (hue / 60.0 - 2.0) * delta
                self.b = round(min_val + hue)
        else:
            self.b = round(max_val)
            if self.h < 240:
                self.r = round(min_val)
                hue = (hue / 60.0 - 4.0) * delta
                self.g = round(min_val - hue)
            else:
                self.g = round(min_val)
                hue = (hue / 60.0 - 4.0) * delta
                self.r = round(min_val + hue)

    def to_hsv(self) -> None:
        """Recompute ``h``/``s``/``v`` from the current ``r``/``g``/``b``."""
        min_val = float(min(self.r, min(self.g, self.b)))
        max_val = float(max(self.r, max(self.g, self.b)))
        delta = max_val - min_val

        self.v = round(max_val)
        if abs(delta) < 1e-6:
            self.h = self.s = 0
            return

        self.s = round(delta / max_val * 255.0)
        if self.r == round(max_val):
            temp = float(self.g - self.b) / delta
        elif self.g == round(max_val):
            temp = 2.0 + (float(self.b - self.r) / delta)
        else:
            temp = 4.0 + (float(self.r - self.g) / delta)

        temp *= 60
        if temp < 0:
            temp += 360
        elif temp >= 360.0:
            temp = 0
        self.h = round(temp)

    def to_qcolor(self) -> QColor:
        """Return this colour as a ``QColor``.

        Returns:
            QColor: The colour with its stored alpha.
        """
        return QColor(int(self.r), int(self.g), int(self.b), int(self._alpha))


def _dim_pixmap(pixmap: QPixmap, factor: float) -> QPixmap:
    """Return ``pixmap`` with its RGB channels scaled by ``factor``.

    Equivalent to wx ``Image.AdjustChannels`` — used to darken the colour wheel
    so the markers stand out. Alpha is preserved so the wheel stays a disc on a
    transparent background.

    Args:
        pixmap (QPixmap): The source pixmap.
        factor (float): Per-channel multiplier in 0..1.

    Returns:
        QPixmap: The dimmed pixmap (the original if it is null).
    """
    if pixmap.isNull():
        return pixmap
    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            color.setRed(round(color.red() * factor))
            color.setGreen(round(color.green() * factor))
            color.setBlue(round(color.blue() * factor))
            image.setPixelColor(x, y, color)
    return QPixmap.fromImage(image)


def _draw_nested_markers(painter: QPainter, bright: QRect) -> None:
    """Draw the three nested marker rectangles (dark / bright / dark).

    Args:
        painter (QPainter): The active painter.
        bright (QRect): The middle (bright) marker rectangle.
    """
    painter.setBrush(Qt.NoBrush)
    outer = bright.adjusted(-1, -1, 1, 1)
    inner = bright.adjusted(1, 1, -1, -1)
    for color, rect in (
        (_MARK_DARK, outer),
        (_MARK_BRIGHT, bright),
        (_MARK_DARK, inner),
    ):
        painter.setPen(QPen(color, 1))
        painter.drawRect(rect)


class HSVWheel(QWidget):
    """Colour wheel selecting hue (angle) and saturation (radius).

    Args:
        editor (VisualWhitepointEditorWindow): The owning editor, queried for
            the shared :class:`Colour` and marker geometry.
    """

    def __init__(self, editor: VisualWhitepointEditorWindow) -> None:
        super().__init__(editor)
        self._editor = editor
        pixmap = get_theme_pixmap_data("colorwheel")
        self._pixmap = _dim_pixmap(pixmap, WHEEL_DIM)
        self.wheel_size = self._pixmap.width() or 115
        self.setFixedSize(self.wheel_size, self.wheel_size)
        self._tracking = False

    @property
    def radius(self) -> float:
        """Inner radius (px) used to map saturation onto the wheel.

        Returns:
            float: Half the wheel size minus the fixed inset.
        """
        return (self.wheel_size - WHEEL_INSET) / 2.0

    def in_circle(self, pos: QPoint) -> bool:
        """Return whether ``pos`` lies within the wheel disc.

        Args:
            pos (QPoint): The point to test (widget coordinates).

        Returns:
            bool: True if inside the wheel.
        """
        return distance(pos, self._editor.centre) <= self.wheel_size / 2

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt override)
        """Paint the dimmed wheel and the current-colour marker.

        Args:
            event (QPaintEvent): The Qt paint event.
        """
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().color(self.backgroundRole()))
        painter.drawPixmap(0, 0, self._pixmap)
        if self._editor.init_over:
            _draw_nested_markers(painter, self._editor.current_rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        """Begin tracking if the press is inside the wheel.

        Args:
            event (QMouseEvent): The Qt mouse event.
        """
        pos = event.pos()
        self._tracking = self.in_circle(pos)
        if self._tracking:
            self._track(pos)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        """Track hue/saturation while the button is held.

        Args:
            event (QMouseEvent): The Qt mouse event.
        """
        if self._tracking:
            self._track(event.pos())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        """Stop tracking on release.

        Args:
            event (QMouseEvent): The Qt mouse event.
        """
        self._tracking = False

    def _track(self, pos: QPoint) -> None:
        """Set hue/saturation from ``pos`` and refresh dependent controls.

        Args:
            pos (QPoint): The tracked point (widget coordinates).
        """
        editor = self._editor
        colour = editor.colour
        centre = editor.centre

        hue = round(rad2deg(angle_from_point(pos, centre)))
        if hue < 0:
            hue += 360
        colour.h = hue
        # Saturation is clamped to a small range (~0..51) since whitepoints sit
        # close to neutral; the * 0.2 factor matches the wx wheel.
        colour.s = min(round(distance(pos, centre) * 255.0 / self.radius * 0.2), 255)

        editor.calc_rects()
        self.update()
        colour.to_rgb()
        editor.set_spin_vals()
        editor.draw_bright()


class BrightCtrl(QWidget):
    """Vertical brightness bar for a colour's value channel.

    Args:
        editor (VisualWhitepointEditorWindow): The owning editor.
        colour (Colour): The colour whose ``v`` this control edits (the
            foreground patch colour or the background colour).
    """

    def __init__(self, editor: VisualWhitepointEditorWindow, colour: Colour) -> None:
        super().__init__(editor)
        self._editor = editor
        self._colour = colour
        self.setFixedSize(20, 102)

    def bright_rect(self) -> QRect:
        """Return the inset rectangle the gradient/marker are drawn in.

        Returns:
            QRect: The client rect inset by 2 px on every side.
        """
        return self.rect().adjusted(2, 2, -2, -2)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt override)
        """Paint the brightness gradient and the value marker.

        Args:
            event (QPaintEvent): The Qt paint event.
        """
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().color(self.backgroundRole()))
        rect = self.bright_rect()

        hue, sat, _ = colorsys.rgb_to_hsv(
            self._colour.r / 255.0, self._colour.g / 255.0, self._colour.b / 255.0
        )
        top = colorsys.hsv_to_rgb(hue, sat, WHEEL_DIM)
        gradient = QLinearGradient(rect.x(), rect.y(), rect.x(), rect.bottom())
        gradient.setColorAt(
            0.0, QColor(round(top[0] * 255), round(top[1] * 255), round(top[2] * 255))
        )
        gradient.setColorAt(1.0, QColor(0, 0, 0))
        painter.fillRect(rect, gradient)

        height = rect.height()
        y = round(self._colour.v / 255.0 * (height - 6))
        y = height - 4 - 1 - y
        _draw_nested_markers(
            painter, QRect(rect.x() - 1, y, rect.width() + 2, 6)
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        """Set the value from the press position.

        Args:
            event (QMouseEvent): The Qt mouse event.
        """
        self._track(event.pos())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (Qt override)
        """Track the value while dragging.

        Args:
            event (QMouseEvent): The Qt mouse event.
        """
        if event.buttons() & Qt.LeftButton:
            self._track(event.pos())

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 (Qt override)
        """Nudge the value with the mouse wheel.

        Args:
            event (QWheelEvent): The Qt wheel event.
        """
        delta = event.angleDelta().y()
        if delta > 0 and self._colour.v < 255:
            self._colour.v += 1
        elif delta < 0 and self._colour.v > 0:
            self._colour.v -= 1
        self._colour.to_rgb()
        self._editor.after_bright_change()

    def _track(self, pos: QPoint) -> None:
        """Set the colour value from a vertical position.

        Args:
            pos (QPoint): The tracked point (widget coordinates).
        """
        rect = self.bright_rect()
        value = (rect.bottom() - pos.y()) * 255 / rect.height()
        self._colour.v = round(max(0, min(value, 255)))
        self._colour.to_rgb()
        self._editor.after_bright_change()


def get_theme_pixmap_data(name: str) -> QPixmap:
    """Return a theme bitmap stored directly under ``theme/`` (not ``icons``).

    The colour wheel lives at ``theme/colorwheel.png`` rather than under the
    sized ``theme/icons`` tree that :func:`DisplayCAL.ui.assets.get_theme_pixmap`
    serves, so it is resolved here via :func:`DisplayCAL.config.get_data_path`.

    Args:
        name (str): Bitmap base name (without extension).

    Returns:
        QPixmap: The loaded pixmap, or a null pixmap if missing.
    """
    path = get_data_path(f"theme/{name}.png")
    return QPixmap(path) if path else QPixmap()


def _icon_button(name: str, tooltip: str) -> QToolButton:
    """Return a small flat tool button with a themed 16px icon.

    Args:
        name (str): Themed icon base name.
        tooltip (str): The button tooltip.

    Returns:
        QToolButton: The configured button.
    """
    button = QToolButton()
    pixmap = get_theme_pixmap(16, name)
    if not pixmap.isNull():
        button.setIcon(QIcon(pixmap))
    button.setAutoRaise(True)
    button.setToolTip(tooltip)
    return button


class _PatchWidget(QWidget):
    """The measurement-area patch, outlined with a nested dark/light marker.

    Qt port of wx's ``newColourPanel``, created with ``style=wx.SIMPLE_BORDER``
    so the measurement area stays visible even when the patch and surrounding
    background colours are identical (e.g. the default all-white values).
    """

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (Qt override)
        """Paint the background fill, then the outline marker on top.

        Args:
            event (QPaintEvent): The Qt paint event.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        _draw_nested_markers(painter, self.rect().adjusted(2, 2, -3, -3))


class _BackgroundArea(QWidget):
    """The surrounding background with the centred foreground colour patch.

    Args:
        parent (QWidget | None): Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAutoFillBackground(True)
        self.patch = _PatchWidget(self)
        self.patch.setAutoFillBackground(True)
        self._scale = 1.0
        self._x = 0.5
        self._y = 0.5
        self._default_size = 300.0

    def set_layout(
        self, default_size: float, scale: float, x: float, y: float
    ) -> None:
        """Store the patch geometry parameters and re-place the patch.

        Args:
            default_size (float): Patch size (px) at scale 1.0.
            scale (float): Size multiplier.
            x (float): Horizontal position in 0..1.
            y (float): Vertical position in 0..1.
        """
        self._default_size = default_size
        self._scale = scale
        self._x = x
        self._y = y
        self._place_patch()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (Qt override)
        """Re-place the patch when the area is resized.

        Args:
            event (QResizeEvent): The Qt resize event.
        """
        self._place_patch()

    def _place_patch(self) -> None:
        """Size and position the patch from the stored parameters."""
        size = max(1, round(self._default_size * self._scale))
        area_w, area_h = self.width(), self.height()
        size = min(size, area_w, area_h)
        px = round((area_w - size) * self._x)
        py = round((area_h - size) * self._y)
        self.patch.setGeometry(px, py, size, size)


class _ProfileManager(QObject):
    """Clear/restore display calibration for the display the window sits on.

    Installs a temporary sRGB profile (clearing ``vcgt``) on the current display
    so the patch is judged against the uncalibrated panel, and restores the
    original profile on close or display change. Seeds the initial whitepoint
    from the display profile's ``vcgt``. Inert when no Argyll display is
    enumerated for the window's geometry.

    Args:
        window (VisualWhitepointEditorWindow): The managed window.
    """

    managers: ClassVar[list[_ProfileManager]] = []

    #: Emitted (r, g, b) with the vcgt-derived initial whitepoint; delivered on
    #: the GUI thread so the window can redraw safely.
    initial_whitepoint = Signal(int, int, int)

    def __init__(self, window: VisualWhitepointEditorWindow) -> None:
        super().__init__(window)
        self._window = window
        self._lock = threading.Lock()
        self._profiles: dict[tuple, ICCProfile] = {}
        self._display: tuple | None = None
        self._srgb_profile = ICCProfile.from_named_rgb_space("sRGB")
        self._srgb_profile.setDescription(
            f"{APPNAME} Visual Whitepoint Editor Temporary Profile"
        )
        self._srgb_profile.calculate_id()
        self._worker = Worker()
        _ProfileManager.managers.append(self)
        self.initial_whitepoint.connect(
            self._window.apply_initial_whitepoint, Qt.QueuedConnection
        )

    def _current_geometry(self) -> tuple | None:
        """Return the (x, y, w, h) geometry of the window's screen.

        Returns:
            tuple | None: The geometry tuple, or None if no screen is available.
        """
        handle = self._window.windowHandle()
        screen = handle.screen() if handle is not None else None
        if screen is None:
            return None
        rect = screen.geometry()
        return (rect.x(), rect.y(), rect.width(), rect.height())

    def update(self, restore_display_profiles: bool = True) -> None:
        """Clear calibration on the current display, restoring the previous one.

        Args:
            restore_display_profiles (bool): Restore any previously cleared
                display before switching.
        """
        if restore_display_profiles:
            self.restore_display_profiles()
        geometry = self._current_geometry()
        if geometry is None:
            return
        self._display = geometry
        display_no = get_argyll_display_number(geometry)
        if display_no is None:
            print(lang.getstr("whitepoint.visual_editor.display_changed.warning"))
            return
        threading.Thread(
            target=self._manage_display,
            name=f"VisualWhitepointEditor.DisplayManager[Display {display_no}]",
            args=(display_no, geometry),
        ).start()
        display_name = get_display_name(display_no, True)
        if display_name:
            display_name = display_name.replace(
                "[PRIMARY]", lang.getstr("display.primary")
            )
            self._window.setWindowTitle(
                f"{display_name} - {lang.getstr('whitepoint.visual_editor')}"
            )

    def _manage_display(self, display_no: int, geometry: tuple) -> None:
        """Remember and clear the calibration on ``display_no`` (thread-safe).

        Args:
            display_no (int): Argyll display index (0-based).
            geometry (tuple): The display geometry key.
        """
        with self._lock:
            try:
                display_profile = get_display_profile(display_no)
            except (OSError, ICCProfileInvalidError, IndexError) as exception:
                print(
                    f"Could not get display profile for display {display_no + 1}:",
                    exception,
                )
                return
            if not display_profile or display_profile.ID == self._srgb_profile.ID:
                return
            profile = display_profile
            if (
                isinstance(profile.tags.get("MS00"), WcsProfilesTagType)
                and "vcgt" not in profile.tags
            ):
                profile.tags["vcgt"] = profile.tags["MS00"].get_vcgt()
            if isinstance(profile.tags.get("vcgt"), VideoCardGammaType):
                values = profile.tags.vcgt.getNormalizedValues()
                r, g, b = (round(values[-1][i] * 255) for i in range(3))
                self.initial_whitepoint.emit(r, g, b)
            if not self._set_profile_temp_filename(display_profile):
                return
            self._profiles[geometry] = display_profile
            self._install_profile(display_no, self._srgb_profile)

    def _install_profile(
        self, display_no: int, profile: ICCProfile, wrapup: bool = False
    ) -> None:
        """Install ``profile`` on ``display_no`` via ``dispwin`` (thread-safe).

        Args:
            display_no (int): Argyll display index (0-based).
            profile (ICCProfile): The profile to install.
            wrapup (bool): Remove temporary files and detach when done.
        """
        dispwin = get_argyll_util("dispwin")
        if not dispwin:
            print(lang.getstr("argyll.util.not_found", "dispwin"))
            return
        if not profile.filename or not os.path.isfile(profile.filename):
            if not self._set_profile_temp_filename(profile):
                return
            profile.write()
        result = self._worker.exec_cmd(
            dispwin,
            ["-v", f"-d{display_no + 1}", "-I", profile.filename],
            capture_output=True,
            dry_run=False,
        )
        if isinstance(result, Exception):
            print(result)
        if wrapup:
            self._worker.wrapup(False)
            if self in _ProfileManager.managers:
                _ProfileManager.managers.remove(self)

    def _install_profile_locked(
        self, display_no: int, profile: ICCProfile, wrapup: bool = False
    ) -> None:
        """Lock-guarded :meth:`_install_profile`.

        Args:
            display_no (int): Argyll display index (0-based).
            profile (ICCProfile): The profile to install.
            wrapup (bool): Remove temporary files and detach when done.
        """
        with self._lock:
            self._install_profile(display_no, profile, wrapup)

    def _set_profile_temp_filename(self, profile: ICCProfile) -> bool:
        """Point ``profile`` at a writable temp path (can't reinstall in place).

        Args:
            profile (ICCProfile): The profile whose filename to relocate.

        Returns:
            bool: True on success, False if a temp dir could not be created.
        """
        temp = self._worker.create_tempdir()
        if isinstance(temp, Exception):
            print(temp)
            return False
        if profile.filename:
            profile_name = os.path.basename(profile.filename)
        else:
            profile_name = profile.getDescription() + PROFILE_EXT
        if (
            sys.platform in ("win32", "darwin")
            or FS_ENC.upper() not in ("UTF8", "UTF-8")
        ) and re.search(r"[^\x20-\x7e]", profile_name):
            profile_name = safe_asciize(profile_name)
        profile.filename = os.path.join(temp, profile_name)
        return True

    def restore_display_profiles(
        self, wrapup: bool = False, wait: bool = False
    ) -> None:
        """Reinstall the memorised display profiles, restoring calibration.

        Args:
            wrapup (bool): Remove temporary files and detach when done.
            wait (bool): Block until each restore thread finishes.
        """
        while self._profiles:
            geometry, profile = self._profiles.popitem()
            display_no = get_argyll_display_number(geometry)
            if display_no is None:
                print(lang.getstr("whitepoint.visual_editor.display_changed.warning"))
                continue
            thread = threading.Thread(
                target=self._install_profile_locked,
                name=f"VisualWhitepointEditor.Restore[Display {display_no}]",
                args=(display_no, profile, wrapup),
            )
            thread.start()
            if wait:
                thread.join()


class _FloatingControlsWindow(QWidget):
    """Floating window that hosts the detached controls panel.

    Qt port of wx's AUI-floated ``mainPanel`` pane (see wx's
    ``PinButton(True)`` / ``float_pane_handler``). There is no AUI-docking
    equivalent under Qt, so this is a plain top-level ``QWidget`` (no modal
    dialog semantics, e.g. no Escape-to-close) that clicking its native close
    button re-docks rather than destroys, mirroring wx's
    ``close_pane_handler`` (which vetoes the close and docks the pane
    instead).

    Args:
        editor (VisualWhitepointEditorWindow): The owning editor.
    """

    def __init__(self, editor: VisualWhitepointEditorWindow) -> None:
        super().__init__(editor, Qt.Tool)
        self._editor = editor

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        """Dock the panel back into the editor instead of closing.

        Args:
            event (QCloseEvent): The Qt close event.
        """
        event.ignore()
        self._editor.dock_panel()


class _PatternGeneratorStreamer:
    """Streams the current colour/geometry to a network pattern generator.

    Port of wx's module-level ``update_patterngenerator`` thread + the
    ``update_patterngenerator_event`` debounce (``wx_visual_whitepoint_editor.py``
    lines 116-138, 2401-2426): runs on a dedicated background thread since
    ``patterngenerator.send()`` can block on network I/O, woken by
    :meth:`update` rather than polling.

    Args:
        window (VisualWhitepointEditorWindow): The owning editor, queried for
            the current foreground/background colour.
        patterngenerator: A pattern-generator client exposing
            ``send(rgb, bgrgb, x=, y=, w=, h=)``.
    """

    def __init__(self, window: VisualWhitepointEditorWindow, patterngenerator) -> None:
        self._window = window
        self._patterngenerator = patterngenerator
        self._event = threading.Event()
        self._running = True
        self._config = (0.0, 0.0, 1.0)
        self._thread = threading.Thread(
            target=self._run,
            name="VisualWhitepointEditorPatternGeneratorUpdateThread",
            daemon=True,
        )
        self._thread.start()

    def update(self, x: float, y: float, size: float) -> None:
        """Queue a new colour/geometry send.

        Args:
            x (float): Patch horizontal position (0..1).
            y (float): Patch vertical position (0..1).
            size (float): Patch size (0..1, fraction of the display).
        """
        self._config = (x, y, size)
        self._event.set()

    def stop(self) -> None:
        """Stop the background thread (does not disconnect the client)."""
        self._running = False
        self._event.set()

    def _run(self) -> None:
        while self._running:
            if self._event.wait(0.05):
                self._event.clear()
                if not self._running:
                    break
                x, y, size = self._config
                colour = self._window.colour
                bgcolour = self._window._bgcolour
                self._patterngenerator.send(
                    (colour.r / 255.0, colour.g / 255.0, colour.b / 255.0),
                    (bgcolour.r / 255.0, bgcolour.g / 255.0, bgcolour.b / 255.0),
                    x=x,
                    y=y,
                    w=size,
                    h=size,
                )
            sleep(0.05)


class VisualWhitepointEditorWindow(BaseWindow):
    """Standalone visual whitepoint editor window."""

    #: Emitted when the embedded "Measure" button is clicked. The main
    #: window (which owns the instrument/worker) drives the actual
    #: measurement and re-enables :attr:`measure_btn` when done -- mirrors
    #: wx's ``measure_btn`` calling back into ``Parent.ambient_measure_handler``.
    measure_requested = Signal()

    def __init__(self) -> None:
        super().__init__(
            name="VisualWhitepointEditor",
            title=lang.getstr("whitepoint.visual_editor"),
            icon_name=APPNAME.lower(),
        )
        rgb = [int(getcfg(f"whitepoint.visual_editor.{a}")) for a in "rgb"]
        self.colour = Colour(*rgb)
        self._bgcolour = Colour(*rgb)
        self._bgcolour.v = int(getcfg("whitepoint.visual_editor.bg_v"))
        self._bgcolour.to_rgb()

        self.init_over = False
        self._in_draw_all = False
        self._setting_spins = False
        self._fullscreen = False
        self.current_rect = QRect(0, 0, 0, 0)
        self.display_size_mm: dict[tuple, list[float]] = {}
        self.default_size = 300.0
        self._pm: _ProfileManager | None = None
        self._float_window: _FloatingControlsWindow | None = None
        self._patterngenerator = None
        self._streamer: _PatternGeneratorStreamer | None = None

        cfg_x, cfg_y, cfg_scale = (
            float(v)
            for v in getcfg(
                "dimensions.measureframe.whitepoint.visual_editor"
            ).split(",")
        )

        self._build_ui(cfg_x, cfg_y, cfg_scale)

        half = self.hsv_wheel.wheel_size // 2
        self.centre = QPoint(half, half)
        self.calc_rects()
        self.set_spin_vals()
        self.init_over = True
        self.resize(900, 620)

    # -- construction ------------------------------------------------------

    def _build_ui(self, cfg_x: float, cfg_y: float, cfg_scale: float) -> None:
        """Build the control panel and background area.

        Args:
            cfg_x (float): Stored patch X position (0..1).
            cfg_y (float): Stored patch Y position (0..1).
            cfg_scale (float): Stored patch size scale.
        """
        central = QWidget(self)
        central.setAutoFillBackground(True)
        root = QHBoxLayout(central)

        controls = QWidget(central)
        controls.setAutoFillBackground(True)
        panel = QVBoxLayout(controls)
        panel.setContentsMargins(12, 12, 12, 12)
        panel.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.addWidget(_section_label(lang.getstr("whitepoint")))
        header_row.addStretch(1)
        self.pin_btn = _icon_button(
            "button-pin", lang.getstr("whitepoint.visual_editor.panel.float")
        )
        self.pin_btn.setCheckable(True)
        self.pin_btn.toggled.connect(self._on_pin_toggled)
        header_row.addWidget(self.pin_btn)
        panel.addLayout(header_row)

        self.hsv_wheel = HSVWheel(self)
        self.bright_ctrl = BrightCtrl(self, self.colour)
        self.bg_bright_ctrl = BrightCtrl(self, self._bgcolour)
        wheel_row = QHBoxLayout()
        wheel_row.addStretch(1)
        wheel_row.addWidget(self.hsv_wheel)
        wheel_row.addSpacing(12)
        wheel_row.addWidget(self.bright_ctrl)
        wheel_row.addSpacing(12)
        wheel_row.addWidget(self.bg_bright_ctrl)
        wheel_row.addStretch(1)
        panel.addLayout(wheel_row)

        self.spins: list[QSpinBox] = []
        spin_grid = QGridLayout()
        channels = ("red", "green", "blue", "hue", "saturation", "brightness")
        for index, channel in enumerate(channels):
            spin = QSpinBox()
            spin.setRange(0, COLOUR_MAX_VALUES[index])
            spin.setAlignment(Qt.AlignRight)
            spin.valueChanged.connect(lambda _v, i=index: self._on_spin(i))
            self.spins.append(spin)
            cell = QVBoxLayout()
            cell.addWidget(QLabel(lang.getstr(channel)))
            cell.addWidget(spin)
            spin_grid.addLayout(cell, index // 3, index % 3)
        panel.addLayout(spin_grid)

        self.reset_btn = QPushButton(lang.getstr("reset"))
        self.reset_btn.clicked.connect(self._on_reset)
        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        reset_row.addWidget(self.reset_btn)
        reset_row.addStretch(1)
        panel.addLayout(reset_row)

        panel.addWidget(_section_label(lang.getstr("measureframe.title")))
        area_grid = QGridLayout()

        self.area_size_slider = _slider(
            10, 1000, round(min(cfg_scale * 100, 1000)), self._on_area
        )
        self.zoom_normal_btn = _icon_button(
            "zoom-original-outline", lang.getstr("measureframe.zoomnormal")
        )
        self.zoom_normal_btn.clicked.connect(self._on_zoom_normal)
        area_grid.addWidget(QLabel(lang.getstr("size")), 0, 0)
        area_grid.addWidget(self.area_size_slider, 0, 1)
        area_grid.addWidget(self.zoom_normal_btn, 0, 2)

        self.area_x_slider = _slider(0, 1000, round(cfg_x * 1000), self._on_area)
        self.center_x_btn = _icon_button(
            "window-center-outline", lang.getstr("measureframe.center")
        )
        self.center_x_btn.clicked.connect(
            lambda: self._center_slider(self.area_x_slider)
        )
        area_grid.addWidget(QLabel("X"), 1, 0)
        area_grid.addWidget(self.area_x_slider, 1, 1)
        area_grid.addWidget(self.center_x_btn, 1, 2)

        self.area_y_slider = _slider(0, 1000, round(cfg_y * 1000), self._on_area)
        self.center_y_btn = _icon_button(
            "window-center-outline", lang.getstr("measureframe.center")
        )
        self.center_y_btn.clicked.connect(
            lambda: self._center_slider(self.area_y_slider)
        )
        area_grid.addWidget(QLabel("Y"), 2, 0)
        area_grid.addWidget(self.area_y_slider, 2, 1)
        area_grid.addWidget(self.center_y_btn, 2, 2)
        area_grid.setColumnStretch(1, 1)
        panel.addLayout(area_grid)

        self.measure_btn = QPushButton(lang.getstr("measure"))
        self.measure_btn.clicked.connect(self._on_measure)
        measure_row = QHBoxLayout()
        measure_row.addStretch(1)
        measure_row.addWidget(self.measure_btn)
        measure_row.addStretch(1)
        panel.addLayout(measure_row)
        panel.addStretch(1)

        self.bg_area = _BackgroundArea(central)
        self.controls = controls
        self._root_layout = root
        root.addWidget(controls, 0)
        root.addWidget(self.bg_area, 1)
        self.setCentralWidget(central)

        self.set_panel_colours()

    # -- drawing / state ---------------------------------------------------

    def calc_rects(self) -> None:
        """Recompute the wheel marker rectangle for the current hue/saturation."""
        pt = self.point_from_angle(self.colour.h, self.colour.s)
        self.current_rect = QRect(pt.x() - 5, pt.y() - 5, 10, 10)

    def point_from_angle(self, angle: float, sat: float) -> QPoint:
        """Return the wheel point for a hue ``angle`` and saturation ``sat``.

        Args:
            angle (float): Hue in degrees.
            sat (float): Saturation (0..255, effectively 0..51 on the wheel).

        Returns:
            QPoint: The point in wheel-widget coordinates.
        """
        radius = self.hsv_wheel.radius
        sat_px = min(sat * radius / 51.0, radius)
        angle_r = deg2rad(angle)
        x = sat_px * cos(angle_r)
        y = sat_px * sin(angle_r)
        return QPoint(round(x) + self.centre.x(), -round(y) + self.centre.y())

    def set_spin_vals(self) -> None:
        """Push the current colour into the spin boxes and repaint the patch."""
        self._setting_spins = True
        for spin, attribute in zip(self.spins, COLOUR_ATTRIBUTES):
            spin.blockSignals(True)
            spin.setValue(int(getattr(self.colour, attribute)))
            spin.blockSignals(False)
        self._setting_spins = False
        self.set_panel_colours()
        self._update_patterngenerator()

    def set_panel_colours(self) -> None:
        """Repaint the foreground patch and background from the colours."""
        self._set_widget_color(self.bg_area.patch, self.colour.to_qcolor())
        self._bgcolour.h = self.colour.h
        self._bgcolour.s = self.colour.s
        self._bgcolour.to_rgb()
        self._set_widget_color(self.bg_area, self._bgcolour.to_qcolor())

    @staticmethod
    def _set_widget_color(widget: QWidget, color: QColor) -> None:
        """Fill ``widget``'s background with ``color``.

        Args:
            widget (QWidget): The widget to recolour.
            color (QColor): The background colour.
        """
        palette = widget.palette()
        palette.setColor(widget.backgroundRole(), color)
        widget.setPalette(palette)

    def draw_bright(self) -> None:
        """Repaint both brightness bars."""
        self.bright_ctrl.update()
        self.bg_bright_ctrl.update()

    def draw_all(self) -> None:
        """Redraw every custom control after a colour change."""
        if not self.init_over or self._in_draw_all:
            return
        self._in_draw_all = True
        self.calc_rects()
        self.hsv_wheel.update()
        self.draw_bright()
        self.set_spin_vals()
        self._in_draw_all = False

    def after_bright_change(self) -> None:
        """Refresh markers and spin values after a brightness edit."""
        self.draw_bright()
        self.set_spin_vals()

    # -- event handlers ----------------------------------------------------

    def _on_spin(self, index: int) -> None:
        """Apply a spin-box edit to the colour and redraw.

        Args:
            index (int): The spin box index into ``COLOUR_ATTRIBUTES``.
        """
        if not self.init_over or self._setting_spins:
            return
        attribute = COLOUR_ATTRIBUTES[index]
        value = self.spins[index].value()
        if value == getattr(self.colour, attribute):
            return
        value = max(0, min(value, COLOUR_MAX_VALUES[index]))
        setattr(self.colour, attribute, value)
        if index < 3:
            self.colour.to_hsv()
        else:
            self.colour.to_rgb()
        self.draw_all()

    def _on_reset(self) -> None:
        """Reset the colour and background brightness to the defaults."""
        rgb = [int(DEFAULTS[f"whitepoint.visual_editor.{a}"]) for a in "rgb"]
        self.colour.r, self.colour.g, self.colour.b = rgb
        self.colour.to_hsv()
        self._bgcolour.v = int(DEFAULTS["whitepoint.visual_editor.bg_v"])
        self.draw_all()

    def _on_area(self) -> None:
        """Re-place the patch from the area sliders."""
        scale = self.area_size_slider.value() / 100.0
        x = self.area_x_slider.value() / 1000.0
        y = self.area_y_slider.value() / 1000.0
        self.bg_area.set_layout(self.default_size, scale, x, y)
        self._update_patterngenerator()

    def _update_patterngenerator(self) -> None:
        """Push the current colour/geometry to the pattern generator, if any.

        Port of wx's ``update_patterngenerator`` instance method
        (``wx_visual_whitepoint_editor.py`` lines 2401-2426): same
        size/x/y normalisation, computed from the slider ranges rather than
        the already-normalised values :meth:`_on_area` uses, so a patch
        pinned to the disc edge stays fully on-screen.
        """
        if self._streamer is None:
            return
        size = min(
            self.area_size_slider.value()
            / float(
                self.area_size_slider.maximum() - self.area_size_slider.minimum()
            ),
            1,
        )
        x = max(
            self.area_x_slider.value() / float(self.area_x_slider.maximum())
            * (1 - size),
            0,
        )
        y = max(
            self.area_y_slider.value() / float(self.area_y_slider.maximum())
            * (1 - size),
            0,
        )
        self._streamer.update(x, y, size)

    def _on_measure(self) -> None:
        """Persist the current colour/geometry and request a measurement.

        Qt port of wx's ``measure()``: disables the button (re-enabled by
        the main window once the measurement completes) and persists
        settings first, since the main window's consumer reads
        ``whitepoint.visual_editor.*`` back out of config.
        """
        self.measure_btn.setEnabled(False)
        self._save_cfg()
        self.measure_requested.emit()

    def _on_zoom_normal(self) -> None:
        """Reset the patch size slider to the default scale."""
        scale = float(
            DEFAULTS["dimensions.measureframe.whitepoint.visual_editor"].split(",")[2]
        )
        self.area_size_slider.setValue(round(scale * 100))

    def set_patterngenerator(self, patterngenerator) -> None:
        """Attach or detach a network pattern generator for patch output.

        Port of the ``patterngenerator`` constructor argument wx's
        ``VisualWhitepointEditor`` takes (``wx_visual_whitepoint_editor.py``
        lines 1948-2209): while attached, the local background/patch area is
        hidden (mirrors wx's ``self.bgPanel.Show(not patterngenerator)``) and
        the current colour + measurement-area geometry stream to the
        generator via :class:`_PatternGeneratorStreamer`. Called by
        :class:`DisplayCAL.ui.main_window.MainWindow` after connecting (see
        :mod:`DisplayCAL.ui.patterngenerator_setup`) since, unlike wx, this
        window is a reused singleton rather than constructed fresh per open.

        Args:
            patterngenerator: A pattern-generator client exposing
                ``send(rgb, bgrgb, x=, y=, w=, h=)``, or None to detach.
        """
        if self._streamer is not None:
            self._streamer.stop()
            self._streamer = None
        self._patterngenerator = patterngenerator
        self.bg_area.setVisible(patterngenerator is None)
        if patterngenerator is not None:
            self._streamer = _PatternGeneratorStreamer(self, patterngenerator)
            self._update_patterngenerator()

    @staticmethod
    def _center_slider(slider: QSlider) -> None:
        """Centre ``slider`` (position sliders run 0..1000).

        Args:
            slider (QSlider): The slider to centre.
        """
        slider.setValue(500)

    # -- controls panel float/dock ------------------------------------------

    def _on_pin_toggled(self, checked: bool) -> None:
        """Float or dock the controls panel in response to the pin button.

        Args:
            checked (bool): True to float the panel, False to dock it.
        """
        if checked:
            self.float_panel()
        else:
            self.dock_panel()

    def float_panel(self) -> None:
        """Detach the controls panel into its own top-level window."""
        if self._float_window is not None:
            return
        self._root_layout.removeWidget(self.controls)
        float_window = _FloatingControlsWindow(self)
        layout = QVBoxLayout(float_window)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.controls)
        self.controls.show()
        self._float_window = float_window
        top_left = self.mapToGlobal(QPoint(0, 0))
        float_window.move(top_left.x() + 10, top_left.y() + 10)
        float_window.resize(self.controls.sizeHint())
        float_window.show()
        self.pin_btn.setToolTip(lang.getstr("whitepoint.visual_editor.panel.dock"))

    def dock_panel(self) -> None:
        """Re-embed a floating controls panel back into the editor window."""
        if self._float_window is None:
            return
        float_window = self._float_window
        self._float_window = None
        self.controls.setParent(None)
        self._root_layout.insertWidget(0, self.controls, 0)
        self.controls.show()
        float_window.deleteLater()
        self.pin_btn.blockSignals(True)
        self.pin_btn.setChecked(False)
        self.pin_btn.blockSignals(False)
        self.pin_btn.setToolTip(lang.getstr("whitepoint.visual_editor.panel.float"))

    def apply_initial_whitepoint(self, r: int, g: int, b: int) -> None:
        """Seed the editor from a display profile's ``vcgt`` whitepoint.

        Args:
            r (int): Red component (0..255).
            g (int): Green component (0..255).
            b (int): Blue component (0..255).
        """
        self.colour.r, self.colour.g, self.colour.b = r, g, b
        self.colour.to_hsv()
        self.draw_all()

    # -- display sizing ----------------------------------------------------

    def _current_screen(self) -> QScreen | None:
        """Return the screen the window is currently on.

        Returns:
            QScreen | None: The window's screen, if resolvable.
        """
        handle = self.windowHandle()
        return handle.screen() if handle is not None else None

    def _refresh_display_metrics(self) -> None:
        """Update the size-slider maximum and default patch size for the screen."""
        screen = self._current_screen()
        if screen is None:
            return
        rect = screen.geometry()
        geometry = (rect.x(), rect.y(), rect.width(), rect.height())
        maxv = 1000
        if real_display_size_mm is not None:
            display_no = get_argyll_display_number(geometry)
            if display_no is not None:
                size_mm = real_display_size_mm.real_display_size_mm(display_no)
                if 0 not in size_mm:
                    self.display_size_mm[geometry] = [float(v) for v in size_mm]
                    maxv = round(max(size_mm))
        if maxv > 100:
            self.area_size_slider.setMaximum(maxv)
        size_mm = self.display_size_mm.get(geometry)
        if size_mm:
            px_per_mm = max(rect.width() / size_mm[0], rect.height() / size_mm[1])
            self.default_size = px_per_mm * 100
        else:
            self.default_size = 300.0

    # -- Qt lifecycle ------------------------------------------------------

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 (Qt override)
        """Start the profile manager and size the patch on first show.

        Args:
            event (QShowEvent): The Qt show event.
        """
        super().showEvent(event)
        if self._pm is None:
            self._refresh_display_metrics()
            self._on_area()
            self._pm = _ProfileManager(self)
            self._pm.update(restore_display_profiles=False)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (Qt override)
        """Handle Escape (exit fullscreen / close) and F11 (toggle fullscreen).

        Args:
            event (QKeyEvent): The Qt key event.
        """
        if event.key() == Qt.Key_Escape:
            if self._fullscreen:
                self._set_fullscreen(False)
            else:
                self.close()
        elif event.key() == Qt.Key_F11:
            self._set_fullscreen(not self._fullscreen)
        else:
            super().keyPressEvent(event)

    def _set_fullscreen(self, fullscreen: bool) -> None:
        """Enter or leave fullscreen.

        Args:
            fullscreen (bool): Whether to show the window fullscreen.
        """
        self._fullscreen = fullscreen
        if fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        """Persist settings and restore display calibration before closing.

        Args:
            event (QCloseEvent): The Qt close event.
        """
        self.dock_panel()
        self._save_cfg()
        if self._pm is not None:
            self._pm.restore_display_profiles(wrapup=True, wait=True)
        if self._streamer is not None:
            self._streamer.stop()
            self._streamer = None
        # Only Chromecast disconnects on close (a per-session device
        # connection); Prisma/Resolve/Web stay connected for reuse, mirroring
        # wx's ``Bind(wx.EVT_CLOSE, self.patterngenerator_disconnect)``, which
        # is likewise only wired up for ``ChromeCastPatternGenerator``.
        if (
            self._patterngenerator is not None
            and ChromeCastPatternGenerator is not None
            and isinstance(self._patterngenerator, ChromeCastPatternGenerator)
        ):
            try:
                self._patterngenerator.disconnect_client()
            except Exception as exception:  # noqa: BLE001 (best-effort cleanup)
                print(exception)
        super().closeEvent(event)

    def _save_cfg(self) -> None:
        """Store the current colour and patch geometry to config."""
        for attribute in "rgb":
            setcfg(
                f"whitepoint.visual_editor.{attribute}",
                int(getattr(self.colour, attribute)),
            )
        setcfg("whitepoint.visual_editor.bg_v", int(self._bgcolour.v))
        x = self.area_x_slider.value() / 1000.0
        y = self.area_y_slider.value() / 1000.0
        scale = self.area_size_slider.value() / 100.0
        setcfg(
            "dimensions.measureframe.whitepoint.visual_editor",
            f"{x:f},{y:f},{scale:f}",
        )


def _section_label(text: str) -> QLabel:
    """Return a bold section heading label.

    Args:
        text (str): The heading text.

    Returns:
        QLabel: The configured label.
    """
    label = QLabel(text)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    return label


def _slider(
    minimum: int, maximum: int, value: int, on_change: Callable[[], None]
) -> QSlider:
    """Return a horizontal slider wired to ``on_change``.

    Args:
        minimum (int): Minimum value.
        maximum (int): Maximum value.
        value (int): Initial value.
        on_change (Callable): Slot connected to ``valueChanged``.

    Returns:
        QSlider: The configured slider.
    """
    slider = QSlider(Qt.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setValue(max(minimum, min(value, maximum)))
    slider.valueChanged.connect(on_change)
    return slider


def main() -> int:
    """Entry point for the Qt visual whitepoint editor.

    Returns:
        int: The Qt application exit code.
    """
    config.initcfg()
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    worker = Worker()
    worker.enumerate_displays_and_ports(
        check_lut_access=False, enumerate_ports=False
    )
    window = VisualWhitepointEditorWindow()
    app.top_window = window
    window.show()
    window.listen()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
