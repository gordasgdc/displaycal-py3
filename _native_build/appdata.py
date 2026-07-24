from pathlib import Path

from _native_build import meta
from _native_build.templates import format_changelog, replace_placeholders


def generate(pydir: Path, lastmod_time) -> None:
    """Generate dist/<APPSTREAM_ID>.appdata.xml from misc/<APPSTREAM_ID>.appdata.xml."""
    with open(str(Path(pydir, "CHANGES.html")), "r", encoding="UTF-8") as f:
        readme = f.read()
        changelog = meta.get_latest_changelog_entry(readme)

    from DisplayCAL.setup import get_scripts
    from DisplayCAL import localization as lang

    scripts = get_scripts()
    provides = [f"<python3>{meta.NAME}</python3>"]

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
    tmpl_name = meta.APPSTREAM_ID + ".appdata.xml"
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
