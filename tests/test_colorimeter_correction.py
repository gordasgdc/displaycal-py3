"""Tests for the toolkit-neutral colorimeter-correction internals.

Covers the pure CCXX byte-injection lifted out of
``MainFrame.create_colorimeter_correction_handler`` in
``DisplayCAL/colorimeter_correction.py``. No display or QApplication is needed.
"""

from DisplayCAL import colorimeter_correction as cc

# A minimal CCMX-shaped blob with the DISPLAY line the injector anchors on.
BASE = b'CCMX\n\nDESCRIPTOR "test"\nDISPLAY "LCD Monitor"\nCOLOR_REP "XYZ"\n'


class TestInjectCcxxMetadata:
    def test_no_values_is_noop(self):
        assert cc.inject_ccxx_metadata(BASE) == BASE

    def test_reference_inserted_above_display(self):
        out = cc.inject_ccxx_metadata(BASE, reference=b"i1 Pro")
        assert b'\nREFERENCE "i1 Pro"\nDISPLAY "LCD Monitor"\n' in out

    def test_str_value_is_utf8_encoded(self):
        out = cc.inject_ccxx_metadata(BASE, manufacturer="Dell")
        assert b'\nMANUFACTURER "Dell"\nDISPLAY "LCD Monitor"\n' in out

    def test_existing_keyword_not_duplicated(self):
        blob = b'CCMX\n\nREFERENCE "already"\nDISPLAY "LCD Monitor"\n'
        out = cc.inject_ccxx_metadata(blob, reference=b"i1 Pro")
        assert out == blob
        assert out.count(b"\nREFERENCE ") == 1

    def test_backslashes_escaped_as_literals(self):
        # A backslash in the value must survive re.sub as a literal backslash,
        # not be interpreted as a replacement backreference/escape.
        out = cc.inject_ccxx_metadata(BASE, manufacturer=b"a\\b")
        assert b'\nMANUFACTURER "a\\b"\nDISPLAY "LCD Monitor"\n' in out

    def test_all_fields_injected_in_fixed_order(self):
        out = cc.inject_ccxx_metadata(
            BASE,
            reference=b"ref",
            technology=b"LCD",
            manufacturer_id="ABC",
            manufacturer="Acme",
            observer=b"1931_2",
            reference_observer="1964_10",
        )
        block = (
            b'\nREFERENCE "ref"'
            b'\nTECHNOLOGY "LCD"'
            b'\nMANUFACTURER_ID "ABC"'
            b'\nMANUFACTURER "Acme"'
            b'\nOBSERVER "1931_2"'
            b'\nREFERENCE_OBSERVER "1964_10"'
            b'\nDISPLAY "LCD Monitor"\n'
        )
        assert block in out

    def test_partial_fields_only_inject_supplied(self):
        out = cc.inject_ccxx_metadata(BASE, technology=b"CRT", observer=b"1931_2")
        assert b'\nTECHNOLOGY "CRT"' in out
        assert b'\nOBSERVER "1931_2"' in out
        assert b"\nMANUFACTURER " not in out
        assert b"\nREFERENCE " not in out

    def test_falsy_values_skipped(self):
        out = cc.inject_ccxx_metadata(
            BASE, reference=b"", technology=None, manufacturer=""
        )
        assert out == BASE

    def test_missing_display_line_leaves_bytes_unchanged(self):
        blob = b'CCMX\n\nDESCRIPTOR "no display line"\n'
        out = cc.inject_ccxx_metadata(blob, reference=b"i1 Pro")
        assert out == blob
