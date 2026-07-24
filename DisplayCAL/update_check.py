"""Toolkit-neutral application / ArgyllCMS update-check logic — Qt port support.

Ports the non-dialog pieces of ``display_cal.py``'s ``is_new_update`` /
``app_update_check`` / ``app_update_confirm`` chain (mirroring the
``preflight_checks.py`` / ``profile_finish.py`` precedent of a plain,
Qt-free module the still-shipping wx path could delegate to). This module is
a **fresh copy**, not an extraction-and-delegate: ``display_cal.py`` imports
``wx`` at module scope, so it can never be imported from the pure-Qt process,
and its ``is_new_update`` / ``get_download_url`` already have dedicated tests
(``tests/test_display_cal.py``) that monkeypatch ``display_cal.requests`` /
``display_cal.sys.platform`` / ``display_cal.platform.machine`` directly on
that module's namespace — a delegating wrapper would silently break them.
Both copies now call the same GitHub / ArgyllCMS APIs; they are expected to
stay in sync by inspection (the logic is small and unlikely to change).

Deliberately not reproduced (only reachable from the wx-side callers, which
never invoke it this way from the Qt startup path either):

* the snapshot/beta release channel (``snapshot=True``) — every wx call site
  that reaches the silent startup check passes ``snapshot=False``; only the
  wx update dialog's own "not up to date, and not a snapshot build" branch
  ever recurses into checking the snapshot channel afterwards, a self-chained
  check this module does not reproduce (a manual "Check for updates" click
  from the Qt UI only checks the stable release);
* the ZeroInstall packaging path (``zeroinstall``, hard-coded ``False`` in wx
  already);
* the in-app auto-download-and-run-the-installer flow
  (``app_update_confirm``'s ``worker.start(consumer, worker.download, ...)``
  branch) — the Qt dialog offers a direct asset download URL (opened in the
  browser) or a "go to website" fallback instead of driving Argyll/DisplayCAL
  installers itself, which is a large, separate feature in its own right.
"""

from __future__ import annotations

import platform
import re
import sys
from dataclasses import dataclass

import requests

from DisplayCAL.argyll import get_argyll_latest_version
from DisplayCAL.meta import (
    DEVELOPMENT_HOME_PAGE,
    DOMAIN,
    GITHUB_API_URL,
    VERSION_TUPLE,
    get_latest_changelog_entry,
)
from DisplayCAL.meta import NAME as APPNAME
from DisplayCAL.worker import http_request

#: ArgyllCMS's own project site, used as the "go to website" fallback since
#: Argyll releases aren't hosted on the DisplayCAL GitHub repo.
ARGYLL_HOME_PAGE = "https://www.argyllcms.com/"


@dataclass
class UpdateCheckResult:
    """A newer version was found for one component ("app" or "argyll")."""

    component: str
    current_version: str
    new_version: str
    changelog_html: str | None
    #: Direct release-asset URL for the current platform, if resolvable.
    download_url: str | None
    #: Fallback "go to website" URL, always set.
    release_page_url: str


def fetch_latest_release_data(timeout: int = 10) -> dict | None:
    """Fetch the latest GitHub release payload for DisplayCAL itself.

    Returns:
        dict | None: The parsed JSON payload, or ``None`` on any network or
            parsing failure (printed, not raised, matching ``is_new_update``).
    """
    headers = {"User-Agent": "DisplayCAL-updater"}
    try:
        response = requests.get(
            f"{GITHUB_API_URL}/releases/latest", headers=headers, timeout=timeout
        )
        response.raise_for_status()
    except requests.RequestException as exception:
        print(f"Error checking for updates: Network error - {exception}")
        return None
    try:
        return response.json()
    except ValueError as exception:
        print(f"Error checking for updates: Parsing error - {exception}")
        return None


def resolve_app_download_url(release_data: dict, newversion: str) -> str | None:
    """Return the release asset URL matching the current platform, if any.

    Toolkit-neutral port of ``display_cal.get_download_url``.
    """
    if sys.platform == "win32":
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            filename = f"{APPNAME}-{newversion}-Windows-arm64.exe"
        else:
            filename = f"{APPNAME}-{newversion}-Windows-x64.exe"
    elif sys.platform == "darwin":
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            filename = f"{APPNAME}-{newversion}-macOS-arm64.dmg"
        else:
            filename = f"{APPNAME}-{newversion}-macOS-x86.dmg"
    else:
        filename = f"{APPNAME.lower()}-{newversion}.tar.gz"
    for asset in release_data.get("assets", []):
        if asset.get("name") == filename:
            return asset.get("browser_download_url")
    return None


def _format_changelog(html: str, domain: str) -> str:
    """Rewrite anchor-only ``href``s and demote heading tags, matching wx."""
    html = re.sub(
        re.compile(r"<h\d>(.+?)</h\d>", flags=re.I | re.S),
        r"<p><strong>\1</strong></p>",
        html,
    )
    return re.sub(
        re.compile(r'href="(#[^"]+)"', flags=re.I),
        rf'href="https://{domain}/\1"',
        html,
    )


def fetch_changelog_html(domain: str, path: str, latest_entry_only: bool) -> str | None:
    """Fetch and lightly reformat a changelog page.

    Args:
        domain: The host to request from.
        path: The changelog path (e.g. ``"CHANGES.html"``).
        latest_entry_only: If True, extract just the most recent entry (the
            app changelog); if False, use the page verbatim (Argyll's).
    """
    resp = http_request(None, domain, "GET", "/" + path, silent=True)
    if not resp:
        return None
    readme = resp.read().decode("utf-8", "replace")
    if latest_entry_only:
        entry = get_latest_changelog_entry(readme)
        if not entry:
            return None
        html = (
            "<!DOCTYPE html><html><head><title></title></head>"
            f"<body>{entry}</body></html>"
        )
    else:
        html = readme
    return _format_changelog(html, domain)


def check_app_update(
    current_version: tuple[int, ...] | None = None,
) -> UpdateCheckResult | None:
    """Check for a newer DisplayCAL release.

    Args:
        current_version: Defaults to the running ``VERSION_TUPLE``.

    Returns:
        UpdateCheckResult | None: None if up to date or the check failed.
    """
    print("Checking for updates...")
    data = fetch_latest_release_data()
    if data is None:
        return None
    try:
        latest = tuple(int(n) for n in data["tag_name"].split("."))
    except (KeyError, ValueError, IndexError, AttributeError, TypeError) as exception:
        print(f"Error checking for updates: Parsing error - {exception}")
        return None
    current = tuple(current_version or VERSION_TUPLE)[:3]
    if latest <= current:
        print("No new updates available.")
        return None
    print("New updates available!")
    newversion = ".".join(str(n) for n in latest)
    return UpdateCheckResult(
        component="app",
        current_version=".".join(str(n) for n in current),
        new_version=newversion,
        changelog_html=fetch_changelog_html(DOMAIN, "CHANGES.html", True),
        download_url=resolve_app_download_url(data, newversion),
        release_page_url=f"{DEVELOPMENT_HOME_PAGE}/releases",
    )


def check_argyll_update(
    current_version: list[int] | None,
) -> UpdateCheckResult | None:
    """Check for a newer ArgyllCMS release.

    Args:
        current_version: The currently detected Argyll version (``Worker
            .argyll_version``, e.g. ``[0, 0, 0]`` when undetected). None or
            an all-zero version skips the check (nothing to compare against).

    Returns:
        UpdateCheckResult | None: None if up to date, undetected, or the
            check failed.
    """
    if not current_version or tuple(current_version) <= (0, 0, 0):
        return None
    latest_str = get_argyll_latest_version()
    try:
        latest = tuple(int(n) for n in latest_str.split("."))
    except (ValueError, AttributeError, TypeError):
        return None
    current = tuple(current_version)
    if latest <= current:
        return None
    return UpdateCheckResult(
        component="argyll",
        current_version=".".join(str(n) for n in current),
        new_version=latest_str,
        changelog_html=fetch_changelog_html(
            DOMAIN, "Argyll/ChangesSummary.html", False
        ),
        download_url=None,
        release_page_url=ARGYLL_HOME_PAGE,
    )
