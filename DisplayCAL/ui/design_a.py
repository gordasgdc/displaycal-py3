"""Visual system «Foaia de probă» (proof sheet) -- tokens, fonts, style sheet, widgets.

The application is drawn like a colour proof checked in a D50 viewing booth: a
paper sheet with ink, process-colour control strips, crop marks and mono "slug"
lines. This module is the single place where that look is defined; the rest of
the UI asks it for colours (:func:`tokens`), a font (:func:`family`) or a ready
widget (:class:`ControlStrip`, :class:`CmykRule`, :class:`CropMarks`).

Nothing here touches measurement: the patch window, colour values, timing and
every calculation live elsewhere, and none of these widgets is ever shown over
a patch.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from qtpy.QtCore import QRectF, QSize, Qt
from qtpy.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetricsF,
    QPainter,
    QPen,
)
from qtpy.QtWidgets import QApplication, QSizePolicy, QWidget

from DisplayCAL import config

#: Process colours (identical in light and dark: they are data, like the ink).
CYAN, MAGENTA, YELLOW, KEY = "#00a3e0", "#d4147a", "#ffd400", "#16171a"
RED, GREEN, BLUE = "#e8312f", "#00a651", "#2e3192"

#: The control strip of the proof: primaries, tints, a grey wedge, a hue sweep.
STRIP = (
    CYAN, MAGENTA, YELLOW, KEY, RED, GREEN, BLUE,
    "#6fc7ec", "#ea7fb3", "#ffea7a",
    "#f6f6f4", "#e0e0de", "#c7c7c5", "#a9a9a7", "#8c8c8a", "#707070", "#555555", "#3b3b3b", KEY,
    RED, "#ff8a3d", YELLOW, "#7ed957", GREEN, "#00b4a6", CYAN, "#4a6fd8", BLUE, "#7a3fb0",
    MAGENTA, "#8f2a2a", "#2f3b4a",
)  # fmt: skip


@dataclass(frozen=True)
class Tokens:
    """Colours of one scheme. ``ink`` on ``sheet`` is the reading pair."""

    dark: bool
    booth: str  # the surround the sheet lies on
    sheet: str  # the paper
    inset: str  # fields and wells (a little off the sheet)
    ink: str
    ink2: str  # secondary text (AA on the sheet)
    hair: str  # hairlines inside a page (rgba)
    rule: str  # the strong rule (= ink)
    ok: str  # status text colours (never the process green on paper)
    warn: str
    bad: str
    focus: str
    patch_bg: str  # primary button ("black patch"; a light patch in dark)
    patch_ink: str
    off_bg: str  # disabled controls
    off_ink: str


LIGHT = Tokens(
    dark=False, booth="#b3b5b8", sheet="#f6f6f4", inset="#fdfdfc", ink="#16171a",
    ink2="#4a4c52", hair="rgba(22,23,26,0.22)", rule="#16171a", ok="#0b7a45",
    warn="#8a5b00", bad="#b3121f", focus="#2e3192", patch_bg="#16171a",
    patch_ink="#f6f6f4", off_bg="#e4e4e0", off_ink="#6b6d73",
)  # fmt: skip
DARK = Tokens(
    dark=True, booth="#26272a", sheet="#1b1c1f", inset="#111214", ink="#eceef2",
    ink2="#a9adb6", hair="rgba(236,238,242,0.22)", rule="#eceef2", ok="#4cc38a",
    warn="#f0b44c", bad="#ff6b6b", focus="#8fa6ff", patch_bg="#eceef2",
    patch_ink="#16171a", off_bg="#2a2b2f", off_ink="#8d919b",
)  # fmt: skip

_fonts: dict[str, str] = {}


def tokens(dark: bool | None = None) -> Tokens:
    """Tokens of the scheme in force (or of the given one)."""
    if dark is None:
        dark = QApplication.palette().window().color().lightness() < 128
    return DARK if dark else LIGHT


def load_fonts() -> dict[str, str]:
    """Register the bundled fonts (once) and return their family names.

    Qt needs absolute paths here. When a file is missing the system fonts are
    used and the layout still works (``sans`` / ``mono`` fall back).
    """
    if _fonts:
        return _fonts
    families: dict[str, str] = {}
    for key, name in (
        ("sans", "Archivo-VF.ttf"),
        ("mono", "B612Mono-Regular.ttf"),
        ("mono_bold", "B612Mono-Bold.ttf"),
    ):
        found = config.get_data_path(f"theme/fonts/{name}")
        path = os.path.abspath(found) if isinstance(found, str) else ""
        if not path or not os.path.isfile(path):
            continue
        ident = QFontDatabase.addApplicationFont(path)
        fams = QFontDatabase.applicationFontFamilies(ident) if ident >= 0 else []
        if fams:
            families[key] = fams[0]
    _fonts.update(
        sans=families.get("sans", ""),
        mono=families.get("mono", ""),
    )
    return _fonts


def family(kind: str = "sans") -> str:
    """Family name for ``sans`` (Archivo) or ``mono`` (B612 Mono); ``""`` = system."""
    return load_fonts().get(kind, "")


def mono_font(point_size: float, bold: bool = False, spacing: float = 105.0) -> QFont:
    """The slug-line face: B612 Mono, tracked out a little."""
    f = QFont(family("mono") or QFont().family())
    f.setPointSizeF(point_size)
    f.setBold(bold)
    f.setLetterSpacing(QFont.PercentageSpacing, spacing)
    return f


def sans_font(point_size: float, weight: int = 800) -> QFont:
    """Archivo at a given CSS-style weight (400 body, 800 headings)."""
    f = QFont(family("sans") or QFont().family())
    f.setPointSizeF(point_size)
    f.setWeight(QFont.Weight(max(1, min(1000, weight))))
    return f


def _mix(a: str, b: str, k: float) -> str:
    """Blend two ``#rrggbb`` colours (``k`` = share of ``b``)."""
    ca, cb = QColor(a), QColor(b)
    return QColor(
        round(ca.red() * (1 - k) + cb.red() * k),
        round(ca.green() * (1 - k) + cb.green() * k),
        round(ca.blue() * (1 - k) + cb.blue() * k),
    ).name()


def global_qss(t: Tokens | None = None) -> str:
    """The application style sheet. Lengths are in ``em`` so text size scales it."""
    t = t or tokens()
    ink, inset = t.ink, t.inset
    found = config.get_data_path(
        "theme/guide/chevron_light.svg" if t.dark else "theme/guide/chevron.svg"
    )
    chevron = found.replace(chr(92), "/") if isinstance(found, str) else ""
    handle = _mix(t.sheet, t.ink2, 0.5)
    tick = config.get_data_path(
        "theme/guide/check.svg" if t.dark else "theme/guide/check_light.svg"
    )
    check_image = (
        f'image:url("{tick.replace(chr(92), "/")}");' if isinstance(tick, str) else ""
    )
    up = config.get_data_path(
        "theme/guide/chevron_up_light.svg" if t.dark else "theme/guide/chevron_up.svg"
    )
    chevron_up = up.replace(chr(92), "/") if isinstance(up, str) else ""
    arrow = (
        f'QComboBox::down-arrow,QSpinBox::down-arrow,QDoubleSpinBox::down-arrow'
        f'{{image:url("{chevron}");width:0.8em;height:0.8em;}}'
        f'QSpinBox::up-arrow,QDoubleSpinBox::up-arrow'
        f'{{image:url("{chevron_up}");width:0.8em;height:0.8em;}}'
        if chevron and chevron_up
        else ""
    )
    return f"""{arrow}
QToolTip{{background:{inset};color:{ink};border:1px solid {ink};padding:0.3em 0.5em;}}
QPushButton{{background:{inset};color:{ink};border:1px solid {ink};border-radius:0;
  padding:0.42em 1.1em;min-height:1.2em;}}
QPushButton:hover{{background:{t.patch_bg};color:{t.patch_ink};}}
QPushButton:pressed{{background:{t.patch_bg};color:{t.patch_ink};}}
QPushButton:focus{{border:2px solid {t.focus};padding:0.34em 1.04em;}}
QPushButton:disabled{{background:{t.off_bg};color:{t.off_ink};border:1px solid {t.hair};}}
QPushButton:flat{{background:transparent;border:none;color:{ink};
  text-decoration:underline;padding:0.3em 0.4em;}}
QPushButton:flat:hover{{background:transparent;color:{t.focus};}}
QPushButton[primary="true"]{{background:{t.patch_bg};color:{t.patch_ink};
  border:1px solid {t.patch_bg};padding:0.5em 1.6em;font-weight:700;}}
QPushButton[primary="true"]:hover{{background:{t.ink2};border-color:{t.ink2};}}
QPushButton[primary="true"]:disabled{{background:{t.off_bg};color:{t.off_ink};
  border:1px solid {t.hair};}}
QRadioButton::indicator{{width:0.9em;height:0.9em;border-radius:0.55em;
  border:2px solid {ink};background:transparent;}}
QRadioButton::indicator:checked{{border:2px solid {ink};
  background:qradialgradient(cx:.5,cy:.5,radius:.5,fx:.5,fy:.5,
  stop:0 {ink},stop:.5 {ink},stop:.56 transparent,stop:1 transparent);}}
QRadioButton::indicator:disabled,QCheckBox::indicator:disabled{{border-color:{t.off_ink};}}
QCheckBox::indicator{{width:0.9em;height:0.9em;border-radius:0;
  border:2px solid {ink};background:transparent;}}
QCheckBox::indicator:checked{{border:2px solid {ink};background:{ink};{check_image}}}
QSlider::groove:horizontal{{height:2px;background:{ink};margin:0;}}
QSlider::sub-page:horizontal{{background:{ink};}}
QSlider::handle:horizontal{{background:{t.patch_bg};border:1px solid {ink};
  width:0.5em;margin:-0.45em 0;border-radius:0;}}
QSlider::handle:horizontal:hover{{background:{t.focus};}}
QSlider:disabled{{opacity:0.5;}}
QToolButton{{background:transparent;color:{ink};border:1px solid transparent;
  border-radius:0;padding:0.25em 0.4em;}}
QToolButton:hover{{background:{t.patch_bg};color:{t.patch_ink};}}
QToolButton:focus{{border:2px solid {t.focus};}}
QToolButton#text_size_button{{border:1px solid {ink};padding:0.1em 0.5em;}}
QToolButton::menu-indicator{{image:none;width:0;}}
QComboBox{{background:{inset};color:{ink};border:1px solid {ink};border-radius:0;
  padding:0.3em 0.6em;min-height:1.3em;}}
QComboBox:focus,QLineEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus{{
  border:2px solid {t.focus};}}
QComboBox:disabled,QLineEdit:disabled,QSpinBox:disabled,QDoubleSpinBox:disabled{{
  background:{t.off_bg};color:{t.off_ink};border:1px solid {t.hair};}}
QSpinBox::up-button,QDoubleSpinBox::up-button{{subcontrol-origin:border;
  subcontrol-position:top right;width:1.3em;border-left:1px solid {ink};
  border-bottom:1px solid {t.hair};}}
QSpinBox::down-button,QDoubleSpinBox::down-button{{subcontrol-origin:border;
  subcontrol-position:bottom right;width:1.3em;border-left:1px solid {ink};}}
QComboBox::drop-down{{border:none;width:1.8em;}}
QComboBox QAbstractItemView{{background:{inset};color:{ink};border:1px solid {ink};
  selection-background-color:{t.patch_bg};selection-color:{t.patch_ink};outline:none;}}
QLineEdit,QSpinBox,QDoubleSpinBox,QPlainTextEdit,QTextEdit{{background:{inset};color:{ink};
  border:1px solid {ink};border-radius:0;padding:0.25em 0.45em;
  selection-background-color:{t.patch_bg};selection-color:{t.patch_ink};}}
QScrollBar:vertical{{background:transparent;width:0.8em;margin:0;}}
QScrollBar::handle:vertical{{background:{handle};min-height:2.2em;border-radius:0;
  margin:0.15em;}}
QScrollBar:horizontal{{background:transparent;height:0.8em;margin:0;}}
QScrollBar::handle:horizontal{{background:{handle};min-width:2.2em;border-radius:0;
  margin:0.15em;}}
QScrollBar::add-line,QScrollBar::sub-line{{width:0;height:0;border:none;background:none;}}
QScrollBar::add-page,QScrollBar::sub-page{{background:none;}}
QMenu{{background:{inset};color:{ink};border:1px solid {ink};padding:0.2em 0;}}
QMenu::item{{padding:0.35em 1.6em;}}
QMenu::item:selected{{background:{t.patch_bg};color:{t.patch_ink};}}
QMenu::separator{{height:1px;background:{t.hair};margin:0.3em 0.5em;}}
QTabWidget::pane{{border:none;border-top:1px solid {ink};}}
QTabBar::tab{{background:transparent;color:{t.ink2};padding:0.5em 1.1em;
  border:1px solid transparent;border-bottom:none;}}
QTabBar::tab:selected{{background:{t.patch_bg};color:{t.patch_ink};}}
QTabBar::tab:hover:!selected{{color:{ink};border-color:{t.hair};}}
QGroupBox{{border:1px solid {t.hair};border-radius:0;margin-top:1.1em;padding-top:0.6em;}}
QGroupBox::title{{subcontrol-origin:margin;left:0.6em;padding:0 0.3em;color:{t.ink2};}}
QProgressBar{{background:{inset};border:1px solid {ink};border-radius:0;
  text-align:center;color:{ink};min-height:1.1em;}}
QProgressBar::chunk{{background:{ink};}}
"""


# --------------------------------------------------------------------- widgets


class ControlStrip(QWidget):
    """The process-colour patch row of the proof: pure decoration, no behaviour."""

    def __init__(self, parent: QWidget | None = None, height: int = 12) -> None:
        super().__init__(parent)
        self.setFixedHeight(height)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        p = QPainter(self)
        w, h = self.width(), self.height()
        n = len(STRIP)
        for i, hexcolor in enumerate(STRIP):
            x0, x1 = round(i * w / n), round((i + 1) * w / n)
            p.fillRect(x0, 0, x1 - x0, h, QColor(hexcolor))
        p.setPen(QPen(QColor(tokens().rule), 1))
        p.drawRect(0, 0, w - 1, h - 1)
        p.end()


class FigureFrame(QWidget):
    """A printed figure: its own paper, a 1 px rule and two registration targets.

    The paper stays light in the dark scheme too (a print lying on the table), so
    the drawings, which assume a light ground, read the same everywhere.
    """

    PAPER = "#f6f6f4"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = None
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def setAlignment(self, _alignment: object) -> None:  # noqa: N802
        """Compatibility with ``QLabel`` callers; the figure is always centred."""

    def setPixmap(self, pixmap: object) -> None:  # noqa: N802
        """Compatibility with ``QLabel`` callers."""
        self.set_pixmap(pixmap)

    def set_pixmap(self, pixmap: object) -> None:
        """Show ``pixmap`` (a ``QPixmap`` with its device pixel ratio set)."""
        self._pixmap = pixmap
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        if self._pixmap is None or self._pixmap.isNull():
            return QSize(200, 140)
        r = self._pixmap.devicePixelRatio() or 1.0
        return QSize(int(self._pixmap.width() / r) + 24, int(self._pixmap.height() / r) + 24)

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = self.rect().adjusted(0, 0, -1, -1)
        p.fillRect(rect, QColor(self.PAPER))
        if self._pixmap is not None and not self._pixmap.isNull():
            r = self._pixmap.devicePixelRatio() or 1.0
            w, h = self._pixmap.width() / r, self._pixmap.height() / r
            scale = min(1.0, (rect.width() - 24) / w, (rect.height() - 24) / h)
            tw, th = w * scale, h * scale
            p.drawPixmap(QRectF((rect.width() - tw) / 2, (rect.height() - th) / 2, tw, th),
                         self._pixmap, QRectF(self._pixmap.rect()))
        ink = QColor(KEY)
        p.setPen(QPen(ink, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(rect)
        draw_registration(p, rect.right() - 13, rect.top() + 13, 5, ink)
        draw_registration(p, rect.left() + 13, rect.bottom() - 13, 5, ink)
        p.end()


class Rule(QWidget):
    """A horizontal rule in ink (``thickness`` px)."""

    def __init__(
        self, thickness: int = 1, parent: QWidget | None = None, hair: bool = False
    ) -> None:
        super().__init__(parent)
        self._hair = hair
        self.setFixedHeight(thickness)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        t = tokens()
        p = QPainter(self)
        color = QColor(t.ink)
        if self._hair:
            color.setAlpha(70)
        p.fillRect(self.rect(), color)
        p.end()


class CmykRule(QWidget):
    """Four short bars C M Y K, the underline of a wordmark or a heading."""

    def __init__(self, width: int = 96, height: int = 4, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        p = QPainter(self)
        w, h = self.width(), self.height()
        for i, hexcolor in enumerate((CYAN, MAGENTA, YELLOW, tokens().ink)):
            p.fillRect(round(i * w / 4), 0, round((i + 1) * w / 4) - round(i * w / 4), h,
                       QColor(hexcolor))
        p.end()


def draw_registration(p: QPainter, cx: float, cy: float, r: float, color: QColor) -> None:
    """A registration target: circle with a cross, drawn at ``(cx, cy)``."""
    p.save()
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(color, 1.2))
    p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
    p.drawLine(int(cx - r * 1.5), int(cy), int(cx + r * 1.5), int(cy))
    p.drawLine(int(cx), int(cy - r * 1.5), int(cx), int(cy + r * 1.5))
    p.restore()


def slug_width(text: str, font: QFont) -> float:
    """Advance of ``text`` in a slug font (used to decide what fits)."""
    return QFontMetricsF(font).horizontalAdvance(text.upper())


def svg_pixmap(path: str, size: int, color: str, dpr: float = 1.0):
    """Render a line icon (strokes in ``currentColor``) at ``size`` logical px."""
    from qtpy.QtCore import QByteArray
    from qtpy.QtGui import QImage, QPixmap
    from qtpy.QtSvg import QSvgRenderer

    with open(path, encoding="utf-8") as fh:
        data = fh.read().replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(data.encode("utf-8")))
    img = QImage(int(size * dpr), int(size * dpr), QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    renderer.render(p)
    p.end()
    pix = QPixmap.fromImage(img)
    pix.setDevicePixelRatio(dpr)
    return pix


def tab_pixmap(key: str, size: int = 28):
    """The line icon of a main tab (``guide``, ``calibration`` ...) in the ink colour."""
    found = config.get_data_path(f"theme/guide/tab_{key}.svg")
    if not isinstance(found, str):
        return None
    app = QApplication.instance()
    dpr = app.devicePixelRatio() if app is not None else 1.0
    return svg_pixmap(found, size, tokens().ink, max(1.0, dpr))


def splash_base(width: int = 560, height: int = 300, dpr: float = 1.0):
    """The start-up splash: a small proof sheet (no version, no message)."""
    from qtpy.QtGui import QPixmap

    from DisplayCAL.ui.header_banner import brand_icon_pixmap

    t = LIGHT  # a splash is a printed card, light in every scheme
    pix = QPixmap(round(width * dpr), round(height * dpr))
    pix.fill(QColor(t.sheet))
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.scale(dpr, dpr)
    ink = QColor(t.ink)
    pad = 28
    p.setPen(QPen(ink, 1))
    p.drawRect(0, 0, width - 1, height - 1)
    p.setFont(mono_font(8.5))
    p.setPen(QColor(t.ink2))
    p.drawText(pad, 12, 260, 18, int(Qt.AlignLeft | Qt.AlignVCenter), "DISPLAYCAL-CG")
    p.fillRect(pad, 31, width - 2 * pad, 1, ink)
    icon = brand_icon_pixmap(128)
    if not icon.isNull():
        p.drawPixmap(QRectF(pad, 58, 88, 88), icon, QRectF(icon.rect()))
    title = sans_font(34, 800)
    p.setFont(title)
    p.setPen(ink)
    fm = p.fontMetrics()
    word = "DisplayCAL-CG"
    x = pad + 88 + 18
    p.drawText(x, 58 + 52, word)
    ww = fm.horizontalAdvance(word)
    for i, hexcolor in enumerate((CYAN, MAGENTA, YELLOW, KEY)):
        x0, x1 = x + round(i * ww / 4), x + round((i + 1) * ww / 4)
        p.fillRect(x0, 58 + 62, x1 - x0, 4, QColor(hexcolor))
    sh = height - 34
    n = len(STRIP)
    for i, hexcolor in enumerate(STRIP):
        x0 = pad + round(i * (width - 2 * pad) / n)
        x1 = pad + round((i + 1) * (width - 2 * pad) / n)
        p.fillRect(x0, sh, x1 - x0, 14, QColor(hexcolor))
    p.setPen(QPen(ink, 1))
    p.setBrush(Qt.NoBrush)
    p.drawRect(pad, sh, width - 2 * pad - 1, 13)
    p.end()
    pix.setDevicePixelRatio(dpr)
    return pix


class BlocksBar(QWidget):
    """The measurement plan drawn as the proof's control strip: one patch per block.

    Static and decorative-informative: it is shown in the guide, never over the
    patch window. Cell widths are proportional to the patches in each block.
    """

    TINTS = ("#6fc7ec", "#ea7fb3", "#ffea7a", "#c7c7c5")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._counts: list[int] = []
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAccessibleName("")

    def set_plan(self, total: int, blocks: int, per_block: int) -> None:
        """Describe the plan: ``blocks`` blocks of about ``per_block`` patches each."""
        if total <= 0:
            counts: list[int] = []
        elif blocks > 1 and per_block > 0:
            counts = [per_block] * blocks
        else:
            counts = [total]
        self._counts = counts
        self.setVisible(bool(counts))
        self.update()
        self.updateGeometry()

    def _font(self) -> QFont:
        return mono_font(max(8.0, self.font().pointSizeF() * 0.78), bold=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        fm = QFontMetricsF(self._font())
        return QSize(200, int(14 + fm.height() + 8))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        if not self._counts:
            return
        t = tokens()
        p = QPainter(self)
        ink = QColor(t.ink)
        w = self.width() - 1
        cell_h = 14
        total = sum(self._counts)
        gap = 2 if len(self._counts) <= 60 else 0
        p.setFont(self._font())
        fm = QFontMetricsF(self._font())
        x = 0.0
        for i, n in enumerate(self._counts):
            span = (w - gap * (len(self._counts) - 1)) * n / total
            rect = QRectF(x, 0, max(1.0, span), cell_h)
            p.fillRect(rect, QColor(self.TINTS[i % len(self.TINTS)]))
            p.setPen(QPen(ink, 1))
            p.setBrush(Qt.NoBrush)
            p.drawRect(rect.adjusted(0, 0, -1, -1))
            label = str(i + 1)
            if len(self._counts) <= 40 and fm.horizontalAdvance(label) + 4 < rect.width():
                p.setPen(QColor(t.ink2))
                p.drawText(QRectF(rect.left(), cell_h + 2, rect.width(), fm.height()),
                           int(Qt.AlignHCenter | Qt.AlignTop), label)
            x += span + gap
        p.end()
