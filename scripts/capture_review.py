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
    ap.add_argument("--text", default="normal", help="text size level: normal|large|xlarge")
    ap.add_argument("--out-name", default="", help="sub-folder name instead of <theme>")
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
    from DisplayCAL.ui import theme as theme_mod

    theme_mod.is_dark = lambda source=None: theme == "dark"
    theme_mod.apply_theme(app)
    from DisplayCAL.ui import main_window as mw

    from DisplayCAL.ui import text_scale

    text_scale.apply(args.text)
    win = mw.MainWindow(worker=Worker())
    win.resize(width, height)
    win.show()
    win.worker.enumerate_displays_and_ports()
    win.update_controls()
    g = win._guide
    g._reached = 4

    from qtpy.QtWidgets import QAbstractButton, QComboBox, QLabel

    def clipped(root) -> list[str]:
        """Visible widgets whose text is wider than the widget (cut off)."""
        bad = []
        for w in root.findChildren(QLabel) + root.findChildren(QAbstractButton) + root.findChildren(QComboBox):
            if not w.isVisible() or w.width() < 8:
                continue
            fm = w.fontMetrics()
            if isinstance(w, QLabel):
                if w.wordWrap() or w.textFormat() == 3 or not w.text() or "<" in w.text() or w.pixmap() is not None:
                    continue
                need, have = fm.horizontalAdvance(w.text()), w.width() - w.contentsMargins().left() - w.contentsMargins().right()
            elif isinstance(w, QComboBox):
                need, have = fm.horizontalAdvance(w.currentText()), w.width() - 36
            else:
                need, have = fm.horizontalAdvance(w.text().replace("&", "")), w.width() - (24 if w.isCheckable() else 14)
                if not w.text() or w.icon().isNull() is False and w.text() == "":
                    continue
            if need > have + 2:
                bad.append(f"{type(w).__name__}: '{(w.text() if not isinstance(w, QComboBox) else w.currentText())[:60]}' needs {need}px has {have}px")
        return bad

    out_dir = os.path.join(args.out, code, args.out_name or theme)
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
        img.fill(QColor("#16171a"))
        p = QPainter(img)
        p.drawImage(0, band_h, base)
        p.setPen(QColor("#f6f6f4"))
        from DisplayCAL.ui import design_a

        p.setFont(design_a.mono_font(9.5, bold=True))
        p.drawText(14, 23, BAND[code].upper())
        p.end()
        counter[0] += 1
        fn = f"{counter[0]:02d}_{name}.png"
        img.save(os.path.join(out_dir, fn))
        index.append(
            {
                "clipped": clipped(widget),
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

    from review_shots import dialogs, finish_dialog, run_shots  # noqa: E402  (next to this script)

    import tempfile

    run_shots(win, g, app, save, tab, config, lang, settle, code)
    dialogs(win, g, app, save, config, lang, settle, code, tempfile.mkdtemp(dir=os.environ.get("TMPDIR")))
    finish_dialog(win, save, lang)
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    print("done", len(index), out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
