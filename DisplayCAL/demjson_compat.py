"""demjson 1.3 compatibility module."""

from __future__ import annotations

import json
import sys
from io import StringIO
from typing import Any

DEBUG = False


def debug_print(*args: list, **kwargs: dict) -> None:
    """Print debug information if DEBUG is enabled."""
    if DEBUG:
        sys.stdout.write(*args, **kwargs)


def decode(txt: str, strict: bool = False, encoding: None | str = None, **kw) -> Any:  # noqa: ANN401
    """Decode a JSON-encoded string into a Python object.

    If 'strict' is set to True, then only strictly-conforming JSON
    output will be produced.  Note that this means that some types
    of values may not be convertible and will result in a
    JSONEncodeError exception.

    The input string can be either a python string or a python unicode
    string.  If it is already a unicode string, then it is assumed
    that no character set decoding is required.

    However, if you pass in a non-Unicode text string (i.e., a python
    type 'str') then an attempt will be made to auto-detect and decode
    the character encoding.  This will be successful if the input was
    encoded in any of UTF-8, UTF-16 (BE or LE), or UTF-32 (BE or LE),
    and of course plain ASCII works too.

    Note though that if you know the character encoding, then you
    should convert to a unicode string yourself, or pass it the name
    of the 'encoding' to avoid the guessing made by the auto
    detection, as with

        python_object = demjson.decode( input_bytes, encoding='utf8' )

    Optional keywords arguments are ignored.

    Args:
        txt (str): The JSON-encoded string to decode.
        strict (bool): If True, only strictly conforming JSON is accepted.
        encoding (str, optional): The character encoding of the input string.
            Defaults to None.
        **kw: Additional keyword arguments (ignored).

    Returns:
        Any: The decoded Python object.
    """
    if strict:
        return json.loads(txt, encoding=encoding, strict=strict)

    # Remove comments
    io = StringIO()
    escape = False
    prev = None
    expect_comment = False
    in_comment = False
    comment_multiline = False
    in_quote = False
    write = True
    for c in txt:
        debug_print(c)
        write = True
        (expect_comment, comment_multiline, in_comment, in_quote, escape, write) = (
            process_character(
                c, prev, expect_comment, comment_multiline, in_comment, in_quote, escape
            )
        )
        if write and not expect_comment and not in_comment:
            io.write(c)
        prev = c
    txt = io.getvalue()
    debug_print("\n")
    if DEBUG:
        print("JSON:", txt)

    return json.loads(txt, encoding=encoding, strict=strict)


def process_character(
    c: str,
    prev: str,
    expect_comment: bool,
    comment_multiline: bool,
    in_comment: bool,
    in_quote: bool,
    escape: bool,
) -> tuple[bool, bool, bool, bool, bool, bool]:
    """Process a character in the JSON string for comment handling.

    Args:
        c (str): The current character being processed.
        prev (str): The previous character processed.
        expect_comment (bool): Whether a comment is expected.
        comment_multiline (bool): Whether the comment is multiline.
        in_comment (bool): Current status of being inside a comment.
        in_quote (bool): Current status of being inside a quote.
        escape (bool): Whether the current character is escaped.

    Returns:
        tuple[bool, bool, bool, bool, bool, bool]: Updated status of whether a
            comment is expected, whether currently in a comment, whether the
            comment is multiline, whether currently in a quote, whether the
            current character is escaped, and whether to write the character to
            output.
    """
    if c == "\\":
        debug_print("<ESCAPE>")
        escape = True
    elif escape:
        debug_print("</ESCAPE>")
        escape = False
    else:
        if not in_quote:
            if c == "/":
                (expect_comment, in_comment, comment_multiline, write) = (
                    handle_forward_slash_char(
                        prev, expect_comment, in_comment, comment_multiline
                    )
                )
            elif c == "*":
                (expect_comment, in_comment, comment_multiline) = (
                    handle_multiline_comment(expect_comment)
                )
            elif expect_comment:
                debug_print("</EXPECT_COMMENT>")
                expect_comment = False
        if c == "\n":
            in_comment, write = handle_newline_char(
                in_comment, comment_multiline, write
            )
        elif c == '"' and not in_comment:
            in_quote = handle_quote_status(in_quote)
    return (expect_comment, comment_multiline, in_comment, in_quote, escape, write)


def handle_forward_slash_char(
    prev: str,
    expect_comment: bool,
    in_comment: bool,
    comment_multiline: bool,
) -> tuple[bool, bool, bool, bool]:
    """Handle the forward slash character in comment processing.

    Args:
        prev (str): The previous character processed.
        expect_comment (bool): Whether a comment is expected.
        in_comment (bool): Current status of being inside a comment.
        comment_multiline (bool): Whether the comment is multiline.

    Returns:
        tuple[bool, bool, bool, bool]: Updated status of being inside a comment,
            whether a multiline comment is expected, and whether to write the
            character to output.
    """
    if expect_comment:
        debug_print("<COMMENT>")
        in_comment = True
        comment_multiline = False
        expect_comment = False
    elif in_comment and prev == "*":
        debug_print("</MULTILINECOMMENT>")
        in_comment = False
        comment_multiline = False
        write = False
    elif not in_comment:
        debug_print("<EXPECT_COMMENT>")
        expect_comment = True
    return expect_comment, in_comment, comment_multiline, write


def handle_multiline_comment(expect_comment: bool) -> tuple[bool, bool, bool]:
    """Handle the start of a multiline comment.

    Args:
        expect_comment (bool): Whether a comment is expected.

    Returns:
        tuple[bool, bool, bool]: Updated status of whether a comment is expected,
            whether currently in a comment, and whether the comment is multiline.
    """
    if expect_comment:
        debug_print("<MULTILINECOMMENT>")
        in_comment = True
        comment_multiline = True
        expect_comment = False
    return expect_comment, in_comment, comment_multiline


def handle_newline_char(
    in_comment: bool, comment_multiline: bool, write: bool
) -> tuple[bool, bool]:
    """Handle newline character in comment processing.

    Args:
        in_comment (bool): Current status of being inside a comment.
        comment_multiline (bool): Whether the comment is multiline.
        write (bool): Whether to write the character to output.

    Returns:
        tuple[bool, bool]: Updated status of being inside a comment and whether
            to write.
    """
    if in_comment and not comment_multiline:
        debug_print("</COMMENT>")
        in_comment = False
        write = False
    return in_comment, write


def handle_quote_status(in_quote: bool) -> bool:
    """Toggle the in_quote status and print debug information.

    Args:
        in_quote (bool): Current status of being inside a quote.

    Returns:
        bool: New status of being inside a quote.
    """
    if in_quote:
        debug_print("</QUOTE>")
        in_quote = False
    else:
        debug_print("<QUOTE>")
        in_quote = True
    return in_quote


def encode(
    obj: Any,  # noqa: ANN401
    strict: bool = False,
    compactly: bool = True,
    escape_unicode: bool = False,
    encoding: None | str = None,
) -> str:
    """Encode a Python object into a JSON-encoded string.

    'strict' is ignored.

    If 'compactly' is set to True, then the resulting string will
    have all extraneous white space removed; if False then the
    string will be "pretty printed" with whitespace and indentation
    added to make it more readable.

    If 'escape_unicode' is set to True, then all non-ASCII characters
    will be represented as a unicode escape sequence; if False then
    the actual real unicode character will be inserted.

    If no encoding is specified (encoding=None) then the output will
    either be a Python string (if entirely ASCII) or a Python unicode
    string type.

    However if an encoding name is given then the returned value will
    be a python string which is the byte sequence encoding the JSON
    value.  As the default/recommended encoding for JSON is UTF-8,
    you should almost always pass in encoding='utf8'.

    Args:
        obj (Any): The Python object to encode.
        strict (bool): Ignored, for compatibility.
        compactly (bool): If True, the output will be compact; if False, it
            will be pretty-printed with indentation.
        escape_unicode (bool): If True, non-ASCII characters will be escaped;
            if False, they will be included as actual characters.
        encoding (str, optional): The character encoding for the output string.
            Defaults to None.

    Returns:
        str: The JSON-encoded string.
    """
    if compactly:
        indent = None
        separators = (",", ":")
    else:
        indent = 2
        separators = (",", ": ")

    ensure_ascii = escape_unicode or encoding is not None

    return json.dumps(
        obj,
        ensure_ascii=ensure_ascii,
        indent=indent,
        separators=separators,
        encoding=encoding or "utf-8",
    )
