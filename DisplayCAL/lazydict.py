"""Lazy-loading dictionaries that defer loading from files (JSON/YAML) until accessed."""  # noqa: E501

from __future__ import annotations

import codecs
import json
import os
from typing import TYPE_CHECKING, Any, TextIO

from DisplayCAL.config import get_data_path
from DisplayCAL.debughelpers import handle_error
from DisplayCAL.util_str import safe_str

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


def unquote(string: str, raise_exception: bool = True) -> str:
    """Remove outer single/double quotes and unescape YAML-style escapes.

    Unlike 'string'.strip("'"'"'), only removes the outermost quote pair.
    Raises ValueError on missing end quote if there is a start quote.

    Args:
        string (str): The string to unquote.
        raise_exception (bool, optional): If True, raises a ValueError if the
            string is not properly quoted. Defaults to True.

    Returns:
        str: The unquoted string.
    """
    if len(string) > 1 and string[0] in "'\"":
        if string[-1] == string[0]:
            # NOTE: Order of unescapes is important to match YAML!
            string = unescape(string[1:-1])

        elif raise_exception:
            raise ValueError("Missing end quote while scanning quoted scalar")
    return string


def escape(string: str) -> bytes:
    """Backslash-escape special chars in string."""
    if isinstance(string, str):
        string = string.encode("string_escape")
    return string


def unescape(string: bytes) -> str:
    """Unescape escaped chars in string."""
    if isinstance(string, bytes):
        string = string.decode("string_escape")
    return string


class LazyDict(dict):
    """Lazy dictionary with key -> value mappings.

    The actual mappings are loaded from the source YAML file when they
    are accessed.

    Args:
        path (None | str, optional): The path to the file to load the
            dictionary from. If not provided, the path set during
            initialization will be used.
        encoding (str, optional): The encoding to use when reading the file.
            Defaults to "UTF-8".
        errors (str, optional): The error handling scheme to use for decoding.
            Defaults to "strict".
    """

    def __init__(
        self,
        path: None | str = None,
        encoding: str = "UTF-8",
        errors: str = "strict",
    ) -> None:
        super().__init__()
        self._is_loaded = False
        self.path = path
        self.encoding = encoding
        self.errors = errors

    def __cmp__(self, other: Any) -> bool:  # noqa: ANN401
        """Compare the dictionary with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if the dictionary is equal to the other object,
                False otherwise.
        """
        self.load()
        return super().__cmp__(other)

    def __contains__(self, key: Any) -> bool:  # noqa: ANN401
        """Check if the dictionary contains a key.

        Args:
            key (Any): The key to check. Any hashable object.

        Returns:
            bool: True if the key is in the dictionary, False otherwise.
        """
        self.load()
        return super().__contains__(key)

    def __delitem__(self, key: Any) -> None:  # noqa: ANN401
        """Delete a key from the dictionary.

        Args:
            key (Any): The key to delete. Any hashable object.
        """
        self.load()
        super().__delitem__(key)

    def __eq__(self, other: object) -> bool:
        """Compare the dictionary with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if the dictionary is equal to the other object,
                False otherwise.
        """
        self.load()
        return super().__eq__(other)

    def __ge__(self, other: Any) -> bool:  # noqa: ANN401
        """Compare the dictionary with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if the dictionary is greater than or equal to the
                other object, False otherwise.
        """
        self.load()
        return super().__ge__(other)

    def __getitem__(self, name: str) -> Any:  # noqa: ANN401
        """Get the value for a given key in the dictionary.

        Args:
            name (str): The key to get the value for.

        Returns:
            Any: The value associated with the key.
        """
        self.load()
        return super().__getitem__(name)

    def __gt__(self, other: Any) -> bool:  # noqa: ANN401
        """Compare the dictionary with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if the dictionary is greater than the other object,
                False otherwise.
        """
        self.load()
        return super().__gt__(other)

    def __iter__(self) -> Iterator:
        """Return an iterator over the dictionary keys.

        Returns:
            Iterator: An iterator over the dictionary keys.
        """
        self.load()
        return super().__iter__()

    def __le__(self, other: Any) -> bool:  # noqa: ANN401
        """Compare the dictionary with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if the dictionary is less than or equal to the other
                object, False otherwise.
        """
        self.load()
        return super().__le__(other)

    def __len__(self) -> int:
        """Return the number of items in the dictionary.

        Returns:
            int: The number of items in the dictionary.
        """
        self.load()
        return super().__len__()

    def __lt__(self, other: Any) -> bool:  # noqa: ANN401
        """Compare the dictionary with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if the dictionary is less than the other object,
                False otherwise.
        """
        self.load()
        return super().__lt__(other)

    def __ne__(self, other: object) -> bool:
        """Compare the dictionary with another object.

        Args:
            other (Any): The object to compare with.

        Returns:
            bool: True if the dictionary is not equal to the other object,
                False otherwise.
        """
        self.load()
        return super().__ne__(other)

    def __repr__(self) -> str:
        """Return a string representation of the dictionary.

        Returns:
            str: A string representation of the dictionary.
        """
        self.load()
        return super().__repr__()

    def __setitem__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Set the value for a given key in the dictionary.

        Args:
            name (str): The key to set.
            value (Any): The value to set for the key.
        """
        self.load()
        super().__setitem__(name, value)

    def __sizeof__(self) -> int:
        """Return the size of the dictionary in bytes.

        Returns:
            int: The size of the dictionary in bytes.
        """
        self.load()
        return super().__sizeof__()

    def clear(self) -> None:
        """Clear the dictionary."""
        if not self._is_loaded:
            self._is_loaded = True
        super().clear()

    def copy(self) -> dict:
        """Return a shallow copy of the dictionary.

        Returns:
            dict: A shallow copy of the dictionary.
        """
        self.load()
        return super().copy()

    def get(self, name: str, fallback: None | Any = None) -> Any:  # noqa: ANN401
        """Get the value for a given key in the dictionary.

        Args:
            name (str): The key to get the value for.
            fallback (Any, optional): The value to return if the key does not
                exist. Defaults to None.

        Returns:
            Any: The value associated with the key, or the fallback value if
                the key does not exist.
        """
        self.load()
        return super().get(name, fallback)

    def items(self) -> tuple[str, Any]:
        """Return a tuple containing the dictionary's items.

        Returns:
            tuple[str, Any]: The dictionary's items, where each item is a tuple
                of (key, value).
        """
        self.load()
        return super().items()

    def iteritems(self) -> Iterator:
        """Return an iterator over the dictionary's items.

        Returns:
            Iterator: An iterator over the dictionary's items, where each item
                is a tuple of (key, value).
        """
        self.load()
        return super().items()

    def iterkeys(self) -> Iterator:
        """Return an iterator over the dictionary's keys.

        Returns:
            Iterator: An iterator over the dictionary's keys.
        """
        self.load()
        return super().keys()

    def itervalues(self) -> Iterator:
        """Return an iterator over the dictionary's values.

        Returns:
            Iterator: An iterator over the dictionary's values.
        """
        self.load()
        return super().values()

    def keys(self) -> Any:  # noqa: ANN401
        """Return a view of the dictionary's keys.

        Returns:
            dict_keys: A view of the dictionary's keys.
        """
        self.load()
        return super().keys()

    def load(
        self,
        path: None | str = None,
        encoding: None | str = None,
        errors: None | str = None,
        raise_exceptions: bool = False,
    ) -> None:
        """Load the dictionary from a file.

        Args:
            path (str, optional): The path to the file to load the dictionary
                from. If not provided, the path set during initialization will
                be used.
            encoding (str, optional): The encoding to use when reading the
                file. Defaults to "UTF-8".
            errors (str, optional): The error handling scheme to use for
                decoding. Defaults to "strict".
            raise_exceptions (bool, optional): If True, exceptions will be
                raised instead of handled. Defaults to False.

        Raises:
            UserWarning: If the file is not found or if there is an error
                parsing the file, a UserWarning will be raised.
            OSError: If there is an OS error while opening the file and
                raise_exceptions is True.
            Exception: If there is an error parsing the file and
                raise_exceptions is True.
        """
        if self._is_loaded or (not path and not self.path):
            return

        self._is_loaded = True
        if not path:
            path = self.path
        if path and not os.path.isabs(path):
            path = get_data_path(path)
        if path and os.path.isfile(path):
            self.path = path
            if encoding:
                self.encoding = encoding
            if errors:
                self.errors = errors
        else:
            handle_error(UserWarning(f"Warning - file not found:\n\n{path}"), tb=False)
            return
        try:
            with open(path, "r", encoding=self.encoding, errors=self.errors) as f:
                self.parse(f)
        except OSError as exception:
            if raise_exceptions:
                raise
            handle_error(exception)
        except Exception as exception:
            if raise_exceptions:
                raise
            handle_error(
                UserWarning(f"Error parsing file:\n\n{path}\n\n{exception}"),
                tb=False,
            )

    def parse(self, iterable: Iterable[tuple[str, Any]]) -> None:
        """Parse the iterable and update the dictionary.

        Args:
            iterable (Iterable[tuple[str, Any]]): An iterable object (e.g.,
                file object) to parse and update the dictionary with.
        """
        # Override this in subclass

    def pop(self, key: str, *args) -> Any:  # noqa: ANN401
        """Remove a key from the dictionary and return its value.

        Args:
            key (str): The key to remove.
            *args: Optional arguments to pass to the pop method.

        Returns:
            Any: The value associated with the key that was removed.
        """
        self.load()
        return super().pop(key, *args)

    def popitem(self, name: str, value: Any) -> tuple[str, Any]:  # noqa: ANN401
        """Remove and return a (key, value) pair from the dictionary.

        Args:
            name (str): The key to remove.
            value (Any): The value to return if the key does not exist.

        Returns:
            tuple: The (key, value) pair removed from the dictionary.
        """
        self.load()
        return super().popitem(name, value)

    def setdefault(self, name: str, value: None | Any = None) -> Any:  # noqa: ANN401
        """Set the default value for a key in the dictionary.

        Args:
            name (str): The key to set the default value for.
            value (Any, optional): The default value to set if the key does
                not exist. Defaults to None.

        Returns:
            Any: The value associated with the key after setting the default.
        """
        self.load()
        return super().setdefault(name, value)

    def update(self, other: dict | Iterable[tuple[str, Any]]) -> None:
        """Update the dictionary with another dictionary or iterable of key-value pairs.

        Args:
            other (dict | Iterable[tuple[str, Any]]): The dictionary or
                iterable of key-value pairs to update the dictionary with.
        """
        self.load()
        super().update(other)

    def values(self) -> Any:  # noqa: ANN401
        """Return a view of the dictionary's values.

        Returns:
            dict_values: A view of the dictionary's values.
        """
        self.load()
        return super().values()


class LazyDictJSON(LazyDict):
    """JSON lazy dictionary."""

    def parse(self, fileobj: TextIO) -> None:
        """Parse fileobj and update dict."""
        super().update(json.load(fileobj))


class LazyDictYAMLUltraLite(LazyDict):
    """'YAML Ultra Lite' lazy dictionary.

    YAML Ultra Lite is a restricted subset of YAML. It only supports the
    following notations:

    Key: Value 1
    "Key 2": "Value 2"
    "Key 3": |-
      Value 3 Line 1
      Value 3 Line 2

    All values are treated as strings.

    Syntax checking is limited for speed.
    Parsing is around a factor of 20 to 30 faster than PyYAML,
    around 8 times faster than JSONDict (based on demjson),
    and about 2 times faster than YAML_Lite.

    Args:
        path (None | str, optional): The path to the file to load the
            dictionary from. If not provided, the path set during
            initialization will be used.
        encoding (str, optional): The encoding to use when reading the file.
            Defaults to "UTF-8".
        errors (str, optional): The error handling scheme to use for decoding.
            Defaults to "strict".
        debug (bool, optional): If True, debug output will be printed during
            parsing. Defaults to False.
    """

    def __init__(
        self,
        path: None | str = None,
        encoding: str = "UTF-8",
        errors: str = "strict",
        debug: bool = False,
    ) -> None:
        super().__init__(path, encoding, errors)
        self.debug = debug

    def debug_print(self, *args: Any) -> None:  # noqa: ANN401
        """Print debug information if debugging is enabled.

        Args:
            *args (Any): The arguments to print.
        """
        if self.debug:
            print(*args)

    def parse(self, fileobj: TextIO) -> None:
        """Parse fileobj and update dict.

        Args:
            fileobj (TextIO): The file-like object to parse.
        """
        block = False
        value = []
        key = None
        # Readlines is actually MUCH faster than iterating over the
        # file object
        for i, line in enumerate(fileobj.readlines(), 1):
            line = line.replace("\r\n", "\n")
            if line.lstrip(" ").startswith("#"):
                # Ignore comments
                pass
            elif line != "\n" and not line.startswith("  "):
                block, value, key = self._parse_line(line, value, key, fileobj, i)
            else:
                if not block:
                    raise ValueError(
                        "Unsupported format ({!r} line {})".format(
                            safe_str(getattr(fileobj, "name", line)), i
                        )
                    )
                value.append(line[2:])
        if key:
            self[key] = "".join(value).rstrip("\n")

    def _parse_line(
        self, line: str, value: list, key: str, fileobj: TextIO, i: int
    ) -> tuple[bool, list, str]:
        """Parse a single line of the file and update the dictionary.

        Args:
            line (str): The line to parse.
            value (list): The current value being built.
            key (str): The current key being built.
            fileobj (TextIO): The file-like object being parsed.
            i (int): The current line number.

        Raises:
            ValueError: If the line is not in the expected format.

        Returns:
            tuple: A tuple containing:
                - block (bool): Whether the line is a block style.
                - value (list): The value parsed from the line.
                - key (str): The key parsed from the line.
        """
        if value:
            self[key] = "".join(value).rstrip("\n")
        # tokens = line.rstrip(' -|\n').split(":", 1)
        tokens = line.split(":", 1)
        if len(tokens) == 1:
            raise ValueError(
                "Unsupported format ({!r} line {})".format(
                    safe_str(getattr(fileobj, "name", line)), i
                )
            )
        # key = tokens[0].strip("'"'"')
        key = self._unquote(tokens[0].strip(), False, False, fileobj, i)
        token = tokens[1].strip(" \n")
        if token.startswith("|-"):
            block = True
            token = token[2:].lstrip(" ")
            if token:
                if token.startswith("#"):
                    value = []
                    return block, value, key
                raise ValueError(
                    "Expected a comment or a line break ({} line {})".format(
                        format(safe_str(getattr(fileobj, "name", line))), i
                    )
                )
        elif token.startswith(("|", ">")):
            raise ValueError(
                "Style not supported ({!r} line {})".format(
                    safe_str(getattr(fileobj, "name", line)), i
                )
            )
        elif token.startswith("\t"):
            raise ValueError(
                "Found character '\\t' that cannot "
                "start any token ({!r} line {})".format(
                    safe_str(getattr(fileobj, "name", line)), i
                )
            )
        if token:
            # Inline value
            block = False
            if token.startswith("#"):
                value = []
                return block, value, key
            comment_offset = token.find("#")
            if (
                comment_offset > -1
                and token[comment_offset - 1 : comment_offset] == " "
            ):
                token = token[:comment_offset].rstrip(" \n")
                if not token:
                    value = []
                    return block, value, key
            # value = [token.strip("'"'"')]
            value = [self._unquote(token, True, True, fileobj, i)]
        else:
            value = []

        return block, value, key

    def _unquote(
        self,
        token: str,
        do_unescape: bool = True,
        check: bool = False,
        fileobj: None | TextIO = None,
        lineno: int = -1,
    ) -> str:
        """Unquote a token, removing outer quotes and unescaping YAML-style escapes.

        Args:
            token (str): The token to unquote.
            do_unescape (bool, optional): If True, unescape the token. Defaults
                to True.
            check (bool, optional): If True, perform additional checks on the
                token. Defaults to False.
            fileobj (TextIO, optional): The file-like object to use for error
                reporting. Defaults to None.
            lineno (int, optional): The line number for error reporting.
                Defaults to -1

        Returns:
            str: The unquoted token.
        """
        if len(token) <= 1:
            return token
        c = token[0]
        if c in "'\"" and c == token[-1]:
            token = token[1:-1]
            if check and token.count(c) != token.count("\\" + c):
                raise ValueError(
                    "Unescaped quotes found in token ({!r} line {})".format(
                        safe_str(getattr(fileobj, "name", token)), lineno
                    )
                )
            if do_unescape:
                token = unescape(token)
        elif check and (token.count('"') != token.count('\\"')):
            raise ValueError(
                "Unbalanced quotes found in token ({!r} line {})".format(
                    safe_str(getattr(fileobj, "name", token)), lineno
                )
            )
        if check and "\\'" in token:
            raise ValueError(
                'Found unknown escape character "\'" ({!r} line {})'.format(
                    safe_str(getattr(fileobj, "name", token)), lineno
                )
            )
        return token


class LazyDictYAMLLite(LazyDictYAMLUltraLite):
    """'YAML Lite' lazy dictionary.

    YAML Lite is a restricted subset of YAML. It only supports the
    following notations:

    Key: Value 1
    "Key 2": "Value 2"
    "Key 3": |-
      Value 3 Line 1
      Value 3 Line 2
    "Key 4": |
      Value 4 Line 1
      Value 4 Line 2
    "Key 5": Folded value 5
      Folded value 5, continued

    All values are treated as strings.

    Syntax checking is limited for speed.
    Parsing is around a factor of 12 to 16 faster than PyYAML,
    and around 4 times faster than JSONDict (based on demjson).

    """

    def parse(self, fileobj: TextIO) -> None:
        """Parse fileobj and update dict.

        Args:
            fileobj (TextIO): The file-like object to parse.
        """
        style = None
        value = []
        block_styles = ("|", ">", "|-", ">-", "|+", ">+")
        quote = None
        key = None
        # Readlines is actually MUCH faster than iterating over the
        # file object
        for i, line in enumerate(fileobj.readlines(), 1):
            line = line.replace("\r\n", "\n")
            line_lwstrip = line.lstrip(" ")
            line_rstrip = line.rstrip() if quote else None
            self.debug_print("LINE", repr(line))
            if not quote and style not in block_styles and line_lwstrip.startswith("#"):
                # Ignore comments
                pass
            elif quote and line_rstrip and line_rstrip[-1] == quote:
                self.debug_print("END QUOTE")
                self.debug_print("+ APPEND STRIPPED", repr(line.strip()))
                value.append(line.strip())
                self._collect(key, value, ">i")
                style = None
                value = []
                quote = None
                key = None
            elif (
                style not in block_styles
                and line.startswith(" ")
                and line_lwstrip
                and line_lwstrip[0] in ("'", '"')
            ):
                self.validate_quote(quote, line, fileobj, i)
                self.debug_print("START QUOTE")
                quote = line_lwstrip[0]
                self.debug_print("+ APPEND LWSTRIPPED", repr(line_lwstrip))
                value.append(line_lwstrip)
            elif line.startswith("  ") and (
                style in block_styles or line_lwstrip != "\n"
            ):
                if style == ">i":
                    if not quote and "\t" in line:
                        raise ValueError(
                            "Found character '\\t' that cannot "
                            "start any token ({!r} line {})".format(
                                safe_str(getattr(fileobj, "name", line)), i
                            )
                        )
                    line = line.strip() + "\n"
                    self.debug_print("APPEND STRIPPED + \\n", repr(line))
                else:
                    line = line[2:]
                    self.debug_print("APPEND [2:]", repr(line))
                value.append(line)
            elif not quote and line_lwstrip != "\n" and not line.startswith(" "):
                style, value, key, quote, skip_to_next_line = self._parse_line(
                    line, key, value, style, quote, fileobj, i
                )
                if skip_to_next_line:
                    continue
            else:
                # if line_lwstrip == "\n":
                self.debug_print("APPEND LWSTRIPPED", repr(line_lwstrip))
                line = line_lwstrip
                value.append(line)
        if quote:
            raise ValueError(
                "EOF while scanning quoted scalar ({!r} line {})".format(
                    safe_str(getattr(fileobj, "name", line)), i
                )
            )
        if key:
            self.debug_print("FINAL COLLECT")
            self._collect(key, value, style)

    def validate_quote(
        self, quote: None | str, line: str, fileobj: TextIO, i: int
    ) -> None:
        """Validate the quote character to ensure it is properly closed.

        Args:
            quote (None | str): The current quote character, if any.
            line (str): The line being parsed.
            fileobj (TextIO): The file-like object being parsed.
            i (int): The current line number.

        Raises:
            ValueError: If the quote character is not properly closed.
        """
        if quote:
            raise ValueError(
                "Wrong end quote while scanning quoted scalar ({!r} line {})".format(
                    safe_str(getattr(fileobj, "name", line)), i
                )
            )

    def _parse_line(
        self,
        line: str,
        key: str,
        value: list,
        style: None | str,
        quote: None | str,
        fileobj: TextIO,
        i: int,
    ) -> tuple[None | str, list, str, None | str, bool]:
        """Parse a single line of the file and update the dictionary.

        Args:
            line (str): The line to parse.
            key (str): The current key being built.
            value (list): The current value being built.
            style (None | str): The current style of the value.
            quote (None | str): The current quote character, if any.
            fileobj (TextIO): The file-like object being parsed.
            i (int): The current line number.

        Raises:
            ValueError: If the line is not in the expected format.
            NotImplementedError: If a folded style is encountered.

        Returns:
            tuple: A tuple containing:
                - style (None | str): The style of the value.
                - value (list): The value parsed from the line.
                - key (str): The key parsed from the line.
                - quote (None | str): The quote character, if any.
                - skip_to_next_line (bool): Whether to skip to the next line.
        """
        if key and value:
            self._collect(key, value, style)
        tokens = line.split(":", 1)
        key = unquote(tokens[0].strip())
        if len(tokens) > 1:
            token = tokens[1].lstrip(" ").rstrip(" \n")
            if token.startswith(("|", ">")):
                if token[1:2] in "+-":
                    style = token[:2]
                    token = token[2:].lstrip(" ")
                else:
                    style = token[:1]
                    token = token[1:].lstrip(" ")
            else:
                style = ""
            self.validate_token(token, line, fileobj, i)
            self.validate_style(style, line, fileobj, i)
            if token.startswith("#"):
                # Block or folded
                self.debug_print("IN BLOCK", repr(key), style)
                value = []
                return style, value, key, quote, True
            if style and token:
                raise ValueError(
                    "Expected a comment or a line break ({!r} line {})".format(
                        safe_str(getattr(fileobj, "name", line)), i
                    )
                )
        else:
            raise ValueError(
                "Unsupported format ({!r} line {})".format(
                    safe_str(getattr(fileobj, "name", line)), i
                )
            )
        if style or not token:
            # Block or folded
            self.debug_print("IN BLOCK", repr(key), style)
            value = []
        else:
            # Inline value
            self.debug_print("IN PLAIN", repr(key), repr(token))
            style = None
            if token.startswith("#"):
                value = []
                return style, value, key, quote, True
            token_rstrip = token.rstrip()
            if (
                token_rstrip
                and token_rstrip[0] in ("'", '"')
                and (len(token_rstrip) < 2 or token_rstrip[0] != token_rstrip[-1])
            ):
                self.debug_print("START QUOTE")
                quote = token_rstrip[0]
            else:
                style = ">i"
                comment_offset = token_rstrip.find("#")
                if (
                    comment_offset > -1
                    and token_rstrip[comment_offset - 1 : comment_offset] == " "
                ):
                    token_rstrip = token_rstrip[:comment_offset].rstrip()
            token_rstrip += "\n"
            self.debug_print("SET", repr(token_rstrip))
            value = [token_rstrip]

        return style, value, key, quote, False

    def validate_token(self, token: str, line: str, fileobj: TextIO, i: int) -> None:
        """Validate the token to ensure it starts with a valid character.

        Args:
            token (str): The token to validate.
            line (str): The line containing the token.
            fileobj (TextIO): The file-like object being parsed.
            i (int): The current line number.

        Raises:
            ValueError: If the token starts with a tab character.
        """
        if token.startswith("\t"):
            raise ValueError(
                "Found character '\\t' that cannot "
                "start any token ({!r} line {})".format(
                    safe_str(getattr(fileobj, "name", line)), i
                )
            )

    def validate_style(
        self, style: None | str, line: str, fileobj: TextIO, i: int
    ) -> None:
        """Validate the style to ensure it is supported.

        Args:
            style (None | str): The style to validate.
            line (str): The line containing the style.
            fileobj (TextIO): The file-like object being parsed.
            i (int): The current line number.

        Raises:
            NotImplementedError: If the style is a folded style (starts with
                '>').
        """
        if style.startswith(">"):
            raise NotImplementedError(
                "Folded style is not supported ({!r} line {})".format(
                    safe_str(getattr(fileobj, "name", line)), i
                )
            )

    def _collect(self, key: str, value: list, style: None | str = None) -> None:
        """Collect the key and value, formatting the value according to style.

        Args:
            key (str): The key to collect.
            value (list): The value to collect, as a list of strings.
            style (None | str, optional): The style to apply to the value.
                Defaults to None.
        """
        self.debug_print("COLLECT", key, value, style)
        chars = "".join(value)
        chars = chars.rstrip(" ") if style != ">i" else chars
        if not style or style.startswith(">"):
            self.debug_print("FOLD")
            out = ""
            state = 0
            for c in chars:
                # print(repr(c), repr(state))
                if c == "\n":
                    if state > 0:
                        out += c
                    state += 1
                else:
                    if state == 1:
                        out += " "
                        state = 0
                    if style == ">i":
                        state = 0
                    out += c
        else:
            out = chars
        out = out.lstrip(" ")
        self.debug_print("OUT", repr(out))
        if not style:
            # Inline value
            out = out.rstrip()
        elif style.endswith("+"):
            # Keep trailing newlines
            self.debug_print("KEEP")
        else:
            out = out.rstrip("\n")
            if style == ">i":
                out = unquote(out)
            elif style.endswith("-"):
                # Chomp trailing newlines
                self.debug_print("CHOMP")
            else:
                # Clip trailing newlines (default)
                self.debug_print("CLIP")
                if chars.endswith("\n"):
                    out += "\n"
        self[key] = out
