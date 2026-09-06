#!/usr/bin/env python3
"""Genereaza cele 3 ghiduri PDF DisplayCAL-CG (RO/EN/ES).
Ruleaza: pip install reportlab pillow && python3 generate_guides.py
Porteaza arhitectura motorului DataMover (`_engine.py`, TOC real +
casete de accent + pasi numerotati + tabele de optiuni) - vezi acolo
comentariile complete de design."""
import os
import shutil

from _engine import build

HERE = os.path.dirname(os.path.abspath(__file__))
# PDF-urile ies la RADACINA repo-ului (nu in docs/) — acolo cauta py2app
# resursele de tip README.html (_setup.py, `data = "."`), ca sa poata fi
# bundle-uite in .app si deschise din meniul Ajutor -> "Citeste-ma"
# (readme_handler, display_cal.py, 2026-09-06). O copie identica se pune
# si in docs/ pentru pagina web de descarcare.
ROOT = os.path.join(HERE, "..", "..")
DOCS = os.path.join(HERE, "..")

import ghid_ro
build("ro", os.path.join(ROOT, "DisplayCAL-CG_Ghid_RO.pdf"), ghid_ro.CONTENT)
shutil.copy(os.path.join(ROOT, "DisplayCAL-CG_Ghid_RO.pdf"), os.path.join(DOCS, "DisplayCAL-CG_Ghid_RO.pdf"))

try:
    import ghid_en
    build("en", os.path.join(ROOT, "DisplayCAL-CG_Guide_EN.pdf"), ghid_en.CONTENT)
    shutil.copy(os.path.join(ROOT, "DisplayCAL-CG_Guide_EN.pdf"), os.path.join(DOCS, "DisplayCAL-CG_Guide_EN.pdf"))
except ImportError:
    print("SKIP: ghid_en.py inca neexistent")

try:
    import ghid_es
    build("es", os.path.join(ROOT, "DisplayCAL-CG_Guia_ES.pdf"), ghid_es.CONTENT)
    shutil.copy(os.path.join(ROOT, "DisplayCAL-CG_Guia_ES.pdf"), os.path.join(DOCS, "DisplayCAL-CG_Guia_ES.pdf"))
except ImportError:
    print("SKIP: ghid_es.py inca neexistent")
