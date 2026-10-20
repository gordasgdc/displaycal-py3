#!/usr/bin/env python3
"""Script-level check of the PDF guides (no visual rendering): pages, size, fonts, words,
forbidden wording, contents numbers. Usage: verify_guides.py <pdf> [...]"""
import os
import subprocess
import sys

from pypdf import PdfReader

FORBIDDEN = [
    "Rulare lungă sigură", "Safe long run", "Ejecución larga segura",
    "Co-Authored", "§c", "§h", "lorem", "preț", "price", "precio",
]


def check(path: str) -> list[str]:
    r = PdfReader(path)
    problems: list[str] = []
    n = len(r.pages)
    # Text through PDFKit (what the system viewer will find, copy and search).
    tool = os.environ.get("PDFPAGES", "/Volumes/CristiGordas/TESTE/GDC_PROJECTS/DisplayCAL-CG/design/src/pdfpages")
    out = subprocess.run([tool, path], capture_output=True, text=True, check=True).stdout
    head, _, body = out.partition("\n---\n")
    counts = [int(line.split()[1]) for line in head.splitlines()]
    words = sum(counts)
    for i, p in enumerate(r.pages, 1):
        w, h = float(p.mediabox.width), float(p.mediabox.height)
        if abs(w - 595.3) > 2 or abs(h - 841.9) > 2:
            problems.append(f"page {i}: size {w:.0f}x{h:.0f} is not A4")
    fonts = set()
    for p in r.pages:
        res = p.get("/Resources") or {}
        for f in (res.get("/Font") or {}).values():
            fonts.add(str(f.get_object().get("/BaseFont")))
    if not any("Archivo" in f for f in fonts):
        problems.append(f"Archivo not embedded: {sorted(fonts)}")
    if any("Helvetica" in f or "Arial" in f or "Times" in f for f in fonts):
        problems.append(f"system font fallback: {sorted(fonts)}")
    full = body
    for term in FORBIDDEN:
        if term.lower() in full.lower():
            problems.append(f"forbidden term: {term!r}")
    blank = [i for i, c in enumerate(counts, 1) if c < 8]
    if blank:
        problems.append(f"nearly empty pages: {blank}")
    print(f"{path.split('/')[-1]}: pages={n} words={words} fonts={len(fonts)} problems={len(problems)}")
    return problems


if __name__ == "__main__":
    bad = 0
    for pdf in sys.argv[1:]:
        for pr in check(pdf):
            print("  -", pr)
            bad += 1
    sys.exit(1 if bad else 0)
