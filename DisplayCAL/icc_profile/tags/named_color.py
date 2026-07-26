"""ICC NamedColor2 tags."""

from __future__ import annotations

from copy import copy
from typing import Any

from DisplayCAL.icc_profile.codecs import (
    uInt16Number,
    uInt16Number_tohex,
    uInt32Number,
    uInt32Number_tohex,
)
from DisplayCAL.icc_profile.structures import AODict
from DisplayCAL.icc_profile.tags.base import ICCProfileTag, Text


class NamedColor2Value:
    """Named Color 2 Value.

    Args:
        valueData (bytes, optional): Binary data containing the named color
            values.
        deviceCoordCount (int, optional): Number of device coordinates.
        pcs (str, optional): PCS name, either "XYZ" or "Lab".
        device (str, optional): Device name, either "RGB" or "Lab".
    """

    def __init__(
        self,
        valueData: bytes = b"\0" * 38,  # noqa: N803
        deviceCoordCount: int = 0,  # noqa: N803
        pcs: str = "XYZ",
        device: str = "RGB",
    ) -> None:
        self._pcsname = pcs
        self._devicename = device
        end = valueData[0:32].find(b"\0")
        if end < 0:
            end = 32
        self.rootName = valueData[0:end]
        self.pcsvalues = [
            uInt16Number(valueData[32:34]),
            uInt16Number(valueData[34:36]),
            uInt16Number(valueData[36:38]),
        ]

        self.pcs = AODict()
        for i, pcsvalue in enumerate(self.pcsvalues):
            if pcs == "Lab":
                if i == 0:
                    # L* range 0..100 + (25500 / 65280.0)
                    self.pcs[pcs[i]] = pcsvalue / 65536.0 * 256 / 255.0 * 100
                else:
                    # a, b range -128..127 + (255/256.0)
                    self.pcs[pcs[i]] = -128 + (pcsvalue / 65536.0 * 256)
            elif pcs == "XYZ":
                # X, Y, Z range 0..100 + (32767 / 32768.0)
                self.pcs[pcs[i]] = pcsvalue / 32768.0 * 100

        device_coords = []
        if deviceCoordCount > 0:
            device_coords.extend(
                uInt16Number(valueData[i : i + 2])
                for i in range(38, 38 + deviceCoordCount * 2, 2)
            )
        self.devicevalues = device_coords
        if device == "Lab":
            # L* range 0..100 + (25500 / 65280.0)
            # a, b range range -128..127 + (255 / 256.0)
            self.device = tuple(
                (
                    v / 65536.0 * 256 / 255.0 * 100
                    if i == 0
                    else -128 + (v / 65536.0 * 256)
                )
                for i, v in enumerate(device_coords)
            )
        elif device == "XYZ":
            # X, Y, Z range 0..100 + (32767 / 32768.0)
            self.device = tuple(v / 32768.0 * 100 for v in device_coords)
        else:
            # Device range 0..100
            self.device = tuple(v / 65535.0 * 100 for v in device_coords)

    @property
    def name(self) -> str:
        """Return the name of the named color.

        Returns:
            str: The name of the named color, decoded from bytes using
                'latin-1' encoding.
        """
        return str(Text(self.rootName.strip(b"\0")), "latin-1")

    def __repr__(self) -> str:
        """Return the string representation of the object.

        Returns:
            str: The string representation of the object.
        """
        pcs = []
        for key in self.pcs:
            value = self.pcs[key]
            pcs.append(f"{key}={value}")
        dev = [f"{value}" for value in self.device]
        return "{}({}, {{{}}}, [{}])".format(
            self.__class__.__name__,
            self.name,
            ", ".join(pcs),
            ", ".join(dev),
        )

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: Raw tag data containing the named color values.
        """
        value_data = []
        value_data.append(self.rootName.ljust(32, b"\0"))
        value_data.extend([uInt16Number_tohex(pcsval) for pcsval in self.pcsvalues])
        value_data.extend(
            [uInt16Number_tohex(deviceval) for deviceval in self.devicevalues]
        )
        return b"".join(value_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set tag data.

        Does nothing, as NamedColor2Value is immutable.

        Args:
            tagData (bytes): Raw tag data to set.
        """


class NamedColor2ValueTuple(tuple):
    """Tuple subclass for NamedColor2Value.

    This class is used to represent a tuple of NamedColor2Value objects.
    """

    __slots__ = ()
    REPR_OUTPUT_SIZE = 10

    def __repr__(self) -> str:
        """Return the string representation of the object.

        Truncates the output if it exceeds the specified size.

        Returns:
            str: The string representation of the object.
        """
        data = list(self[: self.REPR_OUTPUT_SIZE + 1])
        if len(data) > self.REPR_OUTPUT_SIZE:
            data[-1] = "...(remaining elements truncated)..."
        return repr(data)

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: Concatenated tag data from all NamedColor2Value objects in
                the tuple.
        """
        return b"".join([val.tagData for val in self])

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        pass


class NamedColor2Type(ICCProfileTag, AODict):
    """Named Color 2 Type.

    This tag contains a list of named colors, each with a set of device
    coordinates and a set of PCS coordinates. The device coordinates
    are used to identify the color on the device, while the PCS
    coordinates are used to identify the color in a device-independent
    color space. The tag also contains a prefix and suffix that are
    used to format the name of the color.

    Byte offset content encoded as:

        0..3    vendorData        s4Fixed32Number
        4..7    colorCount        uInt32Number
        8..11   deviceCoordCount  uInt32Number
        12..15  reserved          uInt32Number
        16..19  reserved          uInt32Number
        20..51  prefix            s32Fixed32Number
        52..83  suffix            s32Fixed32Number
        84..n   colorValues       NamedColor2Value

    Args:
        tagData (bytes): The raw tag data.
        tagSignature (None | str): The signature of the tag.
        pcs (None | str): The PCS name, either "XYZ" or "Lab".
        device (None | str): The device name, either "RGB" or "Lab".
    """

    REPR_OUTPUT_SIZE = 10

    def __init__(
        self,
        tagData: bytes = b"\0" * 84,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
        pcs: None | str = None,
        device: None | str = None,
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        AODict.__init__(self)

        colorCount = uInt32Number(tagData[12:16])  # noqa: N806
        deviceCoordCount = uInt32Number(tagData[16:20])  # noqa: N806
        stride = 38 + 2 * deviceCoordCount

        self.vendorData = tagData[8:12]
        self.colorCount = colorCount
        self.deviceCoordCount = deviceCoordCount
        self._prefix = Text(tagData[20:52])
        self._suffix = Text(tagData[52:84])
        self._pcsname = pcs
        self._devicename = device

        keys = []
        values = []
        if colorCount > 0:
            start = 84
            end = start + (stride * colorCount)
            for i in range(start, end, stride):
                nc2 = NamedColor2Value(
                    tagData[i : i + stride], deviceCoordCount, pcs=pcs, device=device
                )
                keys.append(nc2.name)
                values.append(nc2)
        self.update(dict(list(zip(keys, values))))

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN401
        """Set an attribute of the object.

        Args:
            name (str): The name of the attribute to set.
            value (Any): The value to set the attribute to.
        """
        object.__setattr__(self, name, value)

    @property
    def prefix(self) -> str:
        """Return the prefix of the named color profile.

        Returns:
            str: The prefix of the named color profile, decoded from bytes
                using 'latin-1' encoding.
        """
        return str(self._prefix.strip(b"\0"), "latin-1")

    @property
    def suffix(self) -> str:
        """Return the suffix of the named color profile.

        Returns:
            str: The suffix of the named color profile, decoded from bytes
                using 'latin-1' encoding.
        """
        return str(self._suffix.strip(b"\0"), "latin-1")

    @property
    def colorValues(self) -> NamedColor2ValueTuple:  # noqa: N802
        """Return a tuple of NamedColor2Value objects.

        Returns:
            NamedColor2ValueTuple: A tuple containing all NamedColor2Value
                objects in the profile.
        """
        return NamedColor2ValueTuple(list(self.values()))

    def add_color(
        self,
        root_name: str,
        *device_coordinates: list[float],
        **pcs_coordinates: dict[str, float],
    ) -> None:
        """Add a named color to the profile.

        Args:
            root_name (str): The name of the color.
            device_coordinates (list): Device coordinates for the color.
            pcs_coordinates (dict): PCS coordinates for the color.

        Raises:
            ICCProfileInvalidError: If the required PCS coordinates or device
                coordinates are not provided, or if the color name already
                exists.
        """
        # Deferred import: ICCProfileInvalidError still lives in
        # DisplayCAL.icc_profile pending its extraction into profile.py
        # (item 10), which itself imports this module.
        from DisplayCAL.icc_profile import ICCProfileInvalidError

        if self._pcsname == "Lab":
            keys = ["L", "a", "b"]
        elif self._pcsname == "XYZ":
            keys = ["X", "Y", "Z"]
        else:
            keys = ["X", "Y", "Z"]

        if not set(pcs_coordinates.keys()).issuperset(set(keys)):
            raise ICCProfileInvalidError(
                "Can't add namedColor2 without all 3 PCS coordinates: "  # noqa: UP032
                "'{}'".format(set(keys) - set(pcs_coordinates.keys()))
            )

        if len(device_coordinates) != self.deviceCoordCount:
            raise ICCProfileInvalidError(
                f"Can't add namedColor2 without all {self.deviceCoordCount} "
                f"device coordinates (called with {len(device_coordinates)})"
            )

        nc2value = NamedColor2Value()
        nc2value._pcsname = self._pcsname
        nc2value._devicename = self._devicename
        nc2value.rootName = root_name

        if root_name in list(self.keys()):
            raise ICCProfileInvalidError(
                f"Can't add namedColor2 with existant name: '{root_name}'"
            )

        nc2value.devicevalues = []
        nc2value.device = tuple(device_coordinates)
        nc2value.pcs = AODict(copy(pcs_coordinates))

        for idx, key in enumerate(keys):
            val = nc2value.pcs[key]
            if key == "L":
                nc2value.pcsvalues[idx] = val * 65536 / (256 / 255.0) / 100.0
            elif key in ("a", "b"):
                nc2value.pcsvalues[idx] = (val + 128) * 65536 / 256.0
            elif key in ("X", "Y", "Z"):
                nc2value.pcsvalues[idx] = val * 32768 / 100.0

        for idx, val in enumerate(nc2value.device):
            if self._devicename == "Lab":
                if idx == 0:
                    # L* range 0..100 + (25500 / 65280.0)
                    nc2value.devicevalues[idx] = val * 65536 / (256 / 255.0) / 100.0
                else:
                    # a, b range -128..127 + (255/256.0)
                    nc2value.devicevalues[idx] = (val + 128) * 65536 / 256.0
            elif self._devicename == "XYZ":
                # X, Y. Z range 0..100 + (32767 / 32768.0)
                nc2value.devicevalues[idx] = val * 32768 / 100.0
            else:
                # Device range 0..100
                nc2value.devicevalues[idx] = val * 65535 / 100.0

        self[nc2value.name] = nc2value

    def __repr__(self) -> str:
        """Return the string representation of the object.

        Truncates the output if it exceeds the specified size.

        Returns:
            str: The string representation of the object.
        """
        data = list(self.items())[: self.REPR_OUTPUT_SIZE + 1]
        if len(data) > self.REPR_OUTPUT_SIZE:
            data[-1] = ("...", "(remaining elements truncated)")
        return repr(dict(data))

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: Raw tag data containing vendor data, color count,
                device coordinate count, prefix, suffix, and color values.
        """
        tagData = [  # noqa: N806
            b"ncl2",
            b"\0" * 4,
            self.vendorData,
            uInt32Number_tohex(len(list(self.items()))),
            uInt32Number_tohex(self.deviceCoordCount),
            self._prefix.ljust(32),
            self._suffix.ljust(32),
            self.colorValues.tagData,
        ]
        return b"".join(tagData)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        pass
