# Build installer Windows — DisplayCAL-CG

Acest fișier există fiindcă pipeline-ul de build Windows (`py2exe` + Inno
Setup) rulează **exclusiv pe Windows real** — verificat direct în
`_native_build/cli.py`: `bdist_cmd = "py2exe"` doar dacă
`sys.platform == "win32"`, iar generarea scriptului `.iss`
(`inno_mod.generate(...)`) e gardată separat cu același test. `py2exe` nici
nu se poate instala pe macOS/Linux. Nu există echivalent Mac al
`build_pkg.sh` pentru Windows — pașii de mai jos trebuie rulați manual, pe
o mașină Windows reală (Parallels sau PC-ul unui prieten, ca la restul
ecosistemului GDC).

Branding-ul (nume, autor, domeniu, iconițe `.ico`, imaginile wizard-ului
`install.bmp`/`icon-install.bmp`) e deja pregătit în acest repo — pașii de
mai jos doar compilează, nu mai trebuie editat nimic în `meta.py`.

## Cerințe

1. Windows 10/11 (x64 sau ARM64).
2. [Python 3.10-3.14](https://www.python.org/downloads/windows/) — bifează
   "Add Python to PATH" la instalare.
3. [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
   — doar componenta "Desktop development with C++".
4. [Inno Setup](https://jrsoftware.org/isdl.php#stable) (5 sau 6).
5. [Git for Windows](https://www.git-scm.com/download/win).

## Pași

```shell
cd %USERPROFILE%
git clone https://github.com/gordasgdc/displaycal-py3.git
cd displaycal-py3
git checkout develop

py -3.11 -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
```

Verifică rapid că branding-ul GDC e activ (trebuie să arate `gordas.dev`,
NU `displaycal.net`):

```shell
python -c "from DisplayCAL import meta; print(meta.NAME, meta.DOMAIN, meta.DEVELOPMENT_HOME_PAGE)"
```

Trebuie să afișeze: `DisplayCAL gordas.dev https://github.com/gordasgdc/displaycal-py3`

Apoi construiește:

```shell
python DisplayCAL\freeze.py
python native_build.py inno
cd dist
iscc DisplayCAL-Setup-py2exe.win-amd64-py3.11.iss
```

(numele exact al fișierului `.iss` depinde de arhitectură/versiunea de
Python — apare afișat în consolă la pasul `native_build.py inno`, sub
`inno_path:`).

Rezultatul e `dist\DisplayCAL-<versiune>-Setup.exe` — instalerul complet,
cu branding GDC (nume, iconițe, culori wizard), toate cele 9 unelte.

## Ce lipsește, deliberat, deocamdată

- **Semnare cod (Authenticode)** — nu există încă certificat de semnare
  Windows (decizie confirmată de Cristi la începutul proiectului) —
  installerul rămâne nesemnat, Windows SmartScreen va arăta un
  avertisment "Windows protected your PC" la prima rulare (userul
  trebuie să apese "More info" → "Run anyway"). De adăugat quando există
  un certificat.
- **Publicare pe GitHub Releases** — după ce `.exe`-ul e construit și
  testat local, se urcă drept asset pe același release `v3.10.0.dev82-cg.1`
  (sau următorul), cu DOUĂ nume (Regula 17): unul versionat
  (`DisplayCAL-CG-<versiune>-Setup.exe`) și unul stabil
  (`DisplayCAL-CG-Setup.exe`, folosit de linkul `releases/latest/download/`
  de pe `docs/index.html`/pagina web — buton deja pregătit, doar dezactivat
  ("în curând") până apare acest fișier).
- **Testare reală a instalerului** — pasul de instalare efectivă (wizard,
  scurtături, dezinstalare) nu poate fi verificat automat de Claude, cere
  o mașină Windows reală.
