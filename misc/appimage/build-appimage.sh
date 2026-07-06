#!/bin/bash
# Build a self-contained AppImage for the `displaycal` GUI.
#
# Must run on the same Ubuntu release/Python it's invoked with, since:
#  - wxPython has no PyPI wheel for Linux; we pull the prebuilt wheel that
#    matches this distro+Python from extras.wxpython.org instead of building
#    it from source.
#  - GTK3/X11/etc. are assumed to already be present on the machine that
#    later runs the AppImage (they are not bundled), same as any other
#    GTK-based AppImage.
#
# Usage: build-appimage.sh <wheel-path> <version> <output-path>
set -euo pipefail

WHEEL_PATH="$1"
VERSION="$2"
OUTPUT_PATH="$3"

MISC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(dirname "$MISC_DIR")"
WORK_DIR="$(mktemp -d)"
APPDIR="$WORK_DIR/DisplayCAL.AppDir"

PYVER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
# Query sysconfig rather than assuming /usr/lib/pythonX.Y, since actions/setup-python
# installs into hostedtoolcache rather than the system prefix.
SYS_PYTHON_LIB="$(python3 -c 'import sysconfig; print(sysconfig.get_path("stdlib"))')"
UBUNTU_RELEASE="$(. /etc/os-release && echo "$VERSION_ID")"

echo "Building AppImage for DisplayCAL ${VERSION} (Python ${PYVER}, Ubuntu ${UBUNTU_RELEASE})"

mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib" "$APPDIR/usr/share/metainfo"

# 1. A relocatable Python: copy the interpreter binary plus a full copy of
#    the standard library (not a `venv`, whose pyvenv.cfg hardcodes the
#    build machine's absolute path to the system install and would break as
#    soon as the AppImage is extracted somewhere else at runtime).
cp "$(command -v "python${PYVER}")" "$APPDIR/usr/bin/python3"
cp -a "$SYS_PYTHON_LIB" "$APPDIR/usr/lib/python${PYVER}"
rm -rf "$APPDIR/usr/lib/python${PYVER}/site-packages" "$APPDIR/usr/lib/python${PYVER}/dist-packages"
mkdir -p "$APPDIR/usr/lib/python${PYVER}/site-packages"

# Python.h and friends, needed since dbus-python (a DisplayCAL dependency on
# Linux) has no prebuilt wheel and gets compiled from source below. sysconfig
# resolves this path relative to sys.prefix, which the copied interpreter
# re-derives from its own location, so it must exist under $APPDIR/usr too.
SYS_PYTHON_INCLUDE="$(python3 -c 'import sysconfig; print(sysconfig.get_path("include"))')"
mkdir -p "$APPDIR/usr/include"
cp -a "$SYS_PYTHON_INCLUDE" "$APPDIR/usr/include/python${PYVER}"

# libpython itself is dlopen()'d by the interpreter binary at startup.
LIBPYTHON="$(ldd "$(command -v "python${PYVER}")" | awk '/libpython/{print $3}')"
[ -n "$LIBPYTHON" ] && cp -L "$LIBPYTHON" "$APPDIR/usr/lib/"

# 2. Install DisplayCAL and its dependencies straight into that prefix,
#    including the Ubuntu-matched wxPython wheel.
"$APPDIR/usr/bin/python3" -m ensurepip --upgrade
"$APPDIR/usr/bin/python3" -m pip install --upgrade \
  --prefix "$APPDIR/usr" \
  --find-links "https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-${UBUNTU_RELEASE}/" \
  "$WHEEL_PATH"

# 3. Desktop integration files.
cp "$REPO_ROOT/misc/displaycal.desktop" "$APPDIR/displaycal.desktop"
cp "$REPO_ROOT/misc/net.displaycal.DisplayCAL.appdata.xml" \
  "$APPDIR/usr/share/metainfo/net.displaycal.DisplayCAL.appdata.xml"
ICON_FILE="$REPO_ROOT/DisplayCAL/theme/icons/256x256/displaycal.png"

# 4. AppRun: invoke the bundled interpreter directly (rather than through a
#    pip-generated console-script, whose shebang hardcodes this build's
#    absolute path) and repoint PYTHONHOME/PYTHONPATH at the AppDir so the
#    bundled stdlib/site-packages are used instead of the host's.
cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
export PYTHONHOME="$HERE/usr"
export LD_LIBRARY_PATH="$HERE/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HERE/usr/bin/python3" -c "import sys; from DisplayCAL.main import main; sys.exit(main())" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# 5. Package. linuxdeploy wires up the top-level .desktop/icon/.DirIcon and
#    bundles the interpreter's own shared-library dependencies (libssl,
#    libffi, ...); it deliberately excludes core system libs like glibc,
#    which AppImages assume the host already provides.
LINUXDEPLOY="$WORK_DIR/linuxdeploy-x86_64.AppImage"
curl -sL -o "$LINUXDEPLOY" \
  https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
chmod +x "$LINUXDEPLOY"

cd "$WORK_DIR"
ARCH=x86_64 "$LINUXDEPLOY" --appimage-extract-and-run \
  --appdir "$APPDIR" \
  --executable "$APPDIR/usr/bin/python3" \
  --desktop-file "$APPDIR/displaycal.desktop" \
  --icon-file "$ICON_FILE" \
  --output appimage

mkdir -p "$(dirname "$OUTPUT_PATH")"
mv "$WORK_DIR"/DisplayCAL*.AppImage "$OUTPUT_PATH"
rm -rf "$WORK_DIR"
