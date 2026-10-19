"""Monitor lookup: detection, honest actions, no serials, no invented URLs."""

from DisplayCAL import display_lookup as dl


def test_external_monitor_on_a_mac_is_not_the_builtin_panel():
    m = dl.detect("BenQ PD3200U @ 1512, 0, 3840x2160", platform="darwin", hw_model="Mac14,9")
    assert m.kind == dl.EXTERNAL and m.name == "BenQ PD3200U" and m.mac_model_id is None


def test_builtin_panel_uses_the_mac_model_identifier():
    m = dl.detect("Mac14,9 @ 0, 0, 1512x982 [PRIMARY]", platform="darwin", hw_model="Mac14,9")
    assert (m.kind, m.mac_model_id) == (dl.APPLE_BUILTIN, "Mac14,9")
    m = dl.detect("Color LCD @ 0, 0, 1440x900", platform="darwin", hw_model="MacBookPro11,1")
    assert (m.kind, m.mac_model_id) == (dl.APPLE_BUILTIN, "MacBookPro11,1")


def test_builtin_name_on_windows_is_just_a_name():
    m = dl.detect("Color LCD", platform="win32", hw_model=None)
    assert m.kind == dl.EXTERNAL


def test_builtin_without_identifier_has_no_everymac_url():
    m = dl.detect("Color LCD", platform="darwin", hw_model=None)
    assert m.kind == dl.APPLE_BUILTIN and m.mac_model_id is None
    (act,) = dl.actions(m)
    assert not act.direct and act.url == dl.EVERYMAC_HOME and "?" not in act.url


def test_everymac_url_only_from_a_model_identifier():
    assert dl.everymac_url("Mac14,9") == "https://everymac.com/ultimate-mac-lookup/?identify=Mac14%2C9"
    for bad in ("C02XYZ123ABC", "serial 12345", "Mac14,9&x=1", "", "BenQ PD3200U", "../x"):
        assert dl.everymac_url(bad) is None


def test_external_monitor_is_copy_and_open_never_a_made_up_search_url():
    m = dl.detect("BenQ PD3200U @ 1512, 0, 3840x2160", platform="darwin", hw_model="Mac14,9")
    (act,) = dl.actions(m)
    assert act.url == dl.DISPLAYSPECS_HOME and act.copy_text == "BenQ PD3200U" and not act.direct


def test_no_model_identified_still_offers_the_site_without_inventing_a_query():
    m = dl.detect("", platform="linux", hw_model=None)
    assert m.kind == dl.UNKNOWN
    (act,) = dl.actions(m)
    assert act.copy_text is None and act.url == dl.DISPLAYSPECS_HOME and act.note_key == "lookup.note.no_model"


def test_serial_fragments_are_dropped_and_model_names_kept():
    assert dl.clean_name("MAG274QRF-QD serial: ABC123456 @ 0, 0, 2560x1440") == "MAG274QRF-QD"
    assert dl.clean_name("ASUS ProArt PA279CV @ 0,0,3840x2160") == "ASUS ProArt PA279CV"


def test_user_correction_cannot_make_an_external_monitor_a_builtin_panel():
    ext = dl.detect("BenQ PD3200U", platform="darwin", hw_model="Mac14,9")
    fixed = dl.corrected(ext, "BenQ PD3200UE")
    assert fixed.kind == dl.EXTERNAL and fixed.corrected and fixed.name == "BenQ PD3200UE"
    cleared = dl.corrected(ext, "   ")
    assert cleared.kind == dl.UNKNOWN
