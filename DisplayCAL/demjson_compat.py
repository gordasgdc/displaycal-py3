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
        return json.loads(txt, strict=strict)

    dem_json_preprocessor = DEMJSONPreprocessor()
    txt = dem_json_preprocessor.process(txt)

    return json.loads(txt)


class DEMJSONPreprocessor:
    """A JSON preprocessor that is compatible with demjson 1.3."""

    def __init__(self) -> None:
        self.prev = None
        self.escape = False
        self.expect_comment = False
        self.in_comment = False
        self.comment_multiline = False
        self.in_quote = False
        self.write = True

    def process(self, txt: str) -> Any:  # noqa: ANN401
        """Process the input JSON string to remove comments.

        Args:
            txt (str): The JSON string to process.

        Returns:
            str: The processed JSON string with comments removed.
        """
        # Remove comments
        io = StringIO()
        for c in txt:
            debug_print(c)
            self.write = True
            self.process_character(c)
            if self.write and not self.expect_comment and not self.in_comment:
                io.write(c)
            self.prev = c
        txt = io.getvalue()
        debug_print("\n")
        if DEBUG:
            print("JSON:", txt)

        return txt

    def process_character(self, c: str) -> None:
        """Process a character in the JSON string for comment handling.

        Args:
            c (str): The current character being processed.
        """
        if c == "\\":
            debug_print("<ESCAPE>")
            self.escape = True
        elif self.escape:
            debug_print("</ESCAPE>")
            self.escape = False
        else:
            if not self.in_quote:
                if c == "/":
                    self.handle_forward_slash_char()
                elif c == "*":
                    self.handle_multiline_comment()
                elif self.expect_comment:
                    debug_print("</EXPECT_COMMENT>")
                    self.expect_comment = False
            if c == "\n":
                self.handle_newline_char()
            elif c == '"' and not self.in_comment:
                self.handle_quote_status()

    def handle_forward_slash_char(self) -> None:
        """Handle the forward slash character in comment processing."""
        if self.expect_comment:
            debug_print("<COMMENT>")
            self.in_comment = True
            self.comment_multiline = False
            self.expect_comment = False
        elif self.in_comment and self.prev == "*":
            debug_print("</MULTILINECOMMENT>")
            self.in_comment = False
            self.comment_multiline = False
            self.write = False
        elif not self.in_comment:
            debug_print("<EXPECT_COMMENT>")
            self.expect_comment = True

    def handle_multiline_comment(self) -> None:
        """Handle the start of a multiline comment."""
        if self.expect_comment:
            debug_print("<MULTILINECOMMENT>")
            self.in_comment = True
            self.comment_multiline = True
            self.expect_comment = False

    def handle_newline_char(self) -> None:
        """Handle newline character in comment processing."""
        if self.in_comment and not self.comment_multiline:
            debug_print("</COMMENT>")
            self.in_comment = False
            self.write = False

    def handle_quote_status(self) -> None:
        """Toggle the in_quote status and print debug information."""
        if self.in_quote:
            debug_print("</QUOTE>")
            self.in_quote = False
        else:
            debug_print("<QUOTE>")
            self.in_quote = True


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
    )
