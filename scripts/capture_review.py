#!/usr/bin/env python3
"""Visual inventory of the main screens and dialogs (offscreen, demonstration data).

Every image carries a band that says the monitor/instrument are simulated; no
real profile, curve or device is touched. Usage:

    capture_review.py <out_dir> [--lang ro] [--theme light] [--size 1180x1000] [--only name,...]

Writes ``<out_dir>/<lang>/<theme>/NN_name.png`` and ``index.json`` (name, title,
what it shows, what is simulated). ``scripts/build_review_html.py`` turns that
into the local HTML review.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BAND = {
    "ro": "DATE DEMONSTRATIVE — monitor și instrument simulate; nicio sondă conectată; nimic real nu este modificat",
    "en": "DEMONSTRATION DATA — simulated monitor and instrument; no instrument connected; nothing real is modified",
    "es": "DATOS DE DEMOSTRACIÓN — monitor e instrumento simulados; ningún instrumento conectado; no se modifica nada real",
}


def main() -> int:
    """Render the inventory."""
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--lang", default="ro")
    ap.add_argument("--theme", default="light")
    ap.add_argument("--size", default="1180x1000")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    width, height = (int(v) for v in args.size.split("x"))
    only = {n for n in args.only.split(",") if n}

    from DisplayCAL import config
    from DisplayCAL import localization as lang
    from DisplayCAL.worker import Worker

    config.initcfg()

    def fake(self: Worker, *a: object, **k: object) -> None:
        self.displays = [
            "DELL U2723QE @ 0, 0, 3840x2160 [PRIMARY]",
            "Color LCD @ 3840, 0, 1512x982",
        ]
        self.instruments = ["i1 DisplayPro, ColorMunki Display", "Spyder5", "i1 Pro"]

    Worker.enumerate_displays_and_ports = fake
    Worker.set_argyll_version = lambda self, *a, **k: None
    Worker.get_instrument_measurement_modes = lambda self, *a, **k: {}
    config.get_display_profile = lambda *a, **k: None

    from qtpy.QtGui import QColor, QImage, QPainter, QPalette
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    from qtpy.QtCore import QTimer

    def _dismiss_modal() -> None:
        """A capture must never wait on a message box: close it and say so."""
        w = app.activeModalWidget()
        if w is not None:
            print("modal dialog auto-closed:", w.windowTitle() or type(w).__name__)
            w.reject()

    _t = QTimer()
    _t.timeout.connect(_dismiss_modal)
    _t.start(400)
    code, theme = args.lang, args.theme
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
    g._reached = 4

    out_dir = os.path.join(args.out, code, theme)
    os.makedirs(out_dir, exist_ok=True)
    index: list[dict] = []
    counter = [0]

    def settle() -> None:
        for _ in range(4):
            app.processEvents()
        if hasattr(win, "_pin_stack_size_to_current_tab"):
            win._pin_stack_size_to_current_tab()
        for _ in range(3):
            app.processEvents()

    def save(widget, name, title, shows, simulated="", framed=True) -> None:
        if only and name not in only:
            return
        settle()
        base = widget.grab().toImage()
        band_h = 34
        img = QImage(base.width(), base.height() + band_h, QImage.Format_ARGB32)
        img.fill(QColor(200, 70, 30))
        p = QPainter(img)
        p.drawImage(0, band_h, base)
        p.setPen(QColor("white"))
        f = p.font()
        f.setBold(True)
        f.setPointSize(12)
        p.setFont(f)
        p.drawText(14, 23, BAND[code])
        p.end()
        counter[0] += 1
        fn = f"{counter[0]:02d}_{name}.png"
        img.save(os.path.join(out_dir, fn))
        index.append(
            {
                "n": counter[0],
                "name": name,
                "file": fn,
                "title": title,
                "shows": shows,
                "simulated": simulated,
                "size": [img.width(), img.height()],
            }
        )

    def tab(key: str, advanced: bool) -> None:
        win.show_advanced_options_action.setChecked(advanced)
        win._select_tab(key)
        settle()

    from review_shots import dialogs, run_shots  # noqa: E402  (next to this script)

    import tempfile

    run_shots(win, g, app, save, tab, config, lang, settle, code)
    dialogs(win, g, app, save, config, lang, settle, code, tempfile.mkdtemp(dir=os.environ.get("TMPDIR")))
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    print("done", len(index), out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
