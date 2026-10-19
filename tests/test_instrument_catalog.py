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


def test_unverified_family_gets_only_generic_steps_and_no_accessories():
    ident = ic.identify("Spyder5")
    seq = ic.resolve_placement(ident, None)
    assert not seq.verified and seq.variant == "generic"
    assert seq.accessories == ()  # nothing is claimed that was not verified
    assert "suction" not in " ".join(seq.accessories)


def test_ambiguous_family_asks_for_model_before_specific_steps():
    ident = ic.identify("i1 DisplayPro, ColorMunki Display")
    generic = ic.resolve_placement(ident, None)
    assert generic.needs_model_choice and not generic.verified
    chosen = ic.resolve_placement(ident, "Calibrite ColorChecker Display / Pro / Plus")
    assert chosen.verified and chosen.variant == "i1d3"
    assert chosen.sources == ("calibrite_qsg",)
    assert "tilt" not in chosen.steps  # the Calibrite guide does not mention it
    assert "suction_cups" not in chosen.accessories


def test_spyderx_steps_follow_the_datacolor_guide():
    ident = ic.identify("SpyderX")
    seq = ic.resolve_placement(ident, "Datacolor SpyderX Pro / Elite")
    assert seq.verified and seq.variant == "spyder_x"
    assert seq.steps == ("face", "cover", "contact", "tilt", "position")
    assert seq.accessories == ("sensor_cover",)


def test_x2_is_not_assumed_to_behave_like_spyderx():
    ident = ic.identify("SpyderX2")
    seq = ic.resolve_placement(ident, "Datacolor Spyder X2 Pro / Elite / Ultra")
    assert not seq.verified


def test_reference_tile_instruments_calibrate_first():
    ident = ic.identify("i1 Pro 2")
    seq = ic.resolve_placement(ident, None)
    assert seq.steps[0] == "calibrate"
