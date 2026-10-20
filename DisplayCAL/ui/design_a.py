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
    dark=False, booth="#e9e8e4", sheet="#f7f6f3", inset="#fbfbf9", ink="#1d1f24",
    ink2="#5b5f68", hair="rgba(29,31,36,0.16)", rule="#1d1f24", ok="#0b7a45",
    warn="#8a5b00", bad="#b3121f", focus="#2d5bd8", patch_bg="#2c2f36",
    patch_ink="#f7f6f3", off_bg="#ecebe7", off_ink="#7d818a",
)  # fmt: skip
DARK = Tokens(
    dark=True, booth="#17181b", sheet="#1c1d20", inset="#26282d", ink="#eceef2",
    ink2="#a3a8b2", hair="rgba(236,238,242,0.16)", rule="#eceef2", ok="#4cc38a",
    warn="#f0b44c", bad="#ff6b6b", focus="#8fa6ff", patch_bg="#3b3e47",
    patch_ink="#f2f3f6", off_bg="#2a2c31", off_ink="#8d919b",
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
    light = not t.dark
    satin = (
        "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #ffffff,stop:1 #f1f0ec)" if light
        else "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #2d2f35,stop:1 #25272c)"
    )
    satin_hover = (
        "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #ffffff,stop:1 #ebeae5)" if light
        else "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #34363d,stop:1 #2b2d33)"
    )
    satin_down = (
        "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #e6e5e0,stop:1 #efeeea)" if light
        else "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #202226,stop:1 #282a2f)"
    )
    edge = "rgba(29,31,36,0.34)" if light else "rgba(236,238,242,0.36)"
    graphite = (
        "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #3b3e47,stop:0.5 #2c2f36,stop:1 #24262c)" if light
        else "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #4a4d57,stop:1 #3b3e47)"
    )
    graphite_hover = (
        "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #484c56,stop:0.5 #383b43,stop:1 #2e3037)" if light
        else "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #565a65,stop:1 #464a54)"
    )
    graphite_down = "#22242a" if light else "#33363e"
    graphite_edge = "#1c1e23" if light else "rgba(236,238,242,0.30)"
    tick = config.get_data_path(
        "theme/guide/check_light.svg"
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
QPushButton{{background:{satin};color:{ink};border:1px solid {t.hair};border-radius:11px;
  padding:0.45em 1.2em;min-height:1.2em;}}
QPushButton:hover{{background:{satin_hover};border-color:{edge};}}
QPushButton:pressed{{background:{satin_down};border-color:{edge};padding-top:0.5em;padding-bottom:0.4em;}}
QPushButton:focus{{border:2px solid {t.focus};padding:0.4em 1.15em;}}
QPushButton:disabled{{background:{t.off_bg};color:{t.off_ink};border:1px solid {t.hair};}}
QPushButton:flat{{background:transparent;border:none;color:{ink};
  text-decoration:underline;padding:0.3em 0.4em;}}
QPushButton:flat:hover{{background:transparent;color:{t.focus};}}
QPushButton[primary="true"]{{background:{graphite};color:{t.patch_ink};
  border:1px solid {graphite_edge};border-radius:11px;padding:0.6em 2em;font-weight:700;}}
QPushButton[primary="true"]:hover{{background:{graphite_hover};}}
QPushButton[primary="true"]:pressed{{background:{graphite_down};padding-top:0.65em;padding-bottom:0.55em;}}
QPushButton[primary="true"]:focus{{border:2px solid {t.focus};padding:0.55em 1.95em;}}
QPushButton[primary="true"]:disabled{{background:{t.off_bg};color:{t.off_ink};
  border:1px solid {t.hair};}}
QComboBox{{background:{satin};color:{ink};border:1px solid {t.hair};
  border-radius:11px;padding:0.4em 0.85em;min-height:1.35em;}}
QComboBox:hover{{border-color:{edge};background:{satin_hover};}}
QComboBox:on{{border-color:{t.focus};}}
QRadioButton::indicator{{width:0.95em;height:0.95em;border-radius:0.55em;
  border:1.5px solid {t.ink2};background:{inset};}}
QRadioButton::indicator:checked{{border:1.5px solid {graphite_edge};
  background:qradialgradient(cx:.5,cy:.5,radius:.5,fx:.5,fy:.5,
  stop:0 {t.patch_bg},stop:.5 {t.patch_bg},stop:.58 {inset},stop:1 {inset});}}
QRadioButton::indicator:disabled,QCheckBox::indicator:disabled{{border-color:{t.off_ink};}}
QCheckBox::indicator{{width:0.95em;height:0.95em;border-radius:5px;
  border:1.5px solid {t.ink2};background:{inset};}}
QCheckBox::indicator:checked{{border:1.5px solid {graphite_edge};background:{t.patch_bg};{check_image}}}
QSlider::groove:horizontal{{height:4px;background:{t.hair};border-radius:2px;margin:0;}}
QSlider::sub-page:horizontal{{background:{t.patch_bg};border-radius:2px;}}
QSlider::handle:horizontal{{background:{satin};border:1px solid {edge};
  width:1.1em;height:1.1em;margin:-0.5em 0;border-radius:0.6em;}}
QSlider::handle:horizontal:hover{{border-color:{t.focus};}}
QToolButton{{background:transparent;color:{ink};border:1px solid transparent;
  border-radius:8px;padding:0.25em 0.4em;}}
QToolButton:hover{{background:{satin_hover};border-color:{t.hair};}}
QToolButton:pressed{{background:{satin_down};}}
QToolButton:focus{{border:2px solid {t.focus};}}
QToolButton#text_size_button{{border:1px solid {t.hair};border-radius:13px;padding:0.35em 0.75em;background:{satin};}}
QToolButton::menu-indicator{{image:none;width:0;}}
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
QLineEdit,QSpinBox,QDoubleSpinBox,QPlainTextEdit,QTextEdit{{background:{satin};color:{ink};
  border:1px solid {t.hair};border-radius:8px;padding:0.25em 0.5em;
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


def icon_pixmap(name: str, size: int = 24, color: str | None = None):
    """A small line icon (``theme/guide/ico_<name>.svg``) in the ink colour."""
    found = config.get_data_path(f"theme/guide/ico_{name}.svg")
    if not isinstance(found, str):
        return None
    app = QApplication.instance()
    dpr = app.devicePixelRatio() if app is not None else 1.0
    return svg_pixmap(found, size, color or tokens().ink, max(1.0, dpr))


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
            rect = QRectF(x, 3, max(1.0, span), 8)
            shade = QColor(ink)
            shade.setAlpha(70 if i % 2 else 120)
            p.setPen(Qt.NoPen)
            p.setBrush(shade)
            p.drawRoundedRect(rect, 3, 3)
            label = str(i + 1)
            if len(self._counts) <= 40 and fm.horizontalAdvance(label) + 4 < rect.width():
                p.setPen(QColor(t.ink2))
                p.drawText(QRectF(rect.left(), 13, rect.width(), fm.height()),
                           int(Qt.AlignHCenter | Qt.AlignTop), label)
            x += span + gap
        p.end()


class Booth(QWidget):
    """The viewing booth: a neutral grey surround, lit from above, with a vignette.

    The sheet lies on it; crop marks stand in the margin at the sheet's corners.
    """

    MARGIN = 26

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        from qtpy.QtGui import QRadialGradient

        t = tokens()
        p = QPainter(self)
        w, h = self.width(), self.height()
        lit = QColor(_mix(t.booth, "#ffffff", 0.22) if not t.dark else _mix(t.booth, "#ffffff", 0.06))
        g = QRadialGradient(w * 0.5, h * 0.18, max(w, h) * 0.95)
        g.setColorAt(0.0, lit)
        g.setColorAt(1.0, QColor(t.booth))
        p.fillRect(self.rect(), g)
        m = self.MARGIN
        paint_sheet_shadow(p, QRectF(self.rect().adjusted(m, m, -m, -m)), t.dark)
        p.end()


class Sheet(QWidget):
    """The paper: soft contact shadow, a hairline edge and a faint sheen of the booth light."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sheen = _Sheen(self)

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        self._sheen.setGeometry(self.rect())
        self._sheen.raise_()
        super().resizeEvent(event)

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        t = tokens()
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(t.sheet))
        edge = QColor(t.ink)
        edge.setAlpha(60)
        p.setPen(QPen(edge, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()


class _Sheen(QWidget):
    """A broad, very soft diagonal highlight over the paper (never over patches)."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        from qtpy.QtGui import QLinearGradient

        w, h = self.width(), self.height()
        p = QPainter(self)
        g = QLinearGradient(0, 0, w, h * 0.7)
        clear, hi = QColor(255, 255, 255, 0), QColor(255, 255, 255, 22 if not tokens().dark else 9)
        g.setColorAt(0.0, clear)
        g.setColorAt(0.36, clear)
        g.setColorAt(0.46, hi)
        g.setColorAt(0.56, clear)
        g.setColorAt(1.0, clear)
        p.fillRect(self.rect(), g)
        p.end()


def paint_sheet_shadow(p: QPainter, rect: QRectF, dark: bool) -> None:
    """Soft shadow of a sheet lying on the booth floor (layered, offset downwards)."""
    layers = 14
    for i in range(layers, 0, -1):
        grow = i * 1.6
        a = int((9 if not dark else 16) * (1 - i / (layers + 1)) ** 1.6)
        c = QColor(10, 12, 16, a)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(rect.adjusted(-grow, -grow * 0.2, grow, grow * 1.5 + 6), 2, 2)


class ProductImage(QWidget):
    """The product image: the monitor with its spectral ribbon, a transparent asset.

    ``theme/guide/monitor_spectral.png`` (separate artwork, no interface in it), shown whole
    with its alpha, smooth-scaled, aspect kept. It is purely decorative and is never shown
    while a measurement runs (the guide hides it).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from qtpy.QtGui import QPixmap

        found = config.get_data_path("theme/guide/monitor_spectral.png")
        self._pix = QPixmap(found) if isinstance(found, str) else QPixmap()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.setMinimumHeight(120)

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        if self._pix.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        scale = min(self.width() / self._pix.width(), self.height() / self._pix.height())
        w, h = self._pix.width() * scale, self._pix.height() * scale
        p.drawPixmap(QRectF(self.width() - w, 0, w, h), self._pix, QRectF(self._pix.rect()))
        p.end()


class HeroPlate(QWidget):
    """The picture: a rendered monitor with the probe on the measuring square.

    A real image asset (``theme/guide/hero_monitor.jpg``), shown whole in a plate with a
    hairline rule and two registration targets. It carries the depth of the screen:
    glass, reflection, the booth floor.
    """

    def __init__(self, parent: QWidget | None = None, aspect: float | None = None, focus: float = 0.52) -> None:
        super().__init__(parent)
        from qtpy.QtGui import QPixmap

        self._aspect, self._focus = aspect, focus
        found = config.get_data_path("theme/guide/hero_monitor.jpg")
        self._pix = QPixmap(found) if isinstance(found, str) else QPixmap()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return not self._pix.isNull()

    def _ratio(self) -> float:
        if self._aspect:
            return self._aspect
        return self._pix.width() / self._pix.height() if not self._pix.isNull() else 2.0

    def heightForWidth(self, w: int) -> int:  # noqa: N802
        return int(w / self._ratio())

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(600, self.heightForWidth(600))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(160, self.heightForWidth(160))

    def paintEvent(self, _event: object) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        from qtpy.QtGui import QPainterPath

        r = self.rect().adjusted(0, 0, -1, -1)
        if not self._pix.isNull():
            # cover: crop the picture to the plate's shape around the monitor
            pw, ph = self._pix.width(), self._pix.height()
            want = self.width() / max(1, self.height())
            sw = min(pw, ph * want)
            sh = sw / want
            sx = max(0.0, min(pw - sw, pw * self._focus - sw / 2))
            p.drawPixmap(QRectF(self.rect()), self._pix, QRectF(sx, (ph - sh) / 2, sw, sh))
            # the booth floor melts into the page: feather every edge into the sheet colour
            from qtpy.QtGui import QLinearGradient

            sheet = QColor(tokens().sheet)
            clear = QColor(sheet)
            clear.setAlpha(0)
            w, h = self.width(), self.height()
            f = int(min(w, h) * 0.16)
            for (x0, y0, x1, y1, rx, ry, rw, rh) in (
                (0, 0, f, 0, 0, 0, f, h), (w, 0, w - f, 0, w - f, 0, f, h),
                (0, 0, 0, f, 0, 0, w, f), (0, h, 0, h - f, 0, h - f, w, f),
            ):
                g = QLinearGradient(x0, y0, x1, y1)
                g.setColorAt(0, sheet)
                g.setColorAt(1, clear)
                p.fillRect(rx, ry, rw, rh, g)
        p.end()
