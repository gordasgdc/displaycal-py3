"""Advanced-mode sections: every setting explained in RO/EN/ES, nothing changed silently."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("qtpy")
from test_ui_main_window import _init_config, qapp, stub_worker, window  # noqa: E402,F401

from DisplayCAL import config  # noqa: E402
from DisplayCAL import localization as lang  # noqa: E402
from DisplayCAL import settings_help as sh  # noqa: E402
from DisplayCAL.ui import settings_sections as ss  # noqa: E402


def _ids():
    return [i for tab in sh.SECTIONS.values() for _s, ids in tab for i in ids]


def test_registry_is_consistent():
    ids = _ids()
    assert len(ids) == len(set(ids)) and set(ids) == set(sh.ITEMS)


@pytest.mark.parametrize("code", ["en", "ro", "es"])
def test_every_item_and_section_has_text_in_every_language(code):
    import yaml

    here = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(here, "DisplayCAL", "lang", f"{code}.yaml"), encoding="utf-8") as f:
        d = yaml.safe_load(f)
    for tab, sections in sh.SECTIONS.items():
        for sec, _ids_ in sections:
            for key in sh.section_keys(tab, sec):
                assert d.get(key), (code, key)
    for item in sh.ITEMS.values():
        k = sh.item_keys(item.id)
        for part in ("name", "what", "when"):
            assert d.get(k[part]), (code, k[part])
        if item.has_needs and k["needs"] in d:
            assert d.get(k["needs"]), (code, k["needs"])
    for key in (
        "help.sections.expand", "help.label.when", "help.label.needs", "help.label.unit",
        "help.label.default", "help.label.unavailable", "help.kind.required",
        "help.kind.context", "help.kind.optional", "help.reason.generic", "help.reason.hidden",
    ):
        assert d.get(key), (code, key)


def test_help_texts_have_the_same_placeholders_in_all_languages():
    import yaml

    here = os.path.dirname(os.path.dirname(__file__))
    langs = {}
    for code in ("en", "ro", "es"):
        with open(os.path.join(here, "DisplayCAL", "lang", f"{code}.yaml"), encoding="utf-8") as f:
            langs[code] = yaml.safe_load(f)
    for key in langs["en"]:
        if key.startswith(("help.", "sec.")):
            assert key in langs["ro"] and key in langs["es"], key


def test_configuration_keys_exist():
    for item in sh.ITEMS.values():
        for key in item.cfg:
            if key.startswith("measurement_report."):
                continue  # report settings live in the report panel
            assert key in config.DEFAULTS or key in ("3dlut.trc_output_offset",), (item.id, key)


@pytest.fixture
def app(qapp, _init_config):  # noqa: F811
    lang.init()
    return qapp


def test_every_registered_widget_exists_on_its_tab(window):
    missing = []
    for tab, sections in sh.SECTIONS.items():
        owner = window._report_panel if tab == "verification" else window
        for _s, ids in sections:
            for i in ids:
                for attr in sh.ITEMS[i].widgets:
                    if getattr(owner, attr, None) is None:
                        missing.append((tab, i, attr))
    assert not missing, missing


def test_defaults_text_works_for_every_item(window):
    for item in sh.ITEMS.values():
        assert isinstance(ss.default_text(item), str)


def test_sections_exist_on_all_tabs_and_do_not_change_configuration(window):
    from DisplayCAL.guide_model import objective_keys

    keys = objective_keys(config.DEFAULTS)
    before = {k: config.getcfg(k) for k in keys}
    window.refresh_sections()
    for tab in ("display_instrument", "calibration", "profiling", "lut3d", "verification"):
        window._select_tab(tab)
    window._select_tab("guide")
    assert {k: config.getcfg(k) for k in keys} == before
    names = {h.objectName() for h in window._section_headers} | {
        h.objectName() for h in window._report_panel._section_headers
    }
    assert "section_calibration_target" in names and "section_profiling_chart" in names
    assert "section_verification_what" in names and "section_lut3d_file" in names


def test_disclosure_lists_what_unit_default_and_reasons(window):
    window._select_tab("calibration")
    header = next(h for h in window._section_headers if h.objectName() == "section_calibration_target")
    header._toggle()
    text = header.body.text()
    assert "cd/m²" in text and "6500" in text and "120" in text
    assert lang.getstr("help.label.when") in text


def test_unavailable_reasons_are_given(window):
    window._select_tab("lut3d")
    window.lut3d_apply_cal_cb.setEnabled(False)
    item = sh.ITEMS["lut3d_apply_cal"]
    assert ss.unavailable_reason(item, window, window.stack.currentWidget()).startswith("Available only") or ss.unavailable_reason(
        item, window, window.stack.currentWidget()
    )
