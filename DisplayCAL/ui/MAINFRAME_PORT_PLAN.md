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
`show_advanced_options` show/hide gating, the estimated-measurement-time
readouts, the black-point-rate advanced control, and the 3D LUT encoding /
HDR / content-colorspace sub-controls. These depend on tools, dialogs or the
Stage-4 flow and are rebuilt natively as those land.

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
`colprof` stage `just_profile_finish` chains into via `start_profile_worker`),
the pre-flight `check_overwrite` / `current_cal_choice` / macOS-bugs preflight
dialogs, and verifying the run end-to-end against a real colorimeter.

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
`colprof` stage, shared with the 5b-iv profile deferral), the calibration success
side effects (`load_cal` + the `calibration.complete` dialog + fast-matrix-shaper
profile), the wx swap-to-progress-dialog once adjustment ends (the adjustment
window stays up showing status pulses through the curve measurement), the
`abort_subprocess` confirm-cancel path (still on the wx `delayedresult` seam, as
in 5b-iii), and verifying end-to-end against a real colorimeter.

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

**Deferred (surfaced as Qt signals, matching `MeasureFrame`):** the actual
measurement run and the test-chart editor are `measure_requested` /
`edit_chart_requested` signals for the not-yet-ported Qt main window to wire up.
Still in the wx path for now: the chart / profile / sim / devlink resolution and
BT.1886 lookup in `measurement_report_handler`, the file-save + overwrite
dialogs, the `worker.Worker` measure run (`measurement_report`), and the big
`placeholders2data` assembly in the consumer (it reads live CGATS / ICCProfile
objects and pulls display / instrument / ccmx strings from widgets) plus
`report.create` + launch. Those land when the Qt main window drives this window.

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
main window. Installing with an elevated scope (local system / network) needs
the wx password-prompt + `sudo` credential caching in `Worker.authenticate()`,
which pops a wx `ConfirmDialog` internally; the scope choice is still offered
and persisted to `profile.install_scope`, but choosing one and clicking
Install surfaces a not-yet-available notice instead of attempting (and
silently failing) an unauthenticated elevated install. The Windows
profile-loader IPC resync (the `send_command("apply-profiles", ...)`
round-trip to a separately running tray process, in both
`profile_load_on_login_handler` and `profile_finish`) is not reproduced;
`profile.load_on_login` is still written directly, which is what
`Worker.install_profile()` itself reads.

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
blur radius was sub-pixel anyway, so dropping it is invisible). **Deferred**
(Pile 2 dialogs not yet ported): the update-check prompt and the
instrument-setup/donation nag that wx runs right after the main window
appears.

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
