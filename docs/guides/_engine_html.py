#!/usr/bin/env python3
"""Motorul HTML -> PDF al ghidurilor DisplayCAL-CG, în Direcția A «Foaia de probă».

Conținutul rămâne cel declarativ din ghid_ro.py / ghid_en.py / ghid_es.py
(blocuri p / h2 / ul / code / img / steps / opt / info / warn / ok / pagebreak).
Aici doar se așază: o pagină A4 = o foaie de probă (slug mono, bandă de control,
cap de capitol cu numeral mare, figuri cu ținte de registru, tabele cu antet negru).
Randarea o face Brave headless (--print-to-pdf); cuprinsul își află numerele de
pagină dintr-o primă trecere (textul fiecărui titlu se caută în PDF).

Ruleaza: python3 generate_guides_html.py   (vezi acolo)
"""
from __future__ import annotations

import html
import os
import re
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.abspath(os.path.join(HERE, "..", "..", "DisplayCAL", "theme", "fonts"))
IMG_DIR = os.path.join(HERE, "img")
BRAVE = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"

STRIP = [
    "#00a3e0", "#d4147a", "#ffd400", "#16171a", "#e8312f", "#00a651", "#2e3192",
    "#6fc7ec", "#ea7fb3", "#ffea7a", "#f6f6f4", "#e0e0de", "#c7c7c5", "#a9a9a7",
    "#8c8c8a", "#707070", "#555555", "#3b3b3b", "#16171a", "#e8312f", "#ff8a3d",
    "#ffd400", "#7ed957", "#00a651", "#00b4a6", "#00a3e0", "#4a6fd8", "#2e3192",
    "#7a3fb0", "#d4147a", "#8f2a2a", "#2f3b4a",
]


def _strip_gradient() -> str:
    n = len(STRIP)
    stops = ",".join(f"{c} {i * 100 / n:.4f}% {(i + 1) * 100 / n:.4f}%" for i, c in enumerate(STRIP))
    return f"linear-gradient(90deg,{stops})"


CSS = """
@font-face{font-family:"Archivo";src:url("file://@@fonts@@/Archivo-VF.ttf");font-weight:100 900;font-stretch:62% 125%}
@font-face{font-family:"B612 Mono";src:url("file://@@fonts@@/B612Mono-Regular.ttf");font-weight:400}
@font-face{font-family:"B612 Mono";src:url("file://@@fonts@@/B612Mono-Bold.ttf");font-weight:700}
@page{size:210mm 297mm;margin:25mm 15mm 19mm 15mm;
  @top-left{content:"@@top_left@@";font:700 7.2pt "B612 Mono";letter-spacing:.07em;color:#16171a;vertical-align:top;padding-top:11mm}
  @top-right{content:"@@top_right@@";font:400 7.2pt "B612 Mono";letter-spacing:.07em;color:#4a4c52;vertical-align:top;padding-top:11mm}
  @bottom-left{content:"@@foot@@";font:400 7pt "B612 Mono";letter-spacing:.07em;color:#4a4c52;vertical-align:bottom;padding-bottom:9mm}
  @bottom-right{content:counter(page);font:700 8pt "B612 Mono";color:#16171a;vertical-align:bottom;padding-bottom:9mm}
  background:#f6f6f4 @@strip@@ no-repeat 15mm 18mm / calc(100% - 30mm) 3.2mm}
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;font:400 10pt/1.5 "Archivo",sans-serif;color:#16171a;background:transparent}
.mono{font-family:"B612 Mono",monospace;letter-spacing:.07em;text-transform:uppercase}
a{color:#16171a;text-decoration:underline;text-underline-offset:.5mm}
b{font-weight:700}
.chap{break-before:page}
.chap:first-of-type{break-before:auto}
.head{display:flex;gap:6mm;align-items:flex-end;border-bottom:.45mm solid #16171a;padding-bottom:3.6mm;margin:0 0 5mm}
.num{font:800 50pt/.78 "Archivo";letter-spacing:-.04em}
h1{font:800 22pt/1.04 "Archivo";font-stretch:106%;letter-spacing:-.025em;margin:0;break-after:avoid}
h2{font:800 13pt/1.2 "Archivo";letter-spacing:-.01em;margin:6mm 0 2.2mm;padding-bottom:1.4mm;border-bottom:.2mm solid rgba(22,23,26,.35);break-after:avoid}
p{margin:0 0 2.8mm;orphans:3;widows:3}
ul{margin:0 0 3mm;padding:0;list-style:none}
ul li{position:relative;padding-left:5mm;margin:0 0 1.4mm}
ul li::before{content:"";position:absolute;left:.6mm;top:1.9mm;width:1.8mm;height:1.8mm;background:#16171a}
pre{font:400 8.4pt/1.45 "B612 Mono",monospace;background:#fdfdfc;border:.2mm solid #16171a;padding:2.6mm 3.2mm;margin:0 0 3.4mm;white-space:pre-wrap;word-break:break-word}
ol.steps{list-style:none;margin:0 0 4mm;padding:0;counter-reset:s}
ol.steps li{counter-increment:s;position:relative;padding:0 0 2.6mm 10mm;break-inside:avoid}
ol.steps li::before{content:counter(s);position:absolute;left:0;top:-.2mm;width:6.4mm;height:6.4mm;border:.3mm solid #16171a;border-radius:50%;font:700 7.6pt/6.1mm "B612 Mono";text-align:center;background:#fdfdfc}
.call{border:.25mm solid #16171a;background:#fdfdfc;margin:3mm 0 4mm;break-inside:avoid}
.call .tag{display:inline-block;font:700 7pt "B612 Mono";letter-spacing:.08em;text-transform:uppercase;padding:1.1mm 2.6mm;background:#16171a;color:#f6f6f4}
.call.warn .tag{background:#d4147a}
.call.ok .tag{background:#00a651;color:#fff}
.call .body{padding:2.2mm 3.2mm 1.2mm;font-size:9.4pt;line-height:1.45}
.call.warn{border-style:dashed}
table.opt{width:100%;border-collapse:collapse;margin:0 0 5mm;font-size:9pt;line-height:1.4}
table.opt th{background:#16171a;color:#f6f6f4;font:700 7.2pt "B612 Mono";letter-spacing:.08em;text-transform:uppercase;text-align:left;padding:1.8mm 2.4mm}
table.opt td{padding:2mm 2.4mm;border-bottom:.2mm solid rgba(22,23,26,.35);vertical-align:top}
table.opt td:first-child{font-weight:700;width:34%}
table.opt tr{break-inside:avoid}
figure{margin:3mm 0 5mm;break-inside:avoid}
figure .fig{position:relative;background:#fff;box-shadow:0 0 0 .25mm #16171a;line-height:0}
figure img{width:100%;display:block}
figure .reg{position:absolute;width:5mm;height:5mm;border:.25mm solid #16171a;border-radius:50%;background:#f6f6f4}
figure .reg::before,figure .reg::after{content:"";position:absolute;background:#16171a}
figure .reg::before{left:-1.4mm;right:-1.4mm;top:2.3mm;height:.25mm}figure .reg::after{top:-1.4mm;bottom:-1.4mm;left:2.3mm;width:.25mm}
figcaption{display:flex;gap:3mm;margin-top:1.8mm;color:#4a4c52;font-size:8pt;line-height:1.4}
figcaption .mono{color:#16171a;white-space:nowrap;font-size:7pt;padding-top:.3mm}
.tocp{break-before:page}
.toc{list-style:none;margin:6mm 0 0;padding:0}
.toc li::before{content:none}
.toc li{padding-left:0}
.toc li{display:flex;align-items:baseline;gap:3mm;padding:1.6mm 0;border-bottom:.2mm solid rgba(22,23,26,.3)}
.toc li.l1{font-weight:800;font-size:11pt;margin-top:2.4mm;border-bottom:.3mm solid #16171a}
.toc li.l2{padding-left:11mm;font-size:9.2pt;color:#4a4c52}
.toc .n{font:700 8pt "B612 Mono";width:8mm}
.toc .t{flex:1}
.toc .p{font:700 8pt "B612 Mono"}
.title h1{font-size:30pt;margin-top:4mm}
.title .sub{font:500 13pt/1.35 "Archivo";margin:4mm 0 1mm;max-width:150mm}
.title .note{color:#4a4c52;font-size:9pt}
.limit{margin:4mm 0;padding:2.6mm 3.4mm;border:.25mm dashed #6a6c72;font-size:8.8pt;color:#4a4c52}
"""


def _markup(text: str) -> str:
    """Reportlab-style inline markup (<b>, <i>, <font color>) -> HTML."""
    out = re.sub(r'<font\s+color="?(#[0-9a-fA-F]{3,6})"?>', r'<span style="color:\1">', text)
    out = out.replace("</font>", "</span>")
    return out.replace("&amp;nbsp;", "&nbsp;")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", s).lower()).strip("-")


def _fig(block_args: tuple, ctx: dict) -> str:
    filename, caption = block_args
    path = os.path.join(ctx["img_dir"], filename)
    if not os.path.exists(path):
        return ""
    ctx["fig"] = ctx.get("fig", 0) + 1
    label = f"{ctx['chapter']}.{ctx['fig_in']}"
    ctx["fig_in"] += 1
    return (
        f'<figure><div class="fig"><img src="file://{html.escape(path)}" alt="">'
        '<span class="reg" style="right:2.2mm;top:2.2mm"></span>'
        '<span class="reg" style="left:2.2mm;bottom:2.2mm"></span></div>'
        f'<figcaption><span class="mono">{ctx["fig_word"]} {label}</span><span>{_markup(caption)}</span></figcaption></figure>'
    )


def _block(block: tuple, ctx: dict) -> str:
    kind = block[0]
    if kind == "p":
        return f"<p>{_markup(block[1])}</p>"
    if kind == "h2":
        ctx["h2s"].append((ctx["chapter"], block[1]))
        return f"<h2>{_markup(block[1])}</h2>"
    if kind == "ul":
        return "<ul>" + "".join(f"<li>{_markup(t)}</li>" for t in block[1]) + "</ul>"
    if kind == "code":
        return f"<pre>{_markup(block[1])}</pre>"
    if kind == "img":
        return _fig(block[1], ctx)
    if kind == "steps":
        return '<ol class="steps">' + "".join(f"<li>{_markup(t)}</li>" for t in block[1]) + "</ol>"
    if kind == "opt":
        header, rows = block[1]
        head = f"<tr><th>{_markup(header[0])}</th><th>{_markup(header[1])}</th></tr>"
        body = "".join(f"<tr><td>{_markup(a)}</td><td>{_markup(b)}</td></tr>" for a, b in rows)
        return f'<table class="opt">{head}{body}</table>'
    if kind in ("info", "warn", "ok"):
        tag, text = block[1]
        return f'<div class="call {kind}"><span class="tag">{_markup(tag)}</span><div class="body">{_markup(text)}</div></div>'
    if kind == "pagebreak":
        return '<div style="break-after:page"></div>'
    return ""


def render_html(content: dict, lang: str, toc_pages: dict | None = None, img_dir: str = IMG_DIR) -> str:
    """The whole interior (title page, contents, chapters) as one HTML document."""
    ctx = {
        "h2s": [], "img_dir": img_dir, "chapter": 0, "fig_in": 1,
        "fig_word": {"ro": "Fig.", "en": "Fig.", "es": "Fig."}.get(lang, "Fig."),
    }
    chapters = []
    for idx, sec in enumerate(content["sections"], 1):
        ctx["chapter"], ctx["fig_in"] = idx, 1
        body = "".join(_block(b, ctx) for b in sec["blocks"])
        chapters.append(
            f'<section class="chap" id="c{idx}"><div class="head"><span class="num">{idx:02d}</span>'
            f"<h1>{_markup(sec['h'])}</h1></div>{body}</section>"
        )
    toc_pages = toc_pages or {}
    toc_rows = []
    for idx, sec in enumerate(content["sections"], 1):
        toc_rows.append(
            f'<li class="l1"><span class="n">{idx:02d}</span><span class="t">{_markup(sec["h"])}</span>'
            f'<span class="p">{toc_pages.get(("c", idx), "")}</span></li>'
        )
        for n, (chap, h) in enumerate([x for x in ctx["h2s"] if x[0] == idx]):
            toc_rows.append(
                f'<li class="l2"><span class="n"></span><span class="t">{_markup(h)}</span>'
                f'<span class="p">{toc_pages.get(("h", idx, n), "")}</span></li>'
            )
    title = (
        '<section class="title"><div class="head"><h1>'
        f"{_markup(content['title'])}</h1></div>"
        f'<p class="sub">{_markup(content["subtitle"])}</p><p class="note">{_markup(content["note"])}</p></section>'
    )
    toc = f'<section class="tocp"><div class="head"><h1>{_markup(content["toc_title"])}</h1></div><ul class="toc">{"".join(toc_rows)}</ul></section>'
    values = {
        "fonts": FONTS,
        "strip": _strip_gradient(),
        "top_left": "DISPLAYCAL-CG",
        "top_right": lang.upper(),
        "foot": content["footer"],
    }
    css = CSS
    for key, value in values.items():
        css = css.replace(f"@@{key}@@", value)
    return (
        f'<!doctype html><html lang="{lang}"><meta charset="utf-8"><title>{html.escape(content["title"])}</title>'
        f"<style>{css}</style><body>{title}{toc}{''.join(chapters)}</body></html>"
    )


def html_to_pdf(html_path: str, pdf_path: str) -> None:
    """Render with headless Brave (Chromium): margin boxes, variable fonts, page breaks."""
    subprocess.run(
        [BRAVE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--run-all-compositor-stages-before-draw", "--virtual-time-budget=20000",
         f"--print-to-pdf={pdf_path}", f"file://{html_path}"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300,
    )


def page_of_titles(pdf_path: str, titles: dict) -> dict:
    """Find the page where each title first appears after the contents page(s)."""
    from pypdf import PdfReader

    reader = PdfReader(pdf_path)
    texts = [re.sub(r"\s+", " ", (p.extract_text() or "")) for p in reader.pages]
    found: dict = {}
    start = 2  # the title page and the contents are never targets
    for key, text in titles.items():
        needle = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()
        for i in range(start, len(texts)):
            if needle and needle in texts[i]:
                found[key] = i + 1
                break
    return found


def build(lang: str, out_path: str, content: dict, img_dir: str = IMG_DIR) -> None:
    """Two passes: lay out, read the page numbers, lay out again with the contents filled."""
    tmp = tempfile.mkdtemp(prefix="guide_")
    h1 = os.path.join(tmp, "g.html")
    pdf1 = os.path.join(tmp, "g1.pdf")
    html_doc = render_html(content, lang, None, img_dir)
    open(h1, "w", encoding="utf-8").write(html_doc)
    html_to_pdf(h1, pdf1)
    titles: dict = {}
    h2_by_chapter: dict = {}
    for idx, sec in enumerate(content["sections"], 1):
        titles[("c", idx)] = sec["h"]
        n = 0
        for b in sec["blocks"]:
            if b[0] == "h2":
                titles[("h", idx, n)] = b[1]
                n += 1
    pages = page_of_titles(pdf1, titles)
    open(h1, "w", encoding="utf-8").write(render_html(content, lang, pages, img_dir))
    html_to_pdf(h1, out_path)
    print(f"OK: {out_path} ({len(pages)} titluri în cuprins)")
