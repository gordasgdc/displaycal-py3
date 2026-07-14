"""Headless tests for the Qt CCMX/CCSS plot window and its MainWindow wiring.

Exercise ``DisplayCAL.ui.ccxx_plot_window.CCXXPlotWindow`` and
``DisplayCAL.ui.plot.ccxx.CCXXPlotWidget`` under the shared offscreen
``QApplication``: construction from a CCMX/CCSS ``CGATS``, the CCSS-only
toggle button switching between the "ccxx" and CIE xy views, and
``MainWindow.colorimeter_correction_info_btn_handler``'s guard clauses and
window-caching. No display or instrument is needed; the CCSS case runs
Argyll's ``spec2cie`` for real (skipped if Argyll isn't installed). See
``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (``CCXXPlot`` visualization).
"""

import os

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL import config  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL.cgats import CGATS  # noqa: E402
from DisplayCAL.config import setcfg  # noqa: E402
from DisplayCAL.worker import Worker  # noqa: E402
from DisplayCAL.worker_base import get_argyll_util  # noqa: E402

CCMX_TEXT = (
    "CCMX\n\n"
    'DESCRIPTOR "Colorimeter Correction Matrix"\n'
    'DISPLAY "Test LCD"\n'
    'REFERENCE "i1 Pro"\n'
    'COLOR_REP "XYZ"\n\n'
    "NUMBER_OF_FIELDS 3\n"
    "BEGIN_DATA_FORMAT\n"
    "XYZ_X XYZ_Y XYZ_Z\n"
    "END_DATA_FORMAT\n\n"
    "NUMBER_OF_SETS 3\n"
    "BEGIN_DATA\n"
    "1.02 0.01 0.02\n"
    "0.01 0.99 0.03\n"
    "0.02 0.02 1.01\n"
    "END_DATA\n"
)

CCSS_PATH = os.path.join(
    os.path.dirname(__file__),
    "data",
    "icc",
    "Dell, DELL UP2516D (i1 Pro 2) 08.2020.ccss",
)

needs_argyll = pytest.mark.skipif(
    not get_argyll_util("spec2cie"), reason="Argyll spec2cie not installed"
)


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
def ccmx_path(tmp_path):
    path = tmp_path / "test.ccmx"
    path.write_text(CCMX_TEXT)
    return str(path)


class TestCCXXPlotWindowCcmx:
    def test_no_toggle_button_for_matrix_correction(self, qapp, ccmx_path):
        from DisplayCAL.ui.ccxx_plot_window import CCXXPlotWindow

        cgats = CGATS(ccmx_path)
        win = CCXXPlotWindow(cgats)
        try:
            assert win.toggle_btn is None
            assert "matrix" in win.windowTitle() or "Matrix" in win.windowTitle()
        finally:
            win.close()

    def test_plot_widget_has_flower_data(self, qapp, ccmx_path):
        from DisplayCAL.ui.ccxx_plot_window import CCXXPlotWindow

        cgats = CGATS(ccmx_path)
        win = CCXXPlotWindow(cgats)
        try:
            assert win.plot._data is not None
            assert win.plot._mode == "ccxx"
        finally:
            win.close()


@needs_argyll
class TestCCXXPlotWindowCcss:
    def test_toggle_button_present_and_switches_modes(self, qapp):
        from DisplayCAL.ui.ccxx_plot_window import CCXXPlotWindow

        # dry_run can leak True from an unrelated test sharing this xdist
        # worker process (pre-existing pollution, see
        # qt-test-suite-order-dependent-flakes); force it off so spec2cie
        # actually runs.
        setcfg("dry_run", 0)
        cgats = CGATS(CCSS_PATH)
        win = CCXXPlotWindow(cgats, Worker())
        try:
            assert win.toggle_btn is not None
            assert win._mode == "ccxx"
            win._toggle()
            assert win._mode == "cie"
            win._toggle()
            assert win._mode == "ccxx"
        finally:
            win.close()


class TestMainWindowHandler:
    @pytest.fixture
    def main_window(self, qapp, monkeypatch):
        from DisplayCAL.ui.main_window import MainWindow
        from DisplayCAL.worker import Worker

        def fake_enumerate(self, *args, **kwargs):
            self.displays = ["DELL U2413 @ 0, 0, 1920x1080 [PRIMARY]"]
            self.instruments = ["i1 DisplayPro, ColorMunki Display"]

        monkeypatch.setattr(Worker, "enumerate_displays_and_ports", fake_enumerate)
        # MainWindow embeds a measurement_report panel (verification/report
        # tab), whose __init__ unconditionally calls
        # self.worker.set_argyll_version("xicclu"). The real implementation
        # shells out to `xicclu -?` with a 30s timeout, which reliably eats
        # the full 30s on CI instead of returning fast (no real
        # instrument/hardware to probe).
        monkeypatch.setattr(Worker, "set_argyll_version", lambda self, *a, **k: None)
        saved = dict(config.CFG["Default"])
        win = MainWindow()
        try:
            yield win
        finally:
            win.close()
            config.CFG["Default"] = saved

    def test_no_file_selected_is_a_no_op(self, main_window):
        setcfg("colorimeter_correction_matrix_file", "")
        main_window.colorimeter_correction_info_btn_handler()
        assert main_window._ccxx_plot_windows == {}

    def test_missing_file_is_a_no_op(self, main_window, tmp_path):
        missing = tmp_path / "does-not-exist.ccmx"
        setcfg("colorimeter_correction_matrix_file", f":{missing}")
        main_window.colorimeter_correction_info_btn_handler()
        assert main_window._ccxx_plot_windows == {}

    def test_opens_and_caches_the_plot_window(self, main_window, ccmx_path):
        setcfg("colorimeter_correction_matrix_file", f":{ccmx_path}")
        main_window.colorimeter_correction_info_btn_handler()
        assert len(main_window._ccxx_plot_windows) == 1
        window = next(iter(main_window._ccxx_plot_windows.values()))
        assert window.isVisible()

        # Re-invoking with the same file re-shows the cached window instead
        # of opening a second one (mirrors wx's ``ccxx_plot_windows`` cache).
        main_window.colorimeter_correction_info_btn_handler()
        assert len(main_window._ccxx_plot_windows) == 1
