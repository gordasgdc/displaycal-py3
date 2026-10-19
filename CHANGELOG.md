# Changelog

## 3.10.0.dev82-cg.4

- New **Guided calibration** tab (default): five steps from a connected instrument to a verified profile, with honest labels for what was detected and what you confirmed.
- Instrument identification that does not guess: when several models share one USB identity you confirm the exact model; model-specific placement help only where the maker documents it.
- Physical-preparation checklist with sources and, for documented instruments, a short placement animation with text steps and reduced-motion support.
- Measurement plan before you start: profile type explained in plain language, patch count, estimated time.
- Safer long runs: large charts can be measured in blocks that are saved as they finish; an interrupted run can be continued with the remaining blocks when the conditions are the same; a session journal records facts about how a run ended; start-up recovery window; sleep prevention only while a run is active; a local notification at the end.
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
- TODO parity: Windows build verification of the new flow pending.
