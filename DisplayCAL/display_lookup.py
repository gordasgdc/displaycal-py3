"""Finding out what a monitor is: model detection and honest lookup actions.

What the two sites really offer (checked 2026-10-19, see ``docs/SOURCES_DISPLAY_LOOKUP.md``):

* **everymac.com** -- a *GET* form: ``https://everymac.com/ultimate-mac-lookup/
  ?identify=<identifier>`` shows the Macs with that *Model Identifier*
  (e.g. ``Mac14,9``). It also accepts serial numbers; this module never builds
  a lookup from anything but a model identifier.
* **displayspecifications.com** -- its search box is an autocomplete script;
  there is no results-page URL (the paths that look like one return the
  generic page). So no search URL is built: the model is copied and the site's
  home page opened.

Nothing here talks to the network, and nothing here selects a correction: what a
site says about a monitor helps to *recognise* it; the colorimeter correction
stays the user's confirmed choice.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from urllib.parse import quote

EVERYMAC_HOME = "https://everymac.com/"
EVERYMAC_LOOKUP = "https://everymac.com/ultimate-mac-lookup/"
DISPLAYSPECS_HOME = "https://www.displayspecifications.com/"
ARGYLL_CCXXMAKE_DOC = "https://www.argyllcms.com/doc/ccxxmake.html"

APPLE_BUILTIN = "apple_builtin"
EXTERNAL = "external"
UNKNOWN = "unknown"

#: ``Mac14,9``, ``MacBookPro18,3``, ``iMac21,1``, ``Macmini9,1`` ...
_MAC_ID = re.compile(r"^(Mac|MacBook|MacBookPro|MacBookAir|iMac|iMacPro|Macmini|MacPro|MacStudio)\d{1,3},\d{1,2}$")
#: Names Apple's built-in panels are reported under.
_BUILTIN_NAMES = re.compile(
    r"^(color lcd|built-?in\b.*|retina display|liquid retina.*|imac|macbook.*display)$", re.I
)
_POSITION = re.compile(r"\s*@\s*-?\d+,.*$")
_FLAGS = re.compile(r"\s*\[[^\]]*\]\s*")
#: "serial: X" / "s/n X" fragments never belong in a query (model names stay intact).
_SERIAL_LIKE = re.compile(r"(?i)\b(serial(?: number)?|s/n)\b\W*\S+")


@dataclass(frozen=True)
class DisplayModel:
    """What is known about the selected monitor."""

    name: str  # as detected (may be corrected by the user)
    kind: str  # APPLE_BUILTIN / EXTERNAL / UNKNOWN
    mac_model_id: str | None = None  # only for an Apple built-in panel
    corrected: bool = False  # the user edited the text


@dataclass(frozen=True)
class LookupAction:
    """One honest thing the user can do to look the model up."""

    key: str  # language key of the button label
    url: str  # what to open
    copy_text: str | None  # what to put on the clipboard first (None: nothing)
    site: str  # everymac.com / displayspecifications.com
    direct: bool  # the URL is a real lookup of this model (not just a home page)
    note_key: str | None = None  # language key of an explanation (e.g. ambiguity)


def clean_name(display: str) -> str:
    """Display text of an Argyll entry without position/flags or serial-like parts."""
    text = _POSITION.sub("", display or "")
    text = _FLAGS.sub(" ", text)
    text = _SERIAL_LIKE.sub("", text)
    return " ".join(text.split())[:80]


def hardware_model() -> str | None:
    """The Mac's model identifier (``sysctl hw.model``), or ``None`` elsewhere."""
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "hw.model"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return out if _MAC_ID.match(out) else None


def detect(
    display_entry: str,
    platform: str | None = None,
    hw_model: str | None | bool = False,
) -> DisplayModel:
    """Classify the selected display.

    An Apple *built-in* panel is recognised only on macOS and only by the names
    Apple's panels are reported under (or the Mac identifier itself); its Mac
    model identifier comes from the hardware. Any other display -- including an
    external monitor attached to a Mac -- is ``EXTERNAL``.

    Args:
        display_entry: The Argyll display entry (``"BenQ PD3200U @ 1512, 0, ..."``).
        platform: ``sys.platform`` override (tests).
        hw_model: The Mac identifier override (tests); ``False`` = ask the system.
    """
    platform = platform or sys.platform
    name = clean_name(display_entry)
    if not name:
        return DisplayModel("", UNKNOWN)
    if platform == "darwin" and (_MAC_ID.match(name) or _BUILTIN_NAMES.match(name)):
        model_id = hardware_model() if hw_model is False else hw_model
        if _MAC_ID.match(name):
            model_id = name
        return DisplayModel(name, APPLE_BUILTIN, model_id or None)
    return DisplayModel(name, EXTERNAL)


def corrected(model: DisplayModel, text: str) -> DisplayModel:
    """The model after the user edited the text.

    Editing never turns a monitor into an Apple built-in one by itself, except
    when the text is exactly a Mac model identifier on macOS.
    """
    text = clean_name(text)
    if not text:
        return DisplayModel("", UNKNOWN, corrected=True)
    if _MAC_ID.match(text) and sys.platform == "darwin":
        return DisplayModel(text, APPLE_BUILTIN, text, True)
    kind = EXTERNAL if model.kind == APPLE_BUILTIN else (model.kind if model.kind != UNKNOWN else EXTERNAL)
    return DisplayModel(text, kind, model.mac_model_id if kind == APPLE_BUILTIN else None, True)


def everymac_url(model_id: str) -> str | None:
    """The EveryMac lookup URL for a Mac model identifier, or ``None``.

    Only a well-formed *model identifier* is accepted, so a serial number or any
    other identifier can never end up in this URL.
    """
    if not model_id or not _MAC_ID.match(model_id):
        return None
    return f"{EVERYMAC_LOOKUP}?identify={quote(model_id, safe='')}"


def actions(model: DisplayModel) -> list[LookupAction]:
    """What can really be offered for this model (never invented URLs)."""
    out: list[LookupAction] = []
    if model.kind == APPLE_BUILTIN:
        url = everymac_url(model.mac_model_id or "")
        if url:
            out.append(
                LookupAction(
                    "lookup.act.everymac_id",
                    url,
                    None,
                    "everymac.com",
                    True,
                    "lookup.note.several_variants",
                )
            )
        else:
            out.append(
                LookupAction(
                    "lookup.act.everymac_home",
                    EVERYMAC_HOME,
                    model.name or None,
                    "everymac.com",
                    False,
                    "lookup.note.no_mac_id",
                )
            )
        return out
    out.append(
        LookupAction(
            "lookup.act.copy_open_specs",
            DISPLAYSPECS_HOME,
            model.name or None,
            "displayspecifications.com",
            False,
            "lookup.note.paste_in_search" if model.name else "lookup.note.no_model",
        )
    )
    return out
