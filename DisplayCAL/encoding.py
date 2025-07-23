"""Utility functions for retrieving system and filesystem encodings."""

from __future__ import annotations

import sys
from typing import BinaryIO, TextIO


def get_encoding(stream: BinaryIO | TextIO) -> str:
    """Return stream encoding.

    Args:
        stream (BinaryIO | TextIO): A binary or text stream (e.g., sys.stdout,
            sys.stdin).

    Returns:
        str: The encoding of the stream, typically "utf-8" for Python 3.6 and
            later.
    """
    return sys.getdefaultencoding()  # which is "utf-8" for all OSes after Python 3.6


def get_encodings() -> tuple[str, str]:
    """Return console encoding, filesystem encoding.

    Returns:
        tuple[str, str]: A tuple containing the console encoding and the
            filesystem encoding. Both are typically "utf-8" for Python 3.6 and
            later.
    """
    enc = get_encoding(sys.stdout)  # this is "utf-8" for all OSes
    fs_enc = sys.getfilesystemencoding() or enc  # this is "utf-8" for all OSes
    return enc, fs_enc
