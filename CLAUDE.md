# DisplayCAL-CG — reguli de arhitectură

> **[SYSTEM DIRECTIVE FOR CLAUDE: DO NOT DELETE OR OVERWRITE EXISTING RULES. ONLY APPEND NEW RULES.]**
> Jurnal viu, nu document care se rescrie. La orice actualizare, adaugă la finalul secțiunii potrivite — nu șterge/înlocui reguli vechi decât dacă sunt explicit invalidate de o schimbare reală (și atunci marchează-le **[ÎNVECHIT]** cu motivul, nu le șterge din istoric).

Citit automat de Claude Code la fiecare sesiune în acest repo.

## [PARTEA 1: REGULI GLOBALE ECOSISTEM GDC — identică în toate proiectele GDC]

> Acest bloc e sincronizat manual în `CLAUDE.md`-ul TUTUROR proiectelor din
> `~/Developer/` (CGConvertor, CursorPro, DataMover, GDCPluginManager,
> GDCPluginManagerWin, GDCVault, GDCVaultWin, gdc-plugin-manager-catalog-vendor,
> gdc-plugin-manager-files, gdc-production-manager, gdc-resolve-encoder,
> displaycal-py3, și orice proiect GDC nou). Dacă modifici o regulă aici,
> propag-o manual și în celelalte fișiere — nu există un fișier
> partajat/include, fiecare `CLAUDE.md` e citit independent per-repo. Vezi
> jurnalul "Sincronizare CLAUDE.md" din secțiunea Partea 2 a fiecărui repo
> pentru data ultimei unificări.

**1. Directoare & structură.** Toate proiectele GDC trăiesc exclusiv în
`~/Developer/<NumeProiect>/`, niciodată în `~/Downloads` sau `~/Desktop`
(curățate automat de CleanMyMac/Hazel pe acest Mac — au șters repo-uri de
sursă în trecut). Niciun repo nou nu se creează/clonează în afara
`~/Developer/`. Certificatele Apple (`.p12`/`.cer`) și orice cheie privată
(`.p8`/`.key`/`.pem`/`.mobileprovision`) stau EXCLUSIV în
`~/Developer/Certificates/` (folder în afara oricărui repo git) — niciodată
comise, indiferent de `.gitignore`.

**2. Securitate — zero secrete în git.** `.git/config` nu conține niciodată
un token în clar în URL-ul remote-ului (`https://user:TOKEN@github.com/...`)
— autentificare exclusiv prin `gh` (credential helper) sau SSH. Orice token
găsit expus se elimină din config imediat; revocarea efectivă din GitHub
Settings e un pas manual al lui Cristi (Claude nu poate revoca un token).
Un secret comis vreodată în istoricul git (verificat cu
`git log --all -p | grep` sau echivalent) trebuie semnalat explicit, nu doar
curățat din starea curentă.

**3. Licențiere & Donație (GDC Plugin Manager / Furnizor).** Toate
aplicațiile standalone GDC folosesc `LicenseCore`/`MachineID` (Ed25519,
aceeași cheie publică hardcodată în tot ecosistemul — copiată byte-for-byte,
NU printr-o dependință de pachet între repo-uri). Probă gratuită implicită:
**15 zile**. Activare manuală prin WhatsApp (ID de mașină pre-completat) →
cod generat din `GenerateSerialView.swift` (Furnizor, `gdcStandaloneProducts`
trebuie să includă `productID`-ul noii aplicații). Valoarea susținerii
aplicației se exprimă EXCLUSIV ca **donație** — sumă implicită de referință
**23 €** dacă nu există alt preț promoțional documentat pentru acea
aplicație — NICIODATĂ cu cuvintele „preț", „cumpără" sau „vânzare" (RO/EN/ES:
niciodată „price"/„buy"/"sale" nici în engleză/spaniolă). Formularea trebuie
să apară clar în: UI-ul aplicației (ecran/pop-up de licență), ghidul PDF, și
orice pagină web dedicată.

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

**[COMPLETARE 2026-08-26, închide o lacună de scop reală]** Interdicția de
mai sus se aplică ACUM și produselor din catalogul GDC Plugin Manager
(LUT/DCTL/PowerGrade vândute prin marketplace-ul gratuit) — găsit la audit
un card cu buton „Cumpără" și sume afișate brut („378,00 €"). Butonul
devine „Donează" peste tot (RO/EN/ES); suma documentată de furnizor pentru
acel produs (promoția specifică lui, nu neapărat 23 €) rămâne vizibilă, dar
NICIODATĂ lângă cuvântul „preț"/„cumpără"/„vânzare" — decizia anterioară de
scop (marketplace = "relație comercială diferită, nu se aplică") e
INVALIDATĂ explicit. Excepție: tabelele interne ale Furnizorului (ex.
`SalesHistoryView`, coloana „Preț" din registrul de vânzări al lui Cristi)
nu sunt UI orientat spre client — rămân neatinse.

**15. CRM Furnizor — set minim de funcționalități administrative
(2026-08-26).** Panoul de Clienți al Furnizorului (`SalesHistoryView.swift`)
nu rămâne un log rigid — trebuie să ofere: filtrare rapidă pe produs
(dropdown dinamic, nu hardcodat), export 1-click (clipboard sau fișier) al
email-urilor/HWID-urilor din selecția curentă (filtrată), copiere rapidă
per-câmp direct din tabel (fără să deschizi editarea), Licențiere în Masă
(paste o listă de email-uri/machine ID-uri → generează automat câte o
licență per linie, pentru un produs/durată alese o singură dată), și
editare liberă a duratei unei licențe deja generate (Zile/Luni/Ani/
Lifetime). Furnizorul arată versiunea curentă în UI, la fel ca orice
aplicație client — nu e scutit de Regula 7 doar pentru că e un instrument
intern.

**16. Design Web "Shift" — compact, fără spații goale (2026-08-26).**
Completare la Regula 12: paginile de prezentare NU doar adoptă paleta
amber/cupru — trebuie și dense/aerisite corect, nu găunoase. `min-height:
100svh` pe un hero cu conținut scurt lasă spațiu gol enorm pe orice ecran
mai mare — evită-l sau limitează-l (ex. `78svh`); padding-ul secțiunilor
(`section`) rămâne generos dar nu excesiv (60px, nu 90px+). Orice accent
vechi (verde/teal/albastru folosit ca accent PRIMAR, nu ca stare
semantică precum "verificat cu succes") se înlocuiește cu amber/cupru —
o variabilă CSS poate păstra alt NUME istoric (`--scope`, `--accent-copy`)
atât timp cât VALOAREA ei devine amber, ca să nu rescrii zeci de
apariții `var(--x)` din foaia de stil.

**4. Manager de Dependențe (Standard GDC, opt-in).** Aplicația de bază
rămâne lightweight — orice dependință externă opțională/grea (ex. FFmpeg
static) se descarcă LA CERERE, nu bundle-uită implicit dacă poate fi evitat.
Indicator global 🔴/🟢 vizibil în header/meniu: verde doar dacă TOATE
componentele obligatorii (non-opționale) sunt OK; componentele opționale
(ex. Homebrew pe Mac) nu blochează starea verde. Click pe indicator deschide
un panou dedicat ("Verificare & Dependențe Sistem") cu o listă modulară de
componente (model generic `DependencyItem` — id, nume, opțional/obligatoriu,
verificare headless, acțiune, niciodată câmpuri hardcodate per-dependință),
fiecare cu propriul status + buton de acțiune (descărcare automată a unui
binar static, sau copiere comandă de instalare). Verificarea rulează headless
la fiecare deschidere a panoului/meniului, actualizând starea instant.

**[NOTĂ pentru acest repo]**: ArgyllCMS (dependința externă critică a
DisplayCAL) are DEJA propriul flux de descărcare/verificare nativ, matur
(`dialog.argyll.notfound.choice` etc.) — nu se înlocuiește cu
`DependencyManager` generic GDC, ar duplica funcționalitate existentă și
testată de comunitatea upstream.

**5. Instalare Autonomă.** Mac: `.pkg` semnat Developer ID Application +
Installer, notarizat, stapled, cu `pkgbuild --install-location "/"` și
payload la `Applications/<App>.app` — instalare DIRECTĂ în `/Applications`
la dublu-click, fără drag-and-drop manual (verificabil cu
`pkgutil --payload-files`). Windows: installer Inno Setup cu
`DefaultDirName={autopf}\GDC\<App>` (Program Files) sau varianta x86,
scurtături automate Desktop + Start Menu, dezinstalare nativă prin
"Apps & Features" (fără script separat necesar dacă Inno Setup o acoperă).

**6. Packaging Mac — arhivă cu STRICT 3 fișiere.** Orice
`<App>-Mac.zip` livrat clientului conține la rădăcină EXACT: (1)
executabilul/`.pkg`-ul semnat+notarizat+stapled, (2)
`Dezinstalare_<App>.command` (dezinstalare completă: procese, TCC dacă
relevant, `~/Library/Application Support`, `Caches`, `Preferences`,
`Saved Application State`, `Logs`, orice item Keychain scris de aplicație),
(3) `Instructiuni_Utilizare.pdf` (RO/EN/ES). NICIODATĂ hack-uri
`xattr -dr com.apple.quarantine` sau launchere `Instalare_*.command` —
pachetul stapled e acceptat nativ de Gatekeeper. Curățarea unei instalări
vechi se face în `installer/scripts/preinstall` (`pkgbuild --scripts`,
pkill + `rm -rf`), niciodată legat de quarantine.

**7. UI Standard — varianta "Shift".** Temă dark, profesională, inspirată de
paginile de Color din DaVinci Resolve (fundal `#14161A`/`#1A1D22`, accent
cald cupru/amber sau altă culoare distinctă per-aplicație, text `#EDEFF2`).
Număr de versiune vizibil în UI (About/Meniu/Settings/Footer), fără excepție.
Update Checker automat la lansare + verificare manuală, conectat la
`update.json`/GitHub Releases API, cu notificare atât banner discrét CÂT ȘI
pop-up modal (o singură dată per versiune nouă, stare de dismissal comună
între cele două) — un simplu banner nu e suficient. `mandatory: true` în
`update.json` ignoră dismissal-ul anterior.

**[NOTĂ pentru acest repo]**: interfața DisplayCAL (wxPython) NU se
rescrie în stilul "Shift" — e un proiect upstream matur, cu propria temă
și convenții UI, folosit de o comunitate mare de utilizatori familiarizați
cu aspectul actual. Rebranding-ul se limitează la nume/logo/traducere, nu
la un redesign vizual complet.

**8. Documentație PDF — standard ultra-detaliat.** Orice
`Instructiuni_Utilizare.pdf` (RO/EN/ES) se redactează pentru un utilizator
complet începător, zero presupuneri, cu secțiunile relevante aplicației:
(a) Panoul de Dependențe — ce înseamnă 🔴/🟢, pas-cu-pas ce face userul la
roșu (unde dă clic, ce se deschide, ce buton apasă); (b) Homebrew (Mac,
dacă aplicabil) — pași la nivel de acțiune: copiază comanda din aplicație,
deschide Terminal (Spotlight, `⌘+Space`), lipește (`⌘+V`), Enter, apoi
explică parola de Mac cerută (invizibilă la tastare) + Enter din nou;
(c) Fluxul de utilizare + acțiuni post-proces — cum se adaugă
fișiere/date, ce face fiecare buton rezultat; (d) Licență & Donație — trial
gratuit explicit (zile), suma exactă ca donație (niciodată "preț"/"vânzare");
(e) Cum funcționează actualizarea automată — ce înseamnă pop-up-ul de
versiune nouă, ce face butonul „Actualizează acum" vs „Mai târziu", și că
instalarea noii versiuni rămâne un pas asistat (descărcare + reinstalare),
nu un update silențios în fundal.

**[NOTĂ pentru acest repo]**: (d) devine "Licență GPLv3 & Susținere
opțională" — fără nicio mențiune de trial/zile, aplicația e completă din
prima zi.

**9. Checklist obligatoriu la FIECARE release** (păstrat identic cu
"DIRECTIVĂ PERMANENTĂ SUPREMĂ" din jurnalul fiecărui proiect — punctele
1-4 de acolo sunt subsumate integral de punctele 5-8 de mai sus). Site-ul
public al fiecărei aplicații trebuie să pointeze mereu la
`releases/latest/download/...` (HTTP 200 verificat, nu presupus), niciodată
un tag fix.

**10. Comunicare & jurnal.** Fiecare `CLAUDE.md` rămâne un jurnal
append-only (regulile vechi nu se șterg, doar se marchează
**[ÎNVECHIT]** cu motivul dacă sunt explicit invalidate). Răspunsurile
Claude rămân ultra-concise: fără explicații de proces, direct codul/
diff-ul/comenzile și statusul. La orice modificare de cod, comanda exactă
de rebuild local se include la finalul răspunsului.

**11. Sincronizare dinamică a Standardului Master (CONTINUOUS UPDATE,
2026-08-26).** Orice adăugare/modificare/optimizare a unei reguli globale
din ACEASTĂ Partea 1 — indiferent din ce proiect pornește — devine automat
noul Standard Master și TREBUIE propagată manual, în ACELAȘI commit sau
imediat următorul, în `CLAUDE.md`-ul tuturor celorlalte proiecte din
`~/Developer/` (nu doar notată "pentru mai târziu"). Orice aplicație NOUĂ
creată în `~/Developer/` primește Partea 1 (versiunea curentă, completă)
încă din primul `CLAUDE.md` scris pentru ea — nu se pornește niciodată de
la un fișier gol sau parțial. Regula 1 de mai sus ("Dacă modifici o regulă
aici, propag-o manual...") descrie mecanismul; aceasta îl declară
obligatoriu, nu opțional.

**12. Profil Utilizator/HWID în Sidebar, Sistem de Revocare Licențe &
Standard Design Web Mobile/Desktop "Shift" (2026-08-26).**
- **Profil Utilizator opțional, vizibil în sidebar-ul UI** (Mac + Windows,
  pe toate aplicațiile cu licențiere GDC): Nume (sau „Anonim" dacă nu e
  completat), Email, și Machine ID (HWID) — afișate clar, nu ascunse
  într-un submeniu. Portat din modulul Tracker existent (Mac,
  `AnalyticsClient.registerDevice` → Supabase `devices`) — Windows trebuie
  aliniat la aceeași infrastructură, nu una separată.
- **Revocare/blacklist de licențe, prin Supabase** (ACEEAȘI bază de date
  deja folosită de Tracker — niciun backend nou de construit). O licență
  Ed25519 rămâne verificată local (offline-first, nicio schimbare la
  activarea inițială), dar clientul verifică periodic + la lansare (dacă
  există conexiune) un tabel de revocări după `machineID`/serial. **Fail
  OPEN, nu fail closed**: fără conexiune la internet, o licență deja
  activată local CONTINUĂ să funcționeze (nu bricuim un user legitim offline)
  — revocarea se aplică abia la următoarea verificare online reușită.
  Furnizor capătă unelte de revocare instant + editare a perioadei de
  valabilitate a unei licențe existente deja generate.
- **Generare flexibilă de licențe** (Furnizor): selector explicit al
  duratei — Zile / Luni / Ani / Forever (Lifetime) / Valabil până la
  versiunea X — nu doar trial fix + activare permanentă binară.
- **Standard Design Web "Shift"** — orice pagină de prezentare/descărcare
  GDC (`gordas.dev` și paginile dedicate per-aplicație) adoptă design-ul
  dark, minimalist, accent amber/cupru consacrat de CG Convertor
  (`gordas.dev/cg-convertor`) — niciun accent verde vechi sau stil
  nealiniat. Toate paginile trebuie optimizate explicit pentru mobil
  (iOS Safari + Android Chrome), verificat vizual la lățimi de telefon,
  nu doar "responsive by CSS framework".

**[NOTĂ pentru acest repo]**: primele două puncte (Profil/HWID, Revocare)
NU se aplică — nu există licențiere pe acest produs (vezi excepția de la
Regula 3). Pagina web (`gordas.dev/DisplayCAL-CG/`) urmează totuși
Standardul Design Web "Shift", ca restul suitei.

**13. Update Checker — specificație UX obligatorie (2026-08-26).** La
lansare, aplicația verifică `update.json`/GitHub Releases; dacă versiunea
locală e mai veche, arată un pop-up/modal Shift (nu doar bannerul discret
din Regula 7) cu: numărul noii versiuni, un rezumat scurt al noutăților
(Release Notes, dacă `update.json` le are — câmp opțional, degradează
elegant dacă lipsește), și DOUĂ butoane explicite — **„Actualizează acum"**
(deschide direct link-ul de descărcare a installer-ului/pachetului nou,
`releases/latest/download/...`, și arată userului că trebuie să
instaleze peste versiunea curentă + repornească aplicația — NU e un
self-update silențios, niciun helper nu înlocuiește bundle-ul/exe-ul în
fundal, vezi WARNING-ul deja existent din `UpdateChecker.swift`/`.cs`) și
**„Mai târziu"** (închide fereastra, aceeași stare de dismissal ca
bannerul). Popup-ul apare o singură dată per versiune nouă, cu excepția
`mandatory: true` (reapare la fiecare lansare). Ghidul PDF (Regula 8(e))
trebuie să explice acest flux exact.

**[NOTĂ pentru acest repo]**: DisplayCAL are deja `update_check.py`
propriu (upstream, matur) — vezi `DisplayCAL/meta.py`
(`GITHUB_API_URL`/`DEVELOPMENT_HOME_PAGE`, redirecționate spre
`gordasgdc/displaycal-py3`, 2026-09-05). Se extinde/verifică acel flux, nu
se înlocuiește cu un checker GDC nou.

**14. Versionare semantică obligatorie la FIECARE schimbare (2026-08-26).**
Orice modificare de cod livrată clientului — oricât de mică — incrementează
numărul de versiune, sincron în TOATE punctele care îl țin (Info.plist Mac,
`.csproj`/`installer.iss` Windows, `docs/update.json`, orice altă constantă
de versiune din acel repo). Format `MAJOR.MINOR.PATCH` (ex. `2.3.1`):
- **PATCH** (ultima cifră, `2.3.0`→`2.3.1`) — orice fix, ajustare, adăugare
  mică sau schimbare care nu rupe compatibilitatea. Cazul implicit, cel mai
  frecvent.
- **MINOR** (cifra din mijloc, `2.3.x`→`2.4.0`) — funcționalitate nouă
  vizibilă (ex. o fază/etapă întreagă ca Panoul de Dependențe sau Profilul
  HWID), fără schimbări radicale de arhitectură.
- **MAJOR** (prima cifră, `2.x.x`→`3.0.0`) — schimbare radicală: rebranding,
  redesign complet de UI, schimbare de arhitectură (ex. sistem nou de
  licențiere), sau orice prag pe care Cristi îl declară explicit "versiune
  majoră".

**[NOTĂ pentru acest repo]**: versiunea urmărește UPSTREAM-ul
(`DisplayCAL/VERSION`, ex. `3.10.0.dev82`), NU un contor GDC separat —
distincția noastră se marchează cu un sufix de build separat (ex.
`+cg.1`, `+cg.2` per resincronizare/rebuild), nu prin schimbarea
numărului de bază, ca update checker-ul upstream (bazat pe compararea
directă a numărului din `VERSION`) să rămână corect.

**17. Orice fișier descărcabil TREBUIE să poarte numărul versiunii în NUMELE
fișierului (2026-08-26).** Nu doar în interiorul aplicației (Regula 14) —
în numele fizic al pachetului: `DataMover-2.5.5.pkg`, nu `DataMover.pkg`;
`GDCPluginManagerSetup-1.2.8.exe`, nu `GDCPluginManagerSetup.exe`. Motiv
direct de la Cristi: probele/build-urile de test se acumulează local (în
`~/Downloads`, `/tmp`, trimise pentru testare) și devin de nerecunoscut
fără versiune în nume — "am o grămadă de descărcări și nu știu ce versiune
sunt, care, ce și cum sunt".
- **Excepție, NU o contrazicere**: mecanismul `releases/latest/download/
  <nume-stabil>` (site-ul, self-updater-ul) are nevoie STRUCTURAL de un
  nume care nu se schimbă niciodată între release-uri — vezi Regula
  Domeniului & Download. Copia asta stabilă tot trebuie publicată, DAR
  ALĂTURI de copia versionată, niciodată singură.
- **Orice fișier construit/descărcat/trimis lui Cristi în afara acestui
  mecanism** (build local de test, artefact de CI descărcat manual,
  fișier trimis prin `SendUserFile`, copie pusă în `/tmp` pentru
  verificare) TREBUIE redenumit explicit cu versiunea înainte de a fi
  oferit — niciodată livrat cu numele generic/stabil, care are sens doar
  ca țintă a unui link fix, nu ca fișier de sine stătător pe disc.

**18-31.** (Standard UX aplicații noi, Regulă Legală/Consent Gate,
Self-Updater, Memory & I/O, PlatformTarget, gardă `dist/` root-owned,
Mărime Text, CHANGELOG+DiagnosticLog, Terminal Live, Pricing dinamic,
audit licență, zero informație internă publică, cod complet/paritate
Mac-Win) — **valabile ca text, dar Regulile 12/18(licență)/20/27/28
(self-updater bazat pe licențiere, pricing, audit licență) NU se aplică
efectiv aici** din motivul explicat la excepția Regulii 3: acest produs nu
are licențiere/trial/preț de auditat. Consent Gate-ul de instalare (Regula
19) RĂMÂNE obligatoriu, dar conținutul lui e licența GPLv3 + creditele
originale, nu Termenii GDC. Vezi textul complet al acestor reguli în
`CLAUDE.md` al oricărui alt repo GDC (ex. `CGConvertor`) — nu duplicat aici
ca să nu divergă la sincronizări viitoare ale Părții 1.

**32. Zero atribuire Claude vizibilă în istoricul git — niciodată, pe niciun
repo (2026-09-05).** Cerut explicit de Cristi. Regulă obligatorie,
permanentă, pentru toate repo-urile GDC — inclusiv acest fork. **Notă
specifică acestui repo**: istoricul UPSTREAM (mii de commit-uri de la
zeci de contribuitori externi, sincronizat prin fast-forward de la
`eoyilmaz/displaycal-py3`) NU se rescrie niciodată — Regula 32 privește
DOAR ce adaugă Claude de-acum înainte în acest fork (niciun commit nou al
lui Claude nu conține `Co-Authored-By: Claude`), nu istoria unui proiect
open-source terț cu mulți autori legitimi.

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
- [x] **Rebranding `DisplayCAL/meta.py`** — `NAME="DisplayCAL-CG"`,
  `AUTHOR`/`AUTHOR_ASCII`/`DESCRIPTION`/`LONG_DESCRIPTION` extinse (credit
  original PĂSTRAT, nu înlocuit — cerință GPLv3), `DOMAIN="gordas.dev"`
  (afectează DOAR metadate de packaging — URL-uri installer, APPSTREAM_ID
  — verificat cu `grep` ce anume citește `meta.DOMAIN` înainte de
  schimbare), `GITHUB_API_URL`/`DEVELOPMENT_HOME_PAGE` redirecționate spre
  `gordasgdc/displaycal-py3` (altfel update checker-ul propriu al
  aplicației ar fi trimis userii spre release-urile upstream, nu ale
  noastre — bug real prins înainte de a fi introdus, nu doar presupus).
  `AUTHOR_EMAIL` **NU** derivat din noul `DOMAIN` — rămâne hardcodat la
  adresele reale ale autorilor originali (`florian@displaycal.net`,
  `eoyilmaz@gmail.com`), ca rebranding-ul să nu creeze o adresă de email
  falsă pe domeniul nostru. Verificat cu import Python real — toate
  valorile calculate corect (`APPSTREAM_ID` → `dev.gordas.DisplayCAL-CG`).
- [ ] **`DisplayCAL/lang/ro.yaml`** — traducere completă RO (1280 chei).
  NEÎNCEPUT.
- [ ] **9 iconițe noi** (`.icns`/`.ico`/`.png`, toate uneltele). NEÎNCEPUT.
- [ ] **`build_pkg.sh`** (macOS, semnare+notarizare Developer ID, pe modelul
  `build_installer.sh` din CGConvertor). NEÎNCEPUT.
- [ ] **Branding Inno Setup Windows** (fără semnare încă). NEÎNCEPUT.
- [ ] **`docs/` GitHub Pages** pe acest repo + oglindă
  `gdc-plugin-manager-catalog-vendor/docs/DisplayCAL-CG/`. NEÎNCEPUT.
- [ ] **`catalog.json`** → intrare nouă în `apps[]`. NEÎNCEPUT.
- [ ] **Fork `release_builds.yml`** + pas de semnare Mac local. NEÎNCEPUT.

**Limitare reală, cunoscută dinainte**: nicio testare funcțională a
calibrării propriu-zise (are nevoie de un colorimetru/spectrofotometru
fizic conectat) — verificarea se oprește la "se instalează, pornește,
interfața arată/traduce corect".
