"""ICC profile tag type classes.

Submodules group tag types by kind (`base`, `curve`, `lut`, `colorant`, `text`,
`dict_type`, `video_card_gamma`, `named_color`, `wcs`). This package re-exports
every tag type class plus the `TAG_SIGNATURE_TO_TAG`/`TYPE_SIGNATURE_TO_TYPE`
registries used to look up a tag class from its signature.
"""

from __future__ import annotations

from DisplayCAL.icc_profile.codecs import videoCardGamma
from DisplayCAL.icc_profile.tags.base import (
    ChromaticAdaptionTag,
    DateTimeType,
    ICCProfileTag,
    LazyLoadTagAODict,
    S15Fixed16ArrayType,
    TagData,
    Text,
    XYZNumber,
    XYZType,
)
from DisplayCAL.icc_profile.tags.colorant import (
    ChromaticityType,
    Colorant,
    ColorantTableType,
    Geometry,
    Illuminant,
    MeasurementType,
    Observer,
    ProfileSequenceDescType,
    ViewingConditionsType,
)
from DisplayCAL.icc_profile.tags.curve import CurveType, ParametricCurveType
from DisplayCAL.icc_profile.tags.dict_type import DictType, DictTypeJSONEncoder
from DisplayCAL.icc_profile.tags.lut import LUT16Type
from DisplayCAL.icc_profile.tags.named_color import (
    NamedColor2Type,
    NamedColor2Value,
    NamedColor2ValueTuple,
)
from DisplayCAL.icc_profile.tags.text import (
    MakeAndModelType,
    MultiLocalizedUnicodeType,
    SignatureType,
    TextDescriptionType,
    TextType,
)
from DisplayCAL.icc_profile.tags.video_card_gamma import (
    VideoCardGammaFormulaType,
    VideoCardGammaTableType,
    VideoCardGammaType,
)
from DisplayCAL.icc_profile.tags.wcs import WcsProfilesTagType

TAG_SIGNATURE_TO_TAG = {"arts": ChromaticAdaptionTag, "chad": ChromaticAdaptionTag}

TYPE_SIGNATURE_TO_TYPE = {
    b"chrm": ChromaticityType,
    b"clrt": ColorantTableType,
    b"curv": CurveType,
    b"desc": TextDescriptionType,  # ICC v2
    b"dict": DictType,  # ICC v2 + v4
    b"dtim": DateTimeType,
    b"meas": MeasurementType,
    b"mluc": MultiLocalizedUnicodeType,  # ICC v4
    b"mft2": LUT16Type,
    b"mmod": MakeAndModelType,  # Apple private tag
    b"ncl2": NamedColor2Type,
    b"para": ParametricCurveType,
    b"pseq": ProfileSequenceDescType,
    b"sf32": S15Fixed16ArrayType,
    b"sig ": SignatureType,
    b"text": TextType,
    b"vcgt": videoCardGamma,
    b"view": ViewingConditionsType,
    b"MS10": WcsProfilesTagType,
    b"XYZ ": XYZType,
}

__all__ = [
    "TAG_SIGNATURE_TO_TAG",
    "TYPE_SIGNATURE_TO_TYPE",
    "ChromaticAdaptionTag",
    "ChromaticityType",
    "Colorant",
    "ColorantTableType",
    "CurveType",
    "DateTimeType",
    "DictType",
    "DictTypeJSONEncoder",
    "Geometry",
    "ICCProfileTag",
    "Illuminant",
    "LUT16Type",
    "LazyLoadTagAODict",
    "MakeAndModelType",
    "MeasurementType",
    "MultiLocalizedUnicodeType",
    "NamedColor2Type",
    "NamedColor2Value",
    "NamedColor2ValueTuple",
    "Observer",
    "ParametricCurveType",
    "ProfileSequenceDescType",
    "S15Fixed16ArrayType",
    "SignatureType",
    "TagData",
    "Text",
    "TextDescriptionType",
    "TextType",
    "VideoCardGammaFormulaType",
    "VideoCardGammaTableType",
    "VideoCardGammaType",
    "ViewingConditionsType",
    "WcsProfilesTagType",
    "XYZNumber",
    "XYZType",
]
