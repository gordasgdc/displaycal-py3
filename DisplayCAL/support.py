"""Voluntary support and feedback helpers (toolkit-neutral).

Two clearly separate, entirely optional actions:

* give the project a star on GitHub -- the application only opens the
  repository page; the user decides and acts in the browser. The application
  never asks for a GitHub login, never handles tokens and never stars anything.
* send feedback -- opens a *new issue* page of the project's GitHub issue
  tracker, pre-filled with what the user typed plus the application version and
  platform. A redacted diagnostic is included only if the user explicitly asks
  for it after previewing it. Nothing is sent by the application itself.

The star supports this fork (DisplayCAL-CG); DisplayCAL itself and the
measurement engine belong to their own authors, who keep their own pages.
"""

from __future__ import annotations

import os
import platform
import re
import sys
from urllib.parse import quote

REPO_URL = "https://github.com/gordasgdc/displaycal-py3"
ISSUES_NEW_URL = f"{REPO_URL}/issues/new"
UPSTREAM_URL = "https://github.com/eoyilmaz/displaycal-py3"
ORIGINAL_URL = "https://displaycal.net/"
ARGYLL_URL = "https://www.argyllcms.com/"

KINDS = ("problem", "suggestion", "experience")

#: GitHub accepts long prefilled URLs only up to a limit; stay well below it.
MAX_URL_LEN = 7000


def app_version_line() -> str:
    """Return e.g. ``DisplayCAL-CG 3.10.0.dev82 (build cg.4)``."""
    from DisplayCAL.meta import CG_BUILD, VERSION_STRING

    return f"DisplayCAL-CG {VERSION_STRING} (build cg.{CG_BUILD})"


def platform_line() -> str:
    """Return a short, non-identifying platform description."""
    if sys.platform == "darwin":
        name = f"macOS {platform.mac_ver()[0]}"
    elif sys.platform == "win32":
        name = f"Windows {platform.release()} ({platform.version()})"
    else:
        name = platform.system() or sys.platform
    return f"{name}, {platform.machine()}"


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_LONG_HEX = re.compile(r"\b[0-9a-fA-F]{24,}\b")
_SERIAL = re.compile(r"(?i)\b(serial(?: number)?|s/n)\b\s*[:=]\s*\S+")
_BEARER = re.compile(r"(?i)\b(token|password|passwd|secret|api[_-]?key)\b\s*[:=]\s*\S+")


def redact(text: str) -> str:
    """Remove what identifies the user or the machine from diagnostic text.

    Home directories and the user name, e-mail addresses, IPv4 addresses, long
    hexadecimal identifiers (hardware IDs, hashes of secrets), instrument serial
    numbers and anything that looks like a token or password. This is
    best-effort: the user is shown the redacted text before anything is shared.
    """
    home = os.path.expanduser("~")
    if home and home not in ("~", os.sep):
        text = text.replace(home, "~")
        text = text.replace(home.replace("\\", "/"), "~")
    text = _EMAIL.sub("<email>", text)
    text = _SERIAL.sub(lambda m: f"{m.group(1)}: <redacted>", text)
    text = _BEARER.sub(lambda m: f"{m.group(1)}: <redacted>", text)
    text = _IPV4.sub("<ip>", text)
    text = _LONG_HEX.sub("<id>", text)
    user = os.environ.get("USER") or os.environ.get("USERNAME") or ""
    if len(user) >= 3:
        text = re.sub(re.escape(user), "<user>", text, flags=re.IGNORECASE)
    return text


def tail_lines(path: str, count: int = 150) -> list[str]:
    """Return the last ``count`` lines of a text file (empty if unreadable)."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 200_000))
            data = f.read()
    except OSError:
        return []
    return data.decode("utf-8", "replace").splitlines()[-count:]


def collect_diagnostic(log_path: str | None = None, lines: int = 150) -> str:
    """Build the redacted diagnostic text (facts plus the tail of the log)."""
    facts = [
        app_version_line(),
        f"Platform: {platform_line()}",
        f"Python: {platform.python_version()}",
    ]
    try:
        from qtpy import QtCore

        facts.append(f"Qt: {QtCore.qVersion()}")
    except ImportError:
        pass
    body = tail_lines(log_path, lines) if log_path else []
    text = "\n".join(facts) + "\n\n--- log (last lines) ---\n" + "\n".join(body)
    return redact(text)


def build_issue_url(
    kind: str,
    description: str,
    diagnostic: str | None = None,
) -> tuple[str, bool]:
    """Return the pre-filled new-issue URL and whether the diagnostic was cut.

    The issue body shows the type, the description, the application version
    and the platform; the diagnostic (already redacted) is added in a
    collapsed block only when given, and shortened to keep the URL usable.
    """
    kind = kind if kind in KINDS else "experience"
    title = {
        "problem": "Problem: ",
        "suggestion": "Suggestion: ",
        "experience": "Feedback: ",
    }[kind] + (description.strip().splitlines()[0][:70] if description.strip() else "")
    head = (
        f"**Type:** {kind}\n**Version:** {app_version_line()}\n"
        f"**Platform:** {platform_line()}\n\n### Description\n{description.strip()}\n"
    )
    truncated = False
    body = head
    if diagnostic:
        block = (
            "\n<details><summary>Diagnostic (redacted, shared by the user)</summary>"
            "\n\n```\n{}\n```\n</details>\n"
        )
        room = MAX_URL_LEN - len(ISSUES_NEW_URL) - len(quote(title)) - 40
        candidate = diagnostic
        while True:
            body = head + block.format(candidate)
            if len(quote(body)) <= room or len(candidate) < 200:
                break
            candidate = candidate[len(candidate) // 4 :]  # keep the newest part
            truncated = True
    url = f"{ISSUES_NEW_URL}?title={quote(title)}&body={quote(body)}"
    return url, truncated
