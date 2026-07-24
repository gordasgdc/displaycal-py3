"""Measurement-file sanity-check review dialog — Qt port.

Qt equivalent of wx's ``MeasurementFileCheckSanityDialog``
(``display_cal.py``): lets the user review, edit or discard patches
``DisplayCAL.measurement_report.resolve_sanity_check`` flagged as suspicious
before a measured TI3 is used to build a profile or measurement report. All
the delta-E math is toolkit-neutral (``DisplayCAL.worker.check_ti3_criteria1``
/ ``check_ti3_criteria2``, via
``DisplayCAL.measurement_report.recompute_sanity_row``); this module only
owns the table widget and its edit/selection interactions.

Dropped versus the wx dialog: the Space-key checkbox shortcut (Qt's default
item delegate already toggles a checkable cell's state on click; a dedicated
key handler wasn't judged worth the complexity for this review-only dialog).
"""

from __future__ import annotations

import re

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import colormath
from DisplayCAL import localization as lang
from DisplayCAL.measurement_report import SanityCheckContext, recompute_sanity_row

#: Grid column indexes, matching wx's ``MeasurementFileCheckSanityDialog``.
_RGB_COLS = (1, 2, 3)
_XYZ_COLS = (6, 7, 8)
_FIELD_NAMES = {
    1: "RGB_R",
    2: "RGB_G",
    3: "RGB_B",
    6: "XYZ_X",
    7: "XYZ_Y",
    8: "XYZ_Z",
}
_HEADERS = [
    "",
    "R %",
    "G %",
    "B %",
    "",
    "",
    "X",
    "Y",
    "Z",
    "ΔE*00\nXYZ A/B",
    "0.5 ΔE*00\nRGB A/B",
    "ΔE*00\nRGB-XYZ",
    "ΔL*00\nRGB-XYZ",
    "ΔC*00\nRGB-XYZ",
    "ΔH*00\nRGB-XYZ",
]
_BAD_COLOR = QColor(204, 0, 0)


def _format_value(value: float) -> str:
    """Format a percentage/XYZ value like wx's grid cell text.

    Ports the ``re.sub(r"^0+(?!\\.)", "", strval) or "0"`` cleanup in
    ``cell_change_handler``.
    """
    text = f"{value:.4f}"
    return re.sub(r"^0+(?!\.)", "", text) or "0"


def _clamp255(values) -> tuple[int, int, int]:
    """Clamp an sRGB triple to a valid ``QColor`` 0-255 range."""
    return tuple(max(0, min(255, round(v))) for v in values)


class MeasurementSanityDialog(QDialog):
    """Review/edit/discard suspicious measurement patches before proceeding.

    Args:
        parent (QWidget | None): Parent widget.
        title (str): Window title (basename of the TI3 file, or a generic
            fallback -- ports the wx dialog's title derivation).
        ctx (SanityCheckContext): The context
            :func:`~DisplayCAL.measurement_report.resolve_sanity_check`
            resolved.
        force (bool): Mirrors wx's ``force`` parameter: when ``True``, the OK
            button stays disabled until at least one row is deselected or
            edited (used by the standalone "check measurement file..." tool,
            not currently ported; both integration points in this Qt port
            pass the default ``False``).
    """

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        ctx: SanityCheckContext,
        force: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._ctx = ctx
        self._force = force
        self._mods: dict[int, dict[str, float]] = {}
        self._updating = False

        layout = QVBoxLayout(self)

        info_row = QHBoxLayout()
        col1 = QLabel(lang.getstr("warning.suspicious_delta_e"))
        col1.setWordWrap(True)
        col2 = QLabel(lang.getstr("warning.suspicious_delta_e.info"))
        col2.setWordWrap(True)
        info_row.addWidget(col1, 1)
        info_row.addWidget(col2, 1)
        layout.addLayout(info_row)

        self.table = QTableWidget(len(ctx.rows), len(_HEADERS), self)
        self.table.setHorizontalHeaderLabels(_HEADERS)
        self.table.setVerticalHeaderLabels([f"{row.sample_id:.0f}" for row in ctx.rows])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._updating = True
        try:
            for row_index, row in enumerate(ctx.rows):
                self._populate_row(row_index, row)
        finally:
            self._updating = False
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        button_row = QHBoxLayout()
        self.select_all_btn = QPushButton()
        self.select_all_btn.clicked.connect(self._toggle_select_all)
        button_row.addWidget(self.select_all_btn)
        invert_btn = QPushButton(lang.getstr("invert_selection"))
        invert_btn.clicked.connect(self._invert_selection)
        button_row.addWidget(invert_btn)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._update_select_all_label()
        self.resize(960, 320)

    # -- row population -----------------------------------------------------

    def _populate_row(self, row_index: int, row) -> None:
        check_item = QTableWidgetItem()
        check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        ok = (
            not row.delta or (row.delta["E_ok"] and row.delta["L_ok"])
        ) and row.delta_to_sRGB["ok"]
        check_item.setCheckState(Qt.Checked if ok else Qt.Unchecked)
        self.table.setItem(row_index, 0, check_item)

        for col, value in zip(_RGB_COLS, row.rgb):
            item = QTableWidgetItem(_format_value(value))
            item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row_index, col, item)
        for col, value in zip(_XYZ_COLS, row.xyz):
            item = QTableWidgetItem(_format_value(value))
            item.setFlags(Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row_index, col, item)

        self._set_readonly(row_index, 4, "")
        self._set_readonly(row_index, 5, "")
        self._paint_swatches(row_index, row.rgb, row.xyz)
        self._set_delta_cells(row_index, row.delta, row.sRGB_delta, row.delta_to_sRGB)

    def _set_readonly(self, row_index: int, col: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(row_index, col, item)

    def _mark_cell(self, row_index: int, col: int, ok: bool) -> None:
        item = self.table.item(row_index, col)
        font = item.font()
        font.setBold(not ok)
        item.setFont(font)
        if ok:
            item.setData(Qt.ForegroundRole, None)
        else:
            item.setForeground(_BAD_COLOR)

    def _paint_swatches(
        self,
        row_index: int,
        rgb: tuple[float, float, float],
        xyz: tuple[float, float, float],
    ) -> None:
        rgb255 = [v / 100.0 * 255 for v in rgb]
        self.table.item(row_index, 4).setBackground(QColor(*_clamp255(rgb255)))
        x, y, z = xyz
        if self._ctx.white:
            x, y, z = colormath.adapt(x, y, z, self._ctx.white, "D65")
        rgb255_xyz = colormath.XYZ2RGB(x / 100.0, y / 100.0, z / 100.0, scale=255)
        self.table.item(row_index, 5).setBackground(QColor(*_clamp255(rgb255_xyz)))

    def _set_delta_cells(
        self,
        row_index: int,
        delta: dict | None,
        sRGB_delta: dict | None,  # noqa: N803
        delta_to_sRGB: dict,  # noqa: N803
    ) -> None:
        for col in _XYZ_COLS:
            ok = (
                not delta or (delta["E_ok"] and (delta["L_ok"] or col != 7))
            ) and delta_to_sRGB["ok"]
            self._mark_cell(row_index, col, ok)
        self._set_readonly(row_index, 9, f"{delta['E']:.2f}" if delta else "")
        if delta:
            self._mark_cell(row_index, 9, delta["E_ok"])
        self._set_readonly(
            row_index, 10, f"{sRGB_delta['E']:.2f}" if sRGB_delta else ""
        )
        for offset, elch in enumerate("ELCH"):
            col = 11 + offset
            self._set_readonly(row_index, col, f"{delta_to_sRGB[elch]:.2f}")
            self._mark_cell(row_index, col, delta_to_sRGB[f"{elch}_ok"])

    # -- editing --------------------------------------------------------

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating:
            return
        row_index, col = item.row(), item.column()
        if col == 0:
            self._update_select_all_label()
            return
        if col not in _FIELD_NAMES:
            return

        row = self._ctx.rows[row_index]
        original = (
            row.rgb[_RGB_COLS.index(col)]
            if col in _RGB_COLS
            else row.xyz[_XYZ_COLS.index(col)]
        )
        text = item.text().strip().replace(",", ".")
        try:
            value = float(text)
            if (col in _RGB_COLS or col == 7) and value > 100:
                raise ValueError(f"Value {value!r} is invalid")
            if value < 0:
                raise ValueError(f"Negative value {value!r} is invalid")
        except ValueError:
            self._updating = True
            try:
                item.setText(_format_value(original))
            finally:
                self._updating = False
            return

        self._updating = True
        try:
            item.setText(_format_value(value))
        finally:
            self._updating = False

        rgb = tuple(float(self.table.item(row_index, c).text()) for c in _RGB_COLS)
        xyz = tuple(float(self.table.item(row_index, c).text()) for c in _XYZ_COLS)
        delta, sRGB_delta, delta_to_sRGB = recompute_sanity_row(  # noqa: N806
            self._ctx, row_index, rgb, xyz
        )
        self._updating = True
        try:
            self._paint_swatches(row_index, rgb, xyz)
            self._set_delta_cells(row_index, delta, sRGB_delta, delta_to_sRGB)
        finally:
            self._updating = False

        field = _FIELD_NAMES[col]
        if value != original:
            self._mods.setdefault(row_index, {})[field] = value
        elif row_index in self._mods:
            self._mods[row_index].pop(field, None)
            if not self._mods[row_index]:
                del self._mods[row_index]

        self._update_ok_enabled()

    # -- selection --------------------------------------------------------

    def _toggle_select_all(self) -> None:
        check = self.select_all_btn.text() == lang.getstr("select_all")
        for row_index in range(self.table.rowCount()):
            self.table.item(row_index, 0).setCheckState(
                Qt.Checked if check else Qt.Unchecked
            )
        self._update_select_all_label()

    def _invert_selection(self) -> None:
        for row_index in range(self.table.rowCount()):
            item = self.table.item(row_index, 0)
            item.setCheckState(
                Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
            )
        self._update_select_all_label()

    def _selection_state(self) -> tuple[bool, bool]:
        has_false = has_true = False
        for row_index in range(self.table.rowCount()):
            if self.table.item(row_index, 0).checkState() == Qt.Checked:
                has_true = True
            else:
                has_false = True
        return has_false, has_true

    def _update_select_all_label(self) -> None:
        has_false, has_true = self._selection_state()
        self.select_all_btn.setText(
            lang.getstr("deselect_all") if has_true else lang.getstr("select_all")
        )
        self._update_ok_enabled(has_false)

    def _update_ok_enabled(self, has_false: bool | None = None) -> None:
        if has_false is None:
            has_false, _has_true = self._selection_state()
        enabled = has_false or not self._force or bool(self._mods)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(enabled)

    # -- result -------------------------------------------------------------

    def removed_row_indexes(self) -> list[int]:
        """Indexes of rows the user unchecked for removal."""
        return [
            row_index
            for row_index in range(self.table.rowCount())
            if self.table.item(row_index, 0).checkState() != Qt.Checked
        ]

    def mods(self) -> dict[int, dict[str, float]]:
        """Row index -> ``{field: value}`` for edited-but-kept rows."""
        return dict(self._mods)
