"""Meta information."""

from __future__ import annotations

import os
import re
import sys

# globals
VERSION_STRING = None
if getattr(sys, "frozen", False):
    base_path = os.path.dirname(sys.executable)
    if sys.platform == "darwin":
        _base_path = os.path.join(os.path.dirname(base_path), "Resources")
        if os.path.isdir(_base_path):
            base_path = _base_path
else:
    base_path = os.path.dirname(__file__)
VERSION_FILE = os.path.join(base_path, "VERSION")

# If it's not in the root, check the DisplayCAL subfolder just in case
if not os.path.isfile(VERSION_FILE):
    VERSION_FILE = os.path.join(base_path, "DisplayCAL", "VERSION")

if os.path.isfile(VERSION_FILE):
    with open(VERSION_FILE, encoding="utf-8") as f:
        VERSION_STRING = f.read().strip()
VERSION_STRING = VERSION_STRING or "0.0.0"
"""str: The version number of DisplayCAL."""

# DisplayCAL-CG Edition (2026-09-05, by Cristi Gordaș / GDC): fork rebranded
# per the fork's own scope decision — GPLv3 §5/§7 requires we keep the
# original authors' notices intact and forbids adding restrictions, but
# does NOT forbid a derivative distribution stating its own identity. We
# ADD our credit, we never remove Höch/Yılmaz's. AUTHOR_EMAIL stays hardcoded
# to their REAL addresses (not derived from DOMAIN below) — DOMAIN here
# only drives *our* packaging metadata (installer URLs, APPSTREAM_ID), it
# must never silently become part of an email address that isn't ours.
AUTHOR = "Florian Höch, Erkan Özgür Yılmaz — DisplayCAL-CG Edition by Cristi Gordaș (GDC)"  # noqa: RUF001
AUTHOR_ASCII = "Florian Hoech, Erkan Ozgur Yilmaz - DisplayCAL-CG Edition by Cristi Gordas (GDC)"
DESCRIPTION = (
    "Display calibration and profiling with a focus on accuracy and versatility "
    "(DisplayCAL-CG Edition)"
)
LONG_DESCRIPTION = (
    "Calibrate and characterize your display devices using one of many supported "
    "measurement instruments, with support for multi-display setups and a variety of "
    "available options for advanced users, such as  verification and reporting "
    "functionality to evaluate ICC profiles and display devices, creating video 3D "
    "LUTs, as well as optional CIECAM02 gamut mapping to take into account varying "
    "viewing conditions. This is DisplayCAL-CG, a GDC distribution of the open-source "
    "DisplayCAL project (originally by Florian Höch and Erkan Özgür Yılmaz), packaged "
    "and localized for the GDC ecosystem under the same GPLv3 license."
)
# DisplayCAL-CG's own packaging domain — drives installer URLs/APPSTREAM_ID
# ONLY (see native_build/templates.py, inno.py). Never used to construct
# AUTHOR_EMAIL (see above).
DOMAIN = "gordas.dev"
# Points the fork's OWN built-in update checker (update_check.py) at OUR
# releases, not upstream's — a rebranded app must never send users to a
# different project's GitHub page when it says "check for updates".
DEVELOPMENT_HOME_PAGE = "https://github.com/gordasgdc/displaycal-py3"
GITHUB_API_URL = "https://api.github.com/repos/gordasgdc/displaycal-py3"
# ArgyllCMS publishes its own changelog; displaycal.net only ever mirrored an
# old copy of it (last updated for V3.0.1), so fetch it straight from the
# source instead of the stale local mirror.
ARGYLL_CHANGELOG_DOMAIN = "www.argyllcms.com"
ARGYLL_CHANGELOG_PATH = "doc/ChangesSummary.html"

# Adresele REALE ale autorilor originali — NICIODATĂ derivate din DOMAIN
# (vezi comentariul de mai sus), ca rebranding-ul să nu creeze o adresă de
# email falsă pe domeniul nostru.
AUTHOR_EMAIL = ", ".join(
    [
        f"florian{chr(0o100)}displaycal.net",
        f"eoyilmaz{chr(0o100)}gmail.com",
    ]
)
# NAME NU devine "DisplayCAL-CG" (2026-09-05, corectat dupa un build real
# esuat — nu doar presupus corect din citirea codului): `NAME` e folosit in
# ~70 de locuri din `_setup.py` ca identificator LITERAL de pachet Python
# (`package_dir: {NAME: NAME}`, `provides: [NAME]`, chei in `package_data`),
# nu doar ca text de afisat. Doua erori reale, gasite abia rulind efectiv
# `pip install -e .`:
#   1. `distutils.versionpredicate` respinge `provides=["DisplayCAL-CG"]`
#      (cratima nu e permisa intr-un identificator "Provides" — ValueError).
#   2. Chiar daca (1) ar fi ocolit, `package_dir`/`package_data` cauta un
#      folder fizic numit "DisplayCAL-CG" — care nu exista (folderul de pe
#      disc, si toate cele ~mii de `import DisplayCAL`/`from DisplayCAL...`
#      din tot codul, raman "DisplayCAL", neschimbabil fara un refactor
#      urias si riscant al intregului pachet).
# Identitatea vizuala "DisplayCAL-CG" ramane completa — nume produs,
# iconite, pagina web, installer — dar traieste EXCLUSIV in stringuri pure
# (AUTHOR/DESCRIPTION mai sus, NAME_HTML), in numele pachetelor de
# distributie (.pkg/.exe, construite de scripturile noastre proprii de
# packaging, NU de acest NAME), si in fisierele de iconite (care raman
# denumite dupa NAME="DisplayCAL", neschimbat — continutul lor e noul
# desen, doar numele fisierului e cel vechi).
NAME = "DisplayCAL"
APPSTREAM_ID = ".".join(reversed([NAME, *DOMAIN.split(".")]))
NAME_HTML = '<span class="appname">Display<span>CAL</span></span>'

PY_MINVERSION = (3, 10)
PY_MAXVERSION = (3, 14)

VERSION_LIN = VERSION_STRING  # Linux
VERSION_MAC = VERSION_STRING  # Mac OS X
VERSION_WIN = VERSION_STRING  # Windows
VERSION_SRC = VERSION_STRING
# follow semver format
VERSION_TUPLE = tuple(int(n) for n in VERSION_STRING.split("-")[0].split(".")[:3])
"""tuple[int, int, int]: The version number as a tuple of integers."""

WX_MINVERSION = (4, 0, 0)
WX_RECVERSION = (4, 2, 0)


def get_latest_changelog_entry(readme: str) -> None | str:
    """Get changelog entry for latest version from ReadMe HTML.

    Args:
        readme (str): ReadMe HTML content.

    Returns:
        None | str: Changelog entry or None if not found.
    """
    changelog = re.search(
        r'<div id="(?:changelog|history)">.+?<h2>.+?</h2>.+?<dl>.+?</dd>', readme, re.S
    )

    if changelog:
        changelog = changelog.group()
        changelog = re.sub(r'\s*<div id="(?:changelog|history)">\n?', "", changelog)
        changelog = re.sub(r"\s*</?d[ld]>\n?", "", changelog)
        changelog = re.sub(r"\s*<(h[23])>.+?</\1>\n?", "", changelog)

    return changelog


def script2pywname(script: str) -> str:
    """Convert all-lowercase script name to mixed-case pyw name."""
    a2b = {
        f"{NAME}-3dlut-maker": f"{NAME}-3DLUT-maker",
        f"{NAME}-vrml-to-x3d-converter": f"{NAME}-VRML-to-X3D-converter",
        f"{NAME}-eecolor-to-madvr-converter": f"{NAME}-eeColor-to-madVR-converter",
    }
    if script.lower().startswith(NAME.lower()):
        pyw = f"{NAME}{script[len(NAME) :]}"
        return a2b.get(pyw, pyw)
    return script
