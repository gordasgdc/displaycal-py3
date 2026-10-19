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
                ("p", "Step 4 shows the plan before anything starts: the "
                      "profile type, the number of patches and an estimated "
                      "time."),
                ("ul", [
                    "<b>Profile type</b> — a matrix profile (one shared curve "
                    "or per-channel curves) is small and predictable; a LUT "
                    "profile (XYZ or Lab) describes more of the screen's "
                    "behaviour but needs more patches. On macOS the preset uses "
                    "the single-curve matrix, inherited from the original "
                    "project because of reported problems with other types on "
                    "that system. More patches is not automatically better: "
                    "it costs time and only helps where the profile type can "
                    "use it.",
                    "<b>Calibration vs profiling</b> — calibration adjusts the "
                    "screen towards a target; profiling measures it and writes "
                    "the ICC profile. The chart (the set of patches) belongs to "
                    "profiling.",
                    "<b>Safe long run (blocks)</b> — a large chart can be "
                    "measured in blocks of 250, 500 or 1000 patches. A "
                    "finished block is saved to disk; if the run is "
                    "interrupted, only the block in progress is lost. Each "
                    "block repeats the white reference, so the run needs one "
                    "extra patch per block and re-initialises the instrument "
                    "between blocks. Instruments that need their own "
                    "calibration cycle measure in one run.",
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
                ("p", "Pasul 4 arată planul înainte de orice pornire: tipul de "
                      "profil, numărul de patch-uri și un timp estimat."),
                ("ul", [
                    "<b>Tipul de profil</b> — un profil matricial (o curbă "
                    "comună sau curbe pe canale) este mic și previzibil; un "
                    "profil LUT (XYZ sau Lab) descrie mai mult din "
                    "comportamentul ecranului, dar cere mai multe patch-uri. "
                    "Pe macOS presetarea folosește matricea cu o singură "
                    "curbă, moștenită de la proiectul original din cauza unor "
                    "probleme raportate cu alte tipuri pe acel sistem. Mai "
                    "multe patch-uri nu înseamnă automat mai bine: costă "
                    "timp și ajută doar acolo unde tipul de profil le poate "
                    "folosi.",
                    "<b>Calibrare față de profilare</b> — calibrarea ajustează "
                    "ecranul spre o țintă; profilarea îl măsoară și scrie "
                    "profilul ICC. Diagrama (setul de patch-uri) ține de "
                    "profilare.",
                    "<b>Rulare lungă sigură (blocuri)</b> — o diagramă mare "
                    "poate fi măsurată în blocuri de 250, 500 sau 1000 de "
                    "patch-uri. Un bloc terminat se salvează pe disc; dacă "
                    "rularea se întrerupe, se pierde doar blocul în curs. "
                    "Fiecare bloc repetă referința albă, deci rularea cere un "
                    "patch în plus per bloc și reinițializează instrumentul "
                    "între blocuri. Instrumentele care au nevoie de propriul "
                    "ciclu de calibrare măsoară într-o singură rulare.",
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
                ("p", "El paso 4 muestra el plan antes de empezar: el tipo de "
                      "perfil, el número de parches y un tiempo estimado."),
                ("ul", [
                    "<b>Tipo de perfil</b> — un perfil matricial (una curva "
                    "compartida o curvas por canal) es pequeño y predecible; "
                    "un perfil LUT (XYZ o Lab) describe más del comportamiento "
                    "de la pantalla pero requiere más parches. En macOS el "
                    "preajuste usa la matriz de curva única, heredada del "
                    "proyecto original por problemas notificados con otros "
                    "tipos en ese sistema. Más parches no es automáticamente "
                    "mejor: cuesta tiempo y solo ayuda donde el tipo de perfil "
                    "puede aprovecharlos.",
                    "<b>Calibración frente a perfilado</b> — la calibración "
                    "ajusta la pantalla hacia un objetivo; el perfilado la "
                    "mide y escribe el perfil ICC. La carta (el conjunto de "
                    "parches) pertenece al perfilado.",
                    "<b>Ejecución larga segura (bloques)</b> — una carta "
                    "grande puede medirse en bloques de 250, 500 o 1000 "
                    "parches. Un bloque terminado se guarda en disco; si la "
                    "ejecución se interrumpe, solo se pierde el bloque en "
                    "curso. Cada bloque repite la referencia blanca, así que "
                    "se necesita un parche extra por bloque y el instrumento "
                    "se reinicializa entre bloques. Los instrumentos que "
                    "necesitan su propio ciclo de calibración miden en una "
                    "sola ejecución.",
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


def sections(lang: str) -> list[dict]:
    """Chapters for one language, in reading order."""
    t = _T[lang]
    return [t[k] for k in ("guided", "prep", "plan", "recovery")]


def support_section(lang: str) -> dict:
    """The support/credits chapter (placed after the licence chapter)."""
    return _T[lang]["support"]
