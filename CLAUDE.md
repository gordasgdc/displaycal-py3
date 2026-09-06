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

**33. Iconițe SVG monocrome, tip contur — niciodată emoji, pe nicio pagină
web GDC (2026-09-05).** Cerut explicit de Cristi, după ce a comparat
`gordas.dev/DisplayCAL-CG/` (emoji colorate ca iconițe de feature) cu
`gordas.dev/mac-master-control-pro/` (sprite SVG monocrom, `currentColor`,
stil contur) — a doua variantă e standardul, prima nu mai e acceptabilă.
Regulă obligatorie pentru orice pagină de prezentare/descărcare GDC nouă
sau atinsă de-acum înainte:
- Un singur `<svg style="display:none">` cu `<symbol>`-uri, inserat o
  singură dată în `<body>`, referit prin `<svg><use href="#icon-x"/></svg>`
  oriunde e nevoie (brand mark din header, badge mare din hero, iconițe de
  feature, iconițe din butoane) — niciodată emoji Unicode (⬇ 🎯 🖥️ 📊 etc.)
  ca iconiță funcțională sau decorativă principală.
- Stil vizual: `fill="none" stroke="currentColor" stroke-width="1.6-1.8"
  stroke-linecap="round"` (contur simplu, 24×24 viewBox) — culoarea vine
  din CSS (`color:var(--accent)` pe containerul părinte), nu hardcodată în
  SVG. Vezi sprite-ul complet de referință din `mac-master-control-pro/`
  (`gear`, `zap`, `piechart`, `globe`, `cloud`, `trash`, `wrench`, `shield`,
  `cpu`, `box`, `harddrive`, `download`, etc.) — reutilizează un icon
  existent din acel sprite dacă se potrivește semantic, înainte de a
  desena unul nou.
- **Atenție la `data-i18n`/`textContent` pe elemente care conțin și un
  `<svg>`** (ex. un buton cu iconiță + text) — `el.textContent = ...` la
  schimbarea de limbă ȘTERGE orice copil SVG din acel element. Textul
  tradus trebuie să stea într-un `<span data-i18n="...">` COPIL, separat
  de `<svg>`, niciodată direct pe elementul care conține iconița.
- **Nu retroactiv, la fiecare pagină deodată** — orice aplicație/pagină
  care încă folosește emoji ca iconițe de feature se aliniază la acest
  model DOAR la următoarea ei atingere/actualizare reală, nu într-o
  sesiune dedicată exclusiv migrării tuturor paginilor existente.
- **Bonus, găsit în aceeași sesiune**: bulina de status colorată
  (`.dot`/`.signed-note .dot`, un `<span>` cu `background` CSS) NU intră
  sub această regulă — e un indicator de stare semantic (verde =
  verificat), nu o iconiță de conținut, poate rămâne CSS pur.

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
