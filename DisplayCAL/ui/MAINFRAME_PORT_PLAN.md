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
  `BaseWindow`), a header-less vertical layout of tab bar + stacked panels +
  action-button bar.
- A tab bar of exclusive `QToolButton` toggles (Display, Calibration, Profiling,
  3D LUT) switching a `QStackedWidget` — the Qt equivalent of the wx custom
  `TabButton` / show-hide-settings-panel mechanism.
- The **Display & Instrument** tab fully wired: display / instrument (comport) /
  observer `QComboBox`es populated from `Worker.enumerate_displays_and_ports`
  and `config`, persisting `display.number` / `comport.number` / `observer`
  through an `_updating` re-entrancy guard (so repopulation never clobbers the
  stored selection). The name-marshalling (`display_items`, `instrument_items`)
  is factored into pure module functions and unit-tested; observer items reuse
  Stage-2 `observer_items()`.
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

**Deferred to later slices (Pile 2 / Stage 4-5):** the measure / visual-editor /
ambient-measure buttons, the gamap and testchart-editor / file-picker / profile
save-path launch buttons, profile-name token expansion + the `?` preview, the
`show_advanced_options` show/hide gating, the estimated-measurement-time
readouts, the black-point-rate advanced control, and the 3D LUT encoding /
HDR / content-colorspace sub-controls. These depend on tools, dialogs or the
Stage-4 flow and are rebuilt natively as those land.

### Stage 4 — Calibrate / measure / profile actions

Wire the action buttons to the Stage-2 flow: `just_calibrate`, `just_measure`,
`just_profile`, `calibrate_and_profile`, `profile_finish`, running Argyll via
`worker.Worker` on a `QThread` (per README pattern #3).

### Stage 5 — Reporting, colorimeter corrections, install/share

The remaining large features, each its own slice: measurement report
(`measurement_report*`), colorimeter-correction create/import/upload (extract
the 1736-line handler first), profile install/load-on-login, profile share.

### Stage 6 — StartupFrame + retire wx paths

Port `StartupFrame`, flip the default toolkit, and begin deleting wx modules
whose Qt replacements are verified.

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
