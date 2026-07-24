#!/usr/bin/env python3

import glob
import os
import re
import shutil
import sys
import time
from distutils.util import get_platform
from hashlib import sha1
from pathlib import Path
from textwrap import fill
from time import gmtime, strftime

pypath = Path(__file__).resolve()
pydir = pypath.parent

sys.path.insert(0, "DisplayCAL")
sys.path.insert(1, str(pydir))


def generate_version_file() -> None:
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


def format_changelog(changelog, fmt="appstream"):
    if fmt.lower() == "appstream":
        from xml.etree import ElementTree as ET

        # Remove changelog entries of prev versions
        changelog = re.sub(r'(?s:\s*<p id="changelog-.*$)', "", changelog)
        # AppStream: Do not assume the format is HTML. Only paragraph (p),
        # ordered list (ol) and unordered list (ul) are supported at this time.
        # + list items (li)
        allowed_tags = ["p", "ol", "ul", "li"]

        changelog = re.sub(r"\s*<dt(?:\s+[^>]*)?>.+?</dt>\n?", "", changelog)
        changelog = re.sub(r"<(h4|p)(?:\s+[^>]*)?>(.+?)</\1>", r"<p>\2</p>", changelog)
        # Remove everything between <!--more-->..<!--/more-->
        changelog = re.sub(r"(?s:<!--more-->.+?<!--/more-->)", "", changelog)
        # Remove all except allowed tags
        tags = re.findall(r"<[^/][^>]+>", changelog)

        for tag in tags:
            tagname = tag.strip("<>").split()[0]

            if tagname not in allowed_tags:
                changelog = changelog.replace(tag, "")
                changelog = changelog.replace("</" + tagname + ">", "")

        # Remove macOS and Windows specific items
        changelog = re.sub(
            r"(?is:<li>[^,:<]*(?:Mac ?OS ?X?|Windows)([^,:<]*):.*?</li>)", "", changelog
        )
        # Remove text "Linux" in item before colon (":")
        changelog = re.sub(r"(<li>[^,:<]*)\s+Linux([^,:<]*):", r"\1\2", changelog)

        # Conform to appstream-util validate-strict rules
        def truncate(matches, maxlen):
            return "%s%s%s" % (
                matches.group(1),
                # appstream-util validate counts bytes, not characters
                matches.group(2)
                .encode("UTF-8")[: maxlen - 3]
                .rstrip()
                .decode("UTF-8", "ignore")
                + "...",
                matches.group(3),
            )

        # - <p> maximum is 600 chars
        changelog = re.sub(
            r"(<p>)\s*([^<]{601,}?)\s*(</p>)",
            lambda matches: truncate(matches, 600),
            changelog,
        )
        # - <li> cannot end in '.'
        changelog = re.sub(r"([^.])\.\s*</li>", r"\1</li>", changelog)
        # - <li> maximum is 100 chars
        changelog = re.sub(
            r"(<li>)\s*([^<]{101,}?)\s*(<(?:ol|ul|/li)>)",
            lambda matches: truncate(matches, 100),
            changelog,
        )

        # Nice formatting
        changelog = re.sub(r"(?m:^\s+)", r"\t" * 4, changelog)  # Multi-line
        changelog = re.sub(r"(<li)", r"\t\1", changelog)
        changelog = re.sub(r"\s*\n\s*\n", "\n", changelog)
        # Remove line breaks
        changelog = re.sub(r"\s*\n+\s*", " ", changelog)

        # Parse into ETree
        tree = ET.fromstring(f"<root>{changelog.encode('UTF-8')}</root>")
    else:
        raise ValueError(f"Changelog format not supported: {fmt!r}")

    # Nice formatting
    from xml.sax.saxutils import escape

    changelog = ""
    nump = 0
    maxp = 3

    for lvl1 in tree:
        if lvl1.tag in {"p", "ol", "ul"}:
            text = lvl1.text.strip()

            if lvl1.tag == "p":
                if nump == maxp:
                    continue
                nump += 1

            changelog = f"{changelog}\t\t\t\t<{lvl1.tag}>\n"

            if text:
                changelog = f"{changelog}\t\t\t\t\t{escape(text)}\n"

            for lvl2 in lvl1:
                if lvl2.tag != "li":
                    continue
                changelog = f"{changelog}\t\t\t\t\t<li>\n\t\t\t\t\t\t{escape(lvl2.text.strip())}\n"

                for lvl3 in lvl2:
                    if lvl3.tag in {"p", "ol", "ul"}:
                        text = lvl3.text.strip()

                        if lvl3.tag == "p":
                            if nump == maxp:
                                continue
                            nump += 1

                        changelog = f"{changelog}\t\t\t\t\t\t<{lvl3.tag}>\n"

                        if text:
                            changelog = f"{changelog}\t\t\t\t\t\t\t{escape(text)}\n"

                        for lvl4 in lvl3:
                            if lvl4.tag == "li":
                                changelog = f"{changelog}\t\t\t\t\t\t\t<li>{escape(lvl4.text.strip())}</li>\n"

                        changelog = f"{changelog}\t\t\t\t\t\t</{lvl3.tag}>\n"
                changelog = f"{changelog}\t\t\t\t\t</li>\n"
            changelog = f"{changelog}\t\t\t\t</{lvl1.tag}>\n"
    changelog = changelog.rstrip()

    return changelog


def replace_placeholders(
    tmpl_path: Path, out_path: Path, lastmod_time= 0, iterable=None
):
    global LONG_DESCRIPTION
    import DisplayCAL

    with open(str(tmpl_path), "r", encoding="UTF-8") as tmpl:
        tmpl_data = tmpl.read()

    if Path(tmpl_path).name.startswith("debian"):
        longdesc_backup = LONG_DESCRIPTION
        LONG_DESCRIPTION = "\n".join(
            [" " + (line if line.strip() else ".") for line in LONG_DESCRIPTION.splitlines()]
        )

    appdatadesc = (
        "\n\t\t\t"
        + LONG_DESCRIPTION.replace("\n", "\n\t\t\t").replace(".\n", ".\n\t\t</p>\n\t\t<p>\n")
        + "\n\t\t"
    )
    mapping = {
        # e.g. Tue Jul 06 2010
        "DATE": strftime(
            "%a %b %d %Y", gmtime(lastmod_time or os.stat(tmpl_path).st_mtime)
        ),
        # e.g. Wed Jul 07 15:25:00 UTC 2010
        "DATETIME": strftime(
            "%a %b %d %H:%M:%S UTC %Y",
            gmtime(lastmod_time or os.stat(tmpl_path).st_mtime),
        ),
        "DEBPACKAGE": NAME.lower(),
        # e.g. Wed, 07 Jul 2010 15:25:00 +0100
        "DEBDATETIME": strftime(
            "%a, %d %b %Y %H:%M:%S ",
            gmtime(lastmod_time or os.stat(tmpl_path).st_mtime),
        )
        + "+0000",
        "DOMAIN": DOMAIN.lower(),
        "REVERSEDOMAIN": ".".join(reversed(DOMAIN.split("."))),
        "ISODATE": strftime(
            "%Y-%m-%d", gmtime(lastmod_time or os.stat(tmpl_path).st_mtime)
        ),
        "ISODATETIME": strftime(
            "%Y-%m-%dT%H:%M:%S", gmtime(lastmod_time or os.stat(tmpl_path).st_mtime)
        )
        + "+0000",
        "ISOTIME": strftime(
            "%H:%M", gmtime(lastmod_time or os.stat(tmpl_path).st_mtime)
        ),
        "TIMESTAMP": str(int(lastmod_time)),
        "SUMMARY": DESCRIPTION,
        "LONG_DESCRIPTION": DESCRIPTION,
        "DESC": LONG_DESCRIPTION,
        "APPDATADESC": f'<p>{appdatadesc}</p>\n\t\t<p xml:lang="en">{appdatadesc}</p>',
        "APPNAME": NAME,
        "APPNAME_HTML": NAME_HTML,
        "APPNAME_LOWER": NAME.lower(),
        "APPSTREAM_ID": APPSTREAM_ID,
        "AUTHOR": AUTHOR,
        "AUTHOR_EMAIL": AUTHOR_EMAIL,
        "MAINTAINER": AUTHOR,
        "MAINTAINER_EMAIL": AUTHOR_EMAIL,
        "MAINTAINER_EMAIL_SHA1": sha1(AUTHOR_EMAIL.encode("utf-8")).hexdigest(),
        "PACKAGE": NAME,
        "PY_MAXVERSION": ".".join(str(n) for n in PY_MAXVERSION),
        "PY_MINVERSION": ".".join(str(n) for n in PY_MINVERSION),
        "VERSION": VERSION_STRING,
        "VERSION_SHORT": re.sub(r"(?:\.0){1,2}$", "", VERSION_STRING),
        "URL": f"https://{DOMAIN.lower()}/",
        # For share counts...
        "HTTPURL": f"http://{DOMAIN.lower()}/",
        "WX_MINVERSION": ".".join(str(n) for n in WX_MINVERSION),
        "YEAR": strftime("%Y", gmtime(lastmod_time or os.stat(tmpl_path).st_mtime)),
    }
    mapping.update(iterable or {})

    for key in mapping:
        val = mapping[key]
        tmpl_data = tmpl_data.replace(f"${{{key}}}", val)

    tmpl_data = tmpl_data.replace(
        f"{mapping['YEAR']}-{mapping['YEAR']}", mapping["YEAR"]
    )

    if Path(tmpl_path).name.startswith("debian"):
        LONG_DESCRIPTION = longdesc_backup

    out_path = Path(out_path)

    if out_path.is_file():
        with open(str(out_path), "r", encoding="UTF-8") as out:
            data = out.read()

        if data == tmpl_data:
            return
    elif not out_path.parent.is_dir():
        os.makedirs(out_path.parent)

    with open(str(out_path), "w", encoding="UTF-8") as out:
        out.write(tmpl_data)


def setup():
    bdist_cmd = None

    if sys.platform == "darwin":
        bdist_cmd = "py2app"
    elif sys.platform == "win32":
        bdist_cmd = "py2exe"

    if "bdist_standalone" in sys.argv[1:]:
        i = sys.argv.index("bdist_standalone")
        sys.argv = sys.argv[:i] + sys.argv[i + 1 :]

        if bdist_cmd and bdist_cmd not in sys.argv[1:i]:
            sys.argv.insert(i, bdist_cmd)
    elif "py2app" in sys.argv[1:]:
        bdist_cmd = "py2app"
    elif "py2exe" in sys.argv[1:]:
        bdist_cmd = "py2exe"

    appdata = "appdata" in sys.argv[1:]
    arch = None
    setup_cfg = None
    dry_run = "-n" in sys.argv[1:] or "--dry-run" in sys.argv[1:]
    help = False
    inno = "inno" in sys.argv[1:]
    purge = "purge" in sys.argv[1:]
    purge_dist = "purge_dist" in sys.argv[1:]
    use_setuptools = "--use-setuptools" in sys.argv[1:]
    stability = "testing"

    argv = list(sys.argv[1:])

    for i, arg in enumerate(reversed(argv)):
        n = len(sys.argv) - i - 1
        arg = arg.split("=")

        if len(arg) == 2:
            if arg[0] == "--force-arch":
                arch = arg[1]
            elif arg[0] in ("--cfg", "--stability"):
                if arg[0] == "--cfg":
                    setup_cfg = arg[1]
                else:
                    stability = arg[1]

                sys.argv = sys.argv[:n] + sys.argv[n + 1 :]
        elif arg[0] == "-h" or arg[0].startswith("--help"):
            help = True

    lastmod_time = 0
    non_build_args = list(
        filter(
            lambda x: x in sys.argv[1:],
            [
                "clean",
                "purge",
                "purge_dist",
                "uninstall",
                "-h",
                "--help",
                "--help-commands",
                "--all",
                "--name",
                "--fullname",
                "--author",
                "--author-email",
                "--maintainer",
                "--maintainer-email",
                "--contact",
                "--contact-email",
                "--url",
                "--license",
                "--licence",
                "--description",
                "--long-description",
                "--platforms",
                "--classifiers",
                "--keywords",
                "--provides",
                "--requires",
                "--obsoletes",
                "--quiet",
                "-q",
                "register",
                "--list-classifiers",
                "upload",
                "--use-distutils",
                "--use-setuptools",
                "--verbose",
                "-v",
            ],
        )
    )

    generate_version_file()

    if not sys.argv[1:]:
        return

    global NAME, NAME_HTML, AUTHOR, AUTHOR_EMAIL, DESCRIPTION, LONG_DESCRIPTION
    global DOMAIN, PY_MAXVERSION, PY_MINVERSION
    global VERSION_STRING, VERSION_LIN, VERSION_MAC
    global VERSION_SRC, VERSION_TUPLE, VERSION_WIN
    global WX_MINVERSION, APPSTREAM_ID

    # Do not remove the following seemingly unused variables,
    # I know that it seems silly, but for now we need them
    import DisplayCAL
    from DisplayCAL.meta import (
        NAME,
        NAME_HTML,
        AUTHOR,
        AUTHOR_EMAIL,
        DESCRIPTION,
        LONG_DESCRIPTION,
        DOMAIN,
        PY_MAXVERSION,
        PY_MINVERSION,
        VERSION_STRING,
        VERSION_LIN,
        VERSION_MAC,
        VERSION_SRC,
        VERSION_TUPLE,
        VERSION_WIN,
        WX_MINVERSION,
        APPSTREAM_ID,
        get_latest_changelog_entry,
    )

    LONG_DESCRIPTION = fill(LONG_DESCRIPTION)

    if not lastmod_time:
        lastmod_time = int(time.time())

    if purge or purge_dist:
        # remove the "build" and "DisplayCAL.egg-info" directories and their
        # contents recursively

        if dry_run:
            print("dry run - nothing will be removed")

        paths = []

        if purge:
            paths += glob.glob(str(Path(pydir, "build"))) + glob.glob(
                str(Path(pydir, NAME + ".egg-info"))
            )
            sys.argv.remove("purge")

        if purge_dist:
            paths += glob.glob(str(Path(pydir, "dist")))
            sys.argv.remove("purge_dist")

        for path in paths:
            path = Path(path)

            if path.exists():
                if dry_run:
                    print(path)
                    continue

                try:
                    shutil.rmtree(path)
                except Exception as e:
                    print(e)
                else:
                    print(f"Removed: {path}")

        if len(sys.argv) == 1 or (len(sys.argv) == 2 and dry_run):
            return

    if "readme" in sys.argv[1:]:
        if not dry_run:
            for tmpl_name in ["CHANGES", "README", "history"]:
                for suffix in ("", "-fr"):
                    if suffix:
                        if tmpl_name == "README":
                            tmpl_name += suffix
                        else:
                            continue

                    replace_placeholders(
                        Path(pydir, "misc", f"{tmpl_name}.template.html"),
                        Path(pydir,  f"{tmpl_name}.html"),
                        lastmod_time,
                        {"STABILITY": "Beta" if stability != "stable" else ""},
                    )
        sys.argv.remove("readme")

        if len(sys.argv) == 1 or (len(sys.argv) == 2 and dry_run):
            return

    if "manifest" in sys.argv[1:]:
        # MANIFEST.in's contents depend on the `attrs` dict DisplayCAL/setup.py's
        # setup() assembles (data_files, packages, ...), so the regeneration
        # itself has to run there, not here.
        from DisplayCAL.setup import setup as real_setup

        real_argv = sys.argv
        sys.argv = [real_argv[0], "generate_manifest_in"] + (
            ["--dry-run"] if dry_run else []
        )
        try:
            real_setup()
        finally:
            sys.argv = real_argv
        sys.argv.remove("manifest")

        if len(sys.argv) == 1 or (len(sys.argv) == 2 and dry_run):
            return

    create_appdata = (
        (appdata or "install" in sys.argv[1:] or "sdist" in sys.argv[1:])
        and not help
        and not dry_run
    )

    if create_appdata:
        with open(str(Path(pydir, "CHANGES.html")), "r", encoding="UTF-8") as f:
            readme = f.read()
            changelog = get_latest_changelog_entry(readme)

    if create_appdata:
        from DisplayCAL.setup import get_scripts
        from DisplayCAL import localization as lang

        scripts = get_scripts()
        provides = [f"<python3>{NAME}</python3>"]

        for script, desc in scripts:
            provides.append(f"<binary>{script}</binary>")

        provides = "\n\t\t".join(provides)
        lang.init()
        languages = []

        for code, tdict in sorted(lang.LDICT.items()):
            if code == "en":
                continue

            untranslated = 0

            for key in tdict:
                if key.startswith("*") and key != "*":
                    untranslated += 1

            languages.append(
                '<lang percentage="%i">%s</lang>'
                % (round((1 - untranslated / (len(tdict) - 1.0)) * 100), code)
            )

        languages = "\n\t\t".join(languages)
        tmpl_name = APPSTREAM_ID + ".appdata.xml"
        misc_tmpl_name = Path(pydir, "misc", tmpl_name)
        dist_tmpl_name = Path(pydir, "dist", tmpl_name)
        replace_placeholders(
            misc_tmpl_name,
            dist_tmpl_name,
            lastmod_time,
            {
                "APPDATAPROVIDES": provides,
                "LANGUAGES": languages,
                "CHANGELOG": format_changelog(changelog, "appstream"),
            },
        )

    if appdata:
        sys.argv.remove("appdata")

    if inno and sys.platform == "win32":
        for tmpl_type in [bdist_cmd]:
            inno_template_path = Path(pydir, "misc", f"{NAME}-Setup-{tmpl_type}.iss")
            with open(inno_template_path, "r") as inno_template:
                print(f"inno_template_path: {inno_template_path}")
                template = inno_template.read()
                # print(template)
                inno_arch_raw = arch or get_platform().split("-")[1]
                inno_arch = "x64" if inno_arch_raw == "amd64" else inno_arch_raw
                inno_script = template % {
                    "AppCopyright": f"© {strftime('%Y')} {AUTHOR}",
                    "AppName": NAME,
                    "AppArch": inno_arch_raw,
                    "InnoArch": inno_arch,
                    "AppVerName": VERSION_STRING,
                    "AppPublisher": AUTHOR,
                    "AppPublisherURL": f"https://{DOMAIN}/",
                    "AppSupportURL": f"https://{DOMAIN}/",
                    "AppUpdatesURL": f"https://{DOMAIN}/",
                    "VersionInfoVersion": ".".join(map(str, VERSION_TUPLE)),
                    "VersionInfoTextVersion": VERSION_STRING,
                    "AppVersion": VERSION_STRING,
                    "Platform": get_platform(),
                    "PythonVersion": f"{sys.version_info[0]}.{sys.version_info[1]}",
                    "URL": f"https://{DOMAIN}/",
                    "HTTPURL": f"http://{DOMAIN}/",
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

        sys.argv.remove("inno")

        if len(sys.argv) == 1 or (len(sys.argv) == 2 and dry_run):
            return

    if not appdata or sys.argv[1:]:
        print(sys.argv[1:])
        from DisplayCAL.setup import setup

        setup()

    if dry_run or help:
        return

    if setup_cfg or ("bdist_msi" in sys.argv[1:] and use_setuptools):
        shutil.copy2(Path(pydir, "setup.cfg.backup"), Path(pydir, "setup.cfg"))


if __name__ == "__main__":
    setup()
