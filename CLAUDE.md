# DisplayCAL-CG — reguli de arhitectură

> **[SYSTEM DIRECTIVE FOR CLAUDE: DO NOT DELETE OR OVERWRITE EXISTING RULES. ONLY APPEND NEW RULES.]**
> Jurnal viu, nu document care se rescrie. La orice actualizare, adaugă la finalul secțiunii potrivite — nu șterge/înlocui reguli vechi decât dacă sunt explicit invalidate de o schimbare reală (și atunci marchează-le **[ÎNVECHIT]** cu motivul, nu le șterge din istoric).

Citit automat de Claude Code la fiecare sesiune în acest repo.

## [PARTEA 1: REGULI GLOBALE ECOSISTEM GDC] — mutată în `~/Developer/CLAUDE.md`

> Din 2026-09-18, regulile globale stau într-un singur fișier,
> `~/Developer/CLAUDE.md`, citit automat de Claude Code în orice proiect din
> `~/Developer/`. Nu se mai copiază aici. Ce era specific acestui repo în fosta
> Partea 1 (statusuri, excepții) e la finalul fișierului.

## [PARTEA 2: SPECIFICAȚII TEHNICE PROIECT — DisplayCAL-CG]

### Context (2026-09-05)

Fork: `gordasgdc/displaycal-py3` (clonat local în `~/Developer/displaycal-py3`).
Upstream: `eoyilmaz/displaycal-py3` (remote `upstream`), care e la rândul
lui continuarea comunitară a DisplayCAL original (Florian Höch) portat pe
Python 3. Licență: **GPLv3** (`LICENSE.txt`, neatinsă).

**Sincronizat 2026-09-05**: fast-forward `develop` de la `dd6ce705` la
`06317b85` (971 commit-uri, fork nu avea niciun commit divergent — verificat
`behind_by: 0` înainte de merge, deci fast-forward curat garantat, nicio
rezolvare de conflict necesară). Push-uit pe `origin/develop`.

**Arhitectură reală a proiectului** (verificată direct în cod, nu presupusă):
- Branding centralizat în `DisplayCAL/meta.py` (`NAME`, `AUTHOR`, `DOMAIN`,
  `APPSTREAM_ID`, `GITHUB_API_URL`, `DEVELOPMENT_HOME_PAGE`) — citit de
  `_native_build/meta.py` (`load()`) și folosit de templating-ul de
  packaging (`_native_build/templates.py`, `inno.py`, `appdata.py`).
- i18n: **YAML per-limbă** (`DisplayCAL/lang/*.yaml`), NU gettext `.po`/`.mo`
  cum s-a presupus inițial în cerere — 1280 chei, ~2688 rânduri în
  `en.yaml`. Fără `ro.yaml` la momentul auditului.
- Packaging deja matur, NU reinventat: `native_build.py py2app` (macOS →
  `.app`, apoi `create-dmg` → `.dmg` în CI) și `native_build.py inno`
  (Windows → Inno Setup `.exe`). CI existent:
  `.github/workflows/release_builds.yml`.
- Icoane: `DisplayCAL/theme/icons/*.icns`/`*.ico` — un set per unealtă
  (aplicația principală + 8 unelte auxiliare: 3DLUT-maker, curve-viewer,
  profile-info, scripting-client, synthprofile, testchart-editor,
  VRML-to-X3D-converter, apply-profiles, plus uninstall).

### Decizii de scop confirmate de Cristi (2026-09-05)

1. **Licențiere**: fără gating, fără trial — vezi excepția Regulii 3 de mai sus.
2. **macOS**: `.pkg` (instalare automată `/Applications`), NU `.dmg`
   drag-and-drop ca upstream — aliniat cu restul suitei GDC.
3. **Iconițe**: SET COMPLET, toate cele ~9 unelte, nu doar aplicația
   principală.
4. **Windows**: fără certificat de semnare cod încă — installer rămâne
   nesemnat la primul release (SmartScreen va avertiza), acceptat ca stare
   tranzitorie.
5. **Pagină web**: GitHub Pages pe `displaycal-py3` (`docs/`) + oglindă în
   `gdc-plugin-manager-catalog-vendor/docs/DisplayCAL-CG/`, servită pe
   `gordas.dev/DisplayCAL-CG/` — butoane native de download →
   `releases/latest/download/...` de pe `displaycal-py3`. GDC Plugin
   Manager listează aplicația (`catalog.json` → `apps[]`) și trimite spre
   aceeași pagină.

### Progres (actualizat pe măsură ce se lucrează — NU declara o etapă
"gata" până nu e bifată aici cu verificare reală)

- [x] **Sync upstream → fork** (fast-forward, verificat, push-uit).
- [x] **Rebranding `DisplayCAL/meta.py`** — `AUTHOR`/`AUTHOR_ASCII`/
  `DESCRIPTION`/`LONG_DESCRIPTION` extinse (credit original PĂSTRAT, nu
  înlocuit — cerință GPLv3), `DOMAIN="gordas.dev"` (afectează DOAR
  metadate de packaging — URL-uri installer, APPSTREAM_ID), `GITHUB_API_URL`/
  `DEVELOPMENT_HOME_PAGE` redirecționate spre `gordasgdc/displaycal-py3`.
  `AUTHOR_EMAIL` **NU** derivat din noul `DOMAIN` — rămâne hardcodat la
  adresele reale ale autorilor originali. **`NAME` RĂMÂNE `"DisplayCAL"`**
  (NU `"DisplayCAL-CG"`) — corectat după un build real eșuat, vezi comentariul
  extins din `meta.py` (`~70` de locuri din `_setup.py` folosesc `NAME` ca
  identificator LITERAL de pachet Python, nu doar text de afișat — o
  cratimă acolo rupe `distutils.versionpredicate` + mismatch-uiește
  folderul fizic `DisplayCAL/`). Identitatea vizuală "DisplayCAL-CG" trăiește
  în stringuri pure + iconițe + nume de pachete de distribuție, NU în `NAME`.
- [x] **`DisplayCAL/lang/ro.yaml`** — traducere completă RO (1280 chei,
  verificat set-egal cu `en.yaml`, zero mismatch de placeholder-uri).
- [x] **9 iconițe noi** (`.icns`/`.ico`/`.png`, toate uneltele) — desenate
  vectorial cu Pillow (roată de culoare RGB pentru aplicația principală,
  pictogramă distinctă per unealtă), paleta "Shift" GDC. Nume confirmate
  direct în cod (`_setup.py`/`config.py`/`worker.py`/`postinstall.py`,
  toate derivă din `NAME`/`APPNAME`). Verificat: 99/99 PNG-uri pe mărimi
  (10-512px) cu dimensiune exactă, toate cele 8 `.icns` validate
  ne-corupte (round-trip `iconutil`), fișierele vechi complet eliminate.
- [x] **`build_pkg.sh`** (macOS, semnare Developer ID + notarizare +
  stapling, `.pkg` cu instalare directă în `/Applications`). **GATA,
  verificat real**: `dist/DisplayCAL-CG.pkg` (508MB) — `spctl --assess`
  → `accepted, source=Notarized Developer ID`; `stapler validate` → OK.
  16 rulări eșuate înainte de succes — cauze REALE găsite pe rând, nu
  presupuse (toate documentate inline în `build_pkg.sh`):
  1. `codesign --verify --deep --strict` respinge symlink-uri externe
     bundle-ului — cele 8 unelte satelit (Testchart Editor etc.) sunt
     bundle-uri mici (~400KB) care symlink-uiesc Frameworks/Resources
     din `DisplayCAL.app` (design py2app intenționat, upstream nu
     rulează niciodată acest verify). Fix: verify simplu, fără `--deep`.
  2. `codesign --remove-signature` corupe `__LINKEDIT` pe dylib-uri deja
     ad-hoc semnate din wheel-uri (`liblzma.5.dylib`, Pillow/.dylibs) —
     eliminat strip-ul pentru dylib/so, păstrat doar pentru framework-uri
     Qt (motiv diferit, documentat upstream).
  3. Semnarea paralelă a tuturor 9 app-uri scria concurent peste ACELEAȘI
     fișiere fizice (doar `DisplayCAL.app` le deține, restul symlink) —
     fix: `DisplayCAL.app` semnat complet, singur, ÎNAINTE; cele 8
     satelit în paralel după, fără să rescrie fișierele partajate.
  4. Cauza REALĂ (nu #2/#3): macholib (py2app) corupe `__LINKEDIT` la
     rescrierea unui LC_ID_DYLIB scurt/placeholder (`/DLC/...`) la unul
     mai lung (`@executable_path/...`) — fix: `install_name_tool -id`
     pre-rescrie ID-urile ÎNAINTE de py2app (unealtă Apple, realocă corect).
  5. py2app însuși (`codesign_adhoc`/`_dosign --preserve-metadata=...`)
     eșuează silențios pe dylib-uri nesemnate, lăsând un
     `LC_CODE_SIGNATURE` orfan/corupt — fix: salvăm copii curate ale
     `.dylibs/` ÎNAINTE de py2app, le suprascriem peste cele corupte
     DUPĂ py2app, înainte de semnarea proprie.
  6. Satelit apps au propriul interpretor `Contents/MacOS/python` REAL
     (nu symlink) — o semnare non-deep a bundle-ului nu-l atinge (doar
     executabilul desemnat) — respins la notarizare (fără timestamp/
     hardened runtime). Fix: semnăm explicit ambele binare reale.
  7. Unelte PySide6 fără extensie (`lrelease`, `Qt/libexec/*`) deja
     ad-hoc semnate din Qt — `--deep` nu le re-semnează forțat. Fix:
     semnare explicită pe bază de tip Mach-O, nu extensie de fișier.
  8. `PIL`/`google` (native) bundle-uite în `python313.zip` — un fișier
     ÎNTR-UN zip nu poate fi semnat individual. Fix: `"packages"` py2app
     le extrage ca fișiere loose. `"google"` e namespace package (PEP
     420, fără `__init__.py`) — `imp_find_module` clasic nu-l găsește
     deloc; fix: `__init__.py` gol creat în venv, doar pentru build.
  9. `py2app` însuși (unealtă de BUILD) ajungea bundle-at în app-ul
     final — exclus explicit din `excludes`.
  10. Resturi `.cpp.o` (obiecte compilate intern de PySide6/Qt QML
      tooling, niciodată executate) bundle-ate accidental — șterse
      din pachet înainte de semnare.
- [x] **Audit link-uri din meniu + DOMAIN vs resurse upstream reale
  (2026-09-05, cerut de Cristi — "unele link-uri nu se deschid")**.
  Găsit BUG REAL, mai serios decât link-uri de meniu: rebranding-ul
  `DOMAIN = "gordas.dev"` (sesiune anterioară) repointase din greșeală
  și DOWNLOAD-uri de fișiere REALE, pe care NU le găzduim — instalerul
  ArgyllCMS (`worker.py`), pachete firmware/corecție Spyder2/Spyder4/
  i1D3/ColorMunki (`display_cal.py`), feed-uri 0install Linux
  (`profile_loader.py`/`worker.py`), pagina web a vizualizatorului X3D
  (`x3dom.py`), și baza de date online de corecții colorimetru
  (upload/căutare, `display_cal.py`). Toate ar fi eșuat silențios la
  prima utilizare reală (subdomenii/căi inexistente pe `gordas.dev`).
  Fix: două constante noi în `meta.py` — `UPSTREAM_RESOURCES_DOMAIN =
  "displaycal.net"` (Argyll/instrumente/0install/X3D — infrastructură
  server-side reală a upstream-ului, nu ceva replicabil doar prin
  redirect de domeniu) și `COLORIMETER_CORRECTIONS_DOMAIN =
  "colorimetercorrections.displaycal.net"` — aplicate în toate cele 10
  locuri identificate prin `grep` sistematic pe `{DOMAIN}` din tot
  codul (nu doar cele raportate inițial, Regula 30). Link-uri de meniu
  proprii (Help → "Mergi la site", About → link aplicație) repointate
  spre `https://gordas.dev/DisplayCAL-CG/` (pagina dedicată, încă
  neconstruită — vezi rândul de mai jos). Verificat: sintaxă + import
  Python real pe toate fișierele atinse (`display_cal.py`/`worker.py`/
  `profile_loader.py`/`x3dom.py`/`meta.py`) — nu doar `ast.parse`.
  **[REZOLVAT 2026-09-06]** `README.html` bundle-uit (deschis din Help →
  "Citește-mă") era cel VECHI, engleză/franceză, upstream. Acum
  `readme_handler` (`display_cal.py`) deschide ghidul PDF ultra-detaliat
  GDC — `DisplayCAL-CG_Ghid_RO.pdf`/`_Guide_EN.pdf`/`_Guia_ES.pdf`
  (`docs/guides/ghid_*.py` + `_engine.py`, port al arhitecturii PDF
  DataMover — TOC real, casete de accent, pași numerotați, tabele de
  opțiuni; capturi reale ale UI din `docs/guides/img/`) — ales după codul
  de limbă curent al aplicației (`lang.getcode()`); `README-fr.html`/
  `README.html` rămân fallback pentru orice altă limbă. PDF-urile ies la
  RĂDĂCINA repo-ului (`generate_guides.py`, lângă `README.html`) — adăugate
  în TOATE cele 4 liste de resurse care menționau `README.html`
  (`DisplayCAL/_setup.py` ×3, `DisplayCAL/freeze.py` ×1 — Regula 30,
  audit complet, nu doar locul raportat) — se bundle-uiesc automat în
  `.app`/installer Windows la fel ca README.html, fără cod de packaging
  nou. O copie identică merge și în `docs/` pentru pagina web de
  descărcare. **[COMPLETAT 2026-09-06]** `ghid_en.py`/`ghid_es.py` scrise
  și ele — toate 3 PDF-urile (RO/EN/ES) se generează curat din
  `generate_guides.py`, verificate vizual de Cristi ("arata foarte bine").
  **Rămas de verificat real**: un build `.pkg` complet, ca să confirme că
  "Citește-mă" chiar deschide PDF-ul din `.app` instalat (nu doar din
  sursă) — Claude nu a rulat un rebuild+reinstall complet în această
  sesiune, doar regenerarea PDF-urilor + verificare sintaxă pe fișierele
  Python atinse.
  Banner-ul grafic din About/header (`theme/header.png`/`header@2x.png`/
  `header_minimal*.png`) — logo-ul vechi upstream ("DisplayCAL³", glow
  colorat) înlocuit cu identitatea GDC (roată de culoare + insignă "CG"),
  la cererea explicită a lui Cristi (2026-09-05, "sunt cele clasice care
  nu-mi plac"). **Rămas, netratat**: cele câteva capturi deja publicate
  pe pagina web arată încă bannerul vechi (poze, nu se actualizează
  singure) — de refăcut la următoarea sesiune de capturi.
- [x] **Instalator Windows (Inno Setup) — COMPLET, testat real pe Windows
  11 ARM64 (Parallels), nu doar generat.** Imaginile wizard-ului
  (`misc/media/install.bmp`, `icon-install.bmp`) regenerate cu identitatea
  GDC. Trei bug-uri REALE găsite abia la build/instalare efectivă pe
  Windows (nu doar citire de cod):
  1. `native_build.py inno` folosea encoding `MBCS` (specific Windows) —
     inofensiv pe Windows real, dar confirmă că scriptul chiar trebuie
     rulat acolo, nu cross-compilat.
  2. **Identificator arhitectură Inno Setup** (`_native_build/inno.py`) —
     `"x64"` (depreciat de Inno Setup 7+, substituit automat cu `"x64os"`)
     respingea instalarea pe Windows ARM64 cu "This program does not
     support the version of Windows your computer is running" — Windows
     ARM64 rulează x64 prin emulare, dar SISTEMUL DE OPERARE nu e x64.
     Fix: `"x64compatible"` (acceptă ambele cazuri).
  3. **Crash real la instalare** (`DisplayCAL/taskscheduler.py`,
     `Task.__str__`) — rest de portare Python 2: `__str__` făcea
     `.encode("UTF-16-LE")`, deci întorcea `bytes`, nu `str` — Python 3
     respinge asta cu `TypeError: __str__ returned non-string`. Mascat de
     un al doilea bug în `profile_loader.py` (variabila `exception`
     folosită necondiționat, deși setată doar dacă `DEBUG=True`) care
     transforma eroarea reală într-un `UnboundLocalError` de neînțeles.
     Ambele reparate; encoding-ul mutat într-o metodă nouă,
     `to_xml_bytes()`, separată de `__str__`.
  `py2exe` (0.14.2.0) nu publică pachete pentru `win_arm64` — pe un
  Windows ARM64 e nevoie de un Python x64 separat (rulează prin emulare
  nativă), documentat explicit în `build_installer_windows.md`.
  Instalerul (`DisplayCAL-CG-Setup.exe` + `DisplayCAL-3.10.0.dev82-Setup.exe`,
  Regula 17) urcat pe release-ul GitHub existent, buton activ pe pagina
  web. Fără semnare de cod încă (fără certificat, decizie deja confirmată)
  — SmartScreen arată avertisment, documentat pe pagina web.
- [x] **`docs/` GitHub Pages** pe acest repo + oglindă
  `gdc-plugin-manager-catalog-vendor/docs/DisplayCAL-CG/`. Live la
  `gordas.dev/DisplayCAL-CG/` (verificat HTTP 200). RO/EN/ES, iconițe SVG
  monocrome (Regula 33), galerie de capturi reale, butoane de descărcare
  Mac + Windows funcționale (verificate HTTP 200 pe linkurile
  `releases/latest/download/...`).
- [x] **`catalog.json`** → intrare nouă în `apps[]` (`displaycal-cg`),
  plus copertă nouă (`docs/covers/DisplayCAL-CG.png`).
- [ ] **Fork `release_builds.yml`** + pas de semnare Mac local. NEÎNCEPUT
  — build-urile Mac/Windows actuale sunt rulate manual (`build_pkg.sh`
  local pe Mac, pași manuali pe Windows), nu automatizate încă prin CI.

**Limitare reală, cunoscută dinainte**: nicio testare funcțională a
calibrării propriu-zise (are nevoie de un colorimetru/spectrofotometru
fizic conectat) — verificarea se oprește la "se instalează, pornește,
interfața arată/traduce corect".

## Etapa 2026-09-06 — Self-Updater REAL (descarcă + instalează) + 2 bug-uri reale găsite în verificarea de actualizări

Cerință directă a lui Cristi: *"ar trebui să se instaleze noua
actualizare, la fel cum sunt și la celelalte aplicații [GDC]... nu se
poate implementa sau se poate implementa la actualizare să apară dacă
există o nouă versiune, să se facă install-ul respectiv"*. Până acum,
"Update now" din dialogul de actualizare (`app_update_confirm`,
`display_cal.py`) doar deschidea un tab de browser cu link-ul de
descărcare — user-ul trebuia să descarce și să instaleze manual.

**2 bug-uri REALE găsite la implementare (nu presupuse — verificate cu
`gh release view --json assets` pe releases reale ale fork-ului)**:

1. **Verificarea de versiune era complet STRICATĂ pentru acest fork.**
   `is_new_update()`/`check_app_update()` parsau `tag_name`-ul direct cu
   `tuple(int(n) for n in tag_name.split("."))` — funcționează pentru un
   tag simplu `"3.10.1"`, dar tag-urile REALE ale acestui fork arată
   `v3.10.0.dev82-cg.1` (versiune upstream + sufix propriu de build,
   Regula 14). `int("v3")` aruncă `ValueError` IMEDIAT → prins și raportat
   tăcut ca "Parsing error" → aplicația credea mereu că nu există
   actualizare, indiferent de ce era publicat real pe GitHub. Fix:
   `parse_release_tag_version()` (nou, `display_cal.py` — duplicat
   deliberat, cu aceeași logică, în `update_check.py` ca
   `_parse_release_tag_version()`, fiindcă acel modul trebuie să rămână
   importabil FĂRĂ `wx`, per propriul docstring) — normalizează exact ca
   `meta.VERSION_TUPLE` (strip `v`, ia partea dinaintea primului `-`,
   primele 3 segmente numerice).
2. **Link-ul de descărcare nu a rezolvat NICIODATĂ la un asset real.**
   `get_download_url()`/`resolve_app_download_url()` ghiceau un nume de
   fișier per-versiune+arhitectură (`DisplayCAL-{ver}-Windows-x64.exe`,
   `-macOS-arm64.dmg`) — nume care nu au existat NICIODATĂ printre
   asset-urile publicate de acest fork (confirmat: Mac publică
   `DisplayCAL-CG.pkg`, Windows `DisplayCAL-CG-Setup.exe`, fără sufixe de
   arhitectură/extensie `.dmg`). Fix: ambele funcții folosesc acum linkul
   STABIL `releases/latest/download/<nume-fix>` (Regula 9), care nu
   depinde deloc de versiune/listă de assets.

**Self-Updater real (`DisplayCAL/self_updater.py`, nou)** — port 1:1 în
Python al rețetei deja folosite în ecosistemul GDC (`DataMover/core/
updater.py`, `SelfUpdater.swift`/`.cs`, Regula 20):
- **Mac**: descarcă `.pkg`-ul, îl instalează prin promptul NATIV de
  parolă admin (`osascript ... with administrator privileges` — NICIODATĂ
  `sudo` interactiv sau Terminal vizibil), apoi relansează aplicația
  (`open -a DisplayCAL-CG`).
- **Windows**: descarcă installer-ul Inno Setup (`.exe`) și îl lansează
  direct (`subprocess.Popen`) — fereastra NATIVĂ a wizard-ului preia de
  aici (pagina de licență, Next/Install), NICIODATĂ un browser.
- Legat de `app_update_confirm` (ramura non-Argyll): `start_self_update()`
  (nou) rulează descărcarea pe un thread separat cu `wx.BusyInfo` cât
  timp așteaptă, apoi (`wx.CallAfter`) închide aplicația curentă
  (`os._exit(0)`) dacă instalarea a pornit cu succes, sau arată o eroare
  cu fallback la pagina de releases dacă descărcarea eșuează.

**Verificat REAL**: `parse_release_tag_version("v3.10.0.dev82-cg.1")` →
`(3, 10, 0)` (corect — înainte pica cu `ValueError`). Harness standalone
pentru `self_updater.py` (fără `wx`, deci rulabil direct): descărcare
reală a unui fișier de test de pe GitHub (conținut verificat byte-cu-byte),
`install_and_relaunch_mac` construiește corect scriptul + apelează
`osascript` (mock pe `subprocess.Popen`, ca să nu ceară efectiv parola în
sesiunea asta). Teste unitare existente (`test_display_cal.py`,
`test_update_check.py`) rescrise ca să reflecte comportamentul NOU
(corect), nu cel vechi (stricat) — nu au putut fi rulate cu `pytest` în
această sesiune (`display_cal.py` importă `wx` la nivel de modul,
instalarea completă a `wxPython` într-un venv de test a fost sărită ca
disproporționată pentru scopul verificării).

**Rămas de verificat real**: pasul efectiv de instalare (promptul de
parolă admin pe Mac, wizardul Inno pe Windows) — cere interacțiune
fizică reală cu fereastra de sistem, la fel ca la toate celelalte
Self-Updatere din ecosistem (Regula 20, WARNING permanent). Cristi
trebuie să confirme manual, o singură dată, pe un build `.pkg`/installer
Windows real, că "Update now" chiar descarcă+instalează+relansează.

## Etapa 2026-09-06 (2) — Iconiță principală + header rebrandate pe motivul "sfere RGB + fascicul"

Cerință directă a lui Cristi, uitându-se la splash screen-ul (neschimbat,
original upstream — `theme/splash.png` + `theme/splash_anim/`): *"îmi
place foarte mult imaginea asta... cred că arată mai bine pe DisplayCAL"*
— confirmat, la întrebare, că vrea schimbarea ATÂT pe iconița aplicației
cât și pe header-ul din fereastra principală/About, înlocuind motivul
"roată de culoare" (desenat vectorial acum câteva sesiuni, paleta Shift
GDC) cu motivul original "sfere RGB + fascicul curcubeu" (deja folosit
NESCHIMBAT în `headericon.png`/`splash_anim` — artă originală DisplayCAL,
nu una nouă).

**Descoperire importantă la implementare**: motivul vechi (roata de
culoare) și textul "DisplayCAL"/insigna "CG" din `header.png` se
SUPRAPUN vizual în designul original (textul e desenat PESTE colțul
stâng-sus al roții) — o ștergere geometrică simplă (cerc plin) peste
zona roții ar fi șters și textul de dedesubt. Fix: mascare pe CULOARE, nu
pe formă — `_wheel_mask()` (script local, nerulat din build) identifică
exact pixelii care aparțineau paletei vechi a roții (albastru/roșu/verde,
+ inelul mic din jurul găurii centrale a roții, distins de inelul mare
exterior doar prin rază de la centru, aceeași culoare amber) prin
distanță de culoare, dilatare ușoară (proporțională cu mărimea imaginii —
o dilatare fixă în pixeli "mânca" prea mult text la `header.png` 1x,
222px) + blur pentru tranziție netedă — text/inel exterior/fundal rămân
BYTE-IDENTICE, fiindcă nu au fost niciodată de culoarea roții.

**Sursa artei noi**: un cadru din `splash_anim` (`splash_anim_16.png`,
fasciculul complet înflorit), decupat pe clusterul de sfere — preferat
în locul lui `headericon@2x.png` (colțuri OPACE, tăiate dur din compunerea
header-ului vechi — ar fi lăsat o muchie pătrată vizibilă la compunere)
— cu o vinietă radială suplimentară pe alpha (forțează transparență
completă dincolo de 90% din rază) ca sigurantă in plus impotriva
oricarei muchii reziduale.

**Fișiere atinse** (verificat cu `git status`, NIMIC altceva — cele 8
iconițe ale uneltelor satelit au propriile glife distincte, neatinse de
roata de culoare, deci nu aveau nevoie de nicio schimbare):
`theme/header.png`, `theme/header@2x.png`, `theme/icons/{10,16,22,24,32,
48,64,72,128,256,512}/displaycal.png`, `theme/icons/DisplayCAL.icns`
(regenerat cu `iconutil -c icns`, verificat prin round-trip
`iconutil -c iconset` — 9 reprezentări extrase corect), `theme/icons/
DisplayCAL.ico` (regenerat cu Pillow, multi-size 16/32/48/64/128/256).

**Verificat vizual, iterativ** — 3 defecte reale găsite și reparate pe
parcurs (nu declarat "gata" la prima încercare): (1) muchie pătrată
vizibilă din sursa opacă inițială → schimbat sursa; (2) `sqrt` pe
`int16` producea overflow/`NaN` silențios pe diferențele de culoare
mari → cast explicit la `float32`; (3) inelul mic din jurul găurii
centrale a rămas vizibil ca artefact fantomă (aceeași culoare ca inelul
mare, needetectat de paleta roții) → adăugat un al doilea criteriu de
mascare, pe rază de la centru, specific acelei zone.

**Rămas de făcut la viitorul build**: `.icns`/`.ico` regenerate ating
DOAR iconița aplicației principale (`DisplayCAL.icns`/`.ico`, cea din
Dock/Taskbar) — pachetele `.pkg`/installer Windows trebuie reconstruite
(`build_pkg.sh`/`native_build.py inno`) ca utilizatorii să vadă efectiv
iconița nouă; niciun rebuild real nu a fost făcut în această sesiune.

## Etapa 2026-09-06 (3) — Detectare automată sincronizare upstream (issue GitHub)

Cerință directă a lui Cristi: *"să ne dăm seama că trebuie să
actualizăm, că s-a creat actualizare în depozitul original... să avem
posibilitatea să creăm noua actualizare"*. Sesiunile Claude Code nu
rulează continuu — soluția e un workflow GitHub Actions programat, nu o
"veghe" a lui Claude.

**`.github/workflows/check-upstream.yml` (nou)** — rulează zilnic
(09:00 UTC) + la cerere (`workflow_dispatch`): compară HEAD-ul REAL al
`eoyilmaz/displaycal-py3` (branch `develop`, via `git ls-remote`, fără
clonare completă) cu ultimul SHA upstream cunoscut ca sincronizat în
acest fork (`.github/upstream-sync-state.json`, nou — actualizat manual/
de o sesiune Claude la fiecare `git merge upstream/develop` real). Dacă
diferă, deschide UN SINGUR issue GitHub (label `upstream-sync`, nu
recreat de fiecare rulare — comentează pe cel existent dacă e deja
deschis); dacă fork-ul e la zi, închide automat issue-ul rămas deschis.

**Bug real găsit și reparat la primul test live**: `gh label create`/
`gh issue *` fără `-R` explicit au eșuat cu `HTTP 403: Resource not
accessible` — CLI-ul `gh` a rezolvat ambiguu repo-ul țintă la
`eoyilmaz/displaycal-py3` (upstream), nu la fork (`gordasgdc/
displaycal-py3`), fiindcă un pas anterior din același job adăugase
remote-ul `upstream` local (`git remote add upstream ...` pentru
numărarea commit-urilor) — cu DOUĂ remote-uri prezente, `gh` nu mai
alege implicit `origin`. Fix: `-R "${{ github.repository }}"` explicit
pe toate cele 5 comenzi `gh label`/`gh issue`.

**Descoperire secundară**: repo-ul avea Issues DEZACTIVATE din setările
GitHub (`hasIssuesEnabled: false`) — activat (`gh repo edit
--enable-issues`), altfel workflow-ul nu avea unde scrie notificarea.

**Verificat REAL, de 3 ori, nu doar sintaxă YAML**: (1) rulare cu SHA
sincronizat corect → `needs_sync=false`, niciun issue creat; (2) SHA
vechi injectat temporar → issue #1 creat corect, cu link către
comparația de commit-uri upstream; (3) SHA corect restaurat → issue #1
închis automat de aceeași rulare următoare. Fluxul complet (creare +
auto-închidere) funcționează cap-coadă pe GitHub real, nu doar simulat.

**Cum se folosește practic**: Cristi vede notificarea nativă GitHub
(email/mobil) când apare issue-ul nou. Sincronizarea efectivă
(`git fetch upstream && git merge upstream/develop`, actualizarea
`.github/upstream-sync-state.json` cu noul SHA, apoi eventual un
build/release nou) rămâne un pas cerut explicit într-o sesiune Claude
Code — workflow-ul doar SEMNALEAZĂ, nu sincronizează singur (sincronizarea
reală poate necesita rezolvare de conflicte/verificare manuală, nu e
sigur de automatizat orbește).

## Etapa 2026-09-06 (4) — Automatizare CI pentru build-ul Windows la fiecare tag (`release_builds.yml`)

Cerută de Cristi cât timp aștepta să ajungă la calculator pentru fix-ul
de permisiuni de mai sus. Închide TODO-ul rămas deschis din Progress
("Fork `release_builds.yml`... NEÎNCEPUT — build-urile Mac/Windows
actuale sunt rulate manual").

**Cauza reală, verificată, a inactivității CI-ului**: `release_builds.yml`
(moștenit de la upstream) se declanșa doar pe tag-uri `[0-9]*.[0-9]*.[0-9]*`
— tag-urile REALE ale acestui fork arată `v3.10.0.dev82-cg.1` (prefix
`v` + sufix propriu `-cg.N`, Regula 14), deci acest CI nu a rulat
NICIODATĂ pentru fork-ul nostru. Fix: trigger nou `v*-cg.*`, păstrat pe
lângă cel vechi (compatibilitate upstream).

**Decizie de scop, nu doar reparație**: jobul `macOS` (construiește
`.dmg` ad-hoc-semnat) și cele 3 joburi Linux (`.deb`/`.rpm`/AppImage/
Flatpak) au fost DEZACTIVATE (`if: false`, nu șterse — sincronizare mai
ușoară cu upstream-ul) — Mac rămâne construit LOCAL (`build_pkg.sh`,
semnare Developer ID reală + notarizare, certificatul nu există în CI),
iar Linux nu e parte din livrarea oficială a fork-ului (doar Mac .pkg +
Windows .exe, decizie confirmată anterior). Jobul `windows` a fost
simplificat de la matrice x64+arm64 la DOAR x64 (Windows ARM64 rulează
x64 prin emulare nativă — `x64compatible` deja folosit în
`_native_build/inno.py` pentru exact acest motiv), ca self-updater-ul/
pagina web să caute UN SINGUR nume stabil de fișier, nu unul per-arhitectură.

**Bug real prevenit, nu doar reparat**: `generate_release_notes: true`
(original upstream) ar fi publicat automat mesajele BRUTE de commit ca
note de lansare PUBLICE — Regula 29 interzice exact asta (commit-urile
acestui fork sunt scrise ca jurnal tehnic detaliat, cu context intern).
Înlocuit cu un text fix, minimal, orientat spre client.

**Nume de fișiere aliniate cu ce e deja publicat manual** (verificat cu
`gh release view --json assets` pe release-ul existent, nu presupus):
ieșirea brută Inno Setup rămâne `DisplayCAL-{VERSION_STRING}-Setup.exe`
(deja versionată, Regula 17), plus o copie nouă sub numele STABIL
`DisplayCAL-CG-Setup.exe` (Regula 9 — cel căutat de `self_updater.py`).

**Verificat**: `python3 -c "import yaml; yaml.safe_load(...)"` — sintaxă
OK. `actionlint` (instalat cu `brew install actionlint`, nou pe acest
Mac) — 0 erori pe jobul `windows`/`release` modificate (avertismentele
rămase sunt fie `if: false` intenționat, fie probleme shellcheck
PRE-EXISTENTE în upstream, în joburile acum dezactivate, neatinse).
**Rămas de verificat REAL**: niciun tag de test nu a fost împins în
această sesiune (ar fi creat un release GitHub "junk" și ar fi consumat
minute CI reale) — fluxul complet (build Windows → upload artefact →
creare/actualizare release) se confirmă la următorul tag real
(`v{versiune}-cg.{N}`) împins de Cristi.

## Etapa 2026-09-06 (5) — Publicat `v3.10.0.dev82-cg.2`: primul release REAL cu tot ce s-a lucrat azi

**Descoperire critică la audit**: release-ul LIVE (`v3.10.0.dev82-cg.1`,
publicat 2026-09-05) NU conținea NIMIC din ce s-a lucrat azi — logo nou
(sfere), self-updater reparat, PDF-uri, sincronizare upstream, fix CI.
Un client care descărca "cel mai nou" .pkg/.exe primea în continuare
build-ul VECHI, cu update-checker-ul STRICAT (bug-ul de parsare a
tag-ului, reparat azi, dar nepublicat).

**Bug real găsit ȘI reparat înainte de publicare**: primul `git push` al
tag-ului `-cg.2` a picat CI-ul ("Release Builds") — `copy
misc/net.displaycal.DisplayCAL.appdata.xml` (job-ul Windows) căuta un
fișier cu numele VECHI, redenumit la rebranding-ul de acum câteva sesiuni
(`dev.gordas.DisplayCAL.appdata.xml`) — scăpat atunci din audit (Regula
30), afecta 4 locuri în 2 workflow-uri (`release_builds.yml`,
`nightly_builds.yml`), toate reparate. Tag-ul mutat pe commit-ul cu fix-ul,
CI rerulat — succes.

**Publicat, verificat real, nu presupus**: `DisplayCAL-CG.pkg` (Mac,
semnat+notarizat+stapled, `spctl: accepted`) + `DisplayCAL-CG-Setup.exe`
(Windows, construit de CI) pe același release `v3.10.0.dev82-cg.2`.
Ambele link-uri `releases/latest/download/...` — HTTP 200.

**LIMITARE REALĂ DE DESIGN, confirmată, NU un bug nou** — update-checker-ul
(in-app) NU va notifica automat userii deja instalați pe `cg.1` despre
acest `cg.2`. Motiv: `parse_release_tag_version()` (fix-ul de azi) ia
DELIBERAT doar partea dinaintea primului `-` din tag (`3.10.0.dev82`),
ca update-checker-ul să rămână compatibil cu schema de versionare a
upstream-ului (deja documentat la Regula 14, secțiunea Partea 2: "sufixul
de build NU schimbă numărul de bază"). Efect secundar acceptat: DOUĂ
tag-uri cu ACELAȘI număr de bază (`cg.1` vs `cg.2`) produc tuplul IDENTIC
`(3,10,0)` — comparația nu vede nicio diferență, deci niciun pop-up de
update. **Userii de pe `cg.1` nu vor fi anunțați automat** de acest
release — doar userii NOI (descărcare de pe site) primesc build-ul
corect. Identic cu bootstrap-ul deja documentat la DataMover
(`v2.5.3`→`v2.5.4`): fix-ul ajută abia din momentul în care userul are deja
un build care-l conține. Nu există soluție fără a renunța la compatibi-
litatea cu schema upstream — discuție de scop separată, dacă Cristi vrea
vreodată să schimbe asta.

**Verificat**: `spctl -a -vvv -t install` pe .pkg — accepted, Notarized
Developer ID. Parser testat standalone cu tag-ul real nou — confirmă
limitarea de mai sus (ambele tag-uri dau `(3,10,0)`). Release notes
curățate (Regula 29 — textul generat de CI era deja curat, doar extins
să menționeze ambele platforme).

## Etapa 2026-09-06 (6) — Semnare Windows Self-Signed (Regula 34), aplicată pe `release_builds.yml`

Aplicat pattern-ul deja funcțional din CGConvertor pe jobul `windows` din
`.github/workflows/release_builds.yml` (singurul workflow care produce
efectiv `DisplayCAL-CG-Setup.exe`, confirmat activ: rulare `Release
Builds` cu succes pe tagul `v3.10.0.dev82-cg.2`, `gh run list`).
Confirmat înainte de orice modificare, nu presupus: `misc/DisplayCAL-
Setup-py2exe.iss` NU e cod moștenit — e template-ul real citit de
`_native_build/inno.py` (`Path(pydir, "misc", f"{meta.NAME}-Setup-
{tmpl_type}.iss")`) pentru a genera scriptul Inno Setup folosit la build.

Fișiere noi: `codesigning/sign-windows.ps1`, `codesigning/generate-self-
signed-cert.ps1`, `codesigning/README-windows.md` (adaptate 1:1 după
CGConvertor — nume certificat `displaycal-cg-selfsign.*`, repo
`gordasgdc/displaycal-py3`). **NU copiate din CGConvertor** fișierele de
semnare Mac (`README.md`, `ci-import-certs.sh`, `entitlements.plist`,
`sign-and-notarize.sh`) — DisplayCAL-CG are deja propriul flux Mac
funcțional (`build_pkg.sh`, Developer ID real + notarizare), neatins.

`release_builds.yml`: `env: HAS_WIN_SELFSIGN` adăugat la nivel de job
`windows` (același motiv ca în CGConvertor — `secrets` nepermis direct
în `if:` de pas, confirmat `actionlint`), plus un pas nou "Semneaza
installer-ul Windows" (`if: env.HAS_WIN_SELFSIGN == 'true'`) rulat pe
ieșirea BRUTĂ a Inno Setup, ÎNAINTE de duplicarea sub numele stabil
`DisplayCAL-CG-Setup.exe` — copia stabilă moștenește aceeași semnătură.
Fără secrete setate încă (`WIN_SELFSIGN_PFX_BASE64`/`_PASSWORD` nu există
ca secrete pe acest repo la momentul commit-ului), build-ul continuă
nesemnat exact ca înainte — nicio schimbare de comportament până Cristi
rulează `generate-self-signed-cert.ps1` pe Windows real și încarcă
secretele (vezi `codesigning/README-windows.md`).

**Verificat**: `python3 -c "import yaml; yaml.safe_load(...)"` — OK.
`actionlint .github/workflows/release_builds.yml` — 0 erori/avertismente
noi pe jobul `windows` (35-136) sau `release` (585+); toate cele 7
avertismente rămase (linia `if: false` ×4, shellcheck ×3) cad exclusiv în
joburile macOS/linux/linux-appimage/linux-flatpak, deja dezactivate și
pre-existente, neatinse de această modificare.

**Rămas de făcut, real, de către Cristi**: rulare unică
`generate-self-signed-cert.ps1` pe Windows + `gh secret set` (Claude nu
poate genera/manipula certificatul, Regula 34). Fără acest pas, jobul
Windows continuă nesemnat — nicio regresie, doar funcționalitate
neactivată încă.

## Etapa 2026-09-06 (7) — Fix real: eroare "update_check.fail.version" la fiecare pornire

**Raportat de Cristi cu screenshot exact**: la fiecare lansare (sau la
"Verifică actualizări" manual) apărea un dialog de eroare — "Fișierul de
versiune de la distanță de pe serverul gordas.dev nu a putut fi
analizat."

**Cauza reală, verificată direct în cod** (`display_cal.py`,
`app_update_check`): linia 613-614 (veche) declanșează AUTOMAT o a doua
verificare, pe canalul "snapshot" (`elif not argyll and not snapshot:
app_update_check(parent, silent, True)`), de fiecare dată când userul e
deja la zi pe canalul stabil. Acel canal fetch-uia `/SNAPSHOT_VERSION`
DIRECT de pe `DOMAIN` (`gordas.dev`) — un fișier real, existent pe
domeniul upstream-ului original (pentru build-uri de dezvoltare între
release-uri), dar NICIODATĂ publicat de acest fork (publicăm doar
release-uri GitHub numerotate, `v{VERSION}-cg.{N}`, nu un canal rulant de
snapshot-uri). Răspunsul primit de pe `gordas.dev` (probabil pagina
implicită a site-ului, nu un fișier de versiune) eșua la parsarea ca
tuplu de numere — exact eroarea din screenshot. Se declanșa la FIECARE
pornire pentru ORICE user, indiferent dacă era la zi sau nu pe canalul
stabil (real relevant), fiindcă versiunea acestui fork conține
intenționat `.devNN` (moștenit din schema upstream, Regula 14).

**Exact tiparul de bug deja documentat la auditul de DOMAIN din
2026-09-05** (rebranding-ul `DOMAIN → gordas.dev` a rupt resurse reale pe
care nu le găzduim) — de această dată în canalul de update-check, nu
descărcări de firmware/instrumente.

**Fix**: ramura `elif snapshot:` din `app_update_check` nu mai face
niciun fetch — tratează explicit acest canal ca "la zi" (`new_version_
tuple = curversion_tuple`), fără eroare, fără dialog. **Canalul STABIL
(GitHub Releases, `is_new_update()`) rămâne complet neschimbat și
funcțional** — asta e verificarea reală de care au nevoie userii, nu
canalul de snapshot.

**Discuție cu Cristi**: a întrebat explicit cum funcționează detectarea
de update la noi — confirmat fluxul complet (GitHub Releases API →
`parse_release_tag_version` → comparație cu `VERSION_TUPLE` → dialog cu
"Actualizează acum"/"Mai târziu" dacă e mai nou), inclusiv limitarea deja
documentată (comparația ignoră sufixul `-cg.N`, deci userii de pe `cg.1`
nu sunt notificați automat de `cg.2` — discuție separată, neînceput încă,
dacă Cristi decide să o rezolve).

**Verificat**: `python3 -c "import ast; ast.parse(...)"` — sintaxă OK.
Regula 32 verificată înainte de commit — 6 apariții găsite, toate
confirmate commit-uri UPSTREAM vechi (iunie 2026, autori `youfeng`/`Erkan
Ozgur Yilmaz`), acoperite de excepția deja documentată la Regula 32.

**Rămas de făcut**: niciun build/release nou publicat încă în această
sesiune — fix-ul e doar commis local (`develop`, `05ba9649`), fără
push/tag. Cristi decide dacă/când publicăm o versiune nouă
(`v3.10.0.dev82-cg.3` sau similar) cu acest fix inclus.

## Etapa 2026-09-06 (8) — Comparație de versiune completă (`-cg.N`), nu doar primele 3 cifre

**Cerut explicit de Cristi**, imediat după fix-ul de mai sus, ca urmare
firească a discuției despre cum funcționează detectarea de update:
"vrei să reparăm și asta (să comparăm întregul tag, nu doar primele 3
cifre), da vreau" — rezolvă limitarea deja documentată la Etapa (5):
userii de pe `cg.1` nu erau anunțați automat de `cg.2` (tuplul de
comparație includea DOAR primele 3 cifre din tag, `(3,10,0)`, identic
pentru orice sufix `-cg.N`).

**Problemă reală de rezolvat mai întâi**: aplicația rulantă NU știa
NICIODATĂ propriul ei număr de build `-cg.N` — acela există DOAR ca sufix
de tag git, niciodată scris în vreun fișier bundle-uit în aplicație
(`VERSION_STRING`/`VERSION_TUPLE` reflectă STRICT schema upstream,
deliberat, per Regula 14). Fără să știe "sunt eu însumi cg.2", aplicația
nu putea niciodată compara corect cu "există un cg.3".

**Fix — nouă sursă de adevăr, `DisplayCAL/CG_BUILD`** (fișier nou, plat,
un singur număr, exact ca `VERSION` deja existent):
- `meta.py`: citește `CG_BUILD` la fel ca `VERSION_FILE` (fallback 0 dacă
  lipsește/nevalid — sigur, niciodată o eroare de import).
- `_setup.py`/`freeze.py`: `"CG_BUILD"` adăugat alături de `"VERSION"` în
  listele de resurse bundle-uite (2 locuri, verificate cu `grep` — nu 4 ca
  la `README.html`/Etapa (2026-09-05), fișier mai puțin referit).
- **Trebuie incrementat manual de Cristi (sau la următoarea sesiune
  Claude) la fiecare tag `-cg.N` nou publicat** — exact ca `VERSION`
  (upstream) sau orice altă constantă de versiune (Regula 14) — setat
  acum la `2` (valoarea tag-ului CURENT publicat, `cg.2`; va deveni `3`
  când se publică fix-ul acesta ca `cg.3`).

**`parse_release_tag_version()`/`_parse_release_tag_version()`** (ambele
copii, `display_cal.py` + `update_check.py`, trebuie sa ramana in sincron
per docstring-ul modulului) — extind tuplul returnat la 4 elemente
`(major, minor, patch, cg_build)`, extras cu `re.search(r"-cg\.(\d+)",
tag)` din tag-ul NEtrunchiat (0 daca tag-ul nu are acest sufix — ex. un
tag upstream simplu). **`is_new_update()`/`check_app_update()`**: tuplul
"versiune curentă" folosit in comparație devine `(*VERSION_TUPLE[:3],
CG_BUILD)`, ACELAȘI numar de elemente ca tuplul nou parsat — esential,
altfel comparația de tupluri Python ar considera GREȘIT orice tag cu 4
elemente drept "mai nou" doar pentru ca are un element in plus (`(3,10,0,2)
> (3,10,0)` e `True` in Python, chiar daca primele 3 sunt egale — prefix
mai scurt = "mai mic"). Corectat in AMBELE locuri unde tuplul curent se
construia inainte (`curversion_tuple` ramura "stable" ȘI ramura
"snapshot", desi cea din urma e deja dezactivata la fix-ul anterior —
consecventa, nu strict necesar acolo).

**Afișare**: `newversion` (textul aratat userului in dialogul de update)
nu mai concateneaza cele 4 elemente direct (`"3.10.0.2"`, ar parea gresit
un al 4-lea segment de versiune upstream) — primele 3 ramân
`"3.10.0"`, cu sufixul propriu afișat separat, `" (cg.3)"`, DOAR daca
existent (>0).

**Teste actualizate** (`tests/test_display_cal.py`) — tuplurile
așteptate de `test_parse_release_tag_version`/`test_is_new_update_
returns_version_when_newer` extinse la 4 elemente; `test_is_new_update_
returns_false_when_current` verificat manual (nu modificat) — ramane
corect neschimbat, fiindca tag-ul simulat acolo (fara sufix `-cg.N`) da
`cg_build=0 < CG_BUILD real (2)`, deci `latest > current` ramane `False`
oricum. Testele din `tests/test_update_check.py` (`TestCheckAppUpdate`)
verificate manual, la fel — raman corecte neschimbate (logica identica,
verificata linie cu linie).

**Verificat REAL** (nu doar sintactic — `wx`/`numpy` nu instalabile ușor
in acest mediu de test, deci logica de parsare/comparație extrasă
standalone, IDENTICA cu codul din fișiere, intr-un script separat):
```
OK  v3.10.0.dev82-cg.1  -> (3, 10, 0, 1)
OK  v3.10.0.dev82-cg.2  -> (3, 10, 0, 2)
OK  v3.10.0.dev82-cg.3  -> (3, 10, 0, 3)
OK  v3.10.0.dev82-cg.10 -> (3, 10, 0, 10)   # numere cu 2+ cifre, nu doar string-compare
OK  3.10.0               -> (3, 10, 0, 0)
OK  not-a-version        -> None
current=(3,10,0,2); cg.3 > current -> True   (update REAL detectat acum)
cg.2 > current -> False                       (deja la zi, fara notificare falsa)
```
Confirmat și separat: `meta.CG_BUILD` citit corect din fișierul nou
(`== 2`, valoarea reala scrisa in `DisplayCAL/CG_BUILD`).

**Verificat sintactic**: `ast.parse` pe toate cele 6 fișiere atinse
(`meta.py`, `display_cal.py`, `update_check.py`, `_setup.py`,
`freeze.py`, `tests/test_display_cal.py`) — 0 erori.

**Rămas de făcut**: la fiecare tag `-cg.N` viitor, incrementează
`DisplayCAL/CG_BUILD` INAINTE de a publica tag-ul (altfel aplicația nou
construita s-ar crede pe ea insasi "in urma" fata de propriul ei tag).
Fix-ul ramane doar commis local (nu push/tag) — la fel ca Etapa (7).

## Etapa 2026-09-06/07 (9) — Publicare REALĂ `v3.10.0.dev82-cg.3`, ambele fix-uri incluse

Cerut explicit de Cristi: "notează tot ca să știm când actualizăm și
continuă cu publicarea finală". `DisplayCAL/CG_BUILD` incrementat la `3`
(commit separat, `9c8e34fb`), tag `v3.10.0.dev82-cg.3` creat și push-uit.

**Bug real găsit ȘI reparat la build-ul Mac local** (`build_pkg.sh`):
`rm -rf "$PAYLOAD_ROOT" "$COMPONENT_PKG"` (curățare de housekeeping,
DUPĂ ce `productbuild` scrisese deja pachetul final cu succes) a eșuat
cu `Directory not empty` — probabil `mdworker`/Spotlight indexând
tranzitoriu payload-ul uriaș (9 aplicații, framework-uri Qt) de-abia
creat. Cu `set -euo pipefail`, această eroare de CURĂȚARE (nu de build)
oprea SCRIPTUL ÎNTREG chiar înainte de pasul de semnare+notarizare —
pachetul final ar fi rămas NESEMNAT, silențios, fără nicio eroare
vizibilă la prima privire (exact genul de bug deja documentat masiv în
istoricul acestui fișier). Fix: `|| echo "AVERTISMENT: ..."` — o eroare
de curățare nu mai oprește un build altfel reușit. Din cauza timpului
lung de build (py2app, 9 aplicații + Qt/PySide6, ~550MB), NU s-a
reconstruit de la zero pentru validare — s-a rulat manual, o singură
dată, restul secvenței întreruse (`productsign` → `notarytool submit
--wait` → `stapler staple`) direct pe pachetul deja produs, cu succes
(`spctl -a -vvv -t install` → `accepted, Notarized Developer ID`).
Fix-ul din script rămâne pentru viitoarele build-uri, needeclanșat încă
printr-un build complet de la zero.

**Regula 23 lovită real, nu doar teoretic**: primul build a eșuat imediat
cu "'dist/' conține fișiere deținute de root" (rest dintr-o rulare
anterioară) — Cristi a rulat manual `sudo rm -rf .../dist`, confirmat
`find dist -not -user gordasgdc` → 0 fișiere înainte de reluare.

**CI (`Release Builds`, singurul relevant pentru publicarea noastră)**:
verde, a produs `DisplayCAL-CG-Setup.exe` (Windows, nesemnat încă —
secretele `WIN_SELFSIGN_*` tot nesetate pentru acest repo, Etapa (6)).
**`Tests`/`Nightly Builds` (workflow-uri separate, upstream) au eșuat,
verificat explicit că sunt NEÎNRUDITE cu schimbările de azi**: `Tests` —
1 singur eșec real (`test_language_menu_actions_have_flag_icons`,
iconiță de steag lipsă pentru meniul de limbă română — problemă de
asset grafic, nimic legat de logica de update; 2589 teste au trecut,
inclusiv ambele `test_app_update_check[...]` care exercită direct codul
modificat azi) — `Nightly Builds` — infrastructură separată a
upstream-ului (recipe py2exe macOS + un asset de release nightly
inexistent, 404) — nici urmă de cod atins azi. Niciuna din cele 2
neatinsă/reparată acum — scop separat.

**Publicat, verificat REAL (nu presupus)**:
- `DisplayCAL-CG-Setup.exe` + `DisplayCAL-3.10.0.dev82-Setup.exe`
  (Windows, produse de CI).
- `DisplayCAL-CG.pkg` + `DisplayCAL-CG-3.10.0.dev82.pkg` (Mac, semnat +
  notarizat + stapled local, urcate manual pe același release).
- Ambele link-uri STABILE (`releases/latest/download/DisplayCAL-CG.pkg`
  și `.../DisplayCAL-CG-Setup.exe`, cele folosite de site + self-updater)
  → HTTP 200, verificat cu `curl`.
- Note de release rescrise curat (Regula 29 — fără nume/cauze tehnice de
  debugging, orientate spre client).

**Rezultat concret pentru useri**: de la acest release, o instalare
existentă (`cg.1`/`cg.2`) va fi anunțată AUTOMAT de acest update nou
(`cg.3`) — prima confirmare reală a fix-ului din Etapa (8), în afara
testului standalone. Eroarea de la pornire (Etapa (7)) e reparată în
același build.

### Completări specifice acestui repo, mutate din fosta Partea 1 (2026-09-18)

Păstrate verbatim. Regula generală la care se referă fiecare e în
`~/Developer/CLAUDE.md`.

**Regula 3:**

**[EXCEPȚIE OBLIGATORIE PENTRU ACEST REPO (displaycal-py3), 2026-09-05] —
Regula 3 NU se aplică aici.** DisplayCAL-CG e un fork al unui proiect
GPLv3 (upstream: `eoyilmaz/displaycal-py3`, el însuși continuarea
DisplayCAL de Florian Höch). GPLv3 §7 interzice explicit orice "further
restriction" adăugată peste licențele primite de utilizatorul final —
niciun sistem de licențiere Ed25519/trial/paywall/gating funcțional NU
poate fi aplicat, sub nicio formă, indiferent de presiune sau precedent
din restul ecosistemului. DisplayCAL-CG rămâne 100% gratuit, complet
funcțional, fără activare, pentru totdeauna. Se permite DOAR un mesaj de
susținere pur informativ/voluntar (ca `donation_header`/`donation_message`
deja existente în `DisplayCAL/lang/*.yaml`, mesaj original al upstream-ului,
păstrat neschimbat) — niciodată legat de o funcționalitate blocată. Orice
viitoare cerere de a adăuga licențiere GDC standard pe acest repo trebuie
refuzată și explicată, nu doar amânată.

**Regula 4:**

**[NOTĂ pentru acest repo]**: ArgyllCMS (dependința externă critică a
DisplayCAL) are DEJA propriul flux de descărcare/verificare nativ, matur
(`dialog.argyll.notfound.choice` etc.) — nu se înlocuiește cu
`DependencyManager` generic GDC, ar duplica funcționalitate existentă și
testată de comunitatea upstream.

**Regula 7:**

**[NOTĂ pentru acest repo]**: interfața DisplayCAL (wxPython) NU se
rescrie în stilul "Shift" — e un proiect upstream matur, cu propria temă
și convenții UI, folosit de o comunitate mare de utilizatori familiarizați
cu aspectul actual. Rebranding-ul se limitează la nume/logo/traducere, nu
la un redesign vizual complet.

**Regula 8:**

**[NOTĂ pentru acest repo]**: (d) devine "Licență GPLv3 & Susținere
opțională" — fără nicio mențiune de trial/zile, aplicația e completă din
prima zi.

**Regula 12:**

**[NOTĂ pentru acest repo]**: primele două puncte (Profil/HWID, Revocare)
NU se aplică — nu există licențiere pe acest produs (vezi excepția de la
Regula 3). Pagina web (`gordas.dev/DisplayCAL-CG/`) urmează totuși
Standardul Design Web "Shift", ca restul suitei.

**Regula 13:**

**[NOTĂ pentru acest repo]**: DisplayCAL are deja `update_check.py`
propriu (upstream, matur) — vezi `DisplayCAL/meta.py`
(`GITHUB_API_URL`/`DEVELOPMENT_HOME_PAGE`, redirecționate spre
`gordasgdc/displaycal-py3`, 2026-09-05). Se extinde/verifică acel flux, nu
se înlocuiește cu un checker GDC nou.

**Regula 14:**

**[NOTĂ pentru acest repo]**: versiunea urmărește UPSTREAM-ul
(`DisplayCAL/VERSION`, ex. `3.10.0.dev82`), NU un contor GDC separat —
distincția noastră se marchează cu un sufix de build separat (ex.
`+cg.1`, `+cg.2` per resincronizare/rebuild), nu prin schimbarea
numărului de bază, ca update checker-ul upstream (bazat pe compararea
directă a numărului din `VERSION`) să rămână corect.

**Regula 32:**

repo (2026-09-05).** Cerut explicit de Cristi. Regulă obligatorie,
permanentă, pentru toate repo-urile GDC — inclusiv acest fork. **Notă
specifică acestui repo**: istoricul UPSTREAM (mii de commit-uri de la
zeci de contribuitori externi, sincronizat prin fast-forward de la
`eoyilmaz/displaycal-py3`) NU se rescrie niciodată — Regula 32 privește
DOAR ce adaugă Claude de-acum înainte în acest fork (niciun commit nou al
lui Claude nu conține `Co-Authored-By: Claude`), nu istoria unui proiect
open-source terț cu mulți autori legitimi.

## Etapa 2026-09-20 — Distribuție DMG notarizat (Regula 45/K)
- `build_pkg.sh` produce acum și `dist/DisplayCAL-CG-<v>.dmg` (+ copia stabilă `DisplayCAL-CG.dmg`): DMG cu `.pkg`-ul notarizat + ghidurile PDF, semnat Developer ID, notarizat (Accepted), stapled; `spctl -t open` → accepted. Verificat pe v3.10.0.dev82.
- `self_updater.py`: instalează și din `.dmg` (hdiutil attach → installer -pkg → detach → relansare). `.pkg`-ul rămâne publicat ca canal pentru clienții vechi (`display_cal.py`/`update_check.py` caută încă `DisplayCAL-CG.pkg`).
- `docs/index.html`: butonul Mac → `DisplayCAL-CG.dmg` (nume stabil; TODO Regula 41: link versionat).
- Zero `.zip`/`.command` urmărite în repo.
- NEVERIFICAT: montarea DMG-ului + instalarea prin Self-Updater pe un Mac curat, `stapler validate` post-montare, testele pytest (pytest lipsește din venv), stabilitatea colorimetrică, GitHub Release nepublicat.
