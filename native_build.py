#!/usr/bin/env python3
"""Thin CLI entry point; the actual packaging/freeze logic lives in `_native_build/`.

Kept as a standalone script at the repo root (rather than folded into the
`_native_build` package) so `python native_build.py ...`/`./native_build.py
...` (used by CI, `Makefile`, and docs) and root `setup.py`'s
`import native_build` keep working unchanged.
"""

import sys
from pathlib import Path

pypath = Path(__file__).resolve()
pydir = pypath.parent

sys.path.insert(0, "DisplayCAL")
sys.path.insert(1, str(pydir))

from _native_build.cli import setup  # noqa: E402
from _native_build.templates import replace_placeholders  # noqa: E402, F401


if __name__ == "__main__":
    setup()
