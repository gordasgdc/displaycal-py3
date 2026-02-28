"""Compress and obfuscate JavaScript code.

It includes classes and methods for parsing, encoding, and packing JavaScript
scripts to reduce their size and improve performance.

  ParseMaster, version 1.0 (pre-release) (2005/05/12) x6
  Copyright 2005, Dean Edwards
  Web: http://dean.edwards.name/

  This software is licensed under the CC-GNU LGPL
  Web: http://creativecommons.org/licenses/LGPL/2.1/

  Ported to Python by Florian Schulze

"""

from __future__ import annotations

import functools
import re
from typing import Callable


class Pattern:
    """A multi-pattern parser.

    Args:
        expression (str): The regular expression pattern to match.
        replacement (str | Callable): The replacement string or function.
            If None, the pattern will be deleted.
        length (int): The number of sub-expressions in the pattern.
    """

    def __init__(
        self, expression: str, replacement: str | Callable, length: int
    ) -> None:
        self.expression = expression
        self.replacement = replacement
        self.length = length

    def __str__(self) -> str:
        """Return the string representation of the pattern.

        Returns:
            str: The string representation of the pattern.
        """
        return f"({self.expression})"


class Patterns(list):
    """A collection of patterns."""

    def __str__(self) -> str:
        """Return the string representation of the patterns.

        Returns:
            str: The string representation of the patterns.
        """
        return "|".join([str(e) for e in self])


class ParseMaster:
    """ParseMaster is a class for parsing and replacing patterns in strings."""

    # constants
    EXPRESSION = 0
    REPLACEMENT = 1
    LENGTH = 2
    GROUPS = re.compile(r"\(", re.M)  # g
    SUB_REPLACE = re.compile(r"\$\d", re.M)
    INDEXED = re.compile(r"^\$\d+$", re.M)
    TRIM = re.compile(r"""(['"])\1\+(.*)\+\1\1$""", re.M)
    ESCAPE = re.compile(r"\\.", re.M)  # g
    # QUOTE = re.compile(r"'", re.M)
    DELETED = re.compile(r"\x01[^\x01]*\x01", re.M)  # g

    def __init__(self) -> None:
        self._patterns = Patterns()  # patterns stored by index
        self._escaped = []
        self.ignoreCase = False
        self.escapeChar = None

    def delete(self, match: re.Match, offset: int) -> str:
        """Replacement function for deleting matched patterns.

        Args:
            match (re.Match): The match object containing the matched patterns.
            offset (int): The offset for the match groups.

        Returns:
            str: A string indicating that the matched pattern should be deleted.
        """
        return "\x01" + match.group(offset) + "\x01"

    def _repl(self, a: re.Match, o: int, r: str, i: int) -> str:
        """Replacement function for complex replacements.

        Args:
            a (re.Match): The match object containing the matched patterns.
            o (int): The offset for the match groups.
            r (str): The replacement string.
            i (int): The number of sub-expressions in the pattern.

        Returns:
            str: The processed replacement string with matched patterns
                replaced.
        """
        while i:
            m = a.group(o + i - 1)
            s = "" if m is None else m
            r = r.replace("$" + str(i), s)
            i = i - 1
        return ParseMaster.TRIM.sub("$1", r)

    def add(
        self, expression: str = "^$", replacement: None | str | Callable = None
    ) -> None:
        """Add a pattern to the parser.

        Args:
            expression (str, optional): The regular expression pattern to
                match.
            replacement (None | str | Callable, optional): The replacement
                string or function. If None, the pattern will be deleted.
        """
        if replacement is None:
            replacement = self.delete
        # count the number of sub-expressions
        #  - add one because each pattern is itself a sub-expression
        length = (
            len(ParseMaster.GROUPS.findall(self._internal_escape(str(expression)))) + 1
        )
        # does the pattern deal with sub-expressions?
        if isinstance(replacement, str) and ParseMaster.SUB_REPLACE.match(replacement):
            # a simple lookup? (e.g. "$2")
            if ParseMaster.INDEXED.match(replacement):
                # store the index (used for fast retrieval of matched strings)
                replacement = int(replacement[1:]) - 1
            else:  # a complicated lookup (e.g. "Hello $2 $1")
                # build a function to do the lookup
                i = length
                r = replacement

                def replacement(a: re.Match, o: int) -> str:
                    """Replacement function for complex replacements.

                    Args:
                        a (re.Match): The match object containing the matched
                            patterns.
                        o (int): The offset for the match groups.

                    Returns:
                        str: The processed replacement string.
                    """
                    return self._repl(a, o, r, i)

        # pass the modified arguments
        self._patterns.append(Pattern(expression, replacement, length))

    def execute(self, string: str) -> str:
        """Execute the global replacement on the given string.

        Args:
            string (str): The string to process.

        Returns:
            str: The processed string with patterns replaced.
        """
        if self.ignoreCase:
            r = re.compile(str(self._patterns), re.I | re.M)
        else:
            r = re.compile(str(self._patterns), re.M)
        string = self._escape(string, self.escapeChar)
        string = r.sub(self._replacement, string)
        string = self._unescape(string, self.escapeChar)
        string = ParseMaster.DELETED.sub("", string)
        return string  # noqa: RET504

    def reset(self) -> None:
        """Reset the patterns collection to an empty state.

        Clear the patterns collections so that this object may be re-used.
        """
        self._patterns = Patterns()

    def _replacement(self, match: re.Match) -> str:
        """Replace matched patterns with their corresponding replacements.

        This is the global replace function (it's quite complicated).

        Args:
            match (re.Match): The match object containing the matched patterns.

        Returns:
            str: The replacement string based on the matched patterns.
        """
        i = 1
        # loop through the patterns
        for pattern in self._patterns:
            if match.group(i) is not None:
                replacement = pattern.replacement
                if callable(replacement):
                    return replacement(match, i)
                if isinstance(replacement, int):
                    return match.group(replacement + i)
                return replacement
            i = i + pattern.length

        return None

    def _escape(self, string: str, escape_char: None | str = None) -> str:
        """Encode escaped characters.

        Args:
            string (str): The string to escape.
            escape_char (None | str, optional): The character used for escaping.
                Defaults to None.
        """

        def repl(match: re.Match) -> str:
            """Replacement function for escaping characters.

            Args:
                match (re.Match): The match object containing the matched
                    patterns.

            Returns:
                str: The escaped character or the escape character if no match
                    is found.
            """
            char = match.group(1)
            self._escaped.append(char)
            return escape_char

        if escape_char is None:
            return string

        r = re.compile(r"\\" + escape_char + r"(.)", re.M)
        return r.sub(repl, string)

    def _unescape(self, string: str, escape_char: None | str = None) -> str:
        """Decode escaped characters.

        Args:
            string (str): The string to unescape.
            escape_char (None | str, optional): The character used for
                escaping. Defaults to None.

        Returns:
            str: The unescaped string.
        """

        def repl(match: re.Match) -> str:
            """Replacement function for unescaping characters.

            Args:
                match (re.Match): The match object containing the matched
                    patterns.

            Returns:
                str: The unescaped character or the escape character if no
                    match is found.
            """
            try:
                # result = eval("'"+escapeChar + self._escaped.pop(0)+"'")
                return escape_char + self._escaped.pop(0)
            except IndexError:
                return escape_char

        if escape_char is None:
            return string
        r = re.compile(r"\\" + escape_char, re.M)
        return r.sub(repl, string)

    def _internal_escape(self, string: str) -> str:
        """Escape special characters in the string for internal processing.

        Args:
            string (str): The string to escape.

        Returns:
            str: The escaped string with special characters removed.
        """
        return ParseMaster.ESCAPE.sub("", string)


class JavaScriptPacker:
    """JavaScriptPacker is a class for compressing and obfuscating JavaScript code.

    packer, version 2.0 (2005/04/20)
    Copyright 2004-2005, Dean Edwards
    License: http://creativecommons.org/licenses/LGPL/2.1/

    Ported to Python by Florian Schulze

    http://dean.edwards.name/packer/

    """

    def basic_compression(self, script: str) -> str:
        """Get a ParseMaster to compress JavaScript code.

        Args:
            script (str): The JavaScript code to compress.

        Returns:
            str: The compressed JavaScript code without special character
                encoding.
        """
        return self.get_compression_parse_master(False, script)

    def special_compression(self, script: str) -> str:
        """Get a ParseMaster to compress JavaScript code with special characters.

        Args:
            script (str): The JavaScript code to compress.

        Returns:
            str: The compressed JavaScript code with special characters
                encoded.
        """
        return self.get_compression_parse_master(True, script)

    def get_compression_parse_master(self, special_chars: bool, script: str) -> str:
        """Get a ParseMaster instance for compressing JavaScript code.

        Args:
            special_chars (bool): Whether to include special character encoding.
            script (str): The JavaScript code to compress.

        Returns:
            str: The compressed JavaScript code.
        """
        ignore = "$1"
        parser = ParseMaster()
        parser.escapeChar = r"\\"
        # protect strings
        parser.add(r"""'[^'\n\r]*'""", ignore)
        parser.add(r'"[^"\n\r]*"', ignore)
        # remove comments
        parser.add(r"""//[^\n\r]*[\n\r]""")
        parser.add(r"""/\*[^*]*\*+([^/][^*]*\*+)*/""")
        # protect regular expressions
        parser.add(r"""\s+(\/[^\/\n\r\*][^\/\n\r]*\/g?i?)""", "$2")
        parser.add(r"""[^\w\$\/'"*)\?:]\/[^\/\n\r\*][^\/\n\r]*\/g?i?""", ignore)
        # remove: ;;; doSomething();
        if special_chars:
            parser.add(""";;;[^\n\r]+[\n\r]""")
        # remove redundant semi-colons
        parser.add(r"""\(;;\)""", "$2")  # protect for (;;) loops
        parser.add(r""";+\s*([};])""", "$2")
        # apply the above
        script = parser.execute(script)

        # remove white-space
        parser.add(r"""(\b|\$)\s+(\b|\$)""", "$2 $3")
        parser.add(r"""([+\-])\s+([+\-])""", "$2 $3")
        parser.add(r"""\s+""", "")
        return parser.execute(script)

    def get_encoder(self, ascii_: int) -> Callable:
        """Get the encoding function based on the ASCII value.

        Args:
            ascii_ (int): The ASCII value to determine the encoding function.

        Returns:
            Callable: The encoding function based on the ASCII value.
        """
        mapping = {}
        base = ord("0")
        mapping.update({i: chr(i + base) for i in range(10)})
        base = ord("a")
        mapping.update({i + 10: chr(i + base) for i in range(26)})
        base = ord("A")
        mapping.update({i + 36: chr(i + base) for i in range(26)})
        base = 161
        mapping.update({i + 62: chr(i + base) for i in range(95)})

        def encode10(char_code: int) -> str:
            """Encode using base10 characters.

            zero encoding
            characters: 0123456789

            Args:
                char_code (int): The character code to encode.

            Returns:
                str: The encoded character code as a string.
            """
            return str(char_code)

        def encode36(char_code: int) -> str:
            """Encode using base36 characters.

            inherent base36 support
            characters: 0123456789abcdefghijklmnopqrstuvwxyz

            Args:
                char_code (int): The character code to encode.

            Returns:
                str: The encoded character code as a string.
            """
            l = []
            remainder = char_code
            while 1:
                result, remainder = divmod(remainder, 36)
                l.append(mapping[remainder])
                if not result:
                    break
                remainder = result
            l.reverse()
            return "".join(l)

        def encode62(char_code: int) -> str:
            """Encode using base62 characters.

            hitch a ride on base36 and add the upper case alpha characters
            characters: 0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ

            Args:
                char_code (int): The character code to encode.

            Returns:
                str: The encoded character code as a string.
            """
            l = []
            remainder = char_code
            while 1:
                result, remainder = divmod(remainder, 62)
                l.append(mapping[remainder])
                if not result:
                    break
                remainder = result
            l.reverse()
            return "".join(l)

        def encode95(char_code: int) -> str:
            """Encode using high-ascii characters.

            Args:
                char_code (int): The character code to encode.

            Returns:
                str: The encoded character code as a string.
            """
            l = []
            remainder = char_code
            while 1:
                result, remainder = divmod(remainder, 95)
                l.append(mapping[remainder + 62])
                if not result:
                    break
                remainder = result
            l.reverse()
            return "".join(l)

        return (
            encode10
            if ascii_ <= 10
            else encode36
            if ascii_ <= 36
            else encode62
            if ascii_ <= 62
            else encode95
        )

    def escape(self, script: str) -> str:
        """Escape the script for safe embedding in a string.

        Args:
            script (str): The JavaScript code to escape.

        Returns:
            str: The escaped JavaScript code.
        """
        return script.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
        # return re.sub(r"""([\\'](?!\n))""", "\\$1", script)

    def escape95(self, script: str) -> str:
        """Escape high-ascii characters in the script.

        Args:
            script (str): The JavaScript code to escape.

        Returns:
            str: The escaped JavaScript code.
        """
        result = []
        for x in script:
            if x > "\xa1":
                x = f"\\x{ord(x):0x}"
            result.append(x)
        return "".join(result)

    def encode_keywords(
        self,
        script: str,
        encoding: int,
        fast_decode: bool,
    ) -> str:
        """Encode keywords in the JavaScript code.

        Args:
            script (str): The JavaScript code to encode.
            encoding (int): The encoding level (0-95).
            fast_decode (bool): Whether to use fast decoding.

        Returns:
            str: The encoded JavaScript code.
        """
        # escape high-ascii values already in the script (i.e. in strings)
        if encoding > 62:
            script = self.escape95(script)
        # create the parser
        parser = ParseMaster()
        encode = self.get_encoder(encoding)
        # for high-ascii, don't encode single character low-ascii
        regexp = r"""\w\w+""" if encoding > 62 else r"""\w+"""
        # build the word list
        keywords = self.analyze(script, regexp, encode)
        encoded = keywords["encoded"]
        # encode

        def repl(match: re.Match, offset: int) -> str:
            """Replacement function for encoding keywords.

            Args:
                match (re.Match): The match object containing the matched
                    patterns.
                offset (int): The offset for the match groups.

            Returns:
                str: The encoded string for the matched pattern.
            """
            return encoded.get(match.group(offset), "")

        parser.add(regexp, repl)
        # if encoded, wrap the script in a decoding function
        script = parser.execute(script)
        return self.boot_strap(script, keywords, encoding, fast_decode)

    def analyze(self, script: str, regexp: str, encode: Callable) -> dict:
        """Analyse the script to find keywords and their frequencies.

        Args:
            script (str): The JavaScript code to analyse.
            regexp (str): The regular expression to match keywords.
            encode (Callable): The encoding function to use for keywords.

        Returns:
            dict: A dictionary containing sorted keywords, their encodings, and
                protected words.
        """
        # analyse
        # retrieve all words in the script
        regexp = re.compile(regexp, re.M)
        all_words = regexp.findall(script)
        sorted_ = []  # list of words sorted by frequency
        encoded = {}  # dictionary of word->encoding
        protected = {}  # instances of "protected" words
        if not all_words:
            return {"sorted": sorted_, "encoded": encoded, "protected": protected}

        unsorted = []
        _protected = {}
        values = {}
        count = {}
        all_words.reverse()
        for word in all_words:
            word = f"${word}"
            if word not in count:
                count[word] = 0
                j = len(unsorted)
                unsorted.append(word)
                # make a dictionary of all of the protected words in this script
                #  these are words that might be mistaken for encoding
                values[j] = encode(j)
                _protected["$" + values[j]] = j
            count[word] = count[word] + 1
        # prepare to sort the word list, first we must protect
        #  words that are also used as codes. we assign them a code
        #  equivalent to the word itself.
        # e.g. if "do" falls within our encoding range
        #      then we store keywords["do"] = "do";
        # this avoids problems when decoding
        sorted_ = [None] * len(unsorted)
        for word in unsorted:
            if word in _protected and isinstance(_protected[word], int):
                sorted_[_protected[word]] = word[1:]
                protected[_protected[word]] = True
                count[word] = 0
        # unsorted.sort(lambda a, b: count[b]-count[a])
        unsorted = sorted(
            unsorted, key=functools.cmp_to_key(lambda a, b: count[b] - count[a])
        )
        j = 0
        for i in range(len(sorted_)):
            if sorted_[i] is None:
                sorted_[i] = unsorted[j][1:]
                j = j + 1
            encoded[sorted_[i]] = values[i]
        return {"sorted": sorted_, "encoded": encoded, "protected": protected}

    def encode_private(self, char_code: int) -> str:
        """Encode private variables (those starting with an underscore).

        Args:
            char_code (int): The character code to encode.

        Returns:
            str: The encoded character code as a string.
        """
        return f"_{char_code}"

    def encode_special_chars(self, script: str) -> str:
        """Encode special characters in the script.

        Args:
            script (str): The JavaScript code to encode.

        Returns:
            str: The encoded JavaScript code.
        """
        parser = ParseMaster()
        # replace: $name -> n, $$name -> $$na

        def repl(match: re.Match, offset: int) -> str:
            """Replacement function for encoding special characters.

            Args:
                match (re.Match): The match object containing the matched
                    patterns.
                offset (int): The offset for the match groups.

            Returns:
                str: The encoded string for the matched pattern.
            """
            # print offset, match.groups()
            length = len(match.group(offset + 2))
            start = length - max(length - len(match.group(offset + 3)), 0)
            return match.group(offset + 1)[start : start + length] + match.group(
                offset + 4
            )

        parser.add(r"""((\$+)([a-zA-Z\$_]+))(\d*)""", repl)
        # replace: _name -> _0, double-underscore (__name) is ignored
        regexp = r"""\b_[A-Za-z\d]\w*"""
        # build the word list
        keywords = self.analyze(script, regexp, self.encode_private)
        # quick ref
        encoded = keywords["encoded"]

        def repl(match: re.Match, offset: int) -> str:
            """Replacement function for encoding special characters.

            Args:
                match (re.Match): The match object containing the matched
                    patterns.
                offset (int): The offset for the match groups.

            Returns:
                str: The encoded string for the matched pattern.
            """
            return encoded.get(match.group(offset), "")

        parser.add(regexp, repl)
        return parser.execute(script)

    def boot_strap(
        self,
        packed: str,
        keywords: dict,
        encoding: int,
        fast_decode: bool,
    ) -> str:
        """Build the boot function used for loading and decoding the packed script.

        Args:
            packed (str): The packed JavaScript code.
            keywords (dict): A dictionary containing the sorted keywords and
                their encodings.
            encoding (int): The encoding level (0-95).
            fast_decode (bool): Whether to use fast decoding.

        Returns:
            str: The bootstrapped JavaScript code.
        """
        encode_regex = re.compile(r"""\$encode\(\$count\)""")
        # $packed: the packed script
        # packed = self.escape(packed)
        # packed = [packed[x*10000:(x+1)*10000] for x in range((len(packed)/10000)+1)]
        # packed = "'" + "'+\n'".join(packed) + "'\n"
        packed = "'" + self.escape(packed) + "'"

        # $count: number of words contained in the script
        count = len(keywords["sorted"])

        # $ascii: base for encoding
        ascii_value = min(count, encoding) or 1

        # $keywords: list of words contained in the script
        for i in keywords["protected"]:
            keywords["sorted"][i] = ""
        # convert from a string to an array
        keywords = "'" + "|".join(keywords["sorted"]) + "'.split('|')"

        encoding_functions = {
            10: """ function($charCode) {return $charCode;}""",
            36: """ function($charCode) {return $charCode.toString(36);}""",
            62: """ function($charCode) {
    return ($charCode < _encoding ? "" :
        arguments.callee(parseInt($charCode / _encoding))) +
        (($charCode = $charCode % _encoding) > 35 ?
        String.fromCharCode($charCode + 29) : $charCode.toString(36));
}""",
            95: """ function($charCode) {
    return ($charCode < _encoding ? "" : arguments.callee($charCode / _encoding)) +
        String.fromCharCode($charCode % _encoding + 161);
}""",
        }

        # $encode: encoding function (used for decoding the script)
        encode = encoding_functions[encoding]
        encode = encode.replace("_encoding", "$ascii")
        encode = encode.replace("arguments.callee", "$encode")
        inline = "$count.toString($ascii)" if ascii_value > 10 else "$count"
        # $decode: code snippet to speed up decoding
        if fast_decode:
            # create the decoder
            decode = r"""// does the browser support String.replace where the
//  replacement value is a function?
if (!''.replace(/^/, String)) {
    // decode all the values we need
    while ($count--) {
        $decode[$encode($count)] = $keywords[$count] || $encode($count);
    }
    // global replacement function
    $keywords = [function($encoded){return $decode[$encoded]}];
    // generic match
    $encode = function(){return'\\w+'};
    // reset the loop counter -  we are now doing a global replace
    $count = 1;
}"""
            if encoding > 62:
                decode = decode.replace("\\\\w", "[\\xa1-\\xff]")
            # perform the encoding inline for lower ascii values
            elif ascii_value < 36:
                decode = encode_regex.sub(inline, decode)
            # special case: when $count==0 there ar no keywords. i want to keep
            #  the basic shape of the unpacking function so i'll frig the code...
            if not count:
                raise NotImplementedError
                # ) $decode = $decode.replace(/(\$count)\s*=\s*1/, "$1=0");

        # boot function
        unpack = r"""function($packed, $ascii, $count, $keywords, $encode, $decode) {
    while ($count--) {
        if ($keywords[$count]) {
            $packed = $packed.replace(
                new RegExp("\\b" + $encode($count) + "\\b", "g"), $keywords[$count]
            );
        }
    }
    return $packed;
}"""
        if fast_decode:
            # insert the decoder
            # unpack = re.sub(r"""\{""", "{" + decode + ";", unpack)
            unpack = unpack.replace("{", "{" + decode + ";", 1)

        if encoding > 62:  # high-ascii
            # get rid of the word-boundaries for regexp matches
            unpack = re.sub(r"""'\\\\b'\s*\+|\+\s*'\\\\b'""", "", unpack)
        if ascii_value > 36 or encoding > 62 or fast_decode:
            # insert the encode function
            # unpack = re.sub(r"""\{""", "{$encode=" + encode + ";", unpack)
            unpack = unpack.replace("{", "{$encode=" + encode + ";", 1)
        else:
            # perform the encoding inline
            unpack = encode_regex.sub(inline, unpack)
        # pack the boot function too
        unpack = self.pack(unpack, 0, False, True)

        # arguments
        params = [packed, str(ascii_value), str(count), keywords]
        if fast_decode:
            # insert placeholders for the decoder
            params.extend(["0", "{}"])

        # the whole thing
        return "eval(" + unpack + "(" + ",".join(params) + "))\n"

    def pack(
        self,
        script: str,
        encoding: int = 0,
        fast_decode: bool = False,
        special_chars: bool = False,
        compaction: bool = True,
    ) -> str:
        """Pack the given JavaScript script.

        Args:
            script (str): The JavaScript code to pack.
            encoding (int, optional): The encoding level (0-95). Defaults to 0.
            fast_decode (bool, optional): Whether to use fast decoding. Defaults
                to False.
            special_chars (bool, optional): Whether to encode special
                characters. Defaults to False.
            compaction (bool, optional): Whether to apply basic compression.
                Defaults to True.

        Returns:
            str: The packed JavaScript code.
        """
        script = script + "\n"
        self._encoding = encoding
        self._fastDecode = fast_decode
        if special_chars:
            script = self.special_compression(script)
            script = self.encode_special_chars(script)
        elif compaction:
            script = self.basic_compression(script)
        if encoding:
            script = self.encode_keywords(script, encoding, fast_decode)
        return script
