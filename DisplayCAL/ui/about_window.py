"""Qt port of ``MainFrame.aboutdialog_handler``'s "About" dialog.

Reproduces the wx dialog's content -- the header banner, app/ArgyllCMS
version + author credits, the translator list, icon-set credits, and the
Python/toolkit/audio-backend versions -- as a single scrollable, read-only
panel. wx builds this from a hand-laid-out grid of ``HyperLinkCtrl`` +
``StaticText`` pairs (``wx_windows.InvincibleFrame``); the Qt port collapses
each pair into one rich-text ``QLabel`` with an inline ``<a href>``, since
Qt's ``QLabel`` already renders and dispatches hyperlinks natively.

One deliberate toolkit-specific substitution: wx's row reports the
``wxPython`` version; this reports the actual Qt binding in use
(``qtpy.API_NAME`` + its version) instead, since that's the toolkit this
port actually runs on.
"""

from __future__ import annotations

import importlib
import re
import sys
from typing import TYPE_CHECKING

from qtpy import API_NAME as QT_API_NAME
from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from DisplayCAL import audio
from DisplayCAL import localization as lang
from DisplayCAL.meta import AUTHOR, DOMAIN, VERSION_STRING
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.ui.header_banner import (
    HEADER_BANNER_SIZE,
    HeaderBanner,
    header_banner_pixmap,
)

if TYPE_CHECKING:
    from DisplayCAL.worker import Worker

try:
    _QT_VERSION = importlib.import_module(QT_API_NAME).__version__
except Exception:  # noqa: BLE001 (best-effort version string only)
    _QT_VERSION = ""


def _link(label: str, url: str) -> str:
    return f'<a href="{url}">{label}</a>'


def _translator_credits() -> list[str]:
    """Port of ``aboutdialog_handler``'s ``lauthors`` grouping/sort."""
    lauthors: dict[str, list[str]] = {}
    for lcode in lang.LDICT:
        lauthor = lang.LDICT[lcode].get("!author", "")
        language = lang.LDICT[lcode].get("!language", "")
        if lauthor and language:
            lauthors.setdefault(lauthor, []).append(language)
    rows = sorted((langs, lauthor) for lauthor, langs in lauthors.items())
    return [f"{', '.join(langs)} - {lauthor}" for langs, lauthor in rows]


class AboutWindow(BaseWindow):
    """The "About DisplayCAL" dialog."""

    #: Matches ``MainWindow._HEADER_LOGO_INSET``: the tagline must start to
    #: the right of the wordmark artwork's baked-in "DisplayCAL" text (which
    #: occupies the banner's left ~80px), not underneath it.
    _TAGLINE_INSET = 80

    def __init__(self, worker: Worker | None, parent: QWidget | None = None) -> None:
        super().__init__(parent, name="", title=lang.getstr("menu.about"))

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        strip = QWidget()
        strip.setFixedHeight(6)
        strip.setStyleSheet("background-color: #66CC00;")
        outer.addWidget(strip)

        # Taller than MainWindow's own header bar (which is wide enough for
        # the tagline to fit on one line to the right of the wordmark): this
        # dialog is narrow enough that the tagline wraps to two lines, so it
        # needs the extra height below the wordmark artwork to avoid
        # overlapping it -- the same reason wx's own About dialog draws this
        # banner at ``size=(320, 120)`` instead of the header bar's ``64``.
        banner = HeaderBanner(
            header_banner_pixmap(), lang.getstr("header"), self._TAGLINE_INSET
        )
        banner.setFixedHeight(2 * HEADER_BANNER_SIZE[1])
        banner.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1,"
            " stop:0 #093d75, stop:0.5 #0e59a9, stop:1 #0e59a9);"
        )
        outer.addWidget(banner)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 12, 12, 12)
        body_layout.setSpacing(2)
        for line in self._body_lines(worker):
            if line is None:
                body_layout.addSpacing(10)
                continue
            label = QLabel(line)
            label.setTextFormat(Qt.RichText)
            label.setOpenExternalLinks(False)
            label.linkActivated.connect(
                lambda url: QDesktopServices.openUrl(QUrl(url))
            )
            label.setWordWrap(True)
            body_layout.addWidget(label)
        body_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        container = QWidget()
        container.setLayout(outer)
        self.setCentralWidget(container)
        self.resize(420, 480)

    @staticmethod
    def _body_lines(worker: Worker | None) -> list[str | None]:
        """Build the rich-text rows, in the same order as wx's ``items`` list."""
        lines: list[str | None] = []

        argyll_version_string = (
            re.sub(r"(?:\.0)+$", ".0", worker.argyll_version_string)
            if worker is not None
            else "0.0.0"
        )
        lines.append(
            f"{_link(APPNAME, f'https://{DOMAIN}/')} {VERSION_STRING} © {AUTHOR}"
        )
        lines.append(
            f"{_link('ArgyllCMS', 'https://github.com/eoyilmaz/argyllcms-binaries')}"
            f" {argyll_version_string} © Graeme Gill"
        )
        lines.append(None)

        lines.append(f"{lang.getstr('translations')}:")
        translator_lines = _translator_credits()
        if translator_lines:
            lines.extend(translator_lines)
        lines.append(None)

        lines.append(
            f"{_link('Apricity Icons', 'https://github.com/Apricity-OS/apricity-icons')}"
            " © Apricity OS Team"
        )
        lines.append(
            f"{_link('Suru Icons', 'https://github.com/snwh/suru-icon-theme')}"
            " © Sam Hewitt"
        )
        lines.append(
            f"Some icons © {_link('GNOME Project', 'https://www.gnome.org/')}"
        )
        lines.append(None)

        match = re.match(r"([^(]+)\s*(\([^(]+\))?\s*(\[[^[]+\])?", sys.version)
        pyver = (match.group(1) if match else sys.version).strip()
        lines.append(f"{_link('Python', 'https://www.python.org/')} {pyver}")
        lines.append(
            f"{_link(QT_API_NAME, 'https://www.qt.io/qt-for-python')} {_QT_VERSION}"
        )
        if audio._LIB:  # noqa: SLF001  (module-level state, no public accessor)
            lines.append(lang.getstr("audio.lib", f"{audio._LIB} {audio._LIB_VERSION}"))

        return lines
