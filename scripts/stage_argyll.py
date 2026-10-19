#!/usr/bin/env python3
"""Stage the pinned ArgyllCMS for an installer build.

Downloads the official archive (https://www.argyllcms.com/, falling back to the
``argyllcms-binaries`` mirror), verifies its SHA-256 against the table pinned in
``DisplayCAL/argyll_integrity.py`` and extracts the parts the application needs
into ``<out>/ArgyllCMS``. Refuses to stage anything that does not verify.

Usage: stage_argyll.py <mac-arm64|mac-x86_64|win64|win-arm64> <cache_dir> <out_dir>

ArgyllCMS is AGPL-3.0; ``License.txt`` and ``ReadMe.txt`` are kept inside the
staged tree, and the corresponding source is available from the same site.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from DisplayCAL.argyll_integrity import PINNED_SHA256  # noqa: E402

VERSION = "3.5.0"
SUFFIX = {
    "mac-arm64": "_macOS11_arm64_bin.tgz",
    "mac-x86_64": "_osx10.6_x86_64_bin.tgz",
    "win64": "_win64_exe.zip",
    "win-arm64": "_win_arm64_exe.zip",
}
SOURCES = (
    "https://www.argyllcms.com/{name}",
    "https://github.com/eoyilmaz/argyllcms-binaries/releases/download/{version}/{name}",
)
KEEP = ("bin", "ref", "License.txt", "ReadMe.txt", "log.txt")


def sha256(path: Path) -> str:
    """Return the SHA-256 of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str, dest: Path) -> None:
    """Download ``name`` to ``dest`` from the first source that verifies."""
    expected = PINNED_SHA256[VERSION][name]
    for template in SOURCES:
        url = template.format(name=name, version=VERSION)
        try:
            print(f"downloading {url}")
            with urllib.request.urlopen(url, timeout=120) as r, dest.open("wb") as f:  # noqa: S310
                shutil.copyfileobj(r, f)
        except OSError as exc:
            print(f"  failed: {exc}")
            continue
        if sha256(dest) == expected:
            print(f"  verified sha256 {expected}")
            return
        print("  HASH MISMATCH - discarding")
        dest.unlink(missing_ok=True)
    raise SystemExit(f"cannot obtain a verified {name}")


def main(argv: list[str]) -> int:
    """Stage Argyll for a platform."""
    if len(argv) != 4 or argv[1] not in SUFFIX:
        print(__doc__)
        return 2
    plat, cache, out = argv[1], Path(argv[2]), Path(argv[3])
    name = f"Argyll_V{VERSION}{SUFFIX[plat]}"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / name
    if not archive.exists() or sha256(archive) != PINNED_SHA256[VERSION][name]:
        archive.unlink(missing_ok=True)
        fetch(name, archive)
    work = cache / f"extract-{plat}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(work)
    else:
        with tarfile.open(archive) as t:
            t.extractall(work, filter="data")
    roots = [p for p in work.iterdir() if p.is_dir()]
    root = roots[0] if len(roots) == 1 else work
    target = out / "ArgyllCMS"
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    for item in KEEP:
        src = root / item
        if src.is_dir():
            shutil.copytree(src, target / item, symlinks=True)
        elif src.exists():
            shutil.copy2(src, target / item)
    if not (target / "bin").is_dir() or not (target / "License.txt").exists():
        raise SystemExit("staged tree is incomplete")
    print(f"staged {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
