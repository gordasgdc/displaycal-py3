#!/usr/bin/env python3
"""Write README.md / README.en.md / README.es.md (short product entry, verified claims only).

The original upstream README text lives in docs/upstream/. Run from anywhere:
    python3 docs/_site_src/build_readme.py
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = "https://gordas.dev/DisplayCAL-CG/"

T = {}
T["ro"] = dict(
    file="README.md", guide_url=SITE + "ghid/", pdf="docs/DisplayCAL-CG_Ghid_RO.pdf", site=SITE, up="docs/upstream/README.upstream.md",
    tag="Calibrare și profilare de monitor, ghidată. Peste ArgyllCMS, gratuit și open source.",
    intro="DisplayCAL-CG te conduce de la sondă la un profil ICC verificat, în cinci pași: ce pregătești, cum așezi instrumentul, cât durează, ce se întâmplă dacă ceva se oprește. Este o ediție întreținută de Cristi Gordaș a proiectului [DisplayCAL](https://displaycal.net) (continuarea comunității: [displaycal-py3](https://github.com/eoyilmaz/displaycal-py3)), peste același cod și aceeași licență GPLv3. **100% gratuit: fără trial, fără activare, fără funcții plătite.**",
    shots=("Pasul «Măsurare»: planul cu totalul de patch-uri, mărimea blocului, numărul de blocuri și timpul estimat.", "Modul avansat, fila Profilare, aceeași configurație."),
    what="## Ce face\n\nMăsoară cum își afișează ecranul culorile și scrie un profil ICC pe care sistemul și programele îl folosesc pentru culori corecte. Este pentru fotografi, coloriști, designeri și oricine are nevoie ca monitorul să arate la fel de la o zi la alta și de la un program la altul.\n\n**Ce îți trebuie:** un colorimetru sau un spectrofotometru compatibil cu ArgyllCMS (de exemplu din familiile i1Display, ColorMunki sau Spyder). Fără instrument fizic nu se poate măsura nimic; aplicația nu simulează măsurători.",
    adds_h="## Ce aduce ediția CG față de proiectul original",
    adds=[
        "**Calibrare ghidată** în cinci pași (monitor și instrument, obiectiv, pregătire, măsurare, instalare și verificare), cu interfață Qt. Modul avansat rămâne, regrupat pe decizii, cu aceeași configurație.",
        "**Pregătire cu surse și poziționarea sondei**, cu animație schematică pentru instrumentele documentate de producător; modelul exact îl confirmi tu când mai multe produse au aceeași identitate USB.",
        "**Planul de măsurare înainte de pornire**: total de patch-uri, mărimea blocului, numărul de blocuri și timp estimat, afișate separat; alegerea sau crearea diagramei lângă total.",
        "**Măsurare în blocuri cu recuperare**: blocurile terminate se salvează local, există un jurnal de sesiune și o reluare cu blocurile rămase (doar în aceleași condiții), iar repausul este împiedicat doar pe durata rulării. Sesiunile de mai multe ore nu au fost încă validate; nimic din aceasta nu garantează stabilitatea.",
        "**Diagnostic local**: jurnale rotative și export de pachet cu redactare implicită, fără trimitere automată.",
        "**Text redimensionabil** («Aa»), contrast verificat, interfață în română, engleză și spaniolă; **ArgyllCMS inclus** și verificat cu o sumă SHA-256 fixă; instalatoare native.",
    ],
    dl_h="## Descărcare",
    dl="Descărcările și pagina de prezentare sunt la **[gordas.dev/DisplayCAL-CG](https://gordas.dev/DisplayCAL-CG/)**; versiunile publicate sunt la [Releases](https://github.com/gordasgdc/displaycal-py3/releases).\n\n| Platformă | Fișier | Note |\n|---|---|---|\n| macOS (Apple Silicon) | `DisplayCAL-CG.dmg` / `.pkg` | semnat Developer ID și notarizat |\n| Windows (x64) | `DisplayCAL-CG-Setup.exe` | încă nesemnat cu un certificat plătit: SmartScreen poate avertiza |",
    req_h="## Cerințe și limite",
    req=[
        "Un instrument de măsură compatibil ArgyllCMS.",
        "Verificat: instalatoarele macOS, instalarea curată pe Windows 11 (VM ARM64 cu emulare x64), o măsurare reală scurtă (38 de patch-uri) cu un colorimetru i1Display pe macOS.",
        "**Neverificat**: sesiuni de mai multe ore, deconectarea sondei în timpul măsurării și revenirea după o pană de curent, Windows pe hardware x64 nativ, macOS pe Intel, alte instrumente decât cel testat, revizuirea traducerilor de către vorbitori nativi.",
    ],
    guide_h="## Ghid, suport, probleme",
    gitems=[
        "[Ghid tehnic detaliat]({g}) (RO) · [PDF]({pdf})",
        "Instrucțiuni de instalare: [macOS](docs/install_instructions_macos.md) · [Windows](docs/install_instructions_windows.md) · [Linux](docs/install_instructions_linux.md)",
        "Diagnostic: **? → Diagnostic și suport** în aplicație creează local un pachet pe care îl atașezi tu la o problemă; nu se trimite nimic automat.",
        "[Raportează o problemă](https://github.com/gordasgdc/displaycal-py3/issues/new)",
    ],
    lic_h="## Licență și credite",
    lic="GPLv3 (vezi [LICENSE.txt](LICENSE.txt)). Aplicația poate afișa mesajul opțional de susținere al proiectului original; îl poți închide.\n\n- **DisplayCAL** — Florian Höch, autorul original.\n- **displaycal-py3** — continuarea comunității (portarea pe Python 3).\n- **ArgyllCMS** — Graeme Gill, motorul de măsurare și de calcul al profilelor.\n- **DisplayCAL-CG** — adaptări, interfață ghidată și pachete de instalare: Cristi Gordaș.\n\nCe a fost preluat selectiv din proiectul original: [UPSTREAM_INTEGRATED.md](docs/UPSTREAM_INTEGRATED.md).",
    up_h="## Documentația proiectului original",
    up_t="README-ul original (tradus) și instrucțiunile lui rămân accesibile: [README.upstream.md](docs/upstream/README.upstream.md) · [documentație](https://displaycal.net).",
    star="Dacă ți-a fost de folos, o stea ajută proiectul să fie găsit.", starbtn="Oferă o stea",
)
T["en"] = dict(
    file="README.en.md", guide_url=SITE + "en/guide/", pdf="docs/DisplayCAL-CG_Guide_EN.pdf", site=SITE + "en/", up="docs/upstream/README.upstream.en.md",
    tag="Guided monitor calibration and profiling. On ArgyllCMS, free and open source.",
    intro="DisplayCAL-CG takes you from the probe to a verified ICC profile in five steps: what to prepare, how to place the instrument, how long it takes, and what happens if something stops. It is an edition of [DisplayCAL](https://displaycal.net) maintained by Cristi Gordaș (the community continuation is [displaycal-py3](https://github.com/eoyilmaz/displaycal-py3)), on the same code and the same GPLv3 licence. **100% free: no trial, no activation, no paid features.**",
    shots=("The “Measurement” step: the plan with total patches, block size, number of blocks and estimated time.", "Advanced mode, Profiling tab, same configuration."),
    what="## What it does\n\nIt measures how your screen shows colour and writes an ICC profile that the system and your programs use for correct colour. It is for photographers, colourists, designers and anyone who needs a monitor to look the same from one day to the next and from one program to another.\n\n**What you need:** a colorimeter or spectrophotometer supported by ArgyllCMS (for example from the i1Display, ColorMunki or Spyder families). Without a physical instrument nothing can be measured; the application does not simulate measurements.",
    adds_h="## What the CG edition adds to the original project",
    adds=[
        "**Guided calibration** in five steps (monitor and instrument, goal, preparation, measurement, install and verify), with a Qt interface. Advanced mode stays, regrouped by decision, on the same configuration.",
        "**Sourced preparation and probe placement**, with a schematic animation for instruments the maker documents; you confirm the exact model when several products share one USB identity.",
        "**The measurement plan before you start**: total patches, block size, number of blocks and estimated time, shown separately; choosing or creating the chart beside the total.",
        "**Measurement in blocks with recovery**: finished blocks are saved locally, there is a session journal and a way to continue with the remaining blocks (only under the same conditions), and sleep is prevented only while a run is active. Sessions of several hours have not been validated yet; none of this guarantees stability.",
        "**Local diagnostics**: rotating logs and a package export with redaction by default, never sent automatically.",
        "**Adjustable text** (“Aa”), checked contrast, Romanian/English/Spanish interface; **ArgyllCMS included** and verified against a fixed SHA-256 hash; native installers.",
    ],
    dl_h="## Download",
    dl="Downloads and the overview page are at **[gordas.dev/DisplayCAL-CG](https://gordas.dev/DisplayCAL-CG/en/)**; published versions are under [Releases](https://github.com/gordasgdc/displaycal-py3/releases).\n\n| Platform | File | Notes |\n|---|---|---|\n| macOS (Apple Silicon) | `DisplayCAL-CG.dmg` / `.pkg` | Developer ID signed and notarized |\n| Windows (x64) | `DisplayCAL-CG-Setup.exe` | not yet signed with a paid certificate: SmartScreen may warn |",
    req_h="## Requirements and limits",
    req=[
        "An ArgyllCMS-supported measuring instrument.",
        "Verified: the macOS installers, a clean install on Windows 11 (ARM64 VM with x64 emulation), a short real measurement (38 patches) with an i1Display colorimeter on macOS.",
        "**Not verified**: multi-hour sessions, unplugging the probe during a measurement and recovery after a power cut, Windows on native x64 hardware, macOS on Intel, instruments other than the one tested, review of the translations by native speakers.",
    ],
    guide_h="## Guide, support, issues",
    gitems=[
        "[Detailed technical guide]({g}) (EN) · [PDF]({pdf})",
        "Install instructions: [macOS](docs/install_instructions_macos.md) · [Windows](docs/install_instructions_windows.md) · [Linux](docs/install_instructions_linux.md)",
        "Diagnostics: **? → Diagnostics and support** in the application builds a package locally that you attach to an issue yourself; nothing is sent automatically.",
        "[Report a problem](https://github.com/gordasgdc/displaycal-py3/issues/new)",
    ],
    lic_h="## Licence and credits",
    lic="GPLv3 (see [LICENSE.txt](LICENSE.txt)). The application may show the original project's optional support message; you can close it.\n\n- **DisplayCAL** — Florian Höch, the original author.\n- **displaycal-py3** — the community continuation (the Python 3 port).\n- **ArgyllCMS** — Graeme Gill, the measurement and profile engine.\n- **DisplayCAL-CG** — adaptations, guided interface and installers: Cristi Gordaș.\n\nWhat was selectively taken from the original project: [UPSTREAM_INTEGRATED.md](docs/UPSTREAM_INTEGRATED.md).",
    up_h="## Original project documentation",
    up_t="The original README and its instructions stay available: [README.upstream.en.md](docs/upstream/README.upstream.en.md) · [documentation](https://displaycal.net).",
    star="If it helped you, a star helps the project get found.", starbtn="Give a star",
)
T["es"] = dict(
    file="README.es.md", guide_url=SITE + "es/guia/", pdf="docs/DisplayCAL-CG_Guia_ES.pdf", site=SITE + "es/", up="docs/upstream/README.upstream.es.md",
    tag="Calibración y perfilado de monitor, guiados. Sobre ArgyllCMS, gratis y de código abierto.",
    intro="DisplayCAL-CG te lleva de la sonda a un perfil ICC verificado en cinco pasos: qué preparar, cómo colocar el instrumento, cuánto tarda y qué pasa si algo se detiene. Es una edición de [DisplayCAL](https://displaycal.net) mantenida por Cristi Gordaș (la continuación de la comunidad es [displaycal-py3](https://github.com/eoyilmaz/displaycal-py3)), sobre el mismo código y la misma licencia GPLv3. **100% gratis: sin prueba, sin activación, sin funciones de pago.**",
    shots=("El paso «Medición»: el plan con total de parches, tamaño del bloque, número de bloques y tiempo estimado.", "Modo avanzado, pestaña Perfilado, la misma configuración."),
    what="## Qué hace\n\nMide cómo muestra el color tu pantalla y escribe un perfil ICC que el sistema y tus programas usan para un color correcto. Es para fotógrafos, coloristas, diseñadores y cualquiera que necesite que el monitor se vea igual de un día a otro y de un programa a otro.\n\n**Qué necesitas:** un colorímetro o espectrofotómetro compatible con ArgyllCMS (por ejemplo de las familias i1Display, ColorMunki o Spyder). Sin un instrumento físico no se puede medir nada; la aplicación no simula mediciones.",
    adds_h="## Qué aporta la edición CG al proyecto original",
    adds=[
        "**Calibración guiada** en cinco pasos (monitor e instrumento, objetivo, preparación, medición, instalar y verificar), con interfaz Qt. El modo avanzado se mantiene, reagrupado por decisión, con la misma configuración.",
        "**Preparación con fuentes y colocación de la sonda**, con una animación esquemática para los instrumentos que el fabricante documenta; el modelo exacto lo confirmas tú cuando varios productos comparten la misma identidad USB.",
        "**El plan de medición antes de empezar**: total de parches, tamaño del bloque, número de bloques y tiempo estimado, mostrados por separado; elegir o crear la carta junto al total.",
        "**Medición en bloques con recuperación**: los bloques terminados se guardan localmente, hay un diario de sesión y se puede continuar con los bloques restantes (solo en las mismas condiciones); el reposo se evita solo durante la ejecución. Las sesiones de varias horas todavía no se han validado; nada de esto garantiza estabilidad.",
        "**Diagnóstico local**: registros rotativos y exportación de un paquete con redacción por defecto, sin envío automático.",
        "**Texto ajustable** («Aa»), contraste comprobado, interfaz en rumano, inglés y español; **ArgyllCMS incluido** y verificado con una suma SHA-256 fija; instaladores nativos.",
    ],
    dl_h="## Descarga",
    dl="Las descargas y la página de presentación están en **[gordas.dev/DisplayCAL-CG](https://gordas.dev/DisplayCAL-CG/es/)**; las versiones publicadas, en [Releases](https://github.com/gordasgdc/displaycal-py3/releases).\n\n| Plataforma | Archivo | Notas |\n|---|---|---|\n| macOS (Apple Silicon) | `DisplayCAL-CG.dmg` / `.pkg` | firmado con Developer ID y notarizado |\n| Windows (x64) | `DisplayCAL-CG-Setup.exe` | aún sin firmar con un certificado de pago: SmartScreen puede avisar |",
    req_h="## Requisitos y límites",
    req=[
        "Un instrumento de medición compatible con ArgyllCMS.",
        "Verificado: los instaladores de macOS, una instalación limpia en Windows 11 (VM ARM64 con emulación x64), una medición real corta (38 parches) con un colorímetro i1Display en macOS.",
        "**No verificado**: sesiones de varias horas, desconexión de la sonda durante la medición y recuperación tras un corte de corriente, Windows en hardware x64 nativo, macOS en Intel, instrumentos distintos del probado, revisión de las traducciones por hablantes nativos.",
    ],
    guide_h="## Guía, soporte, incidencias",
    gitems=[
        "[Guía técnica detallada]({g}) (ES) · [PDF]({pdf})",
        "Instrucciones de instalación: [macOS](docs/install_instructions_macos.md) · [Windows](docs/install_instructions_windows.md) · [Linux](docs/install_instructions_linux.md)",
        "Diagnóstico: **? → Diagnóstico y soporte** en la aplicación crea un paquete en local que adjuntas tú a una incidencia; no se envía nada automáticamente.",
        "[Informar de un problema](https://github.com/gordasgdc/displaycal-py3/issues/new)",
    ],
    lic_h="## Licencia y créditos",
    lic="GPLv3 (ver [LICENSE.txt](LICENSE.txt)). La aplicación puede mostrar el mensaje opcional de apoyo del proyecto original; puedes cerrarlo.\n\n- **DisplayCAL** — Florian Höch, el autor original.\n- **displaycal-py3** — la continuación de la comunidad (el port a Python 3).\n- **ArgyllCMS** — Graeme Gill, el motor de medición y de perfiles.\n- **DisplayCAL-CG** — adaptaciones, interfaz guiada e instaladores: Cristi Gordaș.\n\nQué se tomó de forma selectiva del proyecto original: [UPSTREAM_INTEGRATED.md](docs/UPSTREAM_INTEGRATED.md).",
    up_h="## Documentación del proyecto original",
    up_t="El README original y sus instrucciones siguen accesibles: [README.upstream.es.md](docs/upstream/README.upstream.es.md) · [documentación](https://displaycal.net).",
    star="Si te ha sido útil, una estrella ayuda a que el proyecto se encuentre.", starbtn="Dar una estrella",
)


def render(lang: str, t: dict) -> str:
    items = "\n".join("- " + x.format(g=t["guide_url"], pdf=t["pdf"]) for x in t["gitems"])
    adds = "\n".join("- " + x for x in t["adds"])
    req = "\n".join("- " + x for x in t["req"])
    return f"""[🇷🇴 Română](README.md) · [🇬🇧 English](README.en.md) · [🇪🇸 Español](README.es.md)

<p align="center"><img src="docs/assets/site/icon-b-180.png" width="96" alt="DisplayCAL-CG"></p>

<h1 align="center">DisplayCAL-CG</h1>

<p align="center"><b>{t['tag']}</b></p>

<p align="center"><a href="LICENSE.txt"><img alt="GPLv3" src="https://img.shields.io/badge/license-GPLv3-blue.svg"></a> <a href="https://github.com/gordasgdc/displaycal-py3/releases"><img alt="release" src="https://img.shields.io/github/v/release/gordasgdc/displaycal-py3?include_prereleases&label=release"></a></p>

{t['intro']}

<p align="center"><img src="docs/assets/readme/plan-{lang}.jpg" alt="{t['shots'][0]}" width="760"><br><sub>{t['shots'][0]}</sub></p>

{t['what']}

{t['adds_h']}

{adds}

<p align="center"><img src="docs/assets/readme/adv-{lang}.jpg" alt="{t['shots'][1]}" width="760"><br><sub>{t['shots'][1]}</sub></p>

{t['dl_h']}

{t['dl']}

{t['req_h']}

{req}

{t['guide_h']}

{items}

{t['lic_h']}

{t['lic']}

{t['up_h']}

{t['up_t']}

<p align="center"><a href="https://github.com/gordasgdc/displaycal-py3"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/assets/site/github-invertocat-white.svg"><img src="docs/assets/site/github-invertocat-black.svg" height="18" alt="GitHub"></picture></a> {t['star']} <a href="https://github.com/gordasgdc/displaycal-py3">{t['starbtn']}</a></p>
"""


def main() -> int:
    for lang, t in T.items():
        path = os.path.join(ROOT, t["file"])
        with open(path, "w", encoding="utf-8") as f:
            f.write(render(lang, t))
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
