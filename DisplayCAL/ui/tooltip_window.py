"""Qt port of ``wx_windows.TooltipWindow``.

A small, non-modal popup showing an icon beside word-wrapped rich text,
plus optional flat "link" buttons that open a URL in the system browser.
Unlike wx's version (a reusable multi-column ``InvincibleFrame``), this
port only implements the single-column, non-scrolled shape actually used
by ``MainWindow`` (see ``display_tech_info_show_btn``); add columns/
scrolling here if a future caller needs them.
"""

from __future__ import annotations

from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QDesktopServices, QPixmap
from qtpy.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from DisplayCAL import localization as lang


def info_text_html(label_key: str) -> str:
    """Convert a wx ``StaticFancyText`` markup string to Qt rich text.

    wx's markup (``<font weight='bold'>...</font>``, blank-line paragraph
    breaks) isn't valid Qt rich text; translate it rather than re-authoring
    the (long, translated) ``info.*`` strings. Shared between
    :class:`DisplayCAL.ui.main_window.MainWindow` (its settings-tab info
    panels) and :class:`DisplayCAL.ui.colorimeter_correction_window
    .CreateCorrectionWindow` (its display-technology info popup) so the
    markup translation lives in one place.
    """
    text = lang.getstr(label_key)
    text = text.replace("<font weight='bold'>", "<b>").replace("</font>", "</b>")
    paragraphs = text.split("\n\n")
    return "".join(
        f"<p style='margin:0 0 8px 0'>{paragraph.replace(chr(10), '<br>')}</p>"
        for paragraph in paragraphs
    )


class TooltipWindow(QDialog):
    """Non-modal icon + rich-text popup, optionally with link buttons."""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message_html: str,
        bitmap: QPixmap | None = None,
        links: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__(parent, Qt.Tool)
        self.setWindowTitle(title)
        self.setModal(False)

        outer = QVBoxLayout(self)
        row = QHBoxLayout()
        if bitmap is not None and not bitmap.isNull():
            icon_label = QLabel()
            icon_label.setPixmap(bitmap)
            icon_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
            row.addWidget(icon_label)
        text_label = QLabel(message_html)
        text_label.setTextFormat(Qt.RichText)
        text_label.setWordWrap(True)
        text_label.setMaximumWidth(460)
        row.addWidget(text_label, 1)
        outer.addLayout(row)

        for label, url in links or []:
            link_btn = QPushButton(label)
            link_btn.setFlat(True)
            link_btn.setCursor(Qt.PointingHandCursor)
            link_btn.setStyleSheet("text-align: left; color: palette(link);")
            link_btn.clicked.connect(
                lambda _checked=False, u=url: QDesktopServices.openUrl(QUrl(u))
            )
            outer.addWidget(link_btn)

    def show_and_raise(self) -> None:
        """Show the window (or bring it to front if already shown)."""
        self.show()
        self.raise_()
        self.activateWindow()
