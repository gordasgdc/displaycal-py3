"""Removal of identifying and secret data from text (no dependencies).

Two levels, one place:

* :func:`redact_secrets` -- cheap, applied to every log line as it is written:
  passwords, tokens, keys and e-mail addresses are never stored.
* :func:`redact` -- full, applied to everything that leaves the logs for a
  support package or a feedback text: also home directories and the user name
  (macOS, Windows, Linux styles), volume names, host names, network and
  hardware identifiers, long hexadecimal identifiers and instrument serials.

Both are best effort and always followed by a preview for the user.
"""

from __future__ import annotations

import os
import re
import socket

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_MAC = re.compile(r"\b[0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5}\b")
_LONG_HEX = re.compile(r"\b[0-9a-fA-F]{24,}\b")
_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_SERIAL = re.compile(r"(?i)\b(serial(?: number)?|s/n)\b\s*[:=]\s*\S+")
_SECRET = re.compile(
    r"(?i)\b(token|password|passwd|secret|api[_-]?key|authorization|bearer)\b"
    r"(\s*[:=]\s*|\s+)\S+"
)
_URL_CRED = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@")
_MAC_HOME = re.compile(r"/Users/[^/\s\"']+")
_LINUX_HOME = re.compile(r"/home/[^/\s\"']+")
_WIN_HOME = re.compile(r"(?i)([A-Z]:[\\/]+Users[\\/]+)[^\\/\s\"']+")
_VOLUME = re.compile(r"/Volumes/[^/\s\"']+")


def redact_secrets(text: str) -> str:
    """Remove passwords, tokens, keys, credentials in URLs and e-mail addresses."""
    text = _URL_CRED.sub(lambda m: f"{m.group(1)}<redacted>@", text)
    text = _SECRET.sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", text)
    return _EMAIL.sub("<email>", text)


def redact(text: str) -> str:
    """Remove what identifies the user or the machine from diagnostic text."""
    text = redact_secrets(text)
    home = os.path.expanduser("~")
    if home and home not in ("~", os.sep):
        text = text.replace(home, "~")
        text = text.replace(home.replace("\\", "/"), "~")
    text = _MAC_HOME.sub("/Users/<user>", text)
    text = _LINUX_HOME.sub("/home/<user>", text)
    text = _WIN_HOME.sub(lambda m: f"{m.group(1)}<user>", text)
    text = _VOLUME.sub("/Volumes/<volume>", text)
    text = _SERIAL.sub(lambda m: f"{m.group(1)}: <redacted>", text)
    text = _UUID.sub("<id>", text)
    text = _MAC.sub("<mac>", text)
    text = _IPV4.sub("<ip>", text)
    text = _LONG_HEX.sub("<id>", text)
    for name in (
        os.environ.get("USER"),
        os.environ.get("USERNAME"),
        os.environ.get("LOGNAME"),
    ):
        if name and len(name) >= 3:
            text = re.sub(re.escape(name), "<user>", text, flags=re.IGNORECASE)
    try:
        host = socket.gethostname().split(".")[0]
    except OSError:
        host = ""
    if len(host) >= 5:  # short names ("mac", "pc") would damage ordinary words
        text = re.sub(rf"\b{re.escape(host)}\b", "<host>", text, flags=re.IGNORECASE)
    return text
