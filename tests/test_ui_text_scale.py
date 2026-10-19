"""Text size: one mechanism, live preview, persistence, contrast, no effect on measurement."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("qtpy")
from test_ui_main_window import _init_config, qapp, stub_worker, window  # noqa: E402,F401
from qtpy.QtGui import QColor  # noqa: E402
from qtpy.QtWidgets import QApplication, QLabel  # noqa: E402

from DisplayCAL import config  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL.ui import text_scale as ts  # noqa: E402


@pytest.fixture(autouse=True)
def _restore(qapp, _init_config):  # noqa: F811
    lang.init()
    yield
    ts.apply("normal", persist=False)
    config.setcfg(ts.CFG_KEY, "normal")


def test_levels_scale_the_application_font(qapp):
    base = ts.base_points()
    ts.apply("normal")
    n = QApplication.font().pointSizeF()
    ts.apply("large")
    l = QApplication.font().pointSizeF()
    ts.apply("xlarge")
    x = QApplication.font().pointSizeF()
    assert (round(n, 1), round(l, 1), round(x, 1)) == (round(base, 1), round(base * 1.25, 1), round(base * 1.5, 1))


def test_scaled_widgets_follow_the_level_not_fixed_points(qapp):
    lab = QLabel("x")
    ts.set_scaled_font(lab, 1.5, bold=True)
    ts.set_min_height(lab, 40)
    ts.apply("normal")
    a, h1 = lab.font().pointSizeF(), lab.minimumHeight()
    ts.apply("xlarge")
    assert lab.font().pointSizeF() > a * 1.4 and lab.font().bold()
    assert lab.minimumHeight() > h1


def test_preference_persists_and_invalid_values_fall_back(qapp):
    ts.apply("large", persist=True)
    assert config.getcfg(ts.CFG_KEY) == "large" and ts.stored_level() == "large"
    config.setcfg(ts.CFG_KEY, "nonsense")
    assert ts.stored_level() == "normal"


@pytest.mark.parametrize("dark", [True, False])
def test_secondary_text_meets_wcag_aa_in_both_themes(qapp, dark):
    from DisplayCAL.ui import theme

    pal = theme.build_palette(dark)
    fg, bg = pal.windowText().color(), pal.window().color()
    c = ts.muted_color(fg, bg)
    assert ts.contrast_ratio(c, bg) >= 4.5
    assert ts.contrast_ratio(fg, bg) >= ts.contrast_ratio(c, bg)  # still "secondary"


def test_menu_and_button_are_visible_and_stay_in_sync(window):
    assert window.text_size_menu.title() == lang.getstr("textsize.title")
    acts = window.text_size_menu.actions_by_level
    acts["large"].trigger()
    assert ts.current_level() == "large" and acts["large"].isChecked() and not acts["normal"].isChecked()
    assert window.header_text_size_btn.text() == "Aa" and window._guide.text_size_btn.text() == "Aa"
    reset = [a for a in window.text_size_menu.actions() if a.text() == lang.getstr("textsize.reset")][0]
    assert reset.isEnabled()
    reset.trigger()
    assert ts.current_level() == "normal" and not reset.isEnabled()


def test_text_size_never_touches_the_measurement_settings(window):
    keys = [k for k in config.DEFAULTS if k.startswith(("dimensions.", "size.measureframe", "patterngenerator.", "measure."))]
    before = {k: config.getcfg(k) for k in keys}
    for level in ("xlarge", "large", "normal"):
        window.text_size_menu.actions_by_level[level].trigger()
    assert {k: config.getcfg(k) for k in keys} == before


def test_guided_page_reflows_without_horizontal_scroll_at_large_text(window):
    window.text_size_menu.actions_by_level["xlarge"].trigger()
    window.resize(820, 900)
    window.show()
    window._select_tab("guide")
    for _ in range(4):
        QApplication.processEvents()
    window._pin_stack_size_to_current_tab()
    bar = window._scroll_area.horizontalScrollBar()
    assert bar.maximum() == 0 or not bar.isVisible()


def test_reading_width_is_limited_and_grows_with_text(qapp):
    lab = QLabel("word " * 200)
    lab.setWordWrap(True)
    ts.limit_reading_width(lab, 70)
    ts.apply("normal")
    w1 = lab.maximumWidth()
    ts.apply("xlarge")
    assert 0 < w1 < lab.maximumWidth() < 100000


@pytest.mark.parametrize("level", ["normal", "large", "xlarge"])
def test_guided_footer_stays_on_screen_in_a_modest_window(window, level):
    """At any text size the Back/Continue buttons are visible without outer scroll."""
    from qtpy.QtCore import QPoint

    window.resize(766, 864)
    window.show()
    window._select_tab("guide")
    ts.apply(level)
    for _ in range(4):
        QApplication.processEvents()
    window._pin_stack_size_to_current_tab()
    for _ in range(3):
        QApplication.processEvents()
    g = window._guide
    bottom = g.next_btn.mapTo(window, QPoint(0, g.next_btn.height())).y()
    assert bottom <= window.height(), (level, bottom, window.height())
    assert window._scroll_area.verticalScrollBar().maximum() == 0


@pytest.mark.parametrize("level", ["normal", "xlarge"])
def test_model_question_is_never_covered_by_the_selector_below(window, level):
    """A wrapped label shown late keeps its full height (seen on Windows)."""
    from qtpy.QtWidgets import QLabel

    window.resize(766, 864)
    window.show()
    window._select_tab("guide")
    ts.apply(level)
    for _ in range(4):
        QApplication.processEvents()
    g = window._guide
    g.refresh()
    for _ in range(4):
        QApplication.processEvents()
    if not g.model_box.isVisible():
        pytest.skip("this instrument does not ask for a model")
    label = g.model_box.findChild(QLabel)
    assert label.height() >= label.heightForWidth(label.width())
    assert label.geometry().bottom() < g.model_combo.geometry().top()


def test_limited_width_label_counts_the_lines_it_really_gets(qapp):
    """The layout's height for a wide column must equal the height at the real width."""
    text = "word " * 120
    lab = ts.WrapLabel(text)
    lab.setWordWrap(True)
    lab.setMaximumWidth(300)
    assert lab.heightForWidth(900) == lab.heightForWidth(300)
    plain = QLabel(text)
    plain.setWordWrap(True)
    plain.setMaximumWidth(300)
    assert plain.heightForWidth(900) < lab.heightForWidth(900)  # the old, too small answer


@pytest.mark.parametrize("level", ["normal", "large", "xlarge"])
def test_measurement_plan_fits_a_modest_window_at_any_text_size(window, level, monkeypatch):
    """Nothing on the Măsurare page is cut off at the right edge (seen at XL on macOS)."""
    from qtpy.QtCore import QPoint

    monkeypatch.setattr(window.worker, "blocks_supported", lambda: (True, ""), raising=False)
    window.resize(766, 864)
    window.show()
    window._select_tab("guide")
    ts.apply(level)
    window.testchart_patches_amount.setText("11140")
    config.setcfg("measurement.block_size", 500)
    g = window._guide
    g._reached = 4
    g.go(3)
    g.refresh()
    for _ in range(6):
        QApplication.processEvents()
    window._pin_stack_size_to_current_tab()
    for _ in range(3):
        QApplication.processEvents()
    scroll = g.pages.currentWidget()
    limit = scroll.viewport().width()
    pw = g.plan_widget
    for w in (pw.chart_menu_btn, pw.block_combo, pw.total_label, pw.summary, pw.time):
        right = w.mapTo(scroll.viewport(), QPoint(w.width(), 0)).x()
        assert right <= limit + 1, (level, w, right, limit)
    config.setcfg("measurement.block_size", 0)


@pytest.mark.parametrize("step", [0, 1, 2, 3, 4])
def test_no_guided_page_needs_sideways_scrolling_at_the_largest_text(window, step, monkeypatch):
    monkeypatch.setattr(window.worker, "blocks_supported", lambda: (True, ""), raising=False)
    window.resize(766, 864)
    window.show()
    window._select_tab("guide")
    ts.apply("xlarge")
    g = window._guide
    g._reached = 4
    g.go(step)
    g.refresh()
    for _ in range(6):
        QApplication.processEvents()
    window._pin_stack_size_to_current_tab()
    for _ in range(3):
        QApplication.processEvents()
    bar = g.pages.currentWidget().horizontalScrollBar()
    assert bar.maximum() == 0, (step, bar.maximum())
