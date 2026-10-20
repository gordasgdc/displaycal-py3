# guided_pages.py — the five guided steps as five pages: what you do, why, what you check.
# One "wcv" block per step (rendered by _engine_html). Wording follows the application's
# own texts; nothing here claims more than the application verifies.

_L = {
    "ro": {
        "h": "Cei cinci pași, pe pagini",
        "intro": "Fiecare pagină este un pas din „Calibrare ghidată”: ce faci, de ce, ce verifici. Imaginile sunt capturi din aplicație, cu date demonstrative (monitor și instrument simulate).",
        "labels": ("Ce faci", "De ce", "Ce verifici", "Limită", "Pasul"),
        "fig": "Captură din aplicație (date demonstrative).",
        "pages": [
            {
                "title": "Monitor și instrument",
                "purpose": "Aplicația îți arată ce a detectat: monitorul de calibrat și instrumentul conectat. Tu confirmi; nimic nu e presupus.",
                "img": "step1.png",
                "do": [
                    "Alege din „Monitorul de calibrat” ecranul pe care îl calibrezi, dacă ai mai multe.",
                    "Verifică „Instrument”. Dacă lipsește, conectează-l direct la computer (nu printr-un hub) și apasă <b>Rescanează</b>.",
                    "Dacă același identificator USB e folosit de mai multe produse, alege modelul tău: schimbă doar ajutorul de poziționare, nu măsurarea.",
                ],
                "why": [
                    "Profilul descrie acel monitor, măsurat cu acel instrument.",
                    "Un colorimetru e mai precis cu o corecție potrivită tipului de panou; un spectrofotometru nu are nevoie de ea.",
                ],
                "check": [
                    "Linia de stare spune „detectat de sistem” sau „confirmat de tine”; nimic altceva nu a fost verificat încă.",
                    "Sub alegeri vezi modul de măsurare și corecția folosite.",
                ],
            },
            {
                "title": "Obiectivul tău",
                "purpose": "Alegi pentru ce folosești monitorul. Nu există o țintă unică și cea mai bună.",
                "img": "step2.png",
                "do": [
                    "Alege folosința cea mai apropiată: foto și grafică, video și corecție de culoare, birou și web, laptop, conținut sRGB, soft-proofing sau „Păstrează setările mele actuale”.",
                    "Dacă aplicația arată „Sugerat pentru acest monitor”, e o sugestie, nu o obligație.",
                ],
                "why": [
                    "Fiecare obiectiv încarcă o presetare (punct alb, curbă, calitate); valorile pot fi schimbate ulterior în fila Calibrare.",
                ],
                "check": [
                    "Sub listă apare presetarea încărcată sau mesajul că setările tale actuale au fost păstrate.",
                    "Dacă schimbi apoi setări avansate, aplicația spune că rularea le folosește pe ale tale, nu presetarea.",
                ],
            },
            {
                "title": "Pregătire",
                "purpose": "Nimic nu e bifat în locul tău: încălzirea, lumina și poziționarea nu pot fi observate de aplicație. Bifezi fiecare element când e adevărat.",
                "img": "step3.png",
                "do": [
                    "Monitorul e pornit și stabilizat; un temporizator opțional te ajută să nu uiți.",
                    "Mod de imagine neutru, funcții automate oprite (luminozitate automată, contrast dinamic, night shift, HDR).",
                    "Nicio lampă sau fereastră care se reflectă în ecran.",
                    "Instrumentul e conectat direct; urmărești secvența de poziționare arătată pentru modelul tău.",
                ],
                "why": [
                    "Luminozitatea și culoarea derivă cât se încălzește ecranul; nu există un timp universal de încălzire.",
                    "O schimbare automată în timpul măsurării ar falsifica profilul; lumina parazită intră în citire.",
                ],
                "check": [
                    "Elementele obligatorii bifate deblochează <b>Continuă</b>; lângă butoane se vede ce mai lipsește.",
                    "Fără model confirmat, secvența de poziționare cuprinde doar pași generali.",
                ],
            },
            {
                "title": "Măsurare",
                "purpose": "Aplicația îți arată planul înainte de pornire: câte patch-uri, în câte blocuri, cât durează (o estimare).",
                "img": "step4.png",
                "do": [
                    "Verifică <b>Total</b>: câte patch-uri are diagrama. Dacă e prea mult, alege altă diagramă.",
                    "Alege mărimea blocului. Cu blocuri, citirile terminate se salvează local, pe măsură ce se fac.",
                    "Citește „Timp estimat”: fără o rulare anterioară măsurată, vine din specificațiile instrumentului.",
                ],
                "why": [
                    "Mai multe patch-uri ajută doar unde tipul de profil le poate folosi (mai ales LUT) și costă timp.",
                    "Mărimea blocului nu schimbă totalul, ci felul în care e tăiată aceeași diagramă; fiecare bloc după primul repetă albul de referință.",
                ],
                "check": [
                    "Banda colorată arată câte blocuri vor fi; cifrele de sub ea sunt numerele lor.",
                    "Estimarea e o estimare, nu o garanție.",
                ],
                "limit": "O calibrare de durată a fost finalizată cu succes de proprietarul proiectului, folosind versiunea publică, pe configurația sa. Stabilitatea pe alte configurații și durate nu este încă validată. Raport al proprietarului, nu un test executat de dezvoltare; durata, numărul de patch-uri și versiunea exactă nu sunt consemnate. Salvarea blocurilor nu garantează stabilitatea, acuratețea sau recuperarea în orice condiții.",
            },
            {
                "title": "Instalare și verificare",
                "purpose": "O rulare e reușită doar când profilul există, e instalat pentru acest monitor și trece verificarea.",
                "img": "step5.png",
                "do": [
                    "Deschide instalarea profilului și alege: doar pentru utilizatorul curent sau implicit de sistem.",
                    "Alege, dacă vrei, previzualizarea calibrării și încărcarea ei la autentificare.",
                    "Deschide setările de verificare și rulează o verificare.",
                ],
                "why": [
                    "Aplicațiile fără management de culoare ignoră profilul ICC; ajung la ele doar curbele de calibrare.",
                    "HDR și SDR sunt moduri diferite: o calibrare făcută în unul nu se aplică celuilalt.",
                ],
                "check": [
                    "„Profilul activ acum pentru acest monitor” arată numele profilului instalat.",
                    "Rezultatul verificării, nu simpla terminare a procesului, arată dacă merge.",
                ],
            },
        ],
    },
    "en": {
        "h": "The five steps, page by page",
        "intro": "Each page is one step of “Guided calibration”: what you do, why, what you check. The pictures are screenshots from the application, with demonstration data (simulated monitor and instrument).",
        "labels": ("What you do", "Why", "What you check", "Limit", "Step"),
        "fig": "Screenshot from the application (demonstration data).",
        "pages": [
            {
                "title": "Monitor and instrument",
                "purpose": "The application shows what it detected: the monitor to calibrate and the connected instrument. You confirm; nothing is assumed.",
                "img": "step1.png",
                "do": [
                    "In “Monitor to calibrate”, choose the screen you are calibrating, if you have several.",
                    "Check “Instrument”. If it is missing, plug it straight into the computer (not through a hub) and press <b>Rescan</b>.",
                    "If one USB identifier is shared by several products, pick your model: it only changes the placement help, not the measurement.",
                ],
                "why": [
                    "The profile describes that monitor, measured with that instrument.",
                    "A colorimeter is more accurate with a correction that fits the panel type; a spectrophotometer does not need one.",
                ],
                "check": [
                    "The status line says “detected by the system” or “confirmed by you”; nothing else has been verified yet.",
                    "Under the choices you see the measurement mode and the correction in use.",
                ],
            },
            {
                "title": "Your goal",
                "purpose": "You choose what you use the monitor for. There is no single best target.",
                "img": "step2.png",
                "do": [
                    "Choose the closest use: photo and graphics, video and colour grading, office and web, laptop, sRGB content, soft-proofing, or “Keep my current settings”.",
                    "If the application shows “Suggested for this monitor”, that is a suggestion, not an obligation.",
                ],
                "why": [
                    "Each goal loads a preset (white point, curve, quality); the values can be changed later in the Calibration tab.",
                ],
                "check": [
                    "Under the list you see the preset that was loaded, or the message that your current settings were kept.",
                    "If you then change advanced settings, the application says the run uses yours, not the preset.",
                ],
            },
            {
                "title": "Preparation",
                "purpose": "Nothing is ticked for you: warm-up, light and placement cannot be observed by the application. You tick each item when it is true.",
                "img": "step3.png",
                "do": [
                    "The monitor is on and settled; an optional timer helps you remember.",
                    "Neutral picture mode, automatic features off (auto brightness, dynamic contrast, night shift, HDR).",
                    "No lamp or window reflecting in the screen.",
                    "The instrument is plugged in directly; you follow the placement sequence shown for your model.",
                ],
                "why": [
                    "Brightness and colour drift while the screen warms up; there is no universal warm-up time.",
                    "An automatic change during measurement would falsify the profile; stray light gets into the reading.",
                ],
                "check": [
                    "Ticking the required items unlocks <b>Continue</b>; next to the buttons you see what is still missing.",
                    "Without a confirmed model, the placement sequence contains only general steps.",
                ],
            },
            {
                "title": "Measurement",
                "purpose": "The application shows the plan before you start: how many patches, in how many blocks, how long it takes (an estimate).",
                "img": "step4.png",
                "do": [
                    "Check <b>Total</b>: how many patches the chart has. If it is too many, choose another chart.",
                    "Choose the block size. With blocks, finished readings are saved locally as they are taken.",
                    "Read “Estimated time”: without an earlier measured run, it comes from the instrument’s specifications.",
                ],
                "why": [
                    "More patches only help where the profile type can use them (mostly LUT) and they cost time.",
                    "The block size does not change the total, only how the same chart is cut; every block after the first repeats the reference white.",
                ],
                "check": [
                    "The coloured strip shows how many blocks there will be; the numbers under it are their numbers.",
                    "The estimate is an estimate, not a guarantee.",
                ],
                "limit": "A long calibration was completed successfully by the project owner, using the public version, on their own setup. Stability on other setups and durations is not yet validated. This is the owner's report, not a test run by the development side; the duration, the patch count and the exact version were not recorded. Saving blocks does not guarantee stability, accuracy or recovery in every condition.",
            },
            {
                "title": "Install and verify",
                "purpose": "A run is successful only when the profile exists, is installed for this monitor and passes verification.",
                "img": "step5.png",
                "do": [
                    "Open the profile installation and choose: current user only, or system default.",
                    "Choose, if you want, the calibration preview and loading it at login.",
                    "Open the verification settings and run a verification.",
                ],
                "why": [
                    "Applications without colour management ignore the ICC profile; only the calibration curves reach them.",
                    "HDR and SDR are different modes: a calibration made in one does not apply to the other.",
                ],
                "check": [
                    "“Profile currently active for this monitor” shows the name of the installed profile.",
                    "The verification result, not just the process finishing, shows whether it works.",
                ],
            },
        ],
    },
    "es": {
        "h": "Los cinco pasos, página a página",
        "intro": "Cada página es un paso de «Calibración guiada»: qué haces, por qué, qué compruebas. Las imágenes son capturas de la aplicación, con datos de demostración (monitor e instrumento simulados).",
        "labels": ("Qué haces", "Por qué", "Qué compruebas", "Límite", "Paso"),
        "fig": "Captura de la aplicación (datos de demostración).",
        "pages": [
            {
                "title": "Monitor e instrumento",
                "purpose": "La aplicación muestra lo que ha detectado: el monitor a calibrar y el instrumento conectado. Tú confirmas; no se supone nada.",
                "img": "step1.png",
                "do": [
                    "En «Monitor a calibrar», elige la pantalla que calibras, si tienes varias.",
                    "Revisa «Instrumento». Si falta, conéctalo directamente al ordenador (no a través de un concentrador) y pulsa <b>Volver a buscar</b>.",
                    "Si varios productos comparten el mismo identificador USB, elige tu modelo: solo cambia la ayuda de colocación, no la medición.",
                ],
                "why": [
                    "El perfil describe ese monitor, medido con ese instrumento.",
                    "Un colorímetro es más preciso con una corrección adecuada al tipo de panel; un espectrofotómetro no la necesita.",
                ],
                "check": [
                    "La línea de estado dice «detectado por el sistema» o «confirmado por ti»; nada más se ha verificado todavía.",
                    "Bajo las opciones ves el modo de medición y la corrección en uso.",
                ],
            },
            {
                "title": "Tu objetivo",
                "purpose": "Eliges para qué usas el monitor. No existe un único objetivo mejor.",
                "img": "step2.png",
                "do": [
                    "Elige el uso más cercano: foto y gráficos, vídeo y corrección de color, oficina y web, portátil, contenido sRGB, soft-proofing o «Conservar mi configuración actual».",
                    "Si la aplicación muestra «Sugerido para este monitor», es una sugerencia, no una obligación.",
                ],
                "why": [
                    "Cada objetivo carga un preajuste (punto blanco, curva, calidad); los valores se pueden cambiar después en la pestaña Calibración.",
                ],
                "check": [
                    "Bajo la lista ves el preajuste cargado o el mensaje de que se conservó tu configuración actual.",
                    "Si después cambias ajustes avanzados, la aplicación dice que la ejecución usa los tuyos, no el preajuste.",
                ],
            },
            {
                "title": "Preparación",
                "purpose": "Nada se marca por ti: el calentamiento, la luz y la colocación no los puede observar la aplicación. Marcas cada elemento cuando es cierto.",
                "img": "step3.png",
                "do": [
                    "El monitor está encendido y estabilizado; un temporizador opcional te ayuda a recordarlo.",
                    "Modo de imagen neutro, funciones automáticas desactivadas (brillo automático, contraste dinámico, night shift, HDR).",
                    "Ninguna lámpara ni ventana que se refleje en la pantalla.",
                    "El instrumento está conectado directamente; sigues la secuencia de colocación mostrada para tu modelo.",
                ],
                "why": [
                    "El brillo y el color varían mientras la pantalla se calienta; no existe un tiempo de calentamiento universal.",
                    "Un cambio automático durante la medición falsearía el perfil; la luz parásita entra en la lectura.",
                ],
                "check": [
                    "Marcar los elementos obligatorios desbloquea <b>Continuar</b>; junto a los botones ves lo que falta.",
                    "Sin un modelo confirmado, la secuencia de colocación solo contiene pasos generales.",
                ],
            },
            {
                "title": "Medición",
                "purpose": "La aplicación muestra el plan antes de empezar: cuántos parches, en cuántos bloques, cuánto tarda (una estimación).",
                "img": "step4.png",
                "do": [
                    "Revisa <b>Total</b>: cuántos parches tiene la carta. Si son demasiados, elige otra carta.",
                    "Elige el tamaño del bloque. Con bloques, las lecturas terminadas se guardan localmente a medida que se hacen.",
                    "Lee «Tiempo estimado»: sin una ejecución anterior medida, procede de las especificaciones del instrumento.",
                ],
                "why": [
                    "Más parches solo ayudan donde el tipo de perfil puede usarlos (sobre todo LUT) y cuestan tiempo.",
                    "El tamaño del bloque no cambia el total, solo cómo se corta la misma carta; cada bloque tras el primero repite el blanco de referencia.",
                ],
                "check": [
                    "La banda de colores muestra cuántos bloques habrá; los números bajo ella son sus números.",
                    "La estimación es una estimación, no una garantía.",
                ],
                "limit": "El propietario del proyecto completó con éxito una calibración de larga duración, con la versión pública y en su propia configuración. La estabilidad en otras configuraciones y duraciones aún no está validada. Es un informe del propietario, no una prueba ejecutada por el desarrollo; no constan la duración, el número de parches ni la versión exacta. Guardar los bloques no garantiza estabilidad, precisión ni recuperación en toda condición.",
            },
            {
                "title": "Instalar y verificar",
                "purpose": "Una ejecución solo es correcta cuando el perfil existe, está instalado para este monitor y supera la verificación.",
                "img": "step5.png",
                "do": [
                    "Abre la instalación del perfil y elige: solo el usuario actual o predeterminado del sistema.",
                    "Elige, si quieres, la vista previa de la calibración y cargarla al iniciar sesión.",
                    "Abre los ajustes de verificación y ejecuta una verificación.",
                ],
                "why": [
                    "Las aplicaciones sin gestión de color ignoran el perfil ICC; solo les llegan las curvas de calibración.",
                    "HDR y SDR son modos distintos: una calibración hecha en uno no se aplica al otro.",
                ],
                "check": [
                    "«Perfil activo ahora para este monitor» muestra el nombre del perfil instalado.",
                    "El resultado de la verificación, no que el proceso termine, muestra si funciona.",
                ],
            },
        ],
    },
}


def section(lang: str) -> dict:
    """The chapter, as one section with one ``wcv`` block per step."""
    d = _L[lang]
    blocks = [("p", d["intro"])]
    for n, page in enumerate(d["pages"], 1):
        blocks.append(("wcv", {"n": n, "labels": d["labels"], "fig": d["fig"], **page}))
    return {"h": d["h"], "blocks": blocks}
