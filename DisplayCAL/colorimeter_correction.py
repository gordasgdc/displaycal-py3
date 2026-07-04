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

import os
import re
import sys
from hashlib import md5
from time import strftime, strptime, struct_time
from typing import TYPE_CHECKING

from DisplayCAL import ccmx, colord, config
from DisplayCAL import localization as lang
from DisplayCAL.argyll import make_argyll_compatible_path
from DisplayCAL.argyll_instruments import get_canonical_instrument_name
from DisplayCAL.cgats import CGATS, CGATSError
from DisplayCAL.config import EXE_EXT
from DisplayCAL.debughelpers import Error, Info, Warn
from DisplayCAL.util_os import get_program_file, getenvu, safe_glob, which

if TYPE_CHECKING:
    from DisplayCAL.worker import Worker

#: Hash algorithms accepted for the upload dedup/verification hash. Matches
#: the wx handler's ``globals()[algo_hash[0]]`` lookup, which in practice only
#: ever resolved ``"md5"`` (the only hash function imported at module scope).
_HASH_ALGORITHMS = {"md5": md5}

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


def get_cgats_path(cgats: bytes) -> str:
    """Return the default save path for a CCMX/CCSS file's raw bytes.

    Ports ``display_cal.get_cgats_path``: the file is named after the
    ``DESCRIPTOR`` field (falling back to "unnamed"), sanitised for the
    filesystem and Argyll, with the extension taken from the CGATS type
    keyword on the first line (``CCMX`` / ``CCSS``), saved under the Argyll
    data dir.

    Args:
        cgats: The raw CCXX file bytes.

    Returns:
        The full path to save the file to.
    """
    descriptor = re.search(rb'\nDESCRIPTOR\s+"(.+?)"\n', cgats)
    descriptor = descriptor.groups()[0] if descriptor else b""
    description = descriptor.decode("utf-8") or lang.getstr("unnamed")
    name = make_argyll_compatible_path(description, is_name=True)[:255]
    extension = cgats.split()[0].lower().decode("utf-8")
    return os.path.join(config.get_argyll_data_dir(), f"{name}.{extension}")


# -- Web check ----------------------------------------------------------------

#: Localized-label lookup for the "type" column, keyed by the CGATS type
#: keyword (matches ``colorimeter_correction_web_check_choose``).
_WEB_CHECK_TYPE_LABELS = {
    "CCSS": lambda: lang.getstr("spectral").replace(":", ""),
    "CCMX": lambda: lang.getstr("matrix").replace(":", ""),
}

_MONTH_ABBREVIATIONS = {
    "Jan": "01",
    "Feb": "02",
    "Mar": "03",
    "Apr": "04",
    "May": "05",
    "Jun": "06",
    "Jul": "07",
    "Aug": "08",
    "Sep": "09",
    "Oct": "10",
    "Nov": "11",
    "Dec": "12",
}


def build_web_check_params(worker: Worker) -> dict:
    """Build the GET params for the online colorimeter-correction lookup.

    Toolkit-neutral port of the param-building half of
    ``MainFrame.colorimeter_correction_web_handler`` (the ``http_request``
    call itself, and its progress reporting, stay with the caller).

    Args:
        worker: The running :class:`DisplayCAL.worker.Worker`, used to derive
            the current display/instrument.

    Returns:
        dict: The request params (``get``, ``type``, ``manufacturer_id``,
            ``display``, ``instrument``, ``json``).
    """
    filetype = "ccss,ccmx" if worker.instrument_supports_ccss() else "ccmx"
    return {
        "get": True,
        "type": filetype,
        "manufacturer_id": worker.get_display_edid().get("manufacturer_id", ""),
        "display": worker.get_display_name(False, True) or "Unknown",
        "instrument": worker.get_instrument_name() or "Unknown",
        "json": 1,
    }


def _web_check_spectral_resolution(item: dict) -> str:
    spectral = {}
    for key in ("bands", "start_nm", "end_nm"):
        try:
            v = float(item.get(f"spectral_{key}", 0))
        except (TypeError, ValueError):
            continue
        if v:
            spectral[key] = v
    if not spectral or len(spectral) < 3:
        return lang.getstr("unknown")
    return "{:.1f}nm, {:.0f}-{:.0f}nm".format(
        (spectral["end_nm"] - spectral["start_nm"]) / (spectral["bands"] - 1),
        spectral["start_nm"],
        spectral["end_nm"],
    )


def _web_check_created(item: dict) -> str:
    created = item.get("created")
    if not created:
        return lang.getstr("unknown")
    try:
        created = strptime(created)
    except ValueError:
        datetmp = re.search(
            r"\w+ (\w{3}) (\d{2}) (\d{2}(?::[0-5][0-9]){2}) (\d{4})", created
        )
        if not datetmp:
            return created
        year, month_abbr, day, time_part = (
            datetmp.groups()[3],
            datetmp.groups()[0],
            datetmp.groups()[1],
            datetmp.groups()[2],
        )
        datetmp = f"{year}-{_MONTH_ABBREVIATIONS.get(month_abbr)}-{day} {time_part}"
        try:
            created = strptime(datetmp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return item["created"]
    if isinstance(created, struct_time):
        return strftime("%Y-%m-%d %H:%M:%S", created)
    return created


def parse_web_check_entries(
    entries: list[dict], observer_labels: None | dict[str, str] = None
) -> list[dict]:
    """Turn JSON correction entries from the online DB into display-ready rows.

    Toolkit-neutral port of the per-entry loop in
    ``colorimeter_correction_web_check_choose`` (everything except building
    and driving the wx list-control dialog): CGATS parsing, the
    manufacturer/display quirking, the spectral-resolution summary, the
    created-date normalisation and the fit-method label. Fixes a latent bug
    in the wx handler: it looked ``REFERENCE_OBSERVER`` (``queryv1`` returns
    ``bytes``) up directly in the str-keyed ``observers_ab`` map, so the
    lookup never matched and the "observer" column always showed "unknown".
    This port decodes the key first, so a supplied ``observer_labels`` map
    actually resolves.

    Args:
        entries: The parsed JSON list from the web-check response (a list of
            ``dict``, each describing one correction).
        observer_labels: Optional ``observer value -> localized label`` map
            (see :func:`DisplayCAL.ui.measurement_flow.observer_items`), used
            for the ``REFERENCE_OBSERVER`` column. Defaults to no lookup
            (raw observer key, or "unknown"/"not_applicable").

    Returns:
        list[dict]: One row per entry, each with ``cgats`` (raw bytes,
            required to save byte-identically) plus the display fields
            ``type``, ``description``, ``display``, ``reference``,
            ``spectral_resolution``, ``observer``, ``fit_method``,
            ``fit_avg_de00``, ``fit_max_de00``, ``created``.
    """
    observer_labels = observer_labels or {}
    rows = []
    for item in entries:
        # CGATS is byte string based, make sure to encode Unicode back to
        # UTF-8 for parsing. CGATS accepts ``bytes`` data only.
        cgats_bytes = item.get("cgats", "").encode("utf-8")
        try:
            ccxx = CGATS(cgats_bytes)
        except CGATSError:
            cgats_bytes = b""
            ccxx = CGATS()
        ccxx = ccxx.get(0, ccxx)
        ccxx_type = item.get("type", "").upper()
        manufacturer = colord.quirk_manufacturer(
            item.get("manufacturer") or lang.getstr("unknown")
        )
        display = item.get("display") or lang.getstr("unknown")
        if config.is_virtual_display(display):
            display = manufacturer
        if not display.lower().startswith(manufacturer.lower()):
            display = f"{manufacturer} {display}"
        fit_method = ccxx.queryv1("FIT_METHOD")
        if fit_method and fit_method != b"xy":
            fit_method = lang.getstr("perceptual")
        elif isinstance(fit_method, bytes):
            # Same bytes/str inconsistency as REFERENCE_OBSERVER above: only
            # the "perceptual" branch localized to str, leaving the raw "xy"
            # case as bytes.
            fit_method = fit_method.decode("utf-8")
        is_ccmx = ccxx_type == "CCMX"
        reference_observer = ccxx.queryv1("REFERENCE_OBSERVER")
        if isinstance(reference_observer, bytes):
            # The wx handler looked this bytes value up in a str-keyed dict
            # directly, so it never matched (always fell through to
            # "unknown"/"not_applicable"); decode so the lookup actually
            # works.
            reference_observer = reference_observer.decode("utf-8")
        rows.append(
            {
                "cgats": cgats_bytes,
                "type": _WEB_CHECK_TYPE_LABELS.get(ccxx_type, lambda t=ccxx_type: t)(),
                "description": get_canonical_instrument_name(
                    item.get("description") or lang.getstr("unknown")
                ),
                "display": display,
                "reference": get_canonical_instrument_name(
                    item.get("reference") or lang.getstr("unknown")
                ),
                "spectral_resolution": _web_check_spectral_resolution(item),
                "observer": observer_labels.get(
                    reference_observer,
                    lang.getstr("unknown" if is_ccmx else "not_applicable"),
                ),
                "fit_method": (
                    (fit_method or lang.getstr("unknown"))
                    if is_ccmx
                    else lang.getstr("not_applicable")
                ),
                "fit_avg_de00": (
                    str(ccxx.queryv1("FIT_AVG_DE00") or lang.getstr("unknown"))
                    if is_ccmx
                    else lang.getstr("not_applicable")
                ),
                "fit_max_de00": (
                    str(ccxx.queryv1("FIT_MAX_DE00") or lang.getstr("unknown"))
                    if is_ccmx
                    else lang.getstr("not_applicable")
                ),
                "created": _web_check_created(item),
            }
        )
    return rows


# -- Upload ---------------------------------------------------------------


def validate_upload_originator(cgats_text: str, appname: str) -> bool:
    """Return whether ``cgats_text`` claims an Argyll/``appname`` origin.

    Port of the ``ORIGINATOR`` check in
    ``MainFrame.upload_colorimeter_correction_handler``, which refuses to
    offer upload for files this application didn't (help) create.
    """
    return bool(
        re.search(r'\nORIGINATOR\s+"Argyll', cgats_text)
        or re.search(r'\nORIGINATOR\s+"' + re.escape(appname), cgats_text)
    )


def compute_upload_dedup_hash(cgats: bytes) -> str:
    """Return the MD5 hash used to detect an already-uploaded correction.

    Port of the hash in ``upload_colorimeter_correction`` (module-level,
    ``display_cal.py``): the ``CREATED`` date is stripped first so re-runs of
    the same correction hash identically regardless of when it was made.
    """
    return md5(  # noqa: S324
        re.sub(rb'\nCREATED\s+".+?"\n', rb"\n\n", cgats).strip()
    ).hexdigest()


def build_upload_params(cgats: bytes | str) -> dict:
    """Build the upload params for a CCMX/CCSS correction, with provenance.

    Toolkit-neutral port of the param-building in
    ``MainFrame.upload_colorimeter_correction`` (the confirm dialog and the
    actual HTTP round-trip stay with the caller): strips the platform-specific
    ``REFERENCE``/``TARGET_FILENAME`` fields, then adds the referenced
    reference/target CGATS measurement files verbatim if they still exist on
    disk and match the hash recorded in the correction file.

    Fixes a latent crash in the wx handler: ``upload_colorimeter_correction_
    handler`` reads the file as ``str`` (``.decode()``) and passes it straight
    through, but the byte-stripping regex below uses a ``bytes`` pattern,
    which raises ``TypeError`` against a ``str`` subject. Only the create-
    correction call site (which already holds ``bytes``) avoided it. This
    port normalises to ``bytes`` upfront so both call shapes work.

    Args:
        cgats: The raw correction file bytes or text (not re-parsed CGATS,
            whose keyword order may differ and change the MD5 the server
            sees).

    Returns:
        dict: ``{"cgats": <bytes>}`` plus optional ``reference_cgats`` /
            ``target_cgats`` entries.
    """
    if isinstance(cgats, str):
        cgats = cgats.encode("utf-8")
    ccxx = CGATS(cgats)
    cgats = re.sub(rb'\n(?:REFERENCE|TARGET)_FILENAME\s+"[^"]+"\n', b"\n", cgats)
    params = {"cgats": cgats}
    for label in ("REFERENCE", "TARGET"):
        filename = (ccxx.queryv1(f"{label}_FILENAME") or b"").decode("utf-8")
        algo_hash = ((ccxx.queryv1(f"{label}_HASH") or b"").decode("utf-8")).split(
            ":", 1
        )
        algo = _HASH_ALGORITHMS.get(algo_hash[0])
        if filename and algo and os.path.isfile(filename):
            meas = bytes(CGATS(filename)).strip()
            if algo(meas).hexdigest() == algo_hash[-1]:
                params[label.lower() + "_cgats"] = meas
    return params


# -- Import -----------------------------------------------------------------


def get_argyll_data_files(
    worker: Worker,
    scope: str,
    wildcard: str,
    include_lastmod: bool = False,
) -> list[str | tuple[str, float]]:
    """Get paths of Argyll data files.

    Toolkit-neutral port of ``MainFrame.get_argyll_data_files`` (``self`` ->
    ``worker``, the only instance state it reads).

    Args:
        worker: The running :class:`DisplayCAL.worker.Worker` (only its
            ``argyll_version`` is consulted, for a macOS Argyll 1.9.x quirk).
        scope: A string containing "l" for local system and/or "u" for user.
        wildcard: A wildcard pattern to match files.
        include_lastmod: If True, include the last modification time of the
            files.

    Returns:
        list[str | tuple[str, float]]: A list of file paths, or (path,
            last-modified) tuples if ``include_lastmod``.
    """
    data_files = []
    if sys.platform != "darwin":
        if "l" in scope:
            for commonappdata in config.COMMONAPPDATA:
                data_files += safe_glob(os.path.join(commonappdata, "color", wildcard))
                data_files += safe_glob(
                    os.path.join(commonappdata, "ArgyllCMS", wildcard)
                )
        if "u" in scope:
            data_files += safe_glob(os.path.join(config.APPDATA, "color", wildcard))
    else:
        if "l" in scope:
            data_files += safe_glob(os.path.join(config.LIBRARY, "color", wildcard))
            data_files += safe_glob(os.path.join(config.LIBRARY, "ArgyllCMS", wildcard))
            if [1, 9] <= worker.argyll_version <= [1, 9, 1]:
                # Argyll CMS 1.9 and 1.9.1 use *nix locations due to a
                # configuration problem
                data_files += safe_glob(
                    os.path.join("/usr/local/share", "ArgyllCMS", wildcard)
                )
        if "u" in scope:
            data_files += safe_glob(
                os.path.join(config.LIBRARY_HOME, "color", wildcard)
            )
            if [1, 9] <= worker.argyll_version <= [1, 9, 1]:
                # Argyll CMS 1.9 and 1.9.1 use *nix locations due to a
                # configuration problem
                data_files += safe_glob(
                    os.path.join(config.HOME, ".local", "share", "ArgyllCMS", wildcard)
                )
    if "u" in scope:
        data_files += safe_glob(os.path.join(config.APPDATA, "ArgyllCMS", wildcard))

    # Prefer files with the same basename in the "ArgyllCMS" folder over the
    # "color" folder.
    mapping: dict[str, str] = {}
    for filename in data_files:
        basename = os.path.basename(filename)
        if (
            basename not in mapping
            or os.path.basename(os.path.dirname(filename)) == "ArgyllCMS"
        ):
            mapping[basename] = filename

    if include_lastmod:
        result = []
        for filename in mapping.values():
            try:
                lastmod = os.stat(filename).st_mtime
            except OSError:
                lastmod = -1
            result.append((filename, lastmod))
        return result
    return list(mapping.values())


def discover_auto_import_paths(
    importers: dict,
    i1d3: bool,
    i1d3ccss: bool,
    spyd4: bool,
    spyd4en: bool,
    oeminst: str,
) -> dict[str, list[str]]:
    """Locate on-disk OEM installer files for the "auto" import mode.

    Toolkit-neutral port of the file-discovery half of
    ``MainFrame.import_colorimeter_corrections_producer`` (the trailing
    web-download fallback, which needs ``worker.download``, stays with the
    caller). Pure ``os``/``sys.platform`` globbing, no worker/wx dependency.

    Args:
        importers: Which importers the user selected, as returned by the
            import dialog (keys among ``"icd"``, ``"i1d3"``, ``"spyd4"``).
        i1d3: Whether an i1D3 correction was already imported this run
            (skips the i1D3 lookup).
        i1d3ccss: Whether the ``i1d3ccss`` Argyll utility is available.
        spyd4: Whether a Spyder4/5 correction was already imported this run
            (skips the Spyder4/5 lookup).
        spyd4en: Whether the ``spyd4en`` Argyll utility is available.
        oeminst: Path to the ``oeminst`` Argyll utility, or falsy.

    Returns:
        dict[str, list[str]]: ``{"icd": [...], "i1d3": [...], "spyd4": [...]}``
            for each requested, not-yet-imported importer (only keys with at
            least one discovered path are present).
    """
    found: dict[str, list[str]] = {}
    if importers.get("icd"):
        if sys.platform == "win32":
            icdfn = safe_glob(
                os.path.join(
                    getenvu("PROGRAMFILES", ""),
                    "Quato",
                    "iColorDisplay",
                    "DeviceCorrections.txt",
                )
            )
        elif sys.platform == "darwin":
            icdfn = safe_glob(
                os.path.join(
                    os.path.sep,
                    "Applications",
                    "iColorDisplay*.app",
                    "DeviceCorrections.txt",
                )
            )
            if not icdfn:
                icdfn = safe_glob(
                    os.path.join(
                        os.path.sep,
                        "Volumes",
                        "iColorDisplay*",
                        "iColorDisplay*.app",
                        "DeviceCorrections.txt",
                    )
                )
        else:
            icdfn = []
        if icdfn:
            found["icd"] = icdfn
    if importers.get("i1d3") and (oeminst or i1d3ccss) and not i1d3:
        if sys.platform == "win32":
            i1d3fn = safe_glob(
                os.path.join(
                    getenvu("PROGRAMFILES", ""),
                    "X-Rite",
                    "Devices",
                    "i1d3",
                    "Calibrations",
                    "*.edr",
                )
            )
        elif sys.platform == "darwin":
            i1d3fn = safe_glob(
                os.path.join(
                    os.path.sep,
                    "Library",
                    "Application Support",
                    "X-Rite",
                    "Devices",
                    "i1d3xrdevice",
                    "Contents",
                    "Resources",
                    "Calibrations",
                    "*.edr",
                )
            )
            if not i1d3fn:
                i1d3fn = safe_glob(
                    os.path.join(os.path.sep, "Volumes", "i1Profiler", "*Setup.exe")
                )
            if not i1d3fn:
                i1d3fn = safe_glob(
                    os.path.join(
                        os.path.sep, "Volumes", "ColorMunki Display", "*Setup.exe"
                    )
                )
        else:
            i1d3fn = []
        if i1d3fn:
            found["i1d3"] = i1d3fn
    if importers.get("spyd4") and (oeminst or spyd4en) and not spyd4:
        if sys.platform == "win32":
            spydfn = safe_glob(
                os.path.join(
                    getenvu("PROGRAMFILES", ""), "Datacolor", "Spyder5*", "dccmtr.dll"
                )
            )
            if not spydfn:
                spydfn = safe_glob(
                    os.path.join(
                        getenvu("PROGRAMFILES", ""),
                        "Datacolor",
                        "Spyder4*",
                        "dccmtr.dll",
                    )
                )
        elif sys.platform == "darwin":
            spydfn = safe_glob(
                os.path.join(os.path.sep, "Volumes", "Datacolor", "Data", "Setup.exe")
            )
            if not spydfn:
                spydfn = safe_glob(
                    os.path.join(
                        os.path.sep, "Volumes", "Datacolor_ISO", "Data", "Setup.exe"
                    )
                )
        else:
            spydfn = []
        if spydfn:
            found["spyd4"] = spydfn
    return found


def detect_import_kind(
    worker: Worker,
    result: bool | Exception,
    i1d3: bool,
    i1d3ccss: bool,
    spyd4: bool,
    spyd4en: bool,
    icd: bool,
    oeminst: str,
    path: str | list,
    asroot: bool,
) -> tuple[bool | Exception, bool, bool, bool]:
    """Import colorimeter correction(s) from ``path``.

    Toolkit-neutral port of ``MainFrame.import_colorimeter_correction``
    (``self`` -> ``worker``, ``self.get_argyll_data_files`` ->
    :func:`get_argyll_data_files`): detects what kind of OEM export ``path``
    is (iColor Display's ``DeviceCorrections.txt``, possibly packaged in a
    ``.dmg``/``.cab``/``.exe``; an X-Rite ``.edr``; a Spyder4/5 install; or an
    Argyll ``oeminst``-supported package) and runs the matching
    ``worker.Worker`` import method.

    Args:
        worker: The running :class:`DisplayCAL.worker.Worker`.
        result: Result of the import operation so far.
        i1d3: Whether i1D3 corrections were imported.
        i1d3ccss: Whether the ``i1d3ccss`` Argyll utility is available.
        spyd4: Whether Spyder4/5 corrections were imported.
        spyd4en: Whether the ``spyd4en`` Argyll utility is available.
        icd: Whether iColor Display corrections were imported.
        oeminst: Path to the ``oeminst`` Argyll utility, or falsy.
        path: Path(s) to the correction file(s)/installer to import from.
        asroot: Whether to install as root (system-wide).

    Returns:
        tuple: ``(result, i1d3, spyd4, icd)``, each possibly updated.
    """
    kind = None
    icolordisplay = False
    if isinstance(path, list):
        kind = "xrite"
    elif path and os.path.exists(path):
        ext = os.path.splitext(path)[1]
        kind = "unknown"
        if ext.lower() == ".txt":
            kind = "icd"
            result = True
        else:
            icolordisplay = "icolordisplay" in os.path.basename(path).lower()
            if ext.lower() == ".dmg":
                if icolordisplay:
                    kind = "icd"
                    result = worker.exec_cmd(
                        which("hdiutil"),
                        ["attach", path],
                        capture_output=True,
                        skip_scripts=True,
                    )
                    if result and not isinstance(result, Exception):
                        for _path in safe_glob(
                            os.path.join(
                                os.path.sep,
                                "Volumes",
                                "iColorDisplay*",
                                "iColorDisplay*.app",
                                "Contents",
                                "Resources",
                                "DeviceCorrections.txt",
                            )
                        ):
                            break
                        else:
                            result = Error(
                                lang.getstr("file.missing", "DeviceCorrections.txt")
                            )
            elif i1d3ccss and ext.lower() == ".edr":
                kind = "xrite"
            elif ext.lower() in (".cab", ".exe"):
                if icolordisplay:
                    kind = "icd"
                    sevenzip = get_program_file("7z", "7-zip")
                    if sevenzip:
                        if not config.getcfg("dry_run"):
                            # Extract from NSIS installer
                            temp = worker.create_tempdir()
                            if isinstance(temp, Exception):
                                result = temp
                            else:
                                result = worker.exec_cmd(
                                    sevenzip,
                                    ["e", "-y", path, "DeviceCorrections.txt"],
                                    capture_output=True,
                                    skip_scripts=True,
                                    working_dir=temp,
                                )
                                if result and not isinstance(result, Exception):
                                    path = os.path.join(temp, "DeviceCorrections.txt")
                                else:
                                    worker.wrapup(False)
                    else:
                        result = Error(lang.getstr("file.missing", "7z" + EXE_EXT))
                elif i1d3ccss and (
                    "colormunki" in os.path.basename(path).lower()
                    or "i1profiler" in os.path.basename(path).lower()
                    or os.path.basename(path).lower() == "i1d3"
                ):
                    # Assume X-Rite installer
                    kind = "xrite"
                elif spyd4en and (
                    "spyder4" in os.path.basename(path).lower()
                    or os.path.basename(path).lower() == "spyd4"
                ):
                    # Assume Spyder4/5
                    kind = "spyder4"
    if kind:
        if kind == "icd":
            if not config.getcfg("dry_run") and result and not isinstance(
                result, Exception
            ):
                # Assume iColorDisplay DeviceCorrections.txt
                ccmx_dir = config.get_argyll_data_dir()
                if not os.path.exists(ccmx_dir):
                    from DisplayCAL.worker import check_create_dir

                    result = check_create_dir(ccmx_dir)
                    if isinstance(result, Exception):
                        return result, i1d3, spyd4, icd
                print(lang.getstr("colorimeter_correction.import"))
                print(path)
                try:
                    imported, skipped = ccmx.convert_devicecorrections_to_ccmx(
                        path, ccmx_dir
                    )
                    if imported == 0:
                        raise Info
                except ValueError as exception:
                    result = Error(lang.getstr("file.invalid") + "\n" + str(exception))
                except Info:
                    result = False
                except Exception as exception:  # noqa: BLE001
                    result = exception
                else:
                    result = icd = True
                    if skipped > 0:
                        result = Warn(
                            lang.getstr(
                                "colorimeter_correction.import.partial_warning",
                                ("iColor Display", skipped, imported + skipped),
                            )
                        )
                worker.wrapup(False)
        elif kind == "xrite":
            # Import .edr
            if asroot and sys.platform == "win32":
                ccss = get_argyll_data_files(worker, "l", "*.ccss", True)
            args = path if isinstance(path, list) else [path]
            result = i1d3 = worker.import_edr(args, asroot=asroot)
            if asroot and sys.platform == "win32":
                # Hacky but the only way to know if we were successful
                result = i1d3 = (
                    get_argyll_data_files(worker, "l", "*.ccss", True) != ccss
                )
        elif kind == "spyder4":
            # Import spyd4cal.bin
            result = spyd4 = worker.import_spyd4cal([path], asroot=asroot)
            if asroot and sys.platform == "win32":
                result = spyd4 = get_argyll_data_files(worker, "l", "spyd4cal.bin")
        elif oeminst and not icolordisplay:
            if asroot and sys.platform == "win32":
                ccss = get_argyll_data_files(worker, "l", "*.ccss", True)
            result = worker.import_colorimeter_corrections(oeminst, [path], asroot)
            if ".ccss" in "".join(worker.output) or (
                asroot
                and sys.platform == "win32"
                and get_argyll_data_files(worker, "l", "*.ccss", True) != ccss
            ):
                i1d3 = result
            if "spyd4cal.bin" in "".join(worker.output) or (
                asroot
                and sys.platform == "win32"
                and get_argyll_data_files(worker, "l", "spyd4cal.bin")
            ):
                spyd4 = result
        else:
            result = Error(lang.getstr("error.file_type_unsupported") + "\n" + path)
    return result, i1d3, spyd4, icd
