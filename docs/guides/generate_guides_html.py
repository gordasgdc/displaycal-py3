#!/usr/bin/env python3
"""Ghidurile PDF DisplayCAL-CG (RO/EN/ES) în Direcția A «Foaia de probă».

Interiorul: motorul HTML (`_engine_html.py`, Brave headless). Coperta: șabloanele
`A_cover_<lang>.html` din folderul de design (extern), lipite cu PDFKit ca prima pagină.

Ruleaza:  python3 generate_guides_html.py <folder_design_src> <folder_iesire> [ro,en,es]
  (folder_design_src = .../DisplayCAL-CG/design/src ; conține A_cover_*.html, fonts/, assets/)
Verificare PDF = prin script (pagini, cuvinte, termeni interziși), nu vizual.
"""
import os
import subprocess
import sys
import tempfile

import _engine_html as eng

NAMES = {"ro": "DisplayCAL-CG_Ghid_RO.pdf", "en": "DisplayCAL-CG_Guide_EN.pdf", "es": "DisplayCAL-CG_Guia_ES.pdf"}


def _cover(design_src: str, lang: str, out_pdf: str) -> None:
    html = os.path.join(design_src, f"V2_cover_{lang}.html")
    subprocess.run(
        [eng.BRAVE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         "--virtual-time-budget=15000", f"--print-to-pdf={out_pdf}", f"file://{html}"],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300,
    )


def main() -> None:
    design_src, out_dir = sys.argv[1], sys.argv[2]
    langs = (sys.argv[3] if len(sys.argv) > 3 else "ro,en,es").split(",")
    os.makedirs(out_dir, exist_ok=True)
    merge = os.path.join(design_src, "pdfmerge")
    for lang in langs:
        mod = __import__({"ro": "ghid_ro", "en": "ghid_en", "es": "ghid_es"}[lang])
        tmp = tempfile.mkdtemp(prefix=f"guide_{lang}_")
        inner, cover = os.path.join(tmp, "inner.pdf"), os.path.join(tmp, "cover.pdf")
        eng.build(lang, inner, mod.CONTENT)
        _cover(design_src, lang, cover)
        subprocess.run([merge, os.path.join(out_dir, NAMES[lang]), cover, inner], check=True)


if __name__ == "__main__":
    main()
