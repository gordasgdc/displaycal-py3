# Changelog

## 3.10.0.dev82-cg.7

- Windows: the profile loader (the tray component that applies your calibration when you sign in) no longer stops at start-up with an error, applies the calibration curves, and keeps running when you open its tray menu.
- Windows: the installer now sets up the sign-in task and your choice of who loads the calibration reliably.

## 3.10.0.dev82-cg.6

- New look across the application, in light and dark: ivory and graphite surfaces, satin selectors and buttons with fine edges, a compact header with the symbol and a discreet spectral line, five steps shown as numbered circles with the current step highlighted, a clean product image of a monitor, and quieter secondary text. Fonts Archivo and B612 Mono (SIL Open Font License) are bundled.
- The first screen is rebuilt: monitor and instrument on the left, the product image on the right; the model of the instrument is asked only when the system cannot tell, and the detection line says only what is known.
- The measurement plan shows the blocks as a slim strip next to the totals and the time estimate.
- During a run the progress window stays dark in both appearances and nothing in it moves: a static bar, the elapsed time and the estimate. The measurement itself is unchanged.
- Status colours (warning, error, OK) are readable in light and dark.
- Guides (Romanian, English, Spanish) redesigned: each guided step is one page with what you do, why, and what you check; new screenshots of the new interface; real, searchable text; contents with page numbers.

## 3.10.0.dev82-cg.4

- New **Guided calibration** tab (default): five steps from a connected instrument to a verified profile, with honest labels for what was detected and what you confirmed.
- Instrument identification that does not guess: when several models share one USB identity you confirm the exact model; model-specific placement help only where the maker documents it.
- Physical-preparation checklist with sources and, for documented instruments, a short placement animation with text steps and reduced-motion support.
- Measurement plan before you start: profile type explained in plain language, patch count, estimated time.
- Measurement in blocks with recovery: large charts can be measured in blocks that are saved locally as they finish; after an interruption the finished blocks are kept and the run can be continued with the remaining blocks when the conditions are the same (recovery is not guaranteed in every situation); a session journal records facts about how a run ended; start-up recovery window; sleep prevention only while a run is active; a local notification at the end. Sessions of several hours have not been validated yet.
- ArgyllCMS is now included in the installer and verified against a fixed hash; unverifiable downloads are refused.
- After installing a profile, the active profile is read back and compared.
- Fixed a crash at exit on macOS.
- Voluntary support: star the project on GitHub or send feedback (opens a pre-filled issue in your browser; nothing is sent by the app).
- Qt is now the default interface; the previous interface remains available.
- Guides (Romanian, English, Spanish) rewritten for the guided flow.
- Diagnostic and support (Help menu): open the log folder, see versions, copy the session ID, optional detailed logging for the current run, and export a diagnostic package you can read and send yourself (nothing is uploaded). Logs rotate and are size-limited; personal data is removed from text by default; measurements, ICC profiles and system crash reports are added only if you choose them.
- Log lines now carry an ISO time with offset, a level and a run ID; an unexpected stop is noted at the next start.
- Advanced settings are now grouped by decision. Each section says what each setting changes, when it fits, its unit and default, what it depends on and why a control is unavailable; the guided and advanced modes share one configuration, and a new goal keeps your current settings. The test chart editor explains its fields.
- New link beside the correction choice: "Don't know your monitor's technology? Search the model" (model identifier for built-in Apple screens, copy-and-open for other monitors; nothing is selected for you).
- Text size (Normal / Large / Very large), remembered, live preview, with checked contrast; at a larger size the header keeps its size, the step column becomes one row and the page uses the full width. On macOS the pop-up buttons use a scalable style above Normal so their labels are not cut off.
- Filled primary button on each guided page; quieter secondary controls.
- The macOS installer now installs every file readable by normal users (some bundled files were not).
- Windows: guided flow verified on a clean Windows 11 install (ARM64 VM, x64 emulation).
