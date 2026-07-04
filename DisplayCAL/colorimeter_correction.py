"""Toolkit-neutral internals of the colorimeter-correction (CCMX/CCSS) pipeline.

The pure, window-agnostic pieces of ``MainFrame.create_colorimeter_correction_handler``
(``display_cal.py``): the Argyll / CGATS work that carries no wx (or Qt)
dependency, so both the shipping wx path and the future Qt window can call into
them. A plain ``DisplayCAL`` module (like ``main_settings.py`` /
``measurement_report.py``) so importing it never pulls in Qt.

The dialogs (create wizard, details prompt, the reference-vs-corrected preview
grid), the ``worker.Worker`` execution (``spec2cie`` / ``ccxxmake`` /
``create_ccxx``), and the file-save flow stay in their respective UI layers.
"""

from __future__ import annotations

import re

# The keyword injection order, top-to-bottom, must match the wx handler so the
# emitted CCXX bytes are identical (each field is inserted immediately above the
# DISPLAY line, so insertion order == line order).
_CCXX_METADATA_ORDER = (
    "reference",
    "technology",
    "manufacturer_id",
    "manufacturer",
    "observer",
    "reference_observer",
)
_CCXX_KEYWORDS = {
    "reference": b"REFERENCE",
    "technology": b"TECHNOLOGY",
    "manufacturer_id": b"MANUFACTURER_ID",
    "manufacturer": b"MANUFACTURER",
    "observer": b"OBSERVER",
    "reference_observer": b"REFERENCE_OBSERVER",
}


def _to_bytes(value: str | bytes) -> bytes:
    """Return ``value`` as UTF-8 bytes (passing bytes through unchanged)."""
    if isinstance(value, str):
        return value.encode("utf-8")
    return value


def _insert_ccxx_field(cgats: bytes, keyword: bytes, value: bytes) -> bytes:
    """Insert ``keyword "value"`` immediately above the ``DISPLAY`` line.

    A no-op if the keyword is already present. Backslashes in ``value`` are
    escaped so they survive the ``re.sub`` replacement as literals (matching the
    wx handler).
    """
    if re.search(rb"\n" + keyword + rb'\s+".+?"\n', cgats):
        return cgats
    escaped = value.replace(b"\\", b"\\\\")
    return re.sub(
        rb'(\nDISPLAY\s+"[^"]*"\n)',
        b"\n" + keyword + b' "' + escaped + b'"\\1',
        cgats,
    )


def inject_ccxx_metadata(
    cgats: bytes,
    *,
    reference: str | bytes | None = None,
    technology: str | bytes | None = None,
    manufacturer_id: str | bytes | None = None,
    manufacturer: str | bytes | None = None,
    observer: str | bytes | None = None,
    reference_observer: str | bytes | None = None,
) -> bytes:
    """Inject the optional CCMX/CCSS metadata fields Argyll omits by default.

    Ports the ``REFERENCE`` / ``TECHNOLOGY`` / ``MANUFACTURER_ID`` /
    ``MANUFACTURER`` / ``OBSERVER`` / ``REFERENCE_OBSERVER`` byte rewrites in
    ``create_colorimeter_correction_handler``. Each field is added only when a
    truthy value is supplied and the keyword is not already present, inserted
    above the ``DISPLAY`` line in the fixed order above. ``str`` values are
    UTF-8 encoded (the wx path emitted a mix of already-bytes and UTF-8 encoded
    values; normalising here is byte-identical for real-world inputs, which
    never contain backslashes).

    Args:
        cgats: The raw CCXX file bytes as emitted by ``ccxxmake`` /
            ``create_ccxx`` (must not be re-parsed CGATS, whose keyword order
            may differ, changing the MD5).
        reference: Reference instrument (``TARGET_INSTRUMENT``).
        technology: Display technology string.
        manufacturer_id: PnP manufacturer id.
        manufacturer: Manufacturer name.
        observer: Colorimeter observer.
        reference_observer: Reference observer.

    Returns:
        The (possibly) modified CCXX bytes.
    """
    values = {
        "reference": reference,
        "technology": technology,
        "manufacturer_id": manufacturer_id,
        "manufacturer": manufacturer,
        "observer": observer,
        "reference_observer": reference_observer,
    }
    for field in _CCXX_METADATA_ORDER:
        value = values[field]
        if value:
            cgats = _insert_ccxx_field(cgats, _CCXX_KEYWORDS[field], _to_bytes(value))
    return cgats
