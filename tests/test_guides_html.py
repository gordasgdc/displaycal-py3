"""The guide engine: markup conversion, chapters, contents and hidden page tokens (no browser)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "docs", "guides"))

import _engine_html as eng  # noqa: E402

CONTENT = {
    "title": "Guide", "subtitle": "Sub", "note": "n", "toc_title": "Contents", "footer": "foot",
    "sections": [
        {"h": "One", "blocks": [("p", "A <b>b</b> <font color=\"#d4147a\">c</font>"), ("h2", "Sub one"),
                                 ("steps", ["x", "y"]), ("opt", (("A", "B"), [("k", "v")])),
                                 ("warn", ("T", "body"))]},
        {"h": "Two", "blocks": [("wcv", {"n": 1, "labels": ("Do", "Why", "Check", "Limit", "Step"), "fig": "f",
                                         "title": "Step one", "purpose": "p", "img": "none.png",
                                         "do": ["d"], "why": ["w"], "check": ["c"], "limit": "l"})]},
    ],
}


def test_markup_converts_reportlab_font_tags():
    assert eng._markup('<font color="#d4147a">x</font>') == '<span style="color:#d4147a">x</span>'


def test_html_has_chapters_tokens_and_contents():
    html = eng.render_html(CONTENT, "en", {"c1": 3, "h1_0": 4, "c2": 5, "h2_0": 5})
    assert html.count('class="chap"') == 2
    assert "§c1§" in html and "§h1_0§" in html and "§h2_0§" in html
    assert '<span class="p">5</span>' in html
    assert 'class="call warn"' in html and "ol class=\"steps\"" in html
    assert "Limit" in html


def test_final_render_has_no_tokens():
    html = eng.render_html(CONTENT, "en", {}, tokens=False)
    assert "§" not in html


def test_fonts_are_static_instances_with_real_text_mapping():
    for name in ("Archivo-400.ttf", "Archivo-800.ttf", "Archivo-800-wide.ttf", "B612Mono-Regular.ttf"):
        assert os.path.isfile(os.path.join(eng.FONTS, name))
