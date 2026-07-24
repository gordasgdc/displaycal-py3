import pytest

from DisplayCAL import demjson_compat
from DisplayCAL.demjson_compat import decode, encode


@pytest.fixture(scope="function")
def set_debug_mode():
    # Set debug mode for the duration of the test
    original_debug = demjson_compat.DEBUG
    demjson_compat.DEBUG = True
    yield
    # Restore original debug mode after the test
    demjson_compat.DEBUG = original_debug


def test_decode_simple_json():
    assert decode('{"a": 1, "b": 2}') == {"a": 1, "b": 2}


def test_decode_simple_json_with_debug(capsys, set_debug_mode):
    assert decode('{"a": 1, "b": 2}') == {"a": 1, "b": 2}
    captured = capsys.readouterr()
    assert 'JSON: {"a": 1, "b": 2}\n' in captured.out


def test_decode_with_single_line_comment():
    json_with_comment = """
    {
        // this is a comment
        "a": 1,
        "b": 2 // another comment
    }
    """
    assert decode(json_with_comment) == {"a": 1, "b": 2}


def test_decode_with_multiline_comment():
    json_with_comment = """
    {
        /* this is a
           multiline comment */
        "a": 1,
        "b": 2
    }
    """
    assert decode(json_with_comment) == {"a": 1, "b": 2}


def test_decode_with_comment_inside_string():
    json_with_comment = """
    {
        "a": "// not a comment",
        "b": 2
    }
    """
    assert decode(json_with_comment) == {"a": "// not a comment", "b": 2}


def test_decode_with_multiline_comment_inside_string():
    json_with_comment = """
    {
        "a": "/* not a comment */",
        "b": 2
    }
    """
    assert decode(json_with_comment) == {"a": "/* not a comment */", "b": 2}


def test_decode_with_escape_characters():
    json_with_comment = """
    {
        "a": "value with new line\\n",
        "b": 2 // another comment
    }
    """
    assert decode(json_with_comment) == {"a": "value with new line\n", "b": 2}


def test_decode_with_strict_true():
    # strict=True disables comment removal, so comments should cause an error
    json_with_comment = """
    {
        // comment
        "a": 1
    }
    """
    with pytest.raises(Exception):
        decode(json_with_comment, strict=True)


def test_decode_with_encoding_utf8():
    json_str = '{"a": "ü"}'
    # Should decode correctly with or without encoding specified
    assert decode(json_str, encoding="utf-8") == {"a": "ü"}


def test_decode_ignores_extra_kwargs():
    assert decode('{"a": 1}', foo="bar") == {"a": 1}


def test_decode_empty_object():
    assert decode("{}") == {}


def test_decode_array():
    assert decode("[1, 2, 3]") == [1, 2, 3]


def test_decode_with_nested_comments():
    json_with_comment = """
    {
        /* outer comment
        // inner single-line
        still in comment */
        "a": 1
    }
    """
    assert decode(json_with_comment) == {"a": 1}


def test_encode_simple_object():
    obj = {"a": 1, "b": 2}
    result = encode(obj)
    # Compact encoding, keys order may vary
    assert result.replace(" ", "") in ('{"a":1,"b":2}', '{"b":2,"a":1}')


def test_encode_pretty_printed():
    obj = {"a": 1, "b": 2}
    result = encode(obj, compactly=False)
    # Should contain newlines and indentation
    assert "\n" in result and "  " in result
    assert '"a": 1' in result or '"b": 2' in result


def test_encode_escape_unicode_true():
    obj = {"a": "ü"}
    result = encode(obj, escape_unicode=True)
    assert r"\u00fc" in result


def test_encode_escape_unicode_false():
    obj = {"a": "ü"}
    result = encode(obj, escape_unicode=False)
    assert "ü" in result


def test_encode_with_encoding_utf8():
    obj = {"a": "ü"}
    result = encode(obj, encoding="utf-8")
    # Should be a str containing the unicode character or its escape
    assert isinstance(result, str)
    assert "ü" in result or r"\u00fc" in result


def test_encode_compactly_true_and_false():
    obj = {"a": 1, "b": 2}
    compact = encode(obj, compactly=True)
    pretty = encode(obj, compactly=False)
    assert len(compact) < len(pretty)


def test_encode_array():
    arr = [1, 2, 3]
    result = encode(arr)
    assert result == "[1,2,3]"


def test_encode_nested_object():
    obj = {"a": {"b": [1, 2, 3]}, "c": "test"}
    result = encode(obj)
    assert '"b":[1,2,3]' in result.replace(" ", "")
    assert '"c":"test"' in result.replace(" ", "")


def test_encode_ignores_strict():
    obj = {"a": 1}
    result = encode(obj, strict=True)
    assert result.replace(" ", "") in ('{"a":1}',)


def test_encode_empty_object():
    assert encode({}) == "{}"


def test_encode_empty_array():
    assert encode([]) == "[]"
