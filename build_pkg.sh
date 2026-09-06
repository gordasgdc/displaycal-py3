#!/usr/bin/env bash
# build_pkg.sh — DisplayCAL-CG, packaging macOS (.pkg semnat + notarizat,
# instalare automată în /Applications, standard GDC — vezi CLAUDE.md).
#
# Reutilizează EXACT secvența de semnare din .github/workflows/release_builds.yml
# (upstream, dovedită real — vezi comentariile lungi de-acolo despre
# framework-urile Qt/PySide6 fără symlink-uri standard, care crapă cu
# SIGKILL dacă sunt semnate "normal"), doar cu identitatea noastră reală
# de Developer ID în loc de ad-hoc (`-s -`), plus `--timestamp` (necesar
# pentru notarizare, ad-hoc nu are nevoie).
#
# Necesită: APPLE_SIGN_IDENTITY_APP + APPLE_SIGN_IDENTITY_INSTALLER (sau
# rămâne nesemnat, cu avertisment explicit — la fel ca restul ecosistemului
# GDC). Notarizare: profil keychain "gdc-notary" (`xcrun notarytool
# store-credentials gdc-notary`) sau variabilele APPLE_NOTARY_*.
set -euo pipefail
cd "$(dirname "$0")"

VERSION=$(cat DisplayCAL/VERSION)
PKG_ID="dev.gordas.DisplayCAL-CG.installer"
DIST_DIR="dist"
VENV="${DCAL_BUILD_VENV:-.build-venv}"
ARCH=$(uname -m)  # arm64 sau x86_64

echo "==> DisplayCAL-CG v$VERSION ($ARCH)"

if [ ! -d "$VENV" ]; then
    echo "==> Creez venv de build ($VENV)…"
    python3.13 -m venv "$VENV" 2>/dev/null || python3 -m venv "$VENV"
    "$VENV/bin/pip" install --upgrade pip -q
    "$VENV/bin/pip" install -q -r requirements.txt
    "$VENV/bin/pip" install -q py2app
fi

echo "==> Curăț build-uri py2app anterioare (păstrez dist/copyright + appdata.xml, regenerate de setup())…"
# [2026-09-06] Garda impotriva unui `dist/` cu fisiere ramase root:wheel
# (ex. dintr-un test anterior cu `sudo installer -pkg ... -target /` care
# a atins accidental folderul local) - fara ea, `rm -rf` de mai jos esueaza
# PARTIAL sub `set -e`, oprind scriptul la mijloc cu un dist/ pe jumatate
# curatat, in loc de un mesaj clar. Acelasi tipar ca Regula 23 (DataMover).
if find "$DIST_DIR" -maxdepth 3 -user root -print -quit 2>/dev/null | grep -q .; then
    echo "EROARE: '$DIST_DIR/' conține fișiere deținute de root. Rulează manual:" >&2
    echo "    sudo rm -rf $(pwd)/$DIST_DIR" >&2
    exit 1
fi
rm -rf "$DIST_DIR"/py2app.macosx* "$DIST_DIR"/*.pkg "$DIST_DIR"/payload "$DIST_DIR"/Distribution.xml "$DIST_DIR"/LICENSE.txt

echo "==> pip install -e . (verifică integritatea pachetului Python, regenerează dist/copyright)…"
"$VENV/bin/pip" install -e . -q

mkdir -p "$DIST_DIR"
if [ ! -f "$DIST_DIR/copyright" ]; then
    # `dist/` e complet .gitignore-uit, dar `_setup.py` (linia ~536) cere
    # necondiționat `dist/copyright` să existe pentru build-ul py2app pe
    # macOS (`doc = "."` pe darwin) — regenerăm-o aici, nu doar o dată
    # manual, ca orice build viitor (inclusiv pe alt calculator/CI) să
    # funcționeze fără un pas ascuns.
    echo "==> Generez dist/copyright (cerut de _setup.py, nu versionat)…"
    cat > "$DIST_DIR/copyright" << 'COPYRIGHT_EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: DisplayCAL
Upstream-Contact: Florian Höch <florian@displaycal.net>
Source: https://github.com/eoyilmaz/displaycal-py3

Files: *
Copyright: 2004-2026 Florian Höch, Erkan Özgür Yılmaz
License: GPL-3+

Files: *
Comment: DisplayCAL-CG Edition — packaged, localized (Romanian) and
 distributed by Cristi Gordaș (GDC), under the same GPLv3 license as the
 upstream project. Original authors' copyright and license notices remain
 fully intact per GPLv3 §5/§7 — this is a distribution note, not a
 replacement of the original copyright.

License: GPL-3+
 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.
 .
 On Debian systems, the complete text of the GNU General Public
 License version 3 can be found in "/usr/share/common-licenses/GPL-3".
COPYRIGHT_EOF
fi

# Unele wheel-uri (Pillow ș.a.) vin cu dylib-uri deja ad-hoc semnate în
# .dylibs/ (ex: liblzma.5.dylib). Rescrierea install-name-urilor de către
# macholib (folosit intern de py2app la copiere) NU păstrează corect
# blocul LC_CODE_SIGNATURE existent — rezultă un fișier cu segmentul
# __LINKEDIT corupt ("internal error in Code Signing subsystem" /
# "the __LINKEDIT segment does not cover the end of the file" la
# semnarea noastră ulterioară), confirmat: py2app copiază deja corupt,
# ÎNAINTE să atingem noi ceva. Stripăm semnăturile ad-hoc din sursă,
# în venv, ÎNAINTE de py2app — pe fișierul curat, `codesign
# --remove-signature` e sigur (testat), iar macholib rescrie apoi un
# dylib neted, fără bloc de semnătură de dezaliniat.
echo "==> Curăț semnăturile ad-hoc pre-existente din wheel-uri cu dylib-uri bundle-ate (înainte de py2app)…"
# Restrâns DELIBERAT doar la .dylibs/ (folderul standard în care
# delocate/auditwheel-macos ambalează dylib-uri C partajate lângă un
# wheel, ex: Pillow -> PIL/.dylibs/liblzma.5.dylib) — NU la tot venv-ul.
# Prima încercare a curățat ORICE .dylib/.so "adhoc" din tot $VENV/lib,
# inclusiv extensiile native compilate ale wxPython — asta a produs
# "partially initialized module 'wx' ... circular import" în py2app,
# deci extensiile din pachete precum wxPython/PySide6/numpy NU trebuie
# atinse aici, doar dylib-urile vendored, izolate, care nu sunt module
# Python importabile ele însele.
while IFS= read -r -d '' f; do
    if codesign -dv "$f" 2>&1 | grep -q "adhoc"; then
        codesign --remove-signature "$f" 2>/dev/null || true
    fi
done < <(find "$VENV/lib" -type d -name ".dylibs" -exec find {} -type f -name "*.dylib" -print0 \; 2>/dev/null)

# Cauza REALĂ a corupției (găsită după 6 rulări eșuate, nu presupusă):
# nu semnătura în sine, ci rescrierea LC_ID_DYLIB de către macholib
# (folosit intern de py2app, NU install_name_tool). liblzma.5.dylib
# vine cu un id placeholder scurt ("/DLC/PIL/.dylibs/liblzma.5.dylib",
# stil delocate), iar py2app îl rescrie la unul mai LUNG
# ("@executable_path/../Frameworks/liblzma.5.dylib") — macholib face
# asta prin editare Python pură a load command-urilor, fără să
# realoce corect __LINKEDIT când noul string nu încape în spațiul
# vechi, corupând fișierul (confirmat: aceeași corupere apare chiar
# și pe un fișier fără NICIO semnătură). Fix: rescriem noi ID-ul,
# ÎNAINTE de py2app, cu `install_name_tool` (unealta Apple oficială,
# care realocă corect load command-urile) — verificat direct că
# produce un fișier valid, semnabil normal.
echo "==> Pre-rescriu install-name-urile scurte/placeholder din .dylibs/ (înainte de py2app)…"
while IFS= read -r -d '' f; do
    old_id=$(otool -D "$f" 2>/dev/null | tail -1)
    base=$(basename "$f")
    new_id="@executable_path/../Frameworks/$base"
    if [ -n "$old_id" ] && [ "$old_id" != "$new_id" ]; then
        install_name_tool -id "$new_id" "$f" 2>/dev/null || true
    fi
done < <(find "$VENV/lib" -type d -name ".dylibs" -exec find {} -type f -name "*.dylib" -print0 \; 2>/dev/null)

# Păstrăm o copie CURATĂ, gata pentru semnare, a fiecărui dylib din
# .dylibs/ înainte să-l atingă py2app — vezi mai jos de ce.
CLEAN_DYLIBS_DIR=$(mktemp -d)
find "$VENV/lib" -type d -name ".dylibs" -exec find {} -type f -name "*.dylib" \; 2>/dev/null \
    | while IFS= read -r f; do cp "$f" "$CLEAN_DYLIBS_DIR/$(basename "$f")"; done

# "google" (folosit de protobuf, pentru Chromecast) e un pachet namespace
# PEP 420 — fără __init__.py, `imp_find_module` clasic al py2app nu-l
# poate localiza deloc (ImportError: No module named 'google', reprodus
# real, nu presupus). Creăm un __init__.py gol, DOAR local în venv-ul de
# build — transformă "google" într-un pachet obișnuit, găsibil de py2app,
# fără să schimbe conținutul lui protobuf.
GOOGLE_PKG_DIR="$VENV/lib/python3.13/site-packages/google"
if [ -d "$GOOGLE_PKG_DIR" ] && [ ! -f "$GOOGLE_PKG_DIR/__init__.py" ]; then
    touch "$GOOGLE_PKG_DIR/__init__.py"
fi

echo "==> native_build.py py2app --arch=$ARCH…"
MACOSX_DEPLOYMENT_TARGET="11.0" ARCHFLAGS="-arch $ARCH" \
    "$VENV/bin/python3" native_build.py py2app --arch="$ARCH"

BUILD_FOLDER=$(find "$DIST_DIR" -maxdepth 1 -type d -iname "py2app.macosx*")
APP_ROOT=$(find "$BUILD_FOLDER" -maxdepth 1 -type d -name "DisplayCAL-*")
if [ -z "$APP_ROOT" ]; then
    echo "EROARE: native_build.py nu a produs folderul DisplayCAL-<versiune>" >&2
    exit 1
fi
echo "==> Build produs în: $APP_ROOT"

# Cauza REALĂ, definitivă (găsită după 7 rulări eșuate identic pe
# liblzma.5.dylib, nu presupusă): py2app are propriul
# `codesign_adhoc()` (py2app/util.py) care rulează intern
# `codesign --preserve-metadata=identifier,entitlements,flags,runtime
# -f -s -` pe FIECARE fișier Mach-O din bundle. `--preserve-metadata`
# cere o semnătură EXISTENTĂ validă de la care să preia acele câmpuri —
# pe un dylib fără nicio semnătură (cazul liblzma.5.dylib, cu id
# placeholder rescris de macholib/noi), acest pas eșuează, dar
# codesign scrie totuși un `LC_CODE_SIGNATURE` orfan/corupt pe disc
# înainte de eroare — de aici "code object is not signed at all" +
# "main executable failed strict validation" la ORICE încercare
# ulterioară de semnare, a noastră sau a lui py2app. Fix: suprascriem
# copiile corupte din DisplayCAL.app (singurul deținător fizic — vezi
# comentariul din sign_all_apps) cu versiunea curată, salvată mai sus,
# ÎNAINTE de semnarea noastră proprie (care NU folosește
# --preserve-metadata și funcționează curat pe fișiere nesemnate).
MAIN_FRAMEWORKS="$APP_ROOT/DisplayCAL.app/Contents/Frameworks"
if [ -d "$MAIN_FRAMEWORKS" ]; then
    for clean in "$CLEAN_DYLIBS_DIR"/*.dylib; do
        base=$(basename "$clean")
        if [ -f "$MAIN_FRAMEWORKS/$base" ]; then
            cp "$clean" "$MAIN_FRAMEWORKS/$base"
        fi
    done
fi
rm -rf "$CLEAN_DYLIBS_DIR"

# PySide6 bundlează accidental resturi de build INTERNE ale propriei
# unelte QML (fișiere `.cpp.o` — obiecte C++ compilate, intermediare,
# sub .../PySide6/Qt/qml/.../objects-RelWithDebInfo/...) — sunt Mach-O
# valide (de-aia codesign/notarize le prinde), dar nu sunt executabile
# reale, niciodată rulate de DisplayCAL la runtime. Găsit direct din
# log-ul de notarizare Apple (singurele 2 fișiere rămase nesemnate, din
# 291 inițial) — le eliminăm din pachet, nu le semnăm (n-au ce căuta
# într-o distribuție finală).
echo "==> Elimin resturile de build (.o) bundle-ate accidental de PySide6…"
find "$APP_ROOT/DisplayCAL.app" -type f -name "*.o" -delete 2>/dev/null || true

sign_one_app() {
    local APP_PATH="$1"
    echo "==> [codesigning] Semnez $(basename "$APP_PATH")…"
    # Secvența exactă din release_builds.yml (upstream) — Qt/PySide6
    # își împachetează .framework-urile FĂRĂ symlink-urile standard
    # macOS (fără Versions/Current), deci binarul real din
    # Versions/A/<Nume> trebuie semnat EXPLICIT, separat de directorul
    # .framework — altfel rezultă un crash SIGKILL la runtime,
    # confirmat de upstream, nu presupus.
    # NU rulăm `codesign --remove-signature` pe *.dylib/*.so/*.app aici —
    # multe dylib-uri vin din wheel-uri (ex: liblzma.5.dylib din
    # Pillow/.dylibs) deja ad-hoc semnate la build; `--remove-signature`
    # pe ELE produce "internal error in Code Signing subsystem" și
    # corupe segmentul __LINKEDIT (confirmat direct: fișierul devine
    # nevalid, `install_name_tool` refuză cu "the __LINKEDIT segment
    # does not cover the end of the file"). `codesign --sign -f`
    # înlocuiește o semnătură existentă direct, fără strip — testat pe
    # exact acest fișier, funcționează curat. Strip-ul explicit rămâne
    # DOAR pentru binarul real din interiorul framework-urilor Qt mai
    # jos (Versions/A/<Nume>) — acolo e documentat necesar de upstream
    # pentru un motiv diferit (codesign nu-l "vede" fără el, nu corupere).
    find -L "$APP_PATH" -type d -name "*.framework" -exec codesign --remove-signature {} + 2>/dev/null || true
    find -L "$APP_PATH/Contents" -type d -name "*.framework" | while read -r FW; do
        NAME=$(basename "$FW" .framework)
        find -L "$FW/Versions" -mindepth 2 -maxdepth 2 -type f -name "$NAME" -exec codesign --remove-signature {} + 2>/dev/null || true
    done

    find -L "$APP_PATH/Contents" -type f \( -name "*.dylib" -o -name "*.so" \) \
        -exec codesign --sign "$APPLE_SIGN_IDENTITY_APP" --timestamp -f -o runtime {} + 2>/dev/null || true
    # PySide6 aduce propriile unelte native fără extensie (lrelease,
    # lupdate, balsam, qmlformat, qmllint, qsb, svgtoqml și tot
    # Qt/libexec/*) — deja ad-hoc semnate din distribuția Qt, iar
    # `--deep` de mai jos NU le re-semnează forțat pe cele deja
    # "valide" — respinse direct de notarytool ("no secure timestamp",
    # "hardened runtime not enabled"), găsit abia la prima notarizare
    # reală. Le semnăm explicit, individual, pe baza tipului real
    # (Mach-O), nu al extensiei.
    find -L "$APP_PATH/Contents/Resources" -type f -perm -u+x 2>/dev/null | while read -r f; do
        file "$f" 2>/dev/null | grep -q "Mach-O" \
            && codesign --sign "$APPLE_SIGN_IDENTITY_APP" --timestamp -f -o runtime "$f" 2>/dev/null
    done || true
    find -L "$APP_PATH/Contents" -type d -name "*.app" \
        -exec codesign --sign "$APPLE_SIGN_IDENTITY_APP" --timestamp -f -o runtime {} + 2>/dev/null || true
    find -L "$APP_PATH/Contents" -type d -name "*.framework" | while read -r FW; do
        NAME=$(basename "$FW" .framework)
        find -L "$FW/Versions" -mindepth 2 -maxdepth 2 -type f -name "$NAME" \
            -exec codesign --sign "$APPLE_SIGN_IDENTITY_APP" --timestamp -f -o runtime {} + 2>/dev/null || true
    done
    find -L "$APP_PATH/Contents" -type d -name "*.framework" \
        -exec codesign --sign "$APPLE_SIGN_IDENTITY_APP" --timestamp -f -o runtime {} + 2>/dev/null || true

    codesign --force --deep --timestamp --options runtime \
        --entitlements misc/entitlements.plist \
        --sign "$APPLE_SIGN_IDENTITY_APP" "$APP_PATH"

    echo "==> [codesigning] Verific $(basename "$APP_PATH")…"
    # NU folosim `--deep --strict` aici: py2app construiește cele 8 unelte
    # satelit (Testchart Editor, 3D LUT Maker etc.) ca bundle-uri MICI
    # (~400KB) care partajează Frameworks/Resources/MacOS/python cu
    # DisplayCAL.app prin symlink-uri ce ies din propriul bundle
    # (ex: Testchart Editor.app/Contents/Frameworks/Python.framework ->
    # ../../../DisplayCAL.app/Contents/Frameworks/Python.framework) —
    # design intenționat upstream (vezi comentariile din _setup.py,
    # ~linia 276-331), NU un artefact al semnării noastre paralele.
    # `codesign --verify --deep --strict` respinge ORICE symlink cu
    # destinație în afara bundle-ului ("invalid destination for symbolic
    # link in bundle") — confirmat local, reprodus și fără paralelizare.
    # Upstream însuși (.github/workflows/release_builds.yml) NU rulează
    # niciodată acest verify strict — doar semnează. Verificăm doar
    # sigiliul propriu al bundle-ului (fără -deep), suficient ca sanity
    # check; validarea reală de conținut se face la notarizare, care
    # primește toate cele 9 app-uri împreună (symlink-urile se rezolvă
    # corect în interiorul arhivei trimise).
    codesign --verify --verbose=2 "$APP_PATH"
    echo "==> [codesigning] Gata: $(basename "$APP_PATH")"
}

sign_satellite_app() {
    # Cele 8 unelte satelit (Testchart Editor, 3D LUT Maker etc.) NU au
    # propriile Frameworks/dylib-uri fizice — TOTUL, în afară de propriul
    # executabil mic (Contents/MacOS/DisplayCAL-<tool>) și Info.plist, e
    # symlink către fișierele REALE din DisplayCAL.app (confirmat: `find`
    # fără `-L` arată doar 4 fișiere reale per unealtă, restul symlink-uri
    # cu ținta ../../../DisplayCAL.app/...). De aceea NU repetăm aici
    # pass-urile de strip+resign pe dylib/framework (deja făcute o
    # singură dată, pe fișierele fizice, în sign_one_app("DisplayCAL.app")
    # de mai jos) — a face asta din nou, din 8 procese, ar SCRIE din nou
    # peste ACELEAȘI fișiere fizice, concurent — exact cauza reală a
    # erorii găsite ("liblzma.5.dylib: code object is not signed at all"
    # după rularea în paralel a tuturor celor 9): un satelit rula
    # `codesign --remove-signature` peste fișierul deja semnat de
    # DisplayCAL.app (sau invers), lăsându-l nesemnat la final. Fără
    # `--deep`, `codesign --sign` aici doar CITEȘTE conținutul prin
    # symlink-uri (pentru sigiliul CodeResources) și scrie doar în
    # sigiliul PROPRIU al bundle-ului satelit — sigur de rulat în paralel.
    local APP_PATH="$1"
    echo "==> [codesigning] Semnez $(basename "$APP_PATH") (satelit)…"
    # O semnare NEDEEP pe bundle semnează DOAR executabilul desemnat
    # (CFBundleExecutable din Info.plist, aici "DisplayCAL-<tool>") +
    # sigiliul de resurse — NU atinge alte binare Mach-O reale, proprii,
    # care stau lângă el în MacOS/ dar nu sunt "the" main executable.
    # Fiecare satelit are ȘI propriul interpretor Python real (nu
    # symlink, spre deosebire de restul conținutului) în
    # Contents/MacOS/python — lăsat de py2app doar ad-hoc semnat (fără
    # timestamp, fără hardened runtime), respins direct de notarizare
    # cu exact aceste 3 erori. Le semnăm explicit pe amândouă înainte
    # de sigiliul final al bundle-ului.
    for real_bin in "$APP_PATH/Contents/MacOS"/*; do
        [ -L "$real_bin" ] && continue
        [ -f "$real_bin" ] || continue
        codesign --sign "$APPLE_SIGN_IDENTITY_APP" --timestamp -f -o runtime "$real_bin"
    done
    codesign --force --timestamp --options runtime \
        --entitlements misc/entitlements.plist \
        --sign "$APPLE_SIGN_IDENTITY_APP" "$APP_PATH"
    echo "==> [codesigning] Verific $(basename "$APP_PATH")…"
    codesign --verify --verbose=2 "$APP_PATH"
    echo "==> [codesigning] Gata: $(basename "$APP_PATH")"
}

sign_all_apps() {
    if [ -z "${APPLE_SIGN_IDENTITY_APP:-}" ]; then
        echo "==> [codesigning] APPLE_SIGN_IDENTITY_APP nesetată — .app-urile rămân nesemnate (ad-hoc)."
        for APP_PATH in "$APP_ROOT"/*.app; do
            codesign --force --deep --sign - "$APP_PATH"
        done
        return 0
    fi
    # DisplayCAL.app e SINGURUL bundle care deține fizic dylib-urile și
    # framework-urile (1.4GB) — celelalte 8 doar le simbolizează. Trebuie
    # semnat COMPLET și SINGUR, înaintea oricărui satelit, altfel un
    # satelit pornit concurent ar scrie peste aceleași fișiere fizice
    # (vezi comentariul din sign_satellite_app).
    local main_app="$APP_ROOT/DisplayCAL.app"
    sign_one_app "$main_app"

    # Abia acum, cu fișierele fizice deja semnate definitiv, cele 8
    # satelit pot fi semnate în paralel — nu mai scriu nimic în ele.
    local pids=()
    for APP_PATH in "$APP_ROOT"/*.app; do
        [ "$APP_PATH" = "$main_app" ] && continue
        sign_satellite_app "$APP_PATH" &
        pids+=($!)
    done
    local failed=0
    for pid in "${pids[@]}"; do
        wait "$pid" || failed=1
    done
    if [ "$failed" -ne 0 ]; then
        echo "EROARE: cel puțin o semnare a eșuat (vezi mesajele de mai sus)." >&2
        exit 1
    fi
}
sign_all_apps

if [ -n "${APPLE_SIGN_IDENTITY_APP:-}" ]; then
    # O SINGURĂ notarizare pentru toate cele 9 aplicații (Apple acceptă
    # mai multe executabile semnate într-un singur pachet trimis) — 9
    # trimiteri separate ar însemna 9 cozi de așteptare la Apple, de
    # multe ori mai lent fără niciun beneficiu real.
    echo "==> [codesigning] Împachetez toate cele 9 aplicații pentru O SINGURĂ notarizare…"
    upload_zip="/tmp/notarize-all-$$.zip"
    ditto -c -k --keepParent "$APP_ROOT" "$upload_zip"
    echo "==> [codesigning] Trimit la Apple (poate dura 1-20 min, pachet mare)…"
    if [ -n "${APPLE_NOTARY_KEY_ID:-}" ]; then
        key_p8_path="/tmp/notary-key-$$.p8"
        printf '%s' "$APPLE_NOTARY_KEY_P8" > "$key_p8_path"
        xcrun notarytool submit "$upload_zip" --key "$key_p8_path" --key-id "$APPLE_NOTARY_KEY_ID" --issuer "$APPLE_NOTARY_ISSUER_ID" --wait
        rm -f "$key_p8_path"
    elif [ -n "${APPLE_NOTARY_APPLE_ID:-}" ]; then
        xcrun notarytool submit "$upload_zip" --apple-id "$APPLE_NOTARY_APPLE_ID" --team-id "$APPLE_NOTARY_TEAM_ID" --password "$APPLE_NOTARY_PASSWORD" --wait
    else
        xcrun notarytool submit "$upload_zip" --keychain-profile "gdc-notary" --wait
    fi
    rm -f "$upload_zip"

    echo "==> [codesigning] Staplez fiecare .app (bilet de notarizare, pentru instalare offline)…"
    for APP_PATH in "$APP_ROOT"/*.app; do
        xcrun stapler staple "$APP_PATH"
    done
fi

echo "==> Construiesc payload-ul de instalare (/Applications, toate cele 9 aplicații)…"
PAYLOAD_ROOT="$DIST_DIR/payload"
rm -rf "$PAYLOAD_ROOT"
mkdir -p "$PAYLOAD_ROOT/Applications"
for APP_PATH in "$APP_ROOT"/*.app; do
    cp -R "$APP_PATH" "$PAYLOAD_ROOT/Applications/"
done

COMPONENT_PKG="$DIST_DIR/DisplayCAL-CG-component.pkg"
FINAL_PKG="$DIST_DIR/DisplayCAL-CG-$VERSION.pkg"

echo "==> pkgbuild (instalare directă în /Applications)…"
pkgbuild \
    --root "$PAYLOAD_ROOT" \
    --identifier "$PKG_ID" \
    --version "$VERSION" \
    --install-location "/" \
    "$COMPONENT_PKG"

echo "==> Distribution.xml (licență GPLv3, Regula 19 — consent gate obligatoriu)…"
cat > "$DIST_DIR/Distribution.xml" << EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="1">
    <title>DisplayCAL-CG $VERSION</title>
    <license file="LICENSE.txt" mime-type="text/plain"/>
    <options customize="never" require-scripts="false" rootVolumeOnly="true"/>
    <domains enable_localSystem="true"/>
    <choices-outline>
        <line choice="default">
            <line choice="$PKG_ID"/>
        </line>
    </choices-outline>
    <choice id="default"/>
    <choice id="$PKG_ID" visible="false">
        <pkg-ref id="$PKG_ID"/>
    </choice>
    <pkg-ref id="$PKG_ID" version="$VERSION" onConclusion="none">DisplayCAL-CG-component.pkg</pkg-ref>
</installer-gui-script>
EOF
cp LICENSE.txt "$DIST_DIR/LICENSE.txt"

echo "==> productbuild (installer final)…"
productbuild \
    --distribution "$DIST_DIR/Distribution.xml" \
    --package-path "$DIST_DIR" \
    --resources "$DIST_DIR" \
    "$FINAL_PKG"

rm -rf "$PAYLOAD_ROOT" "$COMPONENT_PKG"

if [ -n "${APPLE_SIGN_IDENTITY_INSTALLER:-}" ]; then
    echo "==> [codesigning] Semnez .pkg-ul final…"
    TMP_SIGNED="${FINAL_PKG%.pkg}-signed.pkg"
    productsign --sign "$APPLE_SIGN_IDENTITY_INSTALLER" "$FINAL_PKG" "$TMP_SIGNED"
    mv "$TMP_SIGNED" "$FINAL_PKG"

    echo "==> [codesigning] Notarizez .pkg-ul final…"
    upload_pkg="/tmp/notarize-pkg-$$.pkg"
    cp "$FINAL_PKG" "$upload_pkg"
    if [ -n "${APPLE_NOTARY_KEY_ID:-}" ]; then
        key_p8_path="/tmp/notary-key-$$.p8"
        printf '%s' "$APPLE_NOTARY_KEY_P8" > "$key_p8_path"
        xcrun notarytool submit "$upload_pkg" --key "$key_p8_path" --key-id "$APPLE_NOTARY_KEY_ID" --issuer "$APPLE_NOTARY_ISSUER_ID" --wait
        rm -f "$key_p8_path"
    elif [ -n "${APPLE_NOTARY_APPLE_ID:-}" ]; then
        xcrun notarytool submit "$upload_pkg" --apple-id "$APPLE_NOTARY_APPLE_ID" --team-id "$APPLE_NOTARY_TEAM_ID" --password "$APPLE_NOTARY_PASSWORD" --wait
    else
        xcrun notarytool submit "$upload_pkg" --keychain-profile "gdc-notary" --wait
    fi
    rm -f "$upload_pkg"
    xcrun stapler staple "$FINAL_PKG"
else
    echo "==> [codesigning] APPLE_SIGN_IDENTITY_INSTALLER nesetată — .pkg rămâne nesemnat."
fi

cp "$FINAL_PKG" "$DIST_DIR/DisplayCAL-CG.pkg"
echo "==> Gata: $FINAL_PKG"
echo "==> Also: $DIST_DIR/DisplayCAL-CG.pkg"
