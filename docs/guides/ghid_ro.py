# ghid_ro.py — continutul ghidului DisplayCAL-CG (romana).
# Structura declarativa citita de `_engine.build()` — vezi acolo tipurile
# de bloc acceptate ("p", "h2", "ul", "code", "img", "steps", "opt",
# "info"/"warn"/"ok", "pagebreak").

CONTENT = {
    "title": "Ghid de utilizare DisplayCAL-CG",
    "subtitle": "Calibrare și profilare de monitor, pas cu pas — ediția GDC",
    "note": "Versiune document 1.0 · bazat pe DisplayCAL-CG 3.10.0.dev82",
    "toc_title": "Cuprins",
    "cover_subtitle": "Calibrare și caracterizare monitor pe baza ArgyllCMS",
    "cover_version_label": "Versiune aplicație",
    "cover_lang_label": "Ediție în limba română",
    "footer": "DisplayCAL-CG — Ghid de utilizare (RO)",
    "sections": [
        {
            "h": "Ce este DisplayCAL-CG",
            "blocks": [
                ("p", "DisplayCAL-CG este o ediție a proiectului open-source "
                       "<b>DisplayCAL</b> (continuarea comunitară a lucrării "
                       "originale a lui Florian Höch), împachetată și tradusă "
                       "integral în română de GDC. Aplicația calibrează și "
                       "profilează monitorul folosind motorul de măsurare "
                       "<b>ArgyllCMS</b> — rezultatul e un monitor cu culori "
                       "corecte și constante, indiferent de aplicația în care "
                       "lucrezi (foto, video, grafică)."),
                ("info", ("Ce înseamnă „calibrare” vs. „profilare”",
                          "<b>Calibrarea</b> aduce monitorul la o stare țintă "
                          "cunoscută (punct alb, luminanță, curbă tonală) prin "
                          "ajustări hardware/software (curbele din placa "
                          "video). <b>Profilarea</b> măsoară apoi cum răspunde "
                          "monitorul calibrat și scrie un <b>profil ICC</b> pe "
                          "care restul sistemului îl folosește pentru "
                          "corecție de culoare precisă. Se fac mereu una după "
                          "alta, în această ordine.")),
                ("p", "Acest ghid explică, pe rând, fiecare din cele 5 tab-uri "
                       "principale ale aplicației (Monitor & instrument, "
                       "Calibrare, Profilare, LUT 3D, Verificare), uneltele "
                       "avansate din meniu, și cum se instalează/actualizează "
                       "aplicația pe Mac și Windows."),
                ("warn", ("Ai nevoie de un instrument de măsurare",
                          "DisplayCAL-CG NU poate calibra un monitor fără un "
                          "colorimetru sau spectrofotometru fizic conectat "
                          "prin USB (ex. X-Rite i1Display Pro, ColorMunki "
                          "Display, Datacolor Spyder). Aplicația detectează "
                          "automat instrumentul conectat în tab-ul „Monitor & "
                          "instrument”.")),
            ],
        },
        {
            "h": "Instalare",
            "blocks": [
                ("h2", "macOS"),
                ("steps", [
                    "Descarcă pachetul <b>DisplayCAL-CG.pkg</b> de pe pagina "
                    "de descărcare (gordas.dev/DisplayCAL-CG).",
                    "Dă dublu-click pe fișierul <b>.pkg</b> descărcat.",
                    "În fereastra de instalare, apasă <b>Continuă</b> pe "
                    "fiecare pas până ajungi la pagina de <b>Licență</b>.",
                    "Citește rezumatul licenței GPLv3 afișat, apasă "
                    "<b>Agree</b> (fără acceptare explicită, instalarea nu "
                    "poate continua — e o cerință a instalatorului nativ "
                    "macOS, nu un pas opțional).",
                    "Apasă <b>Instalează</b> — aplicația și toate cele 9 "
                    "unelte satelit (Profile Info, Curve Viewer, etc.) se "
                    "instalează direct în <b>Applications</b>, fără să tragi "
                    "nimic manual.",
                    "Deschide <b>DisplayCAL-CG</b> din Launchpad/Applications.",
                ]),
                ("info", ("Pachetul e semnat și notarizat de Apple",
                          "Gatekeeper-ul macOS va lăsa aplicația să pornească "
                          "direct, fără avertismentul „nu poate fi deschisă "
                          "pentru că vine de la un dezvoltator neidentificat”.")),
                ("h2", "Windows"),
                ("steps", [
                    "Descarcă instalatorul <b>DisplayCAL-CG-Setup.exe</b> de "
                    "pe pagina de descărcare.",
                    "Dă dublu-click pe fișierul descărcat.",
                    "Dacă apare avertismentul <b>Windows SmartScreen</b> "
                    "(\"Windows a protejat computerul\"), apasă <b>Mai multe "
                    "informații</b>, apoi <b>Rulează oricum</b>.",
                    "La pagina de licență din instalator, selectează "
                    "<b>Accept termenii acordului de licență</b> — butonul "
                    "„Următorul” rămâne dezactivat până bifezi asta.",
                    "Urmează pașii instalatorului (locație implicită "
                    "recomandată) până la <b>Instalează</b>.",
                    "Deschide <b>DisplayCAL-CG</b> din Start Menu sau de pe "
                    "scurtătura de pe Desktop.",
                ]),
                ("warn", ("De ce apare avertismentul SmartScreen",
                          "Instalatorul Windows nu e (încă) semnat cu un "
                          "certificat de cod plătit — avertismentul e normal "
                          "pentru software fără semnătură, nu un semn că "
                          "fișierul e nesigur. Descarcă-l doar de pe pagina "
                          "oficială de mai sus.")),
            ],
        },
        {
            "h": "Monitor & instrument",
            "blocks": [
                ("p", "Primul tab — aici alegi CE monitor calibrezi și CU CE "
                       "instrument. Aplicația trebuie să știe amândouă "
                       "înainte să poți trece la Calibrare."),
                ("img", ("monitor_instrument_full.png",
                        "Tab-ul Monitor & instrument, cu un monitor extern "
                        "și un colorimetru i1DisplayPro deja detectate.")),
                ("opt", (("Câmp", "Ce face"), [
                    ("Monitor", "Alege din listă monitorul de calibrat, dacă "
                                "ai mai multe conectate. Butonul rotund ↻ de "
                                "lângă re-scanează monitoarele conectate."),
                    ("Instrument", "Colorimetrul/spectrofotometrul detectat "
                                   "prin USB. Dacă apare gol, verifică "
                                   "cablul USB și că instrumentul e "
                                   "recunoscut de sistemul de operare."),
                    ("Mod", "Modul de măsurare al instrumentului — "
                            "„Refresh (generic)” e potrivit pentru "
                            "majoritatea monitoarelor LCD/LED. Unele "
                            "instrumente (K-10, Spyder4/5/X) oferă moduri "
                            "precalibrate pentru tipuri specifice de "
                            "monitor — alege-l pe cel mai apropiat de al "
                            "tău dacă există."),
                    ("Compensare drift nivel alb", "Activează dacă monitorul "
                            "e un TV OLED/Plasmă sau alt tip cu ieșire de "
                            "lumină variabilă în funcție de conținutul "
                            "imaginii afișate."),
                    ("Compensare drift nivel negru", "Activează dacă folosești "
                            "un spectrometru în mod de contact pe un monitor "
                            "cu nivel de negru instabil."),
                    ("Niveluri de ieșire", "„Automat” e alegerea corectă în "
                            "aproape toate cazurile. „TV RGB 16-235” se "
                            "folosește doar dacă monitorul/placa video "
                            "limitează intenționat intervalul de semnal, ca "
                            "la un TV conectat ca monitor."),
                    ("Corecție", "Corecția de culoare specifică "
                            "instrumentului + monitorului — DisplayCAL-CG o "
                            "alege automat („Automat (Spectral: ...)”) când "
                            "poate; nu o schimba manual decât dacă știi "
                            "exact ce faci."),
                ])),
                ("info", ("Înainte de a măsura",
                          "Lasă monitorul să se încălzească <b>minimum 30 de "
                          "minute</b> înainte de calibrare — culorile unui "
                          "monitor rece variază pe măsură ce se stabilizează "
                          "termic. Dezactivează orice setare dinamică de "
                          "imagine a monitorului (contrast dinamic, "
                          "luminozitate automată) și evită lumina care cade "
                          "direct pe ecran în timpul măsurătorii.")),
            ],
        },
        {
            "h": "Calibrare",
            "blocks": [
                ("p", "Al doilea tab — aici alegi CE stare țintă vrei pentru "
                       "monitor: ce punct alb, ce luminanță, ce curbă "
                       "tonală."),
                ("img", ("calibrare_full.png",
                        "Setările de calibrare implicite (Gamma 2.2, punct "
                        "alb și nivele „ca măsurat”).")),
                ("opt", (("Câmp", "Ce face"), [
                    ("Ajustare interactivă a monitorului", "Bifat, aplicația "
                            "te ghidează să ajuști manual butoanele fizice "
                            "ale monitorului (luminozitate, contrast, "
                            "RGB) în timpul calibrării, ca să te apropii "
                            "cât mai mult de țintă înainte de a genera "
                            "curbele software."),
                    ("Observator", "Standardul CIE folosit la interpretarea "
                            "culorii — „CIE 1931 2°” e alegerea implicită, "
                            "potrivită imensei majorități a situațiilor."),
                    ("Punct alb", "„Ca măsurat” păstrează punctul alb nativ "
                            "al monitorului. Poți alege în schimb o "
                            "temperatură de culoare fixă (ex. 6500K/D65) "
                            "dacă ai nevoie de un standard exact, cu o "
                            "referință (\"Lumină de zi\"/\"Corp negru\")."),
                    ("Nivel alb / Nivel negru", "„Ca măsurat” păstrează "
                            "luminanța nativă a monitorului. Poți fixa "
                            "manual o valoare (ex. 120 cd/m²) dacă ai un "
                            "standard de luminanță de respectat."),
                    ("Curbă tonală", "Ce formă va avea răspunsul tonal "
                            "rezultat — „Gamma 2.2” e implicit potrivit "
                            "pentru foto/web; „Rec. 1886” sau alte curbe "
                            "sunt relevante mai ales pentru video."),
                    ("Offset de ieșire negru", "0% = negru „pur”; 100% = "
                            "negrul urmează exact curba aleasă fără offset. "
                            "Valorile intermediare compensează monitoare "
                            "cu negru ridicat."),
                    ("Corecție punct negru", "Rata/procentul cu care se "
                            "corectează neliniaritățile din apropierea "
                            "negrului — „Automat” lasă aplicația să decidă."),
                    ("Viteză calibrare", "Un compromis timp/acuratețe — "
                            "„Ridicată” (implicit) e suficientă pentru "
                            "majoritatea utilizărilor."),
                ])),
                ("warn", ("Calibrarea 1D LUT nu înlocuiește un profil ICC",
                          "Curbele generate aici corectează doar tonalitatea "
                          "generală a monitorului — pentru corecție "
                          "completă de culoare, ai nevoie și de un "
                          "<b>profil de dispozitiv ICC</b> sau un <b>LUT "
                          "3D</b>, create în tab-urile următoare.")),
            ],
        },
        {
            "h": "Profilare",
            "blocks": [
                ("p", "Al treilea tab — aici DisplayCAL-CG afișează efectiv "
                       "petice de culoare pe ecran, le măsoară cu "
                       "instrumentul, și construiește <b>profilul ICC</b> "
                       "care caracterizează monitorul tău calibrat."),
                ("img", ("profilare_full.png",
                        "Setările de profilare — tip „Curbă unică + "
                        "matrice”, testchart Auto-optimizat, 34 de petice.")),
                ("opt", (("Câmp", "Ce face"), [
                    ("Tip profil", "„Curbă unică + matrice” e rapid și "
                            "suficient pentru multe monitoare bune; un "
                            "profil bazat pe <b>LUT</b> (tabel de căutare) "
                            "cu sute-mii de petice oferă cea mai bună "
                            "acuratețe posibilă, dar durează mult mai mult."),
                    ("Compensare punct negru", "Recomandat bifat — "
                            "îmbunătățește acuratețea în zonele întunecate."),
                    ("Calitate profil", "Cursor Scăzută→Ridicată — "
                            "influențează cât de fin e calculat profilul "
                            "din datele măsurate, nu numărul de petice."),
                    ("Testchart", "„Auto-optimizat” alege automat "
                            "distribuția peticelor ținând cont de "
                            "neliniaritățile reale ale monitorului tău — "
                            "recomandat pentru cele mai bune rezultate."),
                    ("Numărul de petice", "Cursorul controlează câte petice "
                            "se măsoară — mai multe petice = profil mai "
                            "precis, dar măsurătoare mai lungă."),
                    ("Secvență de petice", "„Minimizează întârzierea de "
                            "răspuns a monitorului” ordonează peticele ca "
                            "să scurteze timpul total de măsurare."),
                    ("Nume profil", "Sablonul de denumire automată — poți "
                            "edita liber câmpul de mai jos dacă vrei un "
                            "nume propriu de profil."),
                ])),
                ("info", ("Cât durează",
                          "Aplicația afișează un timp estimat sub setările "
                          "de profilare (ex. „aproximativ 1 minut” pentru "
                          "34 de petice) — un profil bazat pe LUT, cu mii de "
                          "petice, poate dura de la câteva minute la peste "
                          "o oră.")),
            ],
        },
        {
            "h": "LUT 3D",
            "blocks": [
                ("p", "Tab opțional — generează un <b>LUT 3D</b> (tabel de "
                       "căutare tridimensional) pornind de la profilul deja "
                       "creat, pentru aplicații care suportă corecție de "
                       "culoare prin LUT 3D în loc de profil ICC (comun în "
                       "flux de lucru video/color grading — DaVinci "
                       "Resolve, playere media)."),
                ("img", ("lut3d_full.png",
                        "Setările LUT 3D — sursă Rec709, curbă Rec.1886, "
                        "format IRIDAS .cube, rezoluție 65×65×65.")),
                ("opt", (("Câmp", "Ce face"), [
                    ("Creează LUT 3D după profilare", "Bifează dacă vrei ca "
                            "LUT-ul să se genereze automat imediat după ce "
                            "se termină profilarea, fără un pas separat."),
                    ("Spațiu de culoare sursă", "Spațiul de culoare al "
                            "materialului pe care îl vei reda (ex. „Rec709 "
                            "ITU-R BT.709” pentru video HD standard)."),
                    ("Curbă tonală", "Trebuie să corespundă standardului "
                            "materialului sursă — video HD folosește de "
                            "obicei fie o curbă de putere ~2,2-2,4, fie "
                            "„Rec. 1886”."),
                    ("Mod de mapare a gamutului", "„Dispozitiv-către-PCS "
                            "invers” e alegerea standard pentru un LUT de "
                            "afișare (nu de conversie de conținut)."),
                    ("Intenție de randare", "„Colorimetric absolut cu "
                            "scalarea punctului alb” e recomandat dacă nu "
                            "ai calibrat explicit la punctul alb al "
                            "materialului sursă."),
                    ("Format fișier LUT 3D", "IRIDAS .cube e cel mai larg "
                            "compatibil (Resolve, majoritatea playerelor); "
                            "alte formate există pentru software specific."),
                    ("Rezoluție LUT 3D", "65×65×65 e un compromis bun "
                            "precizie/dimensiune fișier — rezoluții mai mari "
                            "cresc precizia și dimensiunea fișierului."),
                ])),
                ("warn", ("Folosește ACELEAȘI setări cu care s-a creat LUT-ul",
                          "Când verifici ulterior un LUT 3D deja creat (tab-ul "
                          "Verificare), asigură-te că folosești exact "
                          "aceleași setări (spațiu sursă, curbă, intenție de "
                          "randare) — altfel rezultatul verificării nu are "
                          "sens.")),
            ],
        },
        {
            "h": "Verificare",
            "blocks": [
                ("p", "Al cincilea tab — verifică cât de precis e un profil "
                       "ICC sau LUT 3D deja creat, printr-un raport de "
                       "măsurare cu statistici despre erorile de culoare "
                       "măsurate pe un set de petice."),
                ("img", ("verificare.png",
                        "Setările de verificare — testchart extins de "
                        "verificare, 51 de petice, ~2 minute estimat.")),
                ("opt", (("Câmp", "Ce face"), [
                    ("Testchart sau referință", "Setul de petice folosit "
                            "pentru verificare — „Testchart extins de "
                            "verificare” e un set standard, independent de "
                            "cel folosit la profilare (altfel verificarea "
                            "ar fi părtinitoare)."),
                    ("Simulează punctul alb", "Compară rezultatul relativ la "
                            "un punct alb simulat, în loc de cel nativ al "
                            "monitorului."),
                    ("Relativ la punctul alb al profilului monitorului", "La "
                            "fel ca mai sus, dar raportat la punctul alb "
                            "ÎNREGISTRAT în profilul curent."),
                    ("Profil de simulare", "Opțional — verifică cum s-ar "
                            "comporta monitorul dacă ar simula un alt "
                            "profil/spațiu de culoare."),
                ])),
                ("steps", [
                    "Alege testchart-ul de verificare (implicit e potrivit "
                    "în aproape toate cazurile).",
                    "Apasă <b>Raport de măsurare...</b> din josul "
                    "ferestrei.",
                    "Urmează instrumentul pe ecran în timp ce aplicația "
                    "afișează peticele de test și le măsoară pe rând.",
                    "La final, se deschide un raport cu erorile medii/"
                    "maxime de culoare (ΔE) măsurate — cu cât ΔE e mai "
                    "mic, cu atât profilul e mai precis.",
                ]),
                ("info", ("Sfat",
                          "Ține apăsată tasta <b>ALT</b> de pe tastatură "
                          "când apeși „Raport de măsurare...” pentru a crea "
                          "un raport de <b>auto-verificare</b> în loc de un "
                          "raport de măsurare obișnuit.")),
            ],
        },
        {
            "h": "Unelte avansate",
            "blocks": [
                ("p", "Pe lângă fluxul principal (cele 5 tab-uri de mai sus), "
                       "DisplayCAL-CG include mai multe unelte de sine "
                       "stătătoare, utile pentru cazuri speciale — "
                       "accesibile din meniul aplicației principale sau ca "
                       "aplicații separate instalate alături."),
                ("h2", "Creează profil ICC sintetic"),
                ("img", ("creeaza_profil_sintetic.png",
                        "Unealta de creare a unui profil ICC sintetic, "
                        "pornind de la parametri descriși manual (nu de la "
                        "măsurători reale).")),
                ("p", "Construiește un profil ICC pornind de la parametri "
                       "descriși manual (punct alb, gamma, primare de "
                       "culoare) — util pentru a genera un profil de "
                       "referință teoretic, fără să măsori un monitor real "
                       "(ex. pentru simulare sau testare)."),
                ("h2", "Creează LUT 3D (standalone)"),
                ("img", ("creeaza_lut3d_standalone.png",
                        "Unealta independentă de creare LUT 3D, pentru "
                        "conversii între spații de culoare fără să treci "
                        "prin fluxul complet de calibrare a unui monitor.")),
                ("p", "Aceeași logică de generare LUT 3D ca în tab-ul "
                       "„LUT 3D”, dar rulată independent de un flux de "
                       "calibrare a monitorului — utilă pentru a converti "
                       "între două profile/spații de culoare arbitrare."),
                ("h2", "Profile Info"),
                ("img", ("profile_info.png",
                        "Fereastra Profile Info — informații complete despre "
                        "un profil ICC, plus reprezentarea grafică a "
                        "gamutului lui.")),
                ("p", "Deschide orice profil ICC (creat de DisplayCAL-CG sau "
                       "din altă sursă) și arată toate informațiile "
                       "conținute în el — punct alb, curbă tonală, primare "
                       "de culoare — plus o reprezentare grafică 3D a "
                       "gamutului de culoare acoperit."),
                ("h2", "Curbe"),
                ("img", ("curbe.png",
                        "Fereastra Curbe — vizualizarea curbelor de "
                        "calibrare (vcgt) încărcate curent în placa video.")),
                ("p", "Afișează grafic curbele de calibrare (VCGT — Video "
                       "Card Gamma Table) încărcate curent în placa video — "
                       "util pentru a verifica rapid, vizual, ce calibrare "
                       "e activă chiar acum."),
                ("h2", "Jurnal"),
                ("img", ("jurnal.png",
                        "Fereastra Jurnal — jurnalul tehnic detaliat al "
                        "operațiilor ArgyllCMS din spatele aplicației.")),
                ("p", "Jurnalul tehnic detaliat al comenzilor ArgyllCMS "
                       "executate în spate de aplicație — util în principal "
                       "pentru diagnosticare, dacă ceva nu funcționează cum "
                       "te aștepți și vrei să înțelegi exact ce s-a "
                       "întâmplat."),
            ],
        },
        {
            "h": "Licență GPLv3 & susținere opțională",
            "blocks": [
                ("ok", ("100% gratuit, pentru totdeauna",
                        "DisplayCAL-CG e software liber, licențiat GPLv3 — "
                        "complet funcțional din prima zi, fără activare, "
                        "fără probă limitată în timp, fără nicio "
                        "funcționalitate blocată în spatele unei plăți. "
                        "Poți instala, folosi și redistribui aplicația "
                        "liber, respectând termenii licenței GPLv3 incluse "
                        "(LICENSE.txt).")),
                ("p", "DisplayCAL-CG e construit peste munca open-source a "
                       "DisplayCAL (Florian Höch) și a continuatorilor ei "
                       "comunitari — creditele complete rămân vizibile în "
                       "aplicație (Ajutor → Despre)."),
                ("p", "Dacă aplicația ți-a fost utilă, un mesaj opțional de "
                       "susținere apare ocazional în aplicație — e pur "
                       "informativ, niciodată o cerință pentru a folosi "
                       "vreo funcție."),
            ],
        },
        {
            "h": "Actualizări",
            "blocks": [
                ("p", "DisplayCAL-CG verifică automat, la pornire, dacă "
                       "există o versiune mai nouă disponibilă pe pagina de "
                       "descărcări. Poți verifica și manual din meniul "
                       "Ajutor."),
                ("steps", [
                    "Dacă apare o notificare de versiune nouă, apasă "
                    "linkul din notificare — te duce direct la pagina de "
                    "descărcare cu ultima versiune.",
                    "Descarcă noul pachet (.pkg pe Mac, .exe pe Windows).",
                    "Instalează-l peste versiunea curentă, exact ca la "
                    "prima instalare (vezi capitolul „Instalare”) — "
                    "setările și profilele deja create rămân neatinse.",
                    "Repornește aplicația după instalare.",
                ]),
            ],
        },
    ],
}
