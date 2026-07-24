import os
import sys
from distutils.util import get_platform
from pathlib import Path
from time import strftime

from _native_build import meta


def generate(pydir: Path, bdist_cmd: str, arch: str, dry_run: bool) -> None:
    """Generate the Inno Setup `.iss` script for the current build."""
    for tmpl_type in [bdist_cmd]:
        inno_template_path = Path(pydir, "misc", f"{meta.NAME}-Setup-{tmpl_type}.iss")
        with open(inno_template_path, "r") as inno_template:
            print(f"inno_template_path: {inno_template_path}")
            template = inno_template.read()
            # print(template)
            inno_arch_raw = arch or get_platform().split("-")[1]
            inno_arch = "x64" if inno_arch_raw == "amd64" else inno_arch_raw
            inno_script = template % {
                "AppCopyright": f"© {strftime('%Y')} {meta.AUTHOR}",
                "AppName": meta.NAME,
                "AppArch": inno_arch_raw,
                "InnoArch": inno_arch,
                "AppVerName": meta.VERSION_STRING,
                "AppPublisher": meta.AUTHOR,
                "AppPublisherURL": f"https://{meta.DOMAIN}/",
                "AppSupportURL": f"https://{meta.DOMAIN}/",
                "AppUpdatesURL": f"https://{meta.DOMAIN}/",
                "VersionInfoVersion": ".".join(map(str, meta.VERSION_TUPLE)),
                "VersionInfoTextVersion": meta.VERSION_STRING,
                "AppVersion": meta.VERSION_STRING,
                "Platform": get_platform(),
                "PythonVersion": f"{sys.version_info[0]}.{sys.version_info[1]}",
                "URL": f"https://{meta.DOMAIN}/",
                "HTTPURL": f"http://{meta.DOMAIN}/",
            }
        inno_path = Path(
            "dist",
            inno_template_path.name.replace(
                bdist_cmd,
                f"{bdist_cmd}.{get_platform()}-py{sys.version_info[0]}.{sys.version_info[1]}",
            ),
        )
        print(f"inno_path: {inno_path}")

        if not dry_run:
            dist_path = Path("dist")

            if not dist_path.exists():
                os.makedirs(dist_path)

            with open(inno_path, "wb") as inno_file:
                inno_file.write(inno_script.encode("MBCS", "replace"))
