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
| `assets.py` | themed PNG → `QIcon`/`QPixmap` | `config.get_icon*` |
| `file_drop.py` | `FileDropTarget` event filter (suffix→handler) | `wx_addons.FileDrop` |
| `tools/` | standalone tools (one window + `main()` each) | `wx_*` tool modules |

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

## Not yet ported / deliberately deferred

- **Scripting/IPC socket server** (`BaseFrame.listen`/`connection_handler`/
  `message_handler`): binding-agnostic; will move to a reusable mixin when the
  first window that needs it (the main window or scripting client) is ported.
- **The main application window** (`display_cal.MainFrame`, ~22k lines) and its
  custom widgets (grids, gauges, gradient buttons, LUT/plot views). This is the
  bulk of the work and will be tackled in dedicated, refactored pieces — large
  methods broken into smaller ones as they move.
