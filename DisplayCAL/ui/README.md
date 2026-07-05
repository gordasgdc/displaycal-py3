# DisplayCAL Qt UI (`DisplayCAL.ui`)

This package is the **Qt** user interface for DisplayCAL 4.0. It is the
successor to the legacy `wx_*` modules, which are being phased out gradually.

## Coexistence strategy

The migration is **additive**: the wxPython code path is left untouched and
keeps working, while a parallel Qt path is built up here, module by module.
Nothing is deleted until its Qt replacement is in place and verified. This lets
the app ship and run throughout the multi-month migration.

Selecting the UI toolkit is controlled by an environment variable / CLI flag
(see `DisplayCAL.config.get_ui_toolkit`):

- default → **wx** (unchanged behaviour)
- `DISPLAYCAL_UI=qt` or `--qt` → **Qt**, where a Qt port exists

Entry points consult this flag and dispatch to the Qt implementation only for
modules that have been ported; everything else still falls through to wx.

## Binding policy

- We use **qtpy** as the abstraction layer; **PySide6** is the default and only
  shipped/tested binding.
- `DisplayCAL/ui/__init__.py` pins `QT_API=pyside6` *before* qtpy is imported.
- Always import Qt symbols from `qtpy.*`, **never** from `PySide6.*` directly.

## Layout

| Module | Role | wx equivalent |
| --- | --- | --- |
| `__init__.py` | binding pin (`QT_API`) | — |
| `application.py` | `Application(QApplication)`: exit handlers, argv/file-open, SIGINT | `wx_windows.BaseApp` |
| `base_window.py` | `BaseWindow(QMainWindow)`: icon, geometry persistence, menubar | `wx_windows.BaseFrame` (essentials) |
| `scripting.py` | `ScriptingHostMixin`: scripting/IPC socket server | `wx_windows.BaseFrame` (`listen`/`message_handler`/…) |
| `assets.py` | themed PNG → `QIcon`/`QPixmap` | `config.get_icon*` |
| `file_drop.py` | `FileDropTarget` event filter (suffix→handler) | `wx_addons.FileDrop` |
| `theme.py` | OS light/dark detection + plot colours | wx `BGCOLOUR`/`FGCOLOUR`/`GRIDCOLOUR` |
| `plot/` | pyqtgraph-based plotting (gamut view + colorimetry) | `wx_enhanced_plot`, `GamutCanvas` |
| `tools/` | standalone tools (one window + `main()` each) | `wx_*` tool modules |

## Theming (`theme.py`)

The legacy wx UI is hard-coded to a dark scheme (`BGCOLOUR = "#333333"`,
`FGCOLOUR = "#999999"`, `GRIDCOLOUR = "#444444"`) regardless of the OS. The Qt
UI instead **follows the operating system's light/dark preference**: the native
Qt style themes the window chrome (panels, combos, labels, the info panel) from
the OS automatically, so `theme.py` only supplies what pyqtgraph can't derive —
the plot background/grid/axis/locus colours, picked from the *current* palette
via `plot_colors(widget)`. In dark mode these mirror the old wx values; in light
mode they invert to a light canvas. Plots re-theme live on OS-theme change (see
each plot widget's `changeEvent`). Per-datum colours (RGB curve pens in
`CHANNEL_COLORS`, gamut-hull vertex colours) are inherent to the data and stay
constant in both schemes.

### Plotting (`plot/`)

2D plotting uses **pyqtgraph** (axes, grid, zoom/pan, item rendering). The
DisplayCAL-specific parts live here:

- `plot/colorspaces.py` — registry of gamut projections (axis labels, view
  range, XYZ→2D, outline curves), replacing the big `if/elif` ladder in
  `GamutCanvas.DrawCanvas`.
- `plot/gamut.py` — `GamutPlot(pg.PlotWidget)`, the gamut renderer.
- `plot/gamut_data.py` — binding-agnostic gamut sampling via Argyll `xicclu`,
  extracted from `GamutCanvas.setup`.
- `plot/curve.py` — `CurvePlot(pg.PlotWidget)`, per-channel tone-curve renderer.
- `plot/curve_data.py` — extracts `vcgt` and `*TRC` curves from a profile
  (no Argyll), and computes the *measured* tone response live via `xicclu`
  (`measured_tone_response`), all normalised to the unit square.

## Migration pattern (follow `tools/vrml_to_x3d.py`)

`tools/vrml_to_x3d.py` is the **reference vertical slice**. When porting a wx
module:

1. **Keep the backend.** Logic in non-wx modules (`x3dom`, `cgats`,
   `icc_profile`, `colormath`, `config`, `localization`, `util_*`, …) is
   binding-agnostic — call it directly, don't reimplement it.
2. **Subclass the Qt base classes** (`BaseWindow`, `Application`) instead of the
   wx ones. Drop wx-only workarounds (`wx_fixes`, custom DPI/Wayland hacks,
   manual `Fit`/`SetMinSize` juggling); Qt's layouts handle these.
3. **Run long work off the GUI thread** with a small `QThread` that emits a
   result signal (see `_ConversionThread`), rather than the heavyweight
   `worker.Worker` + custom progress dialog. Reach for `worker.Worker` only when
   you genuinely need its Argyll subprocess/progress machinery.
4. **Load assets** via `DisplayCAL.ui.assets`, not the wx `config.get_icon*`
   helpers.
5. **Keep the console / `--no-gui` path** delegating to the existing wx module's
   non-GUI code where one exists, so nothing regresses.
6. **Verify headless**: `QT_QPA_PLATFORM=offscreen python -m
   DisplayCAL.ui.tools.<name>` plus a scripted construct-and-exercise check.

## Ported tools

- **VRML-to-X3D converter** (`tools/vrml_to_x3d.py`) — complete.
- **Profile info / gamut viewer** (`tools/profile_info.py`) — complete. Gamut
  view with colorspace, white-point, rendering-intent and lookup-direction
  controls; a comparison-profile overlay (built-in standard profiles or a
  browsed one, drawn per `plot/gamut.py`'s existing index-1 styling); a
  "Curves" view that embeds `tools/curve_viewer.py`'s `CurvePanel` for the
  tone-response view; and 3D export (VRML/X3D/HTML) via
  `worker.Worker.calculate_gamut` + `x3dom.vrmlfile2x3dfile`, run on a
  `QThread`.
- **Curve viewer** (`tools/curve_viewer.py`) — complete. Calibration (`vcgt`),
  tone-response (`*TRC`) and **measured** curves (live `xicclu`, with intent,
  lookup-direction — forward/inverse/backward — and cLUT/matrix controls);
  loads `.icc`/`.icm`/`.cal`; and a "show actual LUT" toggle that reads the live
  video-card LUT back from the graphics card. The controls-and-plot view
  itself is a standalone `QWidget`, `CurvePanel`, so other tools can embed it
  (see profile-info below); `CurveViewerWindow` is a thin window wrapper
  adding the drop target and scripting.
- **Synthetic ICC creator** (`tools/synth_profile.py`) — complete. Builds RGB or
  grayscale synthetic profiles from entered colorimetry (primaries, white/black
  point, luminance) and a transfer function (gamma, BT.1886, DICOM, L*,
  Rec. 709/1886, SMPTE 240M, SMPTE 2084/PQ with optional roll-off, HLG, sRGB);
  seeds from a dropped `.icc`/`.icm`/`.ti3` or a built-in RGB-space preset; has a
  chromatic-adaptation dialog and metadata (class/technology/CIIS) controls. The
  HDR roll-off controls are inlined here rather than inherited from the large
  `LUT3DMixin`, and the slow HDR cLUT generation runs on a `QThread`.
- **3D LUT maker** (`tools/lut3d.py`) — complete. Builds a 3D LUT mapping a
  source colorspace (input profile) through to a display (output profile), with
  an optional abstract profile, TRC apply-mode (unmodified / black-offset only /
  applied tone curve: gamma 2.2, BT.1886, SMPTE 2084 hard-clip & roll-off, HLG,
  custom), HDR roll-off controls (peak/min/max mastering luminance, saturation,
  hue, ambient, content colorspace), gamut-mapping mode (inverse A2B vs. B2A),
  rendering intent, output format (`.cube`/`.3dl`/eeColor/madVR/mga/`.png`/
  ReShade/dcl/spi3d/icc), encoding, size and bit-depth. The actual Argyll
  `collink` run goes through `worker.Worker.create_3dlut` on a `QThread` with an
  indeterminate progress dialog. The standalone-tool behaviour is reimplemented
  here against the binding-agnostic backend rather than moving the wx-shared
  `LUT3DMixin` (which the still-wx main window also uses); the
  main-window-only create paths (copying an existing LUT, the non-linear
  videoLUT warning) are dropped.
- **Visual whitepoint editor** (`tools/visual_whitepoint_editor.py`) — complete.
  Pick a neutral white by eye: an HSV colour wheel plus two brightness bars
  (foreground patch and surround) drive a large colour patch, with RGB/HSV spin
  boxes for fine tuning and a "measurement area" section that sizes/positions the
  patch. The chosen RGB, background brightness and patch geometry persist to the
  same `whitepoint.visual_editor.*` /
  `dimensions.measureframe.whitepoint.visual_editor` config keys as the wx tool.
  While open, `_ProfileManager` clears the calibration on the window's display
  (installs a temporary sRGB profile via Argyll `dispwin`, restoring on
  close/display-change) and seeds the initial whitepoint from the display
  profile's `vcgt`; it is inert when no Argyll display is enumerated. The wx
  `Colour` conversion maths are reused verbatim; the custom wx spinners/sliders
  and AUI docking are replaced by native `QSpinBox`/`QSlider`, and the wheel and
  brightness bars are re-drawn in Qt `paintEvent`s. The main-window-only paths
  (the **Measure** button, which called the parent's `ambient_measure_handler`,
  and the network **pattern-generator** patch output) are dropped, to return with
  the Qt main window.
- **Testchart editor** (`tools/testchart_editor.py`) — **Stages 1-2**.
  Builds/edits Argyll TI1 charts: a patch grid (R/G/B % columns plus a colour
  swatch marked W/K/R/G/B/C/M/Y like the wx `tc_getcolorlabel`) driven by the
  `targen` parameter controls (white/black/single/gray/multi-dim/full-spread
  counts, the distribution algorithm and its adaption/angle/gamma/neutral-axis/
  dark-region emphasis). Generation runs Argyll `targen` via
  `worker.Worker.prepare_targen` (fully config-driven, binding-agnostic) on a
  `QThread`, reading `temp.ti1` back as a `CGATS`; loading (`.ti1`/`.ti3`/
  `.cgats`/`.txt`/ICC) runs on a background thread and reconstructs the control
  values from the chart's keywords; charts save as `.ti1` (`bytes(cgats)`). The
  custom wx spinners/sliders/`CustomGrid` are replaced by native
  `QSpinBox`/`QSlider`/`QTableWidget`. **Stage 2** adds the self-contained
  outputs: **CSV export** (0..100 / 0..255 / 0..1023 device-value scaling) and
  the **3D view/export** (VRML/X3D/HTML via `CGATS.export_3d`, with the
  device/CIE colorspace selection, RGB black offset, D50 normalization and gzip
  compression), both running off a `QThread` behind an indeterminate progress
  dialog. (Fixing the VRML path here surfaced a latent `write_vrml` bug —
  `out` was never assigned for `file_format == "VRML"` after the June 2025
  colorspace-to-VRML refactor — fixed in `colorspace_to_vrml.py`.) **Deferred to
  later stages** (and to the Qt main window for parent integration): the **image
  / DPX video-pattern export** (depends on the measurement-frame display geometry
  that lives in the not-yet-ported measurement flow), **saturation sweeps**,
  **TI3/CSV/image** patch import, the 23-way **patch reordering**, the
  **precondition-profile / CIE filter** controls, and exact parameter
  reconstruction for keyword-less charts.

### Scripting / IPC server (`scripting.py`)

`ScriptingHostMixin` is the Qt port of the scripting host that lived on
`wx_windows.BaseFrame`. `BaseWindow` mixes it in, so every Qt window can be
driven over the line-based TCP protocol (used by the scripting client and the
`send_command` CLI); each tool's `main()` calls `window.listen()`. The socket
lifecycle (`listen`/`connection_handler`/`message_handler`) and the non-UI
commands (`getappname`, `getcfg`, `getcommands`, `getdefault(s)`, `getvalid`,
`setresponseformat`) are carried over essentially verbatim. The only
toolkit-specific change is marshalling a received command onto the GUI thread: a
small `QObject` bridge re-emits it through a queued signal (replacing
`wx.CallAfter`). `finish_processing` handles the toolkit-agnostic / window-level
commands (`getstate`, `setcfg`, `refresh`, `restore-defaults`, `setlanguage`,
`exit`, `close`, `activate`, `getactivewindow`, `getwindows`, `echo`, `abort`)
and delegates the rest to an overridable `process_data`. The deep per-widget
introspection commands (`interact`, `getuielement(s)`, `getmenus`/
`getmenuitems`, `getcellvalues`, `invokemenu`) are inherently window-specific
and are added per window as those windows are ported.

## Not yet ported / deliberately deferred

- **The main application window** (`display_cal.MainFrame`, ~22k lines) is
  being ported in vertical, independently shippable slices tracked in
  [MAINFRAME_PORT_PLAN.md](MAINFRAME_PORT_PLAN.md). The Qt shell
  (`main_window.py`), all four settings tabs, the calibrate/measure/profile
  worker execution layer, the interactive display-adjustment window and the
  splash screen (`startup.py`) are done; still deferred: some custom widgets
  (grids, gradient buttons), several reporting/install/colorimeter-correction
  dialogs' parent-window wiring, and — until the wx and Qt paths are confirmed
  behaviourally identical — retiring the wx code paths themselves.
