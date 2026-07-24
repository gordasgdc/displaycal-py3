#!/usr/bin/env python3
"""Thin PEP 517 entry point.

setuptools' `build_meta` backend execs whatever file is literally named
`setup.py` on every build hook call, so this file has to exist and has to
route to the real, distutils-based `DisplayCAL._setup.setup()`: that is
where `data_files` (desktop entries, icons, man pages, the appdata.xml
and copyright templates, ...) is actually assembled, pyproject.toml has
no declarative equivalent for it.

Unlike the old `setup.py` (now `native_build.py`), this file does not
sniff `sys.argv` for native-packaging/freeze commands (`py2app`,
`py2exe`, `bdist_deb`, `inno`, `0install`, ...), those are only reachable
by invoking `native_build.py` directly. Its only other job is making
sure the couple of `dist/` files that `DisplayCAL/_setup.py`'s
`data_files` unconditionally references (`dist/copyright` and the
appdata.xml) exist before the real build runs.

`native_build.py`'s `buildservice` flag also generates the copyright
file, but as a side effect of a much bigger "create RPM/DEB/PKGBUILD
control files" block that needs template files not worth requiring
here, so the copyright file is generated directly instead, reusing
`native_build.py`'s own `replace_placeholders()`. Only the `appdata`
flag (safe on its own, no extra template requirements) is reused for
the appdata.xml.
"""

import sys
import time
from pathlib import Path

pydir = Path(__file__).resolve().parent

sys.path.insert(0, str(pydir / "DisplayCAL"))
sys.path.insert(1, str(pydir))


def setup() -> None:
    """Ensure the dist/ template files exist, then run the real build."""
    import native_build

    argv = sys.argv
    try:
        sys.argv = [argv[0], "appdata"]
        native_build.setup()
    finally:
        sys.argv = argv

    # native_build.setup() just populated NAME/DOMAIN/AUTHOR/... as module
    # globals (used by replace_placeholders()'s template mapping), so this
    # has to run after it, not before.
    native_build.replace_placeholders(
        pydir / "misc" / "debian.copyright",
        pydir / "dist" / "copyright",
        int(time.time()),
    )

    from DisplayCAL._setup import setup as real_setup

    real_setup()


if __name__ == "__main__":
    setup()
