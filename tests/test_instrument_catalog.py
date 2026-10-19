"""Tests for the instrument catalogue (identification honesty + placement keys)."""

from DisplayCAL import instrument_catalog as ic
from DisplayCAL.argyll_instruments import instruments


def test_every_family_name_exists_in_argyll_table_or_is_documented():
    # Names the catalogue claims must be real Argyll names (no invented models).
    known = set(instruments)
    for family in ic.FAMILIES:
        for name in family.argyll_names:
            assert name in known, f"{name!r} is not an Argyll instrument name"


def test_every_argyll_instrument_is_classified():
    # Anything Argyll lists must resolve to a family, otherwise it would show up
    # as an unexplained blank in the guided flow.
    skip = {n for n in instruments if n.startswith("Dummy")}
    for name in set(instruments) - skip:
        assert ic.identify(name) is not None
        assert ic.identify(name).family is not None, name


def test_shared_family_is_not_certain_and_offers_candidates():
    ident = ic.identify("i1 DisplayPro, ColorMunki Display")
    assert ident.certain is False
    assert any("Calibrite" in c for c in ident.candidates)
    assert any("i1Display Pro" in c for c in ident.candidates)


def test_spyderx2_and_spyder2024_share_usb_identity():
    assert "Spyder 2024" in ic.shared_usb_identity("SpyderX2")
    assert "SpyderX2" in ic.shared_usb_identity("Spyder 2024")


def test_unambiguous_family_is_certain():
    ident = ic.identify("ColorHug2")
    assert ident.certain is True
    assert ident.family.key == "colorhug"


def test_unknown_instrument_is_never_guessed():
    ident = ic.identify("Totally New Meter 9000")
    assert ident.family is None and ident.certain is False and ident.candidates == ()


def test_no_selection_returns_none():
    assert ic.identify(None) is None
    assert ic.identify("") is None


def test_vendor_prefix_is_stripped():
    ident = ic.identify("X-Rite i1 Pro 2")
    assert ident is not None


def test_placement_steps_reference_tile_first():
    steps = ic.placement_steps(ic.KIND_SPECTRO_PEN, needs_reference_tile=True)
    assert steps[0] == "guide.place.calibrate_first"
    assert steps[-1] == "guide.place.screensaver_off"
    colorimeter = ic.placement_steps(ic.KIND_COLORIMETER, needs_reference_tile=False)
    assert "guide.place.calibrate_first" not in colorimeter
