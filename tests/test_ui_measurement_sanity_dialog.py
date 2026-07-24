"""Headless tests for the measurement sanity-check review dialog.

Exercise ``DisplayCAL.ui.measurement_sanity_dialog.MeasurementSanityDialog``
under the shared offscreen ``QApplication``: row population, editing/
recompute, selection state and the removed/mods result accessors. No display,
Argyll or instrument is needed. The detection logic itself
(``DisplayCAL.measurement_report.resolve_sanity_check``) is covered by
``tests/test_measurement_report.py``; this file only covers the widget.
"""

import os

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL import config  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL import measurement_report as mr  # noqa: E402
from DisplayCAL.cgats import CGATS  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    config.initcfg()
    lang.init()
    lang.update_defaults()
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def ti3_path(data_path):
    return str(
        data_path / "icc" / ("UP2516D #1 2022-03-20 02-08 D6500 2.2 F-S XYZLUT+MTX.ti3")
    )


def _stub_suspicious_pair(item_a, item_b):
    """Same shape as ``check_ti3``'s own suspicious tuples (see
    ``tests/test_measurement_report.py``'s helper of the same name)."""
    delta = {"E": 5.0, "E_ok": False, "L_ok": True}
    sRGB_delta = {"E": 1.0}  # noqa: N806
    prev_delta_to_sRGB = {  # noqa: N806
        "E": 0.1,
        "L": 0,
        "C": 0,
        "H": 0,
        "ok": True,
        "E_ok": True,
        "L_ok": True,
        "C_ok": True,
        "H_ok": True,
    }
    delta_to_sRGB = {  # noqa: N806
        "E": 12.0,
        "L": 1,
        "C": 1,
        "H": 1,
        "ok": False,
        "E_ok": False,
        "L_ok": True,
        "C_ok": True,
        "H_ok": True,
    }
    return (item_a, item_b, delta, sRGB_delta, prev_delta_to_sRGB, delta_to_sRGB)


@pytest.fixture
def ctx(qapp, monkeypatch, ti3_path):
    """A resolved ``SanityCheckContext`` with two rows (item0, item1)."""
    config.setcfg("ti3.check_sanity.auto", 1)
    ti3 = CGATS(ti3_path, True)[0]
    data = ti3.queryv1("DATA")
    item0, item1 = data[0], data[1]
    monkeypatch.setattr(
        mr, "check_ti3", lambda *a, **kw: [_stub_suspicious_pair(item0, item1)]
    )
    return mr.resolve_sanity_check(ti3)


@pytest.fixture
def dialog(qapp, ctx):
    from DisplayCAL.ui.measurement_sanity_dialog import MeasurementSanityDialog

    dlg = MeasurementSanityDialog(None, "Test TI3", ctx)
    try:
        yield dlg
    finally:
        dlg.close()


class TestConstruction:
    def test_row_count_matches_context(self, dialog, ctx):
        assert dialog.table.rowCount() == len(ctx.rows)

    def test_first_row_unchecked_when_not_ok(self, dialog, ctx):
        from qtpy.QtCore import Qt

        # Row 1 (the flagged patch) has delta_to_sRGB["ok"] == False -> unchecked.
        assert dialog.table.item(1, 0).checkState() == Qt.Unchecked

    def test_select_all_label_reflects_initial_state(self, dialog):
        # Row 0 (the "previous" context row) starts checked, so the button
        # offers to deselect all (has_true wins, matching wx's own priority).
        assert dialog.select_all_btn.text() == lang.getstr("deselect_all")


class TestSelection:
    def test_toggle_select_all_unchecks_every_row(self, dialog):
        from qtpy.QtCore import Qt

        # The button starts as "deselect all" (see test above); clicking it
        # unchecks every row.
        dialog._toggle_select_all()
        for row in range(dialog.table.rowCount()):
            assert dialog.table.item(row, 0).checkState() == Qt.Unchecked
        assert dialog.select_all_btn.text() == lang.getstr("select_all")

        # Clicking again (now "select all") checks every row back.
        dialog._toggle_select_all()
        for row in range(dialog.table.rowCount()):
            assert dialog.table.item(row, 0).checkState() == Qt.Checked
        assert dialog.removed_row_indexes() == []

    def test_invert_selection_flips_every_row(self, dialog):
        from qtpy.QtCore import Qt

        before = [
            dialog.table.item(row, 0).checkState() == Qt.Checked
            for row in range(dialog.table.rowCount())
        ]
        dialog._invert_selection()
        after = [
            dialog.table.item(row, 0).checkState() == Qt.Checked
            for row in range(dialog.table.rowCount())
        ]
        assert after == [not v for v in before]

    def test_removed_row_indexes_reflects_unchecked_rows(self, dialog):
        from qtpy.QtCore import Qt

        dialog.table.item(0, 0).setCheckState(Qt.Unchecked)
        dialog.table.item(1, 0).setCheckState(Qt.Checked)
        assert dialog.removed_row_indexes() == [0]


class TestEditing:
    def test_valid_edit_is_recorded_as_mod(self, dialog):
        dialog.table.item(0, 1).setText("42.0000")
        assert dialog.mods() == {0: {"RGB_R": 42.0}}

    def test_invalid_edit_reverts_to_original_value(self, dialog, ctx):
        original = ctx.rows[0].rgb[0]
        dialog.table.item(0, 1).setText("not a number")
        assert float(dialog.table.item(0, 1).text()) == original
        assert dialog.mods() == {}

    def test_out_of_range_rgb_reverts(self, dialog, ctx):
        original = ctx.rows[0].rgb[0]
        dialog.table.item(0, 1).setText("150")
        assert float(dialog.table.item(0, 1).text()) == original
        assert dialog.mods() == {}

    def test_editing_back_to_original_clears_mod(self, dialog, ctx):
        original = ctx.rows[0].rgb[0]
        dialog.table.item(0, 1).setText("42.0000")
        assert dialog.mods()
        dialog.table.item(0, 1).setText(f"{original:.4f}")
        assert dialog.mods() == {}
