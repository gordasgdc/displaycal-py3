"""Help -> Diagnostic and support (offscreen)."""

import os
import zipfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("qtpy")
from test_ui_main_window import _init_config, qapp  # noqa: E402,F401

from DisplayCAL import diagnostics as dg  # noqa: E402
from DisplayCAL.ui import diagnostic_dialog as dd  # noqa: E402


@pytest.fixture
def app(qapp, _init_config):  # noqa: F811
    from DisplayCAL import localization

    localization.init()
    return qapp


def _cats(tmp_path):
    log = tmp_path / "a.log"
    log.write_text("hello /Users/someone/x\n")
    ti3 = tmp_path / "c.ti3"
    ti3.write_text("DATA")
    return [
        dg.Category("versions", True, False, []),
        dg.Category("logs", True, False, [str(log)]),
        dg.Category("measurements", False, True, [str(ti3)]),
        dg.Category("profile", False, True, []),
    ]


def test_export_dialog_shows_categories_and_defaults(app, tmp_path):
    dlg = dd.ExportDialog(None, None, _cats(tmp_path))
    assert dlg.selected() == {"versions", "logs"}  # optional ones off by default
    assert not dlg.boxes["profile"].isEnabled()  # nothing available -> disabled
    assert dlg.redact_cb.isChecked()


def test_export_writes_zip_with_chosen_categories(app, tmp_path):
    dlg = dd.ExportDialog(None, None, _cats(tmp_path))
    dlg.boxes["measurements"].setChecked(True)
    dest = str(tmp_path / "pkg.zip")
    manifest = dlg.export_to(dest)
    with zipfile.ZipFile(dest) as z:
        names = z.namelist()
    assert "measurements/c.ti3" in names and "logs/a.log" in names
    assert manifest["text_redacted"] is True
    assert dlg.saved_path == dest


def test_diagnostic_dialog_has_versions_logs_and_send_explanation(app, monkeypatch):
    opened = []
    monkeypatch.setattr(dd, "launch_file", lambda p: opened.append(p))
    dlg = dd.DiagnosticDialog(None)
    assert "Application" in dlg.versions.toPlainText()
    dlg.open_logs()
    assert opened and os.path.isdir(opened[0])
    assert dlg.issue_btn.text() and dlg.export_btn.text()


def test_debug_toggle_is_temporary_and_visible(app, monkeypatch):
    calls = []
    monkeypatch.setattr(dd.diagnostics, "set_debug", lambda on: calls.append(on))
    dlg = dd.DiagnosticDialog(None)
    dlg.debug_cb.setChecked(True)
    assert calls == [True]
