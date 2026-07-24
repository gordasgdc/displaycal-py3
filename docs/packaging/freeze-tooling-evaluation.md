# Freeze tooling evaluation (#917)

Status: evaluation only, no tooling migration has started. This document is
the deliverable requested by #917: assess maintained alternatives to
`py2app`/`py2exe`/`bdist_bbfreeze`/PyInstaller (`bdist_pyi`) and propose a
migration plan. It does not change `DisplayCAL/freeze.py`, `DisplayCAL/setup.py`,
or `native_build.py`.

**Sequencing note (maintainer decision, 2026-07-24):** DisplayCAL 4.x drops
wx entirely and ships Qt-only. That changes this evaluation materially, wx
bundling is currently the single biggest source of manual hook work for
every candidate below, and it's going away regardless of which freeze tool
is picked. The recommendation in this document (§5) is written for a
**Qt-only** target and assumes the actual freeze-tooling migration happens
*after* wx is fully removed from the codebase, not before. Attempting this
migration while wx and Qt still coexist (the current `DISPLAYCAL_UI=qt`
additive state) would mean paying the wx-bundling cost twice: once now,
and again when wx is deleted. See §2 and §6 for how this affects scoping.

## 1. What's actually live today

`DisplayCAL/setup.py` and `native_build.py` implement four freeze paths as
old-style `distutils` Command classes, but only two of them are exercised by
CI or the release process:

| Path | Used by CI (`release_builds.yml` / `nightly_builds.yml`)? | Notes |
|---|---|---|
| `py2app` (macOS) | Yes | `.app` bundle -> DMG, one build per arch (x86_64 has been dropped from the matrix, arm64 only) |
| `py2exe` (Windows) | Yes | Windows x64 uses the PyPI wheel; win-arm64 has no upstream wheel and needs a `git clone` + `--no-build-isolation` install from `py2exe/py2exe` HEAD (`nightly_builds.yml:53-66`) |
| `bdist_bbfreeze` | No | Referenced in `setup.py`/`native_build.py` only. `bbfreeze` has been unmaintained for years and doesn't install on any currently supported Python (3.9-3.14); this code path is dead |
| `bdist_pyi` (PyInstaller) | No | Partial/started implementation in `native_build.py` (spec template generation, dist-dir layout) but never wired into a CI workflow or documented as a supported build target |

Linux ships as a plain wheel plus DEB/RPM/AppImage/Flatpak, none of which
need a freeze tool at all, so this evaluation is scoped to **macOS and
Windows only**.

Practical implication: this isn't a 1:1 swap of four tools, it's replacing
two live integrations (py2app, py2exe) and deleting two dead ones
(bdist_bbfreeze, bdist_pyi), which #916 already started doing for the
surrounding scaffolding.

## 2. Constraints specific to this codebase

- **wx is transitional, Qt is the long-term target.** Today, wx and Qt
  (PySide6) coexist per the 4.0 migration (`DISPLAYCAL_UI=qt`), and 4.x is
  planned to drop wx entirely. That means "does this tool bundle wx well"
  is a question worth answering only if the migration lands *before* wx is
  removed; if it lands after (the recommended order, see the sequencing
  note above), wx bundling quality drops out of the decision entirely and
  the only hook quality that matters is Qt/PySide6, which is where all
  three candidates below are strongest anyway. This is the single biggest
  way the picture in this document differs from a "freeze tooling in
  isolation" evaluation.
- **Many entry points, not one binary.** `get_scripts()` in `freeze.py`/
  `setup.py` enumerates ~10 standalone tools (3DLUT maker, curve viewer,
  profile info, scripting client, synthprofile, testchart editor,
  VRML-to-X3D converter, eeColor-to-madVR converter, apply-profiles
  launcher, main app), each with its own icon and, on macOS, its own `.app`
  bundle. The current macOS build freezes once and then hand-builds the
  other `.app` bundles as symlink farms into the same frozen payload
  (`create_app_symlinks()` in `DisplayCAL/setup.py:232-383`) rather than
  re-freezing per tool, almost certainly for build-time reasons. Any
  replacement needs an equivalent (either the same symlink-farm trick, or a
  tool that supports multiple-executables-from-one-freeze cheaply).
- **Windows ARM64.** No upstream `py2exe` wheel exists for it today (source
  build workaround, see above). This is the constraint most likely to
  determine which alternative is even viable, since not all candidates
  support it yet.
- **Custom Qt plugin bundling.** `copy_qt_plugins()` in `freeze.py` exists
  specifically because py2exe has no Qt-aware hook and silently drops
  `platforms/qwindows.dll` and friends. This is exactly the kind of thing a
  maintained tool's built-in Qt recipe should remove, so it's a concrete
  signal for evaluating hook quality, not just "does it run."
- **Legacy VC90 CRT handling** (`vc90crt_copy_files`) predates the Universal
  CRT and is very likely dead weight on any Python 3.10+ toolchain
  regardless of which freezer is used; worth a separate cleanup ticket
  independent of #917.

## 3. Candidates

### PyInstaller
Actively maintained, by far the largest hook ecosystem and community, has an
in-tree PySide6 hook (Qt's own docs point to it). Already has a
**half-started integration in this repo** (`bdist_pyi` in
`native_build.py`), so picking it would reuse, rather than discard, existing
work. Pure bundler (no C toolchain needed at build time). Windows ARM64:
supported as a packaging target for a while now. wx hooks exist in the
community but are irrelevant if this migration lands post-wx-removal (see
sequencing note above).

### Nuitka
Actively maintained, compiles to C rather than just bundling the
interpreter, meaningfully smaller/faster output, Qt recommends it (or
PyInstaller) directly in their own deployment docs, for a Qt-only codebase
this endorsement carries more weight than it did in the dual-toolkit
framing. Downsides for us specifically: requires a working C/C++ toolchain
in every build environment (new CI dependency on all three OSes), noticeably
longer build times, and, critically, **standalone/onefile mode does not yet
work on native Windows ARM64** (lacks binary dependency analysis there as of
mid-2026) - the exact target we currently limp along for with a
source-built py2exe. That alone is close to disqualifying unless we're
willing to cross-compile win-arm64 from an x64 host, which is extra
complexity this evaluation shouldn't wave away. This ARM64 gap is
independent of the wx/Qt question, it doesn't improve just because wx is
gone.

### cx_Freeze
Actively maintained (8.6.x shipping regularly through 2026), has in-tree
hooks for PySide6, and is the closest in spirit to what's here today: it's
also a `distutils`/`setuptools` Command-based API (`cx_Freeze.setup(...,
executables=[Executable(...)])`), which is the smallest conceptual jump from
the current `py2exe`/`py2app` `Target`-list pattern in `freeze.py`. Windows
ARM64 MSI support landed for Python 3.13+, which happens to line up with
what `release_builds.yml` already uses for the arm64 runner
(`python-version: '3.13'`) - a real point in its favor, but this specific
claim came from web search rather than a build we've run, and needs
verification with a PoC before being load-bearing for a decision. Its
narrower third-party hook catalog compared to PyInstaller was previously
flagged as a wx-bundling risk; with wx out of the picture (post-4.x) that
concern mostly evaporates since its in-tree PySide6 hook is the only one
that matters.

### Briefcase (BeeWare)
Ruled out regardless of the wx/Qt question. Briefcase is a much larger
commitment than a freeze-tool swap, it dictates project layout and how the
app is packaged end to end, not just how it's frozen, and DisplayCAL's
many hand-built standalone-tool bundles (§2) don't map cleanly onto its
single-app model. Out of scope for #917, which is about freeze tooling,
not a packaging-workflow rewrite.

### PyOxidizer
Ruled out. Development has stalled for years; not a "maintained alternative"
by the issue's own bar.

### bdist_bbfreeze / current PyInstaller stub
Not viable as-is: `bbfreeze` doesn't install on any currently supported
Python. The existing `bdist_pyi` code is a reasonable starting skeleton if
PyInstaller is chosen, not a reason on its own to choose it.

## 4. Comparison summary

Evaluated for the post-wx-removal (Qt-only) target, per the sequencing note
above:

| | PyInstaller | Nuitka | cx_Freeze |
|---|---|---|---|
| Maintenance | Active, largest community | Active | Active |
| Qt (PySide6) hook | In-tree, mature | Plugin, Qt-recommended | In-tree |
| Build-time C toolchain | No | Yes (new CI dependency) | No |
| Windows ARM64 (standalone) | Supported | **Not yet supported** | Supported (Python >= 3.13, needs verification) |
| API shape vs. current code | Spec-file / CLI | CLI / setup.py plugin | `setup(executables=[...])`, closest match to current `Target` pattern |
| Existing work to build on | Partial `bdist_pyi` skeleton | None | None |
| Output size/speed | Baseline | Smaller/faster (compiled) | Baseline |

(wx hook quality dropped from this table, see §2, it only matters if the
migration is done before wx is removed, which is not the recommended order.)

## 5. Recommendation

Evaluate **cx_Freeze first**, with **PyInstaller as the fallback** if cx_Freeze's
Qt hook coverage or Windows ARM64 story doesn't hold up in practice.
Reasoning:

- It's the smallest structural change from `freeze.py`/`setup.py`'s existing
  `Target`-list, Command-class pattern, lowest risk of collateral breakage
  in the parts of this file that aren't about freezing (data file
  enumeration, icon handling, manifest generation).
- Its Windows ARM64 support timeline matches what the release workflow
  already targets (Python 3.13 on `windows-11-arm`), unlike Nuitka which is
  presently not viable there.
- No new C/C++ toolchain requirement in CI, unlike Nuitka.
- With wx gone, its narrower hook catalog (previously a wx-bundling risk
  relative to PyInstaller) stops mattering, its PySide6 hook is in-tree
  either way.

Nuitka remains attractive for output quality (smaller, faster binaries) and
is worth a second look once/if its Windows ARM64 standalone support matures,
but it isn't a safe pick today given our ARM64 requirement.

This recommendation should not be treated as final until backed by a PoC
(see open questions below); it's a starting point for the next issue,
not authorization to start ripping out `py2app`/`py2exe` yet. It also
assumes wx has already been removed by the time that PoC work starts, per
the sequencing note, if that turns out not to be true, re-add the wx hook
comparison this version dropped.

## 6. Proposed migration plan (one platform at a time, per the issue)

0. **Sequencing gate**: don't start the PoC steps below until wx has been
   fully removed from the codebase (4.x). Doing this cleanup today
   (step 1) doesn't depend on that, it's independent of which GUI toolkit
   is in use.
1. **Delete the dead paths now** (`bdist_bbfreeze`, `bdist_pyi` skeleton)
   as a small, independent cleanup, same spirit as #916. Low risk, shrinks
   the surface area before touching anything live, and doesn't need to wait
   on the wx removal.
2. **macOS PoC** (post-wx-removal): build the main app bundle with
   cx_Freeze, verify Qt plugin bundling starts correctly, verify
   codesigning/notarization still works with cx_Freeze's `.app` output
   shape.
3. **Windows PoC** (post-wx-removal): build x64 first (wheel exists), then
   validate the win-arm64 story that's currently a build-from-source
   workaround for py2exe.
4. Only after both PoCs pass: port `create_app_symlinks()`/per-tool icon
   handling, replace `py2app`/`py2exe` in `native_build.py` and the
   `release_builds.yml`/`nightly_builds.yml` workflows, drop
   `requirements-dev.txt`'s `py2app`/`py2exe` lines.
5. Re-evaluate the legacy `vc90crt_copy_files()` step for removal
   separately, it predates the toolchain we build with now regardless of
   which freezer wins.

## 7. Open questions requiring a PoC (not yet answered by this doc)

- Does cx_Freeze's win-arm64 MSI support actually work end-to-end on the
  `windows-11-arm` GitHub runner, or only in theory? (The claim above came
  from web search, not a build we've run.)
- Can cx_Freeze reproduce the multi-`.app`-bundle-from-one-freeze trick
  `create_app_symlinks()` relies on, or does each tool need its own freeze
  invocation (build-time cost)?
- What does cx_Freeze do with the Qt plugin directory by default, does it
  still need a `copy_qt_plugins()`-equivalent, or is that handled by its
  in-tree hook?
- If the wx removal (4.x) slips and this migration ends up needing to
  happen while wx is still present, re-add the wx-bundling comparison this
  revision dropped from §3/§4 before treating §5's recommendation as final.

## Sources

- [Qt for Python & PyInstaller](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html)
- [cx_Freeze release notes](https://cx-freeze.readthedocs.io/en/latest/releasenotes.html)
- [cx_Freeze documentation](https://cx-freeze.readthedocs.io/)
- [Nuitka Windows ARM64 / macOS arm64 platform support discussion](https://github.com/Nuitka/Nuitka/issues/2724)
- [BeeWare February 2026 status update](https://beeware.org/news/buzz/2026/february-2026-status-update/)
