#!/usr/bin/env python3
"""Render the Diagnostic and support dialogs offscreen (RO/EN/ES, light/dark).

The package contents shown come from a folder of sample logs/sessions given on
the command line (development evidence), never from the user's real data.

Usage: capture_diagnostic.py <out_dir> <logdir> <sessions_root>
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    """Render the dialogs."""
    out, logdir, sroot = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    from DisplayCAL import config, diagnostics
    from DisplayCAL import localization as lang

    config.initcfg()
    from qtpy.QtGui import QColor, QPalette
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    from DisplayCAL.ui import diagnostic_dialog as dd

    cats = diagnostics.plan_package(logdir, sroot, os.path.join(out, "x.icc"))
    for code in ("ro", "en", "es"):
        config.setcfg("lang", code)
        lang.init()
        for theme in ("light", "dark"):
            pal = QPalette()
            if theme == "dark":
                pal.setColor(QPalette.Window, QColor("#1e1f23"))
                pal.setColor(QPalette.WindowText, QColor("#eceef1"))
                pal.setColor(QPalette.Base, QColor("#16171a"))
                pal.setColor(QPalette.Text, QColor("#eceef1"))
                pal.setColor(QPalette.Button, QColor("#2a2c31"))
                pal.setColor(QPalette.ButtonText, QColor("#eceef1"))
            app.setPalette(pal)
            for name, dlg in (
                ("diagnostic", dd.DiagnosticDialog(None)),
                ("export", dd.ExportDialog(None, None, cats)),
            ):
                dlg.show()
                for _ in range(3):
                    app.processEvents()
                dlg.grab().save(os.path.join(out, f"{name}_{code}_{theme}.png"))
                dlg.close()
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
