# DisplayCAL-CG — notes for contributors

DisplayCAL-CG is an edition of [DisplayCAL](https://displaycal.net) (community continuation:
[eoyilmaz/displaycal-py3](https://github.com/eoyilmaz/displaycal-py3)), maintained by Cristi Gordaș on the same
code and the same **GPLv3** licence. It stays 100 % free: no licence keys, trial or feature gating, ever.
The original authors' credits are kept in `DisplayCAL/meta.py`, `LICENSE.txt` and `docs/upstream/`.

## Layout worth knowing

- `DisplayCAL/meta.py` — branding constants (`NAME`, `AUTHOR`, `DOMAIN`, GitHub URLs). `NAME` stays `"DisplayCAL"`:
  about seventy places in the setup code use it as a literal package identifier, so a hyphen there breaks packaging.
  The visible name "DisplayCAL-CG" lives in strings, icons and the names of the distributed packages.
- `DisplayCAL/lang/*.yaml` — one YAML file per language (English is the reference; Romanian and Spanish are complete).
  A new string must be added to every file; placeholders (`%s`, `%d`) must match.
- `DisplayCAL/ui/` — the Qt (PySide6) interface. `guide_panel.py` is the guided flow, `main_window.py` the advanced
  tabs, `text_scale.py` the single mechanism for the "Text size" setting (system size × level; widgets declare a
  multiplier instead of hard-coding points).
- `DisplayCAL/measurement_plan.py` — the one function that computes total patches, block size, number of blocks and the
  estimated time; the interface and the measurement runner both use it, so what is shown is what runs.
- `DisplayCAL/worker_session.py`, `session_journal.py`, `measured_speed.py` — session journal, recovery after an
  interrupted run, observed instrument speed.
- `docs/guides/` — sources of the RO/EN/ES PDF guides (`python docs/guides/generate_guides.py`).
- `docs/_site_src/` — sources of the public pages and of the READMEs (`build_site.py`, `build_readme.py`,
  `strings.py`, `ASSET_MANIFEST.md`). The technical guide on the site is generated from `docs/guides/`.

## Versions and updates

- `DisplayCAL/VERSION` follows upstream (for example `3.10.0.dev82`). The edition's own build number is
  `DisplayCAL/CG_BUILD` (an integer, bundled in the application). Tags look like `v3.10.0.dev82-cg.N`.
- The update check compares `(major, minor, patch, cg_build)`, so a new `cg.N` with the same upstream number is
  detected. Increase `CG_BUILD` before tagging a new build.
- Stable download names: `DisplayCAL-CG.pkg`, `DisplayCAL-CG.dmg` (macOS), `DisplayCAL-CG-Setup.exe` (Windows);
  versioned copies are published next to them. The self-updater downloads from `releases/latest/download/<stable name>`.
- Resources that the upstream project hosts (ArgyllCMS downloads, instrument firmware, colorimeter corrections) keep
  pointing at the upstream domains (`UPSTREAM_RESOURCES_DOMAIN`, `COLORIMETER_CORRECTIONS_DOMAIN` in `meta.py`).

## Building

- **macOS** — `build_pkg.sh` (py2app, Developer ID signing, notarization, stapling, `.pkg` and `.dmg`). It needs
  `APPLE_SIGN_IDENTITY_APP`, `APPLE_SIGN_IDENTITY_INSTALLER` and a `notarytool` keychain profile `gdc-notary`
  (or `APPLE_NOTARY_*` variables). Lessons that cost builds: do not sign with `--deep` (the satellite tools symlink into
  the main bundle); sign every Mach-O file by type, not by extension; keep dylibs of wheels out of `python313.zip`;
  pre-write `LC_ID_DYLIB` with `install_name_tool` before py2app; normalise permissions of the payload (a restrictive
  umask once left bundled files unreadable for normal users — the script now fails if any file is not world-readable).
- **Windows** — `python native_build.py inno` (Inno Setup, `x64compatible` so it installs on Windows 11 ARM64 through
  x64 emulation). CI (`.github/workflows/release_builds.yml`) builds the x64 installer on tags `v*-cg.*` and on demand;
  signing runs only when the self-signed certificate secrets exist (`codesigning/README-windows.md`).
- ArgyllCMS is bundled and verified against a fixed hash (`DisplayCAL/argyll_integrity.py`,
  `scripts/stage_argyll.py`); an unverifiable download is refused.

## Tests

```
export QT_QPA_PLATFORM=offscreen          # Qt tests run headless
export PATH=/path/to/ArgyllCMS/bin:$PATH  # some dialogs call Argyll tools
python -m pytest tests/test_ui_text_scale.py tests/test_ui_guide_panel.py -q
```

Qt test files are best run one file at a time. Interface changes should be checked at the three text sizes
(Normal, Large, Very large) and in light and dark themes; macOS and Windows differ in native controls, so check both.

## Conventions

- Public release notes describe what changed for users; internal debugging detail stays in commits and issues.
- A feature is finished when code, packaging, version, `CHANGELOG.md`, the three languages and the Windows/macOS
  parity are done; anything left is stated explicitly.
- Claims in documentation and on the site are limited to what has been verified; unverified limits are listed
  (multi-hour sessions, other instruments, native x64 Windows, Intel Macs, probe disconnection).
