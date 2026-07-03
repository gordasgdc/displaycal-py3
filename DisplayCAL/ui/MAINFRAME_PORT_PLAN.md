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

### Stage 1 — MeasureFrame (measure-frame geometry) → Qt

Port `wx_measure_frame.py::MeasureFrame` (959 lines) to
`DisplayCAL/ui/measure_frame.py`. This is the shared dependency that unblocks
**three** already-ported tools:

- testchart editor's deferred image/DPX pattern export,
- the visual whitepoint editor's **Measure** button,
- the whitepoint editor's pattern-generator patch output.

Geometry persists to the Pile-3 `dimensions.measureframe*` /
`measureframe.*` config keys, so the Qt frame stays interchangeable with the wx
one. Self-contained (no giant `MainFrame` dependency), so it's a clean first
Qt slice. **Verify** headless + against the three consuming tools.

### Stage 2 — Measurement flow orchestration

Port `setup_measurement`, `setup_patterngenerator`, the `measureframe`
subprocess trio (`start_measureframe_subprocess`, `measureframe_subprocess`,
`measureframe_consumer`), `setup_observer_ctrl`, `set_pending_function` /
`call_pending_function`, against the Stage-0 extracted settings. No full main
window yet — expose it as the engine the Qt main window and tools drive.

### Stage 3 — Qt main window shell + settings tabs

Build `DisplayCAL/ui/main_window.py` (`MainWindow(BaseWindow)`): the tabbed
layout, menubar, display/instrument selectors, and the calibration/profiling
settings controls, wired to the Stage-0 settings module and Stage-2 flow.
Embeds the already-ported tool panels (curve viewer's `CurvePanel`, profile
info, etc.) where the wx UI opens child frames. Gated behind `--qt`.

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
