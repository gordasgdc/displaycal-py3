"""Sources behind the preparation and placement guidance of the guided flow.

Every recommendation the guide shows about warming up the monitor, room light
or instrument placement points to one or more of these sources, so the user can
see *who says so* and judge it. Nothing here is a universal rule: figures such
as the 30 minutes in the Datacolor guide are that vendor's recommendation for
its own product and are shown as such.

Checked on 2026-10-19. Page numbers refer to the documents as downloaded then.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    """A documented source of guidance."""

    key: str
    title: str
    url: str
    #: What this source is used for (kept short; shown with the source).
    covers: str


SOURCES: dict[str, Source] = {
    "displaycal": Source(
        "displaycal",
        "DisplayCAL documentation (bundled README): drift compensation, "
        "measuring ambient light",
        "https://displaycal.net/",
        "Drift compensation for a warming-up display or instrument; ambient "
        "light is measured with the instrument pointing up, beside the display.",
    ),
    "argyll_dispcal": Source(
        "argyll_dispcal",
        "ArgyllCMS dispcal documentation",
        "https://www.argyllcms.com/doc/dispcal.html",
        "No fixed warm-up time: white-level drift compensation exists for a "
        "display that is still warming up; black calibration on an opaque "
        "surface away from stray light; ambient light can be taken into account.",
    ),
    "argyll_instruments": Source(
        "argyll_instruments",
        "ArgyllCMS instrument documentation",
        "https://www.argyllcms.com/doc/instruments.html",
        "Which commercial names share one driver; ambient mode on spectrometers "
        "is manual (diffuser fitted by the user).",
    ),
    "datacolor_spyderx": Source(
        "datacolor_spyderx",
        "Datacolor SpyderX User Guide (pp. 12, 19, 21)",
        "https://www.datacolor.com/spyder/wp-content/uploads/2023/05/SpyderX-User-Guide.pdf",
        "Display powered up at least 30 minutes (vendor recommendation); no "
        "direct light on the display; display controls at defaults; direct USB "
        "port; the sensor cover is used as counterweight and the display may be "
        "tilted back slightly so the unit stays flat without being held.",
    ),
    "calibrite_qsg": Source(
        "calibrite_qsg",
        "Calibrite ColorChecker Display Quick Start Guide (pp. 7-14)",
        "https://www.manualslib.com/manual/4091722/Calibrite-Colorchecker-Display.html",
        "Diffuser arm lifted before rotating, rear position for display "
        "measurements; optics in contact with the centre of the display, foam "
        "pad flat; cable and counterweight behind the display, counterweight "
        "adjusted to the display size; ambient: device on the work surface "
        "next to the display with the diffuser pointing up.",
    ),
}
