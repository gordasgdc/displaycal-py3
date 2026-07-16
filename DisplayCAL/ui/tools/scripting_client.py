"""Scripting client — Qt port.

Qt counterpart of :class:`DisplayCAL.wx_scripting_client.ScriptingClientFrame`:
the interactive terminal a user launches (``displaycal-scripting-client``) to
type commands and see responses from another running DisplayCAL window's
scripting/IPC socket (:class:`DisplayCAL.ui.scripting.ScriptingHostMixin`).

Structurally this diverges from the wx version's single caret-restricted
``wx.TextCtrl`` (prompt and input share one widget): here a read-only output
pane and a separate single-line input box are used instead, which is the
idiomatic Qt shape for a console and avoids reimplementing wx's manual
cursor/selection bookkeeping. The wire protocol, local command set (``clear``,
``connect``, ``disconnect``, ``getscriptinghosts``), command history file, and
auto-connect-to-first-detected-host startup behavior all match wx. Like wx,
this window also mixes in :class:`~DisplayCAL.ui.scripting.ScriptingHostMixin`
so it can itself be driven remotely.
"""

from __future__ import annotations

import os
import sys
from typing import Callable

from qtpy.QtCore import QObject, Qt, QThread, Signal
from qtpy.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from qtpy.QtWidgets import QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL.config import CONFIG_HOME, getcfg
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.ui.application import Application
from DisplayCAL.ui.base_window import BaseWindow
from DisplayCAL.wexpect import split_command_line

ERRORCOLOR = "#FF3300"
RESPONSECOLOR = "#CCCCCC"
DEFAULTCOLOR = "#EEEEEE"

#: Background socket round-trips get this long before we give up waiting.
_CONNECT_TIMEOUT_MS = 3500


class _BackgroundTask(QThread):
    """Run a blocking callable off the GUI thread and report its result.

    Args:
        func (Callable): The blocking function to run.
        args (tuple): Positional arguments for ``func``.
        parent (QObject | None): Optional Qt parent.
    """

    done = Signal(object)

    def __init__(
        self,
        func: Callable[..., object],
        args: tuple = (),
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._func = func
        self._args = args

    def run(self) -> None:
        """Execute the callable and emit its result or raised exception."""
        try:
            result = self._func(*self._args)
        except Exception as exception:  # noqa: BLE001
            result = exception
        self.done.emit(result)


class _CommandInput(QLineEdit):
    """Single-line command entry with shell-like history and tab completion.

    Args:
        window (ScriptingClientWindow): The owning window (holds the history
            and command tables consulted while editing).
        parent (QWidget | None): Optional Qt parent.
    """

    def __init__(
        self, window: ScriptingClientWindow, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._window = window

    def keyPressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Intercept Up/Down/Tab for history navigation and completion.

        Args:
            event (QKeyEvent): The key event.
        """
        if event.key() == Qt.Key_Up:
            self._window.history_navigate(-1)
            return
        if event.key() == Qt.Key_Down:
            self._window.history_navigate(1)
            return
        if event.key() == Qt.Key_Tab:
            self._window.complete_command()
            return
        super().keyPressEvent(event)


class ScriptingClientWindow(BaseWindow):
    """Interactive scripting-client terminal window."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            name="scripting",
            title=lang.getstr("scripting-client"),
            icon_name=f"{APPNAME}-scripting-client".lower(),
        )
        self.conn = None
        self.commands: list = []
        self.history: list = []
        self.historypos = 0
        self._pending_command = ""
        self._tasks: list = []
        self.historyfilename = os.path.join(
            CONFIG_HOME, f"{config.APPBASENAME}-scripting-client.history"
        )
        self._load_history()

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        font = QFont("Monospace")
        font.setStyleHint(QFont.TypeWriter)

        self.output = QPlainTextEdit(central)
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(10000)
        self.output.setFont(font)
        self.output.setStyleSheet(
            f"QPlainTextEdit {{ background-color: #272727; color: {DEFAULTCOLOR}; }}"
        )
        layout.addWidget(self.output, 1)

        self.input = _CommandInput(self, central)
        self.input.setFont(font)
        self.input.setPlaceholderText(">")
        self.input.returnPressed.connect(self._on_return_pressed)
        layout.addWidget(self.input)

        self.setCentralWidget(central)
        self.restore_position()
        if not self.restore_size():
            self.resize(getcfg("size.scripting.w"), getcfg("size.scripting.h"))

        scripting_hosts = self.get_scripting_hosts()
        if scripting_hosts:
            self.add_text("> getscriptinghosts\n")
            for host in scripting_hosts:
                self.add_text(host + "\n")
            ip_port = scripting_hosts[0].split()[0]
            self.add_text("> connect " + ip_port + "\n")
            self.connect_handler(ip_port)

        self.input.setFocus()

    # -- output --------------------------------------------------------

    def add_text(self, text: str, color: str | None = None) -> None:
        """Append text to the output pane and scroll to show it.

        Args:
            text (str): The text to append.
            color (str | None): Foreground color (hex), or the default.
        """
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color or DEFAULTCOLOR))
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def add_error_text(self, text: str) -> None:
        """Append text to the output pane, highlighted as an error.

        Args:
            text (str): The error text to append.
        """
        self.add_text(text, ERRORCOLOR)

    # -- history / tab completion ---------------------------------------

    def _load_history(self) -> None:
        """Load previously entered commands from the history file."""
        if os.path.isfile(self.historyfilename):
            try:
                with open(self.historyfilename, encoding="utf-8") as historyfile:
                    self.history = [line.rstrip("\r\n") for line in historyfile]
            except OSError as exception:
                print("Warning - couldn't read history file:", exception)
        self.historypos = len(self.history)

    def _save_history(self) -> None:
        """Persist the entered commands to the history file."""
        try:
            with open(self.historyfilename, "w", encoding="utf-8") as historyfile:
                for command in self.history:
                    if command:
                        historyfile.write(command + "\n")
        except OSError as exception:
            print("Warning - couldn't write history file:", exception)

    def history_navigate(self, direction: int) -> None:
        """Move through command history in the input box.

        Args:
            direction (int): ``-1`` for the previous command, ``1`` for the
                next (back towards the in-progress command).
        """
        if direction < 0:
            if self.historypos <= 0:
                return
            if self.historypos == len(self.history):
                self._pending_command = self.input.text()
            self.historypos -= 1
        else:
            if self.historypos >= len(self.history):
                return
            self.historypos += 1
        if self.historypos == len(self.history):
            self.input.setText(self._pending_command)
        else:
            self.input.setText(self.history[self.historypos])
        self.input.end(False)

    def complete_command(self) -> None:
        """Auto-complete the command name currently being typed."""
        text = self.input.text()
        prefix = text.split()[0] if text.split() else text
        candidates = sorted(
            {
                cmd.split()[0]
                for cmd in {*self.commands, *self.get_commands()}
                if cmd.split()[0].startswith(prefix)
            }
        )
        if not candidates:
            return
        common = os.path.commonprefix(candidates)
        if len(candidates) == 1:
            self.input.setText(candidates[0] + " ")
        elif common and len(common) > len(prefix):
            self.input.setText(common)
        else:
            self.add_text("> " + text + "\n")
            self.add_text(" ".join(candidates) + "\n")
        self.input.end(False)

    # -- connection management -------------------------------------------

    def connect_handler(self, ip_port: str) -> None:
        """Connect to another scripting host given as ``ip:port``.

        Args:
            ip_port (str): The address to connect to, e.g. ``"127.0.0.1:1234"``.
        """
        ip, _, port_str = ip_port.partition(":")
        try:
            port = int(port_str)
        except ValueError:
            self.add_error_text(lang.getstr("port.invalid", port_str) + "\n")
            return
        if self.conn:
            self.disconnect()
        self.add_text(lang.getstr("connecting.to", (ip, port)) + "\n")
        self.input.setEnabled(False)
        task = _BackgroundTask(self._do_connect, (ip, port), self)
        self._tasks.append(task)
        task.done.connect(lambda result: self._on_connected(result, task))
        task.start()

    def _do_connect(self, ip: str, port: int) -> tuple | Exception:
        """Connect and handshake with the remote host (runs off the GUI thread).

        Args:
            ip (str): The IP address to connect to.
            port (int): The port to connect to.

        Returns:
            A ``(conn, commands, appname)`` tuple, or the ``Exception`` raised.
        """
        conn = self.open_connection(ip, port)
        if isinstance(conn, Exception):
            return conn
        try:
            conn.send_command("setresponseformat plain")
            conn.get_single_response()
            conn.send_command("getcommands")
            commands = conn.get_single_response().decode("utf-8").splitlines()
            conn.send_command("getappname")
            appname = conn.get_single_response().decode("utf-8")
        except OSError as exception:
            return exception
        return conn, commands, appname

    def _on_connected(self, result: tuple | Exception, task: _BackgroundTask) -> None:
        """Handle the outcome of a background connect attempt.

        Args:
            result: The ``(conn, commands, appname)`` tuple, or an ``Exception``.
            task (_BackgroundTask): The finished background task (for cleanup).
        """
        self._tasks.remove(task)
        if isinstance(result, Exception):
            self.add_error_text(f"{result}\n")
        else:
            conn, commands, appname = result
            self.conn = conn
            self.commands = commands
            self.add_text(lang.getstr("connection.established") + "\n", RESPONSECOLOR)
            self.add_text(
                lang.getstr("connected.to.at", (appname, *conn.getpeername())) + "\n"
                f"{lang.getstr('scripting-client.cmdhelptext')}\n"
            )
        self.input.setEnabled(True)
        self.input.setFocus()

    def disconnect(self) -> None:
        """Disconnect from the connected application, if any."""
        if self.conn:
            try:
                peer = self.conn.getpeername()
            except OSError:
                peer = None
            self.conn.disconnect()
            self.conn = None
            self.commands = []
            if peer:
                self.add_text(lang.getstr("disconnected.from", peer) + "\n")
        else:
            self.add_error_text(lang.getstr("not_connected") + "\n")

    # -- command entry -----------------------------------------------------

    def _on_return_pressed(self) -> None:
        """Handle Enter in the input box: record history and dispatch."""
        command = self.input.text()
        self.input.clear()
        self.send_command_handler(command)

    def send_command_handler(self, command: str) -> None:
        """Process one command line entered by the user.

        Args:
            command (str): The raw command line as typed.
        """
        stripped = command.strip()
        self.add_text("> " + command + "\n")
        if not stripped:
            return
        if not self.history or self.history[-1] != stripped:
            self.history.append(stripped)
            if len(self.history) > 1000:
                del self.history[0]
        self.historypos = len(self.history)
        self._pending_command = ""
        data = split_command_line(stripped)
        response = self.process_data_local(data)
        if response == "ok":
            return
        if isinstance(response, list):
            self.add_text("\n".join(response) + "\n")
            return
        if not self.conn:
            self.add_error_text(lang.getstr("not_connected") + "\n")
            return
        self.input.setEnabled(False)
        task = _BackgroundTask(self._do_send_command, (stripped,), self)
        self._tasks.append(task)
        task.done.connect(lambda result: self._on_command_result(result, task))
        task.start()

    def _do_send_command(self, command: str) -> str | OSError:
        """Send ``command`` to the connected host and await its response.

        Args:
            command (str): The command line to send.

        Returns:
            str | OSError: The decoded response, or the ``OSError`` raised.
        """
        try:
            self.conn.send_command(command)
            response = self.conn.get_single_response()
        except OSError as exception:
            return exception
        return response.decode("utf-8")

    def _on_command_result(self, result: str | OSError, task: _BackgroundTask) -> None:
        """Handle the outcome of a background command round-trip.

        Args:
            result (str | Exception): The decoded response, or an ``Exception``.
            task (_BackgroundTask): The finished background task (for cleanup).
        """
        self._tasks.remove(task)
        if isinstance(result, Exception):
            self.add_error_text(f"{result}\n")
        elif result:
            text = "< " + "\n< ".join(result.splitlines())
            self.add_text(text + "\n", RESPONSECOLOR)
        self.input.setEnabled(True)
        self.input.setFocus()

    def process_data_local(self, data: list) -> str | list:
        """Interpret a command locally, without involving the remote host.

        Args:
            data (list): The split command line.

        Returns:
            str | list: ``"ok"``, ``"invalid"`` (forward to the remote host
            instead), or a list of lines to display (``getscriptinghosts``).
        """
        if data[0] == "clear" and len(data) == 1:
            self.output.clear()
            return "ok"
        if data[0] == "connect" and len(data) == 2 and len(data[1].split(":")) == 2:
            self.connect_handler(data[1])
            return "ok"
        if data[0] == "disconnect" and len(data) == 1:
            self.disconnect()
            return "ok"
        if data[0] == "getscriptinghosts" and len(data) == 1:
            return self.get_scripting_hosts()
        return "invalid"

    # -- scripting (this window driven remotely) ----------------------------

    def get_commands(self) -> list:
        """Return the scripting commands this window understands.

        Returns:
            list: The common commands plus this tool's local ones.
        """
        return [
            *self.get_common_commands(),
            "clear",
            "connect <ip>:<port>",
            "disconnect",
            "getscriptinghosts",
        ]

    # -- lifecycle -----------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        """Save history and geometry, then let :class:`BaseWindow` finish up.

        Args:
            event (QCloseEvent): The Qt close event.
        """
        for task in list(self._tasks):
            task.wait(_CONNECT_TIMEOUT_MS)
        self._save_history()
        self.save_size()
        super().closeEvent(event)


def main() -> int:
    """Entry point for the Qt scripting client.

    Returns:
        int: The Qt application exit code.
    """
    config.initcfg("scripting-client")
    lang.init()
    lang.update_defaults()

    app = Application(sys.argv)
    window = ScriptingClientWindow()
    app.top_window = window
    if sys.platform == "darwin":
        window.init_menubar()
    window.listen()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
