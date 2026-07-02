import os
import platform
import sys
from pathlib import Path
from unittest.mock import MagicMock
from zlib import crc32

import pytest
import requests
import wx
from wx import AppConsole, Button

from DisplayCAL import display_cal, config
from DisplayCAL.cgats import CGATS
from DisplayCAL.config import get_ccxx_testchart, get_icon, getcfg, setcfg
from DisplayCAL.dev.mocks import check_call, check_call_str
from DisplayCAL.display_cal import (
    app_update_check,
    app_up_to_date,
    check_donation,
    colorimeter_correction_check_overwrite,
    donation_message,
    ExtraArgsFrame,
    GamapFrame,
    get_cgats_measurement_mode,
    get_cgats_path,
    get_profile_load_on_login_label,
    IncrementingInt,
    install_scope_handler,
    MainFrame,
    MeasurementFileCheckSanityDialog,
    show_ccxx_error_dialog,
    StartupFrame,
    webbrowser_open,
)
from DisplayCAL.util_str import universal_newlines
from DisplayCAL.util_list import intlist
from DisplayCAL.worker import Worker, check_ti3
from DisplayCAL.wx_windows import ConfirmDialog, BaseInteractiveDialog


@pytest.fixture(scope="session", name="app", autouse=True)
def fixture_app() -> AppConsole:
    """Return app for tests."""
    return wx.GetApp() or wx.App()


@pytest.fixture(scope="module", name="mainframe")
def fixture_mainframe() -> MainFrame:
    """Return mainframe for tests.

    Module-scoped (not class-scoped) because MainFrame() also creates hidden
    child top-level windows (infoframe, measureframe, ...) that wx never
    fully releases without a running MainLoop(); building a fresh MainFrame()
    per test function leaked dozens of native windows over the file and
    caused multi-minute stalls on macOS CI runners (#778).
    """
    worker = Worker()
    return display_cal.MainFrame(worker=worker)


def test_update_colorimeter_correction_matrix_ctrl_items_1(
    mainframe: MainFrame,
) -> None:
    """MainFrame.update_colorimeter_correction_matrix_ctrl_items() method."""
    # I have no idea how it works, let's see...
    assert mainframe.colorimeter_correction_matrix_ctrl.Items != []
    before_items = mainframe.colorimeter_correction_matrix_ctrl.Items
    before_length = len(before_items)
    mainframe.update_colorimeter_correction_matrix_ctrl_items()
    after_items = mainframe.colorimeter_correction_matrix_ctrl.Items
    after_length = len(after_items)
    assert before_length == after_length
    assert before_items == after_items  # Really don't know anything about the method
    # but it was raising errors before, now it is fixed.


def test_show_ccxx_error_dialog(mainframe: MainFrame) -> None:
    """Test if error message is shown."""
    with check_call_str("DisplayCAL.display_cal.show_result_dialog"):
        show_ccxx_error_dialog(Exception("Malformed demo"), "path", mainframe)


@pytest.mark.skipif(
    sys.platform == "darwin" and os.getenv("GITHUB_ACTIONS") == "true",
    reason="ShowResultDialog is failing on CI macOS machines, skipping test.",
)
@pytest.mark.parametrize("argyll", (True, False), ids=("With argyll", "without argyll"))
@pytest.mark.parametrize("snapshot", (True, False), ids=("Snapshot", "No snapshot"))
@pytest.mark.parametrize("silent", (True, False), ids=("Silent", "Not silent"))
def test_app_update_check(
    mainframe: MainFrame, silent: bool, snapshot: bool, argyll: bool
) -> None:
    """Test the application update check."""
    with check_call(wx, "CallAfter", call_count=1):
        app_update_check(mainframe, silent, snapshot, argyll)


def test_check_donation(mainframe: MainFrame) -> None:
    """Test check for user disabled donation."""
    with check_call(wx, "CallAfter", call_count=-1):
        check_donation(mainframe, False)


def test_app_up_to_date(mainframe: MainFrame) -> None:
    """Test if 'up to date' messagebox is shown."""
    with check_call(BaseInteractiveDialog, "ShowModalThenDestroy", call_count=1):
        app_up_to_date(mainframe)


@pytest.mark.parametrize("response", (wx.ID_OK, wx.ID_NO), ids=("Ok", "Cancel"))
def test_donation_message(mainframe: MainFrame, response: int) -> None:
    """Test if donation messagebox is shown as expected."""
    with check_call(BaseInteractiveDialog, "ShowModal", response, call_count=1):
        with check_call_str(
            "DisplayCAL.display_cal.launch_file",
            call_count=1 if response == wx.ID_OK else 0,
        ):
            donation_message(mainframe)


@pytest.mark.skipif(
    os.getenv("GITHUB_ACTIONS") == "true",
    reason="Seems like the first call of ShowWindowModalBlocking always fails on remote."
    "Locally however the problem cannot be reproduced, skipping test for now."
)
@pytest.mark.parametrize(
    "update",
    (True, False),
    ids=("update comports", "don't update comports"),
)
@pytest.mark.parametrize(
    "response, value", (
        (wx.ID_OK, True),
        (wx.ID_NO, False),
    ),
    ids=("Ok", "Cancel"),
)
def test_colorimeter_correction_check_overwrite(
    data_files, mainframe: MainFrame, response: int, value: bool, update: bool
) -> None:
    """Test if function reacts as expected to user input."""
    path = data_files["0_16.ti3"].absolute()
    with open(path, "rb") as cgatsfile:
        cgats = universal_newlines(cgatsfile.read())
    # Pre-create the target file so os.path.isfile() returns True and the
    # overwrite dialog is always triggered, making the test self-contained.
    target_path = get_cgats_path(cgats)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "wb") as f:
        f.write(b"placeholder")
    try:
        with check_call(BaseInteractiveDialog, "ShowWindowModalBlocking", response):
            assert colorimeter_correction_check_overwrite(mainframe, cgats, update) == value
    finally:
        if os.path.exists(target_path):
            os.remove(target_path)


@pytest.mark.parametrize("file", ("0_16.ti3", "0_16_with_refresh.ti3", "default.ti3"))
@pytest.mark.parametrize(
    "instrument,modes",
    (
        ("ColorHug", ("F", "c", None)),
        ("ColorHug2", ("F", "c", None)),
        ("ColorMunki Smile", ("f", "c", None)),
        ("Colorimtre HCFR", ("R", "c", None)),
        ("K-10", ("F", "c", None)),
        ("fake_instrument", ("l", "c", None)),
    ),
)
def test_get_cgats_measurement_mode(
    data_files, instrument: str, file: str, modes: tuple[str, str, None]
) -> None:
    """Test if expected measurement mode is returned."""
    path = data_files[file].absolute()
    cgats = CGATS(cgats=path)
    if file == "0_16.ti3":
        mode = modes[0]
    elif file == "0_16_with_refresh.ti3":
        mode = modes[1]
    else:
        mode = modes[2]
    assert get_cgats_measurement_mode(cgats, instrument) == mode


def test_get_cgats_path(data_files) -> None:
    """Test if correct cgats path is returned."""
    path = data_files["default.ti3"].absolute()
    with open(path, "rb") as cgatsfile:
        cgats = universal_newlines(cgatsfile.read())
    assert Path(
        config.get_argyll_data_dir()
    ) / "Argyll Calibration Target chart information 3.cti3" == Path(
        get_cgats_path(cgats)
    )


def test_restore_testchart_clears_crash_state(mainframe: MainFrame) -> None:
    """restore_testchart() should clear testchart.file.backup left by a crash.

    If DisplayCAL crashes during a CCXX measurement, testchart.file is set to
    the CCXX testchart and testchart.file.backup holds the original path.
    restore_testchart() must restore the original and clear the backup so that
    is_ccxx_testchart() returns False and the correction section is shown.
    """
    from DisplayCAL.config import is_ccxx_testchart

    original_testchart = getcfg("testchart.file")
    ccxx_testchart = get_ccxx_testchart()

    # Simulate the config state left after a crash mid-CCXX measurement.
    setcfg("testchart.file.backup", original_testchart)
    setcfg("testchart.file", ccxx_testchart)

    try:
        assert is_ccxx_testchart(), "Pre-condition: should look like a CCXX testchart"
        mainframe.restore_testchart()
        assert not is_ccxx_testchart(), "After restore, should no longer be CCXX testchart"
        assert getcfg("testchart.file") == original_testchart
        assert getcfg("testchart.file.backup", False) is None
    finally:
        # Ensure clean state for other tests regardless of assertion outcome.
        setcfg("testchart.file", original_testchart)
        setcfg("testchart.file.backup", None)


def test_restore_measurement_mode_clears_crash_state(mainframe: MainFrame) -> None:
    """restore_measurement_mode() should clear backup values left by a crash.

    If DisplayCAL crashes during a CCXX measurement, measurement_mode.backup
    holds the original mode. restore_measurement_mode() must restore it and
    clear the backup.
    """
    original_mode = getcfg("measurement_mode")

    setcfg("measurement_mode.backup", original_mode)
    setcfg("measurement_mode", "c")  # Simulate mode changed for CCXX measurement.

    try:
        mainframe.restore_measurement_mode()
        assert getcfg("measurement_mode") == original_mode
        assert getcfg("measurement_mode.backup", False) is None
    finally:
        setcfg("measurement_mode", original_mode)
        setcfg("measurement_mode.backup", None)


def test_get_profile_load_on_login_label() -> None:
    """Test if load on login label is returned."""
    assert get_profile_load_on_login_label(True) == "profile.load_on_login"


def test_install_scope_handler(mainframe: MainFrame) -> None:
    """Test if install scope handler calls the correct methods for authentication dialog."""
    dlg = ConfirmDialog(
        mainframe,
        title="colorimeter_correction.import",
        msg="msg",
        ok="ok",
        cancel="cancel",
        bitmap=get_icon(32, "dialog-information"),
        alt="file.select",
    )
    dlg.install_systemwide = wx.RadioButton(dlg, -1, "install_local_system")
    dlg.install_systemwide.Bind(wx.EVT_RADIOBUTTON, install_scope_handler)
    with check_call(Button, "SetAuthNeeded", call_count=2):
        install_scope_handler(dlg=dlg)


def test_webbrowser_open(monkeypatch) -> None:
    """Test if function calls browser as expected."""
    opened_urls = []

    class PatchedWebBrowser:
        @staticmethod
        def open(url: str, new: int = 0, autoraise: bool = True) -> bool:
            opened_urls.append(url)
            return True

    # patch webbrowser.open
    monkeypatch.setattr("DisplayCAL.display_cal.webbrowser", PatchedWebBrowser)
    assert opened_urls == []
    url = "https://github.com/eoyilmaz/displaycal-py3"
    assert webbrowser_open(url)
    assert opened_urls == [url]


def test_incrementing_int() -> None:
    """Testing if self incrementing int increments every time it is used."""
    inc_integer = IncrementingInt()
    assert int(inc_integer) == 0
    [int(inc_integer) for _ in range(9)]
    assert int(inc_integer) == 10


def test_init_extra_args_frame(mainframe: MainFrame) -> None:
    """Test if ExtraArgsFrame is initialized properly"""
    with check_call(ExtraArgsFrame, "update_controls"):
        ExtraArgsFrame(mainframe)


def test_init_gamap_frame(mainframe: MainFrame) -> None:
    """Test if GamapFrame is initialized properly."""
    with check_call(GamapFrame, "update_layout"):
        GamapFrame(mainframe)


@pytest.mark.skipif(
    sys.platform == "darwin" and os.getenv("GITHUB_ACTIONS") == "true",
    reason="StartupFrame is failing on CI macOS machines, skipping test.",
)
def test_init_startup_frame() -> None:
    """Test if StartupFrame is initialized properly."""
    show_func_name = "Show"
    if (
        sys.platform == "darwin"
        and intlist(platform.mac_ver()[0].split(".")) >= [10, 10]
    ) or os.getenv("XDG_SESSION_TYPE") == "wayland":
        show_func_name = "ShowModal"

    with check_call(StartupFrame, show_func_name):
        StartupFrame()


@pytest.mark.skipif(
    sys.platform == "darwin",
    reason="MeasurementFileCheckSanityDialog hard-crashes the pytest-xdist worker "
    "process on macOS due to wxPython grid widget creation in a subprocess context.",
)
def test_init_measurement_file_check_sanity_dialog_frame(
    data_files, mainframe: MainFrame
) -> None:
    """Test if MeasurementFileCheckSanityDialog is initialized properly."""
    path = data_files["0_16.ti3"].absolute()
    cgats = CGATS(cgats=path)
    with check_call(MeasurementFileCheckSanityDialog, "Center"):
        MeasurementFileCheckSanityDialog(mainframe, cgats[0], check_ti3(cgats), False)


# ---------------------------------------------------------------------------
# is_new_update() unit tests
# ---------------------------------------------------------------------------

def test_is_new_update_returns_version_when_newer(monkeypatch):
    """is_new_update() returns a version tuple when a newer release exists."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"tag_name": "99.0.0", "assets": []}
    monkeypatch.setattr("DisplayCAL.display_cal.requests.get", lambda *a, **kw: mock_resp)
    result = display_cal.is_new_update()
    assert result == (99, 0, 0)


def test_is_new_update_returns_false_when_current(monkeypatch):
    """is_new_update() returns False when already on the latest version."""
    from DisplayCAL.meta import VERSION_TUPLE
    tag = ".".join(str(n) for n in VERSION_TUPLE[:3])
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"tag_name": tag, "assets": []}
    monkeypatch.setattr("DisplayCAL.display_cal.requests.get", lambda *a, **kw: mock_resp)
    assert display_cal.is_new_update() is False


def test_is_new_update_returns_false_on_network_error(monkeypatch):
    """is_new_update() returns False and does not raise on network failures."""
    def raise_error(*a, **kw):
        raise requests.RequestException("connection refused")
    monkeypatch.setattr("DisplayCAL.display_cal.requests.get", raise_error)
    assert display_cal.is_new_update() is False


def test_is_new_update_returns_false_on_bad_json(monkeypatch):
    """is_new_update() returns False when the response JSON is missing expected keys."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"unexpected_key": "value"}
    monkeypatch.setattr("DisplayCAL.display_cal.requests.get", lambda *a, **kw: mock_resp)
    assert display_cal.is_new_update() is False


# ---------------------------------------------------------------------------
# get_download_url() unit tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("plat,machine,version,expected_filename", [
    ("win32",  "AMD64",   "3.9.0", "DisplayCAL-3.9.0-Windows-x64.exe"),
    ("win32",  "ARM64",   "3.9.0", "DisplayCAL-3.9.0-Windows-arm64.exe"),
    ("darwin", "arm64",   "3.9.0", "DisplayCAL-3.9.0-macOS-arm64.dmg"),
    ("darwin", "aarch64", "3.9.0", "DisplayCAL-3.9.0-macOS-arm64.dmg"),
    ("darwin", "x86_64",  "3.9.0", "DisplayCAL-3.9.0-macOS-x86.dmg"),
    ("linux",  "x86_64",  "3.9.0", "displaycal-3.9.0.tar.gz"),
])
def test_get_download_url(monkeypatch, plat, machine, version, expected_filename):
    """get_download_url() returns the correct asset URL for each platform."""
    fake_assets = [
        {"name": expected_filename,
         "browser_download_url": f"https://example.com/{expected_filename}"},
    ]
    monkeypatch.setattr(display_cal, "RELEASE_DATA", {"assets": fake_assets})
    monkeypatch.setattr(display_cal.sys, "platform", plat)
    monkeypatch.setattr(display_cal.platform, "machine", lambda: machine)
    assert display_cal.get_download_url(version) == f"https://example.com/{expected_filename}"


def test_get_download_url_returns_none_when_no_matching_asset(monkeypatch):
    """get_download_url() returns None when no asset matches the current platform."""
    monkeypatch.setattr(display_cal, "RELEASE_DATA", {"assets": []})
    monkeypatch.setattr(display_cal.sys, "platform", "linux")
    monkeypatch.setattr(display_cal.platform, "machine", lambda: "x86_64")
    assert display_cal.get_download_url("3.9.0") is None


def test_get_download_url_returns_none_before_release_data_loaded(monkeypatch):
    """get_download_url() returns None gracefully when called before is_new_update()."""
    monkeypatch.setattr(display_cal, "RELEASE_DATA", None)
    assert display_cal.get_download_url("3.9.0") is None


def test_create_profile_name_crc32_with_bytes_edid(
    mainframe: MainFrame, monkeypatch
) -> None:
    """create_profile_name() resolves %crc32 when EDID data is bytes (#776)."""
    raw_edid = b"\x00\xff\xff\xff\xff\xff\xff\x00test-edid-payload"
    monkeypatch.setattr(
        mainframe.worker, "get_display_edid", lambda: {"edid": raw_edid}
    )
    mainframe.profile_name_textctrl.SetValue("%crc32")
    expected = "%X" % (crc32(raw_edid) & 0xFFFFFFFF)
    assert mainframe.create_profile_name() == expected


def test_create_profile_name_crc32_with_str_edid(
    mainframe: MainFrame, monkeypatch
) -> None:
    """create_profile_name() resolves %crc32 when EDID data is a str."""
    raw_edid = "test-edid-payload"
    monkeypatch.setattr(
        mainframe.worker, "get_display_edid", lambda: {"edid": raw_edid}
    )
    mainframe.profile_name_textctrl.SetValue("%crc32")
    expected = "%X" % (crc32(raw_edid.encode("utf-8")) & 0xFFFFFFFF)
    assert mainframe.create_profile_name() == expected


def test_create_profile_name_crc32_without_edid(
    mainframe: MainFrame, monkeypatch
) -> None:
    """create_profile_name() strips %crc32 when no EDID data is available."""
    monkeypatch.setattr(mainframe.worker, "get_display_edid", lambda: {})
    mainframe.profile_name_textctrl.SetValue("name-%crc32-suffix")
    assert mainframe.create_profile_name() == "name-suffix"
