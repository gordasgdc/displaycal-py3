"""Qt widgets that reproduce the "fancy" chrome of the wx progress dialog.

Ports the visual pieces :mod:`DisplayCAL.ui.progress_dialog` originally
dropped as "not load-bearing": the animated shutter/patch throbber
(``DisplayCAL.wx_windows.AnimatedBitmap`` + ``ProgressDialog.get_bitmaps``)
and the thin colour-cycling gauge (``DisplayCAL.wx_windows.BetterPyGauge``).
Sound playback itself is not implemented here -- ``Worker.audio_visual_feedback``
(``DisplayCAL/worker.py``) already plays it directly through the
toolkit-neutral ``DisplayCAL.audio.Sound``; see
:class:`DisplayCAL.ui.worker_runner.ProgressAdapter` for the ``animbmp`` /
``sound_on_off_btn`` duck-typing that lets it find this dialog. Windows
taskbar-progress integration remains out of scope (Windows-only, not visual).

The animation frames are pre-rendered once per progress type with Pillow
(already a project dependency) and cached at module scope, mirroring the wx
``ProgressDialog.bitmaps`` class-level cache.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import QRectF, Qt, QTimer
from qtpy.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPixmap
from qtpy.QtWidgets import QWidget

from DisplayCAL.config import get_data_path

if TYPE_CHECKING:
    from PIL.Image import Image
    from qtpy.QtGui import QPaintEvent

# progress_type -> 0 Processing, 1 Measuring, 2 Generating test patches.
# Matches DisplayCAL.wx_windows.ProgressDialog.get_bitmaps / anim_fadein.
_BITMAP_CACHE: dict[int, list[QPixmap]] = {}

# Determinate gauge colour cycle, lifted verbatim from
# DisplayCAL.wx_windows.ProgressDialog.__init__ (self.gauge.SetBarGradients).
BAR_GRADIENTS = [
    ("#0099CC", "#00CCFF"),
    ("#0088BB", "#00BBEE"),
    ("#0077AA", "#00AADD"),
    ("#006699", "#0099CC"),
    ("#0077AA", "#00AADD"),
    ("#0088BB", "#00BBEE"),
]

# Indeterminate ("pulse") gauge colour cycle, ditto
# (self.gauge.SetIndeterminateBarGradients).
INDETERMINATE_BAR_GRADIENTS = [
    ("#00CCFF", "#001144"),
    ("#00BBEE", "#002255"),
    ("#00AADD", "#003366"),
    ("#0099CC", "#004477"),
    ("#0088BB", "#005588"),
    ("#0077AA", "#006699"),
    ("#006699", "#0077AA"),
    ("#005588", "#0088BB"),
    ("#004477", "#0099CC"),
    ("#003366", "#00AADD"),
    ("#002255", "#00BBEE"),
    ("#001144", "#00CCFF"),
    ("#002255", "#00BBEE"),
    ("#003366", "#00AADD"),
    ("#004477", "#0099CC"),
    ("#005588", "#0088BB"),
    ("#006699", "#0077AA"),
    ("#0077AA", "#006699"),
    ("#0088BB", "#005588"),
    ("#0099CC", "#004477"),
    ("#00AADD", "#003366"),
    ("#00BBEE", "#002255"),
]


def _pil_to_qpixmap(img: Image) -> QPixmap:
    """Convert a Pillow RGBA image to a QPixmap without touching ImageQt.

    Args:
        img (Image): A Pillow ``Image`` (any mode; converted to RGBA).

    Returns:
        QPixmap: The converted pixmap, detached from the source buffer.
    """
    img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qimage = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimage.copy())


def _scale_alpha(img: Image, factor: float) -> Image:
    """Scale an RGBA image's alpha channel by ``factor``.

    Qt/Pillow equivalent of wx ``Image.AdjustChannels(1, 1, 1, factor)``,
    which the wx dialog uses to fade the patch animation in and out.

    Args:
        img: A Pillow RGBA image.
        factor (float): The alpha multiplier (clamped to ``0..1`` per pixel).

    Returns:
        Image: A new image with the scaled alpha channel.
    """
    from PIL import Image

    img = img.convert("RGBA")
    r, g, b, a = img.split()
    a = a.point(lambda v: max(0, min(255, round(v * factor))))
    return Image.merge("RGBA", (r, g, b, a))


def _shutter_frames() -> list[QPixmap]:
    """Build the 15-frame shutter (diaphragm) animation for progress_type 1.

    Port of the ``progress_type == 1`` branch of
    ``DisplayCAL.wx_windows.ProgressDialog.get_bitmaps``: only the first 5
    ``shutter_anim`` frames are used, closing then opening then closing again
    (``[5,4,3,2,1, 1,2,3,4,5, 5,4,3,2,1]``).

    Returns:
        list[QPixmap]: The 15 animation frames, or an empty list if the
        expected assets are missing.
    """
    paths = sorted(get_data_path("theme/shutter_anim", r"\.png$") or [])[:5]
    if len(paths) != 5:
        return []
    frames = [QPixmap(p) for p in reversed(paths)]  # [5,4,3,2,1]
    frames.extend(reversed(frames))  # + [1,2,3,4,5]
    frames.extend(frames[:5])  # + [5,4,3,2,1]
    return frames


def _patch_frames() -> list[QPixmap]:
    """Build the 63-frame test-patch animation for progress_type 2.

    Port of the ``progress_type == 2`` branch of ``get_bitmaps``: the 9
    ``patch_anim`` frames looped 3x while fading in (27 frames), looped once
    at full opacity (9 frames), then looped 3x again while fading out (27
    frames).

    Returns:
        list[QPixmap]: The 63 animation frames, or an empty list if the
        expected assets are missing.
    """
    from PIL import Image

    paths = sorted(get_data_path("theme/patch_anim", r"\.png$") or [])
    if len(paths) != 9:
        return []
    base = [Image.open(p).convert("RGBA") for p in paths]

    frames = list(base)
    for _ in range(3):
        frames.extend(base)
    # frames[:27] fade in, frames[27:36] stay at full opacity.
    for i in range(27):
        frames[i] = _scale_alpha(frames[i], i / 27.0)

    tail = frames[27:36]
    for _ in range(3):
        frames.extend(tail)
    # frames[36:63] fade out.
    for i in range(27):
        idx = 36 + i
        frames[idx] = _scale_alpha(frames[idx], 1 - i / 26.0)

    return [_pil_to_qpixmap(frame) for frame in frames]


def get_progress_bitmaps(progress_type: int) -> list[QPixmap]:
    """Get (and cache) the animation frames for a progress type.

    Args:
        progress_type (int): 0 (processing), 1 (measuring) or 2 (generating
            test patches).

    Returns:
        list[QPixmap]: The animation frames. Empty for progress_type 0 --
        this mirrors the wx dialog, where the "processing" animation
        (shutter + jet frames) never actually assembles because the combined
        frame count fails its own sanity check, so it silently shows nothing.
    """
    if progress_type not in _BITMAP_CACHE:
        if progress_type == 1:
            frames = _shutter_frames()
        elif progress_type == 2:
            frames = _patch_frames()
        else:
            frames = []
        _BITMAP_CACHE[progress_type] = frames
    return _BITMAP_CACHE[progress_type]


class AnimatedBitmap(QWidget):
    """Plays a sequence of QPixmap frames, matching wx ``AnimatedBitmap``.

    Args:
        parent (QWidget | None): Optional parent widget.
        size (tuple[int, int]): Fixed widget size. Defaults to ``(200, 200)``.
        background_color (str): Fill colour painted behind the current frame
            (matches the dialog's dark background).
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        size: tuple[int, int] = (200, 200),
        background_color: str = "#141414",
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(*size)
        self._background_color = QColor(background_color)
        self._frames: list[QPixmap] = []
        self._frame = 0
        self.range = (0, -1)
        self.loop = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer)

    @property
    def frame(self) -> int:
        """The index of the currently displayed frame."""
        return self._frame

    @frame.setter
    def frame(self, value: int) -> None:
        self._frame = value
        self.update()

    def set_bitmaps(
        self,
        bitmaps: list[QPixmap],
        range_: tuple[int, int] = (0, -1),
        loop: bool = True,  # noqa: FBT001, FBT002
    ) -> None:
        """Set the animation frames and looping range.

        Args:
            bitmaps (list[QPixmap]): The animation frames.
            range_ (tuple[int, int]): The looped frame range; -1 means the
                last frame.
            loop (bool): Whether to loop back to ``range_[0]`` at the end.
        """
        self._frames = bitmaps
        self.range = range_
        self.loop = loop
        self._frame = 0
        self.update()

    def play(self, fps: int = 24) -> None:
        """Start advancing frames at ``fps`` frames per second."""
        self._timer.start(int(1000.0 / fps))

    def stop(self) -> None:
        """Stop advancing frames (the current frame stays on screen)."""
        self._timer.stop()

    def _on_timer(self) -> None:
        first_frame, last_frame = self.range
        n = len(self._frames)
        if first_frame < 0:
            first_frame += n
        if last_frame < 0:
            last_frame += n
        frame = self._frame
        if frame < last_frame:
            frame += 1
        elif self.loop:
            frame = first_frame
        if frame != self._frame:
            self._frame = frame
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802, ARG002
        """Paint the current frame over the dialog's background colour."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._background_color)
        if self._frames:
            frame = min(self._frame, len(self._frames) - 1)
            painter.drawPixmap(0, 0, self._frames[frame])


class GradientGauge(QWidget):
    """A thin, colour-cycling progress bar matching wx ``BetterPyGauge``.

    Exposes the subset of ``QProgressBar``'s API the dialog and its tests
    rely on (``minimum``/``maximum``/``value``/``setRange``/``setValue``) so
    it is a drop-in replacement, while painting the same rounded, glowing
    capsule the wx dialog shows: a full-width shimmering bar in indeterminate
    ("pulse") mode, a proportionally filled one once real progress is set.

    Args:
        parent (QWidget | None): Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(4)
        self._minimum = 0
        self._maximum = 0
        self._value = 0.0
        self._indeterminate = True
        self._background_color = QColor("#003366")
        self._bar_gradients = BAR_GRADIENTS
        self._indeterminate_gradients = INDETERMINATE_BAR_GRADIENTS
        self._gradient_index = 0
        self._cycle_timer = QTimer(self)
        self._cycle_timer.timeout.connect(self._on_cycle_tick)
        self._cycle_timer.start(67)  # Matches BetterPyGauge.Start() default.

    def minimum(self) -> int:
        """The gauge's minimum value (always 0)."""
        return self._minimum

    def maximum(self) -> int:
        """The gauge's maximum value (0 while indeterminate)."""
        return self._maximum

    def value(self) -> int:
        """The gauge's current (rounded) value."""
        return round(self._value)

    def setRange(self, minimum: int, maximum: int) -> None:  # noqa: N802
        """Set the gauge range; ``maximum == 0`` means indeterminate.

        Args:
            minimum (int): The minimum value (always 0 in practice).
            maximum (int): The maximum value, or 0 for indeterminate mode.
        """
        self._minimum = minimum
        self._maximum = maximum
        self._indeterminate = maximum == 0
        self.update()

    def setValue(self, value: float) -> None:  # noqa: N802
        """Set the current value and switch to determinate mode.

        Args:
            value (float): The new value, clamped to ``[0, maximum]``.
        """
        self._indeterminate = False
        ceiling = self._maximum or 1
        self._value = max(0.0, min(float(value), float(ceiling)))
        self.update()

    def setTextVisible(self, visible: bool) -> None:  # noqa: N802, FBT001
        """No-op: this gauge never draws a percentage label."""

    def _gradient_pool(self) -> list[tuple[str, str]]:
        """The gradient list to cycle through for the current mode."""
        if self._indeterminate:
            return self._indeterminate_gradients
        return self._bar_gradients

    def _on_cycle_tick(self) -> None:
        pool = self._gradient_pool()
        if not pool:
            return
        self._gradient_index = (self._gradient_index + 1) % len(pool)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802, ARG002
        """Paint the rounded capsule background and the gradient fill."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._background_color))
        painter.drawRoundedRect(rect, radius, radius)

        pool = self._gradient_pool()
        if not pool:
            return
        if self._indeterminate:
            width = rect.width()
        else:
            ceiling = self._maximum or 1
            width = max(rect.width() * (self._value / ceiling), rect.height())
        width = min(width, rect.width())
        if width <= 0:
            return

        c1, c2 = pool[self._gradient_index % len(pool)]
        gradient = QLinearGradient(0, 0, width, 0)
        gradient.setColorAt(0, QColor(c1))
        gradient.setColorAt(1, QColor(c2))
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(QRectF(0, 0, width, rect.height()), radius, radius)
