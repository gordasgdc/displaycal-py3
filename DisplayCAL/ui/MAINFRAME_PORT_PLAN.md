# MainFrame → Qt port plan

Structural analysis of `DisplayCAL/display_cal.py::MainFrame` and a staged plan
for porting it to the Qt UI (`DisplayCAL.ui`). This is the "dedicated, refactored
pieces" work the top-level [README.md](README.md#L198-L204) defers.

## Scale

- `display_cal.py`: 22,921 lines.
- `MainFrame` (L2150–L21826): ~19,700 lines, **352 methods**.
- Sibling frames in the same file: `ExtraArgsFrame`, `GamapFrame`,
  `StartupFrame`, `MeasurementFileCheckSanityDialog`, plus module-level helpers.
- The measurement patch window `MeasureFrame` lives separately in
  `wx_measure_frame.py` (959 lines) and owns the measure-frame geometry that
  three ported tools are waiting on.

### Monster methods (break these up as they move — per README migration pattern #2)

| Lines | Method | Notes |
| --- | --- | --- |
| 1736 | `create_colorimeter_correction_handler` (L13970) | Self-contained feature; a candidate to extract wholesale. |
| 888 | `load_cal_handler` (L19769) | Loads a `.cal`/profile and repopulates every control. |
| 503 | `init_controls` (L3665) | wx widget construction — replaced, not ported. |
| 485 | `init_menus` (L3058) | wx menubar — replaced, not ported. |
| 471 | `measurement_report_consumer` (L10206) | Report result handling. |
| 449 | `profile_finish` (L12423) | Post-profile workflow. |
| 445 | `measurement_report_handler` (L9623) | |
| 412 | `profile_share_handler` (L8422) | Upload to online DB. |
| 407 | `update_colorimeter_correction_matrix_ctrl_items` (L5027) | |
| 329 | `setup_patterngenerator` (L11091) | |

## Three-pile classification

Sorting the 352 methods by *what transfers to Qt*, per the framing agreed with
the maintainer. The goal is that "porting MainFrame" is mostly **extraction of
backend logic** (which also thins the still-shipping wx `MainFrame`), with the
genuinely wx-shaped glue left alone until its Qt replacement lands.

### Pile 1 — backend logic mislocated in the UI → **extract now, both paths win**

These are toolkit-agnostic and can move to plain modules that *both* the wx
`MainFrame` and the future Qt window call into. Extracting them is independently
testable and reduces `MainFrame` today.

- **`*_config_with_option` setters** (~40 methods, L20657–L21059):
  `set_profile_quality_config_with_option`, `set_gamap_*_config_with_option`,
  `set_whitepoint_*_config_with_option`, `set_measurement_mode_*`, … These are
  already essentially pure `option str → config` marshalling. **Lowest-risk
  extraction; do this first as a proof point.**
- **`get_*` settings getters** (L18586–L18900): `get_ambient`,
  `get_instrument_type`, `get_measurement_mode`, `get_profile_type`,
  `get_whitepoint`, `get_luminance`, `get_trc`, `get_calibration_quality`, …
  Currently read widget state; refactor to read `config`, so the value source is
  toolkit-neutral.
- **Measurement-mode derivation**: `get_measurement_modes` (L4698, 243 lines),
  `get_ccxx_measurement_modes` — pure data derivation from instrument/config.
- **Testchart/profile naming**: `create_profile_name` (L18237),
  `profile_name_info`, `check_profile_name` — string building over config.
- **File parsing/validation**: `parse_calibration_file`, `validate_icc_profile`,
  `validate_calibration_data`, `get_calibration_file_path`,
  `remove_missing_calibration`.
- **Orchestration bodies** (the non-widget core of the workflow methods):
  `just_calibrate`, `just_measure`, `just_profile`, `calibrate_and_profile`,
  `check_copy_ti3`, `start_profile_worker`. These already delegate to
  `worker.Worker`; the extractable part is the sequencing/decision logic
  currently interleaved with `HideAll`/dialog calls.
- **Colorimeter-correction pipeline internals**: the producer/consumer bodies of
  `create_colorimeter_correction_handler`, `import_colorimeter_correction`,
  `upload_colorimeter_correction` — the Argyll/CGATS work, not the dialogs.

### Pile 2 — wx widget & event glue → **leave alone, gets replaced not refactored**

Rebuilt natively in Qt; refactoring it in wx is throwaway effort.

- Widget construction/layout: `init_controls` (503), `init_frame` (266),
  `init_menus` (485), `update_menus`, `enable_menus`, `set_size`,
  `get_min_height`, `update_layout`, `update_scrollbars`.
- Frame lifecycle: `OnMove`, `OnResize`, `OnClose`, `Show`, `HideAll`,
  `veto_close_event`, `check_keydown`, `start_timers`/`stop_timers`,
  `init_timers`. (Qt equivalents already exist in `base_window.py`.)
- The ~100 `*_ctrl_handler` / `*_btn_handler` methods **as signatures**
  (`event: wx.Event`). Their *bodies* often contain Pile-1 logic to extract; the
  thin handler shell itself is wx.
- `update_*` UI-sync methods (`update_controls`, `update_main_controls`,
  `update_adjustment_controls`, `show_*_ctrls`, …): the config→widget push is
  glue; any value *computation* inside is Pile 1.

### Pile 3 — shared seams → **document, keep behaviourally identical**

- **Config keys** are the real contract between the two UIs. The measure-frame
  slice hinges on `dimensions.measureframe`,
  `dimensions.measureframe.unzoomed`, `measureframe.center[.manual]`,
  `measureframe.show`, `measureframe.zoomin`, plus `whitepoint.visual_editor.*`
  already shared by the ported whitepoint tool.
- **`worker.Worker` entry points**: `create_3dlut`, `prepare_targen`,
  `calculate_gamut`, calibrate/profile/measure drivers — already
  binding-agnostic and reused by the ported tools.
- **Scripting/IPC**: `get_commands` (L13153) + `process_data` (L13186, 205
  lines) map onto the existing `ScriptingHostMixin`; the per-widget
  introspection commands are added per window as noted in the README.

## Staged port plan

Ordering principle: **unblock the deferred tool work first** (highest
cross-cutting payoff), then port the main window in vertical, independently
shippable slices, extracting Pile-1 logic ahead of each slice so the wx path
benefits immediately.

### Stage 0 — Pile-1 extraction proof (no Qt yet) — **DONE**

Extract the pure `*_config_with_option` setters into a toolkit-neutral module,
have the wx `MainFrame` delegate to it, and add unit tests. Ships with wx
unchanged, verifies the extraction approach, and builds the surface the Qt
window needs.

**Landed:** `DisplayCAL/main_settings.py` (30 functions: 28 `*_config_with_option`
setters plus `update_whitepoint_config_from_temperature` and
`update_ccmx_items_from_path`), covered by `tests/test_main_settings.py` (35
tests). `MainFrame` now delegates via thin one-line wrappers, so the
`load_cal_handler` dispatch table and scripting surface are untouched. Two
setters are intentionally left on `MainFrame` because they're genuinely coupled
to the running window: `set_display_number_config_with_option` (touches
`self.worker` + `get_set_display`) and `set_video_levels_config_with_option`
(calls a UI method).

**Deferred (learned during Stage 0):** the `get_*` settings getters
(`get_whitepoint`, `get_trc`, `get_profile_type`, …) turned out *not* to be
clean Pile 1 — they read **live wx widget state** (`self.whitepoint_ctrl
.GetSelection()`, `self.trc_textctrl.GetValue()`), not `config`. Extracting them
"to read config" would change semantics (UI state can differ from committed
config), so they belong with the Qt widget layer, not a neutral module. They
move in Stage 3 as the Qt controls are built.

### Stage 1 — MeasureFrame (measure-frame geometry) → Qt — **DONE**

Port `wx_measure_frame.py::MeasureFrame` (959 lines) to
`DisplayCAL/ui/measure_frame.py`. This is the shared dependency that unblocks
**three** already-ported tools:

- testchart editor's deferred image/DPX pattern export,
- the visual whitepoint editor's **Measure** button,
- the whitepoint editor's pattern-generator patch output.

Geometry persists to the Pile-3 `dimensions.measureframe*` /
`measureframe.*` config keys, so the Qt frame stays interchangeable with the wx
one. Self-contained (no giant `MainFrame` dependency), so it's a clean first
Qt slice.

**Landed:** `DisplayCAL/ui/measure_frame.py` (`MeasureFrame(BaseWindow)` plus a
`_MeasurePanel` central widget). The load-bearing relative<->pixel geometry
maths is factored out into three toolkit-neutral module-level functions
(`default_measureframe_size`, `compute_frame_geometry` from `place_n_zoom`,
`compute_dimensions` from `get_dimensions`), unit-tested without a screen in
`tests/test_ui_measure_frame.py` (10 tests, exact place->read-back round-trips).
The window uses Qt `QScreen` for display enumeration in place of `wx.Display`,
native widgets for the zoom/centre/darken/measure controls, `show_controls()`
to blank the patch during measurement, and `show_rgb()` (numpy ordered dither
for sub-integer 8-bit levels) for pattern-window output. Verified headless
(`QT_QPA_PLATFORM=offscreen`) construct-and-exercise: show, zoom in/normal/max,
centre, `show_rgb` (dithered + exact), close.

**Parent integration deferred to the Qt main window:** the wx tool called
`self.Parent.call_pending_function()` / `get_set_display()` /
`restore_measurement_mode()` etc. directly. The Qt port exposes a
`measure_requested` (and `pattern_shown`) **signal** instead, so the main window
wires the Measure button to its flow later; standalone, the signal just closes
the window. **Dropped wx-only workarounds:** the `_last_set_size` DPI-correction
hack and the multi-X-screen / TwinView heuristics in `get_display` (Qt works in
logical high-DPI coordinates), matching the other tools' simplifications.

### Stage 2 — Measurement flow orchestration — **DONE**

Port `setup_measurement`, `setup_patterngenerator`, the `measureframe`
subprocess trio (`start_measureframe_subprocess`, `measureframe_subprocess`,
`measureframe_consumer`), `setup_observer_ctrl`, `set_pending_function` /
`call_pending_function`, against the Stage-0 extracted settings. No full main
window yet — expose it as the engine the Qt main window and tools drive.

**Landed:** `DisplayCAL/ui/measurement_flow.py`, a toolkit-neutral engine
covered by `tests/test_ui_measurement_flow.py` (28 tests, no display/QApplication
needed). It holds the load-bearing, testable core of the flow cluster:

- `decide_presentation()` — the `setup_measurement` branch logic returning a
  `PresentationMode` (`CALL_PENDING` for virtual/dry-run displays,
  `SHOW_FRAME` in-process on macOS/Windows/frozen/Wayland-patch, `SUBPROCESS`
  otherwise).
- `build_measureframe_command()` / `run_measureframe_subprocess()` /
  `interpret_measureframe_result()` — the subprocess trio's toolkit-neutral
  parts. The command now launches the **Qt** `DisplayCAL.ui.measure_frame`, and
  the `255` (Measure) / `0` (clean close) exit-code contract is honoured by that
  frame's `main()` (updated in Stage 1's file). `run_measureframe_subprocess`
  takes an `on_start` callback so the caller keeps the `Popen` for cancellation.
- `observer_items()` — `setup_observer_ctrl`'s Argyll-version-dependent observer
  label map, derived from `config.VALID_VALUES["observer"]`.
- `MeasurementFlow` — the `set_pending_function` / `call_pending_function` state
  machine (`set` / `take` / `clear` / `has_pending_function`) plus
  `plan_measurement()`, which stages the pending function and returns the
  presentation decision, keeping the `wrapup` flag out of the pending kwargs.

**Deferred to the Qt main window (Pile 2 / window layer):** the pattern-generator
setup **dialogs** (Prisma host prompt, madTPG / Resolve / Chromecast wait
dialogs) are wx widget glue rebuilt natively later; `patterngenerator_kind()`
captures only the toolkit-neutral choice of *which* flow a display needs. The
threading around the subprocess (wx `delayedresult` → Qt `QThread`) and the
`call_pending_function` window side-effects (hide/blank the frame, the 100 ms
deferral → `QTimer.singleShot`) also belong to that layer, so the engine just
holds and hands back the pending function.

### Stage 3 — Qt main window shell + settings tabs — **DONE**

Build `DisplayCAL/ui/main_window.py` (`MainWindow(BaseWindow)`): the tabbed
layout, menubar, display/instrument selectors, and the calibration/profiling
settings controls, wired to the Stage-0 settings module and Stage-2 flow.
Embeds the already-ported tool panels (curve viewer's `CurvePanel`, profile
info, etc.) where the wx UI opens child frames. Gated behind `--qt`.

Because `MainFrame` is ~19,700 lines, Stage 3 lands as vertical sub-slices that
each populate one tab; the shell + first tab are the first slice.

**Landed (shell + Display & Instrument tab):** `DisplayCAL/ui/main_window.py`,
covered by `tests/test_ui_main_window.py` (10 tests, headless offscreen). It
provides:

- `MainWindow(BaseWindow)` with menubar and geometry persistence (from
  `BaseWindow`), a vertical layout of header bar + tab bar + stacked panels +
  action-button bar (the header landed later, in Session 5 below).
- A tab bar of exclusive `QToolButton` toggles (Display, Calibration, Profiling,
  3D LUT) switching a `QStackedWidget` — the Qt equivalent of the wx custom
  `TabButton` / show-hide-settings-panel mechanism.
- The **Display & Instrument** tab wired: display / instrument (comport)
  `QComboBox`es populated from `Worker.enumerate_displays_and_ports` and
  `config`, persisting `display.number` / `comport.number` through an
  `_updating` re-entrancy guard (so repopulation never clobbers the stored
  selection). The name-marshalling (`display_items`, `instrument_items`) is
  factored into pure module functions and unit-tested. The **observer**
  `QComboBox` lives on the **Calibration** tab instead, matching wx's
  `main.xrc` (`calibration_settings_panel`, right after the two toggles); it
  persists `observer` and reuses Stage-2 `observer_items()`. Also wired,
  matching `main.xrc`'s `display_instrument_panel`: the display-LUT selector
  and link toggle (`display_lut_ctrl`/`display_lut_link_ctrl`, filtered to
  `Worker.lut_access`-capable displays, following `display_ctrl` while
  linked, and — since a wx-vs-Qt screenshot comparison (Session 4, see below)
  caught this row being unconditionally visible — now hidden unless
  `Worker.has_separate_lut_access()` (or the `use_separate_lut_access`
  override) says otherwise, and only ever considered on Linux, matching wx's
  `sys.platform not in ("darwin", "win32")` gate around the whole feature;
  the `detect_displays_and_ports_btn` refresh button (a synchronous
  simplification of wx's progress-dialog-driven `check_update_controls`);
  white/black-level drift compensation checkboxes; the display-update-delay
  and display-settle-time-multiplier override controls; the flash-field-
  pattern-insertion group (checkbox + interval/duration/level); and the
  output-levels radio group (auto/full-range/limited-range, bound to
  `patterngenerator.detect_video_levels` / `.use_video_levels`). Also now
  wired: `measurement_mode_ctrl` and the colorimeter-correction-matrix row,
  after extracting their instrument-capability logic out of `display_cal.py`
  into toolkit-neutral helpers in `DisplayCAL/colorimeter_correction.py`
  (`get_instrument_type`, `compute_measurement_modes`,
  `ColorimeterCorrectionCatalog` + `resolve_colorimeter_correction_selection`),
  mirroring the Stage 5+ CCXX-extraction precedent; `display_cal.py`'s
  `MainFrame.get_measurement_modes` / `get_cgats_measurement_mode` now delegate
  to these helpers unchanged (verified against the existing wx test suite).
  `update_colorimeter_correction_matrix_ctrl_items` itself was **not**
  refactored to delegate (its instance-cached state is read directly by
  `delete_colorimeter_correction_matrix_ctrl_item` elsewhere in `MainFrame`,
  and it's covered only by a shallow idempotency smoke test, so a
  behavior-preserving refactor was judged too risky to do blind); the Qt port
  only reuses the new pure `resolve_colorimeter_correction_selection` function
  standalone. Deliberately not reproduced in the Qt port: malformed-CCXX
  trashing, the observer-control visibility toggle
  (`show_observer_ctrl`), and the old-Argyll "projector/adaptive mode
  unavailable" fallback dialogs; the CCXX "info" button (`CCXXPlot`) shows a
  not-yet-available notice, matching the drop already made in
  `colorimeter_correction_io.py`.
- The calibrate / calibrate&profile / profile action buttons (present but
  disabled — Stage 4 wires them to `flow`, a `MeasurementFlow`).
- Gated behind `--qt`: `DisplayCAL/main.py::_get_qt_main(None)` now returns this
  window's `main`, so `DISPLAYCAL_UI=qt` launches it instead of the wx frame.

**Landed (Calibration / Profiling / 3D LUT tabs):** the three placeholder panels
are now real, config-backed settings tabs, covered by the expanded
`tests/test_ui_main_window.py` (40 tests, headless offscreen):

- **Calibration:** interactive-adjustment / calibration-update toggles;
  whitepoint (native / colortemp / xy, with the active field shown per mode and
  persisted to `whitepoint.colortemp` / `whitepoint.x` / `whitepoint.y`); white
  and black level (as-measured / custom → `calibration.luminance` /
  `calibration.black_luminance`); tone response curve (the 8-row selector +
  gamma text + relative/absolute type → `trc` / `trc.type`, faithful to the wx
  `get_trc` / reverse mapping including the BT.1886 and Gamma-2.2 presets); black
  output offset and black point correction sliders (0-100 → 0.0-1.0); ambient
  light level adjust; and the calibration speed slider with its inverse-quality
  label.
- **Profiling:** profile type (`profile.type`, modern-Argyll ordering), black
  point compensation, profile quality slider (with the gamma+matrix
  force-to-high coercion honoured by `config`), and the profile-name template.
- **3D LUT:** create-after-profiling, file format, LUT size, input/output bit
  depth, rendering intent, apply-TRC and apply-black-offset — all derived from
  `config.VALID_VALUES` so they track Argyll's supported sets.

The load-bearing marshalling (`CALIBRATION_QUALITY_LEVELS` /
`PROFILE_QUALITY_LEVELS` sliders, `PROFILE_TYPES`, `trc_value_from_selection` /
`trc_selection_from_config`, `lut3d_*_items`) is factored into pure module
functions and unit-tested without a display. Checkbox and value-combo bindings go
through generic `_add_check` / `_add_value_combo` helpers plus the `_updating`
re-entrancy guard, so construction-time repopulation never clobbers stored
config. The `get_*` settings getters deferred from Stage 0 are realised here as
the control-reading logic behind these tabs.

**Session 4 — wx-vs-Qt screenshot comparison.** Rendered every Qt settings tab
(`QWidget.grab()`, offscreen) and every wx settings panel (`wx.WindowDC` +
`wx.MemoryDC.Blit`, real window) side by side against an identical stubbed
`Worker` (fixed fake displays/instruments, matching `tests/test_ui_main_window
.py`'s `stub_worker`), the first rendered-pixel comparison done in this
parity-hardening effort (previous sessions only diffed `main.xrc` structurally).
Found and fixed one real regression: `display_lut_ctrl`/`display_lut_link_ctrl`
(Session 2) were unconditionally visible in Qt, where wx only shows that row on
Linux and only when `Worker.has_separate_lut_access()` (or
`use_separate_lut_access`) is true — on macOS/Windows wx hides it
unconditionally and forces `display_lut.link=1`. `update_display_lut_ctrl()`
now reproduces both conditions (`sys.platform not in ("darwin", "win32")` gate
plus the capability check) via `QFormLayout.setRowVisible`; 2 new regression
tests added (`test_display_lut_row_hidden_on_macos_and_windows`,
`test_display_lut_row_hidden_without_separate_lut_access`), and the 3 existing
population tests now force `sys.platform = "linux"` so they still exercise the
algorithm (82 total in `tests/test_ui_main_window.py`, up from 80).

Everything else the comparison surfaced was already-documented deferred scope,
now visually confirmed rather than newly discovered: the colorful wx header
banner (logo + tagline + `<Current>` settings-file selector with info/open/
save/delete/download icons) had no Qt equivalent at the time (later built in
Session 5, below); every tab's explanatory tip text (wx's
`*_settings_info_panel`,
e.g. "Profiling is the process of characterizing..."; not italic despite the
name — see Session 6) had no Qt equivalent at the time either (later built in
Session 6, below); and the
`show_advanced_options` menu toggle (Qt has no menu items beyond File yet)
that in wx hides/shows a large fraction of controls across all four tabs by
default (black level, colortemp locus, display-delay overrides, ffp insertion,
output levels, ambient/black-point-correction, observer, profile type/gamap/
patch-sequence, 3D LUT encoding) — already tracked below, now confirmed via
screenshots to be the single largest source of visible wx/Qt mismatch since Qt
shows all of these unconditionally rather than gating them behind the toggle
(default off in wx).

**Deferred to later slices (Pile 2 / Stage 4-5):** the measure / visual-editor /
ambient-measure buttons, the gamap and testchart-editor / file-picker / profile
save-path launch buttons, profile-name token expansion + the `?` preview, the
estimated-measurement-time readouts, the black-point-rate advanced control,
and the 3D LUT encoding / HDR / content-colorspace sub-controls. These depend
on tools, dialogs or the Stage-4 flow and are rebuilt natively as those land.
(`show_advanced_options` itself is wired as of Session 8, below — this list is
now the reason its gating of *these specific* rows, which don't exist in Qt
yet, is also still deferred.)

**Session 5 — calibration/profile-file header bar.** Built the banner Session 4
flagged as missing: a new `_build_header()` in `main_window.py` adds the green
strip + blue logo/tagline banner and, below it, the functional
`calibration_file_ctrl` bar — the current-calibration/profile combo (recent
files + bundled presets, matching wx's `recent_cals`/`presets` bootstrap) plus
five icon buttons: profile info, load, create session archive, delete, and
install profile. The banner reuses wx's own `theme/header.png` artwork
(`_header_banner_pixmap()`, cropped to its logical `222x64` banner region and
loaded at `@2x` for HiDPI) rather than a separately-assembled icon+text label,
so its baked-in top-to-bottom blue gradient and wordmark colors match wx
exactly (the banner `QWidget` also carries that same gradient as a Qt
stylesheet so it extends past the artwork's fixed width); the icon buttons are
recolored white via `_header_icon_pixmap()` (a `QPainter`
`CompositionMode_SourceIn` fill), mirroring wx's on-the-fly "-inverted"
bitmaps, since they sit on a permanently dark blue bar regardless of the app's
light/dark theme. Chose full functional parity (not just the decorative
banner) after sizing up the five wx handlers behind it: four
(`install_profile_handler`, `create_session_archive_handler` +
producer/consumer, `delete_calibration_handler`, `profile_info_handler`) are
compact (60-100 lines) and already close to toolkit-neutral; the fifth,
`load_cal_handler`, is ~890 lines but turned out to be almost entirely pure
config manipulation already routed through `main_settings`'s per-option
setters (Stage 0) — porting the *orchestration* around those setters was
tractable once that was clear.

New toolkit-neutral module `DisplayCAL/calibration_file.py` (mirroring the
`profile_install.py` / `main_settings.py` precedent) holds: the
`recent_cals`/`presets` bootstrap and current-file resolution
(`build_recent_calibrations`, `resolve_calibration_selection`), calibration/
profile file parsing (`parse_calibration_file`, faithful port of
`parse_calibration_file`/`validate_icc_profile`/`validate_calibration_data`
minus the wx dialogs), the `restore_defaults_handler` config-restore logic
(`restore_defaults`), the dispcal/colprof option dispatch
(`apply_calibration_options`, calling `main_settings`'s setters), the
related-files-for-deletion scan (`related_files_for`, `delete_related_files`,
using `send2trash` same as wx), and session-archive file selection/creation
(`session_archive_filenames`, `session_archive_has_3dlut_files`,
`create_session_archive`, faithful port of
`create_session_archive_producer`). `InstallProfileWindow` (Stage 5+) gained a
one-line public `load_profile(path)` wrapper around its existing `_load_path`
so the header's install button can reuse it directly; the header's info
button reuses `ProfileInfoWindow` the same way.

Deliberately not reproduced (documented in `calibration_file.py`'s module
docstring, not silently dropped): EDID/instrument-ID auto-matching of a
loaded profile against the enumerated displays, and the "d" dispcal option's
virtual-display auto-select (`-dweb`/`-dmadvr`, used by the `video_*`
pattern-generator presets) — both already-deferred Pile-2 pattern-generator
scope; the legacy pre-`ARGYLL_DISPCAL_ARGS` `.cal` parsing branch (vanishing
real-world usage); the `3DLUT_*`/`SIMULATION_PROFILE` HDR config-mapper block
(the 3D LUT tab's HDR/encoding sub-controls are already-tracked deferred
scope above); cross-window resync with `lut3dframe`/`reportframe` (not ported
to Qt); importing compressed session archives via the load button (shows a
not-yet-available notice instead, matching the CCXX-info-button precedent);
and the delete-confirmation dialog's per-file checkboxes (wx lets you
individually toggle which related file gets deleted; Qt's confirmation lists
them as plain text and always deletes all of them). 18 new regression tests
in `tests/test_ui_main_window.py` (100 total, up from 82), covering combo
population/selection, preset loading (real bundled `.icc` presets, not
fakes), and each button's handler including the background-thread archive
path (mirroring `InstallProfileWindow`'s progress-dialog pattern).

**Session 5 follow-up — header visual fixes.** Maintainer screenshot-compared
the new banner against wx and flagged 3 issues, all fixed in `main_window.py`:
the wordmark now uses `_header_banner_pixmap()` (crops wx's own
`theme/header.png`/`header@2x.png` to its native `222x64` region instead of a
bare, undersized `headericon.png`); the banner `QWidget` carries the artwork's
baked-in top-to-bottom blue gradient (`#093d75`→`#0e59a9`) as a Qt stylesheet
`qlineargradient` so it's consistent past the artwork's fixed width; and the 5
header icon buttons are recolored white via `_header_icon_pixmap()` (unconditional,
since the bar is always dark blue regardless of the app's own theme).

**Session 6 — per-tab info panels (Session 4's "low-priority" gap).** Ported
wx's `*_settings_info_panel` (`calibration_settings_info_panel`,
`profile_settings_info_panel`, `lut3d_settings_info_panel`, and
`display_instrument_info_panel`, which uniquely holds two stacked texts —
a clock-icon "warm up" tip plus the usual dialog-information tip) to the
bottom of each of the four Qt settings tabs. New `MainWindow._build_info_panel()`
renders each `(icon_name, label_key)` row as a themed 32x32 icon beside a
word-wrapped `QLabel`; `_info_text_html()` translates wx's
`StaticFancyText` markup (`<font weight='bold'>` spans, blank-line paragraph
breaks) into Qt rich text (`<b>`, `<p>`) rather than re-authoring the long,
already-translated `info.*` strings from `lang/en.yaml`. Confirmed via
`xh_fancytext.py`/`main.xrc`/`display_cal.py` that wx's info text is plain
weight (not italic) apart from the bold spans — italic had been assumed in
the Session 4 note but isn't actually wx's style.

Each tab's builder now does `outer.addWidget(self._build_info_panel(...), 1)`
in place of the old bare `outer.addStretch(1)`, so the panel itself — not an
empty spacer — expands to fill the tab's remaining vertical space, matching
wx's `option=1, wxEXPAND` sizer flag on the same panel; inside
`_build_info_panel`, a trailing `grid.setRowStretch(len(rows), 1)` keeps the
icon/text rows packed at the top of that expanding area instead of being
vertically centered. Since these multi-paragraph texts can make a tab taller
than the window (most visibly the 3D LUT tab's 5-subsection text), the
settings `QStackedWidget` is now wrapped in a `QScrollArea`
(`setWidgetResizable(True)`), mirroring wx's own `calpanel`
(`wxScrolledWindow`, `wxHSCROLL|wxVSCROLL`) — previously the stack had no
scroll wrapper since no prior tab content was tall enough to need one.
Deliberately not reproduced: the wx `display_tech_info_show_btn` /
`TooltipWindow` sub-feature (a separate button + hyperlinked popup describing
LCD/OLED backlight technologies, `info.display_tech*` keys) — a distinct,
larger mini-dialog feature rather than a tip-text gap, left as its own future
slice. 6 new regression tests in `tests/test_ui_main_window.py` (106 total, up
from 100): markup-to-HTML conversion, the scroll-area wrapping, and each
tab's info text being present and translated.

**Session 8 — `show_advanced_options`.** Ported wx's `show_advanced_options`
Options-menu toggle (Session 4 had flagged it as the single largest confirmed
wx/Qt visual mismatch): a new `_build_options_menu()` adds an Options menu
with just this one checkable action — deliberately not the rest of wx's
`menu.options` (startup-sound/splash/fancy-progress/3D-LUT-tab toggles, or the
whole `menu.options.advanced` submenu of debug switches like
`enable_argyll_debug`/`extra_args`), since none of those gate anything this Qt
port has. `MainWindow._update_advanced_options_visibility()` mirrors wx's
`show_advanced_options_handler()` plus the `show_display_delay_ctrls()` /
`show_ffp_ctrls()` / `show_output_levels_ctrls()` helpers it calls, gating:
the Profiling tab's profile-type/black-point-compensation row; the
Calibration tab's black-luminance row; the Display & Instrument tab's
display-update-delay and display-settle-time-multiplier override rows (also
gated on a non-"Untethered" display and, for the settle-time row,
`argyll.version >= "1.7"`); the flash-field-pattern-insertion row (also gated
on the display being a Prisma/Resolve/madVR pattern generator); and the
output-levels row (also gated on the display not being madVR/Untethered).

Porting this also meant filling in wx's `show_trc_controls()` /
`show_observer_ctrl()`, which the Calibration tab's TRC-selection-dependent
rows had never had (Stage 3 always showed them regardless of the selected
TRC row): `_apply_trc_mode()` now shows the gamma text/type fields for the
custom row (7) unconditionally but only for the two typed-gamma rows (1, 4)
when advanced options are on; the ambient-adjustment row for the two fixed
Rec.709/SMPTE-240M rows or any row when advanced; the black-output-offset
slider for the custom row or any row when advanced; the black-point-correction
slider only when advanced (its wx counterpart is also gated on a manual/auto
toggle this Qt port doesn't have, so the slider is always treated as manual);
and the calibration-speed row for any row but "as measured", independent of
advanced options — a real pre-existing gap (not an advanced-options one),
since Stage 3 had this row always visible. `_update_observer_visibility()`
(replacing the "not reproduced" note left in Session 3's colorimeter-
correction port) shows the observer row when interactive-adjustment or a TRC
is set, advanced options are on, and the instrument supports a non-default
observer, wired into the same handlers wx calls it from (TRC change, any
checkbox toggle, comport/CCMX changes) plus the menu toggle itself and
`update_controls()`.

Not reproduced, because the controls themselves don't exist in this Qt port
yet (see the "Deferred" list above): the testchart-patch-sequence row and
gamap button (Profiling tab), the whitepoint colour-temperature-locus row and
the black-point-correction auto-checkbox/rate sub-controls (Calibration tab),
and the 3D LUT gamut-mapping / apply-cal-on-create controls. 14 new
regression tests in `tests/test_ui_main_window.py` (122 total, up from 108),
each setting every config key its assertions depend on explicitly and calling
the `_update_*` method directly rather than relying on `QAction.setChecked` to
detect a change — a real flakiness trap this session hit and fixed: `setcfg()`
only mutates the in-memory `CFG` singleton, or a value an earlier test left
behind (this test file has no per-test config reset beyond `initcfg()`,
which doesn't clear already-set in-memory keys) survives into the next test,
and a `setChecked(True)` that finds the action already checked from such a
leak is a silent no-op (Qt only emits `toggled` on an actual state change),
leaving stale visibility behind.

**Session 9 (Profiling tab: testchart chooser, patch controls, profile-name
tokens, 2026-07-08/09).** Picked from the "Remaining gaps" list: the
Profiling tab's remaining functional controls (3D LUT tab deferred as its own,
larger follow-up — its HDR/gamut-mapping/encoding sub-controls are a
comparably-sized slice on their own). New toolkit-neutral module
`DisplayCAL/profile_name.py` ports `MainFrame.create_profile_name` (the full
`%`-placeholder expansion), `check_profile_name`/the sanitizing fallback in
`profile_name_ctrl_handler`, `get_testchart_names`, the auto-optimize
patch-count/profile-type-nudge math from `testchart_patches_amount_ctrl_handler`,
`load_testchart_from_file`, and the estimated-measurement-time computation from
`wx_report_frame.ReportFrame.update_estimated_measurement_time`. Wired in
`main_window.py`: testchart chooser combo + browse button (validates
`.ti1`/`.ti3`/`.icc`/`.icm`, the last needing an embedded TI3), the
auto-optimize slider + computed patch count + patch-sequence combo (gated by
`show_advanced_options`, joining `gamap_btn` in that gating) + estimated
measurement-time label, and the profile-name live preview + placeholder-legend
info button + save-path picker. `gamap_btn` (opens wx's separate `GamapFrame`)
and `create_testchart_btn` (opens wx's separate `TestchartEditor`) show a
not-yet-available notice, matching the CCXX-info-button precedent — neither
tool window is ported.

Also added the Stage-0-deferred settings getters this needed
(`get_trc`/`get_trc_type`/`get_whitepoint`/`get_whitepoint_locus`/
`get_luminance`/`get_black_luminance`/`get_ambient`/`get_black_output_offset`/
`get_black_point_correction`/`get_calibration_quality`/`get_profile_type`),
and restored `profile_type_ctrl`'s side effects (`gamap_btn` enabled only for
LUT types, black-point-compensation nudged to the type's usual default on
first entering a category, profile quality locked to "high" for the two
gamma-only types) that Stage 3 had never wired — a real pre-existing gap, not
new deferred scope. Fixed a latent bug found while touching this exact row:
`profile_type_ctrl` was seeded straight from `PROFILE_TYPES`' label *keys*
(e.g. `"profile.type.lut_matrix.xyz"`) without `lang.getstr()`, so it showed
raw translation keys instead of real labels.

Not reproduced (documented in `profile_name.py`'s module docstring): the
CCXX-testchart-recommendation confirm dialog
(`check_testchart_patches_amount`), `set_default_testchart`'s testchart reset
on profile-type category change (`TESTCHART_DEFAULTS` only ever resolves to
`"auto"` in this codebase, so the effect is narrow), and the testchart-editor
live-refresh side effect of `set_testchart` (no editor to refresh). 20 new
regression tests in `tests/test_ui_main_window.py` (142 total, up from 122)
plus 46 in a new `tests/test_profile_name.py` for the pure module. Hit two
more instances of the `config.CFG`-leaks-between-tests trap (this time
leaking *out* of a test into unrelated ones): a test that loaded the bundled
`ccxx.ti1` testchart left `testchart.file` pointed at it, which flips
`config.is_ccxx_testchart()` for every later test in the session and broke
two already-passing action-button tests; switched that test to a
non-CCXX-named bundled testchart plus an explicit reset. Separately, found and
fixed a real (if narrow) accessibility bug while screenshot-verifying the
result in the live app: the tab bar's `QToolButton`s were wired to `clicked`,
but macOS's `AXPress` action (used by VoiceOver and by UI-automation tooling)
toggles a checkable button's state directly without necessarily emitting
`clicked`, leaving a tab visually checked but the stack not switched;
reconnected to `toggled` (guarded to only act when becoming checked) instead,
which fires for both.

**Session 10 (3D LUT tab: TRC/HDR/content-colorspace/gamut-mapping/encoding,
2026-07-09).** Closed the "Remaining gaps" item deferred since Session 9: the
3D LUT tab's full functional control set from `main.xrc`'s
`lut3d_settings_panel`. The Stage-3 placeholder (`lut3d_apply_trc_cb` /
`lut3d_apply_black_offset_cb`) had invented two checkboxes that don't exist in
`main.xrc` at all — removed and replaced with the real control set: input
colorspace, the combined TRC/gamma/gamma-type/HDR-peak-luminance row, the HDR
preserve-luminance/-saturation and preserve-hue sliders, mastering
black/peak-luminance + roll-off diffuse-white readout + alternate-clip
checkbox, HLG ambient luminance + system-gamma readout, the content-colorspace
combo and its 4x2 primaries editor grid, black output offset, apply-calibration
checkbox, gamut-mapping-mode radios, format + madVR HDR-display sub-mode,
encoding input/output, size, and bitdepth in/out. New toolkit-neutral
`DisplayCAL/lut3d_settings.py` ports the logic from wx's `LUT3DMixin`
(`wx_lut_3d_frame.py`, shared between the standalone `LUT3DFrame` tool window
and this embedded tab) specialized for the tab's fixed context
(`isinstance(self, LUT3DFrame)` always False, `hasattr(self, "lut3d_create_cb")`
always True): TRC combo selection <-> config mapping (including its
self-correcting `"3dlut.trc"` rewrites), the full `lut3d_show_trc_controls`
visibility cascade as a `Lut3dTrcVisibility` dataclass, BT.2390 diffuse-white
and HLG system-gamma readouts (reusing `colormath.BT2390`/`colormath.HLG`
directly), content-colorspace primaries lookup/resolution, 3D LUT size
snapping, and the format-change cascade (`lut3d_format_ctrl_handler`'s
encoding/size/bitdepth overrides per format). `update_lut3d_controls` gained
its own re-entrancy guard (mirroring
`update_colorimeter_correction_matrix_ctrl_items`) so any control's handler
can call it directly for a full, safe re-sync after an interdependent config
change, rather than threading partial updates through every call site.

Not reproduced (documented in `lut3d_settings.py`'s module docstring): the
`XYZbpout` (last measured/loaded profile's black point) factor in the
black-output-offset row's visibility, treated as always `[0, 0, 0]` (its value
before any profile has been measured) so that visibility reduces to just
`3dlut.create`. Actually creating a 3D LUT (`lut3d_create_handler`,
`lut3d_create_btn` wasn't wired into the button bar at all yet) was left to
the "worker-driven Argyll execution" deferral -- closed in a later session,
see Stage 5's "3D LUT creation" entry below (which also corrects this
paragraph's original claim that black-point-compensation / relative-
colorimetric-rendering-intent confirmation dialogs gate creation itself; they
don't). 50 new tests in `tests/test_lut3d_settings.py` for the
pure module, plus 21 new regression tests in `tests/test_ui_main_window.py`
(163 total, up from 142). Verified visually via offscreen `QWidget.grab()`
screenshots (SMPTE 2084 roll-off with a preset colorspace, and again with a
hand-edited "Custom" one showing the primaries grid).

**Session 11 (wire testchart editor / report window / CCXX import-upload into
MainWindow, 2026-07-09).** Follow-up on the "wire already-ported standalone
tool windows" item left over from Session 9's `gamap_btn`/`create_testchart_btn`
not-yet-available notices: `create_testchart_btn()` now opens
`TestchartEditorWindow()` instead of the stub notice; a new
`measurement_report_btn` opens `ReportWindow()` (its `edit_chart_requested`
signal reuses the same testchart editor instance; its `measure_requested`
signal still shows a not-yet-available notice, since generating a report is a
much larger, separate port — see the Stage 5+ measurement-report sub-slice ii
"Deferred" note); and a new Tools menu wires
`ImportController()`/`UploadController()` (from
`DisplayCAL.ui.colorimeter_correction_io`) for colorimeter-correction
import/upload. `_testchart_editor_window` / `_report_window` follow the same
lazily-created singleton pattern as `_gamap_window` (Session 12, below) and
`_install_profile_window` / `_profile_info_window`.

Also fixed a latent crash in `get_total_patches()` found while exercising the
newly-wired testchart editor without Argyll configured: when Argyll's version
couldn't be determined, `multi_bcc_steps` stayed `None` and
`adjust_gray_patches_count()` crashed comparing `None > 1`; now defaults to
`0`, matching pre-1.6 Argyll behavior (fixed at the source, so the still-
shipping wx path gets the fix too). 88 new/expanded regression tests in
`tests/test_ui_main_window.py`.

**Session 12 (GamapFrame port: gamap_btn, 2026-07-09).** Picked from the
"Remaining gaps" list (maintainer's choice, over 3D LUT creation / measurement
report generation / the small whitepoint-locus advanced-options gap). Ports
wx's `GamapFrame` (`display_cal.py`, `xrc/gamap.xrc`), the standalone window
opened from the Profiling tab's "Advanced..." button, configuring CIECAM02
gamut mapping (source profile, perceptual/saturation intents, source/
destination viewing conditions, default rendering intent) and B2A quality
(low-quality vs. hi-res PCS-to-device tables, hi-res size, smoothing).

New toolkit-neutral `DisplayCAL/gamap_settings.py` holds the Argyll-version-
gated item lists (`viewcond_items`, `intent_items`, mirroring
`GamapFrame.setup_language`'s `VIEWCONDS`/`INTENTS` filtering) and the
`compute_bpc_enabled` predicate (`MainFrame.update_bpc`'s `enable_bpc` check),
shared between the new `DisplayCAL/ui/gamap_window.py` (`GamapWindow
(BaseWindow)`) and `MainWindow` itself. Unlike earlier ported windows,
`GamapWindow` uses Qt signals (`profile_settings_changed`, `b2a_quality_changed`)
in place of wx's direct `self.Parent` attribute access
(`profile_settings_changed()` / `update_bpc()` / `lut3d_update_b2a_controls()`),
since a signal is the idiomatic Qt equivalent and keeps the window
independently testable. `MainWindow._gamap_btn_handler` reuses a single
instance like `_report_window` / `_testchart_editor_window`; the two signals
connect to `_mark_profile_settings_changed` and a new
`_on_gamap_b2a_quality_changed` (calling `_update_bpc()` +
`_update_lut3d_b2a_controls()`, the latter already existing since Session 10).
The wx `hasattr(self.Parent, "lut3dframe")` branch (a separate standalone 3D
LUT tool window) has no Qt equivalent since the 3D LUT tab is embedded
directly in `MainWindow`.

Also wired `MainWindow._update_bpc()` (a port of `MainFrame.update_bpc`,
never ported in Stage 3 despite the checkbox existing since day one — a real
pre-existing gap, not new deferred scope) into `update_profile_controls()`
(initial population) and `_profile_type_ctrl_changed()` (replacing its
Session-9 ad hoc `setChecked` nudge with a `setcfg` nudge + `_update_bpc()`
recompute, matching wx's `profile_type_ctrl_handler` exactly: nudge the
config default, then let `update_bpc()` decide the real enabled/checked
state).

**Fixed a latent wx bug found while porting** (in both `display_cal.py` and
this Qt port, see `gamap_window.py`'s module docstring): `GamapFrame
.gamap_out_viewcond_handler` only ever called `setcfg("gamap_out_viewcond",
...)` from *inside* the nondisplay-viewcond confirmation branch, so picking
any regular (non-warning) destination viewing condition from the dropdown —
e.g. "Monitor in typical work environment" — never persisted to config at
all. Fixed at the source (dedented the `setcfg` / change-notification out of
the nested `if`) so the still-shipping wx path gets the fix too. Note:
`config.VALID_VALUES["gamap_out_viewcond"]` only allows `mt`/`mb`/`md`/`jm`/
`jd` (a separate, pre-existing constraint unrelated to this bug), so the
nondisplay codes the confirmation dialog warns about can still never actually
round-trip through `getcfg` even after confirming — not a regression, just a
pre-existing quirk of that config key, left alone here.

20 new tests in `tests/test_ui_gamap_window.py` (headless, exercising the B2A
and CIECAM02 checkbox cascades, viewcond persistence including the bug-fix
regression test, and the nondisplay confirm/cancel dialog) plus 14 in the new
`tests/test_gamap_settings.py` for the pure module.

### Stage 4 — Calibrate / measure / profile actions — **DONE (orchestration)**

Wire the action buttons to the Stage-2 flow, running the measure-frame
subprocess on a `QThread` (per README pattern #3).

**Landed:** the calibrate / calibrate&profile / profile buttons in
`DisplayCAL/ui/main_window.py` now drive the Stage-2 `MeasurementFlow`, covered
by the expanded `tests/test_ui_main_window.py` (48 tests, headless offscreen):

- A `MeasurementAction` enum names the three workflows the buttons stage.
- `begin_measurement()` — the Qt port of `MainFrame.setup_measurement`: it
  `writecfg()`s, stages the driver through `flow.plan_measurement()`, and
  dispatches on the returned `PresentationMode`:
  - `CALL_PENDING` (virtual display / dry run) -> `call_pending_function()`;
  - `SHOW_FRAME` (macOS / Windows / frozen / Wayland-patch) -> shows the
    in-process Qt `MeasureFrame` as a child and routes its `measure_requested`
    signal to `call_pending_function()`;
  - `SUBPROCESS` -> runs the measure frame as a separate process on
    `_MeasureframeSubprocessThread(QThread)` and acts on the exit code via
    `interpret_measureframe_result()` (`config.initcfg()` + repopulate on
    change, run the pending driver on `255`, restore + surface stderr otherwise).
- `call_pending_function()` — the window-layer side of the Stage-2 pending-
  function machine: hides / blanks the measure frame, then runs the staged
  driver after the 100 ms `QTimer.singleShot` deferral (the wx `CallLater`), via
  an overridable `_defer` seam.
- The committed run is exposed as the `MainWindow.measurement_requested`
  `Signal(MeasurementAction)`, and the main window is restored around it.

**Deferred to Stage 5 (the wx-heavy worker layer):** the actual Argyll execution
behind `measurement_requested` — `just_calibrate` / `just_measure` /
`just_profile` / `calibrate_and_profile` / `profile_finish` driving
`worker.Worker.start`, which in wx owns the `ProgressDialog`, the interactive
`DisplayAdjustmentFrame` / `SimpleTerminal`, and the `BetterWindowDisabler`.
Those windows are Pile-2 glue rebuilt natively before the signal is connected.
Also deferred: the pattern-generator setup dialogs (`patterngenerator_kind()`
already names the branch) and the pre-flight confirmation / overwrite dialogs
(`check_show_macos_bugs_warning`, the fast-matrix-shaper choice, `check_overwrite`).

### Stage 5 — Worker execution layer (make the Stage-4 buttons run)

Connect the Stage-4 `measurement_requested` signal to the actual Argyll
execution so the calibrate / calibrate&profile / profile buttons *run* something.
In wx this is `worker.Worker.start()` (worker.py:15705), which is the most
wx-entangled method in the codebase: it owns the `delayedresult` producer/consumer
threading, `wx.CallAfter`, `BetterWindowDisabler`, and constructs the wx
`ProgressDialog` (and, for interactive calibration, the `DisplayAdjustmentFrame`)
inside `progress_dlg_start()`. None of that can flip to Qt in one increment
without touching the still-shipping wx path, so this lands as sub-slices. The Qt
path drives the worker itself rather than routing through `worker.start()`.

**Sub-slice 5a — native Qt `ProgressDialog` — DONE.** `DisplayCAL/ui/progress_dialog.py`
(`ProgressDialog(QDialog)`), covered by `tests/test_ui_progress_dialog.py`
(17 tests, headless offscreen). It preserves the contract the flow depends on:
an indeterminate (`pulse`) and determinate (`set_progress`) mode over a
`QProgressBar`, elapsed / estimated-remaining read-outs (the maths factored into
the pure, unit-tested `format_elapsed` / `estimate_remaining`), optional cancel
and pause controls surfaced as the `cancelled` / `pause_toggled` signals, a
`keep_going` flag the driver polls (mirroring wx `Pulse` returning
`(keepGoing, skip)`), and position persistence to the shared `position.progress.*`
config keys. **Dropped** (matching the other tools' simplifications): the fancy
animated throbber (`AnimatedBitmap` / `get_bitmaps`), the looping sound effects
(`audio.Sound`), the gradient `BetterPyGauge`, and Windows taskbar-progress
integration.

**Key finding (drives the sub-slicing below):** the worker measurement engine is
*fully wx-event-loop-bound*, not just at the progress dialog. `Worker.start()`
uses `delayedresult` + `wx.CallAfter` for threading / consumer delivery;
`progress_handler` is ticked by the wx `ProgressDialog`'s `wx.Timer` and is
interleaved with `wx.GetApp()` / `wx.CallAfter` / `DisplayAdjustmentFrame`
calls; and mid-measurement, on the worker thread, the instrument handlers
(`check_instrument_place_on_screen`, `do_instrument_calibration`,
`instrument_place_on_screen`, `instrument_reposition_sensor`) construct wx
dialogs (`self.progress_wnd.dlg = <wx dialog>`) and call `wx.CallLater` /
`wx.GetApp()` even on the colorimeter path. The `--qt` process is a pure
`QApplication` with no wx.App / `wx.MainLoop`, so none of that ticks. Making the
Qt buttons run therefore means porting the *driving* and the *instrument
prompts* to Qt (the maintainer chose this "full Qt port" over a wx/Qt
event-loop bridge).

**Sub-slice 5b-i — pure progress parser — DONE.** `DisplayCAL/ui/worker_runner.py`
`parse_progress()`, covered by `tests/test_ui_worker_runner.py` (10 tests, no
display). The toolkit-neutral percentage extraction lifted out of
`Worker.progress_handler` (the `NN%` / `Patch N of M` / `Added N/M` / `It N:`
shapes), which the wx handler cannot share as-is because the rest of it needs a
running wx app. This is what the Qt progress poll will call.

**Sub-slice 5b-ii — QThread worker driver + thread-safe progress adapter — DONE.**
`DisplayCAL/ui/worker_runner.py` gains `_ProducerThread(QThread)`,
`ProgressAdapter(QObject)` and `WorkerRunController(QObject)`, covered by
`tests/test_ui_worker_runner.py` (now 19 tests, headless offscreen with a fake
worker). `_ProducerThread` runs a worker producer (`worker.measure`) off the GUI
thread and delivers its result (bool or Exception) via a signal. `ProgressAdapter`
is the thread-safe stand-in for the wx `progress_wnd`: it returns
`(keepGoing, skip)` synchronously from plain flags (safe to read from the worker
thread) and marshals every GUI update onto the GUI thread through queued signals,
so the worker thread never touches the `QProgressBar`. `WorkerRunController`
installs the adapter, sets the non-interactive `Worker.start()` state subset,
shows the 5a `ProgressDialog`, polls the worker output buffers on a GUI-thread
`QTimer` through `parse_progress()`, and calls the consumer on the GUI thread on
completion; the dialog's `cancelled` / `pause_toggled` signals drive
`abort_subprocess()` / the adapter pause flag.

Now wired to `MainWindow.measurement_requested` (see sub-slice 5b-iv below).

**Sub-slice 5b-iii — Qt instrument-prompt dialogs — DONE.** The mid-measurement
prompts the worker pops on the measurement thread (place instrument on
screen/spot, sensor self-calibration, reposition sensor, ambient single
measurement) previously built a wx `ConfirmDialog` inline and blocked the
worker thread on `ShowModal()`. Those four sites (`instrument_place_on_screen`,
`do_instrument_calibration`, `instrument_reposition_sensor`,
`do_single_measurement`) now route through a new toolkit-neutral
`Worker._prompt_confirm(msg, ok, cancel, icon)` seam: if `progress_wnd` exposes
a callable `confirm` (the Qt adapter) it is used, otherwise the exact wx
`ConfirmDialog` fallback runs, so the shipping wx path is byte-for-byte
unchanged. On the Qt side, `ProgressAdapter.confirm()` is called from the worker
thread, marshals a `_ConfirmRequest` to the GUI thread via a queued signal,
shows a `QMessageBox`, and blocks the worker thread on a `threading.Event` until
the user answers, reproducing the modal `ShowModal()` contract. The
`QMessageBox` construction is isolated in `ProgressAdapter._ask()` so the
blocking round-trip is unit-testable headless without a real modal loop.
`abort_subprocess`'s confirm-cancel dialog is left on the wx path (the Qt
controller only ever calls `abort_subprocess(confirm=False)`).

**Sub-slice 5b-iv — wire `measurement_requested` to the worker — DONE.**
`MainWindow.__init__` connects `measurement_requested` to
`_on_measurement_requested`, which drives the Argyll worker through a lazily
created `WorkerRunController` (over a Qt `ProgressDialog`). The `PROFILE` action
runs the characterization path (`_run_profile_measurement`), a Qt port of the
non-interactive setup `MainFrame.just_profile` does before
`worker.start_measurement`: it sets `dispread_after_dispcal = False`, marks the
worker `interactive` only for an `Untethered` display, clears
`calibration.file.previous`, and calls `controller.run(worker.measure,
_on_measurement_finished, wkwargs={"apply_calibration": True}, ...)`.
`_on_measurement_finished` ports the error / incomplete branches of
`just_profile_finish` (a `QMessageBox` on an `Exception`, the
`profiling.incomplete` notice on a non-dry-run failure, a log line on success).
The signal stays public so other layers / tests still observe committed runs.
The `CALIBRATE` / `CALIBRATE_AND_PROFILE` actions need the interactive
`DisplayAdjustmentFrame` (5c) and surface a not-yet-available notice until then.

**Deferred from 5b-iv:** building the profile from the measurements (the
`colprof` stage `just_profile_finish` chains into via `start_profile_worker`;
landed as sub-slice 5d, below), the pre-flight `check_overwrite` /
`current_cal_choice` / macOS-bugs preflight dialogs, and verifying the run
end-to-end against a real colorimeter.

**Sub-slice 5c — interactive `DisplayAdjustmentFrame`.** Port
`wx_display_adjustment_frame.py::DisplayAdjustmentFrame` (the interactive
display-adjustment window shown during `worker.calibrate`), so the `CALIBRATE`
action's interactive path runs. This is the large Pile-2 interactive window the
calibrate flow needs (the profile path, 5b, does not), so like 5b it lands as
sub-slices.

**Sub-slice 5c-i — toolkit-neutral adjustment parser — DONE.**
`DisplayCAL/ui/display_adjustment.py` `parse_adjustment()`, covered by
`tests/test_ui_display_adjustment.py` (14 tests, no display). The interactive
window works by parsing the text `dispcal` streams while it measures, turning
each reading into gauge positions, target / current read-outs and an
in-tolerance check mark. That parsing — the regex extraction plus the gauge /
tolerance maths in `DisplayAdjustmentFrame.parse_txt` — is toolkit-neutral, but
in wx it is interleaved with `Freeze`/`Thaw`, `SetValue` and check-mark
show/hide on live widgets, so it cannot be reused as-is (the same reason
`worker_runner.parse_progress` was lifted out of the progress handler for the
non-interactive path). `parse_adjustment(txt, ctx)` is the pure port: it takes a
`dispcal` chunk plus an `AdjustmentContext` (the per-page state wx keeps on the
frame — `target_br` / `initial_br` / `target_bl`), updates that context in place,
and returns an `AdjustmentReadings` describing the gauges (`L`/`R`/`G`/`B`
needle positions), the per-metric labels (`luminance` / `black_level` / `rgb` /
`white_point` / `black_point`, each with an `in_tolerance` flag), the measuring
indicator, and the `menu` / `measuring` phase transition. Tested against real
`dispcal` interactive output (captured in the wx frame's own test fixtures)
across every page type and both LCD / CRT measurement modes.

**Sub-slice 5c-ii — Qt `DisplayAdjustmentFrame` widget — DONE.**
`DisplayCAL/ui/display_adjustment_window.py` (`DisplayAdjustmentWindow(BaseWindow)`
plus a private `_AdjustmentPage(QWidget)`), covered by
`tests/test_ui_display_adjustment_window.py` (19 tests, headless offscreen). It
builds the five adjustment pages (black level / white point / white level /
black point / check-all) — each an `_AdjustmentPage` holding its own
`AdjustmentContext`, gauges (`QProgressBar`) and read-out labels (a label + a
checkmark icon) — behind an icon-only `QToolButton` selector column (the Qt
stand-in for the wx `FlatImageBook` left tab strip). `parse_output(txt)` /
`write(txt)` is the `parse_txt` port: it runs each `dispcal` chunk through the
5c-i `parse_adjustment()` and renders the returned `AdjustmentReadings` onto the
current page (gauge values, label text, green + checkmark when in tolerance,
indicator dot), then applies the menu / measuring **phase** transitions to the
start-stop / continue buttons and `is_measuring` / `is_busy` state. `setup()`
ports `_setup`'s mode-dependent page enabling (LCD disables the black pages,
selects white point; CRT selects black level when a black luminance is set) and
the calibration-button label (`calibration.start` / `.skip` / `finish`), and
swaps the CRT/LCD icons. The window is worker-agnostic: instead of calling
`worker.safe_send` it emits the key to send (`" "` / `"1"`..`"5"` / `"7"` /
`"8"` / raw menu key) on the `send_requested` signal, and `pulse()` /
`UpdateProgress()` / `UpdatePulse()` implement the `progress_wnd` status contract.
Geometry shares the `position.progress.*` keys with the progress window. **Dropped**
(matching the other ports): the animated indicator (now a static dot), the
gradient `PyGauge` (now a plain `QProgressBar`), and the looping sound (now a
single best-effort beep behind an overridable `_play_sound` seam).

**Sub-slice 5c-iii — wire the calibrate path — DONE.** `DisplayCAL/ui/worker_runner.py`
gains `_AdjustmentTerminal(QObject)` and `AdjustmentController(QObject)`, covered
by the expanded `tests/test_ui_worker_runner.py` (30 tests, headless offscreen
with a fake worker + fake window), and `MainWindow` now drives them. The
interactive calibration path is the Qt replacement for the
`interactive_frame="adjust"` branch of `Worker.start()`, which is not reachable
from the pure-Qt app (no wx event loop):

- `AdjustmentController` runs `Worker.calibrate` on the 5b `_ProducerThread` with
  the 5c-ii `DisplayAdjustmentWindow` installed as both `worker.terminal` and
  `worker.progress_wnd` (through `_AdjustmentTerminal`), and connects the window's
  `send_requested` keys to `worker.safe_send`. It sets the interactive worker
  state `Worker.start` would (`interactive` / `interactive_frame="adjust"` /
  pauseable / abort flags) and installs the producer thread as `worker.thread`
  (given an `is_alive()` alias) so `exec_cmd` attaches the interactive terminal
  to the output stream.
- `_AdjustmentTerminal` is the thread-safe stand-in for the one wx frame that is
  both the `terminal` (its `write` marshals each `dispcal` chunk to
  `window.parse_output` on the GUI thread) and the `progress_wnd` (`Pulse` /
  `UpdateProgress` / `SetTitle` / `reset` / `Show` marshalled likewise, the
  `keepGoing` / `skip` flags read synchronously from any thread, and `confirm`
  reproducing the blocking `ConfirmDialog.ShowModal` for the mid-measurement
  instrument prompts, reusing the 5b-iii `_ConfirmRequest` round-trip).
- `MainWindow._run_calibration_measurement` ports the setup `just_calibrate` /
  `calibrate_and_profile` do: it sets `calibration.continue_next` (and, for
  calibrate&profile, `dispcal_create_fast_matrix_shaper=False` /
  `dispread_after_dispcal=True`), and dispatches on whether interactive display
  adjustment is on (and this is not a calibration update) — interactive runs go
  through the `AdjustmentController`, non-interactive ones through the 5a
  `ProgressDialog` / `WorkerRunController`. `_on_calibration_finished` ports the
  error / incomplete branches of `just_calibrate_finish` and, on a successful
  calibrate&profile, chains the characterization measurement
  (`_run_profile_measurement`). This replaces the 5b-iv not-yet-available notice.

**Deferred from 5c-iii:** building the profile from a calibrate&profile run (the
`colprof` stage, shared with the 5b-iv profile deferral; landed as sub-slice 5d,
below), the calibration success side effects (`load_cal` + the
`calibration.complete` dialog + fast-matrix-shaper profile), the wx
swap-to-progress-dialog once adjustment ends (the adjustment window stays up
showing status pulses through the curve measurement), the `abort_subprocess`
confirm-cancel path (still on the wx `delayedresult` seam, as in 5b-iii), and
verifying end-to-end against a real colorimeter.

**Sub-slice 5d — build the profile from measurements (the `colprof` stage) —
DONE (2026-07-09).** Picked from the "Remaining gaps" list (maintainer's choice,
over 3D LUT creation / measurement report generation). Closes the 5b-iv/5c-iii
deferral: the `PROFILE` and `CALIBRATE_AND_PROFILE` action buttons now actually
build a `.icc` file, not just run the measurement.

New toolkit-neutral `DisplayCAL/profile_finish.py` (mirroring the
`profile_install.py`/`main_settings.py` precedent) holds the pure pieces of
`MainFrame.start_profile_worker` / `profile_finish`: `resolve_profile_path()`
(the default `profile.save_path`/`profile.name.expanded` derivation),
`validate_built_profile()` (loads and checks the built profile is an `mntr`/
`RGB` display profile, raising `ProfileFinishInvalidError` /
`ProfileFinishNotDisplayError` in place of wx's inline `InfoDialog`+return
branches), `format_completion_extra()` (the self-check dE / gamut coverage /
gamut volume summary read from the profile's `meta` tag), and
`sync_calibration_file_config()` (points `calibration.file` /
`3dlut.output.profile` / `measurement_report.output_profile` at the new
profile). `MainWindow._on_measurement_finished` (the consumer of both the
`PROFILE` action's direct measurement and the `CALIBRATE_AND_PROFILE` chain's
characterization measurement) now calls `_build_profile_from_measurement()` on
success, which copies the working TI3 (`worker.wrapup(copy=True, remove=False,
ext_filter=[".ti3"])`) and runs `worker.create_profile` through the same
`WorkerRunController` used for the measurement itself; `_on_profile_build_finished`
validates the result via `profile_finish`, updates the calibration/profile combo,
and offers to install the new profile via a `QMessageBox.question` that, on Yes,
reuses the already-ported `InstallProfileWindow` (`install_profile_btn_handler`)
rather than reproducing wx's install dialog.

**Dropped / simplified versus `profile_finish`** (documented in
`profile_finish.py`'s module docstring): the big `ConfirmDialog` with its
share-profile button (dead upstream anyway, see Stage 5+ below) and
calibration-preview / show-LUT / show-profile-info checkboxes; the
install-scope radio buttons and Windows profile-loader `getcfg` round trip
(the reused `InstallProfileWindow` already offers scope, gated the same way);
the automatic 3D LUT creation offer (`install_3dlut`, `lut3d_create_handler`
isn't wired yet either, see `lut3d_settings.py`'s deferred item); the
measurement-file sanity-check confirmation dialog
(`measurement_file_check_confirm`) that gates wx's TI3 copy (always proceeds,
matching that dialog's "confirm" branch); and the `options_dispcal and
options_colprof` branch of `profile_finish`, which calls the giant
`load_cal_handler` to reload every settings control from the profile's
embedded cal curves (`sync_calibration_file_config` always takes the simpler
"just point at the new file" branch instead). Not reproduced for a
calibrate-only run (`just_calibrate_finish`, a different wx method from the
`calibrate_and_profile_finish` this sub-slice mirrors):
`update_calibration_file_ctrl()`, the `profile.update`/fast-matrix-shaper auto
quick-profile chain, and the TRC-branch `load_cal` + completion dialog — a
pre-existing gap, not new deferred scope.

10 new tests in `tests/test_profile_finish.py` for the pure module, plus 13
new/updated regression tests in `tests/test_ui_main_window.py` (182 total).

**Sub-slice 5e — pre-flight confirmation / overwrite dialogs — DONE (2026-07-09).**
Picked from the "Remaining gaps" list (maintainer's choice, over 3D LUT creation
and measurement report generation). Before this slice the three action buttons
ran straight into `begin_measurement` with no guard rails at all, so a real run
could silently overwrite an existing `.cal`/`.ti3`/profile file. Ports wx's
`check_overwrite`, `check_show_macos_bugs_warning` and `current_cal_choice`
(`display_cal.py`) into every action button's guard chain.

New toolkit-neutral `DisplayCAL/preflight_checks.py` (mirroring the
`profile_finish.py` precedent): `resolve_overwrite_path()` (the destination-path
derivation `check_overwrite` tests for existence), `macos_bugs_warning_applicable()`
/ `should_warn_calibration_bugs()` / `should_warn_profile_bugs()` (the
platform/config predicates gating the two macOS-bugs warnings), and
`resolve_cal_choice_info()` / `compute_cal_choice_result()` (the message/checkbox
setup and post-dialog branch logic behind `current_cal_choice`, split into a
pre-dialog `CalChoiceInfo` and a post-dialog `CalChoiceResult` so the wx and Qt
dialogs can share both halves without either owning the other's widgets). The wx
`MainFrame` now delegates to all of these (verified against the full
`test_display_cal.py` suite, unchanged); the actual `ConfirmDialog` construction
and `self.reset_cal()` call stay in wx, matching the `profile_finish.py` /
`profile_install.py` split between pure logic and toolkit-owned dialogs.

`MainWindow` gained `_check_overwrite()` (a `QMessageBox.warning` Ok/Cancel),
`_check_show_macos_bugs_warning()` (two sequential `QMessageBox.warning`
Yes/No/Cancel prompts, applying the same config resets wx does on "Yes" --
`black_luminance_ctrl`/`black_point_correction_ctrl` for the calibration
warning, `profile_type_ctrl`/`update_profile_controls()` for the profile
warning), `_current_cal_choice()` (a new `_CalChoiceDialog(QDialog)` with the
"embed calibration" / "use linear instead" checkboxes, since a stock
`QMessageBox` only supports one), and `_reset_video_lut()` (a synchronous
`worker.prepare_dispwin`/`exec_cmd` port of `MainFrame.reset_cal`, minus the
embedded curve-viewer refresh the Qt main window doesn't have). All three
action-button handlers now run the full wx guard chain before staging a
measurement; `profile_btn_handler`'s `current_cal_choice()` result is stashed in
a new `_pending_apply_calibration` attribute for `_run_profile_measurement` to
thread into `worker.measure(apply_calibration=...)` once the run actually
starts (previously hardcoded to `True`), mirroring how wx threads the same value
through `setup_measurement(self.just_profile, apply_calibration)`.

**Dropped / deferred versus the wx handlers:** the `silent=True`
`current_cal_choice` call path (only reachable from an auto-retry event this Qt
port doesn't have yet, see `measure_auto` -- not ported); and the
success/failure `InfoDialog` pair `MainFrame.install_cal` shows
(`_reset_video_lut` runs silently). (The fast-matrix-shaper/profile-update
choice dialog `calibrate_btn_handler` shows first was itself deferred here but
ported in a later session -- see below.)

26 new tests in `tests/test_preflight_checks.py` for the pure module, plus 17
new/updated regression tests in `tests/test_ui_main_window.py` (198 total).
Hit the same test-modal-hang trap `test_ui_main_window.py`'s own history
already warns about (see the memory note "Qt test modal-hang gotcha"): the one
existing test that clicks the action buttons directly (`test_action_button_dry
_run_emits_request`) started hanging once `profile_btn_handler` began showing a
real modal `_CalChoiceDialog` mid-click; fixed with a new `_stub_preflight_checks`
fixture applied there, alongside dedicated tests for every new pre-flight code
path (each answering its own dialog explicitly rather than letting one hang).

**Fast-matrix-shaper/profile-update choice dialog:** closed the deferral noted
above. Added `resolve_fast_matrix_shaper_choice_info()` /
`apply_fast_matrix_shaper_choice()` to `preflight_checks.py`, a faithful port of
`calibrate_btn_handler`'s guard (`not profile.update and (not calibration.update
or is_profile()) and trc`) and its `update_profile` message/button-label
branch, minus the wx `CustomEvent` half of the guard (no Qt caller of
`calibrate_btn_handler` is ever anything but a real click, so that clause is
always true here). `MainWindow._fast_matrix_shaper_choice()` builds the 3-button
`QMessageBox` (`QMessageBox.AcceptRole`/`ActionRole`/`RejectRole`, since a stock
`QMessageBox` has no custom-labeled third button otherwise) mirroring wx's
`ConfirmDialog(ok=..., alt=lang.getstr("button.calibrate"), cancel=...)`, and
`calibrate_btn_handler` now threads its result into
`self.worker.dispcal_create_fast_matrix_shaper` exactly like the wx handler
does, so a "create fast matrix shaper" / "update profile" choice now actually
reaches `worker.prepare_dispcal`'s `-o` flag (dispcal itself builds the profile
file during calibration; verified this doesn't require a separate `colprof`
step). The completion-chain gap noted here in an earlier draft (calibrate-only
runs not refreshing the calibration-file control or offering an install) was
closed in the next session, below.

**Calibrate-only completion chain — DONE (2026-07-09).** Closed the deferral
noted above: `_on_calibration_finished` now ports the rest of
`just_calibrate_finish` for a calibrate-only run. `update_calibration_file_ctrl()`
always refreshes first, then either the fast-matrix-shaper/`profile.update`
profile (already built by `dispcal` itself, per the previous session) is
validated and offered for install via `_on_profile_build_finished` (which
gained an optional `success_msg` so this path can say "calibration.complete"
instead of the colprof path's "profiling.complete", matching wx's two
`profile_finish` call sites), or -- the plain-calibrate case, `elif
getcfg("trc")` -- the new calibration is loaded onto the video card gamma
table via a new `_load_cal()` (a port of `MainFrame.load_cal`, minus the
curve-viewer refresh, same silent pattern as `_reset_video_lut`) plus a
completion notice. 8 new tests in `tests/test_ui_main_window.py` (214 total).

**3D LUT creation (manual `lut3d_create_btn`) — DONE (2026-07-09).** Picked
from the "Remaining gaps" list (maintainer's choice, over measurement-report
edge cases and header-bar/tab-parity deferrals). Closes the "actually creating
a 3D LUT" item tracked since Session 10 above (and corrects that entry's
inaccurate claim of black-point-compensation / relative-colorimetric-
rendering-intent confirmation dialogs gating creation -- those
(`MainFrame.lut3d_check_bpc`, and the never-called
`check_3dlut_relcol_rendering_intent`) actually gate the BPC checkbox and
`3dlut.rendering_intent` combo's own handlers, not `lut3d_create_handler`).

`lut3d_settings.py` gains `resolve_create_trc_gamma()`,
`content_rgb_space_for_creation()` and `resolve_creation_whitepoint()`,
factoring out the two branches of `LUT3DMixin.lut3d_create_producer` with
real logic worth sharing/testing between the embedded tab and the standalone
3D LUT maker's own (independently written) `create_3dlut`; the rest of that
method is a flat, untestable config-to-kwarg mapping built inline by each
caller. `MainWindow.lut3d_create_btn_handler()` is the `MainFrame`-embedded
half of `LUT3DMixin.lut3d_create_handler` (`not isinstance(self,
LUT3DFrame)`): the input profile comes from `3dlut.input.profile` and the
output profile is the current calibration/profile selection
(`config.get_current_profile()`) -- this port has no abstract-profile picker
or standalone input/output combos like the standalone maker does. wx never
shows a save dialog for this button (only the standalone maker does): the
path comes from `Worker.lut3d_get_filename()`, with the same overwrite
confirmation the other action buttons use. Runs `worker.create_3dlut`
through the existing `WorkerRunController`. `_update_action_buttons()` now
hides the calibrate/profile buttons and shows `lut3d_create_btn` whenever the
3D LUT tab is active with manual creation (`not getcfg("3dlut.create")`),
mirroring `MainFrame.update_main_controls`.

**Dropped / deferred:** wx's success path chaining into `profile_finish` to
offer installing the created 3D LUT (a separate, larger feature covering
madVR/Prisma API install, ReShade folder detection, and the "copy to
location" flow) -- this port's completion is silent on success (matching the
standalone 3D LUT maker's own `_on_create_done`), reporting only errors. Also
not reproduced: the auto-chain creating a 3D LUT automatically after
profiling (`3dlut.create` when checked just hides the manual button today,
it doesn't yet trigger creation itself), and `MainFrame.lut3d_check_bpc`'s
warning offering to turn off profile black-point compensation when both it
and `3dlut.create` are enabled together. 16 new tests in
`tests/test_ui_main_window.py`; also caught and fixed a real test hazard in
passing (not a product bug): two new tests initially let a real
`Worker.lut3d_get_filename`-computed path reach `waccess`'s unmocked
filesystem probe, which via `tempfile.TemporaryFile` hung indefinitely in
this sandboxed environment and, once, left a stray `.cube` file next to the
checked-in test fixtures -- fixed by mocking `waccess` in those tests.

**Whitepoint colour-temperature-locus row — DONE (2026-07-09).** Picked from
the "Remaining gaps" list (maintainer's choice, over the 3D LUT install-offer
chain and `Worker.authenticate()`'s elevated-scope profile install). Closed
the small gap the module docstring had flagged since Session 8: wx's
`whitepoint_colortemp_locus_ctrl` (daylight/blackbody choice for the
color-temperature -> xy conversion) had no Qt equivalent at all.

`main_window.py` gained `whitepoint_colortemp_locus_label` /
`whitepoint_colortemp_locus_ctrl`, placed in the whitepoint row right after
the Kelvin spinbox, matching `main.xrc`'s widget order exactly (`whitepoint
_ctrl`, colortemp spinbox, locus label + combo, then x/y). `_apply_whitepoint
_mode()` (already the single choke point wx's `whitepoint_ctrl_handler` and
`show_advanced_options_handler` both drive through) now also gates this row:
visible for the "as measured" and "color temperature" modes, hidden for
"x,y chromaticity" (mirrors `whitepoint_ctrl_handler`'s `Hide()` in the
chromaticity branch), and only ever shown when `show_advanced_options` is on.
`get_whitepoint_locus()` (a Stage-0 deferral, previously hardcoded to always
return `"t"`) now reads the combo's selection (`"t"` daylight / `"T"`
blackbody), and a new `_whitepoint_locus_changed()` persists it to
`whitepoint.colortemp.locus`, both faithful ports of wx's
`get_whitepoint_locus` / `whitepoint_colortemp_locus_ctrl_handler`.
`update_calibration_controls()` repopulates the combo from config on load/
undo, matching wx's `SetSelection` via the `whitepoint_colortemp_loci_ba`
reverse map.

Not reproduced: `update_adjustment_controls`'s extra `not auto and do_cal`
gating condition on this same row, which belongs to the interactive
calibration-adjustment page (`DisplayAdjustmentWindow`, sub-slice 5c-ii) as a
separate, independently-scoped page, not this settings tab's row visibility.
3 new tests in `tests/test_ui_main_window.py` (245 total): value persistence
(both directions), the advanced-options/whitepoint-mode visibility gate, and
config-to-control repopulation.

**Fixed a latent shared `config.getcfg()` bug found while chasing an
unrelated pre-existing test failure** (`test_lut3d_create_btn_handler_missing
_input_profile_shows_error`, order-dependent under `pytest -n auto`, not
caused by the whitepoint-locus change above): `getcfg`'s path-correction
branch (`DisplayCAL/config.py`) gated on `name.endswith("file")`, intended to
catch keys like `calibration.file` / `testchart.file`, but the substring
`"file"` is also the last four letters of `"profile"` -- so it silently
caught every `"...profile"`-suffixed key too (`3dlut.input.profile`,
`3dlut.abstract.profile`, `3dlut.output.profile`,
`measurement_report.output_profile`, `measurement_report.devlink_profile`,
`measurement_report.simulation_profile`, `gamap_profile`,
`tc_precond_profile`). Whenever one of those was set to a path that doesn't
currently exist on disk, `getcfg` silently substituted the key's bundled
default instead of returning the stored (invalid) path -- so any "is this
profile missing?" check built on `getcfg` (in both the wx and Qt UIs, since
`config.py` is shared) could never actually observe a missing profile.
Narrowed the check to `name.endswith(".file")` (a real dot-delimited "file"
word), which still matches the two intended keys and no longer matches any
`"...profile"` key. Fixed at the source, so the still-shipping wx path gets
the fix too. 9 new regression tests in `tests/test_config.py` (parametrized
over all 8 affected keys plus a `calibration.file` control case proving the
intended behaviour is unchanged).

**Also fixed a pytest-xdist-only test-isolation flake** in
`tests/test_ui_main_window.py`'s `window` fixture: the four `*_has_info
_panel_text` tests bake `lang.getstr()` output into `QLabel`s at `MainWindow`
construction time, but called `lang.init()` from the test body, after
construction -- too late if this was the first `MainWindow` built in a given
`pytest-xdist` worker process (harmless in the normal single-process run,
where dozens of earlier tests already populate `lang.LDICT` first). Moved
`lang.init()` into the `window` fixture itself, ahead of construction, so
translations are always loaded regardless of worker/test order.

**3D LUT install-offer chain — DONE (2026-07-09).** Picked from the
"Remaining gaps" list (maintainer's choice, over `Worker.authenticate()`'s
elevated-scope profile install and the measurement-report edge cases).
Closes three related deferrals noted since the "3D LUT creation" and
"3D LUT tab" sessions above: `lut3d_create_btn_handler`'s completion was
silent on success instead of offering to install the result;
`3dlut.create` only hid the manual create button instead of actually
auto-chaining LUT creation after a profiling run; and
`MainFrame.lut3d_check_bpc`'s black-point-compensation warning had no Qt
equivalent at all.

`DisplayCAL/lut3d_settings.py` gains `install_via_copy()`, a faithful port
of the `copy_from_path` branch of `LUT3DMixin.lut3d_create_handler`
(`wx_lut_3d_frame.py:880-1009`, minus the dead `MasterEffect` sub-branch
guarded upstream by a hardcoded `use_mclut3d = False`): eeColor's 6
companion 1D-LUT files, and ReShade's install-layout detection (>=3.x
`reshade-shaders/{Textures,Shaders}` split, or <3.0's `ReShade.fx` --
following it if it's a symlink -- patched in place) plus writing a
templated `ColorLookupTable.fx` next to the copied texture. **Fixed a
latent bug found while porting** (in both `wx_lut_3d_frame.py` and this new
module): the <3.0 `ReShade.fx` patch ran `re.sub` with `str` patterns
against `reshade_fx`, which is `bytes` (`open(..., "rb")`) -- a `TypeError`
in real Python 3, so this branch could never have actually run without
crashing. Fixed at the source with `bytes` patterns, so the still-shipping
wx path gets the fix too (previously unreachable/untested since it needs an
actual pre-3.0 ReShade install with a non-symlinked `ReShade.fx` on disk).

`main_window.py`: `_on_lut3d_create_finished` now offers to install/copy a
successfully created 3D LUT via `_offer_install_3dlut()` (a port of the
3D-LUT branch of `MainFrame.profile_finish`, taken once the LUT file exists
on disk -- the OK-button label mirrors wx's install/save-as distinction).
Accepting routes through `_install_3dlut()` (a port of
`profile_finish_action`'s `install_3dlut_api` branch): the generic
copy-to-path and ReShade destinations actually install via
`lut3d_settings.install_via_copy()` behind a new
`_prompt_3dlut_copy_destination()` (a folder picker for ReShade, a save-file
dialog with the format's usual extension otherwise, reusing
`_check_overwrite()`); the madVR (via `madtpg`) and Prisma (its HTTP REST
API) destinations both install through the already-toolkit-neutral
`Worker.install_3dlut`, but reaching that point in wx needs the
still-unported `setup_patterngenerator` connection dialogs (the Prisma host
prompt with mDNS discovery, the madTPG connect-wait dialog) -- so, matching
the CCXX-info-button / elevated-install-scope precedent, this port shows a
not-yet-available notice for that branch instead of attempting an
unconfigured connection.

`3dlut.create` now really auto-chains: `_on_profile_build_finished` checks
it before showing the plain profile-install offer and, if set, calls the
new `_chain_3dlut_after_profile()` instead (matching wx, which never offers
to install the *profile* in this case, only the 3D LUT) -- if the LUT file
doesn't exist yet this creates it via the existing
`lut3d_create_btn_handler()` (identical validation/creation logic to the
manual button click, since wx uses the very same handler for both), which
chains into the install offer itself once creation succeeds; if the file
already exists, the offer is shown directly. wx picks the offer's message
(`"calibration_profiling.complete"` vs. falling back to
`"profiling.complete"`) from whether `3dlut.create` is checked at
*completion* time, not from which caller triggered creation, so
`_on_lut3d_create_finished` does the same rather than threading a
caller-specific message through.

New `_check_lut3d_bpc()` ports `MainFrame.lut3d_check_bpc`: wired into
`_check_handler` so both the black-point-compensation and `3dlut.create`
checkboxes trigger it (mirroring wx calling it from both handlers
unconditionally; the warning itself is a no-op unless both are currently
checked). Accepting turns BPC back off and re-runs `_update_bpc()`;
declining leaves both settings as chosen.

**Dropped / deferred versus wx:** the madVR/Prisma **API** install
destinations (see above -- needs `setup_patterngenerator`); the
share-profile button and calibration-preview / show-LUT / show-profile-info
checkboxes on the install-offer dialog (the same cuts
`_on_profile_build_finished`'s plain profile-install offer already makes);
and the `EDID`/instrument-ID auto-matching `check_overwrite` variants that
don't apply to 3D LUTs. 6 new tests in `tests/test_lut3d_settings.py` for
`install_via_copy()` (plain single-file, eeColor companions present/absent,
ReShade modern-shaders-folder, ReShade legacy-patch, ReShade no-existing-layout)
plus 26 new/updated regression tests in `tests/test_ui_main_window.py`.

### Stage 5+ — Reporting, colorimeter corrections, install/share

The remaining large features, each its own slice: measurement report
(`measurement_report*`), colorimeter-correction create/import/upload (extract
the 1736-line handler first), profile install/load-on-login, profile share.

**Measurement report sub-slice i — toolkit-neutral report helpers — DONE.**
`DisplayCAL/measurement_report.py` (a plain, Qt-free `DisplayCAL` module like
`main_settings.py`, so the still-shipping wx path can import it without pulling
in Qt), covered by `tests/test_measurement_report.py` (19 tests, no display).
It holds the pure string / number marshalling lifted out of
`MainFrame.measurement_report_handler` / `measurement_report_consumer`:
`default_report_filename` (the save-dialog default `.html` name + unsafe-char
sanitisation), `resolve_quantization_bits` (the `-Z <bits>` / `-Zbits` / `-E`->8
dispread-arg derivation), `quantize_gray` (the grayscale reference rescale to a
bit grid), and `report_trc_label` (the default-target -> `"BT.1886"` label). The
wx `MainFrame` now delegates to all four (byte-for-byte identical output, same
ruff profile), so the extraction thins the wx consumer today and hands the Qt
report layer a ready seam.

**Measurement report sub-slice ii — the Qt settings window — DONE.**
`DisplayCAL/ui/measurement_report.py` ports `wx_report_frame.ReportFrame` to a
`ReportWindow(BaseWindow)`, covered by `tests/test_ui_measurement_report.py` (13
headless tests under the offscreen `QApplication`). The wx `xrc/report.xrc`
widget set and top-to-bottom order are hand-built with native Qt widgets (the
custom wx `FileBrowseButtonWithHistory` becomes the same editable-combo +
browse-button `_FileBrowse` stand-in the Qt 3D LUT window uses). All the
config-driven behaviour is ported: the chart/reference loader + fields chooser,
the simulation / device-link / output profile controls with their `xicclu`
blackpoint lookups and profile-class validation (`set_profile`), the
unmodified / black-offset / BT.1886-style TRC block with gamma + gamma-type +
black-output-offset slider/spin (guarded against Qt's programmatic-`setValue`
re-entrancy via `_GuardContext`, as in `lut3d.py`), the whitepoint-simulation
options, the estimated-measurement-time readout, and the big
`mr_update_main_controls` show/hide/enable orchestration. It reuses the sub-slice
i helpers. Runnable standalone via `python -m DisplayCAL.ui.measurement_report`.

**Measurement report sub-slice iii — actually generating the report — DONE
(2026-07-09).** Picked from the "Remaining gaps" list (maintainer's choice, over
3D LUT creation). Closed the sub-slice i/ii deferral: `ReportWindow.measure_requested`
(previously a not-yet-available notice) now drives the full pipeline through
`MainWindow._on_report_measure_requested`. Extended
`DisplayCAL/measurement_report.py` with the rest of the toolkit-neutral core --
`resolve_report_context` (chart load, simulation/devlink/output profile
resolution, the BT.1886-style TRC target and its `xicclu` blackpoint lookup, the
reference-value `chart_lookup` calls; ports `measurement_report_handler`),
`stage_measurement_files` (temp-dir/TI1/profile/cal staging; ports
`measurement_report`'s pre-`worker.start` half), and `finalize_measurement_report`
(the measured-TI3 processing -- quantization, devlink white-patch rescale, Lab
conversion, instrument/ccmx label building -- plus the `placeholders2data`
assembly and `report.create` + `launch_file`; ports `measurement_report_consumer`).
All three take `worker: Worker` directly (the `preflight_checks.py` precedent of
treating `Worker` as an already-toolkit-neutral collaborator), so the only
window-shaped code left in `main_window.py` is the save-path `QFileDialog` +
overwrite `QMessageBox` and staging the run through the same
`flow.plan_measurement` / `WorkerRunController` engine the calibrate/profile
buttons use (`_begin_report_measurement` generalizes `begin_measurement` since
the report flow isn't a `MeasurementAction`). 28 new tests in
`tests/test_measurement_report.py` (real `.ti1`/`.ti3`/`.icc` dispread/colprof
fixtures against a minimal `FakeWorker`, no Argyll/display needed) and 17 in
`tests/test_ui_main_window.py`.

**Measurement report sub-slice iv — self-check report, low-res-B2A offer,
sanity-check review grid — DONE (2026-07-09).** Closed all three deferrals
left open above (maintainer's choice, "measurement report edge cases", over
the elevated-scope profile install and the madVR/Prisma 3D LUT API install
destinations).

- **Self-check report** (hold Alt while clicking Measure): `ReportWindow
  .measure_requested` (`ui/measurement_report.py`) now carries a bool --
  `_measure_btn_clicked` reads `QApplication.keyboardModifiers() &
  Qt.AltModifier` at click time, the Qt equivalent of wx's
  `wx.GetKeyState(wx.WXK_ALT)` read in `measurement_report_handler` (the
  button-label swap wx's `MainFrame.check_keydown` timer does lives on a
  different widget in this port -- the main window's own always-visible
  `measurement_report_btn`, which here only opens the settings window rather
  than triggering measurement directly -- so it has no faithful 1:1 target and
  was left unported). New `DisplayCAL/measurement_report.py::
  perform_self_check_lookup` ports the `self_check_report and oprof` branch:
  writes `oprof` (baking in its calibration curve via a real `applycal` run
  first if the device link expects one applied, reusing the already-toolkit-
  neutral `_applycal_bug_workaround`), looks the chart up through it directly
  (`chart_lookup(..., pcs="x", intent="a", white_patches=0)`, no instrument
  involved) and stages the result as a TI3 exactly like a real measurement's
  output. `MainWindow._run_report_self_check` runs it synchronously (no
  progress dialog -- it's local computation, no subprocess/instrument
  round-trip) and feeds the result into the same
  `_on_report_measurement_finished` a real measurement uses.
  `finalize_measurement_report` gained a `self_check_report` parameter
  swapping in the profile's own device/description for the
  display/instrument/CCMX placeholders (`report_type="Self Check"`,
  `instrument="N/A"`, `ccmx="N/A"`), matching `measurement_report_consumer`'s
  own branch.
- **`check_profile_b2a_hires`'s low-res-B2A offer**: new pure predicate
  `profile_b2a_is_lowres()` (B2A0 present, `LUT16Type`, `clut_grid_steps <
  17`, Argyll-created). `MainWindow._offer_profile_hires_b2a` gates both
  `_on_report_measure_requested` (right after `resolve_report_context`, same
  point wx's `check_profile_b2a_hires` call sits) -- the report is always
  refused when flagged, offering the regenerate-and-save side effect
  independently via `worker.update_profile_B2A` /
  `_on_profile_hires_b2a_finished` (a port of `profile_hires_b2a_consumer`:
  save-path picker if the profile has no file yet, then install-offer via the
  already-ported `InstallProfileWindow`). Not reproduced: the standalone
  "Tools > Advanced" menu entry that lets the wx dialog re-pick an arbitrary
  profile (`profile_hires_b2a_handler`'s own entry point) -- the Tools menu
  itself isn't ported, so this Qt port only reaches the regenerate offer from
  the measurement-report flow's already-resolved profile.
- **`measurement_file_check_confirm`'s suspicious-patch review grid**: new
  `DisplayCAL/ui/measurement_sanity_dialog.py::MeasurementSanityDialog`, a
  `QTableWidget`-based port of wx's `MeasurementFileCheckSanityDialog`
  (checkbox column, editable R/G/B and X/Y/Z cells with live sRGB/measured
  colour swatches, per-cell bold-red marking for out-of-tolerance deltas,
  select-all/deselect-all toggle, invert-selection). All the delta-E math
  stays toolkit-neutral: `measurement_report.py` gained
  `resolve_sanity_check()` (the `check_ti3`-driven detection + row/dedup
  logic), `recompute_sanity_row()` (the live-edit recompute via
  `check_ti3_criteria1`/`2`, faithfully reproducing a wx quirk where a row's
  recompute reads its *original* "previous row" values, not any of that row's
  own since-edited ones), `apply_sanity_check_result()` (removal via
  `CGATS.remove()` + mods application) and `resync_report_ti3_removals()` (the
  reference/simulation-TI3 patch-count resync the measurement-report path
  needs when items are dropped). New `MainWindow._check_measurement_sanity`
  wires the dialog into both call sites wx gates through this same helper:
  `_build_profile_from_measurement` (new `resolve_working_ti3_path()` finds
  the just-measured working TI3 the way `check_copy_ti3`'s no-explicit-TI3
  branch does) and `_on_report_measurement_finished` (loads `ti3_measured`
  before `finalize_measurement_report`, which re-loads the same -- now
  possibly user-edited-and-rewritten -- file from disk, so no `ti3_measured`
  parameter needed on that function; only `removed_items` was added for the
  resync). `force=True` (the standalone "check measurement file..." tool's
  parameter, not currently reachable from this Qt port) is threaded through
  for parity but always `False` from both integration points today.

Not reproduced (documented in the relevant module docstrings): the standalone
"Tools > Advanced > Check measurement file..." tool and its
"check automatically" menu toggle (the Tools menu isn't ported at all yet);
the Space-key checkbox shortcut in the review grid (Qt's default item
delegate already supports mouse-toggling a checkable cell). 52 new/updated
tests in `tests/test_measurement_report.py`, 10 in the new
`tests/test_ui_measurement_sanity_dialog.py`, 2 in `tests/test_ui_measurement_
report.py`.

**Colorimeter-correction sub-slice i — CCXX metadata injection — DONE.**
`DisplayCAL/colorimeter_correction.py` (another plain, Qt-free `DisplayCAL`
module), covered by `tests/test_colorimeter_correction.py` (9 tests, no display).
`inject_ccxx_metadata()` is the pure port of the raw-bytes rewriting near the
end of the 1736-line `create_colorimeter_correction_handler()` that adds the
`REFERENCE` / `TECHNOLOGY` / `MANUFACTURER_ID` / `MANUFACTURER` / `OBSERVER` /
`REFERENCE_OBSERVER` fields Argyll omits from CCMX/CCSS by default (inserted
above the `DISPLAY` line, in a fixed order so the output MD5 is stable, skipping
any field already present). It normalizes `str`/`bytes` values (the wx path had
a latent `b"%s" % str` crash if the technology string arrived as `str`), which
is byte-identical for real inputs (no backslashes). The wx handler now delegates
(same ruff profile). This is the first bite of the plan's "extract the 1736-line
handler first"; the dialogs, the `spec2cie` / `ccxxmake` / `create_ccxx` worker
run, the four-color-matrix path, the reference-vs-corrected preview grid, and
`import_colorimeter_correction` / `upload_colorimeter_correction` remain.

**Colorimeter-correction sub-slice ii — the Qt create window — DONE.**
`DisplayCAL/ui/colorimeter_correction_window.py` (`CreateCorrectionWindow
(BaseWindow)`), covered by `tests/test_ui_colorimeter_correction_window.py` (15
tests, headless offscreen; 2 run the real `ccxxmake` pipeline end to end and are
skipped when no Argyll install is present). Unlike the other ported settings
windows, this one runs the actual Argyll pipeline itself rather than deferring
it: correction-type (matrix/spectral + four-color-matrix) and reference/
colorimeter instrument + measurement-mode + observer + TI3 selection, TI3
loading/validation (spectral/EDID detection dropped in favour of dedicated
reference/colorimeter controls, the CCXX-testchart patch trimming kept,
`check_add_display_type_base_id` + `DISPLAY_TYPE_REFRESH` backfill kept since
`ccxxmake` hard-requires them), the auto-derived description/display/
manufacturer/technology fields, the `spec2cie`/`ccxxmake`/`create_ccxx` run on a
`QThread` (the `lut3d.py` `_CreateThread` pattern) behind an indeterminate
`QProgressDialog`, the four-color-matrix recomputation
(`colormath.four_color_matrix`), metadata injection (reusing sub-slice i's
`inject_ccxx_metadata` plus a newly-extracted `get_cgats_path`, both now shared
with the wx path), the `FIT_METHOD`/`FIT_*_DE94`/`FIT_*_DE00` metadata, and a
`_PreviewDialog` (`QTableWidget` with sRGB swatches, the Qt stand-in for the wx
reference-vs-corrected confirmation grid) before the overwrite-check + save.
Verified against a real Argyll install: constructs a valid CCMX from synthetic
TI3 fixtures with correct correction-matrix values, fit-error metadata and
technology defaulting (LCD, fixing a latent bytes/str comparison bug in the wx
handler that silently defaulted the technology chooser to CRT).

**Dropped / simplified versus the wx handler:** the "Measure reference" /
"Measure colorimeter" buttons need the live measurement flow (main-window
territory), so they only emit `measure_reference_requested` /
`measure_colorimeter_requested` signals, matching the `ReportWindow` /
`MeasureFrame` deferral. TI3 controls accept only `.ti3` (the wx `.icc`/`.icm`-
as-reference path via `ti1_lookup_to_ti3` is dropped). Measurement-mode choices
come from the generic `Worker.get_instrument_measurement_modes()` rather than
the wx handler's hard-coded per-instrument label overrides. The `spec2cie`
reference-observer override and the provenance-only `REFERENCE_FILENAME`/
`*_HASH` metadata are not reproduced. The web-check, import and upload entry
points (sub-slice iii, below) and the wx-only `CCXXPlot` spectral/matrix
visualization (still future work) were tracked as separate items.

**Colorimeter-correction sub-slice iii — import/upload/web-check — DONE.**
`DisplayCAL/colorimeter_correction.py` gains the remaining toolkit-neutral
pieces, covered by the expanded `tests/test_colorimeter_correction.py` (35
tests, no display): `parse_web_check_entries()` (the JSON-entry-to-row loop
from `colorimeter_correction_web_check_choose`, minus the wx `ListCtrl`
dialog), `build_web_check_params()` (from `colorimeter_correction_web_
handler`), `build_upload_params()` / `compute_upload_dedup_hash()` /
`validate_upload_originator()` (from `MainFrame.upload_colorimeter_
correction` / `upload_colorimeter_correction_handler` / the module-level
`upload_colorimeter_correction`), and `get_argyll_data_files()` /
`discover_auto_import_paths()` / `detect_import_kind()` (from `MainFrame.
get_argyll_data_files` / `import_colorimeter_corrections_producer` /
`import_colorimeter_correction`, `self` → `worker`). The wx `MainFrame` now
delegates to all of these (byte-for-byte identical CGATS output), thinning
~350 lines out of the three handlers. Two latent wx bugs, both fixed at the
source (so the still-shipping wx path gets the fix too): `REFERENCE_OBSERVER`
(and `FIT_METHOD`'s "xy" case) came back from `queryv1()` as `bytes` but were
looked up/compared against `str` data, so the web-check dialog's "observer"
column always showed "unknown"; and `upload_colorimeter_correction_handler`
passed a `str` (from `.decode()`) into a helper that later ran a `bytes`-
pattern regex against it, raising `TypeError` for every manually-chosen
upload file (the create-correction call site, which already held `bytes`,
never hit it). `build_upload_params()` now normalizes `str` input to `bytes`
upfront.

`DisplayCAL/ui/colorimeter_correction_io.py` provides the Qt side, covered by
`tests/test_ui_colorimeter_correction_io.py` (15 tests, headless offscreen):
three `QObject` controllers (`WebCheckController`, `ImportController`,
`UploadController`), each owning a background `QThread` plus an indeterminate
progress dialog (the `_CreateThread` pattern from
`ui/colorimeter_correction_window.py`), plus a small standalone launcher
window (`ColorimeterCorrectionIOWindow`, `python -m DisplayCAL.ui
.colorimeter_correction_io`) with one button per flow for manual testing.
`WebCheckController` runs the `http_request` GET on the thread, parses the
response with `parse_web_check_entries()`, and shows a `_WebCheckChooserDialog`
(a `QTableWidget` chooser, auto-selecting when there's only one match) before
saving via the new `save_correction()` (write + overwrite-check + `colorimeter
_correction_matrix_file` config update). `ImportController` shows an
`_ImportOptionsDialog` (auto-detect checkboxes per importer + a file picker
alternative + install-scope radios), then runs the same auto-discovery /
per-path dispatch / OEM-package auto-download loop the wx producer did
(toolkit-neutral, so it runs unchanged on the `QThread`) and reports success/
failure like `import_colorimeter_corrections_consumer`. `UploadController`
validates the ORIGINATOR, confirms, then runs the duplicate-check GET +
upload POST on the thread.

**Dropped / deferred versus the wx handlers:** the "info" button
(`CCXXPlot` spectral/matrix preview) is not reproduced, matching the drop
already made in `colorimeter_correction_window.py`. Choosing an elevated
import scope (local system/network) shows a not-yet-available notice instead
of attempting an unauthenticated install, matching `profile_install_window
.py`'s deferral (needs `Worker.authenticate()`'s wx password prompt). These
flows are standalone (own `Worker`, own dialogs) and not yet wired to a live
main window, so the wx consumer's `update_measurement_modes()` /
`update_colorimeter_correction_matrix_ctrl_items()` refresh is not
reproduced; the future Qt main window will need to refresh its own state
after a successful import/web choice.

**Profile share — effectively retired.** `profile_share_handler()` returns early
with a "icc.opensuse.org is not working anymore / temporarily disabled" notice
(#194); everything after is dead code. The Qt port is just that notice, so there
is no extraction to do here until/unless the upload endpoint is revived.

**Profile install / load-on-login sub-slice i — toolkit-neutral helpers — DONE.**
`DisplayCAL/profile_install.py` (another plain, Qt-free `DisplayCAL` module),
covered by `tests/test_profile_install.py` (20 tests, no display). It holds
the pure pieces lifted out of `install_profile_handler`, `profile_finish` and
`profile_finish_consumer`: `load_installable_profile()` (the `mntr`/`RGB`
validation, raising a new `ProfileUnsupportedError` instead of building the wx
error dialog inline), `get_profile_load_on_login_label()` (moved here
verbatim; `display_cal.py`'s function of the same name now delegates),
`resolve_install_scope_options()` (the platform/Argyll-version/privilege
boolean guarding the user/local-system/network radio buttons, returning which
of `"u"`/`"l"`/`"n"` to offer), and `summarize_install_result()` (the
all-good/some-good/per-method-breakdown derivation from `Worker
.install_profile()`'s 4-tuple result, replacing the wx consumer's inline
icon/message logic). The wx `MainFrame` now delegates to all four.

**Profile install / load-on-login sub-slice ii — the Qt window — DONE.**
`DisplayCAL/ui/profile_install_window.py` (`InstallProfileWindow(BaseWindow)`)
is the Qt port of the install-profile portion of `profile_finish` (not its 3D
LUT install branch, already covered by the ported `ui/tools/lut3d`), covered
by `tests/test_ui_profile_install_window.py` (12 tests, headless offscreen).
Standalone-runnable (`python -m DisplayCAL.ui.profile_install_window`), it
covers `select_install_profile_handler` + `install_profile_handler` (browse or
drop an `.icc`/`.icm`, validated via the sub-slice-i helper), a "show profile
info" button that opens the already-ported `ui.tools.profile_info
.ProfileInfoWindow`, the load-on-login checkbox (+ the Windows-only "handled
by OS" sub-checkbox, backed by `util_win.calibration_management_isenabled`/
`enable_calibration_management`), the install-scope radio buttons built from
`resolve_install_scope_options()`, and the actual install via
`Worker.install_profile()` on a `QThread` behind an indeterminate
`QProgressDialog` (the `lut3d.py` `_CreateThread` pattern), with the result
reported through `summarize_install_result()`.

**Dropped / deferred versus the wx dialog:** the calibration-preview and "show
LUT" checkboxes need a live calibration session on the running main window
(the wx dialog reads `self.cal` / `self.preview`); they return with the Qt
main window. The Windows profile-loader IPC resync (the
`send_command("apply-profiles", ...)` round-trip to a separately running tray
process, in both `profile_load_on_login_handler` and `profile_finish`) is not
reproduced; `profile.load_on_login` is still written directly, which is what
`Worker.install_profile()` itself reads. (Installing with an elevated scope
was deferred here too, until the next entry below closed it.)

**`Worker.authenticate()` elevated install — DONE (2026-07-09).** Picked from
the "Remaining gaps" list (maintainer's choice, over the pattern-generator
setup dialogs). Closes the elevated-install deferral left by both
`profile_install_window.py` above and `colorimeter_correction_io.py`'s
`ImportController` (Stage 5+ "Colorimeter-correction sub-slice iii"): choosing
the local-system/network install scope, or the system-wide import-scope radio
button, no longer shows a not-yet-available notice.

`Sudo.authenticate` (`worker.py`) gained an optional `prompt` callable: when
given, it's called with the prompt message in place of building the wx
password `ConfirmDialog` inline, and is expected to return the entered
password or `None` on cancel; `prompt=None` (the default, so the still-shipping
wx path is byte-for-byte unchanged) keeps the original dialog. `Worker.authenticate`
(the higher-level method `exec_cmd` calls when a command needs `asroot`) gained
a matching `Worker.password_prompt` attribute (`None` by default) threaded into
that call. `DisplayCAL/ui/worker_runner.py` gains `PasswordPromptAdapter(QObject)`,
the Qt implementation of the seam: it mirrors `ProgressAdapter.confirm()`'s
blocking marshal-to-GUI-thread pattern (a `threading.Event`-guarded request
object, a queued signal, and a same-thread fast path) but shows a small
`QDialog` with a password-mode `QLineEdit` instead of a yes/no `QMessageBox`,
returning the typed text or `None` on cancel/reject. `InstallProfileWindow`
and `ImportController` each assign a `PasswordPromptAdapter` to their
`Worker.password_prompt` (`ImportController` does so defensively, in case a
future caller passes in a `Worker` that doesn't already have one), so
`worker.install_profile()` / the colorimeter-correction import's system-wide
scope now actually prompt for and use a password when `dispwin -I -Sl`/`-Sn`
or the OEM importer's asroot path triggers `exec_cmd(asroot=True)`. Windows
elevation (UAC) and macOS/Linux "already root" still bypass the prompt
entirely (`Worker.authenticate` returns `None` early in both cases), matching
wx; no wx behaviour changed since the seam is purely additive (default `None`
preserves the exact original dialog and loop logic).

**Fixed a real bug found while porting** (in `colorimeter_correction_io.py`,
not present in the wx path): `ImportController._do_import`'s auto-download
fallback loop (the second of two `ccxx_helpers.detect_import_kind()` call
sites) had `asroot` hardcoded to `False` instead of threading
`self._asroot` through like the first call site — so a system-wide import
would authenticate for files found locally but silently fall back to a
user-scope install for anything reached via the automatic OEM-package
download. Fixed to match wx's single `asroot` parameter threaded through both
branches of `import_colorimeter_corrections_producer`.

5 new tests in `tests/test_worker.py` (`Sudo.authenticate()`'s prompt seam:
accept, cancel, and retry-after-rejected-password, each driven by a scripted
fake `wexpect.spawn` handle so no real `sudo` subprocess runs; plus
`Worker.password_prompt` defaulting to `None` and being threaded through to
`Sudo.authenticate()`), 5 new tests in `tests/test_ui_worker_runner.py`
(`PasswordPromptAdapter`'s same-thread/blocking/cancel paths, plus two
end-to-end dialog round-trips typing into and accepting/rejecting the real
`QDialog`), and the two windows' existing not-yet-available-notice tests were
rewritten to assert the elevated path actually runs (`profile_install_window`
already had `Worker.install_profile()` mocked at that layer; the
`colorimeter_correction_io` replacement mocks `detect_import_kind()` and uses
"files" mode rather than "auto" so the fixture's stub instrument list can't
trigger a real network download through the unrelated auto-checked
importers).

**`display_tech_info_show_btn` / `TooltipWindow` — DONE (2026-07-09).** Picked
as the first item of a "small polish bundle" (maintainer's choice, over the
madVR/Prisma 3D LUT API install, the standalone Tools menu, and standalone
tool-window ports). Closes the Session 6 deferral: the Display & Instrument
tab's info panel was missing the "Show information about common display
technologies" button entirely.

New `DisplayCAL/ui/tooltip_window.py::TooltipWindow(QDialog)` is a
deliberately narrower Qt port of wx's reusable `TooltipWindow`
(`wx_windows.py`): icon + word-wrapped rich text (reusing
`MainWindow._info_text_html`'s markup translation) plus optional flat "link"
buttons that open a URL via `QDesktopServices.openUrl` -- only the
single-column, non-scrolled shape `display_tech_info_show_btn` actually needs,
not wx's generic multi-column/scrolled/header-row constructor options.
`MainWindow._build_info_panel()` gained an optional `extra: QWidget` param
(appended below the icon/text rows, indented to align under the text column)
so the button can live inside the existing Display & Instrument info panel
like wx's version does, rather than becoming a new sibling widget.
`_display_tech_info_show_btn_handler()` lazily builds and caches a single
`_display_tech_info_window` instance and calls its `show_and_raise()`,
mirroring wx's `hasattr(self, "display_tech_info_tooltip_window")` cache
check. 3 new tests in `tests/test_ui_main_window.py` (277 total). Verified
visually via rendered `QWidget.grab()` screenshots of both the button's tab
placement and the popup's content/links.

**Profiling tab: `set_default_testchart` reset + CCXX-testchart-recommendation
dialog — DONE (2026-07-10).** Second item of the "small polish bundle"
(maintainer's choice). Closes the Session 9 deferral documented in
`profile_name.py`'s module docstring.

`profile_name.py` gains the pure pieces: `discover_distributed_testcharts()`
+ `default_testchart_names()` (port of the two `RES_FILES`/`TESTCHART_DEFAULTS`
scans `MainFrame.__init__` does once at startup), `resolve_default_testchart()`
(port of `MainFrame.set_default_testchart`'s path-resolution half, returning a
`DefaultTestchartResolution` the caller applies instead of driving an
`InfoDialog` itself), and `testchart_recommendation_auto_optimize()` (port of
`check_testchart_patches_amount`'s recommended-patch-count gating and
suggested-``auto_optimize`` math). `main_window.py`'s
`_profile_type_ctrl_changed` now calls new `_apply_default_testchart()` (always,
mirroring wx calling `set_default_testchart` unconditionally) and, only for a
genuine combo click, new `_check_testchart_patches_amount()` (a `QMessageBox
.question` confirm, matching wx's `ConfirmDialog`). Distinguishing a real click
from the internal re-entry `_apply_testchart_patches_amount` already made
(wx calls `profile_type_ctrl_handler(None)` for this) needed a new
`_profile_type_change_is_synthetic` flag, set right before that method's own
`setCurrentIndex`/direct-call re-entry into `_profile_type_ctrl_changed`, since
both paths reach the same Qt signal-connected handler indistinguishably
otherwise.

**Real (if surprising) wx behavior found while porting, not a bug:** because
every `TESTCHART_DEFAULTS` entry resolves to `"auto"` today (no profile type
has a quality-specific override), `set_default_testchart` resets *any*
non-bundled testchart selection back to `"auto"` on **every** profile-type
handler call, regardless of `force`/category-change -- `force` only protects a
testchart already named one of the bundled defaults, and `"auto"` itself
short-circuits before `force` is ever consulted, so it has no currently
observable effect. Ported faithfully rather than "fixed," and documented
directly in the regression tests that exercise it
(`test_profile_type_ctrl_resets_testchart_within_same_category_too`).

Not reproduced: the missing-`.ti1` `InfoDialog` (only reachable if a future
`TESTCHART_DEFAULTS` entry stops being `"auto"`; falls back to a `print()` for
now, matching the "not alert-worthy for a currently-dead branch" judgment call
made elsewhere in this port). 12 new tests in `tests/test_profile_name.py`
(58 total) exercise `resolve_default_testchart`/`testchart_recommendation_
auto_optimize` directly, including the non-"auto" branch via a
`TESTCHART_DEFAULTS` monkeypatch (dead in production today, still verified
correct). 6 new tests in `tests/test_ui_main_window.py` (280 total,
confirmed green under `-n auto`, ~70s) plus 4 pre-existing profile-type-combo
tests updated to stub `QMessageBox.question` -- a real combo click can now
pop the recommendation dialog, which would otherwise hang headless (see
[[qt-test-modal-hang-gotcha]]).

**Standalone Tools menu (partial), 2026-07-10.** Maintainer's choice over the
madVR/Prisma 3D LUT API install, the Stage-6 startup dialogs (update-check
prompt / instrument-setup nag), and further header-bar/small deferrals.
`menu.tools.advanced` (`mainmenu.xrc`) has six entries; three are ported here:

- **"profile.b2a.hires" (regenerate hires B2A tables for an arbitrary
  profile) -- DONE.** `MainWindow._profile_hires_b2a_action_handler` +
  `_select_profile_for_hires_b2a` port `profile_hires_b2a_handler`'s
  no-profile-argument path (the automatic low-res-detected call site remains
  `_offer_profile_hires_b2a`, unchanged). Profile selection is a simplified
  `select_profile`: a 3-button current/browse/cancel `QMessageBox` (only when
  a current profile exists, matching `_fast_matrix_shaper_choice`'s
  custom-labelled-button pattern) falling back straight to a file browse.
  Same A2B-tag/PCS validation as wx, then reuses the existing
  `worker.update_profile_B2A` run and `_on_profile_hires_b2a_finished`
  save/install-offer path.
- **"measurement_file.check_sanity" ("Check measurement file...") -- DONE for
  a plain `.ti3`; deferred for an ICC profile's embedded chart.**
  `MainWindow._measurement_file_check_action_handler` ports
  `measurement_file_check_handler`'s file-picking/loading half via new
  toolkit-neutral `measurement_report.load_measurement_file()` (raises
  `MeasurementFileError` with the same translated messages wx shows), then
  reuses the already-ported `_check_measurement_sanity(ti3, force=True)` --
  the same review dialog a live measurement uses, just forced regardless of
  the auto-check config. A `.ti3` file is saved back via a save-as dialog.
  An ICC profile's embedded chart shows a not-yet-available notice instead of
  wx's regenerate-and-install chain: that chain's target,
  `create_profile_handler` ("create profile from existing measurements"), is
  a distinct, unported File-menu feature in its own right (multi-file
  picking/merging, its own save-path dialog, a "no CAL info" confirm) --
  discovered while tracing this handler's `profile` branch, out of scope for
  this session. New `measurement_report.build_regenerated_profile_tag_data()`
  is still added (a direct, tested port of the tag-serialization step
  `create_profile_handler` would need) so a future session porting that
  feature doesn't have to re-derive it.
- **"measurement_file.check_sanity.auto" ("check automatically" toggle) --
  DONE.** `MainWindow._measurement_file_check_auto_toggled` ports
  `measurement_file_check_auto_handler`: confirms once (a `QMessageBox`) before
  turning the auto-check on, reverting the checkbox if declined; turning it
  off needs no confirmation.

Not reproduced: "synthicc.create" (the synthetic-ICC creator is already its
own standalone tool, `ui/tools/synth_profile.py`, just not cross-linked from
this menu) and "measure.testchart" / "specplot.run" (`measure_handler` /
`specplot_handler` aren't ported).

**Two real latent wx bugs found while tracing this feature, fixed at the
source in `display_cal.py` (both also fixed in the new toolkit-neutral
`load_measurement_file()` / `build_regenerated_profile_tag_data()`):**
`measurement_file_check_handler` and `create_profile_handler` both compared a
`bytes` tag slice (`profile.tags.get("CIED", "") or profile.tags.get("targ",
""))[0:4]`, always `bytes` when the tag exists since `Text` subclasses
`bytes`) against the `str` literal `"CTI3"` -- never equal in Python 3, so
the "no embedded TI3" error fired for *every* ICC profile passed to either
handler, even one with a perfectly valid embedded chart. Fixed by comparing
against `b"CTI3"` with a `b""` fallback default. Separately,
`measurement_file_check_handler`'s profile-regeneration branch built
`TextType(b"text\0\0\0\0" + ti3 + b"\0", b"targ")` where `ti3` was, by that
point in the method, the parsed `CGATS` object (reassigned earlier), not
bytes -- concatenating `bytes + CGATS` raises `TypeError`, so this branch
crashed 100% of the time it was ever reached. Fixed via `bytes(ti3)`. Neither
bug had test coverage before this session (added: `TestLoadMeasurementFile`,
`TestBuildRegeneratedProfileTagData` in `test_measurement_report.py`).

21 new tests in `tests/test_ui_main_window.py` (301 total), 11 new in
`tests/test_measurement_report.py` (58 total, both files confirmed green
under `-n auto`).

**`create_profile_handler` ("Create profile from measurement data...", File
menu), 2026-07-10.** Closes the deferral the previous session's Standalone
Tools menu work discovered; maintainer's choice over the madVR/Prisma 3D LUT
API install, the Stage-6 Pile-2 startup dialogs, and the header-bar
deferrals. New toolkit-neutral `DisplayCAL/create_profile.py` ports
`create_profile_handler`'s (`display_cal.py`) non-dialog pieces:
`load_measurement_lines()` (per-file load, raw stripped lines rather than a
parsed `CGATS` since the merge step below needs to re-serialize several
charts verbatim before anything is parsed -- a deliberate near-duplicate of
`measurement_report.load_measurement_file()`, not a refactor of it),
`has_calibration_curves()`, `resolve_source_naming()`, `is_temp_path()`,
`merge_measurement_files()` (writes per-file temp copies, runs Argyll's
`average` utility, cleans up regardless of outcome), and
`resolve_profile_creation_inputs()` (dispcal/targen option extraction +
display name/manufacturer, mirroring the `.ti3`-source vs. profile-source
branch). `MainWindow._build_file_menu()` adds the **first Qt File menu item**
beyond `BaseWindow.init_menubar()`'s bare "Quit" -- `BaseWindow.init_menubar`
now keeps an end separator (`_file_menu_end_separator`) so subclasses can
insert items before it while "Quit" stays pinned to the bottom, shared by
every Qt window. `MainWindow._create_profile_action_handler` (the File-menu
click) and `MainWindow._run_create_profile(paths, skip_ti3_check=False)` (the
shared orchestration, re-entered by the regenerate branch below) reproduce
the rest of the wx handler: multi-select open dialog, per-file "no CAL info"
confirm (`_confirm_ti3_no_cal_info`), save-path dialog +
extension-normalize + conditional overwrite confirm
(`_confirm_overwrite_profile`, only needed when the typed path had no
`.icc`/`.icm` extension and `PROFILE_EXT` was appended afterward, bypassing
the save dialog's own overwrite prompt), then the same
`worker.create_profile` run through `WorkerRunController` /
`_on_profile_build_finished` the colprof stage (sub-slice 5d) already uses --
matching wx's own reuse of one shared `profile_finish` consumer for both
flows.

Also closed the sibling deferral in `_measurement_file_check_action_handler`
(previous session): its ICC-profile-embedded-chart branch no longer shows a
not-yet-available notice -- it now confirms regeneration
(`profile.confirm_regeneration`), re-embeds the checked chart via the
already-ported `measurement_report.build_regenerated_profile_tag_data()`,
writes a temp copy, and re-enters `_run_create_profile([tmp_path],
skip_ti3_check=True)`, matching wx's `create_profile_handler(None, tmp_path,
True)` re-entry exactly.

**Real latent bug found and fixed at the source, `DisplayCAL/worker.py`
(`Worker.create_profile`):** its docstring always claimed a `str` path on
success, but the method's actual final `return result` carried whatever
`update_profile()` returned -- `True`, a bare boolean, never the path.
Harmless for every wx call site (`profile_finish` receives the path
separately via an explicit `ckwargs["profile_path"]`, only checking `result`
for truthiness/`Exception`-ness) but a real bug for this Qt port: both
`_build_profile_from_measurement`'s existing `controller.run(worker
.create_profile, self._on_profile_build_finished, wkwargs={"tags": True})`
call (sub-slice 5d) and this session's new one feed the producer's return
value straight into `_on_profile_build_finished`'s `profile_path = result`,
which would have received `True` and crashed loading `ICCProfile(True)`. Confirmed
by tracing `update_profile()`'s own two return statements (`True` / an
`Exception`, never a path) and cross-checking `_on_calibration_finished`'s
existing (already-shipped, already-correct) direct call --
`self._on_profile_build_finished(profile_finish.resolve_profile_path(), ...)`
-- which only makes sense if `_on_profile_build_finished`'s first argument is
meant to be a path. Fixed by assigning `result = dst_path` in the success
branch, immediately before the existing `return result`. Not covered by a
new dedicated `test_worker.py` unit test: `create_profile()` has no existing
test coverage at all (confirmed by grep) and is deeply coupled to a real
Argyll `colprof` subprocess run (`self.exec_cmd(cmd, ...)` mid-method,
`ti3 = CGATS(args[-1] + ".ti3")` unconditionally reading a real file off
disk) -- mirroring the Session 3 precedent of declining to add
integration-depth coverage for an already-untested, deeply-Argyll-coupled
method beyond its reach. The fix is exercised indirectly by every new Qt-side
test that asserts `worker.create_profile` is the producer threaded into
`_on_profile_build_finished`.

45 new tests: `tests/test_create_profile.py` (23, pure module-level), 22 in
`tests/test_ui_main_window.py` (2 replace the old "not yet available" test;
321 total in that file), full suite (`test_ui_main_window.py`,
`test_create_profile.py`, `test_measurement_report.py`,
`test_ui_startup.py`, `test_worker.py`) confirmed green under `-n auto`.

**Updated remaining-gaps list:** madVR/Prisma 3D LUT API install
destinations; Stage 6's deferred Pile-2 dialogs (update-check prompt,
instrument-setup/donation nag); the header-bar deferrals (EDID display
matching, legacy `.cal` parsing, 3D LUT HDR config-mapper, archive import via
load, per-file delete-confirmation checkboxes); `CCXXPlot` visualization; the
standalone `LUT3DFrame` tool window; the rest of wx's File menu
(`calibration.load`, `testchart.set`, `testchart.edit`,
`profile.set_save_path`, `create_profile_from_edid`,
`install_display_profile`, `profile.share`, `profile.info` -- several already
reachable elsewhere in this window, e.g. `install_profile_btn_handler`); the
rest of `menu.tools.advanced` (`synthicc.create`, `measure.testchart`,
`specplot.run`); and Stage 7 (retire wx), still gated on maintainer
confidence.

**Rest of the File menu — DONE (2026-07-10).** Offered a 4-way choice (rest of
the File menu / Stage 6 Pile-2 startup dialogs / header-bar deferrals /
remaining `menu.tools.advanced` entries), the maintainer picked "rest of the
File menu". `_build_file_menu` now adds every `menu.file` item from
`mainmenu.xrc` in xrc order, ahead of `_file_menu_end_separator`:
`calibration.load` (`Ctrl+O`), `testchart.set`, `testchart.edit`,
`profile.set_save_path`, a separator, `create_profile`,
`create_profile_from_edid`, `install_display_profile`, `profile.share`,
`profile.info`. Five of these (`calibration.load` -> `load_cal_btn_handler`,
`testchart.set` -> `_testchart_btn_handler`, `testchart.edit` ->
`_create_testchart_btn_handler`, `profile.set_save_path` ->
`_profile_save_path_btn_handler`, `profile.info` -> `profile_info_btn_handler`)
just expose an already-ported header-bar/tab handler as a menu action, no new
logic. Two are new, small handlers: `_select_install_profile_action_handler`
(a picked-profile install via `QFileDialog` + the already-ported
`InstallProfileWindow.load_profile`, distinct from
`install_profile_btn_handler`'s current-profile shortcut) and
`_create_profile_from_edid_action_handler` /
`_create_profile_from_edid_finish` (port of wx's `create_profile_from_edid` /
`create_profile_from_edid_finish`: builds an `ICCProfile.from_edid()` purely
from the display's EDID, no measurement needed; when
`profile.create_gamut_views` is set, calculates the gamut view through the
same `WorkerRunController` the other worker-driven flows use before baking its
result into the profile's metadata; either way hands off to the existing
`_on_profile_build_finished` rather than reproducing wx's separate
install-offer dialog). `profile.share` mirrors wx's own `profile_share_handler`,
which is already unconditionally disabled (icc.opensuse.org has been down
since #194) -- a plain notice instead of porting the large, permanently
unreachable body below wx's early return.

Hit a real instance of [[qt-test-modal-hang-gotcha]] while writing the EDID
tests: the gamut-calculation test's fake `WorkerRunController` correctly
avoided a real worker thread, but the consumer lambda it captured still called
the real `_create_profile_from_edid_finish` -> real `_on_profile_build_finished`,
which tried to `profile_finish.validate_built_profile()` a path the fake
profile never actually wrote real bytes to -- reaching an unmocked
`QMessageBox.critical` that blocks forever offscreen. Confirmed via
`faulthandler.dump_traceback_later`, not just a slow run (5+ minutes wall time
against ~2s of CPU time is the tell). Fixed by stubbing
`_on_profile_build_finished` in that one test, since it's already covered on
its own elsewhere. 12 new tests in `tests/test_ui_main_window.py` (333 total),
full suite green under `-n auto` (~87s).

**Rest of `menu.tools.advanced` — DONE (2026-07-10).** Offered a 4-way choice
(madVR/Prisma 3D LUT API install / Stage 6 Pile-2 startup dialogs / header-bar
deferrals / rest of the Tools menu), the maintainer picked "rest of the Tools
menu". All six `menu.tools.advanced` entries from `mainmenu.xrc` are now
reproduced, in xrc order: `synthicc.create` (`_synthicc_create_action_handler`,
a cross-link that reuses the already-ported standalone
`ui/tools/synth_profile.py` window as a singleton, same pattern as
`_gamap_btn_handler`), `profile.b2a.hires` (already ported), `measure.testchart`
(`_measure_testchart_action_handler`, new), `specplot.run`
(`_specplot_action_handler`, new), and the two `measurement_file.check_sanity`
entries (already ported).

`measure.testchart` is the port of `MainFrame.measure_handler`: unlike the
Profiling tab's "Profile" button, it runs a characterization measurement
without building an ICC profile afterward -- used either as a plain "capture a
TI3 for this testchart" tool, or (when the testchart is a CCXX reference/
colorimeter chart) to gather the raw measurement a colorimeter-correction
matrix is built from. New `measurement_report.compute_ccxx_measurement_basename()`
is the pure-naming half of `setup_ccxx_measurement`; new
`MainWindow._setup_ccxx_measurement()` owns the directory-picker/write-access
half. The measurement itself is staged through a new
`_begin_testchart_measurement()`/`_run_measure_testchart()` pair, generalized
from `begin_measurement()` the same way `_begin_report_measurement()` is (this
flow doesn't fit the `MeasurementAction` enum either). Finish handling
(`_on_measure_testchart_finished`, porting `just_measure_finish`) reviews and
copies the working TI3 via a new `_check_copy_ti3()` (a port of
`MainFrame.check_copy_ti3`, deliberately *not* unified with
`_build_profile_from_measurement`'s pre-existing inline equivalent -- the two
callers tolerate a falsy, non-exception copy result differently), then either
records the TI3 as a colorimeter-correction source
(`_record_ccxx_measurement_paths`) or offers to open the containing folder
(`_offer_open_measurement_folder`).

Two deliberate deviations from wx, both documented at the call site: (1)
`_setup_ccxx_measurement()`'s success/failure is honored by its caller (bails
out on failure with an error already shown) -- wx's `measure_handler` ignores
`setup_ccxx_measurement`'s outcome entirely and measures anyway, which would
proceed with a stale/unset `measurement.name.expanded` after a write-access
failure; judged worth fixing rather than faithfully reproducing. (2) wx chains
a CCXX measurement started *from* the correction-creation dialog
(`comport.number.backup` set) back into `create_colorimeter_correction_handler`
with the new TI3 paths pre-filled -- not reproduced, since the Qt
`CreateCorrectionWindow` has no matching "measure now" entry point that would
set that backup, making the chain unreachable either way. The restore-side
port (`_restore_measurement_mode_and_testchart`, mirroring
`restore_measurement_mode`/`restore_testchart`) is still included, cheaply, so
a future session wiring that entry point doesn't also have to add this half.

`specplot.run` is a small, self-contained port of `MainFrame.specplot_handler`
/ `specplot_consumer`: file picker, then Argyll `specplot` via the shared
`WorkerRunController`.

38 new tests: 3 in `tests/test_measurement_report.py`
(`TestComputeCcxxMeasurementBasename`), 35 in `tests/test_ui_main_window.py`
(378 total in that file). Full suite green under `-n auto` (~100s).

**Updated remaining-gaps list:** madVR/Prisma 3D LUT API install destinations;
Stage 6's deferred Pile-2 dialogs (update-check prompt, instrument-setup/
donation nag); the header-bar deferrals (EDID display matching, legacy `.cal`
parsing, 3D LUT HDR config-mapper, archive import via load, per-file
delete-confirmation checkboxes); `CCXXPlot` visualization; the standalone
`LUT3DFrame` tool window; and Stage 7 (retire wx), still gated on maintainer
confidence. `menu.tools.advanced` is now fully ported; the rest of
`menu.tools` (display/port detection, video-card-gamma-table reset, instrument
driver install, the `menu.tools.report` submenu, `calibration.show_lut`,
`infoframe.toggle`, `log.autoshow`) was never in scope for this port (see
`_build_tools_menu`'s docstring) and isn't tracked as a gap unless a
maintainer wants it.

### Stage 6 — StartupFrame — **DONE**

Port `StartupFrame` (the splash screen + background display/instrument
enumeration shown before the main window appears). The wx `MainFrame` and all
wx tool frames keep shipping unchanged and reachable — this stage only adds
the Qt splash screen ahead of the already-ported `MainWindow`. No wx module is
deleted in this stage.

**Flipping the default toolkit** (making Qt the default without
`DISPLAYCAL_UI=qt`/`--qt`) is a deliberate separate decision, held back
until the maintainer is ready to make Qt the default experience — not
bundled into this stage.

**Landed:** `DisplayCAL/ui/startup.py`, covered by `tests/test_ui_startup.py`
(14 tests, headless offscreen with a fake worker and stubbed frames/sound).
`StartupController` shows a `QSplashScreen` (the splash pixmap picked per
`splash.simple`, message via `welcome_message()`) and runs two things
concurrently rather than wx's serial animation-then-enumerate order:

- `_EnumerateThread(QThread)` runs `Worker.enumerate_displays_and_ports` off
  the GUI thread — the Qt replacement for the wx `delayedresult.startWorker`
  producer/consumer pair — guarded by a 20-second `QTimer` that calls
  `worker.abort_subprocess()` if enumeration hangs (matching wx's
  `CallLater(20000, ...)`). `should_enumerate_ports()` is the extracted,
  unit-tested port of the `enumerate_ports` kwarg derivation
  (`FORCE_SKIP_INITIAL_INSTRUMENT_DETECTION` / `enumerate_ports.auto` /
  instrument count).
- `_SplashAnimator` plays the wx icon-reveal (`theme/splash_anim`, 16 frames)
  and fading-in version-number overlay (`theme/splash_version`, 11 alpha
  steps via `load_version_frames()`), optionally preceded by the `splash.zoom`
  ease-out zoom-in effect (`zoom_scales()`, ported from
  `colormath.special_pow(t, -2084)`), composing each frame with `QPainter` and
  pushing it via `QSplashScreen.setPixmap()` (re-applying `showMessage()` each
  frame, since `setPixmap` clears it).
- `play_startup_sound()` is the verbatim port of the `startup_sound.enable`
  block (`audio.safe_init()` + `audio.Sound("theme/intro_new.wav")`).

`StartupController._maybe_finish()` only hands the populated `Worker` to
`on_ready` once *both* the animation and enumeration have finished (matching
wx's "proceed to the main window regardless" behaviour even on an enumeration
exception, which is printed, not swallowed), so the splash is naturally up for
at least as long as the animation takes rather than an artificial timer —
this also is what fixes the initial version's problem of the splash flashing
by too fast to see anything on a fast Argyll install. `MainWindow.__init__`
gained an optional `worker` parameter so it adopts this pre-enumerated worker
instead of re-running `enumerate_displays_and_ports` synchronously on the GUI
thread (the standalone/test path is unaffected: omitting `worker` keeps the
original synchronous construction). `main.py::_get_qt_main(None)` now points
at `startup.main` instead of `main_window.main` directly, so the `--qt`/
`DISPLAYCAL_UI=qt` main-application entry point shows the splash first.
Verified end to end against a real Argyll install headless: splash animates
through all frames, sound subsystem initializes (`pyglet`), background
enumeration populates real display/instrument names, `MainWindow` picks them
up with no second enumeration pass.

**Dropped** (Qt natively supports translucent PNG windows, none of this is
needed): the desktop-screenshot-behind-a-shaped-window trick (`grab_image`,
its macOS `screencapture` / Wayland `gnome-screenshot`/`spectacle` paths and
gamma correction), and reapplying the base bitmap's alpha channel / blurring
each zoom frame (`QImage` keeps alpha through scaling natively in Qt; the wx
blur radius was sub-pixel anyway, so dropping it is invisible).

**Post-launch dialogs (update-check prompt, instrument-setup/donation nag) —
DONE (2026-07-10).** Closed the deferral noted above (maintainer's choice,
over the header-bar deferrals / standalone `LUT3DFrame` tool window /
`CCXXPlot` visualization / madVR-Prisma 3D LUT API install). Ports the tail of
wx's `StartupFrame.setup_frame_finish`: once the main window is shown, either
a silent update check or the instrument-setup/donation-nag check runs,
depending on the persisted `update_check` setting.

New toolkit-neutral `DisplayCAL/update_check.py` (covered by
`tests/test_update_check.py`, 22 tests, no display) is a **fresh copy** of the
non-dialog pieces of `display_cal.py`'s `is_new_update` / `app_update_check` /
`app_update_confirm` chain, not an extraction-and-delegate like the rest of
this plan's toolkit-neutral modules: `display_cal.py` imports `wx` at module
scope (so it can never be imported from the pure-Qt process, unlike
`worker.py`/`argyll.py`/`config.py`), and its `is_new_update` /
`get_download_url` already have dedicated tests that monkeypatch
`display_cal.requests` / `display_cal.sys.platform` /
`display_cal.platform.machine` directly on that module's namespace — a
delegating wrapper would silently break them. `check_app_update()` /
`check_argyll_update()` call the same GitHub / ArgyllCMS-binaries APIs as the
wx originals and return a plain `UpdateCheckResult` (version strings,
changelog HTML, resolved download URL) instead of driving a dialog. New
toolkit-neutral `DisplayCAL/instrument_setup.py` (covered by
`tests/test_instrument_setup.py`, 12 tests, no display) ports the detection
half of `MainFrame.check_instrument_setup` (`resolve_instrument_setup_needs`,
against `Worker.instruments` and the already-ported
`ColorimeterCorrectionCatalog.instruments` in place of wx's
`MainFrame.ccmx_instruments`) and the config-mutating gate of `check_donation`
(`should_show_donation_message`, dropping the snapshot-build branch since it's
never reached from the Qt path).

`DisplayCAL/ui/update_check_window.py` (`UpdateCheckController`, covered by
`tests/test_ui_update_check_window.py`, 9 tests, headless offscreen) checks
both the DisplayCAL and ArgyllCMS release channels off the GUI thread in one
background call, then shows an `_UpdateAvailableDialog` (changelog
`QTextBrowser`, the "check on startup" checkbox, a single "Download"/"Go to
website" button that opens the resolved URL via `launch_file` rather than
reproducing wx's in-app auto-download-and-run flow) for whichever channel has
a newer version — both, if both do — or, for a manual/non-silent check, a
plain "up to date" `QMessageBox` when neither does. `MainWindow` gained a
minimal Help menu (`_build_help_menu`: just the `update_check` /
`update_check.onstartup` pair, not wx's license/support/bug-report entries)
and `run_post_launch_checks()` (called by `ui/startup.py`'s `main()` one event
loop turn after `window.show()`, via `QTimer.singleShot(0, ...)` mirroring
wx's `wx.CallAfter`): silent update check first when `update_check` is set,
chaining into `_run_instrument_setup_and_donation_check()` when it finds
nothing (mirroring wx's `app_update_check` → `check_instrument_setup` chain),
otherwise straight to the instrument-setup/donation check. That method reuses
the already-ported `ImportController` (`colorimeter_correction_io.py`) for
the colorimeter-correction-import branch — a real, working import flow, not a
notice — and `_DonationDialog` (a new private `QDialog` on `main_window.py`,
alongside `_CalChoiceDialog`) for the donation nag itself, a faithful port of
`display_cal.donation_message`.

**Dropped / deferred versus wx** (documented in the relevant module
docstrings): the Spyder2 "enable" wizard
(`MainFrame.enable_spyder2_handler`, which patches OEM firmware through the
discontinued `spyd2en` Argyll utility for a colorimeter out of production
since 2009) — detected (`InstrumentSetupNeeds.needs_spyder2_enable`) but
shown as a not-yet-available notice instead of a wizard, then falls straight
through to the donation check like a cancelled wx wizard would; the
snapshot/beta release channel (never reached by any reachable wx call site
either); the ZeroInstall packaging path (already hard-coded off in wx); wx's
self-chained "check the other channel after declining" behaviour (this
controller already checks both channels in one pass, so there's nothing to
chain); and the in-app auto-download-and-run-the-installer flow (a large,
separate feature — the dialog opens the resolved URL in the system browser
instead).

**Fixed a real, unrelated latent bug found while running the full test suite
for this session:** `install_profile_handler` (`display_cal.py`) showed a
real (unmocked) `InfoDialog` mid-suite reading "Unsupported profile type
(b'mntr') and/or colorspace (b'RGB')" — nine call sites across
`display_cal.py`, `worker.py`, `profile_install.py`, `wx_lut_viewer.py`,
`wx_lut_3d_frame.py`, `wx_synth_icc_frame.py`, `wx_report_frame.py` and
`wx_profile_info.py` built the `"profile.unsupported"` message from raw
`ICCProfile.profileClass`/`.colorSpace`/`.connectionColorSpace` `bytes`
without decoding them first, so `%s`-formatting rendered Python's `bytes`
repr (`b'mntr'`) instead of `mntr`. All nine now `.decode("utf-8")` before
formatting. Unrelated to this session's Qt work, but the wx full-suite run
(no offscreen/virtual-display sandboxing on macOS the way the Qt tests get
via `QT_QPA_PLATFORM=offscreen`) surfaced it as a real dialog requiring a
click; the specific triggering test wasn't tracked down (out of scope here),
but the message-formatting bug itself is real and unambiguous regardless of
which test path reaches it.

**Updated remaining-gaps list:** madVR/Prisma 3D LUT API install destinations
(needs the still-unported `setup_patterngenerator` connection dialogs); the
Spyder2 firmware-enable wizard (see above); the header-bar deferrals (EDID
display matching, legacy `.cal` parsing, 3D LUT HDR config-mapper, archive
import via load, per-file delete-confirmation checkboxes); `CCXXPlot`
visualization; the standalone `LUT3DFrame` tool window; wx's full Help menu
(license, "go to website", support, bug-report — only the update-check pair
is reproduced); and Stage 7 (retire wx), still gated on maintainer confidence.

### Stage 7 — Retire wx code paths

Delete the wx modules whose Qt replacements have been verified equivalent.
This is explicitly **gated**, not scheduled: it only starts once we're
confident the wx and Qt paths are near identical in behaviour and layout
(per [[feedback-qt-port-layout-parity]] — matched sizer order/widget
placement, not just matched widget sets), across real-world use, not just the
headless construct-and-exercise checks each stage has used so far. Until that
confidence exists, Stage 6 ships with both toolkits coexisting indefinitely.

## Risks / guardrails

- The wx `MainFrame` is the most-used, least-covered path; the migration premise
  is that it keeps shipping untouched ([README.md](README.md#L6-L11)). Favour
  **extraction** (Pile 1) over restructuring wx widgets (Pile 2), and back each
  extraction with tests before it moves.
- Keep the config keys (Pile 3) byte-for-byte identical so a user can switch
  toolkits mid-project without losing state.
- Each stage must be independently shippable and verified headless
  (`QT_QPA_PLATFORM=offscreen`) plus a construct-and-exercise check, per the
  established tool-porting pattern.
