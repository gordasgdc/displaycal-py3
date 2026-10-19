#!/usr/bin/env python3
"""Render the guided-flow screens offscreen (no display, no instrument).

Used for the documentation and the website. The monitor and instrument shown
are *simulated* and every image carries an explicit "demonstration data" band,
so a simulated state is never presented as a real detection.

Usage: capture_guide_screens.py <out_dir> [--lang ro,en,es] [--theme light,dark]
       [--size 1180x900]
"""

from __future__ import annotations

import argparse
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BAND = {
    "ro": "DATE DEMONSTRATIVE — monitor și instrument simulate; nicio sondă nu este conectată",
    "en": "DEMONSTRATION DATA — simulated monitor and instrument; no instrument is connected",
    "es": "DATOS DE DEMOSTRACIÓN — monitor e instrumento simulados; ningún instrumento conectado",
}
MODEL = "Calibrite ColorChecker Display / Pro / Plus"


def main() -> int:
    """Render all requested screens."""
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--lang", default="ro,en,es")
    ap.add_argument("--theme", default="light,dark")
    ap.add_argument("--size", default="1180x900")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    width, height = (int(v) for v in args.size.split("x"))

    from DisplayCAL import config
    from DisplayCAL import localization as lang
    from DisplayCAL.worker import Worker

    config.initcfg()

    def fake(self: Worker, *a: object, **k: object) -> None:
        self.displays = [
            "DELL U2723QE @ 0, 0, 3840x2160 [PRIMARY]",
            "Color LCD @ 3840, 0, 1512x982",
        ]
        self.instruments = ["i1 DisplayPro, ColorMunki Display", "Spyder5"]

    Worker.enumerate_displays_and_ports = fake
    Worker.set_argyll_version = lambda self, *a, **k: None
    Worker.get_instrument_measurement_modes = lambda self, *a, **k: {}
    config.get_display_profile = lambda *a, **k: None

    from qtpy.QtGui import QColor, QImage, QPainter, QPalette
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    for code in args.lang.split(","):
        for theme in args.theme.split(","):
            config.setcfg("lang", code)
            lang.init()
            lang.update_defaults()
            pal = QPalette(app.style().standardPalette())
            if theme == "dark":
                pal.setColor(QPalette.Window, QColor("#1e1f23"))
                pal.setColor(QPalette.WindowText, QColor("#eceef1"))
                pal.setColor(QPalette.Base, QColor("#16171a"))
                pal.setColor(QPalette.Text, QColor("#eceef1"))
                pal.setColor(QPalette.Button, QColor("#2a2c31"))
                pal.setColor(QPalette.ButtonText, QColor("#eceef1"))
            app.setPalette(pal)
            from DisplayCAL.ui import main_window as mw

            win = mw.MainWindow(worker=Worker())
            win.resize(width, height)
            win.show()
            win.worker.enumerate_displays_and_ports()
            win.update_controls()
            g = win._guide
            g._model["i1 DisplayPro, ColorMunki Display"] = MODEL
            g._reached = 4
            g.prepare.stop_motion()
            for step in range(4):
                if step == 1:
                    g.go(1)
                    g.goal_buttons["photo"].setChecked(True)
                if step == 2:
                    g.go(2)
                    g.prepare.player._timeline.goto(2)
                    g.prepare.player._render()
                if step == 3:
                    for cb in g.prepare._boxes.values():
                        cb.setChecked(True)
                    g.go(3)
                if step == 0:
                    g.go(0)
                g.prepare.stop_motion()
                for _ in range(3):  # deferred relayouts settle over a few passes
                    app.processEvents()
                base = win.grab().toImage()
                img = QImage(base.width(), base.height() + 34, QImage.Format_ARGB32)
                img.fill(QColor(200, 70, 30))
                painter = QPainter(img)
                painter.drawImage(0, 34, base)
                painter.setPen(QColor("white"))
                f = painter.font()
                f.setBold(True)
                f.setPointSize(13)
                painter.setFont(f)
                painter.drawText(14, 23, BAND[code])
                painter.end()
                img.save(os.path.join(args.out, f"guide_step{step + 1}_{code}_{theme}.png"))
            win.close()
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
