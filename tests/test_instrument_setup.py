"""Tests for the toolkit-neutral instrument-setup / donation-nag helpers.

Covers ``DisplayCAL/instrument_setup.py``, the detection half of
``MainFrame.check_instrument_setup`` / ``check_donation``. No display or
QApplication is needed.
"""

from DisplayCAL import instrument_setup as isetup
from DisplayCAL.config import getcfg, setcfg
from DisplayCAL.meta import VERSION_STRING, VERSION_TUPLE


class FakeWorker:
    def __init__(self, instruments, spyder2_firmware=True, spyder4_cal=True):
        self.instruments = instruments
        self._spyder2_firmware = spyder2_firmware
        self._spyder4_cal = spyder4_cal

    def spyder2_firmware_exists(self, scope=None):
        return self._spyder2_firmware

    def spyder4_cal_exists(self):
        return self._spyder4_cal


class TestResolveInstrumentSetupNeeds:
    def test_no_instruments_needs_nothing(self):
        setcfg("colorimeter_correction_matrix_file", "AUTO:")
        worker = FakeWorker(instruments=[])
        needs = isetup.resolve_instrument_setup_needs(worker, [])
        assert needs.needs_spyder2_enable is False
        assert needs.needs_correction_import is False

    def test_i1d3_needs_import_when_uncovered(self):
        setcfg("colorimeter_correction_matrix_file", "AUTO:")
        worker = FakeWorker(instruments=["i1 DisplayPro, ColorMunki Display"])
        needs = isetup.resolve_instrument_setup_needs(worker, [])
        assert needs.needs_correction_import is True

    def test_i1d3_already_covered_needs_nothing(self):
        setcfg("colorimeter_correction_matrix_file", "AUTO:")
        worker = FakeWorker(instruments=["i1 DisplayPro, ColorMunki Display"])
        needs = isetup.resolve_instrument_setup_needs(worker, [""])
        assert needs.needs_correction_import is False

    def test_dtp94_needs_import_when_uncovered(self):
        setcfg("colorimeter_correction_matrix_file", "AUTO:")
        worker = FakeWorker(instruments=["DTP94"])
        needs = isetup.resolve_instrument_setup_needs(worker, [])
        assert needs.needs_correction_import is True

    def test_explicit_correction_file_suppresses_import_need(self):
        setcfg("colorimeter_correction_matrix_file", "/some/file.ccmx")
        worker = FakeWorker(instruments=["DTP94", "i1 DisplayPro, ColorMunki Display"])
        needs = isetup.resolve_instrument_setup_needs(worker, [])
        assert needs.needs_correction_import is False

    def test_spyder2_without_firmware_needs_enable_and_blocks_import(self):
        setcfg("colorimeter_correction_matrix_file", "AUTO:")
        worker = FakeWorker(instruments=["Spyder2"], spyder2_firmware=False)
        needs = isetup.resolve_instrument_setup_needs(worker, [])
        assert needs.needs_spyder2_enable is True
        # Spyder2 also matches the "icd" correction-import condition, but the
        # wx original short-circuits the import check while spyd2 is pending.
        assert needs.needs_correction_import is False

    def test_spyder2_with_firmware_present_falls_through_to_import_check(self):
        setcfg("colorimeter_correction_matrix_file", "AUTO:")
        worker = FakeWorker(instruments=["Spyder2"], spyder2_firmware=True)
        needs = isetup.resolve_instrument_setup_needs(worker, [])
        assert needs.needs_spyder2_enable is False
        assert needs.needs_correction_import is True

    def test_spyder4_needs_import_when_cal_missing(self):
        setcfg("colorimeter_correction_matrix_file", "AUTO:")
        worker = FakeWorker(instruments=["Spyder4"], spyder4_cal=False)
        needs = isetup.resolve_instrument_setup_needs(worker, [])
        assert needs.needs_correction_import is True

    def test_spyder4_with_cal_present_needs_nothing(self):
        setcfg("colorimeter_correction_matrix_file", "AUTO:")
        worker = FakeWorker(instruments=["Spyder4"], spyder4_cal=True)
        needs = isetup.resolve_instrument_setup_needs(worker, [])
        assert needs.needs_correction_import is False


class TestShouldShowDonationMessage:
    def test_returns_configured_flag(self):
        setcfg("last_launch", VERSION_STRING)
        setcfg("show_donation_message", 0)
        assert isetup.should_show_donation_message() is False
        setcfg("show_donation_message", 1)
        assert isetup.should_show_donation_message() is True

    def test_major_version_bump_resets_flag_and_updates_last_launch(self):
        old_major = max(VERSION_TUPLE[0] - 1, 0)
        setcfg("last_launch", f"{old_major}.0.0")
        setcfg("show_donation_message", 0)
        assert isetup.should_show_donation_message() is True
        assert getcfg("last_launch") == VERSION_STRING
