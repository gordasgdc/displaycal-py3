from pathlib import Path


def generate_version_file(pydir: Path) -> None:
    """Generate VERSION file from DisplayCAL/VERSION if it exists.

    otherwise use "0.0.0" as version.
    """
    version_base_file_path = Path(pydir, "DisplayCAL", "VERSION")
    version_base = "0.0.0"

    if version_base_file_path.is_file():
        with open(version_base_file_path) as version_base_file:
            version_base = version_base_file.read().strip()

    with open(Path(pydir, "VERSION"), "w") as versiontxt:
        versiontxt.write(version_base)
