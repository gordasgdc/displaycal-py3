"""Utility functions and exceptions for debugging and error handling in DisplayCAL.

It includes functionality for retrieving event object names and types, handling
errors with optional logging and user notifications, and printing call stacks
for debugging purposes.
"""

from __future__ import annotations

import sys
import traceback
from typing import TYPE_CHECKING

from DisplayCAL.meta import WX_RECVERSION
from DisplayCAL.options import DEBUG
from DisplayCAL.util_str import box

if TYPE_CHECKING:
    from types import TracebackType

    from DisplayCAL.wx_addons import wx  # noqa: TC004


WX_EVENT_TYPES = {}


def print_safe(text: str) -> None:
    """Print text, tolerating terminals/pipes that can't encode all of it.

    On Windows, stdout is sometimes attached to a non-UTF-8 pipe or console
    codepage (e.g. cp1252 under Git Bash or when output is redirected), which
    can't represent the box-drawing characters used by ``box()``. Falling
    back to a lossy encode/decode keeps error reporting from crashing itself.
    """
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(encoding, errors="replace").decode(encoding))


def getevtobjname(event: wx.Event, window: None | wx.Window = None) -> None | str:
    """Get and return the event object's name.

    Args:
        event (wx.Event): The event object to get the name from.
        window (None | wx.Window, optional): Optional window to search for the
            event object.

    Returns:
        None | str: The name of the event object, or None if it cannot be
            determined.
    """
    try:
        event_object = event.GetEventObject()
        if not event_object and window:
            event_object = window.FindWindowById(event.GetId())
        if event_object and hasattr(event_object, "GetName"):
            return event_object.GetName()
    except Exception:
        pass


def getevttype(event: wx.Event) -> None | str:
    """Get and return the event object's type.

    Args:
        event: The event object to get the type from.

    Returns:
        None | str: The name of the event type, or None if it cannot be
            determined.
    """
    if not WX_EVENT_TYPES:
        from DisplayCAL.wx_addons import wx

        try:
            for name in dir(wx):
                if name.find("EVT_") == 0:
                    attr = getattr(wx, name)
                    if hasattr(attr, "evtType"):
                        WX_EVENT_TYPES[attr.evtType[0]] = name
        except Exception:
            pass
    type_id = event.GetEventType()
    if type_id in WX_EVENT_TYPES:
        return WX_EVENT_TYPES[type_id]
    return None


def handle_error(
    error: tuple[type, str, TracebackType] | Exception,
    parent: None | wx.Window = None,
    silent: bool = False,
    tb: bool = True,
) -> None:
    """Log an error string and show an error dialog.

    Args:
        error (tuple[type, str, TracebackType] | Exception): The error to handle,
            which can be a tuple containing the exception type, value, and
            traceback, or an Exception instance.
        parent (None | wx.Window): The parent window for the error dialog.
        silent (bool): If True, suppresses the dialog display.
        tb (bool): If True, includes the traceback in the error message.
    """
    traceback.print_exc()
    msg = ""
    if isinstance(error, tuple):
        # We got a tuple. Assume (etype, value, tb)
        tbstr = "".join(traceback.format_exception(*error))
        error = error[1]
    else:
        tbstr = traceback.format_exc()

    if (
        tb
        and tbstr.strip() != "None"
        and isinstance(error, Exception)
        and (
            DEBUG
            or not isinstance(error, OSError)
            or not getattr(error, "filename", None)
        )
    ):
        # Print a traceback if in debug mode, for non OS errors,
        # and for OS errors not related to files
        errstr, tbstr = (str(v) for v in (error, tbstr))
        msg = f"{errstr}\n\n{tbstr}"
        if msg.startswith(errstr):
            print_safe(box(tbstr))
        else:
            print_safe(box(msg))
    else:
        msg = str(error)
        print_safe(box(msg))

    if silent:
        return

    try:
        show_error_dialog(error, msg, parent)
    except Exception as exception:
        traceback.print_exc()
        print("Warning: handle_error():", str(exception))


def show_error_dialog(
    error: Exception,
    msg: str,
    parent: None | wx.Window = None,
) -> None:
    """Show an error dialog.

    Args:
        error (Exception): The error to display.
        msg (str): The message to display in the dialog.
        parent (None | wx.Window): The parent window for the dialog.
    """
    from DisplayCAL.wx_addons import wx

    if wx.VERSION < WX_RECVERSION:  # noqa: SIM300
        msg += (
            "\n\nWARNING: Your version of wxPython ({}) is outdated "
            "and no longer supported. You should consider updating "
            "to wxPython {} or newer.".format(
                wx.__version__, ".".join(str(n) for n in WX_RECVERSION)
            )
        )
    app = wx.GetApp()
    if app is None and parent is None:
        app = wx.App(redirect=False)
        # wxPython 3 bugfix: We also need a toplevel window
        frame = wx.Frame(None)
        parent = False
    else:
        frame = None
    parent = wx.GetActiveWindow() if parent is None else parent
    if parent:
        try:
            parent.IsShownOnScreen()
        except Exception:
            # If the parent is still being constructed, we can't use it
            parent = None
    icon = wx.ICON_INFORMATION
    if not isinstance(error, Info):
        if isinstance(error, Warning):
            icon = wx.ICON_WARNING
        elif isinstance(error, Exception):
            icon = wx.ICON_ERROR
    dlg = wx.MessageDialog(
        (parent if parent not in (False, None) and parent.IsShownOnScreen() else None),
        msg,
        app.AppName,
        wx.OK | icon,
    )
    if frame:
        # wxPython 3 bugfix: We need to use CallLater and MainLoop
        wx.CallLater(1, dlg.ShowModal)
        wx.CallLater(1, frame.Close)
        app.MainLoop()
    else:
        dlg.ShowModal()
        dlg.Destroy()


def print_callstack() -> None:
    """Print call stack."""
    import inspect

    stack = inspect.stack()
    indent = ""
    for _frame, filename, linenum, funcname, line, _exc in reversed(stack[1:]):
        print(indent, funcname, filename, linenum, repr("".join(line).strip()))
        indent += " "


class ResourceError(Exception):
    """Error class for resource errors."""


class Error(Exception):
    """Error class for fatal errors."""


class Info(UserWarning):
    """Info class for non-fatal errors."""


class UnloggedError(Error):
    """Error class for non-fatal errors that should not be logged."""


class UnloggedInfo(Info):
    """Info class for non-fatal errors that should not be logged."""


class UnloggedWarning(UserWarning):
    """Warning class for non-fatal errors that should not be logged."""


class DownloadError(Error):
    """Error class for download errors."""

    def __init__(self, *args) -> None:
        Error.__init__(self, *args[:-1])
        self.url = args[1]


class UntracedError(Error):
    """Error class for errors that should not be logged."""


class Warn(UserWarning):
    """Warning class for non-fatal errors."""
