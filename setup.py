#!/usr/bin/env python3
"""Thin PEP 517 entry point.

setuptools' `build_meta` backend execs whatever file is literally named
`setup.py` on every build hook call, so this file has to exist and has to
route to the real, distutils-based `DisplayCAL.setup.setup()`: that is
where `data_files` (desktop entries, icons, man pages, the appdata.xml
and copyright templates, ...) is actually assembled, pyproject.toml has
no declarative equivalent for it.

Unlike the old `setup.py` (now `native_build.py`), this file does not
sniff `sys.argv` for native-packaging/freeze commands (`py2app`,
`py2exe`, `bdist_deb`, `inno`, `0install`, ...), those are only reachable
by invoking `native_build.py` directly. Its only other job is making
sure the couple of `dist/` files that `DisplayCAL/setup.py`'s
`data_files` unconditionally references (`dist/copyright` and the
appdata.xml) exist before the real build runs, by delegating to
`native_build.py`'s existing `appdata`/`buildservice` template
generation instead of duplicating it.
"""

import sys
from pathlib import Path

pydir = Path(__file__).resolve().parent

sys.path.insert(0, str(pydir / "DisplayCAL"))
sys.path.insert(1, str(pydir))


def setup() -> None:
    """Ensure the dist/ template files exist, then run the real build."""
    import native_build

    argv = sys.argv
    try:
        sys.argv = [argv[0], "appdata", "buildservice"]
        native_build.setup()
    finally:
        sys.argv = argv

    from DisplayCAL.setup import setup as real_setup

    real_setup()


if __name__ == "__main__":
    setup()
