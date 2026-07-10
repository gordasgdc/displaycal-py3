"""Toolkit-neutral instrument-setup / donation-nag detection — Qt port support.

Ports the detection half of ``display_cal.MainFrame.check_instrument_setup``
and the config-mutating gate of ``display_cal.check_donation`` (both in
``display_cal.py``): given a ``Worker``'s enumerated instrument list and the
set of instruments already covered by a colorimeter correction, decide
whether an import prompt is needed and whether to show the donation message.
The actual prompts (colorimeter-correction import dialog, donation dialog)
are toolkit-specific and live with their caller.

Deliberately not reproduced here (documented at the one call site that needs
it, ``ui/main_window.py``): the Spyder2 "enable" wizard
(``MainFrame.enable_spyder2_handler``), which downloads/patches OEM firmware
through the discontinued ``spyd2en`` Argyll utility for a colorimeter that has
been out of production since 2009 — judged not worth a first Qt port given how
small its remaining install base is. ``needs_spyder2_enable`` is still
detected (so the caller can show a one-line not-yet-available notice rather
than silently doing nothing), but no wizard is built.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from DisplayCAL.config import getcfg, setcfg
from DisplayCAL.meta import VERSION_STRING, VERSION_TUPLE
from DisplayCAL.util_list import intlist
from DisplayCAL.worker import Worker


@dataclass
class InstrumentSetupNeeds:
    """What :func:`resolve_instrument_setup_needs` found is needed, if anything."""

    needs_spyder2_enable: bool
    needs_correction_import: bool


def resolve_instrument_setup_needs(
    worker: Worker, ccmx_instruments: Iterable[str]
) -> InstrumentSetupNeeds:
    """Port of the detection half of ``MainFrame.check_instrument_setup``.

    Args:
        worker: A ``Worker`` with populated ``instruments``.
        ccmx_instruments: Instrument names already covered by a discovered
            colorimeter correction (``ColorimeterCorrectionCatalog.instruments
            .values()`` on the Qt side, ``MainFrame.ccmx_instruments.values()``
            on the wx side).
    """
    ccmx_instruments = list(ccmx_instruments)
    if getcfg("colorimeter_correction_matrix_file") in ("AUTO:", ""):
        i1d3 = (
            "i1 DisplayPro, ColorMunki Display" in worker.instruments
            and "" not in ccmx_instruments
        )
        icd = (
            ("DTP94" in worker.instruments and "DTP94" not in ccmx_instruments)
            or (
                "i1 Display 2" in worker.instruments
                and "i1 Display 2" not in ccmx_instruments
            )
            or (
                "Spyder2" in worker.instruments
                and "Spyder2" not in ccmx_instruments
            )
            or (
                "Spyder3" in worker.instruments
                and "Spyder3" not in ccmx_instruments
            )
        )
    else:
        i1d3 = False
        icd = False
    spyd2 = "Spyder2" in worker.instruments and not worker.spyder2_firmware_exists()
    spyd4 = (
        "Spyder4" in worker.instruments or "Spyder5" in worker.instruments
    ) and not worker.spyder4_cal_exists()
    return InstrumentSetupNeeds(
        needs_spyder2_enable=spyd2,
        needs_correction_import=not spyd2 and (i1d3 or icd or spyd4),
    )


def should_show_donation_message() -> bool:
    """Port of ``check_donation``'s config-mutating gate, minus showing the dialog.

    Resets ``show_donation_message`` after a major-version update (same
    ``getcfg("last_launch", "0.0.0")`` fallback as the wx original; the
    snapshot-build skip is dropped since it's never reached from the Qt
    startup path, matching :mod:`DisplayCAL.update_check`'s scope note).
    """
    if VERSION_TUPLE[0] > intlist(getcfg("last_launch", "0.0.0").split("."))[0]:
        setcfg("show_donation_message", 1)
        setcfg("last_launch", VERSION_STRING)
    return bool(getcfg("show_donation_message"))
