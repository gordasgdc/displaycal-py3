"""Binary/numeric codecs for encoding and decoding ICC profile data.

These are pure conversions between Python values and the fixed-width binary
representations used throughout the ICC profile format (uInt8/16/32/64Number,
s15Fixed16Number, u8Fixed8Number, u16Fixed16Number, dateTimeNumber, etc).
"""

from __future__ import annotations

import binascii
import datetime
import re
import struct
from typing import TYPE_CHECKING, Callable

from DisplayCAL import colormath

if TYPE_CHECKING:
    from DisplayCAL.icc_profile.tags.video_card_gamma import (
        VideoCardGammaFormulaType,
        VideoCardGammaTableType,
    )


def legacy_PCSLab_dec_to_uInt16(L: float, a: float, b: float) -> list[int]:  # noqa: N802, N803
    """Convert ICCv2 (legacy) PCS L*a*b* float values to int.

    Only used by LUT16Type and namedColor2Type in ICCv4.

    Args:
        L (float): L* value in float format.
        a (float): a* value in float format.
        b (float): b* value in float format.

    Returns:
        list[int]: List of int values representing L*, a*, and b* in 16-bit.
    """
    return [
        v * (652.80, 256, 256)[i] + (0, 32768, 32768)[i]
        for i, v in enumerate((L, a, b))
    ]


def legacy_PCSLab_uInt16_to_dec(  # noqa: N802
    L_uInt16: int,  # noqa: N803
    a_uInt16: int,  # noqa: N803
    b_uInt16: int,  # noqa: N803
) -> list[float]:
    """Convert ICCv2 (legacy) PCS L*a*b* to float values.

    Args:
        L_uInt16 (int): L* value in 16-bit unsigned integer format.
        a_uInt16 (int): a* value in 16-bit unsigned integer format.
        b_uInt16 (int): b* value in 16-bit unsigned integer format.

    Returns:
        list: List of float values representing L*, a*, and b*.
    """
    # ICCv2 (legacy) PCS L*a*b* encoding
    # Only used by LUT16Type and namedColor2Type in ICCv4
    return [
        (v - (0, 32768, 32768)[i]) / (65280.0, 32768.0, 32768.0)[i] * (100, 128, 128)[i]
        for i, v in enumerate((L_uInt16, a_uInt16, b_uInt16))
    ]


def hexrepr(bytestring: bytes, mapping: None | dict = None) -> str:
    """Generate hex representation of a bytes instance.

    Args:
        bytestring (bytes): The bytes to convert.
        mapping (dict): A dictionary to map the ASCII representation to
            a string.

    Returns:
        str: The hex representation of the bytes.
    """
    hex_repr = (b"0x%s" % binascii.hexlify(bytestring).upper()).decode()
    ascii_repr = re.sub(b"[^\x20-\x7e]", b"", bytestring)
    if ascii_repr == bytestring:
        hex_repr += f" '{ascii_repr.decode()}'"
        if mapping:
            value = mapping.get(ascii_repr)
            if value:
                hex_repr = f"{hex_repr} {value}"
    return hex_repr


def dateTimeNumber(binary_string: bytes) -> datetime.datetime:  # noqa: N802
    """Convert a 12-byte hex representation to a datetime object.

    Byte
    Offset Content                                     Encoded as...
    0..1   number of the year (actual year, e.g. 1994) uInt16Number
    2..3   number of the month (1-12)                  uInt16Number
    4..5   number of the day of the month (1-31)       uInt16Number
    6..7   number of hours (0-23)                      uInt16Number
    8..9   number of minutes (0-59)                     uInt16Number
    10..11 number of seconds (0-59)                     uInt16Number

    Args:
        binary_string (bytes): A 12 character long bytes value representing a
            datetime value.

    Returns:
        datetime: The datetime object represented by the hex.
    """
    Y, m, d, H, M, S = [  # noqa: N806
        uInt16Number(chunk)
        for chunk in (
            binary_string[:2],
            binary_string[2:4],
            binary_string[4:6],
            binary_string[6:8],
            binary_string[8:10],
            binary_string[10:12],
        )
    ]
    return datetime.datetime(*(Y, m, d, H, M, S))


def dateTimeNumber_tohex(dt: datetime.datetime) -> bytes:  # noqa: N802
    """Convert a datetime object to a 12-byte hex representation.

    Args:
        dt (datetime): The datetime object to convert.

    Returns:
        bytes: The 12-byte hex representation of the datetime.
    """
    data = [uInt16Number_tohex(n) for n in dt.timetuple()[:6]]
    return b"".join(data)


def s15Fixed16Number(binaryString: bytes) -> float:  # noqa: N802, N803
    """Convert a 4-byte hex representation to a float.

    Args:
        binaryString (bytes): The 4-byte hex representation.

    Returns:
        float: The number represented by the hex.
    """
    return struct.unpack(">i", binaryString)[0] / 65536.0


def s15Fixed16Number_tohex(num: int) -> bytes:  # noqa: N802
    """Convert a number to a 4-byte hex representation.

    Args:
        num (int): The number to convert.

    Returns:
        bytes: The 4-byte hex representation of the number.
    """
    return struct.pack(">i", round(num * 65536))


def s15f16_is_equal(a: bytes, b: bytes, quantizer: None | Callable = None) -> bool:
    """Compare two s15Fixed16Number values.

    Args:
        a (bytes): First value.
        b (bytes): Second value.
        quantizer (Optional[callable]): A callable to quantize the values.
            Defaults to None.

    Returns:
        bool: True if the values are equal, False otherwise.
    """
    if quantizer is None:

        def quantizer(v: int) -> float:
            """Default quantizer for s15Fixed16Number.

            Args:
                v (int): The value to quantize.

            Returns:
                float: The quantized value.
            """
            return s15Fixed16Number(s15Fixed16Number_tohex(v))

    return colormath.is_equal(a, b, quantizer)


def u16Fixed16Number(binaryString: bytes) -> int:  # noqa: N802, N803
    """Convert a 2-byte hex representation to a number.

    Args:
        binaryString (bytes): The 2-byte hex representation.

    Returns:
        int: The number represented by the hex.
    """
    return struct.unpack(">I", binaryString)[0] / 65536.0


def u16Fixed16Number_tohex(num: int) -> bytes:  # noqa: N802
    """Convert a number to a 2-byte hex representation.

    Args:
        num (int): The number to convert.

    Returns:
        bytes: The 2-byte hex representation of the number.
    """
    return struct.pack(">I", round(num * 65536) & 0xFFFFFFFF)


def u8Fixed8Number(binaryString: bytes) -> int:  # noqa: N802, N803
    """Convert a 1-byte hex representation to a number.

    Args:
        binaryString (bytes): The 1-byte hex representation.

    Returns:
        int: The number represented by the hex.
    """
    return struct.unpack(">H", binaryString)[0] / 256.0


def u8Fixed8Number_tohex(num: int) -> bytes:  # noqa: N802
    """Convert a number to a 1-byte hex representation.

    Args:
        num (int): The number to convert.

    Returns:
        bytes: The 1-byte hex representation of the number.
    """
    return struct.pack(">H", round(num * 256))


def uInt16Number(binaryString: bytes) -> int:  # noqa: N802, N803
    """Convert a 2-byte hex representation to a number.

    Args:
        binaryString (bytes): The 2-byte hex representation.

    Returns:
        int: The number represented by the hex.
    """
    return struct.unpack(">H", binaryString)[0]


def uInt16Number_tohex(num: int) -> bytes:  # noqa: N802
    """Convert a number to a 2-byte hex representation.

    Args:
        num (int): The number to convert.

    Returns:
        bytes: The 2-byte hex representation of the number.
    """
    return struct.pack(">H", round(num))  # num can be float despite the type hint


def uInt32Number(binaryString: bytes) -> int:  # noqa: N802, N803
    """Convert a 4-byte hex representation to a number.

    Args:
        binaryString (bytes): The 4-byte hex representation.

    Returns:
        int: The number represented by the hex.
    """
    return struct.unpack(">I", binaryString)[0]


def uInt32Number_tohex(num: int) -> bytes:  # noqa: N802
    """Convert a number to a 4-byte hex representation.

    Args:
        num (int): The number to convert.

    Returns:
        bytes: The 4-byte hex representation of the number.
    """
    return struct.pack(">I", round(num))  # num can be float despite the type hint


def uInt64Number(binaryString: bytes) -> int:  # noqa: N802, N803
    """Convert a 8-byte hex representation to a number.

    Args:
        binaryString (bytes): The 8-byte hex representation.

    Returns:
        int: The number represented by the hex.
    """
    return struct.unpack(">Q", binaryString)[0]


def uInt64Number_tohex(num: int) -> bytes:  # noqa: N802
    """Convert a number to a 8-byte hex representation.

    Args:
        num (int): The number to convert.

    Returns:
        bytes: The 8-byte hex representation of the number.
    """
    return struct.pack(">Q", round(num))  # num can be float despite the type hint


def uInt8Number(binaryString: bytes) -> int:  # noqa: N802, N803
    """Convert a 1-byte hex representation to a number.

    Args:
        binaryString (bytes): The 1-byte hex representation.

    Returns:
        int: The number represented by the hex.
    """
    return struct.unpack(">H", b"\0" + binaryString)[0]


def uInt8Number_tohex(num: int) -> bytes:  # noqa: N802
    """Convert a number to a 1-byte hex representation.

    Args:
        num (int): The number to convert.

    Returns:
        bytes: The 1-byte hex representation of the number.
    """
    return struct.pack(">H", round(num))[1:2]  # num can be float despite the type hint


def videoCardGamma(  # noqa: N802
    tagData: bytes,  # noqa: N803
    tagSignature: str,  # noqa: N803
) -> None | VideoCardGammaTableType | VideoCardGammaFormulaType:
    """Generate a VideoCardGammaTableType or VideoCardGammaFormulaType tag.

    Args:
        tagData (bytes): The raw tag data containing the video LUT curves.
        tagSignature (str): The signature of the tag, typically "vcgt".

    Returns:
        None | VideoCardGammaTableType | VideoCardGammaFormulaType: The parsed
            tag data as a VideoCardGammaTableType or VideoCardGammaFormulaType
            object, or None if the tag type is not recognized.
    """
    # Deferred import: avoids a circular import with the tag classes, which
    # themselves live downstream of these codecs.
    from DisplayCAL.icc_profile import (
        VideoCardGammaFormulaType,
        VideoCardGammaTableType,
    )

    # reserved = uInt32Number(tagData[4:8])
    tag_type = uInt32Number(tagData[8:12])
    if tag_type == 0:  # table
        return VideoCardGammaTableType(tagData, tagSignature)
    if tag_type == 1:  # formula
        return VideoCardGammaFormulaType(tagData, tagSignature)
    return None
