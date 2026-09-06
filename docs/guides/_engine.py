#!/usr/bin/env python3
"""Motorul de compunere al ghidurilor PDF DataMover (RO/EN/ES).

[REFACUT COMPLET 2026-09-03] Cerinta explicita a lui Cristi: "ghidul sa fie
pas cu pas si foarte, foarte detaliat. Toate optiunile si toate ipostazele sa
fie trecute in acel PDF. PDF-ul trebuie sa arate impecabil."

Fata de versiunea din 2026-08-29, motorul castiga:
  - CUPRINS REAL, cu numere de pagina (reportlab TableOfContents +
    multiBuild - paginile se afla abia la a doua trecere de compunere);
  - casete de accent (info / atentie / sfat) - un ghid "toate ipostazele"
    devine altfel un zid de text in care avertismentele importante se pierd;
  - tabele cu antet, pentru listele de optiuni;
  - pasi numerotati cu bulina colorata, pentru procedurile pas cu pas;
  - antet de sectiune cu numerotare automata, ca trimiterile din text
    ("vezi capitolul 6") sa nu se strice cand se adauga un capitol.

Continutul propriu-zis sta in ghid_ro.py / ghid_en.py / ghid_es.py.
Ruleaza: pip install reportlab pillow && python3 generate_guides.py
"""
import os
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, Table, TableStyle,
    Image, PageBreak, KeepTogether,
)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(HERE, "img")
# Urmareste upstream (DisplayCAL/VERSION), nu un contor GDC separat -
# vezi Regula 14, nota specifica acestui repo in CLAUDE.md.
APP_VERSION = "3.10.0.dev82"

# Arial (nu Helvetica standard-14) - WinAnsiEncoding-ul fonturilor standard
# PDF nu are glyph-uri pentru diacriticele romanesti (a/s/t cu semne), ies ca
# patrate goale fara font TTF embedat.
pdfmetrics.registerFont(TTFont("Arial", "/System/Library/Fonts/Supplemental/Arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic", "/System/Library/Fonts/Supplemental/Arial Italic.ttf"))

# Accent identic cu pagina web gordas.dev/DisplayCAL-CG/ (docs/index.html
# --accent, aceeasi paleta "Shift" GDC folosita de restul suitei).
ACCENT = colors.HexColor("#E8963C")
ACCENT_SOFT = colors.HexColor("#fdf1e3")
ACCENT_LINE = colors.HexColor("#f2cd9e")
GREEN = colors.HexColor("#2f9e5c")          # STRICT semantic - verificare reusita
GREEN_SOFT = colors.HexColor("#eaf6ee")
RED = colors.HexColor("#b0342c")
RED_SOFT = colors.HexColor("#fbeeed")
INK = colors.HexColor("#1a1a1a")
INK_DARK = colors.HexColor("#14161a")
GREY = colors.HexColor("#555555")
GREY_LINE = colors.HexColor("#dddddd")
MAX_IMG_W = 15.5 * cm


def styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("CoverApp", fontName="Arial-Bold", fontSize=30, textColor=colors.white, leading=34))
    ss.add(ParagraphStyle("CoverSub", fontName="Arial", fontSize=13.5, textColor=colors.HexColor("#f2cfa8"), spaceBefore=8))
    ss.add(ParagraphStyle("CoverVer", fontName="Arial", fontSize=10, textColor=colors.HexColor("#c7cbd1"), spaceBefore=4))
    ss.add(ParagraphStyle("GTitle", parent=ss["Title"], fontName="Arial-Bold", fontSize=21, textColor=INK,
                          spaceAfter=4, alignment=TA_LEFT))
    ss.add(ParagraphStyle("GSubtitle", parent=ss["Normal"], fontName="Arial", fontSize=11, textColor=GREY, spaceAfter=2))
    ss.add(ParagraphStyle("GNote", parent=ss["Normal"], fontSize=9, textColor=GREY, spaceAfter=16, fontName="Arial-Italic"))
    ss.add(ParagraphStyle("H1", parent=ss["Heading1"], fontName="Arial-Bold", fontSize=15.5, textColor=ACCENT,
                          spaceBefore=20, spaceAfter=9))
    ss.add(ParagraphStyle("H2", parent=ss["Heading2"], fontName="Arial-Bold", fontSize=11.8, textColor=INK,
                          spaceBefore=13, spaceAfter=5))
    ss.add(ParagraphStyle("Body", parent=ss["Normal"], fontName="Arial", fontSize=10.2, leading=14.8, spaceAfter=6))
    ss.add(ParagraphStyle("GBullet", parent=ss["Normal"], fontName="Arial", fontSize=10.2, leading=14.8))
    ss.add(ParagraphStyle("Caption", fontName="Arial-Italic", fontSize=8.5, textColor=GREY,
                          spaceBefore=4, spaceAfter=14, alignment=TA_CENTER))
    ss.add(ParagraphStyle("Mono", parent=ss["Normal"], fontName="Courier", fontSize=9.5, textColor=INK,
                          backColor=colors.HexColor("#f2f2f2"), leftIndent=6, rightIndent=6,
                          spaceBefore=5, spaceAfter=9, borderPadding=5))
    ss.add(ParagraphStyle("CalloutBody", parent=ss["Normal"], fontName="Arial", fontSize=9.6, leading=13.6))
    ss.add(ParagraphStyle("CalloutTag", fontName="Arial-Bold", fontSize=9.6, leading=13.6))
    ss.add(ParagraphStyle("StepNum", fontName="Arial-Bold", fontSize=10.2, textColor=colors.white,
                          alignment=TA_CENTER, leading=13))
    ss.add(ParagraphStyle("THead", fontName="Arial-Bold", fontSize=9.6, textColor=colors.white, leading=13)) 
    ss.add(ParagraphStyle("TCellLabel", parent=ss["Body"], fontName="Arial-Bold", textColor=ACCENT, spaceAfter=0, fontSize=9.8))
    ss.add(ParagraphStyle("TCell", parent=ss["Body"], spaceAfter=0, fontSize=9.8, leading=13.6))
    ss.add(ParagraphStyle("TOCTitle", fontName="Arial-Bold", fontSize=11.8, textColor=INK,
                          spaceBefore=13, spaceAfter=7))
    ss.add(ParagraphStyle("TOCH1", fontName="Arial-Bold", fontSize=11, leading=18, textColor=INK))
    ss.add(ParagraphStyle("TOCH2", fontName="Arial", fontSize=9.8, leading=15, leftIndent=16, textColor=GREY))
    return ss


def screenshot(ss, filename, caption_text):
    """Sare peste discret daca fisierul lipseste local - ghidul tot se
    genereaza, doar fara acea imagine."""
    path = os.path.join(IMG_DIR, filename)
    if not os.path.exists(path):
        return []
    with PILImage.open(path) as im:
        w, h = im.size
    target_w = min(MAX_IMG_W, w / 2)   # capturi retina ~2x - evita supra-scalarea
    img = Image(path, width=target_w, height=target_w * h / w)
    img.hAlign = "CENTER"
    return [img, Paragraph(caption_text, ss["Caption"])]


def callout(ss, doc_width, kind, tag, text):
    """Caseta colorata: 'info' (amber), 'warn' (rosu), 'ok' (verde).
    Intr-un ghid care trece prin TOATE optiunile, avertismentele care
    chiar conteaza trebuie sa iasa din text, nu sa se piarda in el."""
    palette = {
        "info": (ACCENT_SOFT, ACCENT, ACCENT_LINE),
        "warn": (RED_SOFT, RED, colors.HexColor("#f0c9c5")),
        "ok": (GREEN_SOFT, GREEN, colors.HexColor("#c7e6d3")),
    }[kind]
    bg, fg, line = palette
    tag_p = Paragraph(f'<font color="#{fg.hexval()[2:]}">{tag}</font>', ss["CalloutTag"])
    body_p = Paragraph(text, ss["CalloutBody"])
    t = Table([[tag_p], [body_p]], colWidths=[doc_width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, fg),
        ("BOX", (0, 0), (-1, -1), 0.5, line),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (0, 0), 7),
        ("BOTTOMPADDING", (0, 0), (0, 0), 1),
        ("TOPPADDING", (0, 1), (0, 1), 0),
        ("BOTTOMPADDING", (0, 1), (0, 1), 8),
    ]))
    return [Spacer(1, 4), KeepTogether(t), Spacer(1, 10)]


def steps(ss, doc_width, items):
    """Pasi numerotati, cu bulina amber - pentru proceduri reale
    (instalare, activare, un transfer complet), unde ordinea conteaza."""
    rows = []
    for i, text in enumerate(items, 1):
        num = Table([[Paragraph(str(i), ss["StepNum"])]], colWidths=[7 * mm], rowHeights=[7 * mm])
        num.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("ROUNDEDCORNERS", [3, 3, 3, 3]),
        ]))
        rows.append([num, Paragraph(text, ss["TCell"])])
    t = Table(rows, colWidths=[10 * mm, doc_width - 10 * mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    return [KeepTogether(t) if len(items) <= 5 else t, Spacer(1, 4)]


def opt_table(ss, doc_width, header, rows):
    """Tabel cu antet colorat - pentru listele de optiuni (fiecare setare,
    fiecare model de verificare, fiecare status din raport)."""
    data = [[Paragraph(header[0], ss["THead"]), Paragraph(header[1], ss["THead"])]]
    data += [[Paragraph(a, ss["TCellLabel"]), Paragraph(b, ss["TCell"])] for a, b in rows]
    col0 = 45 * mm
    t = Table(data, colWidths=[col0, doc_width - col0], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK_DARK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GREY_LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#faf7f3")]),
        ("BOX", (0, 0), (-1, -1), 0.5, GREY_LINE),
    ]))
    return [t, Spacer(1, 12)]


class GuideDoc(SimpleDocTemplate):
    """Necesar pentru cuprins: reportlab afla numarul de pagina al unui
    titlu abia cand acesta e efectiv asezat pe pagina, deci cuprinsul se
    umple printr-o notificare (`TOCEntry`) trimisa din `afterFlowable`,
    iar documentul se compune de DOUA ori (multiBuild)."""

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        name = flowable.style.name
        if name == "H1":
            self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))
        elif name == "H2":
            self.notify("TOCEntry", (1, flowable.getPlainText(), self.page))


def _cover_canvas(canvas, doc):
    canvas.saveState()
    w, h = A4
    band_h = 9.5 * cm
    canvas.setFillColor(INK_DARK)
    canvas.rect(0, h - band_h, w, band_h, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, h - band_h - 0.2 * cm, w, 0.2 * cm, fill=1, stroke=0)
    canvas.restoreState()


def _content_canvas(canvas, doc, footer_text):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(ACCENT)
    canvas.rect(0, h - 0.4 * cm, w, 0.4 * cm, fill=1, stroke=0)
    canvas.setStrokeColor(GREY_LINE)
    canvas.setLineWidth(0.4)
    canvas.line(2 * cm, 1.65 * cm, w - 2 * cm, 1.65 * cm)
    canvas.setFont("Arial", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(2 * cm, 1.2 * cm, footer_text)
    canvas.drawRightString(w - 2 * cm, 1.2 * cm, str(canvas.getPageNumber()))
    canvas.restoreState()


def build(lang, out_path, content):
    ss = styles()
    doc = GuideDoc(out_path, pagesize=A4,
                   leftMargin=22 * mm, rightMargin=22 * mm, topMargin=20 * mm, bottomMargin=20 * mm,
                   title=content["title"], author="Cristi Gordas",
                   subject=content["subtitle"])
    W = doc.width

    toc = TableOfContents()
    toc.levelStyles = [ss["TOCH1"], ss["TOCH2"]]
    toc.dotsMinLevel = 0

    flow = [
        Spacer(1, 3.9 * cm),
        Paragraph("DisplayCAL-CG", ss["CoverApp"]),
        Paragraph(content["cover_subtitle"], ss["CoverSub"]),
        Spacer(1, 3.5 * cm),
        Paragraph(f"{content['cover_version_label']} {APP_VERSION}", ss["CoverVer"]),
        Paragraph(content["cover_lang_label"], ss["CoverVer"]),
        PageBreak(),
        Paragraph(content["title"], ss["GTitle"]),
        Paragraph(content["subtitle"], ss["GSubtitle"]),
        Paragraph(content["note"], ss["GNote"]),
        Paragraph(content["toc_title"], ss["TOCTitle"]),
        toc,
        PageBreak(),
    ]

    for idx, section in enumerate(content["sections"], 1):
        flow.append(Paragraph(f"{idx}. {section['h']}", ss["H1"]))
        for block in section["blocks"]:
            kind = block[0]
            if kind == "p":
                flow.append(Paragraph(block[1], ss["Body"]))
            elif kind == "h2":
                flow.append(Paragraph(block[1], ss["H2"]))
            elif kind == "ul":
                items = [ListItem(Paragraph(t, ss["GBullet"]), leftIndent=12, bulletColor=ACCENT)
                         for t in block[1]]
                flow.append(ListFlowable(items, bulletType="bullet", start="-", leftIndent=14, spaceAfter=9))
            elif kind == "code":
                flow.append(Paragraph(block[1], ss["Mono"]))
            elif kind == "img":
                flow.extend(screenshot(ss, block[1][0], block[1][1]))
            elif kind == "steps":
                flow.extend(steps(ss, W, block[1]))
            elif kind == "opt":
                flow.extend(opt_table(ss, W, block[1][0], block[1][1]))
            elif kind in ("info", "warn", "ok"):
                flow.extend(callout(ss, W, kind, block[1][0], block[1][1]))
            elif kind == "pagebreak":
                flow.append(PageBreak())

    doc.multiBuild(flow,
                   onFirstPage=_cover_canvas,
                   onLaterPages=lambda c, d: _content_canvas(c, d, content["footer"]))
    print(f"OK: {out_path}")
