"""Tests for issue #846: the Verification tab's chart-edit button used to
open/edit the wrong testchart.

wx's ``TestchartEditor`` binds each editor instance to a ``cfg`` config key
and a ``parent_set_chart_methodname`` callback (``DisplayCAL/wx_testchart_editor.py``),
so saving a chart from the report's editor retargets
``measurement_report.chart`` (via ``ReportFrame.mr_set_testchart``) rather
than the Profiling tab's ``testchart.file``. The Qt port's
``TestchartEditorWindow`` had no such parameters at all -- these tests
exercise the ported ``cfg``/``chart_selected_callback`` wiring directly.
"""

import os

import pytest

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import getcfg, setcfg

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL.cgats import CGATS  # noqa: E402
from DisplayCAL.ui.tools import testchart_editor as te  # noqa: E402

_TI1 = b"""CTI1

NUMBER_OF_FIELDS 7
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 4
BEGIN_DATA
1 0.000000 0.000000 0.000000 0 0 0
2 25.000000 25.000000 25.000000 5 5 5
3 50.000000 50.000000 50.000000 10 10 10
4 100.000000 100.000000 100.000000 20 20 20
END_DATA
"""


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _init():
    """Config + localization must be live for the localized read-outs."""
    config.initcfg()
    lang.init()
    yield


class _FakeConfirmMessageBox:
    """Stand-in for ``te.QMessageBox`` used by ``_confirm_select_chart``."""

    Question = 0
    AcceptRole = 1
    RejectRole = 2

    clicked_role = None  # "ok" | "cancel", set per-test

    def __init__(self, parent=None):
        self._buttons = {}

    def setWindowTitle(self, title):
        pass

    def setIcon(self, icon):
        pass

    def setText(self, text):
        self.text = text

    def addButton(self, text, role):
        button = (text, role)
        self._buttons[role] = button
        return button

    def exec_(self):
        return None

    def clickedButton(self):
        role = {"ok": self.AcceptRole, "cancel": self.RejectRole}[self.clicked_role]
        return self._buttons[role]


def _loaded_window(qapp, tmp_path, **kwargs):
    window = te.TestchartEditorWindow(**kwargs)
    path = tmp_path / "source.ti1"
    path.write_bytes(_TI1)
    window.ti1 = CGATS(str(path))
    return window


def test_constructor_defaults_match_profiling_tab_chart(qapp):
    window = te.TestchartEditorWindow()
    try:
        assert window.cfg == "testchart.file"
        assert window._chart_selected_callback is None
    finally:
        window.close()


def test_constructor_binds_report_chart_cfg_and_callback(qapp):
    calls = []
    window = te.TestchartEditorWindow(
        cfg="measurement_report.chart",
        chart_selected_callback=calls.append,
    )
    try:
        assert window.cfg == "measurement_report.chart"
        assert window._chart_selected_callback == calls.append
    finally:
        window.close()


def test_save_as_without_callback_does_not_touch_cfg(qapp, tmp_path, monkeypatch):
    """Default (Profiling-tab-style) construction: no confirm dialog, no cfg writes."""
    monkeypatch.setattr(te, "QMessageBox", _FakeConfirmMessageBox)
    setcfg("testchart.file", "auto")
    window = _loaded_window(qapp, tmp_path)
    try:
        target = str(tmp_path / "out.ti1")
        assert window.tc_save_as(target) is True
        assert getcfg("testchart.file") == "auto"
    finally:
        window.close()


def test_save_as_matching_cfg_invokes_callback_without_prompting(
    qapp, tmp_path, monkeypatch
):
    """Saving to the path already active in ``cfg`` calls back with no prompt."""
    monkeypatch.setattr(te, "QMessageBox", _FakeConfirmMessageBox)
    target = str(tmp_path / "report.ti1")
    setcfg("measurement_report.chart", target)
    calls = []
    window = _loaded_window(
        qapp,
        tmp_path,
        cfg="measurement_report.chart",
        chart_selected_callback=calls.append,
    )
    try:
        assert window.tc_save_as(target) is True
        assert calls == [target]
    finally:
        window.close()


def test_save_as_different_path_confirmed_retargets_report_chart(
    qapp, tmp_path, monkeypatch
):
    """Saving elsewhere prompts; confirming updates ``measurement_report.chart``
    and calls back, mirroring wx's ``mr_set_testchart`` wiring."""
    monkeypatch.setattr(te, "QMessageBox", _FakeConfirmMessageBox)
    _FakeConfirmMessageBox.clicked_role = "ok"
    original = str(tmp_path / "original.ti1")
    setcfg("measurement_report.chart", original)
    calls = []
    window = _loaded_window(
        qapp,
        tmp_path,
        cfg="measurement_report.chart",
        chart_selected_callback=calls.append,
    )
    try:
        target = str(tmp_path / "edited.ti1")
        assert window.tc_save_as(target) is True
        assert getcfg("measurement_report.chart") == target
        assert calls == [target]
    finally:
        window.close()


def test_save_as_different_path_declined_leaves_report_chart_untouched(
    qapp, tmp_path, monkeypatch
):
    """Declining the confirm prompt leaves ``measurement_report.chart`` alone
    and never calls back -- the report keeps showing its original chart."""
    monkeypatch.setattr(te, "QMessageBox", _FakeConfirmMessageBox)
    _FakeConfirmMessageBox.clicked_role = "cancel"
    original = str(tmp_path / "original.ti1")
    setcfg("measurement_report.chart", original)
    calls = []
    window = _loaded_window(
        qapp,
        tmp_path,
        cfg="measurement_report.chart",
        chart_selected_callback=calls.append,
    )
    try:
        target = str(tmp_path / "edited.ti1")
        assert window.tc_save_as(target) is True
        assert getcfg("measurement_report.chart") == original
        assert calls == []
    finally:
        window.close()
