"""Classes for the various enums used in the Windows Color System API.

There are also some helper functions to convert between enum values and their
string representations.
"""

from enum import IntEnum, IntFlag, auto


class dwDeviceClass(IntEnum):  # noqa: N801
    """Available device classes to be used in the dwDeviceClass field."""

    CLASS_SCANNER = int.from_bytes(b"scnr", byteorder="big")
    CLASS_MONITOR = int.from_bytes(b"mntr", byteorder="big")
    CLASS_PRINTER = int.from_bytes(b"prtr", byteorder="big")


class dwFieldsUsed(IntFlag):  # noqa: N801
    """Available fields to be used in the ENUMTYPEW structure."""

    ET_DEVICENAME = 0x00000001
    ET_MEDIATYPE = 0x00000002
    ET_DITHERMODE = 0x00000004
    ET_RESOLUTION = 0x00000008
    ET_CMMTYPE = 0x00000010
    ET_CLASS = 0x00000020
    ET_DATACOLORSPACE = 0x00000040
    ET_CONNECTIONSPACE = 0x00000080
    ET_SIGNATURE = 0x00000100
    ET_PLATFORM = 0x00000200
    ET_PROFILEFLAGS = 0x00000400
    ET_MANUFACTURER = 0x00000800
    ET_MODEL = 0x00001000
    ET_ATTRIBUTES = 0x00002000
    ET_RENDERINGINTENT = 0x00004000
    ET_CREATOR = 0x00008000
    ET_DEVICECLASS = 0x00010000


class WCS_PROF_SCOPE(IntEnum):  # noqa: N801
    """Available profile scopes to be used in the WCS API."""

    SYSTEM_WIDE = 0
    CURRENT_USER = 1


class COLORPROFILETYPE(IntEnum):
    """Available color profile types to be used in the COLORPROFILETYPE field."""

    CPT_ICC = 0
    CPT_DMP = auto()
    CPT_CAMP = auto()
    CPT_GMMP = auto()


class COLORPROFILESUBTYPE(IntEnum):
    """Available color profile subtypes to be used in the COLORPROFILESUBTYPE field."""

    # intent
    CPST_PERCEPTUAL = 0
    CPST_RELATIVE_COLORIMETRIC = auto()
    CPST_SATURATION = auto()
    CPST_ABSOLUTE_COLORIMETRIC = auto()
    # working space
    CPST_NONE = auto()  # makes the API deduct profile subtype from the profile itself
    CPST_RGB_WORKING_SPACE = auto()
    CPST_CUSTOM_WORKING_SPACE = auto()
    CPST_STANDARD_DISPLAY_COLOR_MODE = auto()
    CPST_EXTENDED_DISPLAY_COLOR_MODE = auto()
