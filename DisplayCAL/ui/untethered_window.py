"""Native Qt untethered measurement navigation window (issue #841).

Qt port of ``wx_untethered_frame.py::UntetheredFrame``: the interactive window
shown while measuring against the "Untethered" pseudo-display, where there is
no video signal to synchronize a patch generator against. The user instead
points the instrument at a patch shown as a plain color swatch on screen and
confirms each reading manually. ``spotread`` streams a prompt per patch; this
window turns each output chunk into the RGB patch to display, tracks the
measured Lab/XYZ per patch in a table, and lets the user step forward/back,
auto-advance through unmeasured patches, or finish and write the CTI3.

As with the other interactive ports (see
``DisplayCAL/ui/display_adjustment_window.py``), the *fancy* presentation is
dropped: wx's ``CustomGrid`` becomes a plain ``QTableWidget`` with native
column resizing (no manual scrollbar-width math), and the looping sound
effects become single best-effort beeps.

The window is toolkit- and worker-agnostic: instead of calling
``worker.safe_send`` directly (as the wx frame does), it emits the key to send
on :attr:`UntetheredWindow.send_requested`. Wiring that to a running
interactive ``spotread`` (with a thread-safe proxy of this window as the
worker's ``terminal``/``progress_wnd``) is
:class:`DisplayCAL.ui.worker_runner.UntetheredController`.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, QTimer, Signal
from qtpy.QtGui import QColor, QIcon
from qtpy.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import audio, colormath
from DisplayCAL import localization as lang
from DisplayCAL.config import get_data_path, getcfg, setcfg, writecfg
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui.assets import get_theme_pixmap
from DisplayCAL.ui.base_window import BaseWindow

if TYPE_CHECKING:
    from qtpy.QtGui import QCloseEvent, QKeyEvent
    from qtpy.QtWidgets import QWidget as QtWidget

    from DisplayCAL.cgats import CGATS

# Colours the wx frame uses verbatim.
BGCOLOUR = "#333333"
FGCOLOUR = "#999999"

_GRID_HEADERS = ("R", "G", "B", "", "", "L*", "a*", "b*")
#: Column indices for the two colour-swatch cells (measured-RGB, measured-Lab).
_RGB_SWATCH_COL = 3
_LAB_SWATCH_COL = 4


def _icon(size: int, name: str) -> QIcon:
    """Return a themed pixmap wrapped as a ``QIcon`` (possibly empty)."""
    return QIcon(get_theme_pixmap(size, name))


def _checkerboard_pixmap():
    """Load the "no patch yet" checkerboard placeholder image."""
    from qtpy.QtGui import QPixmap

    path = get_data_path("theme/checkerboard-32x32x5-333-444.png")
    return QPixmap(path) if path else QPixmap()


class UntetheredWindow(BaseWindow):
    """Interactive untethered-measurement navigation window.

    Feed each ``spotread`` output chunk to :meth:`parse_txt` (or :meth:`write`);
    the window tracks the current patch, renders the RGB/measured-Lab swatches
    and the per-patch grid, and enables the right buttons for the current
    phase. User actions (navigate, measure, finish) are surfaced as the key
    string to send to ``spotread`` on :attr:`send_requested`.

    Args:
        parent (QtWidget | None): Optional parent widget.
    """

    #: Emitted with the key string to send to the interactive ``spotread``
    #: (``" "`` to trigger a reading, ``"Q"`` / ``"\x1b"`` to quit/abort).
    send_requested = Signal(str)

    #: Emitted once the window has accepted a close request, so the driver
    #: can abort a still-running ``spotread`` subprocess.
    closing = Signal()

    #: Emitted on Escape / "Q": a full worker abort (port of the wx frame's
    #: ``key_handler`` calling ``self.worker.abort_subprocess()`` directly),
    #: distinct from :attr:`send_requested`'s raw keystrokes -- the driver
    #: connects this to ``worker.abort_subprocess()``.
    abort_requested = Signal()

    def __init__(self, parent: QtWidget | None = None) -> None:
        super().__init__(
            parent,
            name="untetheredframe",
            title=lang.getstr("measurement.untethered"),
            icon_name=APPNAME.lower(),
        )
        # QLabel/QCheckBox text is styled individually with FGCOLOUR below, but
        # the grid's cell/header text is palette-driven (not per-widget
        # styled), so without an explicit color here it renders in the OS
        # palette's *own* text color (dark on a light-mode OS) against this
        # forced-dark background -- unreadable regardless of the OS theme,
        # since this window (like DisplayAdjustmentWindow) is intentionally
        # always dark, matching the wx frame's hardcoded BGCOLOUR/FGCOLOUR.
        self.setStyleSheet(
            f"QWidget {{ background-color: {BGCOLOUR}; color: {FGCOLOUR}; }}"
            f"QTableWidget {{ background-color: {BGCOLOUR}; color: {FGCOLOUR};"
            " gridline-color: #444444; }"
            f"QHeaderView::section {{ background-color: #222222; color: {FGCOLOUR}; }}"
            # An explicit ``color`` in a stylesheet always wins over the
            # palette, including the palette's automatic dimming of disabled
            # widgets -- without this, a disabled button (e.g. "Finish" before
            # all patches are measured) renders with identical, active-looking
            # text and reads as unresponsive rather than legitimately disabled.
            "QPushButton:disabled, QToolButton:disabled { color: #666666; }"
        )

        #: The CGATS test chart being measured; set by the driver before the
        #: first output chunk arrives (mirrors ``Worker.set_terminal_cgats``).
        self.cgats: CGATS | None = None
        self.keep_going = True
        self.is_measuring = False
        self.last_error: str | None = None
        self.index = -1
        self.index_max = -1
        self.last_XYZ = (-1, -1, -1)
        self.white_XYZ = (-1, -1, -1)
        self.measure_count = 0
        self.measured: list[int] = []
        self.finished = False
        self._checkerboard = _checkerboard_pixmap()

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        panel = QGridLayout()
        outer.addLayout(panel)

        self.label_rgb = QLabel(" ")
        self.label_rgb.setStyleSheet(f"color: {FGCOLOUR};")
        panel.addWidget(self.label_rgb, 0, 0)
        self.label_xyz = QLabel(" ")
        self.label_xyz.setStyleSheet(f"color: {FGCOLOUR};")
        panel.addWidget(self.label_xyz, 0, 1)

        self.panel_rgb = QLabel()
        self.panel_rgb.setFixedSize(256, 256)
        self.panel_rgb.setScaledContents(True)
        self.panel_rgb.setFrameShape(QLabel.Shape.Box)
        panel.addWidget(self.panel_rgb, 1, 0)
        self.panel_xyz = QLabel()
        self.panel_xyz.setFixedSize(256, 256)
        self.panel_xyz.setScaledContents(True)
        self.panel_xyz.setFrameShape(QLabel.Shape.Box)
        panel.addWidget(self.panel_xyz, 1, 1)

        nav_row = QHBoxLayout()
        self.back_btn = QToolButton()
        self.back_btn.setIcon(_icon(10, "back"))
        self.back_btn.clicked.connect(self._back_btn_handler)
        nav_row.addWidget(self.back_btn)
        self.index_label = QLabel(" ")
        self.index_label.setStyleSheet(f"color: {FGCOLOUR};")
        nav_row.addWidget(self.index_label)
        self.next_btn = QToolButton()
        self.next_btn.setIcon(_icon(10, "play"))
        self.next_btn.clicked.connect(self._next_btn_handler)
        nav_row.addWidget(self.next_btn)
        nav_row.addStretch(1)
        self.auto_cb = QCheckBox(lang.getstr("auto"))
        self.auto_cb.setStyleSheet(f"color: {FGCOLOUR};")
        self.auto_cb.toggled.connect(self._auto_ctrl_handler)
        nav_row.addWidget(self.auto_cb)
        panel.addLayout(nav_row, 2, 0)

        measure_row = QHBoxLayout()
        self.measure_btn = QPushButton(lang.getstr("measure"))
        self.measure_btn.setIcon(_icon(10, "play"))
        self.measure_btn.clicked.connect(self._measure_btn_handler)
        measure_row.addWidget(self.measure_btn)
        self.sound_on_off_btn = QToolButton()
        self.sound_on_off_btn.setToolTip(lang.getstr("measurement.play_sound"))
        self.sound_on_off_btn.clicked.connect(self._toggle_sound)
        measure_row.addWidget(self.sound_on_off_btn)
        measure_row.addStretch(1)
        self.finish_btn = QPushButton(lang.getstr("finish"))
        self.finish_btn.clicked.connect(self._finish_btn_handler)
        measure_row.addWidget(self.finish_btn)
        panel.addLayout(measure_row, 2, 1)

        self.grid = QTableWidget(0, len(_GRID_HEADERS))
        self.grid.setHorizontalHeaderLabels(_GRID_HEADERS)
        self.grid.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.grid.verticalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignRight)
        self.grid.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.grid.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.grid.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.grid.cellClicked.connect(self._on_cell_clicked)
        outer.addWidget(self.grid, 1)

        self._set_sound_icon()
        self._setup()

    # -- setup / reset -------------------------------------------------------

    def _setup(self) -> None:
        """Reset all per-run state and controls to their initial values."""
        self.keep_going = True
        self.last_error = None
        self.index = -1
        self.index_max = -1
        self.last_XYZ = (-1, -1, -1)
        self.white_XYZ = (-1, -1, -1)
        self.measure_count = 0
        self.measured = []
        self.finished = False
        self.label_rgb.setText(" ")
        self.label_xyz.setText(" ")
        self._set_swatch_checkerboard(self.panel_rgb)
        self._set_swatch_checkerboard(self.panel_xyz)
        self.index_label.setText(" ")
        self._enable_buttons(False)
        self.auto_cb.setChecked(bool(getcfg("untethered.measure.auto")))
        self.finish_btn.setEnabled(False)
        self.grid.setRowCount(0)

    def reset(self) -> None:
        """Reset the window to its pre-measurement state (driver hook)."""
        self._setup()

    def set_cgats(self, cgats: CGATS) -> None:
        """Attach the CGATS test chart being measured (driver hook)."""
        self.cgats = cgats

    # -- rendering ------------------------------------------------------------

    def parse_txt(self, txt: str) -> None:
        """Parse one ``spotread`` output chunk and render it.

        Port of ``UntetheredFrame.parse_txt``.

        Args:
            txt (str): A chunk of ``spotread`` output.
        """
        if not txt or self.cgats is None:
            return
        data_len = len(self.cgats[0].DATA)
        if self.grid.rowCount() < data_len:
            self.index = 0
            self.index_max = data_len - 1
            self._populate_grid(data_len)
        if "Connecting to the instrument" in txt:
            self.pulse(lang.getstr("instrument.initializing"))
        if "Spot read needs a calibration" in txt:
            self.is_measuring = False
        if "Spot read failed" in txt:
            self.last_error = txt
        if "Result is XYZ:" in txt:
            self._handle_result(txt, data_len)
        if "key to take a reading" in txt and not self.last_error:
            self._handle_ready_for_reading()

    def write(self, txt: str) -> None:
        """Render a ``spotread`` chunk (the worker's ``progress_wnd.write``)."""
        self.parse_txt(txt)

    def _populate_grid(self, data_len: int) -> None:
        """Grow the grid to ``data_len`` rows and fill in the RGB patches."""
        self.grid.setRowCount(data_len)
        for i in range(data_len):
            row = self.cgats[0].DATA[i]
            self._set_row_label(i, str(i + 1))
            rgb = []
            for j, label in enumerate("RGB"):
                value = round(row[f"RGB_{label}"] / 100.0 * 255)
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.grid.setItem(i, j, item)
                rgb.append(value)
            for col in range(3, len(_GRID_HEADERS)):
                item = QTableWidgetItem()
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.grid.setItem(i, col, item)
            self.grid.item(i, _RGB_SWATCH_COL).setBackground(QColor(*rgb))

    def _set_row_label(self, row: int, text: str) -> None:
        """Set the vertical header label of ``row``."""
        item = self.grid.verticalHeaderItem(row)
        if item is None:
            item = QTableWidgetItem()
            self.grid.setVerticalHeaderItem(row, item)
        item.setText(text)

    def _get_lab_rgb(self) -> tuple[list[float], list[int]]:
        """Compute the Lab and swatch-RGB values for the current patch.

        Port of ``UntetheredFrame.get_Lab_RGB``.
        """
        row = self.cgats[0].DATA[self.index]
        XYZ = row["XYZ_X"], row["XYZ_Y"], row["XYZ_Z"]
        self.last_XYZ = XYZ
        Lab = colormath.XYZ2Lab(*XYZ)
        if self.white_XYZ[1] > 0:
            XYZ = [v / self.white_XYZ[1] * 100 for v in XYZ]
            white_XYZ_Y100 = [v / self.white_XYZ[1] * 100 for v in self.white_XYZ]
            white_CCT = colormath.XYZ2CCT(*white_XYZ_Y100)
            if white_CCT:
                DXYZ = colormath.CIEDCCT2XYZ(white_CCT, scale=100.0)
                if DXYZ:
                    white_CIEDCCT_Lab = colormath.XYZ2Lab(*DXYZ)
                PXYZ = colormath.planckianCT2XYZ(white_CCT, scale=100.0)
                if PXYZ:
                    white_planckianCCT_Lab = colormath.XYZ2Lab(*PXYZ)
                white_Lab = colormath.XYZ2Lab(*white_XYZ_Y100)
                if (
                    DXYZ
                    and PXYZ
                    and (
                        colormath.delta(*white_CIEDCCT_Lab + white_Lab)["E"] < 6
                        or colormath.delta(*white_planckianCCT_Lab + white_Lab)["E"] < 6
                    )
                ):
                    XYZ = colormath.adapt(XYZ[0], XYZ[1], XYZ[2], white_XYZ_Y100, "D65")
        X, Y, Z = (v / 100.0 for v in XYZ)
        color = [round(v) for v in colormath.XYZ2RGB(X, Y, Z, scale=255)]
        return Lab, color

    def _handle_result(self, txt: str, data_len: int) -> None:
        """Handle a "Result is XYZ:" line: record it and advance if settled."""
        self.last_error = None
        self._play_sound("beep.wav")
        match = re.search(
            r"XYZ:\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", txt
        )
        if not match:
            return

        def is_white(r) -> bool:
            return r["RGB_R"] == 100 and r["RGB_G"] == 100 and r["RGB_B"] == 100

        XYZ = [float(v) for v in match.groups()]
        row = self.cgats[0].DATA[self.index]
        if is_white(row) and XYZ[1] > 0:
            self.cgats[0].add_keyword(
                "LUMINANCE_XYZ_CDM2", "{:.6f} {:.6f} {:.6f}".format(*tuple(XYZ))
            )
            self.white_XYZ = XYZ
        Lab1 = colormath.XYZ2Lab(*self.last_XYZ)
        Lab2 = colormath.XYZ2Lab(*XYZ)
        delta = colormath.delta(*Lab1 + Lab2)
        consecutive_white_patch = (
            self.index
            and is_white(row)
            and is_white(self.cgats[0].DATA[self.index - 1])
        )
        measurement_exceeds_delta = delta["E"] > getcfg("untethered.min_delta") or (
            abs(delta["L"]) > getcfg("untethered.min_delta.lightness")
            and abs(delta["C"]) < getcfg("untethered.max_delta.chroma")
        )
        if not (consecutive_white_patch or measurement_exceeds_delta):
            return
        self.measure_count += 1
        if self.measure_count != 2:
            return
        self._play_sound("camera_shutter.wav")
        self.measure_count = 0
        self._set_row_label(self.index, str(self.index + 1))
        query = self.cgats[0].queryi1(
            {
                "RGB_R": row["RGB_R"],
                "RGB_G": row["RGB_G"],
                "RGB_B": row["RGB_B"],
                "SAMPLE_ID": row["SAMPLE_ID"],
            }
        )
        if query:
            index = query.SAMPLE_ID - 1
            if index not in self.measured:
                self.measured.append(index)
            query["XYZ_X"], query["XYZ_Y"], query["XYZ_Z"] = XYZ
        if getcfg("untethered.measure.auto"):
            self.show_rgb(clear_xyz=False, mark_current_row=False)
        self.show_xyz()
        Lab, color = self._get_lab_rgb()
        self.grid.item(query.SAMPLE_ID - 1, _LAB_SWATCH_COL).setBackground(
            QColor(*color)
        )
        for j in range(3):
            self.grid.item(query.SAMPLE_ID - 1, 5 + j).setText(f"{Lab[j]:.2f}")
        self.grid.scrollToItem(self.grid.item(self.index, 0))
        if len(self.measured) == data_len:
            self.finished = True
            self.finish_btn.setEnabled(True)
            return
        index = self.index
        for i in range(self.index + 1, data_len):
            if getcfg("untethered.measure.auto") or i not in self.measured:
                self.index = i
                break
        if self.index == index:
            for i in range(self.index - 1, -1, -1):
                if i not in self.measured:
                    self.index = i
                    break
        if self.index != index:
            # Refresh the on-screen target swatch to the new patch's colour
            # (show_rgb also marks the row label and scrolls it into view).
            # The device stays physically fixed for the whole session -- only
            # the displayed colour advances -- so without this the swatch
            # keeps showing the just-committed patch, the (stationary)
            # instrument keeps reading that same already-known colour, and
            # since untethered.min_delta is checked against the last
            # *committed* value, every further reading stays "too close" to
            # commit again: the run gets stuck on this patch forever.
            show_xyz = self.index in self.measured
            self.show_rgb(not show_xyz)
            if show_xyz:
                self.show_xyz()

    def _handle_ready_for_reading(self) -> None:
        """Handle "hit a key to take a reading": auto-measure or wait for input."""
        if getcfg("untethered.measure.auto") and self.is_measuring:
            if not self.finished and self.keep_going:
                self._measure()
            else:
                self._enable_buttons()
        else:
            show_xyz = self.index in self.measured
            delay = int(getcfg("untethered.measure.manual.delay") * 1000)
            QTimer.singleShot(delay, lambda: self.show_rgb(not show_xyz))
            if show_xyz:
                QTimer.singleShot(delay, self.show_xyz)
            QTimer.singleShot(delay, self._enable_buttons)

    def pulse(self, msg: str = "") -> bool:
        """Show a transient status message in the RGB label.

        Port of ``UntetheredFrame.Pulse``.

        Args:
            msg (str): The status message. Empty just returns the current state.

        Returns:
            bool: The current :attr:`keep_going` state.
        """
        if msg:
            self.label_rgb.setText(msg)
        return self.keep_going

    # The worker's ``progress_wnd`` also calls these; both defer to ``pulse``.
    def UpdateProgress(self, value: float, msg: str = "") -> bool:  # noqa: N802
        """Progress-window shim: forward to :meth:`pulse` (value ignored)."""
        return self.pulse(msg)

    def UpdatePulse(self, msg: str = "") -> bool:  # noqa: N802
        """Progress-window shim: forward to :meth:`pulse`."""
        return self.pulse(msg)

    # -- swatches -------------------------------------------------------------

    def _set_swatch_color(self, label: QLabel, color) -> None:
        """Fill a patch swatch with a solid RGB colour."""
        # A leftover pixmap paints over the label regardless of stylesheet, so
        # it must be cleared for the background-color to become visible.
        label.clear()
        label.setStyleSheet(
            f"background-color: rgb({color[0]}, {color[1]}, {color[2]});"
        )

    def _set_swatch_checkerboard(self, label: QLabel) -> None:
        """Reset a patch swatch to the "no patch yet" checkerboard."""
        label.setStyleSheet("")
        label.setPixmap(self._checkerboard)

    def show_rgb(self, clear_xyz: bool = True, mark_current_row: bool = True) -> None:
        """Display the RGB patch and colour for the current index.

        Port of ``UntetheredFrame.show_RGB``.
        """
        row = self.cgats[0].DATA[self.index]
        r = round(row["RGB_R"] / 100.0 * 255)
        g = round(row["RGB_G"] / 100.0 * 255)
        b = round(row["RGB_B"] / 100.0 * 255)
        self.label_rgb.setText(f"RGB {r} {g} {b}")
        self._set_swatch_color(self.panel_rgb, (r, g, b))
        if clear_xyz:
            self.label_xyz.setText(" ")
            self._set_swatch_checkerboard(self.panel_xyz)
        if mark_current_row:
            self._set_row_label(self.index, f"► {self.index + 1}")
            self.grid.scrollToItem(self.grid.item(self.index, 0))
        if self.index not in {r.row() for r in self.grid.selectedIndexes()}:
            self.grid.selectRow(self.index)
            self.grid.setCurrentCell(self.index, 0)
        self.index_label.setText(f"{self.index + 1}/{len(self.cgats[0].DATA)}")

    def show_xyz(self) -> None:
        """Display the measured Lab/colour for the current index."""
        Lab, color = self._get_lab_rgb()
        self.label_xyz.setText("L*a*b* {:.2f} {:.2f} {:.2f}".format(*Lab))
        self._set_swatch_color(self.panel_xyz, color)

    # -- navigation / buttons ---------------------------------------------

    def _navigate_to(self, index: int) -> None:
        """Jump to ``index`` (port of ``UntetheredFrame.update``)."""
        self._set_row_label(self.index, str(self.index + 1))
        self.index = index
        show_xyz = self.index in self.measured
        self.show_rgb(not show_xyz)
        if show_xyz:
            self.show_xyz()
        self._enable_buttons()

    def _back_btn_handler(self) -> None:
        if self.index > 0:
            self._navigate_to(self.index - 1)

    def _next_btn_handler(self) -> None:
        if self.index < self.index_max:
            self._navigate_to(self.index + 1)

    def _on_cell_clicked(self, row: int, _column: int) -> None:
        if not self.is_measuring and row > -1:
            self._navigate_to(row)

    def _enable_buttons(
        self, enable: bool = True, enable_measure_button: bool = False
    ) -> None:
        """Enable/disable the navigation and measure buttons.

        Port of ``UntetheredFrame.enable_btns``.
        """
        self.is_measuring = not enable and enable_measure_button
        self.back_btn.setEnabled(enable and self.index > 0)
        self.next_btn.setEnabled(enable and self.index < self.index_max)
        self.measure_btn.setIcon(_icon(10, "play" if enable else "pause"))
        self.measure_btn.setEnabled(enable or enable_measure_button)
        if self.measure_btn.isEnabled() and not self.grid.hasFocus():
            self.measure_btn.setFocus()

    def _measure(self) -> None:
        self._enable_buttons(False, True)
        # Use a delay to allow for TFT lag.
        QTimer.singleShot(200, lambda: self._send(" "))

    def _measure_btn_handler(self) -> None:
        if self.is_measuring:
            self.is_measuring = False
        else:
            self.last_XYZ = (-1, -1, -1)
            self.measure_count = 1
            self._measure()

    def _auto_ctrl_handler(self, checked: bool) -> None:
        setcfg("untethered.measure.auto", int(checked))

    def _finish_btn_handler(self) -> None:
        self.finish_btn.setEnabled(False)
        self._finalize_cgats()
        self._send("Q")
        QTimer.singleShot(500, lambda: self._send("Q"))

    def _finalize_cgats(self) -> None:
        """Write the completed measurement as a CTI3 (port of the tail of
        ``UntetheredFrame.finish_btn_handler``)."""
        self.cgats[0].type = b"CTI3"
        self.cgats[0].add_keyword("COLOR_REP", "RGB_XYZ")
        if self.white_XYZ[1] > 0:
            query = self.cgats[0].DATA
            for i in query:
                XYZ = query[i]["XYZ_X"], query[i]["XYZ_Y"], query[i]["XYZ_Z"]
                XYZ = [v / self.white_XYZ[1] * 100 for v in XYZ]
                query[i]["XYZ_X"], query[i]["XYZ_Y"], query[i]["XYZ_Z"] = XYZ
            normalized = "YES"
        else:
            normalized = "NO"
        self.cgats[0].add_keyword("NORMALIZED_TO_Y_100", normalized)
        self.cgats[0].add_keyword("DEVICE_CLASS", "DISPLAY")
        self.cgats[0].add_keyword("INSTRUMENT_TYPE_SPECTRAL", "NO")
        if hasattr(self.cgats[0], "APPROX_WHITE_POINT"):
            self.cgats[0].remove_keyword("APPROX_WHITE_POINT")
        for i, label in reversed(list(self.cgats[0].DATA_FORMAT.items())):
            if label.startswith(b"LAB_"):
                self.cgats[0].DATA_FORMAT.pop(i)
        for label in (b"XYZ_X", b"XYZ_Y", b"XYZ_Z"):
            if label not in list(self.cgats[0].DATA_FORMAT.values()):
                self.cgats[0].DATA_FORMAT.add_data((label,))
        self.cgats[0].write(os.path.splitext(self.cgats.filename)[0] + ".ti3")

    def _toggle_sound(self) -> None:
        setcfg(
            "measurement.play_sound", int(not bool(getcfg("measurement.play_sound")))
        )
        self._set_sound_icon()

    def _set_sound_icon(self) -> None:
        name = "sound_volume_full" if getcfg("measurement.play_sound") else "sound_off"
        self.sound_on_off_btn.setIcon(_icon(16, name))

    def _play_sound(self, filename: str) -> None:
        """Best-effort single sound, built lazily (port of the wx frame's
        eager ``audio.Sound`` construction in ``__init__``).

        Deferred to first use -- and wrapped defensively -- like
        ``DisplayAdjustmentWindow._play_sound``: constructing ``audio.Sound``
        eagerly at window construction (as the wx frame does) means every
        ``UntetheredWindow()`` pays for backend/device probing whether or not
        a sound is ever actually played, which is wasted work in headless
        contexts (tests, CI) and a failure there must never break the window.
        """
        if not getcfg("measurement.play_sound"):
            return
        try:
            audio.Sound(get_data_path(filename)).safe_play()
        except Exception:  # noqa: BLE001 - a missing/failed sound must never break measurement
            pass

    def _send(self, key: str) -> None:
        """Request that ``key`` be sent to the interactive ``spotread``."""
        self.send_requested.emit(key)

    # -- keyboard -----------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Handle the untethered-navigation key bindings.

        Args:
            event (QKeyEvent): The Qt key event.
        """
        key = event.key()
        text = event.text()
        if key in (Qt.Key.Key_Up,):
            self._back_btn_handler()
        elif key in (Qt.Key.Key_Down,):
            self._next_btn_handler()
        elif key == Qt.Key.Key_Home:
            if self.index > -1:
                self._navigate_to(0)
        elif key == Qt.Key.Key_End:
            if self.index_max > -1:
                self._navigate_to(self.index_max)
        elif key == Qt.Key.Key_PageDown:
            if self.index > -1:
                self._navigate_to(min(self.index + 10, self.index_max))
        elif key == Qt.Key.Key_PageUp:
            if self.index > -1:
                self._navigate_to(max(self.index - 10, 0))
        elif key == Qt.Key.Key_Escape or text.upper() == "Q":
            self.abort_requested.emit()
        elif text and self.measure_btn.isEnabled():
            self._measure_btn_handler()
        else:
            super().keyPressEvent(event)

    # -- geometry / lifecycle ------------------------------------------------

    @property
    def _pos_prefix(self) -> str:
        """Share the ``position.progress.*`` keys with the wx frame / dialog."""
        return "position.progress"

    def place(self) -> None:
        """Restore the last saved position (shared with the progress window)."""
        self.restore_position()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Persist config on close and tell the driver to abort.

        Args:
            event (QCloseEvent): The Qt close event.
        """
        self.keep_going = False
        writecfg()
        super().closeEvent(event)
        if event.isAccepted():
            self.closing.emit()
