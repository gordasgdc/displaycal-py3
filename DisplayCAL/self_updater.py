"""Real self-updater for DisplayCAL-CG — download the new package and
launch its native installer, instead of just opening a browser tab.

[2026-09-06] Cerut explicit de Cristi: "ar trebui să se instaleze noua
actualizare, la fel cum sunt și la celelalte aplicații [GDC]" — pana acum
"Update now" deschidea doar un tab de browser (`webbrowser.open_new_tab`,
`display_cal.app_update_confirm`), lasand userul sa descarce si sa
instaleze manual. Port 1:1, in Python, al reteitei deja folosite in restul
ecosistemului GDC (`DataMover/core/updater.py`, `SelfUpdater.swift`/`.cs`):
Mac descarca un `.pkg` si il instaleaza prin promptul NATIV de parola
admin (`osascript ... with administrator privileges`); Windows descarca
installer-ul Inno Setup (`.exe`) si il lanseaza direct — fereastra nativa
a installer-ului apare, NICIODATA un browser.

Foloseste doar biblioteca standard (fara dependinte noi) — la fel ca
`DataMover/core/updater.py`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

APPNAME_DISPLAY = "DisplayCAL-CG"


def download_installer(url: str, timeout: int = 60) -> tuple[str | None, str | None]:
    """Download the installer (.pkg on Mac, .exe on Windows) to a fresh
    temp directory. Returns (path, error) — exactly one is None."""
    ext = os.path.splitext(url.split("?")[0])[1] or ".bin"
    temp_dir = tempfile.mkdtemp(prefix="displaycal_cg_update_")
    download_path = os.path.join(temp_dir, f"{APPNAME_DISPLAY}-update{ext}")
    request = urllib.request.Request(url, headers={"User-Agent": "DisplayCAL-CG-updater"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, \
                open(download_path, "wb") as out_file:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out_file.write(chunk)
    except (urllib.error.URLError, OSError) as exception:
        return None, f"Descărcarea actualizării a eșuat: {exception}"
    return download_path, None


def install_and_relaunch_mac(pkg_path: str) -> tuple[bool, str | None]:
    """Install the downloaded .pkg via the native macOS admin-password
    prompt (osascript "with administrator privileges" — never a raw
    `sudo` without a TTY, never a visible Terminal window), then relaunch
    the app. Runs a detached shell script so the CURRENT process (about to
    be replaced on disk) doesn't need to stay alive for the install."""
    if not pkg_path or not os.path.isfile(pkg_path):
        return False, "Fișierul .pkg descărcat nu a fost găsit."
    temp_dir = os.path.dirname(pkg_path)
    script_path = os.path.join(temp_dir, "displaycal_cg_update.sh")
    log_path = os.path.join(temp_dir, "displaycal_cg_update.log")
    script_content = f"""#!/bin/bash
exec > "{log_path}" 2>&1
sleep 2
echo "Instalez actualizarea DisplayCAL-CG..."
installer -pkg "{pkg_path}" -target /
status=$?
if [ $status -ne 0 ]; then
    echo "Instalarea a eșuat (cod $status)."
    exit $status
fi
echo "Pornesc aplicația actualizată..."
open -a "{APPNAME_DISPLAY}"
rm -rf "{temp_dir}"
"""
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_content)
    os.chmod(script_path, 0o755)
    escaped_path = script_path.replace('"', '\\"')
    apple_script = f'do shell script "{escaped_path}" with administrator privileges'
    try:
        subprocess.Popen(["osascript", "-e", apple_script])
    except OSError as exception:
        return False, f"Nu am putut porni instalarea: {exception}"
    return True, None


def install_and_relaunch_windows(exe_path: str) -> tuple[bool, str | None]:
    """Launch the downloaded Inno Setup installer (.exe) directly — its
    own native wizard takes over from here (license page, Next/Install,
    optional relaunch via its `[Run]` section), exactly like every other
    GDC Windows app. The current process should quit right after this
    returns so the installer can replace files freely."""
    if not exe_path or not os.path.isfile(exe_path):
        return False, "Fișierul .exe descărcat nu a fost găsit."
    try:
        subprocess.Popen([exe_path], shell=False)
    except OSError as exception:
        return False, f"Nu am putut porni instalarea: {exception}"
    return True, None


def perform_self_update(url: str) -> tuple[bool, str | None]:
    """Full flow: download the installer for the current platform, then
    launch it. Returns (started_ok, error_message)."""
    if sys.platform not in ("darwin", "win32"):
        return False, "Actualizarea automată e disponibilă doar pe Mac și Windows."
    path, error = download_installer(url)
    if error:
        return False, error
    if sys.platform == "darwin":
        return install_and_relaunch_mac(path)
    return install_and_relaunch_windows(path)
