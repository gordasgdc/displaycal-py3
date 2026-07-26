"""ICC Colorant-family tags.

Includes `Colorant`, `ColorantTableType`, `ChromaticityType`, `Geometry`,
`Illuminant`, `Observer`, `MeasurementType`, `ViewingConditionsType`, and
`ProfileSequenceDescType`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from DisplayCAL.icc_profile.codecs import (
    u16Fixed16Number,
    u16Fixed16Number_tohex,
    uInt16Number,
    uInt16Number_tohex,
    uInt32Number,
    uInt32Number_tohex,
)
from DisplayCAL.icc_profile.constants import COLORANTS, GEOMETRY, ILLUMINANTS, OBSERVERS
from DisplayCAL.icc_profile.structures import ADict, AODict
from DisplayCAL.icc_profile.tags.base import ICCProfileTag, XYZNumber
from DisplayCAL.icc_profile.tags.text import (
    MultiLocalizedUnicodeType,
    TextDescriptionType,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from DisplayCAL.icc_profile import ICCProfile


class Colorant:
    """Colorant class to handle colorant information.

    Args:
        binaryString (bytes, optional): A 4-byte binary string representing the
            colorant type.
    """

    def __init__(self, binaryString: bytes = b"\0" * 4) -> None:  # noqa: N803
        self._type = uInt32Number(binaryString)
        self._channels = []

    def __getitem__(self, key: str) -> Any:  # noqa: ANN401
        """Get attribute via dictionary key.

        Args:
            key (str): The attribute name.

        Returns:
            Any: The value of the attribute.
        """
        return self.__getattribute__(key)

    def __iter__(self) -> Iterator[str]:
        """Return an iterator over the keys of the object.

        Returns:
            iter: An iterator over the keys of the object.
        """
        return iter(list(self.keys()))

    def __repr__(self) -> str:
        """Return the string representation of the object.

        Returns:
            str: The string representation of the object.
        """
        items = []
        for key, value in (("type", self.type), ("description", self.description)):
            items.append(f"{key!r}: {value!r}")
        channels = [
            "[{}]".format(", ".join([str(v) for v in xy])) for xy in self.channels
        ]
        items.append("'channels': [{}]".format(", ".join(channels)))
        return "{{{}}}".format(", ".join(items))

    def __setitem__(self, key: str, value: Any) -> None:  # noqa: ANN401
        """Set attribute via dictionary key.

        Args:
            key (str): The attribute name.
            value (Any): The value to set.
        """
        object.__setattr__(self, key, value)

    @property
    def channels(self) -> list:
        """Return the channels of the colorant.

        Returns:
            list: A list of channels, where each channel is a list of values
                representing the colorant's channels. If no channels are set,
        """
        if not self._channels and self._type and self._type in COLORANTS:
            return [list(xy) for xy in COLORANTS[self._type]["channels"]]
        return self._channels

    @channels.setter
    def channels(self, channels: list) -> None:
        """Set the channels of the colorant.

        Args:
            channels (list): A list of channels, where each channel is a list
                of values representing the colorant's channels.
        """
        self._channels = channels

    @property
    def description(self) -> str:
        """Return the description of the colorant.

        Returns:
            str: The description of the colorant, which is based on its type.
        """
        return COLORANTS.get(self._type, COLORANTS[0])["description"]

    @description.setter
    def description(self, value: str) -> None:
        """Set the description of the colorant.

        Does nothing, as the description is derived from the type.

        Args:
            value (str): The description of the colorant.
        """

    def get(self, key: str, default: None | Any = None) -> Any:  # noqa: ANN401
        """Get the value of the attribute with the given key.

        Args:
            key (str): The key of the attribute to get.
            default (None | Any, optional): The default value to return if the
                key does not exist.

        Returns:
            Any: The value of the attribute with the given key, or the default
                value if the key does not exist.
        """
        return getattr(self, key, default)

    def items(self) -> list[tuple[str, Any]]:
        """Return a list of key-value pairs in the object.

        Returns:
            list[tuple[str, Any]]: A list of key-value pairs in the object.
        """
        return list(zip(list(self.keys()), list(self.values())))

    def iteritems(self) -> Iterator[tuple[str, Any]]:
        """Return an iterator over the key-value pairs in the object.

        Returns:
            Iterator[tuple[str, Any]]: An iterator over the key-value pairs in
                the object.
        """
        return zip(list(self.keys()), iter(self.values()))

    iterkeys = __iter__

    def itervalues(self) -> Iterator:
        """Return an iterator over the values in the object.

        Returns:
            Iterator: An iterator over the values in the object.
        """
        return map(self.get, list(self.keys()))

    def keys(self) -> list[str]:
        """Return a list of keys in the object.

        Returns:
            list[str]: A list of keys in the object.
        """
        return ["type", "description", "channels"]

    def round(self, digits: int = 4) -> Colorant:
        """Return a new Colorant object with rounded channel values.

        Args:
            digits (int): The number of decimal places to round to. Defaults to
                4.

        Returns:
            Colorant: A new Colorant object with rounded channel values.
        """
        colorant = self.__class__()
        colorant.type = self.type
        for xy in self.channels:
            colorant._channels.append([round(value, digits) for value in xy])
        return colorant

    @property
    def type(self) -> int:
        """Return the type of the colorant.

        Returns:
            int: The type of the colorant, which should be one of the
                predefined colorant types in COLORANTS.
        """
        return self._type

    @type.setter
    def type(self, value: int) -> None:
        """Set the type of the colorant.

        Args:
            value (int): The type of the colorant, which should be one of the
                predefined colorant types in COLORANTS.
        """
        if value and value != self._type and value in COLORANTS:
            self._channels = []
        self._type = value

    def update(self, *args: tuple, **kwargs: dict) -> None:
        """Update the object with key-value pairs from the given arguments.

        Args:
            *args: Iterable of key-value pairs or a dictionary.
            **kwargs: Additional key-value pairs to update the object with.

        Raises:
            TypeError: If more than one argument is provided.
        """
        if len(args) > 1:
            raise TypeError(f"update expected at most 1 arguments, got {len(args):d}")
        for iterable in args + tuple(kwargs.items()):
            if hasattr(iterable, "items"):
                self.update(iter(iterable.items()))
            elif hasattr(iterable, "keys"):
                for key in list(iterable.keys()):
                    self[key] = iterable[key]
            else:
                for key, val in iterable:
                    self[key] = val

    def values(self) -> list:
        """Return a list of values in the object.

        Returns:
            list: A list of values in the object.
        """
        return list(map(self.get, list(self.keys())))


class Geometry(ADict):
    """Geometry attribute dictionary class.

    Args:
        binaryString (bytes): The binary string representing the geometry type.
    """

    def __init__(self, binaryString: bytes) -> None:  # noqa: N803
        super().__init__()
        self.type = uInt32Number(binaryString)
        self.description = GEOMETRY[self.type]


class Illuminant(ADict):
    """Illuminant attribute dictionary class.

    Args:
        binaryString (bytes): The binary string representing the illuminant
            type.
    """

    def __init__(self, binaryString: bytes) -> None:  # noqa: N803
        super().__init__()
        self.type = uInt32Number(binaryString)
        self.description = ILLUMINANTS[self.type]


class Observer(ADict):
    """ICC Observer tag.

    Args:
        bytes_data (bytes): Raw tag data containing the observer type.
    """

    def __init__(self, bytes_data: bytes) -> None:
        super(ADict, self).__init__()
        self.type = uInt32Number(bytes_data)
        self.description = OBSERVERS[self.type]


class ChromaticityType(ICCProfileTag, Colorant):
    """ICC ChromaticityType tag.

    Args:
        tagData (bytes, optional): Raw tag data. Defaults to None.
        tagSignature (str, optional): Tag signature. Defaults to None.
    """

    def __init__(
        self,
        tagData: None | bytes = None,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        if not tagData:
            Colorant.__init__(self, uInt32Number_tohex(1))
            return
        device_channels_count = uInt16Number(tagData[8:10])
        Colorant.__init__(self, uInt32Number_tohex(uInt16Number(tagData[10:12])))
        channels = tagData[12:]
        for _count in range(device_channels_count):
            self._channels.append(
                [u16Fixed16Number(channels[:4]), u16Fixed16Number(channels[4:8])]
            )
            channels = channels[8:]

    __repr__ = Colorant.__repr__

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: Raw tag data for the ChromaticityType tag.
        """
        tag_data = [b"chrm", b"\0" * 4, uInt16Number_tohex(len(self.channels))]
        tag_data.append(uInt16Number_tohex(self.type))
        tag_data.extend(
            u16Fixed16Number_tohex(xy) for channel in self.channels for xy in channel
        )
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set raw tag data.

        Does nothing as this tag is read-only.

        Args:
            tagData (bytes): Raw tag data.
        """


class ColorantTableType(ICCProfileTag, AODict):
    """ICC ColorantTableType tag.

    Args:
        tagData (bytes, optional): Raw tag data. Defaults to None.
        tagSignature (str, optional): Tag signature. Defaults to None.
        pcs (bytes, optional): Profile connection space. Defaults to None.
    """

    def __init__(
        self,
        tagData: None | bytes = None,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
        pcs: None | bytes = None,
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        AODict.__init__(self)
        if not tagData:
            return
        colorant_count = uInt32Number(tagData[8:12])
        data = tagData[12:]
        for _count in range(colorant_count):
            pcsvalues = [
                uInt16Number(data[32:34]),
                uInt16Number(data[34:36]),
                uInt16Number(data[36:38]),
            ]
            for i, pcsvalue in enumerate(pcsvalues):
                if pcs in (b"Lab", b"RGB", b"CMYK", b"YCbr"):
                    keys = ["L", "a", "b"]
                    if i == 0:
                        # L* range 0..100 + (25500 / 65280.0)
                        pcsvalues[i] = pcsvalue / 65536.0 * 256 / 255.0 * 100
                    else:
                        # a, b range -128..127 + (255 / 256.0)
                        pcsvalues[i] = -128 + (pcsvalue / 65536.0 * 256)
                elif pcs == b"XYZ":
                    # X, Y, Z range 0..100 + (32767 / 32768.0)
                    keys = ["X", "Y", "Z"]
                    pcsvalues[i] = pcsvalue / 32768.0 * 100
                else:
                    print(f"Warning: Non-standard profile connection space '{pcs}'")
                    return
            end = data[:32].find(b"\0")
            if end < 0:
                end = 32
            name = data[:end]
            self[name] = AODict(list(zip(keys, pcsvalues)))
            data = data[38:]


class MeasurementType(ICCProfileTag, ADict):
    """ICC measurementType tag.

    Args:
        tagData (bytes): The raw tag data.
        tagSignature (str): The signature of the tag.
    """

    def __init__(self, tagData: bytes, tagSignature: str) -> None:  # noqa: N803
        ICCProfileTag.__init__(self, tagData, tagSignature)

        print(f"tagData[8:12]: {tagData[8:12]}")

        self.update(
            {
                "observer": Observer(tagData[8:12]),
                "backing": XYZNumber(tagData[12:24]),
                "geometry": Geometry(tagData[24:28]),
                "flare": u16Fixed16Number(tagData[28:32]),
                "illuminantType": Illuminant(tagData[32:36]),
            }
        )


class ProfileSequenceDescType(ICCProfileTag, list):
    """ICC profileSequenceDescType tag.

    Args:
        tagData (None | bytes, optional): Raw tag data. Defaults to None.
        tagSignature (None | str, optional): Tag signature. Defaults to None.
        profile (None | ICCProfile, optional): The ICC profile associated with
            this tag. Defaults to None.
    """

    def __init__(
        self,
        tagData: None | bytes = None,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
        profile: None | ICCProfile = None,
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.profile = profile
        if not tagData:
            return
        count = uInt32Number(tagData[8:12])
        desc_data = tagData[12:]
        while count:
            # NOTE: Like in the profile header, the attributes are a 64 bit
            # value, but the least significant 32 bits (big-endian) are
            # reserved for the ICC.
            attributes = uInt32Number(desc_data[8:12])
            desc = {
                "manufacturer": desc_data[0:4],
                "model": desc_data[4:8],
                "attributes": {
                    "reflective": attributes & 1 == 0,
                    "glossy": attributes & 2 == 0,
                    "positive": attributes & 4 == 0,
                    "color": attributes & 8 == 0,
                },
                "tech": desc_data[16:20],
            }
            desc_data = desc_data[20:]
            for desc_type in ("dmnd", "dmdd"):
                tag_type = desc_data[0:4]
                if tag_type == "desc":
                    cls = TextDescriptionType
                elif tag_type == "mluc":
                    cls = MultiLocalizedUnicodeType
                else:
                    print(
                        "Error (non-critical): could not fully decode 'pseq' - "
                        f"unknown {desc_type!r} tag type {tag_type!r}"
                    )
                    count = 1  # Skip remaining
                    break
                desc[desc_type] = cls(desc_data)
                desc_data = desc_data[len(desc[desc_type].tagData) :]
            self.append(desc)
            count -= 1

    def add(self, profile: ICCProfile) -> None:
        """Add description structure of profile.

        Args:
            profile (ICCProfile): The ICC profile to add.
        """
        desc = {}
        desc.update(profile.device)
        desc["tech"] = profile.tags.get("tech", b"").ljust(4, b"\0")[:4]
        for desc_type in ("dmnd", "dmdd"):
            if self.profile.version >= 4:
                cls = MultiLocalizedUnicodeType
            else:
                cls = TextDescriptionType
            if self.profile.version < 4 and profile.version < 4:
                # Both profiles not v4
                tag = profile.tags.get(desc_type, cls())
            else:
                tag = cls()
                description = str(profile.tags.get(desc_type, ""))
                if self.profile.version < 4:
                    # Other profile is v4
                    tag.ASCII = description.encode("ASCII", "asciize")
                    if description != tag.ASCII:
                        tag.Unicode = description
                else:
                    # Other profile is v2
                    tag.add_localized_string("en", "US", description)
            desc[desc_type] = tag
        self.append(desc)

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: The raw tag data formatted as bytes.
        """
        tag_data = [b"pseq", b"\0" * 4, uInt32Number_tohex(len(self))]
        for desc in self:
            tag_data.append(desc.get("manufacturer", b"").ljust(4, b"\0")[:4])
            tag_data.append(desc.get("model", b"").ljust(4, b"\0")[:4])
            attributes = 0
            for name, bit in {
                "reflective": 1,
                "glossy": 2,
                "positive": 4,
                "color": 8,
            }.items():
                if not desc.get("attributes", {}).get(name):
                    attributes |= bit
            tag_data.append(uInt32Number_tohex(attributes) + b"\0" * 4)
            tag_data.append(desc.get("tech", b"").ljust(4, b"\0")[:4])
            tag_data.extend(
                desc.get(desc_type, b"").tagData for desc_type in ("dmnd", "dmdd")
            )
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set raw tag data.

        Does nothing, as this tag is read-only.

        Args:
            tagData (bytes): Raw tag data to set.
        """


class ViewingConditionsType(ICCProfileTag, ADict):
    """ICC viewing conditions tag type.

    Args:
        tagData (bytes): The raw tag data.
        tagSignature (str): The signature of the tag.
    """

    def __init__(self, tagData: bytes, tagSignature: str) -> None:  # noqa: N803
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.update(
            {
                "illuminant": XYZNumber(tagData[8:20]),
                "surround": XYZNumber(tagData[20:32]),
                "illuminantType": Illuminant(tagData[32:36]),
            }
        )
