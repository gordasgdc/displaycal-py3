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
# Resolve to an absolute path before we `cd "$WORK_DIR"` below: a relative
# path (as the CI workflow passes, e.g. "dist/DisplayCAL-x86_64.AppImage")
# would otherwise land inside the temp work dir and get wiped out by the
# final `rm -rf "$WORK_DIR"`.
OUTPUT_PATH="$(realpath -m "$3")"

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

# 2b. Prune Qt subsystems DisplayCAL/pyqtgraph/qtpy never import (verified via
# grep: only QtCore/QtGui/QtWidgets, plus a handful of small supporting
# modules, are ever touched). The full PySide6 wheel bundles dozens of
# unrelated Qt subsystems (Quick/Qml, Multimedia with a bundled ffmpeg,
# WebEngine, Bluetooth, 3D, ...), and linuxdeploy below walks every .so it
# finds anywhere under the AppDir (not just ones reachable from
# --executable), so it aborts on incomplete/broken dependency chains inside
# those unused subsystems, e.g. a QtQuick VirtualKeyboard QML plugin needing
# libQt6QuickShapesDesignHelpers.so.6, which the wheel doesn't even ship.
# This is a denylist, not an allowlist: anything not named below (including
# Linux-specific internals like libQt6XcbQpa.so, invisible when checking
# against a macOS/Windows PySide6 install) is left alone.
QT_DIR="$APPDIR/usr/lib/python${PYVER}/site-packages/PySide6/Qt"
if [ -d "$QT_DIR" ]; then
  rm -rf "$QT_DIR/qml"
  UNUSED_QT_MODULES="3DAnimation 3DCore 3DExtras 3DInput 3DLogic \
    3DQuick 3DQuickAnimation 3DQuickExtras 3DQuickInput \
    3DQuickLogic 3DQuickRender 3DQuickScene2D 3DQuickScene3D \
    3DRender Bluetooth CanvasPainter Charts ChartsQml DataVisualization \
    DataVisualizationQml Designer DesignerComponents Graphs GraphsWidgets \
    Help HttpServer LabsAnimation LabsFolderListModel LabsPlatform \
    LabsQmlModels LabsSettings LabsSharedImage LabsStyleKit \
    LabsStyleKitImpl LabsSynchronizer LabsWavefrontMesh Location Lottie \
    LottieVectorImageGenerator LottieVectorImageHelpers Multimedia \
    MultimediaQuick MultimediaWidgets NetworkAuth Nfc Pdf PdfQuick \
    PdfWidgets Positioning PositioningQuick Qml QmlCompiler QmlCore \
    QmlLocalStorage QmlMeta QmlModels QmlNetwork QmlWorkerScript \
    QmlXmlListModel Quick Quick3D Quick3DAssetImport Quick3DAssetUtils \
    Quick3DEffects Quick3DGlslParser Quick3DHelpers Quick3DHelpersImpl \
    Quick3DIblBaker Quick3DParticleEffects Quick3DParticles \
    Quick3DRuntimeRender Quick3DSpatialAudio Quick3DUtils Quick3DXr \
    QuickControls2 QuickControls2Basic QuickControls2BasicStyleImpl \
    QuickControls2FluentWinUI3StyleImpl QuickControls2Fusion \
    QuickControls2FusionStyleImpl QuickControls2IOSStyleImpl \
    QuickControls2Imagine QuickControls2ImagineStyleImpl \
    QuickControls2Impl QuickControls2MacOSStyleImpl QuickControls2Material \
    QuickControls2MaterialStyleImpl QuickControls2Universal \
    QuickControls2UniversalStyleImpl QuickDialogs2 QuickDialogs2QuickImpl \
    QuickDialogs2Utils QuickEffects QuickLayouts QuickParticles \
    QuickShapes QuickTemplates2 QuickTest QuickTimeline \
    QuickTimelineBlendTrees QuickVectorImage QuickVectorImageGenerator \
    QuickVectorImageHelpers QuickWidgets RemoteObjects RemoteObjectsQml \
    Scxml ScxmlQml Sensors SensorsQuick SerialBus SerialPort ShaderTools \
    SpatialAudio Sql StateMachine StateMachineQml TextToSpeech UiTools \
    VirtualKeyboard VirtualKeyboardQml VirtualKeyboardSettings WebChannel \
    WebChannelQuick WebEngineCore WebEngineQuick \
    WebEngineQuickDelegatesQml WebEngineWidgets WebSockets WebView \
    WebViewQuick"
  for module in $UNUSED_QT_MODULES; do
    rm -f "$QT_DIR/lib/libQt6${module}.so"*
  done
  # Multimedia's bundled ffmpeg codec libraries.
  rm -f "$QT_DIR/lib"/libavcodec.so* "$QT_DIR/lib"/libavformat.so* \
    "$QT_DIR/lib"/libavutil.so* "$QT_DIR/lib"/libswresample.so* \
    "$QT_DIR/lib"/libswscale.so*

  # Same idea for the plugin tree: keep only the plugin kinds our own Qt
  # bundling config for the frozen Windows/macOS builds also keeps (see
  # DisplayCAL/setup.py's py2app qt_plugins option and
  # DisplayCAL/freeze.py's copy_qt_plugins()), plus a few small always-safe
  # ones.
  if [ -d "$QT_DIR/plugins" ]; then
    for d in "$QT_DIR/plugins"/*/; do
      name="$(basename "$d")"
      case "$name" in
        platforms|styles|imageformats|iconengines|platforminputcontexts|generic|networkinformation|tls|sqldrivers) ;;
        *) rm -rf "$d" ;;
      esac
    done
  fi

  # Each pruned Qt module also has its own shiboken Python-extension wrapper
  # one level up (e.g. PySide6/QtBluetooth.abi3.so, distinct from
  # Qt/lib/libQt6Bluetooth.so.6 above); linuxdeploy walks every .so under the
  # whole AppDir, so leaving these behind makes it try to resolve the
  # libQt6*.so.6 dependency we just deleted, e.g.:
  #   Could not find dependency: libQt6Bluetooth.so.6
  PYSIDE_DIR="$(dirname "$QT_DIR")"
  for module in $UNUSED_QT_MODULES; do
    rm -f "$PYSIDE_DIR/Qt${module}.abi3.so"
  done
fi

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
