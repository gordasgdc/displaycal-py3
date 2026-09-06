# ghid_en.py — DisplayCAL-CG user guide content (English).
# Declarative structure read by `_engine.build()` — see there for the
# accepted block types ("p", "h2", "ul", "code", "img", "steps", "opt",
# "info"/"warn"/"ok", "pagebreak").

CONTENT = {
    "title": "DisplayCAL-CG User Guide",
    "subtitle": "Monitor calibration and profiling, step by step — GDC edition",
    "note": "Document version 1.0 · based on DisplayCAL-CG 3.10.0.dev82",
    "toc_title": "Contents",
    "cover_subtitle": "Display calibration and characterization powered by ArgyllCMS",
    "cover_version_label": "App version",
    "cover_lang_label": "English edition",
    "footer": "DisplayCAL-CG — User Guide (EN)",
    "sections": [
        {
            "h": "What is DisplayCAL-CG",
            "blocks": [
                ("p", "DisplayCAL-CG is a GDC edition of the open-source "
                       "<b>DisplayCAL</b> project (the community continuation "
                       "of Florian Höch's original work), repackaged and "
                       "fully translated by GDC. The application calibrates "
                       "and profiles your monitor using the <b>ArgyllCMS</b> "
                       "measurement engine — the result is a monitor with "
                       "correct, consistent colors no matter which "
                       "application you're working in (photo, video, "
                       "graphics)."),
                ("info", ("Calibration vs. profiling — what's the difference",
                          "<b>Calibration</b> brings the monitor to a known "
                          "target state (white point, luminance, tone curve) "
                          "through hardware/software adjustments (the video "
                          "card's curves). <b>Profiling</b> then measures how "
                          "the calibrated monitor responds and writes an "
                          "<b>ICC profile</b> that the rest of the system "
                          "uses for accurate color correction. They're "
                          "always done one after the other, in this order.")),
                ("p", "This guide walks through each of the 5 main tabs "
                       "(Display & instrument, Calibration, Profiling, "
                       "3D LUT, Verification), the advanced tools available "
                       "from the menus, and how to install/update the "
                       "application on Mac and Windows."),
                ("warn", ("You need a measurement device",
                          "DisplayCAL-CG CANNOT calibrate a monitor without "
                          "a physical colorimeter or spectrophotometer "
                          "connected via USB (e.g. X-Rite i1Display Pro, "
                          "ColorMunki Display, Datacolor Spyder). The app "
                          "auto-detects the connected device on the "
                          "\"Display & instrument\" tab.")),
            ],
        },
        {
            "h": "Installation",
            "blocks": [
                ("h2", "macOS"),
                ("steps", [
                    "Download the <b>DisplayCAL-CG.pkg</b> package from the "
                    "download page (gordas.dev/DisplayCAL-CG).",
                    "Double-click the downloaded <b>.pkg</b> file.",
                    "In the installer window, click <b>Continue</b> on each "
                    "step until you reach the <b>License</b> page.",
                    "Read the GPLv3 license summary shown, click "
                    "<b>Agree</b> (without explicit acceptance, the install "
                    "cannot proceed — this is a requirement of the native "
                    "macOS installer, not an optional step).",
                    "Click <b>Install</b> — the app and all 9 satellite "
                    "tools (Profile Info, Curve Viewer, etc.) are installed "
                    "directly into <b>Applications</b>, nothing to drag "
                    "manually.",
                    "Open <b>DisplayCAL-CG</b> from Launchpad/Applications.",
                ]),
                ("info", ("The package is Apple-signed and notarized",
                          "macOS Gatekeeper will let the app launch "
                          "directly, without the \"cannot be opened because "
                          "it is from an unidentified developer\" warning.")),
                ("h2", "Windows"),
                ("steps", [
                    "Download the <b>DisplayCAL-CG-Setup.exe</b> installer "
                    "from the download page.",
                    "Double-click the downloaded file.",
                    "If the <b>Windows SmartScreen</b> warning appears "
                    "(\"Windows protected your PC\"), click <b>More info</b>, "
                    "then <b>Run anyway</b>.",
                    "On the installer's license page, select <b>I accept "
                    "the agreement</b> — the \"Next\" button stays disabled "
                    "until you check this.",
                    "Follow the installer's steps (the default location is "
                    "recommended) through to <b>Install</b>.",
                    "Open <b>DisplayCAL-CG</b> from the Start Menu or the "
                    "Desktop shortcut.",
                ]),
                ("warn", ("Why the SmartScreen warning appears",
                          "The Windows installer isn't (yet) signed with a "
                          "paid code-signing certificate — the warning is "
                          "normal for unsigned software, not a sign that "
                          "the file is unsafe. Only download it from the "
                          "official page above.")),
            ],
        },
        {
            "h": "Display & instrument",
            "blocks": [
                ("p", "The first tab — pick WHICH monitor you're calibrating "
                       "and WITH WHICH instrument. The app needs to know "
                       "both before you can move on to Calibration."),
                ("img", ("monitor_instrument_full.png",
                        "The Display & instrument tab, with an external "
                        "monitor and an i1DisplayPro colorimeter already "
                        "detected.")),
                ("opt", (("Field", "What it does"), [
                    ("Display", "Pick the monitor to calibrate from the "
                                "list if you have more than one connected. "
                                "The round ↻ button next to it rescans "
                                "connected displays."),
                    ("Instrument", "The colorimeter/spectrophotometer "
                                   "detected via USB. If it's empty, check "
                                   "the USB cable and that the instrument "
                                   "is recognized by the operating system."),
                    ("Measurement mode", "The instrument's measurement mode "
                            "— \"Refresh (generic)\" suits most LCD/LED "
                            "monitors. Some instruments (K-10, Spyder4/5/X) "
                            "offer precalibrated modes for specific display "
                            "types — pick the closest match if one exists."),
                    ("White level drift compensation", "Enable if the "
                            "display is an OLED/Plasma TV or another type "
                            "with variable light output depending on "
                            "on-screen content."),
                    ("Black level drift compensation", "Enable if you're "
                            "using a spectrometer in contact mode on a "
                            "display with an unstable black level."),
                    ("Output levels", "\"Auto\" is correct in nearly all "
                            "cases. \"TV RGB 16-235\" only applies if the "
                            "display/video card deliberately limits the "
                            "signal range, as with a TV used as a monitor."),
                    ("Correction", "The instrument+display specific color "
                            "correction — DisplayCAL-CG picks it "
                            "automatically (\"Auto (Spectral: ...)\") when "
                            "it can; don't change it manually unless you "
                            "know exactly what you're doing."),
                ])),
                ("info", ("Before you measure",
                          "Let the display warm up for <b>at least 30 "
                          "minutes</b> before calibrating — a cold monitor's "
                          "colors drift as it stabilizes thermally. Turn off "
                          "any dynamic picture settings (dynamic contrast, "
                          "auto brightness) and avoid light falling directly "
                          "on the screen during measurement.")),
            ],
        },
        {
            "h": "Calibration",
            "blocks": [
                ("p", "The second tab — choose WHAT target state you want "
                       "for the display: what white point, what luminance, "
                       "what tone curve."),
                ("img", ("calibrare_full.png",
                        "Default calibration settings (Gamma 2.2, white "
                        "point and levels \"as measured\").")),
                ("opt", (("Field", "What it does"), [
                    ("Interactive display adjustment", "When checked, the "
                            "app guides you to manually adjust the "
                            "monitor's physical controls (brightness, "
                            "contrast, RGB) during calibration, to get as "
                            "close as possible to the target before "
                            "generating the software curves."),
                    ("Observer", "The CIE standard used to interpret color "
                            "— \"CIE 1931 2°\" is the default, suitable for "
                            "the vast majority of situations."),
                    ("White point", "\"As measured\" keeps the display's "
                            "native white point. You can instead pick a "
                            "fixed color temperature (e.g. 6500K/D65) if "
                            "you need to hit an exact standard, with a "
                            "reference (\"Daylight\"/\"Black body\")."),
                    ("White level / Black level", "\"As measured\" keeps "
                            "the display's native luminance. You can set a "
                            "fixed value manually (e.g. 120 cd/m²) if you "
                            "need to meet a luminance standard."),
                    ("Tonal response curve", "The shape the resulting tone "
                            "response will have — \"Gamma 2.2\" is the "
                            "default fit for photo/web; \"Rec. 1886\" or "
                            "other curves matter mostly for video."),
                    ("Black output offset", "0% = \"pure\" black; 100% = "
                            "black follows the chosen curve exactly with no "
                            "offset. In-between values compensate for "
                            "displays with elevated black levels."),
                    ("Black point correction", "The rate/percentage used to "
                            "correct near-black nonlinearities — \"Auto\" "
                            "lets the app decide."),
                    ("Calibration speed", "A time/accuracy trade-off — "
                            "\"High\" (default) is enough for most uses."),
                ])),
                ("warn", ("1D LUT calibration doesn't replace an ICC profile",
                          "The curves generated here only correct the "
                          "display's overall tonality — for full color "
                          "correction you also need a <b>device ICC "
                          "profile</b> or a <b>3D LUT</b>, created in the "
                          "following tabs.")),
            ],
        },
        {
            "h": "Profiling",
            "blocks": [
                ("p", "The third tab — DisplayCAL-CG displays actual color "
                       "patches on screen, measures them with the "
                       "instrument, and builds the <b>ICC profile</b> that "
                       "characterizes your now-calibrated display."),
                ("img", ("profilare_full.png",
                        "Profiling settings — \"Single curve + matrix\" "
                        "profile type, auto-optimized testchart, 34 "
                        "patches.")),
                ("opt", (("Field", "What it does"), [
                    ("Profile type", "\"Single curve + matrix\" is fast and "
                            "sufficient for many good displays; a "
                            "<b>LUT</b>-based profile with hundreds to "
                            "thousands of patches gives the best possible "
                            "accuracy, but takes much longer."),
                    ("Black point compensation", "Recommended checked — "
                            "improves accuracy in dark areas."),
                    ("Profile quality", "Low→High slider — affects how "
                            "finely the profile is computed from the "
                            "measured data, not the number of patches."),
                    ("Testchart", "\"Auto-optimized\" automatically picks "
                            "patch distribution accounting for your "
                            "display's actual nonlinearities — recommended "
                            "for the best results."),
                    ("Number of patches", "The slider controls how many "
                            "patches get measured — more patches = a more "
                            "accurate profile, but a longer measurement."),
                    ("Patch order", "\"Minimize display response delay\" "
                            "orders the patches to shorten total "
                            "measurement time."),
                    ("Profile name", "The automatic naming template — you "
                            "can freely edit the field below if you want a "
                            "custom profile name."),
                ])),
                ("info", ("How long it takes",
                          "The app shows an estimated time under the "
                          "profiling settings (e.g. \"about 1 minute\" for "
                          "34 patches) — a LUT-based profile with thousands "
                          "of patches can take anywhere from a few minutes "
                          "to over an hour.")),
            ],
        },
        {
            "h": "3D LUT",
            "blocks": [
                ("p", "An optional tab — generates a <b>3D LUT</b> (a "
                       "three-dimensional lookup table) from the profile "
                       "already created, for applications that support "
                       "color correction via 3D LUT instead of an ICC "
                       "profile (common in video/color-grading workflows — "
                       "DaVinci Resolve, media players)."),
                ("img", ("lut3d_full.png",
                        "3D LUT settings — Rec709 source, Rec.1886 curve, "
                        "IRIDAS .cube format, 65×65×65 resolution.")),
                ("opt", (("Field", "What it does"), [
                    ("Create 3D LUT after profiling", "Check this if you "
                            "want the LUT to be generated automatically "
                            "right after profiling finishes, as one "
                            "continuous step."),
                    ("Source colorspace", "The colorspace of the material "
                            "you'll be playing back (e.g. \"Rec709 ITU-R "
                            "BT.709\" for standard HD video)."),
                    ("Tone curve", "Must match the source material's "
                            "standard — HD video typically uses either a "
                            "~2.2-2.4 power curve or \"Rec. 1886\"."),
                    ("Gamut mapping mode", "\"Inverse device-to-PCS\" is "
                            "the standard choice for a display LUT (not a "
                            "content-conversion LUT)."),
                    ("Rendering intent", "\"Absolute colorimetric with "
                            "white point scaling\" is recommended if you "
                            "haven't explicitly calibrated to the source "
                            "material's white point."),
                    ("3D LUT file format", "IRIDAS .cube is the most widely "
                            "compatible (Resolve, most media players); "
                            "other formats exist for specific software."),
                    ("3D LUT resolution", "65×65×65 is a good "
                            "accuracy/file-size trade-off — higher "
                            "resolutions increase both precision and file "
                            "size."),
                ])),
                ("warn", ("Use the SAME settings the LUT was created with",
                          "When later verifying an already-created 3D LUT "
                          "(Verification tab), make sure you use exactly "
                          "the same settings (source space, curve, "
                          "rendering intent) — otherwise the verification "
                          "result is meaningless.")),
            ],
        },
        {
            "h": "Verification",
            "blocks": [
                ("p", "The fifth tab — checks how accurate an already "
                       "created ICC profile or 3D LUT is, via a measurement "
                       "report with statistics on the color errors measured "
                       "across a set of patches."),
                ("img", ("verificare.png",
                        "Verification settings — extended verification "
                        "testchart, 51 patches, ~2 minutes estimated.")),
                ("opt", (("Field", "What it does"), [
                    ("Testchart or reference", "The patch set used for "
                            "verification — \"Extended verification "
                            "testchart\" is a standard set, independent of "
                            "the one used for profiling (otherwise the "
                            "verification would be biased)."),
                    ("Simulate white point", "Compares the result relative "
                            "to a simulated white point, instead of the "
                            "display's native one."),
                    ("Relative to display profile white point", "Similar to "
                            "the above, but relative to the white point "
                            "RECORDED in the current profile."),
                    ("Simulation profile", "Optional — checks how the "
                            "display would behave if it simulated another "
                            "profile/colorspace."),
                ])),
                ("steps", [
                    "Pick the verification testchart (the default suits "
                    "almost every case).",
                    "Click <b>Measurement report...</b> at the bottom of "
                    "the window.",
                    "Follow the instrument on screen as the app displays "
                    "and measures the test patches one by one.",
                    "At the end, a report opens with the average/maximum "
                    "color errors measured (ΔE) — the lower the ΔE, the "
                    "more accurate the profile.",
                ]),
                ("info", ("Tip",
                          "Hold down the <b>ALT</b> key on your keyboard "
                          "when clicking \"Measurement report...\" to "
                          "create a <b>self-check</b> report instead of a "
                          "regular measurement report.")),
            ],
        },
        {
            "h": "Advanced tools",
            "blocks": [
                ("p", "Besides the main workflow (the 5 tabs above), "
                       "DisplayCAL-CG includes several standalone tools, "
                       "useful for special cases — accessible from the main "
                       "app's menu or as separate applications installed "
                       "alongside it."),
                ("h2", "Create synthetic ICC profile"),
                ("img", ("creeaza_profil_sintetic.png",
                        "The synthetic ICC profile creation tool, built "
                        "from manually described parameters (not from real "
                        "measurements).")),
                ("p", "Builds an ICC profile from manually described "
                       "parameters (white point, gamma, color primaries) — "
                       "useful for generating a theoretical reference "
                       "profile without measuring a real display (e.g. for "
                       "simulation or testing)."),
                ("h2", "Create 3D LUT (standalone)"),
                ("img", ("creeaza_lut3d_standalone.png",
                        "The standalone 3D LUT creation tool, for "
                        "converting between colorspaces without going "
                        "through a full display-calibration workflow.")),
                ("p", "The same 3D LUT generation logic as the \"3D LUT\" "
                       "tab, but run independently of any display "
                       "calibration workflow — useful for converting "
                       "between two arbitrary profiles/colorspaces."),
                ("h2", "Profile Info"),
                ("img", ("profile_info.png",
                        "The Profile Info window — complete information "
                        "about an ICC profile, plus a graphical "
                        "representation of its gamut.")),
                ("p", "Opens any ICC profile (created by DisplayCAL-CG or "
                       "from another source) and shows all the information "
                       "it contains — white point, tone curve, color "
                       "primaries — plus a 3D graphical representation of "
                       "the covered color gamut."),
                ("h2", "Curves"),
                ("img", ("curbe.png",
                        "The Curves window — a visualization of the "
                        "calibration curves (vcgt) currently loaded into "
                        "the video card.")),
                ("p", "Graphically shows the calibration curves (VCGT — "
                       "Video Card Gamma Table) currently loaded into the "
                       "video card — useful for a quick visual check of "
                       "what calibration is active right now."),
                ("h2", "Log"),
                ("img", ("jurnal.png",
                        "The Log window — the detailed technical log of "
                        "the ArgyllCMS operations behind the application.")),
                ("p", "The detailed technical log of the ArgyllCMS commands "
                       "run behind the scenes by the app — mainly useful "
                       "for troubleshooting if something isn't working as "
                       "expected and you want to understand exactly what "
                       "happened."),
            ],
        },
        {
            "h": "GPLv3 license & optional support",
            "blocks": [
                ("ok", ("100% free, forever",
                        "DisplayCAL-CG is free software, licensed under "
                        "GPLv3 — fully functional from day one, no "
                        "activation, no time-limited trial, no feature "
                        "locked behind a payment. You can install, use and "
                        "redistribute the application freely, subject to "
                        "the included GPLv3 license terms (LICENSE.txt).")),
                ("p", "DisplayCAL-CG is built on the open-source work of "
                       "DisplayCAL (Florian Höch) and its community "
                       "continuators — full credits remain visible in the "
                       "app (Help → About)."),
                ("p", "If the app has been useful to you, an optional "
                       "support message appears occasionally in the "
                       "application — it's purely informational, never a "
                       "requirement to use any feature."),
            ],
        },
        {
            "h": "Updates",
            "blocks": [
                ("p", "DisplayCAL-CG automatically checks at startup "
                       "whether a newer version is available on the "
                       "download page. You can also check manually from "
                       "the Help menu."),
                ("steps", [
                    "If a new-version notification appears, click the link "
                    "in it — it takes you straight to the download page "
                    "with the latest version.",
                    "Download the new package (.pkg on Mac, .exe on "
                    "Windows).",
                    "Install it over the current version, exactly as with "
                    "the first install (see the \"Installation\" chapter) "
                    "— your settings and already-created profiles remain "
                    "untouched.",
                    "Restart the application after installing.",
                ]),
            ],
        },
    ],
}
