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
| `plot/` | pyqtgraph-based plotting (gamut view + colorimetry) | `wx_enhanced_plot`, `GamutCanvas` |
| `tools/` | standalone tools (one window + `main()` each) | `wx_*` tool modules |

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
- **Profile info / gamut viewer** (`tools/profile_info.py`) — gamut view with
  colorspace + white-point controls, profile load/drop, info panel. Still to
  add: tone-response-curve view, profile comparison overlay,
  rendering-intent/direction controls, 3D/VRML export.
- **Curve viewer** (`tools/curve_viewer.py`) — complete. Calibration (`vcgt`),
  tone-response (`*TRC`) and **measured** curves (live `xicclu`, with intent,
  lookup-direction — forward/inverse/backward — and cLUT/matrix controls);
  loads `.icc`/`.icm`/`.cal`; and a "show actual LUT" toggle that reads the live
  video-card LUT back from the graphics card.
- **Synthetic ICC creator** (`tools/synth_profile.py`) — complete. Builds RGB or
  grayscale synthetic profiles from entered colorimetry (primaries, white/black
  point, luminance) and a transfer function (gamma, BT.1886, DICOM, L*,
  Rec. 709/1886, SMPTE 240M, SMPTE 2084/PQ with optional roll-off, HLG, sRGB);
  seeds from a dropped `.icc`/`.icm`/`.ti3` or a built-in RGB-space preset; has a
  chromatic-adaptation dialog and metadata (class/technology/CIIS) controls. The
  HDR roll-off controls are inlined here rather than inherited from the large
  `LUT3DMixin`, and the slow HDR cLUT generation runs on a `QThread`.

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

- **The main application window** (`display_cal.MainFrame`, ~22k lines) and its
  custom widgets (grids, gauges, gradient buttons, LUT/plot views). This is the
  bulk of the work and will be tackled in dedicated, refactored pieces — large
  methods broken into smaller ones as they move.
