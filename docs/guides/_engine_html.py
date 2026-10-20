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
FONTS = os.path.join(HERE, "fonts")  # static instances (a variable font loses its text mapping in PDF)
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
@font-face{font-family:"Archivo";src:url("file://@@fonts@@/Archivo-400.ttf");font-weight:400}
@font-face{font-family:"Archivo";src:url("file://@@fonts@@/Archivo-500.ttf");font-weight:500}
@font-face{font-family:"Archivo";src:url("file://@@fonts@@/Archivo-700.ttf");font-weight:700}
@font-face{font-family:"Archivo";src:url("file://@@fonts@@/Archivo-800.ttf");font-weight:800}
@font-face{font-family:"Archivo Wide";src:url("file://@@fonts@@/Archivo-800-wide.ttf");font-weight:800}
@font-face{font-family:"B612 Mono";src:url("file://@@fonts@@/B612Mono-Regular.ttf");font-weight:400}
@font-face{font-family:"B612 Mono";src:url("file://@@fonts@@/B612Mono-Bold.ttf");font-weight:700}
@page{size:210mm 297mm;margin:24mm 16mm 19mm 16mm;
  @top-left{content:"DisplayCAL-CG";font:700 9pt "Archivo";color:#1d1f24;vertical-align:top;padding-top:10mm}
  @top-right{content:"@@top_right@@";font:500 8pt "Archivo";color:#5b5f68;vertical-align:top;padding-top:10mm}
  @bottom-left{content:"@@foot@@";font:400 8pt "Archivo";color:#5b5f68;vertical-align:bottom;padding-bottom:9mm}
  @bottom-right{content:counter(page);font:700 9pt "Archivo";color:#1d1f24;vertical-align:bottom;padding-bottom:9mm}
  background:#f7f6f3 linear-gradient(90deg,rgba(255,255,255,0),#2e3192 8%,#d4147a 28%,#e8312f 46%,#ffd400 62%,#00a651 80%,#00a3e0 92%,rgba(255,255,255,0)) no-repeat 16mm 17mm / calc(100% - 32mm) .7mm}
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;font:400 10pt/1.5 "Archivo",sans-serif;color:#1d1f24;background:transparent}
.mono{font-family:"Archivo";font-weight:600}
a{color:#1d1f24;text-decoration:underline;text-underline-offset:.5mm}
b{font-weight:700}
.tok{font-size:1px;color:transparent;position:absolute}
.chap{break-before:page}
.chap:first-of-type{break-before:auto}
.head{display:flex;gap:6mm;align-items:flex-end;padding-bottom:2mm;margin:0 0 4mm}
.num{display:none}
h1{font:800 22pt/1.04 "Archivo Wide","Archivo";letter-spacing:-.025em;margin:0;break-after:avoid}
h2{font:800 13pt/1.2 "Archivo";letter-spacing:-.01em;margin:6mm 0 2.2mm;break-after:avoid}
p{margin:0 0 2.8mm;orphans:3;widows:3}
ul{margin:0 0 3mm;padding:0;list-style:none}
ul li{position:relative;padding-left:5mm;margin:0 0 1.4mm}
ul li::before{content:"";position:absolute;left:.6mm;top:2.1mm;width:1.6mm;height:1.6mm;border-radius:50%;background:#2c2f36}
pre{font:400 8.4pt/1.45 "B612 Mono",monospace;background:#fbfbf9;border:.2mm solid rgba(29,31,36,.16);border-radius:3mm;padding:2.6mm 3.4mm;margin:0 0 3.4mm;white-space:pre-wrap;word-break:break-word}
ol.steps{list-style:none;margin:0 0 4mm;padding:0;counter-reset:s}
ol.steps li{counter-increment:s;position:relative;padding:0 0 2.6mm 10mm;break-inside:avoid}
ol.steps li::before{content:counter(s);position:absolute;left:0;top:-.2mm;width:6.4mm;height:6.4mm;border:.3mm solid #2c2f36;border-radius:50%;font:700 8pt/6.1mm "Archivo";text-align:center;background:#fbfbf9}
.call{border:.2mm solid rgba(29,31,36,.16);border-radius:3.5mm;background:#fbfbf9;margin:3mm 0 4mm;break-inside:avoid;overflow:hidden}
.call .tag{display:inline-block;font:700 8pt "Archivo";padding:1.2mm 3mm;margin:2mm 0 0 2.4mm;border-radius:5mm;background:#2c2f36;color:#f7f6f3}
.call.warn .tag{background:#d4147a}
.call.ok .tag{background:#00a651;color:#fff}
.call .body{padding:2.2mm 3.2mm 1.2mm;font-size:9.4pt;line-height:1.45}
.call.warn{border-color:rgba(179,18,31,.45)}
table.opt{width:100%;border-collapse:collapse;margin:0 0 5mm;font-size:9pt;line-height:1.4}
table.opt th{background:#2c2f36;color:#f7f6f3;font:700 8pt "Archivo";text-align:left;padding:2mm 2.6mm}
table.opt td{padding:2mm 2.4mm;border-bottom:.2mm solid rgba(22,23,26,.35);vertical-align:top}
table.opt td:first-child{font-weight:700;width:34%}
table.opt tr{break-inside:avoid}
figure{margin:3mm 0 5mm;break-inside:avoid}
figure .fig{position:relative;background:#fff;border-radius:3mm;overflow:hidden;box-shadow:0 0 0 .2mm rgba(29,31,36,.18),0 1.2mm 3mm rgba(29,31,36,.14);line-height:0}
figure img{width:100%;display:block}
figure .reg{position:absolute;width:5mm;height:5mm;border:.25mm solid #1d1f24;border-radius:50%;background:#f6f6f4}
figure .reg::before,figure .reg::after{content:"";position:absolute;background:#1d1f24}
figure .reg::before{left:-1.4mm;right:-1.4mm;top:2.3mm;height:.25mm}figure .reg::after{top:-1.4mm;bottom:-1.4mm;left:2.3mm;width:.25mm}
figcaption{display:flex;gap:3mm;margin-top:1.8mm;color:#4a4c52;font-size:8pt;line-height:1.4}
figcaption .mono{color:#1d1f24;white-space:nowrap;font-size:8pt}
.wcv{break-before:page}
.wcv .slugline{color:#5b5f68;font-size:8.4pt}
.wcv .slugline b{color:#1d1f24}
h2.wcvh{display:flex;align-items:baseline;gap:4mm;font:800 20pt/1.05 "Archivo";letter-spacing:-.025em;padding-bottom:1mm;margin:2mm 0 3mm}
h2.wcvh .wn{display:none}
.purpose{font:500 10.6pt/1.4 "Archivo";margin:0 0 3mm}
.three{display:grid;grid-template-columns:repeat(3,1fr);gap:5mm;margin-top:3mm}
.blk{border-top:.25mm solid rgba(29,31,36,.25);padding-top:2.2mm}
.blk h3{font:700 9pt "Archivo";margin:0 0 2mm;display:flex;align-items:center;gap:2mm}
.blk h3 i{width:5mm;height:5mm;border-radius:50%;background:#2c2f36;color:#f7f6f3;border:0;display:grid;place-items:center;font-style:normal;font-size:6.8pt}
.blk p{margin:0 0 1.6mm;font-size:8.8pt;line-height:1.4}
.blk.why,.blk.chk{border-top-color:#8a8c92}
.tocp{break-before:page}
.toc{list-style:none;margin:6mm 0 0;padding:0}
.toc li::before{content:none}
.toc li{padding-left:0}
.toc li{display:flex;align-items:baseline;gap:3mm;padding:1.6mm 0;border-bottom:.2mm solid rgba(29,31,36,.14)}
.toc li.l1{font-weight:800;font-size:11pt;margin-top:2.4mm}
.toc li.l2{padding-left:11mm;font-size:9.2pt;color:#4a4c52}
.toc .n{font:700 8pt "B612 Mono";width:8mm}
.toc .t{flex:1}
.toc .p{font:700 8pt "B612 Mono"}
.title h1{font-size:30pt;margin-top:4mm}
.title .sub{font:500 13pt/1.35 "Archivo";margin:4mm 0 1mm;max-width:150mm}
.title .note{color:#4a4c52;font-size:9pt}
.limit{margin:4mm 0;padding:2.6mm 3.6mm;border:.2mm solid rgba(29,31,36,.2);border-radius:3.5mm;font-size:8.8pt;color:#4a4c52}
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
        ''
        '</div>'
        f'<figcaption><span class="mono">{ctx["fig_word"]} {label}</span><span>{_markup(caption)}</span></figcaption></figure>'
    )


def _tok(ctx: dict, title: str) -> str:
    """Register a contents entry; the hidden token lets pass 2 find its page."""
    n = sum(1 for c, _ in ctx["h2s"] if c == ctx["chapter"])
    ctx["h2s"].append((ctx["chapter"], title))
    return f'<span class="tok">§h{ctx["chapter"]}_{n}§</span>'


def _wcv(d: dict, ctx: dict) -> str:
    """One guided step as a page: head, figure, then what you do / why / what you check."""
    do_l, why_l, chk_l, lim_l, step_w = d["labels"]
    path = os.path.join(ctx["img_dir"], d["img"])
    fig = ""
    if os.path.exists(path):
        fig = (
            f'<figure><div class="fig"><img src="file://{html.escape(path)}" alt="">'
            ''
            '</div>'
            f'<figcaption><span class="mono">{ctx["fig_word"]} {ctx["chapter"]}.{d["n"]}</span>'
            f'<span>{_markup(d["fig"])}</span></figcaption></figure>'
        )
    def col(cls: str, label: str, items: list, mark: str) -> str:
        lis = "".join(f"<p><b>{i}.</b> {_markup(t)}</p>" if cls == "do" else f"<p>{_markup(t)}</p>" for i, t in enumerate(items, 1))
        return f'<div class="blk {cls}"><h3><i>{mark}</i>{label}</h3>{lis}</div>'
    limit = f'<div class="limit"><span class="mono">{lim_l}</span> {_markup(d["limit"])}</div>' if d.get("limit") else ""
    tok = _tok(ctx, d["title"])
    return (
        f'<div class="wcv">{tok}<div class="slugline mono"><b>{step_w} {d["n"]} / 5</b></div>'
        f'<h2 class="wcvh"><span class="wn">{d["n"]:02d}</span>{_markup(d["title"])}</h2>'
        f'<p class="purpose">{_markup(d["purpose"])}</p>{fig}'
        f'<div class="three">{col("do", do_l, d["do"], "↗")}{col("why", why_l, d["why"], "?")}{col("chk", chk_l, d["check"], "✓")}</div>{limit}</div>'
    )


def _block(block: tuple, ctx: dict) -> str:
    kind = block[0]
    if kind == "p":
        return f"<p>{_markup(block[1])}</p>"
    if kind == "h2":
        return f"<h2>{_tok(ctx, block[1])}{_markup(block[1])}</h2>"
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
    if kind == "wcv":
        return _wcv(block[1], ctx)
    if kind == "pagebreak":
        return '<div style="break-after:page"></div>'
    return ""


def render_html(content: dict, lang: str, toc_pages: dict | None = None, img_dir: str = IMG_DIR, tokens: bool = True) -> str:
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
            f'<section class="chap" id="c{idx}"><span class="tok">§c{idx}§</span><div class="head"><span class="num">{idx:02d}</span>'
            f"<h1>{_markup(sec['h'])}</h1></div>{body}</section>"
        )
    toc_pages = toc_pages or {}
    toc_rows = []
    for idx, sec in enumerate(content["sections"], 1):
        toc_rows.append(
            f'<li class="l1"><span class="n">{idx:02d}</span><span class="t">{_markup(sec["h"])}</span>'
            f'<span class="p">{toc_pages.get(f"c{idx}", "")}</span></li>'
        )
        for n, (chap, h) in enumerate([x for x in ctx["h2s"] if x[0] == idx]):
            toc_rows.append(
                f'<li class="l2"><span class="n"></span><span class="t">{_markup(h)}</span>'
                f'<span class="p">{toc_pages.get(f"h{idx}_{n}", "")}</span></li>'
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
        "top_right": {"ro": "Ghid de utilizare", "en": "User guide", "es": "Guía de uso"}.get(lang, ""),
        "foot": content["footer"],
    }
    css = CSS
    for key, value in values.items():
        css = css.replace(f"@@{key}@@", value)
    out = (
        f'<!doctype html><html lang="{lang}"><meta charset="utf-8"><title>{html.escape(content["title"])}</title>'
        f"<style>{css}</style><body>{title}{toc}{''.join(chapters)}</body></html>"
    )
    return out if tokens else re.sub(r'<span class="tok">[^<]*</span>', "", out)


def html_to_pdf(html_path: str, pdf_path: str) -> None:
    """Render with headless Brave (Chromium): margin boxes, variable fonts, page breaks."""
    subprocess.run(
        [BRAVE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--run-all-compositor-stages-before-draw", "--virtual-time-budget=20000",
         f"--print-to-pdf={pdf_path}", f"file://{html_path}"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300,
    )


def page_of_titles(pdf_path: str, tokens: list) -> dict:
    """Page number (1-based) of each hidden token (``§c3§``, ``§h3_0§``)."""
    from pypdf import PdfReader

    texts = [p.extract_text() or "" for p in PdfReader(pdf_path).pages]
    found: dict = {}
    for tok in tokens:
        for i, text in enumerate(texts):
            if f"§{tok}§" in text:
                found[tok] = i + 1
                break
    return found


def build(lang: str, out_path: str, content: dict, img_dir: str | None = None) -> None:
    img_dir = img_dir or os.path.join(IMG_DIR, lang)
    """Two passes: lay out, read the page numbers, lay out again with the contents filled."""
    tmp = tempfile.mkdtemp(prefix="guide_")
    h1 = os.path.join(tmp, "g.html")
    pdf1 = os.path.join(tmp, "g1.pdf")
    html_doc = render_html(content, lang, None, img_dir)
    open(h1, "w", encoding="utf-8").write(html_doc)
    html_to_pdf(h1, pdf1)
    tokens = []
    for idx, sec in enumerate(content["sections"], 1):
        tokens.append(f"c{idx}")
        n = 0
        for blk in sec["blocks"]:
            if blk[0] in ("h2", "wcv"):
                tokens.append(f"h{idx}_{n}")
                n += 1
    pages = page_of_titles(pdf1, tokens)
    open(h1, "w", encoding="utf-8").write(render_html(content, lang, pages, img_dir, tokens=False))
    html_to_pdf(h1, out_path)
    print(f"OK: {out_path} ({len(pages)}/{len(tokens)} intrări în cuprins)")
