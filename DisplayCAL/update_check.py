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
  branch) for the *update-available* dialogs — the Qt
  ``_UpdateAvailableDialog`` offers a direct asset download URL (opened in
  the browser) or a "go to website" fallback instead of driving
  Argyll/DisplayCAL installers itself. The *missing*-ArgyllCMS startup
  prompt (``MainWindow._prompt_missing_argyll``) is a separate flow and
  does drive a real in-app download + extract, via
  :func:`resolve_argyll_download_url` below plus a small Qt-only
  ``_ArgyllDownloadThread`` (``main_window.py``) — installing ArgyllCMS in
  the first place is table-stakes for a working app, unlike an optional
  version bump.
"""

from __future__ import annotations

import platform
import re
import sys
from dataclasses import dataclass

import requests

from DisplayCAL.argyll import get_argyll_latest_version
from DisplayCAL.meta import (
    ARGYLL_CHANGELOG_DOMAIN,
    ARGYLL_CHANGELOG_PATH,
    CG_BUILD,
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


def _parse_release_tag_version(tag_name: str) -> tuple[int, ...] | None:
    """Extract a comparable (major, minor, patch, cg_build) tuple from a
    GitHub release tag name — deliberate duplicate of
    ``display_cal.parse_release_tag_version`` (this module must stay
    importable without ``wx``, see the module docstring). This fork's
    tags look like ``v3.10.0.dev82-cg.1`` (upstream version + our own
    build suffix, see CLAUDE.md), not a plain ``X.Y.Z`` — strip a leading
    "v", keep only what precedes the first "-", and take the first 3
    numeric dot-separated segments.

    [FIX 2026-09-06 (2)] 4th element `cg_build`, parsed from "-cg.N" in
    the (unstripped) tag — see the sibling docstring in ``display_cal.py``
    for why (two tags with the same base number were previously
    indistinguishable, so installed-but-outdated users were never
    notified). 0 if the tag has no such suffix."""
    stripped = tag_name.strip().lstrip("vV")
    core = stripped.split("-")[0]
    parts = core.split(".")[:3]
    cg_match = re.search(r"-cg\.(\d+)", stripped)
    cg_build = int(cg_match.group(1)) if cg_match else 0
    try:
        return (*(int(p) for p in parts), cg_build)
    except ValueError:
        return None


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
    """Return the stable release-asset URL for the current platform.

    [2026-09-06] Toolkit-neutral port of ``display_cal.get_download_url``
    — rewritten the same way: the guessed per-version filenames
    (``{APPNAME}-{ver}-Windows-x64.exe``, ``-macOS-arm64.dmg``) never
    matched any asset actually published by this fork (verified with
    ``gh release view --json assets``: real names are
    ``DisplayCAL-CG-Setup.exe``/``DisplayCAL-CG.pkg``), so this always
    silently returned None. Uses the STABLE ``releases/latest/download/``
    name instead (Regula 9) — ``newversion``/``release_data`` are kept as
    parameters for signature compatibility with callers, not used to
    build the URL anymore.
    """
    if sys.platform == "win32":
        filename = "DisplayCAL-CG-Setup.exe"
    elif sys.platform == "darwin":
        filename = "DisplayCAL-CG.pkg"
    else:
        return None
    return f"{DEVELOPMENT_HOME_PAGE}/releases/latest/download/{filename}"


def resolve_argyll_download_url(newversion: str, domain: str) -> str:
    """Return the ArgyllCMS release archive URL for the current platform.

    Toolkit-neutral port of the ArgyllCMS branch of wx's
    ``app_update_confirm`` (``display_cal.py``): same
    ``argyll.domain``-relative GitHub Releases layout and per-platform
    suffix table, simplified to ``platform.machine()`` detection (no
    Windows registry lookup) like :func:`resolve_app_download_url`.
    Confirmed against the real ``eoyilmaz/argyllcms-binaries`` release
    assets, which are named exactly ``Argyll_V{version}{suffix}``.

    Args:
        newversion: The ArgyllCMS version string (e.g. ``"3.5.0"``).
        domain: The ``argyll.domain`` config value (a GitHub repo URL).
    """
    machine = platform.machine().lower()
    if sys.platform == "win32":
        if machine in ("arm64", "aarch64"):
            suffix = "_win_arm64_exe.zip"
        elif machine in ("amd64", "x86_64"):
            suffix = "_win64_exe.zip"
        else:
            suffix = "_win32_exe.zip"
    elif sys.platform == "darwin":
        if machine in ("arm64", "aarch64"):
            suffix = "_macOS11_arm64_bin.tgz"
        else:
            suffix = "_osx10.6_x86_64_bin.tgz"
    elif machine in ("x86_64", "amd64") or platform.architecture()[0] == "64bit":
        suffix = "_linux_x86_64_bin.tgz"
    else:
        suffix = "_linux_x86_bin.tgz"
    return f"{domain}/releases/download/{newversion}/Argyll_V{newversion}{suffix}"


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
    latest = _parse_release_tag_version(data.get("tag_name", ""))
    if latest is None:
        print(f"Error checking for updates: Parsing error - unparseable tag_name {data.get('tag_name')!r}")
        return None
    # [FIX 2026-09-06 (2)] Include CG_BUILD — vezi comentariul din
    # display_cal.parse_release_tag_version/is_new_update pentru motiv.
    current = (*tuple(current_version or VERSION_TUPLE)[:3], CG_BUILD)
    if latest <= current:
        print("No new updates available.")
        return None
    print("New updates available!")
    newversion = ".".join(str(n) for n in latest[:3])
    if len(latest) > 3 and latest[3]:
        newversion += f" (cg.{latest[3]})"
    return UpdateCheckResult(
        component="app",
        current_version=".".join(str(n) for n in current[:3]),
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
            ARGYLL_CHANGELOG_DOMAIN, ARGYLL_CHANGELOG_PATH, False
        ),
        download_url=None,
        release_page_url=ARGYLL_HOME_PAGE,
    )
