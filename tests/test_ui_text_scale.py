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


def test_style_sheet_labels_follow_the_text_size_both_ways(window):
    """Section descriptions in the advanced tabs (they carry a style sheet) change with the level."""
    window._select_tab("profiling")
    QApplication.processEvents()
    headers = window._section_headers
    assert headers
    for level in ("xlarge", "normal", "large", "normal"):
        ts.apply(level)
        QApplication.processEvents()
        app_pt = round(QApplication.font().pointSizeF(), 1)
        for h in headers:
            assert round(h.purpose.font().pointSizeF(), 1) == app_pt, (level, h.section)
            assert round(h.toggle.font().pointSizeF(), 1) == app_pt, (level, h.section)


def test_long_paths_get_break_points_but_markup_and_short_words_are_untouched():
    text = "Logs: /Volumes/Cristi/TESTE/GDC_PROJECTS/DisplayCAL-CG/Library/Logs <b>/very/long/path/inside/markup/here/x</b> ok"
    out = ts.breakable(text)
    assert "​" in out.split()[1] or "/​" in out
    assert out.replace("​", "") == text
    assert ts.breakable("short words only") == "short words only"
    assert "<b>/very/long/path/inside/markup/here/x</b>" in out


def test_diagnostic_dialog_fits_its_window_at_the_largest_text(qapp, monkeypatch, tmp_path):
    from qtpy.QtWidgets import QScrollArea

    from DisplayCAL import config as cfg
    from DisplayCAL.ui import diagnostic_dialog as dd

    long_dir = str(tmp_path / ("a_very_long_folder_name_" * 4) / "Library" / "Logs" / "DisplayCAL")
    monkeypatch.setattr(dd.dlog, "_LOGDIR", long_dir, raising=False)
    ts.apply("xlarge")
    dlg = dd.DiagnosticDialog()
    dlg.show()
    for _ in range(5):
        QApplication.processEvents()
    area = dlg.findChild(QScrollArea)
    assert area.horizontalScrollBar().maximum() == 0


@pytest.mark.parametrize("which", ["export", "feedback", "support_star", "support_welcome"])
def test_other_dialogs_do_not_need_sideways_scrolling_at_the_largest_text(qapp, which):
    from qtpy.QtWidgets import QScrollArea

    from DisplayCAL.ui import diagnostic_dialog as dd
    from DisplayCAL.ui import support_dialog as sd

    ts.apply("xlarge")
    if which == "export":
        dlg = dd.ExportDialog()
    elif which == "feedback":
        dlg = sd.FeedbackDialog()
    else:
        classes = [getattr(sd, n) for n in dir(sd) if n.endswith("Dialog") and n not in ("FeedbackDialog", "_TextDialog")]
        if len(classes) < 2:
            pytest.skip("no such dialog")
        cls = classes[0 if which == "support_star" else 1]
        try:
            dlg = cls() if which == "support_star" else cls("3.10.0.dev82")
        except TypeError:
            pytest.skip("different constructor")
    dlg.show()
    for _ in range(5):
        QApplication.processEvents()
    for area in dlg.findChildren(QScrollArea):
        assert area.horizontalScrollBar().maximum() == 0, (which, area.horizontalScrollBar().maximum())
    assert dlg.width() <= QApplication.primaryScreen().availableGeometry().width()


@pytest.mark.parametrize("tab", ["display_instrument", "calibration", "profiling", "lut3d", "verification"])
def test_advanced_tabs_have_no_sideways_scroll_at_the_largest_text(window, tab):
    window.resize(916, 864)
    window.show()
    ts.apply("xlarge")
    window._select_tab(tab)
    for _ in range(6):
        QApplication.processEvents()
    window._pin_stack_size_to_current_tab()
    for _ in range(3):
        QApplication.processEvents()
    assert window._scroll_area.horizontalScrollBar().maximum() == 0, (tab, window._scroll_area.horizontalScrollBar().maximum())


@pytest.mark.parametrize("width,level", [(766, "normal"), (766, "xlarge"), (1300, "normal")])
def test_sleep_option_text_is_never_squeezed_or_centred(window, monkeypatch, width, level):
    """The option's wrapped label keeps its full height and sits next to the box."""
    from qtpy.QtCore import QPoint

    monkeypatch.setattr(window.worker, "blocks_supported", lambda: (True, ""), raising=False)
    window.resize(width, 864)
    window.show()
    window._select_tab("guide")
    ts.apply(level)
    g = window._guide
    g._reached = 4
    g.go(3)
    g.refresh()
    for _ in range(6):
        QApplication.processEvents()
    window._pin_stack_size_to_current_tab()
    for _ in range(3):
        QApplication.processEvents()
    from qtpy.QtWidgets import QLabel

    label = next(l for l in g.findChildren(QLabel) if l.text() == lang.getstr("awake.keep"))
    assert label.height() >= label.heightForWidth(label.width())
    gap = label.mapTo(g, QPoint(0, 0)).x() - g.awake_cb.mapTo(g, QPoint(g.awake_cb.width(), 0)).x()
    assert gap < 40, gap


def test_text_size_button_on_the_dark_bar_states_its_own_colours(qapp):
    """White text on a transparent fill with an outline: readable whatever the platform style."""
    from DisplayCAL.ui.text_size_menu import TextSizeButton

    btn = TextSizeButton(on_dark_bar=True)
    css = btn.styleSheet()
    assert "color: #ffffff" in css and "background: transparent" in css and "border:" in css


def _settle(window, level):
    window.resize(766, 864)
    window.show()
    window._select_tab("guide")
    ts.apply(level)
    for _ in range(5):
        QApplication.processEvents()
    window._pin_stack_size_to_current_tab()
    for _ in range(3):
        QApplication.processEvents()


def test_brand_banner_keeps_its_height_whatever_the_text_size(window):
    from DisplayCAL.ui.header_banner import HeaderBanner

    heights = {}
    for level in ("normal", "large", "xlarge"):
        _settle(window, level)
        heights[level] = window.findChild(HeaderBanner).height()
    assert len(set(heights.values())) == 1, heights


def test_large_text_gives_the_room_to_the_content(window):
    """The step column becomes a one-row strip: the page gets (nearly) the full width."""
    from qtpy.QtCore import QPoint

    _settle(window, "normal")
    g = window._guide
    normal_w = g.pages.width()
    normal_top = g.pages.mapTo(window, QPoint(0, 0)).y()
    assert not g.rail._compact
    _settle(window, "xlarge")
    assert g.rail._compact and g.rail.height() < 80
    assert g.pages.width() > normal_w + 120
    # the page starts no lower than a strip's height below where it started at Normal
    assert g.pages.mapTo(window, QPoint(0, 0)).y() <= normal_top + 40
    # still reachable and the reader's size is untouched
    assert window._scroll_area.verticalScrollBar().maximum() == 0
    assert ts.factor() == 1.5
