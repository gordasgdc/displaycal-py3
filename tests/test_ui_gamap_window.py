"""Headless tests for the Qt gamut-mapping options window.

Exercise ``DisplayCAL.ui.gamap_window.GamapWindow`` under the shared offscreen
``QApplication``: control construction, the B2A quality checkbox cascade, the
CIECAM02 perceptual/saturation checkbox cascade, viewing-condition persistence
(including the latent wx bug fixed while porting — see the module docstring),
and the signals ``MainWindow`` connects to. No display, Argyll or instrument is
needed. See ``DisplayCAL/ui/MAINFRAME_PORT_PLAN.md`` (Stage 3+, gamap window).
"""

import os

import pytest

# Run headless: pick the offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyside6")

pytest.importorskip("qtpy")

from DisplayCAL import config  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL.config import getcfg, setcfg  # noqa: E402

#: A bundled reference profile that ships inside the repo (not the Argyll
#: install), so it's always present in CI. profileClass is "mntr" (display).
_ACES_ICM = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "DisplayCAL",
    "ref",
    "ACES.icm",
)


@pytest.fixture(scope="session")
def qapp():
    """Provide a singleton offscreen QApplication for the test session."""
    from qtpy.QtWidgets import QApplication

    config.initcfg()
    lang.init()
    lang.update_defaults()
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp):
    """Create a fresh GamapWindow with config isolated per test.

    Constructing the window and exercising its handlers writes to the global
    ``config.CFG``; snapshot and restore it so these tests don't leak state
    into the rest of the suite.
    """
    from DisplayCAL.ui.gamap_window import GamapWindow

    saved = dict(config.CFG["Default"])
    setcfg("argyll.version", "1.9.2")
    win = GamapWindow()
    try:
        yield win
    finally:
        win.close()
        config.CFG["Default"] = saved


class TestConstruction:
    def test_expected_controls_exist(self, window):
        for attr in (
            "low_quality_b2a_cb",
            "b2a_hires_cb",
            "b2a_size_ctrl",
            "b2a_smooth_cb",
            "gamap_default_intent_ctrl",
            "gamap_perceptual_cb",
            "gamap_perceptual_intent_ctrl",
            "gamap_saturation_cb",
            "gamap_saturation_intent_ctrl",
            "gamap_profile_ctrl",
            "gamap_src_viewcond_ctrl",
            "gamap_out_viewcond_ctrl",
        ):
            assert hasattr(window, attr), attr

    def test_viewcond_combos_have_none_option_first(self, window):
        assert window.gamap_src_viewcond_ctrl.itemData(0) is None
        assert window.gamap_out_viewcond_ctrl.itemData(0) is None

    def test_intent_combos_populated_for_modern_argyll(self, window):
        codes = [
            window.gamap_perceptual_intent_ctrl.itemData(i)
            for i in range(window.gamap_perceptual_intent_ctrl.count())
        ]
        assert "pa" in codes
        assert "lp" in codes

    def test_b2a_size_combo_has_auto_option(self, window):
        codes = [
            window.b2a_size_ctrl.itemData(i)
            for i in range(window.b2a_size_ctrl.count())
        ]
        assert -1 in codes


class TestUpdateControlsFromConfig:
    def test_low_quality_b2a_reflects_config(self, window):
        setcfg("profile.type", "l")
        setcfg("profile.quality.b2a", "l")
        setcfg("profile.b2a.hires", 0)
        window.update_controls()
        assert window.low_quality_b2a_cb.isChecked()
        assert not window.b2a_hires_cb.isChecked()

    def test_b2a_hires_disables_low_quality(self, window):
        setcfg("profile.type", "l")
        setcfg("profile.b2a.hires", 1)
        window.update_controls()
        assert window.b2a_hires_cb.isChecked()
        assert not window.low_quality_b2a_cb.isEnabled()

    def test_non_lut_profile_type_disables_gamap(self, window):
        setcfg("profile.type", "s")
        window.update_controls()
        assert not window.gamap_perceptual_cb.isChecked()
        assert not window.gamap_perceptual_cb.isEnabled()


class TestB2AQualityCascade:
    def test_checking_hires_disables_low_quality_and_enables_size(self, window):
        setcfg("profile.type", "l")
        window.update_controls()
        window.b2a_hires_cb.setChecked(True)
        assert window.b2a_size_ctrl.isEnabled()
        assert not window.low_quality_b2a_cb.isEnabled()
        assert getcfg("profile.b2a.hires") == 1

    def test_checking_low_quality_disables_hires(self, window):
        setcfg("profile.type", "l")
        setcfg("profile.b2a.hires", 0)
        window.update_controls()
        window.low_quality_b2a_cb.setChecked(True)
        assert not window.b2a_hires_cb.isEnabled()
        assert getcfg("profile.quality.b2a") == "l"

    def test_b2a_quality_changed_signal_emitted(self, window):
        setcfg("profile.type", "l")
        setcfg("profile.b2a.hires", 0)
        window.update_controls()
        calls = []
        window.b2a_quality_changed.connect(lambda: calls.append(True))
        window.b2a_hires_cb.setChecked(True)
        assert calls

    def test_b2a_size_change_persists(self, window):
        setcfg("profile.type", "l")
        setcfg("profile.b2a.hires", 1)
        window.update_controls()
        index = window.b2a_size_ctrl.findData(65)
        assert index >= 0
        window.b2a_size_ctrl.setCurrentIndex(index)
        assert getcfg("profile.b2a.hires.size") == 65


class TestGamapPerceptualSaturationCascade:
    def test_checking_saturation_forces_perceptual_on(self, window):
        setcfg("profile.type", "l")
        window.update_controls()
        window.gamap_perceptual_cb.setChecked(False)
        window.gamap_saturation_cb.setChecked(True)
        assert window.gamap_perceptual_cb.isChecked()
        assert getcfg("gamap_saturation") == 1
        assert getcfg("gamap_perceptual") == 1

    def test_unchecking_perceptual_forces_saturation_off(self, window):
        setcfg("profile.type", "l")
        window.update_controls()
        window.gamap_perceptual_cb.setChecked(True)
        window.gamap_saturation_cb.setChecked(True)
        window.gamap_perceptual_cb.setChecked(False)
        assert not window.gamap_saturation_cb.isChecked()
        assert getcfg("gamap_saturation") == 0

    def test_profile_settings_changed_emitted_on_perceptual_toggle(self, window):
        setcfg("profile.type", "l")
        setcfg("gamap_perceptual", 0)
        window.update_controls()
        calls = []
        window.profile_settings_changed.connect(lambda: calls.append(True))
        window.gamap_perceptual_cb.setChecked(True)
        assert calls


class TestViewcondPersistence:
    def test_src_viewcond_selection_persists(self, window):
        setcfg("profile.type", "l")
        window.update_controls()
        index = window.gamap_src_viewcond_ctrl.findData("mt")
        assert index >= 0
        window.gamap_src_viewcond_ctrl.setCurrentIndex(index)
        assert getcfg("gamap_src_viewcond") == "mt"

    def test_out_viewcond_non_nondisplay_selection_persists(self, window):
        # Regression test for the latent wx bug fixed while porting: wx's
        # ``gamap_out_viewcond_handler`` only ever called ``setcfg`` from
        # inside the nondisplay-viewcond confirmation branch, so selecting a
        # regular (non-warning) destination viewing condition never
        # persisted at all.
        setcfg("profile.type", "l")
        setcfg("gamap_out_viewcond", None)
        window.update_controls()
        index = window.gamap_out_viewcond_ctrl.findData("mt")
        assert index >= 0
        window.gamap_out_viewcond_ctrl.setCurrentIndex(index)
        assert getcfg("gamap_out_viewcond") == "mt"

    def test_out_viewcond_nondisplay_selection_needs_confirmation(
        self, window, monkeypatch
    ):
        from DisplayCAL.ui import gamap_window as gw

        setcfg("profile.type", "l")
        setcfg("gamap_out_viewcond", None)
        window.update_controls()
        monkeypatch.setattr(
            gw.QMessageBox,
            "question",
            staticmethod(lambda *a, **k: gw.QMessageBox.Cancel),
        )
        index = window.gamap_out_viewcond_ctrl.findData("pp")
        assert index >= 0
        window.gamap_out_viewcond_ctrl.setCurrentIndex(index)
        # Cancelled -> reverted, not persisted.
        assert getcfg("gamap_out_viewcond") is None

    def test_out_viewcond_nondisplay_selection_confirmed(self, window, monkeypatch):
        # Note: ``config.VALID_VALUES["gamap_out_viewcond"]`` only allows
        # mt/mb/md/jm/jd (a pre-existing, shared config constraint unrelated
        # to this window), so a nondisplay code like "pp" can never actually
        # round-trip through ``getcfg`` even when confirmed. What *should*
        # happen (and is toolkit-independent) is that confirming doesn't
        # revert the combo back to the previous selection the way cancelling
        # does.
        from DisplayCAL.ui import gamap_window as gw

        setcfg("profile.type", "l")
        setcfg("gamap_out_viewcond", None)
        window.update_controls()
        monkeypatch.setattr(
            gw.QMessageBox, "question", staticmethod(lambda *a, **k: gw.QMessageBox.Ok)
        )
        index = window.gamap_out_viewcond_ctrl.findData("pp")
        assert index >= 0
        window.gamap_out_viewcond_ctrl.setCurrentIndex(index)
        assert window.gamap_out_viewcond_ctrl.currentData() == "pp"


@pytest.mark.skipif(
    not os.path.isfile(_ACES_ICM), reason="bundled reference profile missing"
)
class TestGamapProfileAutoPreselect:
    def test_selecting_display_profile_preselects_monitor_viewcond(self, window):
        setcfg("profile.type", "l")
        setcfg("gamap_src_viewcond", None)
        window.update_controls()
        window.gamap_perceptual_cb.setChecked(True)
        window.gamap_profile_ctrl.set_path(_ACES_ICM)
        window._gamap_profile_changed(user_event=True)
        assert getcfg("gamap_src_viewcond") == "mt"

    def test_invalid_profile_path_shows_error_and_clears(self, window, monkeypatch):
        from DisplayCAL.ui import gamap_window as gw

        errors = []
        monkeypatch.setattr(
            gw.QMessageBox, "critical", staticmethod(lambda *a, **k: errors.append(a))
        )
        setcfg("profile.type", "l")
        window.update_controls()
        window.gamap_perceptual_cb.setChecked(True)
        bogus = _ACES_ICM + ".bogus-does-not-exist"
        # Fake an existing-but-unparsable path by pointing at a directory.
        directory = os.path.dirname(_ACES_ICM)
        window.gamap_profile_ctrl.set_path(directory)
        window._gamap_profile_changed(user_event=True)
        assert errors
        assert window.gamap_profile_ctrl.path() == ""
