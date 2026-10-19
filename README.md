![license](https://img.shields.io/badge/License-GPL%20v3-blue.svg)
![pyversion](https://img.shields.io/pypi/pyversions/DisplayCAL.svg)
![pypiversion](https://img.shields.io/pypi/v/DisplayCAL.svg)
![wheel](https://img.shields.io/pypi/wheel/DisplayCAL.svg)

[🇷🇴 Română](README.md) &middot; [🇬🇧 English](README.en.md) &middot; [🇪🇸 Español](README.es.md)

DisplayCAL-CG — Distribuție GDC
================================

Acesta este **DisplayCAL-CG**, o distribuție întreținută de GDC a acestui
proiect, peste același cod și aceeași licență GPLv3 ca proiectul original de
mai jos. Fără licențiere, fără probă, fără nicio formă de monetizare.

Ce aduce această ediție:

- **Calibrare ghidată** în cinci pași, cu interfață Qt: monitor și instrument,
  obiectiv, pregătire fizică (listă cu surse, animație de poziționare pentru
  instrumentele documentate de producător), plan de măsurare, instalare și
  verificare a profilului.
- **Identificare onestă a instrumentului**: dacă mai multe modele au aceeași
  identitate USB, modelul exact îl confirmi tu.
- **Sesiuni lungi mai sigure**: măsurare pe blocuri salvate pe măsură ce se
  termină, jurnal de sesiune, reluare cu blocurile rămase (doar în aceleași
  condiții), împiedicarea repausului doar pe durata rulării.
- **ArgyllCMS inclus** în instalator și verificat cu o sumă SHA-256 fixă.
- Interfață și ghiduri în română, engleză și spaniolă; instalatoare native
  pentru macOS (`.pkg`, semnat și notarizat) și Windows.

- **Descărcare & pagină web:** [gordas.dev/DisplayCAL-CG](https://gordas.dev/DisplayCAL-CG/)
- **Versiuni (macOS `.pkg`):** [github.com/gordasgdc/displaycal-py3/releases](https://github.com/gordasgdc/displaycal-py3/releases)
- **Întreținut de:** Cristi Gordaș (GDC) — doar rebranding, traducere română
  și pachet nativ de instalare. Tot creditul pentru DisplayCAL însuși
  aparține autorilor originali de mai jos.

Tot ce urmează mai jos e `README.md`-ul original al proiectului upstream,
tradus în română — codul și funcționalitatea rămân identice.

---

Proiectul DisplayCAL pentru Python 3
=====================================

Acest proiect și-a propus să modernizeze codul DisplayCAL, inclusiv suport
pentru Python 3.

Florian Höch, dezvoltatorul original, a făcut o treabă incredibilă creând și
întreținând DisplayCAL în toți acești ani. Dar, se pare că, în timpul
pandemiei, complet de înțeles, și-a pierdut pasiunea pentru proiect. Acum e
timpul ca noi, comunitatea DisplayCAL, să contribuim înapoi la această
unealtă extraordinară.

Acest proiect se bazează pe ``HEAD``-ul versiunii de pe Sourceforge, care
avea 5 commit-uri suplimentare create de Florian peste versiunea ``3.8.9.3``,
lansată pe 14 ianuarie 2020.

Datorită eforturilor comunității, DisplayCAL funcționează acum cu Python
3.9+:

![image](screenshots/DisplayCAL-screenshot-GNOME-3.9.5-running_on_python3.10.png)

Instrucțiuni de instalare
==========================

Urmează instrucțiunile în funcție de sistemul tău de operare:

- [Windows](docs/install_instructions_windows.md)
- [MacOS](docs/install_instructions_macos.md)
- [Linux](docs/install_instructions_linux.md)

Distracție plăcută!
