"""Toolkit-neutral helpers for the measurement report feature.

These are the pure pieces lifted out of ``MainFrame.measurement_report_handler``
and ``MainFrame.measurement_report_consumer`` (``display_cal.py``): string /
number marshalling that carries no wx (or Qt) dependency, so both the shipping
wx path and the future Qt window can call into them (a plain ``DisplayCAL``
module so importing it never pulls in Qt, matching ``main_settings.py``). The wx
frame delegates to these; the Qt main window reuses them as its report layer is
built.

The genuinely window-shaped parts (file-save dialog, overwrite confirm, the
``worker.Worker`` measurement run, and the big ``placeholders2data`` assembly
that reads live CGATS / ICCProfile objects) stay in their respective UI layers.
"""

from __future__ import annotations

import re
from time import strftime

from DisplayCAL.worker import get_arg

# Characters Argyll / the filesystem cannot carry in a report filename, matching
# the sanitisation the wx handler applies to the display name.
_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:;*?"<>|]+')


def default_report_filename(
    report_type: str,
    version_string: str,
    display_name: str,
    timestamp: str | None = None,
) -> str:
    """Build the default ``.html`` filename offered in the save dialog.

    Ports the ``default_file`` construction in ``measurement_report_handler``.

    Args:
        report_type: ``"Measurement"`` or ``"Self Check"``.
        version_string: The application version string (``VERSION_STRING``).
        display_name: The display name, already stripped of the localized
            ``display.primary`` suffix by the caller.
        timestamp: ``"%Y-%m-%d %H-%M"`` timestamp; defaults to now.

    Returns:
        The suggested filename, including the ``.html`` extension.
    """
    if timestamp is None:
        timestamp = strftime("%Y-%m-%d %H-%M")
    safe_display = _UNSAFE_FILENAME_CHARS.sub("_", display_name)
    return f"{report_type} Report {version_string} - {safe_display} - {timestamp}.html"


def resolve_quantization_bits(args: list) -> int | None:
    """Determine the reference-value quantization bit depth from dispread args.

    Ports the ``qbits`` derivation in ``measurement_report_consumer``: an
    explicit ``-Z <bits>`` (or ``-Zbits``) wins, otherwise video encoding
    (``-E``) implies ArgyllCMS' 8-bit default.

    Args:
        args: The dispread argument list (after
            ``worker.add_measurement_features``).

    Returns:
        The bit depth, or ``None`` if no quantization applies.
    """
    quantize_arg = get_arg("-Z", args)
    if quantize_arg:
        try:
            if quantize_arg[1] == "-Z":
                # Next arg is quantization bit depth
                return int(args[quantize_arg[0] + 1])
            # Quantization bit depth is part of arg string
            return int(quantize_arg[1][2:])
        except (IndexError, TypeError, ValueError):
            return None
    elif "-E" in args:
        return 8  # ArgyllCMS default for video encoding (see dispread doc)
    return None


def quantize_gray(gray: list, qbits: int) -> list:
    """Quantize grayscale RGB reference values to ``qbits`` bits.

    Ports the ``gray`` rescaling in ``measurement_report_consumer``.

    Args:
        gray: A list of ``[R, G, B]`` triples in 0-100.
        qbits: The quantization bit depth.

    Returns:
        A new list of quantized ``[R, G, B]`` triples.
    """
    qmax = 2**qbits - 1.0
    return [
        [round(round(v / 100.0 * qmax) / qmax * 100.0, 4) for v in rgb] for rgb in gray
    ]


def report_trc_label(
    trc_gamma: float, trc_gamma_type: str, trc_output_offset: float
) -> str:
    """Return the report's TRC label for the given TRC config values.

    Ports the ``trc`` derivation in ``measurement_report_consumer``: the default
    BT.1886 target (gamma 2.4, type ``B``, no output offset) is labelled
    ``"BT.1886"``, anything else is unlabelled.

    Args:
        trc_gamma: ``measurement_report.trc_gamma``.
        trc_gamma_type: ``measurement_report.trc_gamma_type``.
        trc_output_offset: ``measurement_report.trc_output_offset``.

    Returns:
        ``"BT.1886"`` for the default target, otherwise ``""``.
    """
    if trc_gamma != 2.4 or trc_gamma_type != "B" or trc_output_offset:
        return ""
    return "BT.1886"
