# guided_sections.py — chapters about the guided flow, shared by the three guides.
# Everything stated here is what the application actually does; see
# DisplayCAL/guide_model.py, instrument_catalog.py, session_journal.py.
# `sections(lang)` returns section dicts for `_engine.build()`.

_T = {
    "en": {
        "guided": {
            "h": "Guided calibration (5 steps)",
            "blocks": [
                ("p", "The first tab, <b>Guided calibration</b>, takes you from a "
                      "connected instrument to a verified profile in five steps. "
                      "All advanced options stay available in the other tabs."),
                ("steps", [
                    "<b>Monitor and instrument</b> — the application shows what "
                    "it detected. Some instruments share one USB identity "
                    "(for example the i1 DisplayPro and ColorMunki Display), so "
                    "it cannot tell the exact model by itself: you confirm it, "
                    "and every line says whether it was <i>detected by the "
                    "system</i> or <i>confirmed by you</i>.",
                    "<b>Your goal</b> — pick the purpose (photo, video, general "
                    "use…). Each goal maps to a ready-made preset.",
                    "<b>Preparation</b> — a short checklist for the things the "
                    "software cannot do for you (see below). Nothing is ticked "
                    "automatically.",
                    "<b>Measurement</b> — a summary of what will happen, the "
                    "measurement plan, and the start button.",
                    "<b>Install and verify</b> — opens only after a valid "
                    "profile exists. After installing, the application reads "
                    "back the active profile and tells you whether it is really "
                    "the one that was just created.",
                ]),
                ("info", ("Text size",
                          "The <b>Aa</b> button (also in the Options menu) sets "
                          "the text size: Normal, Large or Very large. It starts "
                          "from the size your system uses, applies at once to "
                          "the whole application including explanations and "
                          "dialogs, and can be reset to the default. It changes "
                          "only the text of the application; the measurement "
                          "window, the patch size and colours are not affected."
                          )),
                ("info", ("If something is missing",
                          "When ArgyllCMS, a display or an instrument is not "
                          "found, the first step says so plainly and what to do. "
                          "The Argyll engine is included in the installer "
                          "(verified against a fixed SHA-256 hash); if a download "
                          "is ever needed, a file that does not match the expected "
                          "hash is refused.")),
            ],
        },
        "prep": {
            "h": "Physical preparation",
            "blocks": [
                ("p", "Before measuring, the checklist covers the monitor "
                      "(stable, final settings), the room (no light falling on "
                      "the screen), and the instrument (correct placement, "
                      "cable, cap). Each item has a short <i>why</i> with its "
                      "sources, and you tick them yourself."),
                ("warn", ("No universal warm-up time",
                          "There is no single warm-up time valid for every "
                          "monitor. The application does not invent one: it "
                          "shows a figure only when the instrument maker "
                          "publishes it (for example 30 minutes for Datacolor "
                          "SpyderX), and presents it as that maker's "
                          "recommendation.")),
                ("p", "For the instruments whose placement is documented by "
                      "the maker (Calibrite ColorChecker Display, Pro, Plus and "
                      "Datacolor SpyderX) a short animation shows the steps, with "
                      "a text version of each step; play/pause and previous/next "
                      "buttons control it, and it respects the system “reduce "
                      "motion” setting. For other instruments the steps are "
                      "generic and say so. The animation always stops before "
                      "measurement starts; the measurement window itself shows "
                      "only neutral patches."),
            ],
        },
        "plan": {
            "h": "Measurement plan and long sessions",
            "blocks": [
                ("p", "Step 4 shows the plan before anything starts, with three "
                      "numbers kept apart: the <b>total patches in the chart</b>, "
                      "the <b>largest block</b> and the <b>number of blocks</b> "
                      "(for example “11,000 patches in total · blocks of at most "
                      "500 · about 22 blocks”), plus the estimated time. The same "
                      "plan appears in the Profiling tab, and the button "
                      "<b>Choose or create a chart</b> beside the total opens the "
                      "chart file chooser or the chart editor. The block size "
                      "never changes the total: it only decides how the same "
                      "chart is cut into pieces."),
                ("ul", [
                    "<b>Profile type</b> — a matrix profile (one shared curve "
                    "or per-channel curves) is small and predictable; a LUT "
                    "profile (XYZ or Lab) describes more of the screen's "
                    "behaviour but needs more patches. The profile type, the "
                    "calibration curves and the measurement chart are three "
                    "different things: curves adjust the monitor, the chart is "
                    "what is measured, the type is how the result is described "
                    "to applications. <i>Macs:</i> on macOS 10.8 or newer the "
                    "application asks once if the type is anything other than "
                    "single curve + matrix with black point compensation, "
                    "because, according to the original project, applications "
                    "that use Apple's own colour module (Preview, Quick Look) "
                    "may show black crush and posterization with other display "
                    "profile types. It is a question, not a ban: Yes switches, "
                    "No keeps your choice. Applications with their own colour "
                    "management (Adobe, GIMP, Krita) and workflows using a 3D "
                    "LUT are not affected. More patches is not automatically "
                    "better: it costs time, lets the display drift and only "
                    "helps where the profile type can use it; verify the "
                    "result afterwards.",
                    "<b>Calibration vs profiling</b> — calibration adjusts the "
                    "screen towards a target; profiling measures it and writes "
                    "the ICC profile. The chart (the set of patches) belongs to "
                    "profiling.",
                    "<b>Safe long run (blocks)</b> — a large chart can be "
                    "measured in blocks of at most 100, 250, 500, 1000 or 2000 patches "
                    "(or another size you type). There is no fixed upper limit "
                    "on the chart itself: charts of 11,000 patches or more can "
                    "be measured this way. A finished block is saved to disk; if the run is "
                    "interrupted, only the block in progress is lost. Each "
                    "block repeats the white reference, so the run needs one "
                    "extra white reading per block after the first (shown "
                    "separately) and re-initialises the instrument between "
                    "blocks. The time estimate uses the speed this instrument "
                    "really had in earlier runs on this computer when there is "
                    "such a history, otherwise its specification, and says "
                    "which; it is never a guarantee. Instruments that need "
                    "their own calibration cycle measure in one run.",
                    "<b>Keep the computer awake</b> — on by default, only for "
                    "the duration of the run, released at the end. It cannot "
                    "prevent: closing the lid, choosing Sleep, the power "
                    "button, a flat battery, locking the screen or switching "
                    "user. Keep the computer plugged in and the session "
                    "unlocked.",
                ]),
                ("p", "At the end of a long run the application shows a local "
                      "notification (nothing leaves the computer)."),
            ],
        },
        "recovery": {
            "h": "If a run stops unexpectedly",
            "blocks": [
                ("p", "While measuring, the application keeps a record on disk "
                      "(a journal updated continuously, saved atomically, in the "
                      "application's data folder). It records facts, not "
                      "guesses: when activity was last seen, progress, which "
                      "stage, how the measurement engine ended, memory and "
                      "free disk space, and whether the computer was suspended."),
                ("p", "At the next start, if a session never recorded an end, "
                      "a window lists what is known and offers:"),
                ("ul", [
                    "<b>Export</b> everything recoverable to a folder of your "
                    "choice.",
                    "<b>Show folder</b> to inspect the files.",
                    "<b>Continue with the remaining blocks</b> — offered only "
                    "for runs measured in blocks, and only when the monitor, "
                    "instrument, mode, correction, engine version and profile "
                    "type are the same. Measurements taken under different "
                    "conditions are never combined silently. The block that was "
                    "in progress is measured again from its start.",
                    "<b>Dismiss</b> or mark as seen.",
                ]),
                ("warn", ("What cannot be recovered",
                          "A run measured as a single block keeps its readings "
                          "only inside the measurement engine until it ends; "
                          "if it is interrupted, they are lost. That is why "
                          "long runs should use blocks.")),
            ],
        },
        "diag": {
            "h": "Diagnostic and support",
            "blocks": [
                ("p", "<b>Help → Diagnostic and support</b> gathers what you need "
                      "when something goes wrong, on macOS and Windows. "
                      "Everything stays on your computer; the application "
                      "uploads nothing and asks for no account."),
                ("ul", [
                    "<b>Log folder</b> — a button opens it. On macOS it is "
                    "<i>~/Library/Logs/DisplayCAL</i>; on Windows "
                    "<i>%LOCALAPPDATA%\\DisplayCAL\\Logs</i>. The logs rotate "
                    "daily and when a file reaches 5 MB, and the total is "
                    "capped, so they cannot fill the disk.",
                    "<b>Versions</b> — application, system, Qt, ArgyllCMS and "
                    "other components, in a box you can copy.",
                    "<b>Session ID</b> — each run of the application has a short "
                    "ID that appears on every log line; a measurement session "
                    "also appears under its own ID. Copy it into your report.",
                    "<b>Detailed logging</b> — can be switched on for the "
                    "current run only; it switches itself off after 60 minutes "
                    "and is never kept for the next start.",
                ]),
                ("steps", [
                    "Press <b>Export diagnostic package…</b>.",
                    "A window shows what will be included, with sizes. Always "
                    "included: versions, the application log, the journals of "
                    "the last three measurement sessions (stages, how each "
                    "ArgyllCMS process started and ended, progress, memory, free "
                    "disk space) and crash traces written by the application. "
                    "<b>Only if you tick them</b>: measurement files, the "
                    "display's ICC profile and, on macOS, the system's crash "
                    "reports about the application. Memory dumps and your "
                    "personal files are never included.",
                    "Personal data is removed from the text by default (user "
                    "name, home folders, e-mail, tokens, network and hardware "
                    "identifiers). Unticking this asks for confirmation.",
                    "Choose where to save the ZIP. You can open it with any "
                    "tool and read it; <i>manifest.json</i> says what is inside "
                    "and what was left out.",
                ]),
                ("info", ("Sending it to support is your decision",
                          "The application never sends the package. If you want "
                          "help: open the support page (button in the same "
                          "window), describe the problem and attach the ZIP to "
                          "the report. If you prefer, look inside first and "
                          "send only part of it.")),
                ("p", "After an unexpected stop, the next start notes in the "
                      "log that the previous run did not shut down normally, "
                      "and the recovery window (previous chapter) lists the "
                      "unfinished sessions; both are covered by the package."),
            ],
        },
        "advanced": {
            "h": "Advanced settings, grouped by decision",
            "blocks": [
                ("p", "The advanced tabs keep every professional control. Each tab "
                      "is now divided into sections named after the decision you "
                      "take (for example <b>What the screen should look like</b>, "
                      "<b>Type of profile</b>, <b>File format and precision</b>). "
                      "Under each section title, <b>What each setting here "
                      "changes</b> opens a list that says, for every setting: what "
                      "it changes, when it fits, its unit and the application's "
                      "default, what it depends on, and whether it is "
                      "<i>required to run</i>, <i>depends on your case</i> or "
                      "<i>optional</i>."),
                ("p", "When a control is unavailable or hidden, the same list "
                      "says <b>why</b> (for example: a spectrometer does not use "
                      "a correction; the 3D LUT tab is switched on in the Options "
                      "menu; the PCS-to-device mode needs a LUT-type profile). The "
                      "explanation is also in the control's tooltip."),
                ("ul", [
                    "The guided and the advanced mode work on the <b>same "
                    "configuration</b>. Opening the advanced tabs and coming "
                    "back changes nothing. In the guided flow the goal "
                    "<i>Keep my current settings</i> loads no preset at all; if "
                    "you changed settings after choosing a preset, the guided "
                    "flow tells you how many settings differ and offers to load "
                    "the preset again or to treat them as your own.",
                    "Defaults are shown as <i>the application's default</i>, "
                    "never as a universal recommendation: the text says in "
                    "which case a choice fits.",
                    "In the test chart editor every field has a tooltip, taken "
                    "from the ArgyllCMS <i>targen</i> documentation.",
                ]),
            ],
        },
        "lookup": {
            "h": "Finding your monitor's technology",
            "blocks": [
                ("p", "Next to the colorimeter correction (in the guided flow "
                      "and in the advanced Display tab) the link <b>Don't know "
                      "your monitor's technology? Search the model</b> opens a "
                      "window with the detected model, which you can correct."),
                ("ul", [
                    "For the <b>built-in Apple screen</b> the Mac's model "
                    "identifier (for example Mac14,9) is used and EveryMac's "
                    "lookup page for that identifier opens; the list is shown as "
                    "it is, because several configurations can share one "
                    "identifier. An <b>external monitor connected to a Mac</b> is "
                    "not treated as the built-in screen.",
                    "For other monitors the model is copied and "
                    "displayspecifications.com opens: that site's search cannot "
                    "be filled from a link, so you paste the model into it.",
                    "No serial number or personal identifier is sent; the "
                    "application itself uses no internet here (your browser "
                    "does), so without a connection the model simply stays on "
                    "the clipboard.",
                ]),
                ("warn", ("A specification page is not a correction",
                          "The window explains four different things: panel "
                          "technology (IPS, VA…), light-emitting technology "
                          "(white LED, phosphor, quantum dot, OLED…), measurement "
                          "mode, and correction (spectral or matrix). What a site "
                          "says about a monitor helps to recognise it; it is not "
                          "a validated correction for the combination of your "
                          "monitor and your instrument, and nothing is selected "
                          "for you.")),
            ],
        },
        "support": {
            "h": "Support, feedback and credits",
            "blocks": [
                ("p", "At the end of the flow, and in <b>Help</b> and "
                      "<b>About</b>, two voluntary actions are offered: giving "
                      "the project a star on GitHub (it only opens the "
                      "repository page in your browser) and sending feedback "
                      "(a small form that opens a pre-filled GitHub issue in "
                      "your browser; you see what is included first, and the "
                      "optional diagnostic has a preview and has personal "
                      "paths removed). The application sends nothing itself and "
                      "asks for no account. The invitation can be closed, or "
                      "turned off for good."),
                ("p", "Credits: DisplayCAL by Florian Höch, the "
                      "displaycal-py3 continuation and its contributors, the "
                      "ArgyllCMS engine by Graeme Gill, and this edition by "
                      "Cristi Gordaș. Licence: GPLv3."),
            ],
        },
    },
    "ro": {
        "guided": {
            "h": "Calibrare ghidată (5 pași)",
            "blocks": [
                ("p", "Prima filă, <b>Calibrare ghidată</b>, te duce de la un "
                      "instrument conectat la un profil verificat, în cinci pași. "
                      "Toate opțiunile avansate rămân disponibile în celelalte "
                      "file."),
                ("steps", [
                    "<b>Monitor și instrument</b> — aplicația arată ce a "
                    "detectat. Unele instrumente au aceeași identitate USB "
                    "(de exemplu i1 DisplayPro și ColorMunki Display), deci "
                    "nu poate afla singură modelul exact: îl confirmi tu, iar "
                    "fiecare rând spune dacă a fost <i>detectat de sistem</i> "
                    "sau <i>confirmat de tine</i>.",
                    "<b>Obiectivul tău</b> — alegi scopul (foto, video, uz "
                    "general…). Fiecare obiectiv corespunde unei presetări "
                    "gata făcute.",
                    "<b>Pregătire</b> — o listă scurtă pentru lucrurile pe "
                    "care programul nu le poate face în locul tău (vezi mai "
                    "jos). Nimic nu se bifează automat.",
                    "<b>Măsurare</b> — un rezumat al celor ce urmează, planul "
                    "de măsurare și butonul de pornire.",
                    "<b>Instalare și verificare</b> — se deschide abia după "
                    "ce există un profil valid. După instalare, aplicația "
                    "citește profilul activ și îți spune dacă este chiar "
                    "cel creat acum.",
                ]),
                ("info", ("Dimensiunea textului",
                          "Butonul <b>Aa</b> (și din meniul Opțiuni) stabilește "
                          "dimensiunea textului: Normal, Mare sau Foarte mare. "
                          "Pornește de la dimensiunea folosită de sistem, se "
                          "aplică imediat întregii aplicații, inclusiv "
                          "explicațiilor și dialogurilor, și poate fi readusă la "
                          "valoarea implicită. Schimbă doar textul aplicației; "
                          "fereastra de măsurare, mărimea patch-urilor și "
                          "culorile nu sunt afectate."
                          )),
                ("info", ("Dacă lipsește ceva",
                          "Când ArgyllCMS, un monitor sau un instrument nu "
                          "este găsit, primul pas spune clar acest lucru și ce "
                          "ai de făcut. Motorul Argyll este inclus în "
                          "instalator (verificat cu o sumă SHA-256 fixă); dacă "
                          "vreodată e nevoie de o descărcare, un fișier care nu "
                          "corespunde sumei așteptate este refuzat.")),
            ],
        },
        "prep": {
            "h": "Pregătirea fizică",
            "blocks": [
                ("p", "Înainte de măsurare, lista acoperă monitorul (stabil, "
                      "cu setările finale), camera (fără lumină care cade pe "
                      "ecran) și instrumentul (poziționare corectă, cablu, "
                      "capac). Fiecare element are un scurt <i>de ce</i> cu "
                      "sursele lui, iar bifarea o faci tu."),
                ("warn", ("Nu există un timp universal de încălzire",
                          "Nu există un singur timp de încălzire valabil "
                          "pentru orice monitor. Aplicația nu inventează unul: "
                          "arată o cifră doar când producătorul instrumentului "
                          "o publică (de exemplu 30 de minute pentru Datacolor "
                          "SpyderX) și o prezintă ca recomandare a acelui "
                          "producător.")),
                ("p", "Pentru instrumentele a căror poziționare este "
                      "documentată de producător (Calibrite ColorChecker "
                      "Display, Pro, Plus și Datacolor SpyderX) o scurtă "
                      "animație arată pașii, cu o variantă text pentru fiecare; "
                      "butoanele redare/pauză și anterior/următor o controlează, "
                      "iar ea respectă setarea sistemului de reducere a "
                      "mișcării. Pentru celelalte instrumente pașii sunt "
                      "generici și o spun. Animația se oprește mereu înainte "
                      "de începerea măsurării; fereastra de măsurare arată "
                      "numai patch-uri neutre."),
            ],
        },
        "plan": {
            "h": "Planul de măsurare și sesiunile lungi",
            "blocks": [
                ("p", "Pasul 4 arată planul înainte de orice pornire, cu trei "
                      "numere ținute separat: <b>totalul de patch-uri din "
                      "diagramă</b>, <b>cel mai mare bloc</b> și <b>numărul de "
                      "blocuri</b> (de exemplu „11.000 de patch-uri în total · "
                      "blocuri de maximum 500 · aproximativ 22 de blocuri”), plus "
                      "timpul estimat. Același plan apare în fila Profilare, iar "
                      "butonul <b>Alege sau creează diagrama</b> de lângă total "
                      "deschide selectorul de fișier sau editorul de diagrame. "
                      "Mărimea blocului nu schimbă niciodată totalul: decide "
                      "doar cum este tăiată aceeași diagramă în bucăți."),
                ("ul", [
                    "<b>Tipul de profil</b> — un profil matricial (o curbă "
                    "comună sau curbe pe canale) este mic și previzibil; un "
                    "profil LUT (XYZ sau Lab) descrie mai mult din "
                    "comportamentul ecranului, dar cere mai multe patch-uri. "
                    "Tipul de profil, curbele de calibrare și diagrama de "
                    "măsurare sunt trei lucruri diferite: curbele reglează "
                    "monitorul, diagrama este ce se măsoară, tipul este felul "
                    "în care rezultatul este descris aplicațiilor. <i>Pe "
                    "Mac:</i> pe macOS 10.8 sau mai nou aplicația întreabă o "
                    "dată dacă tipul este altul decât curbă unică + matrice cu "
                    "compensarea punctului negru, pentru că, potrivit "
                    "proiectului original, aplicațiile care folosesc modulul de "
                    "culoare propriu al Apple (Preview, Quick Look) pot arăta "
                    "negru strivit și posterizare cu alte tipuri de profil. Este "
                    "o întrebare, nu o interdicție: Da schimbă, Nu păstrează "
                    "alegerea ta. Aplicațiile cu management propriu al culorii "
                    "(Adobe, GIMP, Krita) și fluxurile cu LUT 3D nu sunt "
                    "afectate. Mai multe patch-uri nu înseamnă automat mai bine: "
                    "costă timp, lasă ecranul să derive și ajută doar acolo "
                    "unde tipul de profil le poate folosi; verifică rezultatul "
                    "după aceea.",
                    "<b>Calibrare față de profilare</b> — calibrarea ajustează "
                    "ecranul spre o țintă; profilarea îl măsoară și scrie "
                    "profilul ICC. Diagrama (setul de patch-uri) ține de "
                    "profilare.",
                    "<b>Rulare lungă sigură (blocuri)</b> — o diagramă mare "
                    "poate fi măsurată în blocuri de maximum 100, 250, 500, 1000 sau "
                    "2000 de patch-uri (sau altă mărime pe care o scrii). Nu "
                    "există o limită superioară fixă pentru diagrama însăși: "
                    "diagrame de 11.000 de patch-uri sau mai multe pot fi "
                    "măsurate așa. Un bloc terminat se salvează pe disc; dacă "
                    "rularea se întrerupe, se pierde doar blocul în curs. "
                    "Fiecare bloc repetă referința albă, deci rularea cere o "
                    "citire de alb în plus per bloc după primul (afișată "
                    "separat) și reinițializează instrumentul între blocuri. "
                    "Estimarea de timp folosește viteza pe care a avut-o "
                    "efectiv acest instrument în rulările anterioare de pe "
                    "acest calculator, dacă există un istoric, altfel "
                    "specificațiile lui, și spune care; nu este niciodată o "
                    "garanție. Instrumentele care au nevoie de propriul ciclu "
                    "de calibrare măsoară într-o singură rulare.",
                    "<b>Ține computerul treaz</b> — activ implicit, doar pe "
                    "durata rulării, eliberat la final. Nu poate împiedica: "
                    "închiderea capacului, alegerea Repaus, butonul de "
                    "pornire, o baterie descărcată, blocarea ecranului sau "
                    "schimbarea utilizatorului. Ține computerul la "
                    "alimentare și sesiunea deblocată.",
                ]),
                ("p", "La sfârșitul unei rulări lungi aplicația arată o "
                      "notificare locală (nimic nu iese din computer)."),
            ],
        },
        "recovery": {
            "h": "Dacă o rulare se oprește neașteptat",
            "blocks": [
                ("p", "În timpul măsurării, aplicația ține o evidență pe disc "
                      "(un jurnal actualizat continuu, salvat atomic, în "
                      "folderul de date al aplicației). Ea consemnează fapte, "
                      "nu presupuneri: ultimul semn de activitate, progresul, "
                      "etapa, cum s-a încheiat motorul de măsurare, memoria și "
                      "spațiul liber pe disc și dacă computerul a fost "
                      "suspendat."),
                ("p", "La pornirea următoare, dacă o sesiune nu și-a "
                      "consemnat sfârșitul, o fereastră listează ce se știe "
                      "și oferă:"),
                ("ul", [
                    "<b>Exportă</b> tot ce se poate recupera într-un folder "
                    "ales de tine.",
                    "<b>Arată folderul</b> pentru a inspecta fișierele.",
                    "<b>Continuă cu blocurile rămase</b> — oferit doar pentru "
                    "rulările măsurate în blocuri și doar dacă monitorul, "
                    "instrumentul, modul, corecția, versiunea motorului și "
                    "tipul de profil sunt aceleași. Măsurători făcute în "
                    "condiții diferite nu se combină niciodată pe tăcute. "
                    "Blocul care era în curs se măsoară din nou de la "
                    "început.",
                    "<b>Închide</b> sau marchează ca văzut.",
                ]),
                ("warn", ("Ce nu se poate recupera",
                          "O rulare măsurată ca un singur bloc își ține "
                          "citirile doar în motorul de măsurare până se "
                          "termină; dacă este întreruptă, ele se pierd. "
                          "De aceea rulările lungi trebuie făcute pe blocuri.")),
            ],
        },
        "diag": {
            "h": "Diagnostic și suport",
            "blocks": [
                ("p", "<b>Ajutor → Diagnostic și suport</b> reunește ce îți "
                      "trebuie când ceva nu merge, pe macOS și pe Windows. "
                      "Totul rămâne pe computerul tău; aplicația nu încarcă "
                      "nimic și nu cere cont."),
                ("ul", [
                    "<b>Folderul de loguri</b> — un buton îl deschide. Pe macOS "
                    "este <i>~/Library/Logs/DisplayCAL</i>; pe Windows "
                    "<i>%LOCALAPPDATA%\\DisplayCAL\\Logs</i>. Logurile se "
                    "rotesc zilnic și când un fișier ajunge la 5 MB, iar "
                    "totalul este limitat, deci nu pot umple discul.",
                    "<b>Versiuni</b> — aplicația, sistemul, Qt, ArgyllCMS și "
                    "alte componente, într-o casetă pe care o poți copia.",
                    "<b>ID-ul sesiunii</b> — fiecare rulare a aplicației are "
                    "un ID scurt care apare pe fiecare linie de log; o sesiune "
                    "de măsurare apare și sub propriul ID. Copiază-l în raport.",
                    "<b>Jurnal detaliat</b> — poate fi pornit doar pentru "
                    "rularea curentă; se oprește singur după 60 de minute și "
                    "nu se păstrează pentru pornirea următoare.",
                ]),
                ("steps", [
                    "Apasă <b>Exportă pachet de diagnostic…</b>.",
                    "O fereastră arată ce va fi inclus, cu dimensiuni. Mereu "
                    "incluse: versiunile, jurnalul aplicației, jurnalele "
                    "ultimelor trei sesiuni de măsurare (etape, cum a pornit și "
                    "cum s-a încheiat fiecare proces ArgyllCMS, progres, "
                    "memorie, spațiu liber pe disc) și urmele de blocare "
                    "scrise de aplicație. <b>Numai dacă le bifezi</b>: "
                    "fișierele de măsurare, profilul ICC al monitorului și, pe "
                    "macOS, rapoartele de blocare ale sistemului despre "
                    "aplicație. Dump-urile de memorie și fișierele tale "
                    "personale nu se includ niciodată.",
                    "Datele personale sunt eliminate implicit din text (nume de "
                    "utilizator, foldere personale, e-mail, tokenuri, "
                    "identificatori de rețea și hardware). Debifarea cere "
                    "confirmare.",
                    "Alege unde se salvează ZIP-ul. Îl poți deschide cu orice "
                    "program și citi; <i>manifest.json</i> spune ce conține și "
                    "ce a fost lăsat deoparte.",
                ]),
                ("info", ("Trimiterea către suport e decizia ta",
                          "Aplicația nu trimite niciodată pachetul. Dacă vrei "
                          "ajutor: deschide pagina de suport (buton în aceeași "
                          "fereastră), descrie problema și atașează ZIP-ul la "
                          "raport. Dacă preferi, uită-te mai întâi înăuntru și "
                          "trimite doar o parte.")),
                ("p", "După o oprire neașteptată, la pornirea următoare logul "
                      "notează că rularea anterioară nu s-a închis normal, iar "
                      "fereastra de recuperare (capitolul anterior) listează "
                      "sesiunile neterminate; ambele intră în pachet."),
            ],
        },
        "advanced": {
            "h": "Setări avansate, grupate pe decizii",
            "blocks": [
                ("p", "Filele avansate păstrează toate controalele profesionale. "
                      "Fiecare filă este acum împărțită în secțiuni numite după "
                      "decizia pe care o iei (de exemplu <b>Cum trebuie să arate "
                      "ecranul</b>, <b>Tipul de profil</b>, <b>Format de fișier și "
                      "precizie</b>). Sub titlul fiecărei secțiuni, <b>Ce schimbă "
                      "fiecare setare de aici</b> deschide o listă care spune, "
                      "pentru fiecare setare: ce schimbă, când se potrivește, "
                      "unitatea și valoarea implicită a aplicației, de ce "
                      "depinde și dacă este <i>necesară pentru rulare</i>, "
                      "<i>depinde de situația ta</i> sau <i>opțională</i>."),
                ("p", "Când un control este indisponibil sau ascuns, aceeași "
                      "listă spune <b>de ce</b> (de exemplu: un spectrometru nu "
                      "folosește o corecție; fila LUT 3D se activează din meniul "
                      "Opțiuni; modul PCS-către-dispozitiv cere un profil de tip "
                      "LUT). Explicația apare și în indiciul controlului."),
                ("ul", [
                    "Modul ghidat și cel avansat lucrează pe <b>aceeași "
                    "configurație</b>. Deschiderea filelor avansate și "
                    "întoarcerea nu schimbă nimic. În fluxul ghidat, obiectivul "
                    "<i>Păstrează setările mele actuale</i> nu încarcă nicio "
                    "presetare; dacă ai schimbat setări după alegerea unei "
                    "presetări, fluxul ghidat îți spune câte setări diferă și "
                    "îți oferă să încarci din nou presetarea sau să le tratezi "
                    "drept ale tale.",
                    "Valorile implicite sunt arătate ca <i>valoarea implicită a "
                    "aplicației</i>, niciodată ca recomandare universală: textul "
                    "spune în ce caz se potrivește o alegere.",
                    "În editorul de diagrame fiecare câmp are un indiciu, luat "
                    "din documentația ArgyllCMS <i>targen</i>.",
                ]),
            ],
        },
        "lookup": {
            "h": "Cum afli tehnologia monitorului",
            "blocks": [
                ("p", "Lângă corecția colorimetrului (în fluxul ghidat și în "
                      "fila avansată Monitor) linkul <b>Nu știi tehnologia "
                      "monitorului? Caută modelul</b> deschide o fereastră cu "
                      "modelul detectat, pe care îl poți corecta."),
                ("ul", [
                    "Pentru <b>ecranul integrat Apple</b> se folosește "
                    "identificatorul modelului de Mac (de exemplu Mac14,9) și "
                    "se deschide pagina de căutare EveryMac pentru acel "
                    "identificator; lista e arătată ca atare, fiindcă mai multe "
                    "configurații pot avea același identificator. Un <b>monitor "
                    "extern conectat la un Mac</b> nu este tratat drept ecranul "
                    "integrat.",
                    "Pentru celelalte monitoare modelul se copiază și se "
                    "deschide displayspecifications.com: căutarea acelui site "
                    "nu poate fi completată dintr-un link, deci lipești tu "
                    "modelul în ea.",
                    "Nu se trimite niciun număr de serie sau identificator "
                    "personal; aplicația nu folosește internetul aici (o face "
                    "browserul tău), deci fără conexiune modelul rămâne în "
                    "clipboard.",
                ]),
                ("warn", ("O pagină de specificații nu este o corecție",
                          "Fereastra explică patru lucruri diferite: tehnologia "
                          "panoului (IPS, VA…), tehnologia emisivă (LED alb, "
                          "fosfor, quantum dot, OLED…), modul de măsurare și "
                          "corecția (spectrală sau matriceală). Ce spune un site "
                          "despre un monitor ajută la recunoașterea lui; nu este "
                          "o corecție validată pentru combinația monitorului și "
                          "instrumentului tău, iar nimic nu se alege în locul "
                          "tău.")),
            ],
        },
        "support": {
            "h": "Susținere, feedback și credite",
            "blocks": [
                ("p", "La sfârșitul fluxului, precum și în <b>Ajutor</b> și "
                      "<b>Despre</b>, sunt oferite două acțiuni voluntare: o "
                      "stea pe GitHub pentru proiect (doar deschide pagina "
                      "depozitului în browser) și trimiterea de feedback (un "
                      "mic formular care deschide în browser o problemă GitHub "
                      "precompletată; vezi mai întâi ce se include, iar "
                      "diagnosticul opțional are previzualizare și căile "
                      "personale sunt eliminate). Aplicația nu trimite nimic "
                      "singură și nu cere cont. Invitația poate fi închisă sau "
                      "oprită definitiv."),
                ("p", "Credite: DisplayCAL de Florian Höch, continuarea "
                      "displaycal-py3 și contribuitorii ei, motorul ArgyllCMS "
                      "de Graeme Gill și această ediție de Cristi Gordaș. "
                      "Licență: GPLv3."),
            ],
        },
    },
    "es": {
        "guided": {
            "h": "Calibración guiada (5 pasos)",
            "blocks": [
                ("p", "La primera pestaña, <b>Calibración guiada</b>, te lleva "
                      "de un instrumento conectado a un perfil verificado en "
                      "cinco pasos. Todas las opciones avanzadas siguen "
                      "disponibles en las demás pestañas."),
                ("steps", [
                    "<b>Monitor e instrumento</b> — la aplicación muestra lo "
                    "que detectó. Algunos instrumentos comparten la misma "
                    "identidad USB (por ejemplo i1 DisplayPro y ColorMunki "
                    "Display), así que no puede saber el modelo exacto por "
                    "sí sola: lo confirmas tú, y cada línea indica si fue "
                    "<i>detectado por el sistema</i> o <i>confirmado por "
                    "ti</i>.",
                    "<b>Tu objetivo</b> — eliges el propósito (foto, vídeo, "
                    "uso general…). Cada objetivo corresponde a un preajuste "
                    "ya preparado.",
                    "<b>Preparación</b> — una lista breve de lo que el "
                    "programa no puede hacer por ti (ver abajo). Nada se marca "
                    "automáticamente.",
                    "<b>Medición</b> — un resumen de lo que va a ocurrir, el "
                    "plan de medición y el botón de inicio.",
                    "<b>Instalar y verificar</b> — solo se abre cuando existe "
                    "un perfil válido. Tras instalarlo, la aplicación lee el "
                    "perfil activo y te dice si es realmente el que acaba de "
                    "crearse.",
                ]),
                ("info", ("Tamaño del texto",
                          "El botón <b>Aa</b> (también en el menú Opciones) fija "
                          "el tamaño del texto: Normal, Grande o Muy grande. "
                          "Parte del tamaño que usa el sistema, se aplica al "
                          "instante a toda la aplicación, incluidas las "
                          "explicaciones y los diálogos, y puede restablecerse al "
                          "valor predeterminado. Solo cambia el texto de la "
                          "aplicación; la ventana de medición, el tamaño de los "
                          "parches y los colores no se ven afectados."
                          )),
                ("info", ("Si falta algo",
                          "Cuando no se encuentra ArgyllCMS, una pantalla o un "
                          "instrumento, el primer paso lo dice con claridad y "
                          "qué hacer. El motor Argyll viene incluido en el "
                          "instalador (verificado con un hash SHA-256 fijo); "
                          "si alguna vez hace falta una descarga, se rechaza "
                          "un archivo que no coincida con el hash esperado.")),
            ],
        },
        "prep": {
            "h": "Preparación física",
            "blocks": [
                ("p", "Antes de medir, la lista cubre el monitor (estable, "
                      "con los ajustes finales), la sala (sin luz que incida "
                      "en la pantalla) y el instrumento (colocación correcta, "
                      "cable, tapa). Cada punto tiene un breve <i>por qué</i> "
                      "con sus fuentes, y los marcas tú."),
                ("warn", ("No hay un tiempo de calentamiento universal",
                          "No existe un único tiempo de calentamiento válido "
                          "para cualquier monitor. La aplicación no inventa "
                          "uno: muestra una cifra solo cuando el fabricante "
                          "del instrumento la publica (por ejemplo 30 minutos "
                          "para Datacolor SpyderX) y la presenta como "
                          "recomendación de ese fabricante.")),
                ("p", "Para los instrumentos cuya colocación documenta el "
                      "fabricante (Calibrite ColorChecker Display, Pro, Plus y "
                      "Datacolor SpyderX) una breve animación muestra los "
                      "pasos, con una versión en texto de cada uno; los "
                      "botones reproducir/pausa y anterior/siguiente la "
                      "controlan y respeta el ajuste del sistema de reducir "
                      "movimiento. Para otros instrumentos los pasos son "
                      "genéricos y lo indican. La animación siempre se "
                      "detiene antes de empezar la medición; la ventana de "
                      "medición solo muestra parches neutros."),
            ],
        },
        "plan": {
            "h": "Plan de medición y sesiones largas",
            "blocks": [
                ("p", "El paso 4 muestra el plan antes de empezar, con tres "
                      "números separados: el <b>total de parches de la "
                      "carta</b>, el <b>bloque más grande</b> y el <b>número de "
                      "bloques</b> (por ejemplo «11.000 parches en total · "
                      "bloques de como máximo 500 · aproximadamente 22 "
                      "bloques»), más el tiempo estimado. El mismo plan aparece "
                      "en la pestaña Perfilado, y el botón <b>Elegir o crear la "
                      "carta</b> junto al total abre el selector de archivo o el "
                      "editor de cartas. El tamaño del bloque nunca cambia el "
                      "total: solo decide cómo se corta la misma carta en "
                      "trozos."),
                ("ul", [
                    "<b>Tipo de perfil</b> — un perfil matricial (una curva "
                    "compartida o curvas por canal) es pequeño y predecible; "
                    "un perfil LUT (XYZ o Lab) describe más del comportamiento "
                    "de la pantalla pero requiere más parches. El tipo de perfil, "
                    "las curvas de calibración y la carta de medición son tres "
                    "cosas distintas: las curvas ajustan el monitor, la carta "
                    "es lo que se mide, el tipo es cómo se describe el "
                    "resultado a las aplicaciones. <i>En Mac:</i> en macOS 10.8 "
                    "o posterior la aplicación pregunta una vez si el tipo es "
                    "distinto de curva única + matriz con compensación del "
                    "punto negro porque, según el proyecto original, las "
                    "aplicaciones que usan el módulo de color propio de Apple "
                    "(Vista Previa, Quick Look) pueden mostrar negros "
                    "aplastados y posterización con otros tipos de perfil. Es "
                    "una pregunta, no una prohibición: Sí cambia, No mantiene "
                    "tu elección. Las aplicaciones con gestión de color propia "
                    "(Adobe, GIMP, Krita) y los flujos con LUT 3D no se ven "
                    "afectados. Más parches no es automáticamente mejor: "
                    "cuesta tiempo, deja que la pantalla derive y solo ayuda "
                    "donde el tipo de perfil puede aprovecharlos; verifica el "
                    "resultado después.",
                    "<b>Calibración frente a perfilado</b> — la calibración "
                    "ajusta la pantalla hacia un objetivo; el perfilado la "
                    "mide y escribe el perfil ICC. La carta (el conjunto de "
                    "parches) pertenece al perfilado.",
                    "<b>Ejecución larga segura (bloques)</b> — una carta "
                    "grande puede medirse en bloques de como máximo 100, 250, 500, "
                    "1000 o 2000 parches (u otro tamaño que escribas). No hay un "
                    "límite superior fijo para la carta en sí: cartas de 11.000 "
                    "parches o más pueden medirse así. Un bloque terminado se "
                    "guarda en disco; si la "
                    "ejecución se interrumpe, solo se pierde el bloque en "
                    "curso. Cada bloque repite la referencia blanca, así que "
                    "se necesita una lectura de blanco extra por bloque "
                    "después del primero (mostrada aparte) y el instrumento se "
                    "reinicializa entre bloques. La estimación de tiempo usa la "
                    "velocidad que tuvo realmente este instrumento en "
                    "ejecuciones anteriores en este ordenador, si hay "
                    "historial, y si no su especificación, e indica cuál; "
                    "nunca es una garantía. Los instrumentos que necesitan su "
                    "propio ciclo de calibración miden en una sola ejecución.",
                    "<b>Mantener el ordenador despierto</b> — activo por "
                    "defecto, solo durante la ejecución, se libera al "
                    "terminar. No puede evitar: cerrar la tapa, elegir "
                    "Suspender, el botón de encendido, una batería agotada, "
                    "bloquear la pantalla o cambiar de usuario. Mantén el "
                    "ordenador enchufado y la sesión desbloqueada.",
                ]),
                ("p", "Al terminar una ejecución larga la aplicación muestra "
                      "una notificación local (nada sale del ordenador)."),
            ],
        },
        "recovery": {
            "h": "Si una ejecución se detiene inesperadamente",
            "blocks": [
                ("p", "Mientras mide, la aplicación guarda un registro en "
                      "disco (un diario actualizado de forma continua, guardado "
                      "de forma atómica, en la carpeta de datos de la "
                      "aplicación). Registra hechos, no suposiciones: la "
                      "última señal de actividad, el progreso, la etapa, cómo "
                      "terminó el motor de medición, la memoria y el espacio "
                      "libre en disco, y si el ordenador estuvo suspendido."),
                ("p", "En el siguiente inicio, si una sesión no registró su "
                      "final, una ventana lista lo que se sabe y ofrece:"),
                ("ul", [
                    "<b>Exportar</b> todo lo recuperable a una carpeta que "
                    "elijas.",
                    "<b>Mostrar carpeta</b> para inspeccionar los archivos.",
                    "<b>Continuar con los bloques restantes</b> — ofrecido "
                    "solo para ejecuciones medidas en bloques y solo si el "
                    "monitor, el instrumento, el modo, la corrección, la "
                    "versión del motor y el tipo de perfil son los mismos. "
                    "Las mediciones hechas en condiciones distintas nunca se "
                    "combinan en silencio. El bloque que estaba en curso se "
                    "mide de nuevo desde su inicio.",
                    "<b>Descartar</b> o marcar como visto.",
                ]),
                ("warn", ("Lo que no se puede recuperar",
                          "Una ejecución medida como un solo bloque mantiene "
                          "sus lecturas solo dentro del motor de medición "
                          "hasta que termina; si se interrumpe, se pierden. "
                          "Por eso las ejecuciones largas deben usar bloques.")),
            ],
        },
        "diag": {
            "h": "Diagnóstico y soporte",
            "blocks": [
                ("p", "<b>Ayuda → Diagnóstico y soporte</b> reúne lo que "
                      "necesitas cuando algo sale mal, en macOS y Windows. "
                      "Todo queda en tu ordenador; la aplicación no sube nada "
                      "y no pide cuenta."),
                ("ul", [
                    "<b>Carpeta de registros</b> — un botón la abre. En macOS "
                    "es <i>~/Library/Logs/DisplayCAL</i>; en Windows "
                    "<i>%LOCALAPPDATA%\\DisplayCAL\\Logs</i>. Los registros "
                    "rotan a diario y cuando un archivo llega a 5 MB, y el "
                    "total está limitado, así que no pueden llenar el disco.",
                    "<b>Versiones</b> — aplicación, sistema, Qt, ArgyllCMS y "
                    "otros componentes, en un cuadro que puedes copiar.",
                    "<b>ID de sesión</b> — cada ejecución de la aplicación "
                    "tiene un ID corto que aparece en cada línea del registro; "
                    "una sesión de medición aparece además con su propio ID. "
                    "Cópialo en tu informe.",
                    "<b>Registro detallado</b> — puede activarse solo para la "
                    "ejecución actual; se desactiva solo tras 60 minutos y no "
                    "se conserva para el siguiente inicio.",
                ]),
                ("steps", [
                    "Pulsa <b>Exportar paquete de diagnóstico…</b>.",
                    "Una ventana muestra qué se incluirá, con tamaños. Siempre "
                    "incluidos: versiones, el registro de la aplicación, los "
                    "diarios de las tres últimas sesiones de medición "
                    "(etapas, cómo empezó y terminó cada proceso de ArgyllCMS, "
                    "progreso, memoria, espacio libre en disco) y las trazas de "
                    "fallo escritas por la aplicación. <b>Solo si las "
                    "marcas</b>: archivos de medición, el perfil ICC de la "
                    "pantalla y, en macOS, los informes de fallo del sistema "
                    "sobre la aplicación. Los volcados de memoria y tus "
                    "archivos personales nunca se incluyen.",
                    "Por defecto se eliminan del texto los datos personales "
                    "(nombre de usuario, carpetas personales, correo, tokens, "
                    "identificadores de red y hardware). Desmarcarlo pide "
                    "confirmación.",
                    "Elige dónde guardar el ZIP. Puedes abrirlo con cualquier "
                    "programa y leerlo; <i>manifest.json</i> indica qué "
                    "contiene y qué se dejó fuera.",
                ]),
                ("info", ("Enviarlo al soporte es decisión tuya",
                          "La aplicación nunca envía el paquete. Si quieres "
                          "ayuda: abre la página de soporte (botón en la misma "
                          "ventana), describe el problema y adjunta el ZIP al "
                          "informe. Si prefieres, mira primero dentro y envía "
                          "solo una parte.")),
                ("p", "Tras una parada inesperada, en el siguiente inicio el "
                      "registro anota que la ejecución anterior no terminó "
                      "con normalidad, y la ventana de recuperación (capítulo "
                      "anterior) lista las sesiones sin terminar; ambas cosas "
                      "entran en el paquete."),
            ],
        },
        "advanced": {
            "h": "Ajustes avanzados, agrupados por decisión",
            "blocks": [
                ("p", "Las pestañas avanzadas conservan todos los controles "
                      "profesionales. Cada pestaña se divide ahora en secciones "
                      "con el nombre de la decisión que tomas (por ejemplo "
                      "<b>Cómo debe verse la pantalla</b>, <b>Tipo de perfil</b>, "
                      "<b>Formato de archivo y precisión</b>). Bajo el título de "
                      "cada sección, <b>Qué cambia cada ajuste de aquí</b> abre "
                      "una lista que indica, para cada ajuste: qué cambia, "
                      "cuándo encaja, su unidad y el valor predeterminado de la "
                      "aplicación, de qué depende y si es <i>necesario para "
                      "ejecutar</i>, <i>depende de tu caso</i> u "
                      "<i>opcional</i>."),
                ("p", "Cuando un control no está disponible u oculto, la misma "
                      "lista dice <b>por qué</b> (por ejemplo: un espectrómetro "
                      "no usa corrección; la pestaña LUT 3D se activa en el menú "
                      "Opciones; el modo PCS a dispositivo requiere un perfil de "
                      "tipo LUT). La explicación también está en la descripción "
                      "emergente del control."),
                ("ul", [
                    "El modo guiado y el avanzado trabajan con la <b>misma "
                    "configuración</b>. Abrir las pestañas avanzadas y volver "
                    "no cambia nada. En el flujo guiado, el objetivo "
                    "<i>Mantener mis ajustes actuales</i> no carga ningún "
                    "preajuste; si cambiaste ajustes tras elegir un preajuste, "
                    "el flujo guiado te dice cuántos difieren y te ofrece "
                    "cargar de nuevo el preajuste o tratarlos como propios.",
                    "Los valores predeterminados se muestran como <i>valor "
                    "predeterminado de la aplicación</i>, nunca como "
                    "recomendación universal: el texto dice en qué caso encaja "
                    "una elección.",
                    "En el editor de cartas cada campo tiene una descripción "
                    "emergente, tomada de la documentación de ArgyllCMS "
                    "<i>targen</i>.",
                ]),
            ],
        },
        "lookup": {
            "h": "Cómo averiguar la tecnología de tu monitor",
            "blocks": [
                ("p", "Junto a la corrección del colorímetro (en el flujo "
                      "guiado y en la pestaña avanzada Pantalla) el enlace "
                      "<b>¿No conoces la tecnología de tu monitor? Busca el "
                      "modelo</b> abre una ventana con el modelo detectado, que "
                      "puedes corregir."),
                ("ul", [
                    "Para la <b>pantalla integrada de Apple</b> se usa el "
                    "identificador del modelo de Mac (por ejemplo Mac14,9) y se "
                    "abre la página de búsqueda de EveryMac para ese "
                    "identificador; la lista se muestra tal cual, porque varias "
                    "configuraciones pueden compartir un identificador. Un "
                    "<b>monitor externo conectado a un Mac</b> no se trata como "
                    "la pantalla integrada.",
                    "Para otros monitores se copia el modelo y se abre "
                    "displayspecifications.com: la búsqueda de ese sitio no se "
                    "puede rellenar desde un enlace, así que pegas el modelo en "
                    "ella.",
                    "No se envía ningún número de serie ni identificador "
                    "personal; la aplicación no usa internet aquí (lo hace tu "
                    "navegador), así que sin conexión el modelo queda en el "
                    "portapapeles.",
                ]),
                ("warn", ("Una página de especificaciones no es una corrección",
                          "La ventana explica cuatro cosas distintas: tecnología "
                          "del panel (IPS, VA…), tecnología emisiva (LED blanco, "
                          "fósforo, punto cuántico, OLED…), modo de medición y "
                          "corrección (espectral o matricial). Lo que diga un "
                          "sitio sobre un monitor ayuda a reconocerlo; no es una "
                          "corrección validada para la combinación de tu monitor "
                          "y tu instrumento, y no se elige nada por ti.")),
            ],
        },
        "support": {
            "h": "Apoyo, comentarios y créditos",
            "blocks": [
                ("p", "Al final del flujo, y en <b>Ayuda</b> y "
                      "<b>Acerca de</b>, se ofrecen dos acciones voluntarias: "
                      "dar una estrella al proyecto en GitHub (solo abre la "
                      "página del repositorio en tu navegador) y enviar "
                      "comentarios (un pequeño formulario que abre en el "
                      "navegador una incidencia de GitHub rellenada; ves "
                      "primero qué se incluye, y el diagnóstico opcional "
                      "tiene vista previa y las rutas personales se "
                      "eliminan). La aplicación no envía nada por sí misma y "
                      "no pide cuenta. La invitación puede cerrarse o "
                      "desactivarse para siempre."),
                ("p", "Créditos: DisplayCAL de Florian Höch, la continuación "
                      "displaycal-py3 y sus colaboradores, el motor ArgyllCMS "
                      "de Graeme Gill y esta edición de Cristi Gordaș. "
                      "Licencia: GPLv3."),
            ],
        },
    },
}

import os as _os

_YAML = {}


def _y(lang: str, key: str) -> str:
    """A string from the application's own language file (one source of truth)."""
    if lang not in _YAML:
        import yaml

        path = _os.path.join(_os.path.dirname(__file__), "..", "..", "DisplayCAL", "lang", f"{lang}.yaml")
        with open(path, encoding="utf-8") as f:
            _YAML[lang] = yaml.safe_load(f)
    return str(_YAML[lang][key]).strip()


_EXTRA = {
    "en": {
        "results": ("What the results mean, and their limits",
            "Verification measures a set of patches and compares them with what the profile predicts. It describes those patches, on that monitor, with that instrument, at that moment; it is not a certificate for every colour.",
            "What is what", "Limits to keep in mind",
            "Two more limits: a result obtained with one instrument says nothing about another, and a profile made with a long, drifting run is only as good as the stability of the screen during it. Verify after profiling and repeat if the screen has changed."),
        "uninstall": ("Uninstall and where your data stays",
            ["<b>macOS</b> — quit the application, then move DisplayCAL and the other tools (Curve Viewer, ICC Profile Info, Testchart Editor, 3D LUT Maker, Scripting Client, Synthetic ICC, VRML to X3D) from Applications to the Bin.",
             "<b>Windows</b> — Settings → Apps → DisplayCAL-CG → Uninstall."],
            "The application's data is not removed by either way, so you can reinstall without losing settings. To delete it too:",
            ["macOS: <font face='Courier'>~/Library/Preferences/DisplayCAL</font> (settings), <font face='Courier'>~/Library/Application Support/DisplayCAL</font> (data and session records), <font face='Courier'>~/Library/Logs/DisplayCAL</font> (logs).",
             "Windows: <font face='Courier'>%APPDATA%\\DisplayCAL</font> (settings, data and session records), <font face='Courier'>%LOCALAPPDATA%\\DisplayCAL\\Logs</font> (logs)."]),
    },
    "ro": {
        "results": ("Ce înseamnă rezultatele și care le sunt limitele",
            "Verificarea măsoară un set de patch-uri și le compară cu ce prezice profilul. Descrie acele patch-uri, pe acel monitor, cu acel instrument, în acel moment; nu este un certificat pentru fiecare culoare.",
            "Ce este ce", "Limite de ținut minte",
            "Încă două limite: un rezultat obținut cu un instrument nu spune nimic despre altul, iar un profil făcut dintr-o rulare lungă, cu derivă, este la fel de bun ca stabilitatea ecranului în acel timp. Verifică după profilare și repetă dacă ecranul s-a schimbat."),
        "uninstall": ("Dezinstalare și unde rămân datele tale",
            ["<b>macOS</b> — închide aplicația, apoi mută DisplayCAL și celelalte unelte (Curve Viewer, ICC Profile Info, Testchart Editor, 3D LUT Maker, Scripting Client, Synthetic ICC, VRML to X3D) din Applications în Coș.",
             "<b>Windows</b> — Setări → Aplicații → DisplayCAL-CG → Dezinstalează."],
            "Datele aplicației nu sunt șterse în niciunul dintre cazuri, deci poți reinstala fără să pierzi setările. Ca să le ștergi și pe ele:",
            ["macOS: <font face='Courier'>~/Library/Preferences/DisplayCAL</font> (setări), <font face='Courier'>~/Library/Application Support/DisplayCAL</font> (date și înregistrările sesiunilor), <font face='Courier'>~/Library/Logs/DisplayCAL</font> (jurnale).",
             "Windows: <font face='Courier'>%APPDATA%\\DisplayCAL</font> (setări, date și înregistrările sesiunilor), <font face='Courier'>%LOCALAPPDATA%\\DisplayCAL\\Logs</font> (jurnale)."]),
    },
    "es": {
        "results": ("Qué significan los resultados y sus límites",
            "La verificación mide un conjunto de parches y los compara con lo que predice el perfil. Describe esos parches, en ese monitor, con ese instrumento, en ese momento; no es un certificado para cada color.",
            "Qué es qué", "Límites que conviene recordar",
            "Dos límites más: un resultado obtenido con un instrumento no dice nada de otro, y un perfil hecho con una ejecución larga y con deriva es tan bueno como la estabilidad de la pantalla durante ella. Verifica tras perfilar y repite si la pantalla ha cambiado."),
        "uninstall": ("Desinstalar y dónde quedan tus datos",
            ["<b>macOS</b> — cierra la aplicación y mueve DisplayCAL y las demás herramientas (Curve Viewer, ICC Profile Info, Testchart Editor, 3D LUT Maker, Scripting Client, Synthetic ICC, VRML to X3D) de Aplicaciones a la Papelera.",
             "<b>Windows</b> — Configuración → Aplicaciones → DisplayCAL-CG → Desinstalar."],
            "Los datos de la aplicación no se borran en ningún caso, así que puedes reinstalar sin perder los ajustes. Para borrarlos también:",
            ["macOS: <font face='Courier'>~/Library/Preferences/DisplayCAL</font> (ajustes), <font face='Courier'>~/Library/Application Support/DisplayCAL</font> (datos y registros de sesión), <font face='Courier'>~/Library/Logs/DisplayCAL</font> (registros).",
             "Windows: <font face='Courier'>%APPDATA%\\DisplayCAL</font> (ajustes, datos y registros de sesión), <font face='Courier'>%LOCALAPPDATA%\\DisplayCAL\\Logs</font> (registros)."]),
    },
}


def _extra_sections(lang: str) -> list[dict]:
    r = _EXTRA[lang]
    h, intro, what, lim, more = r["results"]
    concepts = [
        f"<b>{_y(lang, k)}</b> — {_y(lang, k + '.info')}"
        for k in ("guide.concept.calibration", "guide.concept.profile", "guide.concept.curves", "guide.concept.lut3d")
    ]
    limits = [_y(lang, k) for k in ("guide.limit.color_management", "guide.limit.hdr", "guide.limit.multi_display")]
    results = {
        "h": h,
        "blocks": [
            ("p", _y(lang, "guide.s5.intro")),
            ("p", intro),
            ("h2", what),
            ("ul", concepts),
            ("h2", lim),
            ("ul", limits),
            ("p", more),
        ],
    }
    uh, ul, p2, ul2 = r["uninstall"]
    uninstall = {"h": uh, "blocks": [("ul", ul), ("p", p2), ("ul", ul2)]}
    return [results, uninstall]



def sections(lang: str) -> list[dict]:
    """Chapters for one language, in reading order."""
    t = _T[lang]
    res, uninst = _extra_sections(lang)
    return [t["guided"], t["prep"], t["plan"], t["recovery"], res, t["diag"], t["advanced"], t["lookup"], uninst]


def support_section(lang: str) -> dict:
    """The support/credits chapter (placed after the licence chapter)."""
    return _T[lang]["support"]
