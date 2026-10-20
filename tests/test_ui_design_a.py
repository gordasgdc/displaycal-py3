"""The proof-sheet visual system: contrast of the tokens, bundled fonts, widgets."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("qtpy")

from qtpy.QtGui import QColor  # noqa: E402

from DisplayCAL.ui import design_a  # noqa: E402


def _lum(c: QColor) -> float:
    def ch(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())


def _ratio(a: str, b: str) -> float:
    la, lb = _lum(QColor(a)), _lum(QColor(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("tokens", [design_a.LIGHT, design_a.DARK], ids=["light", "dark"])
def test_text_colours_reach_aa_on_the_sheet_and_on_fields(tokens):
    for name in ("ink", "ink2", "ok", "warn", "bad"):
        for ground in (tokens.sheet, tokens.inset):
            assert _ratio(getattr(tokens, name), ground) >= 4.5, (name, ground)
    assert _ratio(tokens.patch_ink, tokens.patch_bg) >= 7
    assert _ratio(tokens.focus, tokens.sheet) >= 3  # a focus ring needs 3:1


def test_fonts_are_bundled_and_load(qapp):
    fams = design_a.load_fonts()
    assert fams["sans"] and "Archivo" in fams["sans"]
    assert fams["mono"] and "B612" in fams["mono"]


def test_application_sheet_covers_the_common_controls():
    css = design_a.global_qss(design_a.LIGHT)
    for needle in ("QPushButton", "QComboBox", "QCheckBox::indicator", "QRadioButton::indicator",
                   "QSlider", "QScrollBar", "QMenu", "QTabBar", 'QPushButton[primary="true"]'):
        assert needle in css
    assert design_a.LIGHT.patch_bg in css


def test_process_colours_are_the_proof_strip():
    assert design_a.STRIP[:4] == (design_a.CYAN, design_a.MAGENTA, design_a.YELLOW, design_a.KEY)
    assert len(design_a.STRIP) == 32


def test_blocks_bar_follows_the_plan(qapp):
    bar = design_a.BlocksBar()
    bar.set_plan(10986, 22, 500)
    assert len(bar._counts) == 22 and sum(bar._counts) >= 10986 - 22
    bar.set_plan(34, 1, 34)
    assert bar._counts == [34]
    bar.set_plan(0, 1, 0)
    assert bar._counts == []
