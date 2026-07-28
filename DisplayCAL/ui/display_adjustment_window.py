"""Native Qt interactive display-adjustment window (Stage 5c-ii).

Qt successor to ``wx_display_adjustment_frame.py::DisplayAdjustmentFrame``, the
window shown during ``worker.calibrate`` that walks the user through adjusting
the monitor (brightness, RGB gain / offset, black level) to hit the calibration
targets. ``dispcal`` streams interactive text while it measures; the window turns
each reading into gauge positions, target / current read-outs and an
in-tolerance check mark, and lets the user pick which adjustment to run.

The toolkit-neutral core of that -- the regex extraction plus the gauge /
tolerance maths -- was lifted out in sub-slice 5c-i as
:func:`DisplayCAL.ui.display_adjustment.parse_adjustment`. This module is the
widget layer on top: it builds the five adjustment pages (black level / white
point / white level / black point / check-all) with their gauges and labels,
feeds each ``dispcal`` chunk through :func:`parse_adjustment`, and renders the
returned :class:`AdjustmentReadings`. As the other tool ports did, the *fancy*
presentation is dropped: the animated indicator becomes a static dot, the
gradient ``PyGauge`` becomes a plain ``QProgressBar``, and the looping sound
effect becomes a single best-effort beep.

The window is toolkit-facing but worker-agnostic: instead of calling
``worker.safe_send`` directly (as the wx frame does), it emits the key to send on
:attr:`DisplayAdjustmentWindow.send_requested`. Wiring that to the running
interactive ``dispcal`` (with this window as the worker's ``progress_wnd``) is
sub-slice 5c-iii.

See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 5, sub-slice 5c).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QIcon, QPainter, QPixmap
from qtpy.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import localization as lang
from DisplayCAL.config import get_data_path, getcfg, writecfg
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui.assets import get_theme_pixmap
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.display_adjustment import (
    AdjustmentContext,
    AdjustmentReadings,
    parse_adjustment,
)
from DisplayCAL.util_str import wrap

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent, QKeyEvent
    from qtpy.QtWidgets import QWidget as QtWidget

# Colours the wx frame uses verbatim.
BGCOLOUR = "#333333"
BORDERCOLOUR = "#222222"
FGCOLOUR = "#999999"
GREEN = "#33cc00"

# wx sizes gauges and their markers at a fixed 200 (* dpiscale) px wide
# instead of letting them stretch with the window
# (``wx_display_adjustment_frame.py:681``, ``:713``).
_GAUGE_WIDTH = 200

# Flat dark button chrome matching wx's hand-painted ``FlatShadedButton``
# (``DisplayCAL/wx_windows.py``, ``OnPaint``): borderless, rounded, #222222
# fill with #999999 text, lightened on hover/press. Scoped by object name so
# it doesn't bleed onto ``_SelectorButton``'s own (differently styled)
# ``QToolButton``s.
_ACTION_BUTTON_STYLESHEET = """
QPushButton#adjustmentBtn, QPushButton#calibrationBtn, QToolButton#soundButton {
    color: #999999;
    background-color: #222222;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
}
QPushButton#adjustmentBtn:hover, QPushButton#calibrationBtn:hover, QToolButton#soundButton:hover {
    background-color: #3d3d3d;
    color: #b3b3b3;
}
QPushButton#adjustmentBtn:pressed, QPushButton#calibrationBtn:pressed, QToolButton#soundButton:pressed {
    background-color: #1a1a1a;
}
QPushButton#adjustmentBtn:disabled, QPushButton#calibrationBtn:disabled {
    color: #5c5c5c;
    background-color: #1a1a1a;
}
QToolButton#soundButton {
    padding: 8px;
}
"""

# Gauge bar gradients (dark -> bright shade), per channel, from
# ``DisplayAdjustmentPanel.add_gauge``'s ``gaugecolors``. The dim set is used
# on the "black_level" and "rgb_offset" (CRT black-point) pages, the bright
# set everywhere else. "L" is a grey/white gradient, never blue.
_GAUGE_COLOURS_DIM = {
    "R": ("#660000", "#cc0000"),
    "G": ("#006600", "#00cc00"),
    "B": ("#000066", "#0000cc"),
    "L": ("#666666", "#cccccc"),
}
_GAUGE_COLOURS_BRIGHT = {
    "R": ("#990000", "#ff0000"),
    "G": ("#009900", "#00ff00"),
    "B": ("#000099", "#0000ff"),
    "L": ("#999999", "#ffffff"),
}

# Page definitions, in the wx tab order. Each entry is
# ``(ctrltype, title-key, argyll key num)``; the title is joined from one or two
# localized strings, matching the wx ``DisplayAdjustmentFrame`` page titles.
_PAGES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("black_level", ("calibration.black_luminance",), "1"),
    ("rgb_gain", ("whitepoint", "calibration.luminance"), "2"),
    ("luminance", ("calibration.luminance",), "3"),
    ("rgb_offset", ("black_point", "calibration.black_luminance"), "4"),
    ("check_all", ("calibration.check_all",), "5"),
)

# 72x72 selector icon per page, keyed by ctrltype, with the CRT overrides the wx
# ``_assign_image_list`` applies (black luminance shows the luminance icon,
# luminance shows the contrast icon).
_SELECTOR_ICONS = {
    "black_level": {False: "black_luminance", True: "luminance"},
    "rgb_gain": {False: "white_point", True: "white_point"},
    "luminance": {False: "luminance", True: "contrast"},
    "rgb_offset": {False: "black_point", True: "black_point"},
    "check_all": {False: "check_all", True: "check_all"},
}

# 16x16 luminance-gauge icon per (normalized) ctrltype, with the CRT overrides
# from the wx ``_setup`` ``bitmaps`` map.
_LUM_ICONS = {
    "black_level": {False: "black_level", True: "luminance"},
    "luminance": {False: "luminance", True: "contrast"},
}


def _pixmap_icon(size: int, name: str) -> QIcon:
    """Return a themed pixmap wrapped as a ``QIcon`` (possibly empty)."""
    return QIcon(get_theme_pixmap(size, name))


#: Gap baked into each action-button icon's own pixmap, right after its
#: opaque content, so the rendered icon-to-text gap matches wx's explicit
#: 10px ``constant`` between bitmap and label
#: (``FlatShadedButton.DoGetBestSize``, ``wx_windows.py:3989``). Qt's own
#: built-in icon/text spacing on ``QPushButton`` is only a couple of pixels
#: and isn't exposed as a stylesheet property, so the gap has to live in the
#: icon itself.
_BUTTON_ICON_TEXT_GAP = 8


def _button_icon(name: str, height: int = 10) -> tuple[QIcon, QSize]:
    """A ``play``/``pause``/``skip`` icon plus the ``QSize`` to display it at.

    These only exist as ``10x10`` assets (``skip.png`` is actually a 22x10
    ">>|" glyph -- not square), too small to read clearly next to the 16px
    sound-button icon in the same row. Loads the ``@2x`` (double-resolution)
    variant when available so downscaling to ``height`` stays crisp, the same
    trick :func:`~DisplayCAL.ui.assets.get_header_icon_pixmap` uses for retina
    assets elsewhere in the Qt port, and derives the width from the source's
    own aspect ratio rather than forcing a square box (which would squash
    ``skip``), mirroring wx's ``FlatShadedButton.DoGetBestSize`` pinning only
    the bitmap's height and keeping its native width
    (``wx_windows.py:3994-3998``).

    The returned pixmap has :data:`_BUTTON_ICON_TEXT_GAP` of trailing
    transparent padding baked in (and the returned size includes it), so the
    button's built-in icon/text gap doesn't need to be relied on.
    """
    path = get_data_path(f"theme/icons/10x10/{name}@2x.png") or get_data_path(
        f"theme/icons/10x10/{name}.png"
    )
    pixmap = QPixmap(path) if path else QPixmap()
    if pixmap.isNull():
        return QIcon(), QSize(height, height)
    # Qt auto-detects the "@2x" filename suffix and sets devicePixelRatio=2,
    # which makes drawPixmap() render it at HALF the size computed below
    # (size() returns raw buffer pixels, but painting honours the ratio).
    # Reset it since we're doing our own manual height-based scaling.
    pixmap.setDevicePixelRatio(1.0)
    width = round(pixmap.width() * height / pixmap.height())
    scaled = pixmap.scaled(
        width,
        height,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    padded_width = width + _BUTTON_ICON_TEXT_GAP
    padded = QPixmap(padded_width, height)
    padded.fill(Qt.GlobalColor.transparent)
    painter = QPainter(padded)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return QIcon(padded), QSize(padded_width, height)


def _tab_state_pixmap(name: str) -> QPixmap:
    """Load one of the page-selector's droplet-shaped tab-state PNGs.

    ``theme/tab_selected.png`` / ``theme/tab_hilite.png`` live directly under
    ``theme/`` (not ``theme/icons/<size>x<size>/``), so this bypasses
    :func:`~DisplayCAL.ui.assets.get_theme_pixmap`.
    """
    path = get_data_path(f"theme/{name}.png")
    return QPixmap(path) if path else QPixmap()


class _SelectorButton(QToolButton):
    """A page-selector button with wx's droplet-shaped checked/hover
    background instead of Qt's native checked-button chrome.

    Port of ``DisplayAdjustmentImageContainer.OnPaint``, which draws the
    ``tab_selected`` state image behind the currently-selected tab's icon,
    and ``tab_hilite`` behind a hovered one.
    """

    _selected_pixmap: QPixmap | None = None
    _hilite_pixmap: QPixmap | None = None

    def __init__(self) -> None:
        super().__init__()
        if _SelectorButton._selected_pixmap is None:
            _SelectorButton._selected_pixmap = _tab_state_pixmap("tab_selected")
            _SelectorButton._hilite_pixmap = _tab_state_pixmap("tab_hilite")
        if not self._selected_pixmap.isNull():
            self.setFixedSize(self._selected_pixmap.size())
        self.setStyleSheet(
            "QToolButton, QToolButton:checked, QToolButton:hover {"
            " border: none; background: transparent; }"
        )

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        pixmap = None
        if self.isChecked():
            pixmap = self._selected_pixmap
        elif self.underMouse():
            pixmap = self._hilite_pixmap
        if pixmap is not None and not pixmap.isNull():
            painter = QPainter(self)
            painter.drawPixmap(self.rect(), pixmap)
            painter.end()
        super().paintEvent(event)


def _gauge_stylesheet(name: str, ctrltype: str) -> str:
    """QSS for gauge ``name``'s channel-coloured bar, matching wx's gradient.

    Port of ``DisplayAdjustmentPanel.add_gauge``'s ``gaugecolors``: each
    channel gets its own dark -> bright gradient (R red, G green, B blue, L
    grey/white -- never blue), dimmed on the CRT black-point pages.
    """
    colours = (
        _GAUGE_COLOURS_DIM
        if ctrltype in ("black_level", "rgb_offset")
        else _GAUGE_COLOURS_BRIGHT
    )
    dark, bright = colours[name]
    return (
        f"QProgressBar {{ background-color: {BORDERCOLOUR};"
        f" border: 1px solid {BORDERCOLOUR}; }}"
        "QProgressBar::chunk { background-color:"
        f" qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {dark}, stop:1 {bright}); }}"
    )


def _set_pixmap(label: QLabel, size: int, name: str) -> None:
    """Set ``label``'s pixmap to the themed asset ``name`` if it exists."""
    pixmap = get_theme_pixmap(size, name)
    if not pixmap.isNull():
        label.setPixmap(pixmap)


def _marker_label(direction: str) -> QLabel:
    """A gauge's target-value tick mark (``theme/marker_top``/``_btm``).

    The asset is a 200x10 PNG that is transparent except for a short tick at
    its horizontal centre; port of ``DisplayAdjustmentPanel.add_marker``,
    which places one above and one below every gauge to mark the target
    (50%) position. wx sizes both the marker and the gauge it belongs to at a
    fixed ``200 * scale`` px wide (``add_gauge``/``add_marker``,
    ``wx_display_adjustment_frame.py:681``, ``:713``) rather than letting them
    stretch with the window, so the tick renders at its authored width;
    letting our grid column stretch to fill the page (as it did before)
    doubled the asset's width along with everything else in that column.
    """
    label = QLabel()
    label.setFixedSize(_GAUGE_WIDTH, 10)
    label.setScaledContents(True)
    path = get_data_path(f"theme/marker_{direction}.png")
    if path:
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            label.setPixmap(pixmap)
    return label


def _reserve_metric_label_size(label: QLabel) -> None:
    """Lock in room for the widest/tallest metric read-out up front.

    Every metric label (``luminance`` / ``black_level`` / ``rgb`` /
    ``white_point`` / ``black_point``) starts as one blank line, then later
    grows to one or two real lines (a target/initial line plus a current
    line) once readings arrive -- after the window is already shown and Qt's
    top-level layout no longer auto-grows the window to fit. Left alone, that
    second line gets clipped at the bottom of the window instead of making it
    taller. Port of the wx frame's ``add_txt``, which sizes a worst-case
    two-line placeholder with ``Fit()`` and locks it in with ``SetMinSize()``
    before any real reading has arrived.
    """
    words = (lang.getstr("initial"), lang.getstr("current"), lang.getstr("target"))
    longest = max(words, key=len)
    placeholder = f"{longest} x 0.0000 y 0.0000 VDT 0000K 0.0 ΔE*00\nX"
    original = label.text()
    label.setText(placeholder)
    label.setMinimumSize(label.sizeHint())
    label.setText(original)


class _AdjustmentPage(QWidget):
    """One adjustment page: a title, a hint, and its gauges + read-out labels.

    Args:
        ctrltype (str): The page's control type -- ``black_level``, ``rgb_gain``,
            ``luminance``, ``rgb_offset`` or ``check_all``.
        title (str): The already-localized page title.
    """

    def __init__(self, ctrltype: str, title: str) -> None:
        super().__init__()
        self.ctrltype = ctrltype
        self.context = AdjustmentContext(ctrltype)
        #: Gauge name (``L`` / ``R`` / ``G`` / ``B``) -> its progress bar.
        self.gauges: dict[str, QProgressBar] = {}
        #: Metric name -> ``(read-out label, checkmark label)``.
        self.labels: dict[str, tuple[QLabel, QLabel]] = {}
        #: Metric name -> its leading icon label (so mode swaps can update it).
        self._icons: dict[str, QLabel] = {}

        outer = QVBoxLayout(self)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {FGCOLOUR};")
        title_font = title_label.font()
        title_font.setPointSize(title_font.pointSize() + 1)
        title_font.setBold(True)
        title_label.setFont(title_font)
        outer.addWidget(title_label)
        self.desc = QLabel(" ")
        self.desc.setWordWrap(True)
        self.desc.setStyleSheet(f"color: {FGCOLOUR};")
        outer.addWidget(self.desc)

        self._grid = QGridLayout()
        self._grid.setColumnStretch(2, 1)
        outer.addLayout(self._grid)
        outer.addStretch(1)
        self._row = 0

        if ctrltype == "check_all":
            self.desc.setText(
                lang.getstr("calibration.interactive_display_adjustment.check_all")
            )
            for name, tip in (
                ("luminance", "calibration.luminance"),
                ("black_level", "calibration.black_luminance"),
                ("white_point", "whitepoint"),
                ("black_point", "black_point"),
            ):
                self._add_label(name, icon=name, tooltip=lang.getstr(tip))
            return

        if ctrltype.startswith("rgb"):
            if ctrltype == "rgb_offset":
                hint = "calibration.interactive_display_adjustment.black_point.crt"
            else:
                hint = "calibration.interactive_display_adjustment.white_point"
            self.desc.setText(
                lang.getstr(hint)
                + " "
                + lang.getstr(
                    "calibration.interactive_display_adjustment.generic_hint.plural"
                )
            )
            self._add_gauge("R", text="R", btm_marker=False)
            self._add_gauge("G", text="G", top_marker=False, btm_marker=False)
            self._add_gauge("B", text="B", top_marker=False)
            self._add_label("rgb")

        # The luminance gauge + read-out (present on every non-check_all page).
        self._add_gauge("L", icon=self._lum_icon_name(False))
        self._add_label("luminance")

    def _add_gauge(
        self,
        name: str,
        text: str | None = None,
        icon: str | None = None,
        top_marker: bool = True,
        btm_marker: bool = True,
    ) -> None:
        """Add a gauge row: a leading label / icon and a channel-coloured
        1..100 progress bar, optionally bracketed by top/bottom
        target-marker ticks. For a run of adjacent gauges (R/G/B), only the
        first's top and the last's bottom marker should be drawn -- passing
        ``top_marker=False`` / ``btm_marker=False`` suppresses the ticks
        that would otherwise appear between them."""
        if top_marker:
            self._grid.addWidget(_marker_label("top"), self._row, 1, 1, 2)
            self._row += 1
        head = QLabel(text or " ")
        head.setStyleSheet(f"color: {FGCOLOUR};")
        if icon:
            _set_pixmap(head, 16, icon)
            self._icons[name] = head
        gauge = QProgressBar()
        gauge.setRange(0, 100)
        gauge.setValue(0)
        gauge.setTextVisible(False)
        gauge.setFixedSize(_GAUGE_WIDTH, 10)
        gauge.setStyleSheet(_gauge_stylesheet(name, self.ctrltype))
        self.gauges[name] = gauge
        self._grid.addWidget(head, self._row, 0)
        self._grid.addWidget(gauge, self._row, 1, 1, 2)
        self._row += 1
        if btm_marker:
            self._grid.addWidget(_marker_label("btm"), self._row, 1, 1, 2)
            self._row += 1

    def _add_label(
        self, name: str, icon: str | None = None, tooltip: str | None = None
    ) -> None:
        """Add a read-out row: an optional metric icon, a checkmark, a label."""
        col = 0
        if icon:
            icon_label = QLabel()
            _set_pixmap(icon_label, 16, icon)
            if tooltip:
                icon_label.setToolTip(tooltip)
            self._icons[name] = icon_label
            self._grid.addWidget(icon_label, self._row, col)
            col += 1
        checkmark = QLabel()
        _set_pixmap(checkmark, 16, "checkmark")
        checkmark.setVisible(False)
        self._grid.addWidget(checkmark, self._row, col)
        col += 1
        label = QLabel(" ")
        label.setStyleSheet(f"color: {FGCOLOUR};")
        _reserve_metric_label_size(label)
        self._grid.addWidget(label, self._row, col, 1, 3 - col)
        self.labels[name] = (label, checkmark)
        self._row += 1

    def _lum_icon_name(self, is_crt: bool) -> str:
        """The luminance-gauge icon name for this page in the given mode."""
        normalized = {"rgb_offset": "black_level", "rgb_gain": "luminance"}.get(
            self.ctrltype, self.ctrltype
        )
        return _LUM_ICONS.get(normalized, {}).get(is_crt, normalized)

    def apply_mode(self, is_crt: bool) -> None:
        """Update mode-dependent icons and the hint text for CRT vs LCD."""
        self.context.measurement_mode = "c" if is_crt else "l"
        if self.ctrltype == "check_all":
            for name in ("luminance", "black_level"):
                icon = self._icons.get(name)
                if icon is not None:
                    _set_pixmap(icon, 16, _LUM_ICONS[name][is_crt])
        elif "L" in self._icons:
            _set_pixmap(self._icons["L"], 16, self._lum_icon_name(is_crt))
        self._update_desc(is_crt)

    def _update_desc(self, is_crt: bool) -> None:
        """Port of ``DisplayAdjustmentPanel.update_desc`` (luminance pages)."""
        if self.ctrltype not in ("luminance", "black_level"):
            return
        if self.ctrltype == "black_level":
            hint = "calibration.interactive_display_adjustment.black_level.crt"
        elif is_crt:
            hint = "calibration.interactive_display_adjustment.white_level.crt"
        else:
            hint = "calibration.interactive_display_adjustment.white_level.lcd"
        self.desc.setText(
            lang.getstr(hint)
            + " "
            + lang.getstr(
                "calibration.interactive_display_adjustment.generic_hint.singular"
            )
        )

    def reset(self) -> None:
        """Zero the gauges, hide the check marks and blank the read-outs."""
        self.context.initial_br = None
        self.context.target_bl = None
        for gauge in self.gauges.values():
            gauge.setValue(0)
        for label, checkmark in self.labels.values():
            label.setText(" ")
            label.setStyleSheet(f"color: {FGCOLOUR};")
            checkmark.setVisible(False)


class DisplayAdjustmentWindow(BaseWindow):
    """Interactive display-adjustment window driven by ``dispcal`` output.

    Feed each interactive ``dispcal`` chunk to :meth:`parse_output` (or
    :meth:`write`); the window parses it, renders the gauges / read-outs, and
    tracks the measuring / menu phase to enable the right buttons. User actions
    (start / stop an adjustment, continue to calibration, menu keys) are surfaced
    as the string to send to ``dispcal`` on :attr:`send_requested`.

    Args:
        parent (QtWidget | None): Optional parent widget.
    """

    #: Emitted with the key string to send to the interactive ``dispcal``
    #: (``" "`` to abort, ``"1"``..``"5"`` to start a page, ``"7"`` / ``"8"`` to
    #: continue, or a raw menu key). Wired to ``worker.safe_send`` in 5c-iii.
    send_requested = Signal(str)

    #: Emitted once the window has accepted a close request. The driver uses
    #: this to abort a still-running interactive ``dispcal`` subprocess -
    #: without it, closing the window while measuring (or while parked at the
    #: interactive menu) leaves the subprocess -- and its on-screen patch
    #: window -- running with nothing left to talk to it.
    closing = Signal()

    def __init__(self, parent: QtWidget | None = None) -> None:
        super().__init__(
            parent,
            name="displayadjustmentframe",
            title=lang.getstr("calibration.interactive_display_adjustment"),
            icon_name=APPNAME.lower(),
        )
        self.setStyleSheet(
            f"QWidget {{ background-color: {BGCOLOUR}; }}\n"
            + _ACTION_BUTTON_STYLESHEET
        )

        # Parse / phase state, mirroring the wx frame.
        self.keep_going = True
        self.is_measuring: bool | None = None
        self.is_busy: bool | None = None
        self.cold_run = True
        self.lastmsg = ""
        self.disabled_pages: list[int] = []
        self._argyll_key = {i: page[2] for i, page in enumerate(_PAGES)}

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        top = QHBoxLayout()
        root.addLayout(top, 1)

        # Left: an icon-only page selector (the wx ``FlatImageBook`` tab column).
        self._selector = QButtonGroup(self)
        self._selector.setExclusive(True)
        selector_col = QVBoxLayout()
        self._selector_buttons: list[QToolButton] = []
        self._stack = QStackedWidget()
        self.pages: list[_AdjustmentPage] = []
        for index, (ctrltype, title_keys, _key) in enumerate(_PAGES):
            title = " / ".join(lang.getstr(k) for k in title_keys)
            page = _AdjustmentPage(ctrltype, title)
            self.pages.append(page)
            self._stack.addWidget(page)
            button = _SelectorButton()
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setToolTip(title)
            icon_name = _SELECTOR_ICONS[ctrltype][False]
            button.setIcon(_pixmap_icon(72, icon_name))
            button.setIconSize(get_theme_pixmap(72, icon_name).size())
            button.clicked.connect(lambda _c=False, i=index: self._on_select(i))
            self._selector.addButton(button, index)
            self._selector_buttons.append(button)
            selector_col.addWidget(button)
        selector_col.addStretch(1)
        top.addLayout(selector_col)

        # Right: the stacked adjustment pages.
        top.addWidget(self._stack, 1)

        # Button bar spans the full width of the dialog, below the selector
        # column and the stacked pages, matching the wx frame's layout.
        button_row = QHBoxLayout()
        self._indicator = QLabel()
        self._indicator.setFixedSize(10, 10)
        button_row.addWidget(self._indicator)
        button_row.addStretch(1)
        self.adjustment_btn = QPushButton(
            lang.getstr("calibration.interactive_display_adjustment.start")
        )
        button_height = 31
        self.adjustment_btn.setObjectName("adjustmentBtn")
        self.adjustment_btn.setFixedHeight(button_height)
        icon, icon_size = _button_icon("play")
        self.adjustment_btn.setIcon(icon)
        self.adjustment_btn.setIconSize(icon_size)
        self.adjustment_btn.setEnabled(False)
        self.adjustment_btn.clicked.connect(self.start_interactive_adjustment)
        button_row.addWidget(self.adjustment_btn)
        self.sound_on_off_btn = QToolButton()
        self.sound_on_off_btn.setFixedHeight(button_height)
        self.sound_on_off_btn.setObjectName("soundButton")
        self.sound_on_off_btn.setToolTip(lang.getstr("measurement.play_sound"))
        self.sound_on_off_btn.clicked.connect(self._toggle_sound)
        button_row.addWidget(self.sound_on_off_btn)
        self.calibration_btn = QPushButton(lang.getstr("calibration.start"))
        self.calibration_btn.setObjectName("calibrationBtn")
        self.calibration_btn.setFixedHeight(button_height)
        icon, icon_size = _button_icon("skip")
        self.calibration_btn.setIcon(icon)
        self.calibration_btn.setIconSize(icon_size)
        self.calibration_btn.setEnabled(False)
        self.calibration_btn.clicked.connect(self.continue_to_calibration)
        button_row.addWidget(self.calibration_btn)
        root.addLayout(button_row)

        self._set_sound_icon()
        self.setup()

    # -- setup / reset ------------------------------------------------------

    def setup(self) -> None:
        """Port of ``DisplayAdjustmentFrame._setup``: mode-dependent init."""
        self.cold_run = True
        self.is_busy = None
        self.is_measuring = None
        self.keep_going = True
        self.lastmsg = ""
        is_crt = getcfg("measurement_mode") == "c"
        for index, page in enumerate(self.pages):
            page.apply_mode(is_crt)
            self._selector_buttons[index].setIcon(
                _pixmap_icon(72, _SELECTOR_ICONS[page.ctrltype][is_crt])
            )
        if is_crt:
            self.disabled_pages = []
            if getcfg("calibration.black_luminance", False):
                self.set_selection(0)
            else:
                self.disabled_pages = [0]
                self.set_selection(1)
        else:
            self.disabled_pages = [0, 3]
            self.set_selection(1)
        for index, button in enumerate(self._selector_buttons):
            button.setVisible(index not in self.disabled_pages)
        if getcfg("trc"):
            self.calibration_btn.setText(lang.getstr("calibration.start"))
        elif getcfg("calibration.continue_next"):
            self.calibration_btn.setText(lang.getstr("calibration.skip"))
        else:
            self.calibration_btn.setText(lang.getstr("finish"))

    def reset(self) -> None:
        """Reset every page and the buttons to the pre-adjustment state."""
        self.setup()
        for page in self.pages:
            page.reset()
        self._set_adjustment_button("start", enabled=False)
        self.calibration_btn.setEnabled(False)
        self._clear_indicator()

    def current_page(self) -> _AdjustmentPage:
        """The page for the currently selected adjustment."""
        return self.pages[self._stack.currentIndex()]

    def set_selection(self, index: int) -> None:
        """Select the adjustment page at ``index`` (updating the selector)."""
        self._stack.setCurrentIndex(index)
        button = self._selector_buttons[index]
        button.setChecked(True)

    def _on_select(self, index: int) -> None:
        """Handle a selector click: abort any measurement, switch page."""
        if index in self.disabled_pages:
            return
        self.abort()
        self._stack.setCurrentIndex(index)

    # -- rendering ----------------------------------------------------------

    def parse_output(self, txt: str) -> None:
        """Parse one ``dispcal`` chunk and render it (port of ``parse_txt``).

        Args:
            txt (str): A chunk of interactive ``dispcal`` output.
        """
        if not txt:
            return
        self.pulse(txt)
        page = self.current_page()
        readings = parse_adjustment(txt, page.context)
        self._apply_readings(readings, page)
        self._handle_phase(readings)

    def write(self, txt: str) -> None:
        """Render a ``dispcal`` chunk (the worker's ``progress_wnd.write``).

        The wx frame defers this onto the GUI thread with ``wx.CallAfter``; under
        Qt that cross-thread marshalling is the driver's job (sub-slice 5c-iii),
        so here it renders directly.

        Args:
            txt (str): A chunk of interactive ``dispcal`` output.
        """
        self.parse_output(txt)

    def _apply_readings(
        self, readings: AdjustmentReadings, page: _AdjustmentPage
    ) -> None:
        """Push parsed gauges / labels / indicator onto ``page``."""
        for name, value in readings.gauges.items():
            gauge = page.gauges.get(name)
            if gauge is not None:
                gauge.setValue(value)
        for name, metric in readings.labels.items():
            entry = page.labels.get(name)
            if entry is None:
                continue
            label, checkmark = entry
            label.setText(metric.text)
            checkmark.setVisible(metric.in_tolerance)
            colour = GREEN if metric.in_tolerance else FGCOLOUR
            label.setStyleSheet(f"color: {colour};")
        if readings.indicator is not None:
            self._set_indicator(readings.indicator)
        if readings.reading_event:
            self._play_sound()

    def _handle_phase(self, readings: AdjustmentReadings) -> None:
        """Port the button / state transitions at the tail of ``parse_txt``."""
        if readings.phase == "menu":
            if self.cold_run:
                self.cold_run = False
            if self.is_measuring is not False:
                if self.is_measuring is True:
                    self._set_adjustment_button("start", enabled=True)
                else:
                    self.adjustment_btn.setEnabled(True)
                self.is_busy = False
                self.is_measuring = False
                self._clear_indicator()
            self.calibration_btn.setEnabled(True)
            if not self.isVisible():
                self.show()
            self.raise_()
        elif readings.phase == "measuring":
            self.is_busy = True
            if not self.is_measuring:
                self._set_adjustment_button("stop", enabled=True)
            self.is_measuring = True

    def pulse(self, msg: str = "") -> bool:
        """Show a transient status message (port of ``DisplayAdjustmentFrame.Pulse``).

        Args:
            msg (str): The status message. Empty just returns the current state.

        Returns:
            bool: The current :attr:`keep_going` state, mirroring wx ``Pulse``.
        """
        if not msg:
            return self.keep_going
        msg = str(msg)
        recognized = (
            msg
            in (
                lang.getstr("instrument.initializing"),
                lang.getstr("instrument.calibrating"),
                lang.getstr("please_wait"),
                lang.getstr("aborting"),
            )
            or msg == " " * 4
            or ": error -" in msg.lower()
            or "failed" in msg.lower()
            or msg.startswith(
                (lang.getstr("webserver.waiting"), lang.getstr("connection.waiting"))
            )
        )
        if recognized and msg != self.lastmsg:
            self.lastmsg = msg
            page = self.current_page()
            for label, checkmark in page.labels.values():
                checkmark.setVisible(False)
                label.setText(" ")
            if page.labels:
                first = next(iter(page.labels.values()))[0]
                first.setText(wrap(msg, 46))
                first.setStyleSheet(f"color: {FGCOLOUR};")
        return self.keep_going

    # The worker's ``progress_wnd`` also calls these; both defer to ``pulse``.
    def UpdateProgress(self, value: int, msg: str = "") -> bool:  # noqa: N802
        """Progress-window shim: forward to :meth:`pulse` (value ignored)."""
        return self.pulse(msg)

    def UpdatePulse(self, msg: str = "") -> bool:  # noqa: N802
        """Progress-window shim: forward to :meth:`pulse`."""
        return self.pulse(msg)

    # -- indicator / sound --------------------------------------------------

    def _set_indicator(self, name: str) -> None:
        """Show the measuring indicator dot (``record`` / ``record_outline``)."""
        _set_pixmap(self._indicator, 10, name)

    def _clear_indicator(self) -> None:
        """Clear the measuring indicator dot."""
        self._indicator.clear()

    def _toggle_sound(self) -> None:
        """Toggle the measurement sound setting and update the button icon."""
        from DisplayCAL.config import setcfg

        setcfg(
            "measurement.play_sound",
            int(not bool(getcfg("measurement.play_sound"))),
        )
        self._set_sound_icon()

    def _set_sound_icon(self) -> None:
        """Set the sound button icon from the current setting."""
        name = "sound_volume_full" if getcfg("measurement.play_sound") else "sound_off"
        self.sound_on_off_btn.setIcon(_pixmap_icon(16, name))
        self.sound_on_off_btn.setIconSize(QSize(13, 13))

    def _play_sound(self) -> None:
        """Best-effort single beep on a fresh reading (overridable seam)."""
        if not getcfg("measurement.play_sound"):
            return
        try:
            from DisplayCAL import audio
            from DisplayCAL.config import get_data_path

            audio.Sound(get_data_path("beep.wav")).safe_play()
        except Exception:  # noqa: BLE001 - a missing/failed sound must never break adjustment
            pass

    # -- worker-key actions -------------------------------------------------

    def _send(self, key: str) -> None:
        """Request that ``key`` be sent to the interactive ``dispcal``."""
        self.send_requested.emit(key)

    def abort(self) -> None:
        """Abort the current measurement (send a space) if one is running."""
        if self.is_measuring:
            self._send(" ")

    def abort_and_send(self, key: str) -> None:
        """Abort any measurement, then send ``key`` and mark the window busy."""
        self.abort()
        self._send(key)
        self.is_busy = True
        self.adjustment_btn.setEnabled(False)
        self.calibration_btn.setEnabled(False)

    def start_interactive_adjustment(self) -> None:
        """Start (or, if measuring, abort) the selected page's adjustment."""
        if self.is_measuring:
            self.abort()
        else:
            self.abort_and_send(self._argyll_key[self._stack.currentIndex()])

    def continue_to_calibration(self) -> None:
        """Continue past adjustment (``7`` to calibrate, ``8`` to finish)."""
        self.abort_and_send("7" if getcfg("trc") else "8")

    def _set_adjustment_button(self, startstop: str, *, enabled: bool) -> None:
        """Set the start/stop button's label, icon and enabled state."""
        self.adjustment_btn.setText(
            lang.getstr(f"calibration.interactive_display_adjustment.{startstop}")
        )
        icon, icon_size = _button_icon("pause" if startstop == "stop" else "play")
        self.adjustment_btn.setIcon(icon)
        self.adjustment_btn.setIconSize(icon_size)
        self.adjustment_btn.setEnabled(enabled)

    # -- keyboard -----------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Handle the interactive-adjustment key bindings.

        Args:
            event (QKeyEvent): The Qt key event.
        """
        key = event.key()
        text = event.text()
        if key == Qt.Key.Key_Space:
            if self.is_measuring:
                self.abort()
            else:
                self.start_interactive_adjustment()
        elif text in ("1", "2", "3", "4", "5"):
            index = int(text) - 1
            if index not in self.disabled_pages and not self.is_measuring:
                self.set_selection(index)
                self.start_interactive_adjustment()
        elif key == Qt.Key.Key_Escape or text in ("7", "8", "Q", "q"):
            if not getcfg("trc") and text == "7":
                return
            self._send("\x1b" if key == Qt.Key.Key_Escape else text)
        else:
            super().keyPressEvent(event)

    # -- geometry / lifecycle ----------------------------------------------

    @property
    def _pos_prefix(self) -> str:
        """Share the ``position.progress.*`` keys with the wx frame / dialog."""
        return "position.progress"

    def place(self) -> None:
        """Restore the last saved position (shared with the progress window)."""
        self.restore_position()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Persist config on close and tell the driver to abort, mirroring wx.

        The wx frame's own ``keepGoing`` flag *is* what ``Worker.calibrate``
        polls (it reads the frame directly as ``progress_wnd``), so setting it
        false on close was enough to unwind the running ``dispcal``. Under Qt
        the worker instead polls a thread-safe proxy (``_AdjustmentTerminal``),
        so :attr:`keep_going` going false here does nothing on its own; the
        driver must be told explicitly via :attr:`closing`.

        Args:
            event (QCloseEvent): The Qt close event.
        """
        self.keep_going = False
        writecfg()
        super().closeEvent(event)
        if event.isAccepted():
            self.closing.emit()
