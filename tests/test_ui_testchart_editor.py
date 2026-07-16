"""Tests for the Qt testchart editor's row-editing shortcuts (issue #842).

The wx testchart editor (``wx_testchart_editor.tc_key_handler``) supports
deleting selected patch rows with Delete/Backspace, saving with Ctrl+S, and
inserting a white patch row by double-clicking a row label. None of this was
wired up in the Qt port (``DisplayCAL.ui.tools.testchart_editor``) - these
tests exercise the ported behavior directly against
``TestchartEditorWindow``.
"""

import os

import pytest

from DisplayCAL import config
from DisplayCAL import localization as lang

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from qtpy.QtCore import Qt, QItemSelectionModel  # noqa: E402
from qtpy.QtGui import QKeyEvent  # noqa: E402

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


@pytest.fixture
def window(qapp):
    """A fresh testchart editor window."""
    win = te.TestchartEditorWindow()
    yield win
    win.close()


@pytest.fixture
def loaded(window, tmp_path):
    """The window with a 4-row chart loaded into the grid."""
    path = tmp_path / "test.ti1"
    path.write_bytes(_TI1)
    window.ti1 = CGATS(str(path))
    window._populate_grid()
    window.tc_check()
    return window


def _key_event(key, modifiers=Qt.NoModifier):
    return QKeyEvent(QKeyEvent.KeyPress, key, modifiers)


def test_ctrl_delete_removes_selected_rows(loaded):
    window = loaded
    assert window.grid.rowCount() == 4
    window.grid.selectRow(1)  # the 25% patch
    window.keyPressEvent(_key_event(Qt.Key_Delete, Qt.ControlModifier))
    assert window.grid.rowCount() == 3
    data = window.ti1.queryv1("DATA")
    remaining = sorted(sample.RGB_R for sample in data.values())
    assert remaining == [0.0, 50.0, 100.0]
    assert window.ti1.modified


def test_ctrl_backspace_removes_multiple_selected_rows(loaded):
    window = loaded
    window.grid.selectRow(0)
    window.grid.selectionModel().select(
        window.grid.model().index(2, 0),
        QItemSelectionModel.Select | QItemSelectionModel.Rows,
    )
    window.keyPressEvent(_key_event(Qt.Key_Backspace, Qt.ControlModifier))
    assert window.grid.rowCount() == 2
    data = window.ti1.queryv1("DATA")
    remaining = sorted(sample.RGB_R for sample in data.values())
    assert remaining == [25.0, 100.0]


def test_ctrl_delete_all_rows_clears_chart_instead_of_emptying_it(loaded):
    window = loaded
    window.grid.selectAll()
    window.keyPressEvent(_key_event(Qt.Key_Delete, Qt.ControlModifier))
    assert window.ti1 is None
    assert window.grid.rowCount() == 0


def test_ctrl_delete_with_no_selection_is_a_no_op(loaded):
    window = loaded
    window.grid.clearSelection()
    window.keyPressEvent(_key_event(Qt.Key_Delete, Qt.ControlModifier))
    assert window.grid.rowCount() == 4


def test_plain_delete_without_modifier_is_ignored(loaded):
    """Bare Delete/Backspace is left to the default Qt table-view handling.

    Row deletion mirrors wx's ``tc_key_handler``, which only acts on
    Ctrl/Cmd+Delete or Ctrl/Cmd+Backspace.
    """
    window = loaded
    window.grid.selectRow(1)
    window.keyPressEvent(_key_event(Qt.Key_Delete))
    assert window.grid.rowCount() == 4


def test_ctrl_s_saves_when_filename_exists_and_modified(loaded, monkeypatch):
    window = loaded
    window.ti1.setmodified(True)
    saved = []
    monkeypatch.setattr(window, "tc_save", lambda: saved.append(True))
    monkeypatch.setattr(window, "tc_save_as", lambda *a, **k: saved.append(False))
    window.keyPressEvent(_key_event(Qt.Key_S, Qt.ControlModifier))
    assert saved == [True]


def test_ctrl_s_falls_back_to_save_as_without_filename(window, monkeypatch):
    window.ti1 = CGATS()
    window.ti1.filename = None
    save_as_called = []
    monkeypatch.setattr(window, "tc_save_as", lambda *a, **k: save_as_called.append(1))
    window.keyPressEvent(_key_event(Qt.Key_S, Qt.ControlModifier))
    assert save_as_called == [1]


def test_ctrl_s_does_nothing_when_unmodified(loaded, monkeypatch):
    window = loaded
    window.ti1.setmodified(False)
    calls = []
    monkeypatch.setattr(window, "tc_save", lambda: calls.append("save"))
    monkeypatch.setattr(window, "tc_save_as", lambda *a, **k: calls.append("save_as"))
    window.keyPressEvent(_key_event(Qt.Key_S, Qt.ControlModifier))
    assert calls == []


def test_row_label_double_click_inserts_white_patch_row(loaded):
    window = loaded
    window._on_row_label_dclick(0)
    assert window.grid.rowCount() == 5
    data = window.ti1.queryv1("DATA")
    inserted = data[1]
    assert inserted.RGB_R == inserted.RGB_G == inserted.RGB_B == 100.0
    assert inserted.XYZ_Y == 100.0
