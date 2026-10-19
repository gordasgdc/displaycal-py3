"""The measurement plan on screen: three separate numbers, one configuration."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")
pytest.importorskip("qtpy")

from test_ui_main_window import _init_config, qapp, stub_worker, window  # noqa: E402,F401

from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL import measurement_plan as mp  # noqa: E402
from DisplayCAL.config import getcfg, setcfg  # noqa: E402
from DisplayCAL.ui import plan_widget as pw  # noqa: E402


@pytest.fixture
def plan(window, monkeypatch):
    monkeypatch.setattr(window.worker, "blocks_supported", lambda: (True, ""), raising=False)
    window.testchart_patches_amount.setText("11140")
    setcfg("measurement.block_size", 500)
    window.refresh_plan_widgets()
    yield window
    setcfg("measurement.block_size", 0)


def test_total_block_and_blocks_are_separate_lines(plan):
    w = plan.plan_widget
    assert "11" in w.total_label.text() and "140" in w.total_label.text()
    text = w.summary.text()
    assert "500" in text and "23" in text and "140" in text
    assert w.block_combo.currentData() == 500
    assert "22" in w.white.text()  # extra white readings stated separately


def test_guided_and_advanced_views_share_one_configuration(plan):
    guided = plan._guide.plan_widget
    advanced = plan.plan_widget
    assert guided.summary.text() == advanced.summary.text()
    idx = guided.block_combo.findData(1000)
    guided.block_combo.setCurrentIndex(idx)
    assert getcfg("measurement.block_size") == 1000
    assert advanced.block_combo.currentData() == 1000  # followed without reopening
    assert "12" in advanced.summary.text()  # 11139 / 1000 -> 12 blocks


def test_changing_block_size_never_changes_the_total(plan):
    for size in (100, 250, 500, 1000, 2000, 0):
        setcfg("measurement.block_size", size)
        plan.refresh_plan_widgets()
        assert plan.testchart_patches_amount.text() == "11140"
        assert mp.make_plan(11140, size).total == 11140


def test_chart_chooser_is_beside_the_total_in_both_views(plan):
    for widget in (plan.plan_widget, plan._guide.plan_widget):
        assert widget.chart_menu_btn.menu() is not None
        assert len(widget.chart_menu_btn.menu().actions()) == 2
        assert widget.chart_menu_btn.text()


def test_unsupported_instrument_keeps_one_run_and_says_why(window, monkeypatch):
    monkeypatch.setattr(
        window.worker, "blocks_supported", lambda: (False, "blocks.needs_calibration"), raising=False
    )
    window.testchart_patches_amount.setText("3000")
    setcfg("measurement.block_size", 500)
    window.refresh_plan_widgets()
    w = window.plan_widget
    assert not w.block_combo.isEnabled()
    assert "3" in w.summary.text() and "block" not in w.summary.text().lower().replace("blocks", "")
    assert w.note.text()
    setcfg("measurement.block_size", 0)


@pytest.mark.parametrize("code", ["en", "ro", "es"])
def test_every_new_text_exists_and_formats_in_each_language(code, plan):
    setcfg("lang", code)
    try:
        plan.refresh_plan_widgets()
        w = plan.plan_widget
        for label in (w.total_label, w.summary, w.white, w.time):
            assert label.text() and "%" not in label.text()
        assert w.chart_menu_btn.text()
        assert ("11.140" if code != "en" else "11,140") in w.total_label.text()
    finally:
        setcfg("lang", "en")


def test_romanian_block_count_grammar():
    setcfg("lang", "ro")
    try:
        assert pw.nblocks_text(1) == "un singur bloc"
        assert pw.nblocks_text(5) == "5 blocuri"
        assert pw.nblocks_text(22) == "22 de blocuri"
        assert pw.nblocks_text(112) == "112 blocuri"
        assert pw.nblocks_text(120) == "120 de blocuri"
    finally:
        setcfg("lang", "en")
