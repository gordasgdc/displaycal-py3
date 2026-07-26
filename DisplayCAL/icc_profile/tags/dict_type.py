"""ICC dictType tag.

Includes `DictType` and its `DictTypeJSONEncoder` helper.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from DisplayCAL.icc_profile.codecs import uInt32Number, uInt32Number_tohex
from DisplayCAL.icc_profile.structures import ADict, AODict
from DisplayCAL.icc_profile.tags.base import ICCProfileTag
from DisplayCAL.icc_profile.tags.text import MultiLocalizedUnicodeType


class DictType(ICCProfileTag, AODict):
    """ICC dictType Tag.

    Implements all features of 'Dictionary Type and Metadata TAG Definition'
    (ICC spec revision 2010-02-25), including shared data (the latter will
    only be effective for mutable types, ie. MultiLocalizedUnicodeType)

    Examples:

    tag[key]   Returns the (non-localized) value
    tag.getname(key, locale='en_US') Returns the localized name if present
    tag.getvalue(key, locale='en_US') Returns the localized value if present
    tag[key] = value   Sets the (non-localized) value

    """

    def __init__(
        self,
        tagData: None | bytes = None,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        AODict.__init__(self)
        if not tagData:
            return
        numrecords = uInt32Number(tagData[8:12])
        recordlen = uInt32Number(tagData[12:16])
        if recordlen not in (16, 24, 32):
            print(
                f"Error (non-critical): '{tagData[:4]}' invalid record length "
                f"(expected 16, 24 or 32, got {recordlen})"
            )
            return
        elements = {}
        for n in range(numrecords):
            record = tagData[16 + n * recordlen : 16 + (n + 1) * recordlen]
            if len(record) < recordlen:
                print(
                    f"Error (non-critical): '{tagData[:4]}' record {n} too short "
                    f"(expected {recordlen} bytes, got {len(record)} bytes)"
                )
                break
            for key, offsetpos in (
                ("name", 0),
                ("value", 8),
                ("display_name", 16),
                ("display_value", 24),
            ):
                if (
                    offsetpos in (0, 8)
                    or recordlen == offsetpos + 8
                    or recordlen == offsetpos + 16
                ):
                    # Required:
                    # Bytes 0..3, 4..7: Name offset and size
                    # Bytes 8..11, 12..15: Value offset and size
                    # Optional:
                    # Bytes 16..23, 24..23: Display name offset and size
                    # Bytes 24..27, 28..31: Display value offset and size
                    offset = uInt32Number(record[offsetpos : offsetpos + 4])
                    size = uInt32Number(record[offsetpos + 4 : offsetpos + 8])
                    if offset > 0:
                        if (offset, size) in elements:
                            # Use existing element if same offset and size
                            # This will really only make a difference for
                            # mutable types i.e. MultiLocalizedUnicodeType
                            data = elements[(offset, size)]
                        else:
                            data = tagData[offset : offset + size]
                            try:
                                if key.startswith("display_"):
                                    data = MultiLocalizedUnicodeType(data, "mluc")
                                else:
                                    data = data.decode("UTF-16-BE", "replace").rstrip(
                                        "\0"
                                    )
                            except Exception:
                                print(
                                    "Error (non-critical): could not decode "
                                    f"'{tagData[:4]}', offset {offset}, length {size}"
                                )
                            # Remember element by offset and size
                            elements[(offset, size)] = data
                        if key == "name":
                            name = data
                            self[name] = ""
                        else:
                            self.get(name)[key] = data

    def __getitem__(self, name: str) -> Any:  # noqa: ANN401
        """Get item from dict.

        Args:
            name (str): Name of the item.

        Returns:
            Any: Value of the item.
        """
        return self.get(name).value

    def __setitem__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Set item in dict.

        Args:
            name (str): Name of the item.
            value (Any): Value of the item.
        """
        AODict.__setitem__(self, name, ADict(value=value))

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: The raw tag data representing the dictionary.
        """
        numrecords = len(self)
        recordlen = 16
        keys = ("name", "value")
        for value in self.values():
            if not isinstance(value, dict):
                continue
            if "display_value" in value:
                recordlen = 32
                break
            if "display_name" in value:
                recordlen = 24
        if recordlen > 16:
            keys += ("display_name",)
        if recordlen > 24:
            keys += ("display_value",)
        tag_data = [
            b"dict",
            b"\0" * 4,
            uInt32Number_tohex(numrecords),
            uInt32Number_tohex(recordlen),
        ]
        storage_offset = 16 + numrecords * recordlen
        storage = []
        elements = []
        offsets = []
        for item in self.items():
            for key in keys:
                if key == "name":
                    element = item[0]
                else:
                    element = item[1].get(key) if isinstance(item[1], dict) else item[1]
                if element is None:
                    offset = 0
                    size = 0
                elif element in elements:
                    # Use existing offset and size if same element
                    offset, size = offsets[elements.index(element)]
                else:
                    offset = storage_offset + len(b"".join(storage))
                    if isinstance(element, MultiLocalizedUnicodeType):
                        data = element.tagData
                    else:
                        data = str(element).encode("UTF-16-BE")
                    size = len(data)
                    if isinstance(element, MultiLocalizedUnicodeType):
                        # Remember element, offset and size
                        elements.append(element)
                        offsets.append((offset, size))
                    # Pad all data with binary zeros so it lies on
                    # 4-byte boundaries
                    padding = math.ceil(size / 4.0) * 4 - size
                    data += b"\0" * padding
                    storage.append(data)
                tag_data.append(uInt32Number_tohex(offset))
                tag_data.append(uInt32Number_tohex(size))
        tag_data.extend(storage)
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set raw tag data.

        Does nothing, as the tagData is read-only.

        Args:
            tagData (bytes): The raw tag data to set.
        """

    def getname(
        self,
        name: str,
        default: None | Any = None,  # noqa: ANN401
        locale: str = "en_US",
    ) -> str:
        """Convenience function to get (localized) names.

        Args:
            name (str): The name of the item to get.
            default (Any, optional): Default value to return if the item is not
                found. Defaults to None.
            locale (str, optional): Locale to use for localized names. Defaults
                to "en_US".

        Returns:
            str: The localized name of the item if available, otherwise the
                default value or the non-localized name.
        """
        item = self.get(name, default)
        if item is default:
            return default
        if locale and "display_name" in item:
            return item.display_name.get_localized_string(*locale.split("_"))
        return name

    def getvalue(
        self,
        name: str,
        default: None | Any = None,  # noqa: ANN401
        locale: str = "en_US",
    ) -> Any:  # noqa: ANN401
        """Convenience function to get (localized) values.

        Args:
            name (str): The name of the item to get.
            default (Any, optional): Default value to return if the item is not
                found. Defaults to None.
            locale (str, optional): Locale to use for localized values.
                Defaults to "en_US".

        Returns:
            Any: The localized value of the item if available, otherwise the
                default value or the non-localized value.
        """
        item = self.get(name, default)
        if item is default:
            return default
        if locale and "display_value" in item:
            return item.display_value.get_localized_string(*locale.split("_"))
        if isinstance(item, dict):
            return item.value
        return item

    def setitem(
        self,
        name: str,
        value: Any,  # noqa: ANN401
        display_name: None | dict = None,
        display_value: None | dict = None,
    ) -> None:
        """Convenience function to set items.

        display_name and display_value (if given) should be dict types with
        country -> language -> string mappings, e.g.:

        {"en": {"US": u"localized string"},
         "de": {"DE": u"localized string", "CH": u"localized string"}}


        Args:
            name (str): The name of the item to set.
            value (Any): The value to set for the item.
            display_name (None | dict, optional): Localized display names for
                the item.
            display_value (None | dict, optional): Localized display values
                for the item.
        """
        self[name] = value
        item = self.get(name)
        if display_name:
            item.display_name = MultiLocalizedUnicodeType()
            item.display_name.update(display_name)
        if display_value:
            item.display_value = MultiLocalizedUnicodeType()
            item.display_value.update(display_value)

    def to_json(
        self, encoding: str = "UTF-8", errors: str = "replace", locale: str = "en_US"
    ) -> str:
        """Return a JSON representation.

        Display names/values are used if present.

        Args:
            encoding (str, optional): Encoding to use for the JSON string.
                Defaults to "UTF-8".
            errors (str, optional): Error handling scheme for encoding.
                Defaults to "replace".
            locale (str, optional): Locale to use for localized names/values.
                Defaults to "en_US".

        Returns:
            str: JSON representation of the DictType object.
        """
        return DictTypeJSONEncoder(locale=locale).encode(self)


class DictTypeJSONEncoder(json.JSONEncoder):
    """JSON Encoder for the DictType class."""

    def __init__(self, *args, **kwargs) -> None:
        self.locale = kwargs.pop("locale") or "en_US"
        super().__init__(*args, **kwargs)

    def default(self, obj: Any) -> dict:  # noqa: ANN401
        """Default method for encoding objects to JSON.

        Args:
            obj (object): The object to encode.

        Returns:
            dict: Encoded object as a dictionary.
        """
        return_data = {}
        regex = re.compile(r"\\x([0-9a-f]{2})")
        repl_str = r"\\u00\1"
        for name in obj:
            value = obj.getvalue(name, None, self.locale)
            name = obj.getname(name, None, self.locale)
            value = '"{}"'.format(repr(str(value))[2:-1].replace('"', '\\"'))
            name = regex.sub(repl_str, name)
            value = regex.sub(repl_str, value)
            return_data[name] = value
        return return_data
