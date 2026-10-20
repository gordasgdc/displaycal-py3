"""The measurement plan in plain numbers, shared by the guided and advanced views.

Three different numbers are shown on separate lines so they cannot be confused:
the patches in the chart (total), the largest block, and how many blocks that
makes. The numbers come from :func:`DisplayCAL.measurement_plan.make_plan`, the
function the runner itself uses, and the block size is the one configuration key
``measurement.block_size`` in both views. Nothing here changes a measurement.
"""

from __future__ import annotations

from qtpy.QtWidgets import (
    QComboBox,
    QInputDialog,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import localization as lang
from DisplayCAL import measured_speed, measurement_plan as mp
from DisplayCAL import profile_name as profile_name_mod
from DisplayCAL.config import getcfg, setcfg
from DisplayCAL.ui import design_a, text_scale
from DisplayCAL.ui.guide_widgets import css as _css
from DisplayCAL.ui.guide_widgets import label as _label
from DisplayCAL.ui.guide_widgets import m as _m
from DisplayCAL.ui.guide_widgets import WrapRow
from DisplayCAL.ui.guide_widgets import tokens as _tokens

_OTHER = -1


def _tr(key: str, *args) -> str:
    return lang.getstr(key, list(args)) if args else lang.getstr(key)


def nblocks_text(n: int) -> str:
    """``one block`` / ``5 blocks`` / ``22 de blocuri`` (Romanian ``de`` rule)."""
    if n <= 1:
        return _tr("plan.nblocks.one")
    code = lang.getcode()
    many = code == "ro" and not (2 <= n % 100 <= 19)
    return _tr("plan.nblocks.many" if many else "plan.nblocks.few", n)


def plan_for(window) -> tuple[mp.Plan, bool]:
    """The plan for the chart now configured, and whether blocks can be used."""
    try:
        total = int(window.testchart_patches_amount.text() or 0)
    except (ValueError, AttributeError):
        total = 0
    worker = window.worker
    supported = (
        worker.blocks_supported()[0] if hasattr(worker, "blocks_supported") else False
    )
    size = int(getcfg("measurement.block_size") or 0) if supported else 0
    return mp.make_plan(total, size), supported


def speed_for(window, plan: mp.Plan) -> mp.Speed | None:
    """Observed speed of this instrument if there is a history, else its spec."""
    worker = window.worker
    try:
        seen = measured_speed.observed(worker.get_instrument_name())
    except Exception:  # noqa: BLE001 - a hint, never a blocker
        seen = None
    if seen is not None:
        return seen
    try:
        est = profile_name_mod.estimate_measurement_time(worker, plan.total)
    except Exception:  # noqa: BLE001
        return None
    if est.hours is None or not plan.total:
        return None
    return measured_speed.specified((est.hours * 3600 + est.minutes * 60) / plan.total)


class ChartPlanWidget(QWidget):
    """Chart total, chart chooser, block size, blocks and estimated time."""

    def __init__(self, window, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.window_ref = window
        self._syncing = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.total_label = _label("", size=1.05, bold=True)
        self.chart_menu_btn = self._make_chart_button()
        self._top_row = WrapRow(self.total_label, self.chart_menu_btn)
        lay.addWidget(self._top_row)
        self.block_combo = QComboBox()
        self.block_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.block_combo.setMinimumContentsLength(12)
        self.block_combo.currentIndexChanged.connect(self._block_changed)
        self._block_row = WrapRow(
            _label(_tr("plan.blocks.title"), bold=True), self.block_combo, grow_second=True
        )
        lay.addWidget(self._block_row)
        self.blocks_bar = design_a.BlocksBar()
        lay.addWidget(self.blocks_bar)
        self.summary = _label("", size=1.05)
        self.white = _label("", muted=True)
        self.time = _label("", size=1.05)
        self.basis = _label("", muted=True)
        self.long = _label("", size=1.05)
        self.note = _label("", muted=True)
        for w in (self.summary, self.white, self.time, self.basis, self.long, self.note):
            lay.addWidget(w)
        window.__dict__.setdefault("_plan_widgets", []).append(self)
        self._fill_combo()

    # chart chooser ----------------------------------------------------------
    def _make_chart_button(self) -> QPushButton:
        btn = QPushButton(_m(_tr("plan.chart_menu")))
        text_scale.set_scaled_font(btn, 1.0)
        menu = QMenu(btn)
        w = self.window_ref
        menu.addAction(_m(_tr("plan.chart_menu.choose")), w._testchart_btn_handler)
        menu.addAction(_m(_tr("plan.chart_menu.edit")), w._create_testchart_btn_handler)
        btn.setMenu(menu)
        return btn

    # block size -------------------------------------------------------------
    def _fill_combo(self) -> None:
        current = int(getcfg("measurement.block_size") or 0)
        self._syncing = True
        try:
            self.block_combo.clear()
            sizes = list(mp.BLOCK_CHOICES)
            if current and current not in sizes:
                sizes.append(current)
            for n in sizes:
                self.block_combo.addItem(
                    _tr("plan.blocks.off") if n == 0 else _tr("plan.blocks.n", mp.count_text(n, lang.getcode())),
                    n,
                )
            self.block_combo.addItem(_tr("plan.blocks.other"), _OTHER)
            self.block_combo.setCurrentIndex(max(self.block_combo.findData(current), 0))
        finally:
            self._syncing = False

    def _block_changed(self, index: int) -> None:
        if self._syncing or index < 0:
            return
        value = self.block_combo.itemData(index)
        if value == _OTHER:
            n, ok = QInputDialog.getInt(
                self,
                _tr("plan.blocks.title"),
                _tr("plan.blocks.other.prompt"),
                max(int(getcfg("measurement.block_size") or 500), 20),
                20,
                1_000_000,
            )
            if not ok:
                self._fill_combo()
                return
            value = n
        setcfg("measurement.block_size", int(value or 0))
        self.window_ref.refresh_plan_widgets()

    # painting ---------------------------------------------------------------
    def refresh(self) -> None:
        w = self.window_ref
        plan, supported = plan_for(w)
        code = lang.getcode()
        count = lambda n: mp.count_text(n, code)  # noqa: E731
        self._fill_combo()
        self.block_combo.setEnabled(supported)
        self.total_label.setText(_tr("plan.total", count(plan.total)))
        self.blocks_bar.set_plan(plan.total, plan.blocks, plan.per_block)
        if plan.split:
            self.summary.setText(
                _tr(
                    "plan.summary.split",
                    count(plan.total),
                    count(plan.block_size),
                    nblocks_text(plan.blocks),
                )
            )
            self.white.setText(
                _tr("plan.summary.each", count(plan.per_block))
                + " "
                + _tr("plan.summary.white", count(plan.extra_white), count(plan.readings))
            )
        else:
            self.summary.setText(_tr("plan.summary.single", count(plan.total)))
            self.white.setText("")
        self.white.setVisible(bool(self.white.text()))
        speed = speed_for(w, plan)
        t = _tokens()
        hours = None
        if speed is None:
            self.time.setText(_tr("plan.time.none"))
            self.time.setStyleSheet("")
            self.basis.setText("")
        else:
            mid = speed.typical * plan.readings
            hours = mid / 3600.0
            text = mp.time_range_text(plan, speed)
            self.time.setText(_tr("plan.time.observed" if speed.observed else "plan.time.spec", text))
            self.basis.setText(_tr("plan.time.basis.observed" if speed.observed else "plan.time.basis.spec"))
            color = (
                t["bad"] if hours > 7 else t["warn"] if hours > 3 else t["text"]
            )
            self.time.setStyleSheet(f"color:{_css(color)};")
        self.basis.setVisible(bool(self.basis.text()))
        self.long.setText(_tr("plan.long.warn") if hours and hours >= 1 else "")
        self.long.setVisible(bool(self.long.text()))
        current = int(getcfg("measurement.block_size") or 0)
        if not supported:
            why = w.worker.blocks_supported()[1] if hasattr(w.worker, "blocks_supported") else "blocks.no_instrument"
            self.note.setText(_tr(why))
        else:
            rec = mp.recommend_block_size(plan.total, hours, True, current)
            if rec:
                self.note.setText(
                    f"{_tr('plan.blocks.recommend')} ({_tr('plan.blocks.n', count(rec))})"
                )
            elif current and not plan.split and plan.total > 0:
                self.note.setText(_tr("plan.blocks.not_split", count(current)))
            elif plan.total and plan.total <= 600:
                self.note.setText(_tr("plan.blocks.too_small"))
            else:
                self.note.setText("")
        self.note.setVisible(bool(self.note.text()))
        self._top_row.reflow()
        self._block_row.reflow()
