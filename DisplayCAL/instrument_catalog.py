"""Instrument catalogue for the guided workflow (identification + placement help).

This module is deliberately toolkit-neutral and has no side effects: it maps the
instrument *names Argyll reports* (see :mod:`DisplayCAL.argyll_instruments`) to
human-oriented families that carry a plain-language description, probe
placement steps and the accessories the guided flow should mention.

Identification is honest about uncertainty. Argyll reports a single identifier
for hardware families that are sold under several commercial names (for example
``"i1 DisplayPro, ColorMunki Display"``, which the ArgyllCMS documentation lists
together with the Calibrite ColorChecker Display / Pro / Plus and "other branded
i1d3's"; or ``"SpyderX2"`` / ``"Spyder 2024"``, which share a USB ID). For such
families :func:`identify` returns ``certain=False`` and the user interface must
ask the user to confirm the commercial model instead of presenting a guess as a
fact.

Provenance of the descriptive text: the family grouping and the "which names
share one driver" facts come from the ArgyllCMS instrument documentation
(https://www.argyllcms.com/doc/instruments.html); placement steps are generic
good practice for display measurement and, where an instrument needs its own
calibration position, defer to the prompts shown by the measurement engine.
Illustrations in ``DisplayCAL/theme/instruments`` are original artwork, not
manufacturer photographs; no endorsement, certification or partnership with any
manufacturer is implied.
"""

from __future__ import annotations

from dataclasses import dataclass

from DisplayCAL.argyll_instruments import (
    get_canonical_instrument_name,
)
from DisplayCAL.argyll_instruments import instruments as argyll_instruments

# Placement/illustration kinds (the key also names the SVG in theme/instruments).
KIND_COLORIMETER = "colorimeter"  # puck-style, sits on the screen
KIND_SPECTRO_PUCK = "spectro_puck"  # ColorMunki-style spectrophotometer
KIND_SPECTRO_PEN = "spectro_pen"  # i1 Pro-style spectrophotometer
KIND_OTHER = "other"  # tele-spectroradiometers, built-in meters, DIY, dummy


@dataclass(frozen=True)
class InstrumentFamily:
    """A group of instruments the Argyll driver cannot tell apart.

    Attributes:
        key: Stable identifier.
        argyll_names: Instrument names exactly as Argyll/``argyll_instruments``
            report them.
        brand_hint: Manufacturer(s) as stated in the ArgyllCMS documentation.
        commercial_names: Names the user may recognise from the box; shown as
            candidates when ``ambiguous`` is true.
        ambiguous: ``True`` when several commercial products share this driver
            identity, so the model must be confirmed by the user.
        kind: One of the ``KIND_*`` constants (selects illustration/placement).
        spectral: ``True`` for spectrophotometers (can create their own spectral
            corrections and need no colorimeter correction).
        needs_reference_tile: ``True`` when the instrument calibrates its sensor
            on a reference tile or base (Argyll ``sensor_cal``).
        ambient: ``True`` when the family has an ambient-light measurement
            option for at least one commercial model (model dependent).
    """

    key: str
    argyll_names: tuple[str, ...]
    brand_hint: str
    commercial_names: tuple[str, ...]
    ambiguous: bool
    kind: str
    spectral: bool
    needs_reference_tile: bool
    ambient: bool = False


FAMILIES: tuple[InstrumentFamily, ...] = (
    InstrumentFamily(
        key="i1d3",
        argyll_names=("i1 DisplayPro, ColorMunki Display",),
        brand_hint="X-Rite / Calibrite",
        commercial_names=(
            "X-Rite i1Display Pro",
            "X-Rite i1Display Pro Plus",
            "X-Rite ColorMunki Display",
            "X-Rite i1Display Studio",
            "Calibrite ColorChecker Display / Pro / Plus",
        ),
        ambiguous=True,
        kind=KIND_COLORIMETER,
        spectral=False,
        needs_reference_tile=False,
        ambient=True,
    ),
    InstrumentFamily(
        key="i1d2",
        argyll_names=("i1 Display 2", "i1 Display", "i1 Display 1"),
        brand_hint="X-Rite / GretagMacbeth",
        commercial_names=(
            "Eye-One Display 1",
            "Eye-One Display 2",
            "Eye-One Display LT",
        ),
        ambiguous=True,
        kind=KIND_COLORIMETER,
        spectral=False,
        needs_reference_tile=False,
    ),
    InstrumentFamily(
        key="colormunki_photo",
        argyll_names=("ColorMunki",),
        brand_hint="X-Rite",
        commercial_names=("X-Rite ColorMunki Photo", "X-Rite ColorMunki Design"),
        ambiguous=True,
        kind=KIND_SPECTRO_PUCK,
        spectral=True,
        needs_reference_tile=True,
        ambient=True,
    ),
    InstrumentFamily(
        key="colormunki_smile",
        argyll_names=("ColorMunki Smile",),
        brand_hint="X-Rite",
        commercial_names=("X-Rite ColorMunki Smile", "X-Rite ColorMunki Create"),
        ambiguous=True,
        kind=KIND_COLORIMETER,
        spectral=False,
        needs_reference_tile=False,
    ),
    InstrumentFamily(
        key="i1pro",
        argyll_names=("i1 Pro", "i1 Pro 2", "i1 Pro 3", "i1 Monitor"),
        brand_hint="X-Rite",
        commercial_names=(
            "X-Rite i1Pro",
            "X-Rite i1Pro 2",
            "X-Rite i1Pro 3 / 3 Plus",
            "X-Rite i1 Monitor",
        ),
        ambiguous=True,
        kind=KIND_SPECTRO_PEN,
        spectral=True,
        needs_reference_tile=True,
        ambient=True,
    ),
    InstrumentFamily(
        key="spyder_x",
        argyll_names=("SpyderX", "SpyderX2", "Spyder 2024"),
        brand_hint="Datacolor",
        commercial_names=(
            "Datacolor SpyderX Pro / Elite",
            "Datacolor Spyder X2 Pro / Elite / Ultra",
        ),
        ambiguous=True,
        kind=KIND_COLORIMETER,
        spectral=False,
        needs_reference_tile=True,
        ambient=True,
    ),
    InstrumentFamily(
        key="spyder_5",
        argyll_names=("Spyder5", "Spyder4", "Spyder3", "Spyder2", "Spyder1"),
        brand_hint="Datacolor",
        commercial_names=(
            "Datacolor Spyder5 Express / Pro / Elite",
            "Datacolor Spyder4 Express / Pro / Elite",
            "Datacolor Spyder3",
        ),
        ambiguous=True,
        kind=KIND_COLORIMETER,
        spectral=False,
        needs_reference_tile=False,
        ambient=True,
    ),
    InstrumentFamily(
        key="huey",
        argyll_names=("Huey",),
        brand_hint="X-Rite / Pantone",
        commercial_names=("Pantone Huey", "Pantone Huey Pro"),
        ambiguous=True,
        kind=KIND_COLORIMETER,
        spectral=False,
        needs_reference_tile=False,
    ),
    InstrumentFamily(
        key="colorhug",
        argyll_names=("ColorHug", "ColorHug2"),
        brand_hint="Hughski",
        commercial_names=("Hughski ColorHug", "Hughski ColorHug2"),
        ambiguous=False,
        kind=KIND_COLORIMETER,
        spectral=False,
        needs_reference_tile=False,
    ),
    InstrumentFamily(
        key="dtp9x",
        argyll_names=("DTP92", "DTP94"),
        brand_hint="X-Rite",
        commercial_names=("X-Rite DTP92", "X-Rite DTP94 (Optix)"),
        ambiguous=False,
        kind=KIND_COLORIMETER,
        spectral=False,
        needs_reference_tile=False,
    ),
    InstrumentFamily(
        key="other",
        argyll_names=(
            "Spectrolino",
            "SpectroScan",
            "SpectroScanT",
            "Spectrocam",
            "EX1",
            "K-10",
            "specbos",
            "specbos 1201",
            "spectraval",
            "Colorimtre HCFR",
        ),
        brand_hint="various",
        commercial_names=(),
        ambiguous=False,
        kind=KIND_OTHER,
        spectral=False,
        needs_reference_tile=False,
    ),
)

_BY_ARGYLL_NAME: dict[str, InstrumentFamily] = {
    name: family for family in FAMILIES for name in family.argyll_names
}


@dataclass(frozen=True)
class Identification:
    """Result of identifying an instrument from the name Argyll reported."""

    detected_name: str  # exactly what the engine reported
    family: InstrumentFamily | None
    certain: bool  # False => ask the user to confirm the commercial model
    candidates: tuple[str, ...]  # commercial names to offer when not certain


def identify(detected_name: str | None) -> Identification | None:
    """Identify an instrument from the name Argyll reported.

    Args:
        detected_name: Instrument name from the enumeration (may carry a vendor
            prefix, which is stripped to the canonical Argyll name).

    Returns:
        ``None`` when nothing is selected/detected. Otherwise an
        :class:`Identification`; unknown instruments get ``family=None`` and are
        shown under their detected name only (never guessed).
    """
    if not detected_name:
        return None
    name = get_canonical_instrument_name(detected_name)
    family = _BY_ARGYLL_NAME.get(name) or _BY_ARGYLL_NAME.get(detected_name)
    if family is None:
        return Identification(name, None, False, ())
    if family.ambiguous:
        return Identification(name, family, False, family.commercial_names)
    return Identification(name, family, True, family.commercial_names)


def usb_ids_for(argyll_name: str) -> list[tuple[int, int]]:
    """Return the ``(vid, pid)`` pairs Argyll's table lists for an instrument."""
    entry = argyll_instruments.get(argyll_name, {})
    return [(u["vid"], u["pid"]) for u in entry.get("usb_ids", [])]


def shared_usb_identity(argyll_name: str) -> list[str]:
    """Other Argyll names that carry the same USB ID(s) as ``argyll_name``.

    A non-empty result means the USB identity alone cannot tell the models apart.
    """
    mine = set(usb_ids_for(argyll_name))
    if not mine:
        return []
    return sorted(
        other
        for other in argyll_instruments
        if other != argyll_name and mine & set(usb_ids_for(other))
    )


@dataclass(frozen=True)
class PlacementSequence:
    """The physical placement steps to show for an instrument.

    ``verified`` is true only when the steps come from a manufacturer document
    for exactly the model the user confirmed; otherwise the generic, honest
    steps are returned and ``needs_model_choice`` says whether confirming the
    model would unlock model-specific ones.
    """

    steps: tuple[str, ...]  # step ids, in order
    verified: bool
    #: Variant key for the step texts (``guide.pl.<variant>.<step>``).
    variant: str
    sources: tuple[str, ...]  # keys of DisplayCAL.guide_sources.SOURCES
    accessories: tuple[str, ...]  # ``guide.acc.<key>``
    needs_model_choice: bool
    kind: str


#: Models for which a manufacturer document describes the physical steps:
#: ``candidate name -> (variant, steps, sources, accessories)``.
VERIFIED_MODELS: dict[
    str, tuple[str, tuple[str, ...], tuple[str, ...], tuple[str, ...]]
] = {
    "Calibrite ColorChecker Display / Pro / Plus": (
        "i1d3",
        ("face", "diffuser", "cable", "contact", "position"),
        ("calibrite_qsg",),
        ("counterweight", "ambient_diffuser"),
    ),
    "Datacolor SpyderX Pro / Elite": (
        "spyder_x",
        ("face", "cover", "contact", "tilt", "position"),
        ("datacolor_spyderx",),
        ("sensor_cover",),
    ),
}

GENERIC_STEPS = ("face", "contact", "position")


def resolve_placement(
    ident: Identification | None, chosen_model: str | None = None
) -> PlacementSequence:
    """Return the placement steps for the detected instrument and chosen model."""
    kind = ident.family.kind if ident and ident.family else KIND_OTHER
    needs_tile = bool(ident and ident.family and ident.family.needs_reference_tile)
    generic = (("calibrate",) if needs_tile else ()) + GENERIC_STEPS
    if ident and ident.family and chosen_model in VERIFIED_MODELS:
        variant, steps, sources, accessories = VERIFIED_MODELS[chosen_model]
        return PlacementSequence(
            steps, True, variant, sources, accessories, False, kind
        )
    unlock = bool(
        ident
        and ident.family
        and not ident.certain
        and any(c in VERIFIED_MODELS for c in ident.candidates)
        and chosen_model is None
    )
    return PlacementSequence(generic, False, "generic", (), (), unlock, kind)
