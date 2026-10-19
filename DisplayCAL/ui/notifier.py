"""Local notification when a long session ends (nothing leaves the computer)."""

from __future__ import annotations

from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QApplication, QSystemTrayIcon, QWidget

from DisplayCAL import localization as lang


def notify(window: QWidget | None, title: str, message: str) -> bool:
    """Show a system notification and ask for attention; best effort.

    Returns ``True`` when a notification was shown. No network, no account.
    """
    app = QApplication.instance()
    if app is not None and window is not None:
        app.alert(window, 0)
    if not QSystemTrayIcon.isSystemTrayAvailable() or window is None:
        return False
    tray = QSystemTrayIcon(window.windowIcon(), window)
    tray.show()
    tray.showMessage(title, message, QSystemTrayIcon.Information, 10000)
    QTimer.singleShot(15000, tray.hide)  # no lasting tray icon
    window._notifier_tray = tray  # keep a reference while it is shown
    return True


def session_message(outcome: str, reason: str | None) -> tuple[str, str]:
    """Title and text for a finished session."""
    key = {"completed": "notify.done", "cancelled": "notify.cancelled"}.get(
        outcome, "notify.failed"
    )
    text = reason or ""
    if reason and "repeating the same output" in reason:
        text = lang.getstr("notify.flood")
    return lang.getstr(key), text
