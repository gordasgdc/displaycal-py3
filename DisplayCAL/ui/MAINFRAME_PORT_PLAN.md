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
