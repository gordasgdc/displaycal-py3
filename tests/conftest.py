import os
import sys
import tempfile

# Isolate every DisplayCAL user path (preferences/config file, logs, storage,
# cache, ...) under a throwaway per-session directory, so running the test
# suite never reads from or writes to the developer's real config (e.g.
# ~/Library/Preferences/DisplayCAL/DisplayCAL.ini on macOS, ~/.config/DisplayCAL
# on Linux). DisplayCAL computes these paths from $HOME (and the XDG_* /
# Windows equivalents) at *import time* (see DisplayCAL/defaultpaths.py), so
# this must run before the first import of any DisplayCAL module — hence it
# sits at the very top of this file, ahead of every other import.
_TEST_HOME = tempfile.mkdtemp(prefix="displaycal-test-home-")
os.environ["HOME"] = _TEST_HOME
# Force (not setdefault) these: CI runners (e.g. GitHub Actions) often already
# export XDG_CONFIG_HOME/XDG_CACHE_HOME/XDG_DATA_HOME pointing outside
# _TEST_HOME, which would defeat the isolation above.
os.environ["XDG_CACHE_HOME"] = os.path.join(_TEST_HOME, ".cache")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_TEST_HOME, ".config")
os.environ["XDG_DATA_HOME"] = os.path.join(_TEST_HOME, ".local", "share")
if sys.platform == "win32":
    # Best-effort: the pywin32 SHGetSpecialFolderPath lookup DisplayCAL uses on
    # Windows queries the OS directly and ignores these, but the ctypes
    # fallback and any other HOME-based logic still benefit.
    os.environ["USERPROFILE"] = _TEST_HOME
    os.environ.setdefault("APPDATA", os.path.join(_TEST_HOME, "AppData", "Roaming"))
    os.environ.setdefault("LOCALAPPDATA", os.path.join(_TEST_HOME, "AppData", "Local"))

import faulthandler
import glob
import platform
import pathlib
import shutil
import subprocess
import tarfile
import time
import webbrowser
import zipfile

# Diagnostic-only: CI hangs (see issue #7's Qt-migration test-suite work) have
# repeatedly turned out to be real, un-mocked blocking calls (subprocesses,
# modal dialogs, QThread signal delivery) that are invisible from the outside
# -- a cancelled GitHub Actions job's log shows only the last test that
# *finished*, never what the process was actually doing when it stalled.
# Periodically dumping every thread's real Python-level stack trace turns
# that blind spot into a two-minute wait at most. Written to its own file
# rather than stderr: pytest's default per-test fd-level capturing would
# otherwise trap the dump in a buffer that's only flushed when the test
# finishes -- exactly what never happens on a hang. The workflow's
# "Dump thread stacks" step (if: always()) prints this file even when the
# job gets cancelled mid-test. Gated to CI only so local runs stay quiet.
if os.environ.get("GITHUB_ACTIONS") == "true":
    faulthandler.enable()
    _faulthandler_dump_file = open("faulthandler_dump.log", "a", buffering=1)
    faulthandler.dump_traceback_later(
        90, repeat=True, file=_faulthandler_dump_file
    )

from urllib.error import URLError

from requests import HTTPError

from DisplayCAL.debughelpers import DownloadError
import pytest

from DisplayCAL import config
from DisplayCAL.util_os import which
from DisplayCAL.worker import Worker

import DisplayCAL
from DisplayCAL import real_display_size_mm
from DisplayCAL.argyll import (
    get_argyll_latest_version,
    get_argyll_version_string,
    parse_argyll_version_string,
)
from DisplayCAL.colormath import get_rgb_space
from DisplayCAL.config import setcfg, writecfg
from DisplayCAL.icc_profile import ICCProfile
from DisplayCAL import util_os

# Never let a test pop a real browser tab or hand a URL/file to the OS's
# default-app opener. Help-menu / update-check / donate handlers across both
# the wx and Qt UIs call ``util_os.launch_file`` (which shells out to macOS's
# ``open``) or ``webbrowser.open`` directly, and several of those handlers
# aren't mocked by the tests that exercise them. Patching ``util_os`` here,
# before any other DisplayCAL module has a chance to do
# ``from DisplayCAL.util_os import launch_file`` (which binds a separate name
# into that module's own namespace), means every such import picks up this
# no-op instead of the real one. Tests that assert on the call args still
# work: their own ``monkeypatch.setattr(some_module, "launch_file", ...)``
# overrides this for the duration of that test and reverts back to this
# no-op afterwards, never to the real, OS-shelling-out function.
util_os.launch_file = lambda *args, **kwargs: None
webbrowser.open = lambda *args, **kwargs: True
webbrowser.open_new = lambda *args, **kwargs: True
webbrowser.open_new_tab = lambda *args, **kwargs: True
try:
    # Same reasoning for the Qt side: about_window.py / tooltip_window.py
    # call QDesktopServices.openUrl() directly on link/button activation.
    from qtpy.QtGui import QDesktopServices

    QDesktopServices.openUrl = staticmethod(lambda *args, **kwargs: True)
except ImportError:
    pass


@pytest.fixture(scope="module")
def data_files():
    """Generate data file list."""
    #  test/data
    extensions = [
        "*.cal",
        "*.icc",
        "*.lin",
        "*.ti1",
        "*.ti3",
        "*.tsv",
        "*.txt",
        "*.vrml",
    ]

    displaycal_parent_dir = pathlib.Path(DisplayCAL.__file__).parent
    search_paths = [
        displaycal_parent_dir,
        displaycal_parent_dir / "presets",
        displaycal_parent_dir / "ti1",
        displaycal_parent_dir.parent / "misc" / "ti3",
        displaycal_parent_dir.parent / "tests" / "data",
        displaycal_parent_dir.parent / "tests" / "data" / "sample",
        displaycal_parent_dir.parent / "tests" / "data" / "sample" / "issue129",
        displaycal_parent_dir.parent / "tests" / "data" / "sample" / "issue268",
        displaycal_parent_dir.parent / "tests" / "data" / "icc",
    ]
    d_files = {}
    for path in search_paths:
        for extension in extensions:
            # add files from DisplayCal/presets folder
            for element in path.glob(extension):
                d_files[element.name] = element

    yield d_files


@pytest.fixture(scope="module")
def data_path():
    """Return the tests/data folder path."""
    displaycal_parent_dir = pathlib.Path(DisplayCAL.__file__).parent
    return displaycal_parent_dir.parent / "tests" / "data"


@pytest.fixture(scope="session")
def setup_argyll():
    """Setup ArgyllCMS.

    This will search for ArgyllCMS binaries under ``.local/bin/Argyll*/bin`` and if it
    can not find it, it will download from the source.
    """
    # check if ArgyllCMS is already installed
    xicclu_path = which(f"xicclu{config.EXE_EXT}")
    if xicclu_path:
        # ArgyllCMS is already installed
        argyll_path = pathlib.Path(xicclu_path).parent
        setcfg("argyll.dir", str(argyll_path.absolute()))
        argyll_version_string = get_argyll_version_string("xicclu", True, [str(argyll_path)])
        argyll_version = parse_argyll_version_string(argyll_version_string)
        print(f"argyll_version_string: {argyll_version_string}")
        print(f"argyll_version: {argyll_version}")
        setcfg("argyll.version", argyll_version_string)
        writecfg()
        yield argyll_path
        return

    # first look in to ~/local/bin/ArgyllCMS
    home = pathlib.Path().home()
    argyll_search_paths = glob.glob(str(home / ".local" / "bin" / "Argyll*" / "bin"))

    argyll_path = None
    for path in reversed(argyll_search_paths):
        path = pathlib.Path(path)
        if path.is_dir():
            argyll_path = path
            setcfg("argyll.dir", str(argyll_path.absolute()))
            argyll_version_string = get_argyll_version_string(
                "xicclu", True, [str(path)]
            )
            argyll_version = parse_argyll_version_string(argyll_version_string)
            print(f"argyll_version_string: {argyll_version_string}")
            print(f"argyll_version: {argyll_version}")
            setcfg("argyll.version", argyll_version_string)
            writecfg()
            break

    print(f"argyll_path: {argyll_path}")
    if argyll_path:
        yield argyll_path
        return

    # apparently argyll has not been found
    # download from source
    get_argyll_latest_version.cache_clear()
    argyll_version = get_argyll_latest_version()
    if argyll_version == config.DEFAULTS.get("argyll.version"):
        # get_argyll_latest_version() couldn't reach the GitHub API (e.g. rate
        # limited) and fell back to the unusable placeholder version, which
        # would otherwise produce a guaranteed 404 download URL below. Fall
        # back to the version pinned in the CI workflow (the same version
        # used to pre-install ArgyllCMS on the runners) instead of giving up.
        env_version = os.environ.get("ARGYLL_VERSION")
        if env_version:
            print(
                f"Could not determine latest ArgyllCMS version, falling back "
                f"to $ARGYLL_VERSION={env_version!r}"
            )
            argyll_version = env_version
    argyll_domain = config.DEFAULTS.get("argyll.domain", "")
    mac_suffix = (
        "macOS11_arm64_bin.tgz"
        if platform.machine().lower() in ("arm64", "aarch64")
        else "osx10.6_x86_64_bin.tgz"
    )
    argyll_download_url = {
        "win32": f"{argyll_domain}/releases/download/{argyll_version}/Argyll_V{argyll_version}_win64_exe.zip",
        "darwin": f"{argyll_domain}/releases/download/{argyll_version}/Argyll_V{argyll_version}_{mac_suffix}",
        "linux": f"{argyll_domain}/releases/download/{argyll_version}/Argyll_V{argyll_version}_linux_x86_64_bin.tgz",
    }

    url = argyll_download_url[sys.platform]

    argyll_temp_path = tempfile.mkdtemp()
    # store current working directory
    current_working_directory = os.getcwd()

    # change dir to argyll temp path
    os.chdir(argyll_temp_path)

    # Download the package file if it doesn't already exist
    argyll_package_file_name = "Argyll.tgz" if sys.platform != "win32" else "Argyll.zip"
    if not os.path.exists(argyll_package_file_name):
        print(f"Downloading: {argyll_package_file_name}")
        print(f"URL: {url}")
        worker = Worker()
        max_download_retries = 3
        base_delay = 10
        for download_attempt in range(max_download_retries):
            result = worker.download(url, download_dir=argyll_temp_path)
            if isinstance(result, (DownloadError, HTTPError, PermissionError, URLError)):
                delay = base_delay * (2**download_attempt)
                if download_attempt < max_download_retries - 1:
                    print(
                        f"Error downloading {url}: {result}. "
                        f"Waiting {delay}s before retry..."
                    )
                    time.sleep(delay)
                else:
                    print(f"Error downloading {url}: {result}")
                    raise result
            else:
                break
        download_path = result
        print(f"Downloaded to: {download_path}")
        if os.path.exists(download_path):
            shutil.move(download_path, argyll_package_file_name)
    else:
        print(f"Package file already exists: {argyll_package_file_name}")
        print("Not downloading it again!")

    print(f"Decompressing Argyll Package: {argyll_package_file_name}")
    if sys.platform == "win32":
        with zipfile.ZipFile(argyll_package_file_name, "r") as zip_ref:
            zip_ref.extractall()
    else:
        with tarfile.open(argyll_package_file_name) as tar:
            tar.extractall()

    def cleanup():
        # cleanup the test
        shutil.rmtree(argyll_temp_path, ignore_errors=True)
        os.chdir(current_working_directory)

    argyll_path = pathlib.Path(argyll_temp_path) / f"Argyll_V{argyll_version}" / "bin"
    print(f"argyll_path: {argyll_path}")
    if argyll_path.is_dir():
        print("argyll_path is valid!")
        setcfg("argyll.dir", str(argyll_path.absolute()))
        argyll_version_string = get_argyll_version_string("xicclu", True, [str(argyll_path)])
        argyll_version = parse_argyll_version_string(argyll_version_string)
        print(f"argyll_version_string: {argyll_version_string}")
        print(f"argyll_version: {argyll_version}")
        setcfg("argyll.version", argyll_version_string)
        writecfg()
        os.environ["PATH"] = f"{argyll_path}{os.pathsep}{os.environ['PATH']}"
        yield argyll_path
        setcfg("argyll.dir", "")
        writecfg()
        cleanup()
    else:
        print("argyll_path is invalid!")
        cleanup()
        pytest.skip("ArgyllCMS can not be setup!")


@pytest.fixture(scope="function")
def random_icc_profile():
    """Create a random ICCProfile suitable for modification."""
    rec709_gamma18 = list(get_rgb_space("Rec. 709"))
    icc_profile = ICCProfile.from_rgb_space(
        rec709_gamma18, b"Rec. 709 gamma 1.8"
    )
    icc_profile_path = tempfile.mktemp(suffix=".icc")
    icc_profile.write(icc_profile_path)

    yield icc_profile, icc_profile_path

    # clean the file
    os.remove(icc_profile_path)


@pytest.fixture(scope="function")
def patch_subprocess():
    """Patch subprocess.

    Yields:
        Any: The patched subprocess class.
    """

    class Process:
        def __init__(self, output=None):
            self.output = output

        def communicate(self):
            return self.output, None

    class PatchedSubprocess:
        passed_args = []
        passed_kwargs = {}
        STDOUT = None
        PIPE = None
        output = {}
        wShowWindow = None
        STARTUPINFO = subprocess.STARTUPINFO if sys.platform == "win32" else None
        STARTF_USESHOWWINDOW = (
            subprocess.STARTF_USESHOWWINDOW if sys.platform == "win32" else None
        )
        SW_HIDE = subprocess.SW_HIDE if sys.platform == "win32" else None

        @classmethod
        def Popen(cls, *args, **kwargs):
            cls.passed_args += args
            cls.passed_kwargs.update(kwargs)
            process = Process(output=cls.output.get("".join(*args)))
            return process

    yield PatchedSubprocess


@pytest.fixture(scope="function")
def patch_argyll_util(monkeypatch):
    """Patch argyll.

    Yields:
        Any: The patched argyll class.
    """

    class PatchedArgyll:
        passed_util_name = []

        @classmethod
        def get_argyll_util(cls, util_name):
            cls.passed_util_name.append(util_name)
            return "dispwin"

    monkeypatch.setattr("DisplayCAL.real_display_size_mm.argyll", PatchedArgyll)

    yield PatchedArgyll


@pytest.fixture(scope="function")
def clear_displays():
    """Clear real_display_size_mm._displays."""
    real_display_size_mm._displays = None
    assert real_display_size_mm._displays is None
