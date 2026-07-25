"""ICC profile utilities for color management across devices.

ICC profiles describe device or color space color characteristics for
consistent color reproduction. This module provides, utilities for parsing,
validating, and manipulating ICC profile data.
"""

from __future__ import annotations

from DisplayCAL.icc_profile.codecs import (
    dateTimeNumber,
    dateTimeNumber_tohex,
    hexrepr,
    s15f16_is_equal,
    s15Fixed16Number,
    s15Fixed16Number_tohex,
    uInt8Number_tohex,
    uInt16Number_tohex,
    uInt32Number,
    uInt32Number_tohex,
)
from DisplayCAL.icc_profile.constants import (
    CIIS,
    CMMS,
    DEBUG,
    ENC,
    ENCODINGS,
    ERROR_PROFILE_NOT_ASSOCIATED_WITH_DEVICE,
    ERROR_SUCCESS,
    GAMUT_VOLUME_ADOBERGB,
    GAMUT_VOLUME_SMPTE431_P3,
    GAMUT_VOLUME_SRGB,
    MANUFACTURERS,
    PLATFORM,
    PROFILE_CLASS,
    TAGS,
    TECH,
)
from DisplayCAL.icc_profile.display_profile import (
    _winreg_get_display_profiles,
    get_display_profile,
    get_display_profile_linux,
    get_display_profile_macos,
    get_display_profile_windows,
    set_display_profile,
    unset_display_profile,
)
from DisplayCAL.icc_profile.profile import ICCProfile, ICCProfileInvalidError
from DisplayCAL.icc_profile.structures import (
    ADict,
    AODict,
    CRInterpolation,
    DictList,
    DictListItem,
)
from DisplayCAL.icc_profile.synthetic import (
    create_RGB_A2B_XYZ,
    create_synthetic_clut_profile,
    create_synthetic_hdr_clut_profile,
    create_synthetic_hlg_clut_profile,
    create_synthetic_smpte2084_clut_profile,
)
from DisplayCAL.icc_profile.tags import (
    TAG_SIGNATURE_TO_TAG,
    TYPE_SIGNATURE_TO_TYPE,
    ChromaticAdaptionTag,
    ChromaticityType,
    Colorant,
    ColorantTableType,
    CurveType,
    DateTimeType,
    DictType,
    DictTypeJSONEncoder,
    Geometry,
    ICCProfileTag,
    Illuminant,
    LazyLoadTagAODict,
    LUT16Type,
    MakeAndModelType,
    MeasurementType,
    MultiLocalizedUnicodeType,
    NamedColor2Type,
    NamedColor2Value,
    NamedColor2ValueTuple,
    Observer,
    ParametricCurveType,
    ProfileSequenceDescType,
    S15Fixed16ArrayType,
    SignatureType,
    TagData,
    Text,
    TextDescriptionType,
    TextType,
    VideoCardGammaFormulaType,
    VideoCardGammaTableType,
    VideoCardGammaType,
    ViewingConditionsType,
    WcsProfilesTagType,
    XYZNumber,
    XYZType,
)
from DisplayCAL.icc_profile.tonemap import _mp_apply
