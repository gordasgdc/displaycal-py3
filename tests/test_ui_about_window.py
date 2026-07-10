"""Headless tests for the Qt "About DisplayCAL" dialog.

Exercises ``DisplayCAL.ui.about_window.AboutWindow`` under the shared
offscreen ``QApplication``: the credit-line assembly (``_body_lines``, a pure
helper independent of any live worker/display) and basic window construction.
See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 3, Help menu).
"""

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL.ui import about_window as aw  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    from qtpy.QtWidgets import QApplication

    lang.init()
    app = QApplication.instance() or QApplication([])
    yield app


def test_body_lines_include_app_and_argyll_credits(qapp):
    worker = SimpleNamespace(argyll_version_string="2.3.1")
    lines = aw.AboutWindow._body_lines(worker)
    joined = "\n".join(line for line in lines if line is not None)
    assert "DisplayCAL" in joined
    assert "2.3.1" in joined
    assert "ArgyllCMS" in joined
    assert "Graeme Gill" in joined


def test_body_lines_without_worker_falls_back_to_zero_version(qapp):
    lines = aw.AboutWindow._body_lines(None)
    joined = "\n".join(line for line in lines if line is not None)
    assert "0.0.0" in joined


def test_body_lines_include_python_and_qt_binding(qapp):
    lines = aw.AboutWindow._body_lines(None)
    joined = "\n".join(line for line in lines if line is not None)
    assert "Python" in joined
    assert aw.QT_API_NAME in joined


def test_body_lines_include_icon_credits(qapp):
    lines = aw.AboutWindow._body_lines(None)
    joined = "\n".join(line for line in lines if line is not None)
    assert "Apricity" in joined
    assert "Suru" in joined
    assert "GNOME" in joined


def test_translator_credits_group_by_author():
    aw.lang.LDICT.clear()
    aw.lang.LDICT["en"] = {"!author": "A. Author", "!language": "English"}
    aw.lang.LDICT["de"] = {"!author": "A. Author", "!language": "Deutsch"}
    aw.lang.LDICT["fr"] = {"!author": "F. Other", "!language": "Français"}
    try:
        credits = aw._translator_credits()
    finally:
        lang.init()
    assert "English, Deutsch - A. Author" in credits
    assert "Français - F. Other" in credits


def test_about_window_constructs_and_shows(qapp):
    window = aw.AboutWindow(None)
    window.show()
    assert window.windowTitle() == lang.getstr("menu.about")
    window.close()


def test_about_window_banner_is_taller_than_header_bar(qapp):
    # The dialog is narrow enough that the tagline wraps to two lines; the
    # banner must be tall enough for that wrap to clear the wordmark artwork
    # instead of overlapping it (see the module's __init__ comment).
    window = aw.AboutWindow(None)
    banner = window.findChild(aw.HeaderBanner)
    assert banner is not None
    assert banner.height() == 2 * aw.HEADER_BANNER_SIZE[1]
    window.close()
