"""Module-level constants for ICC profile parsing and identification."""

from __future__ import annotations

from DisplayCAL.encoding import get_encodings

# Gamut volumes in cubic colorspace units (L*a*b*) as reported by Argyll's
# iccgamut
GAMUT_VOLUME_SRGB = 833675.435316  # rel. col.
GAMUT_VOLUME_ADOBERGB = 1209986.014983  # rel. col.%
GAMUT_VOLUME_SMPTE431_P3 = 1176953.485921  # rel. col.

# http://msdn.microsoft.com/en-us/library/dd371953%28v=vs.85%29.aspx
COLOR_PROFILE_SUBTYPE = {
    "NONE": 0x0000,
    "RGB_WORKING_SPACE": 0x0001,
    "PERCEPTUAL": 0x0002,
    "ABSOLUTE_COLORIMETRIC": 0x0004,
    "RELATIVE_COLORIMETRIC": 0x0008,
    "SATURATION": 0x0010,
    "CUSTOM_WORKING_SPACE": 0x0020,
}

# http://msdn.microsoft.com/en-us/library/dd371955%28v=vs.85%29.aspx (wrong)
# http://msdn.microsoft.com/en-us/library/windows/hardware/ff546018%28v=vs.85%29.aspx (ok)  # noqa: E501
COLOR_PROFILE_TYPE = {"ICC": 0, "DMP": 1, "CAMP": 2, "GMMP": 3}

WCS_PROFILE_MANAGEMENT_SCOPE = {"SYSTEM_WIDE": 0, "CURRENT_USER": 1}

ERROR_PROFILE_NOT_ASSOCIATED_WITH_DEVICE = 2015
ERROR_SUCCESS = 0

DEBUG = False

ENC, FS_ENC = get_encodings()

CMMS = {
    b"argl": "ArgyllCMS",
    b"ADBE": "Adobe",
    b"ACMS": "Agfa",
    b"Agfa": "Agfa",
    b"APPL": "Apple",
    b"appl": "Apple",
    b"CCMS": "ColorGear",
    b"UCCM": "ColorGear Lite",
    b"DL&C": "Digital Light & Color",
    b"EFI ": "EFI",
    b"FF  ": "Fuji Film",
    b"HCMM": "Harlequin RIP",
    b"LgoS": "LogoSync",
    b"HDM ": "Heidelberg",
    b"Lino": "Linotype",
    b"lino": "Linotype",
    b"lcms": "Little CMS",
    b"KCMS": "Kodak",
    b"MCML": "Konica Minolta",
    b"MSFT": "Microsoft",
    b"SIGN": "Mutoh",
    b"RGMS": "DeviceLink",
    b"SICC": "SampleICC",
    b"32BT": "the imaging factory",
    b"WTG ": "Ware to Go",
    b"zc00": "Zoran",
}

ENCODINGS = {
    "mac": {
        141: "africaans",
        36: "albanian",
        85: "amharic",
        12: "arabic",
        51: "armenian",
        68: "assamese",
        134: "aymara",
        49: "azerbaijani-cyrllic",
        50: "azerbaijani-arabic",
        129: "basque",
        67: "bengali",
        137: "dzongkha",
        142: "breton",
        44: "bulgarian",
        77: "burmese",
        46: "byelorussian",
        78: "khmer",
        130: "catalan",
        92: "chewa",
        33: "simpchinese",
        19: "tradchinese",
        18: "croatian",
        38: "czech",
        7: "danish",
        4: "dutch",
        0: "roman",
        94: "esperanto",
        27: "estonian",
        30: "faeroese",
        31: "farsi",
        13: "finnish",
        34: "flemish",
        1: "french",
        140: "galician",
        144: "scottishgaelic",
        145: "manxgaelic",
        52: "georgian",
        2: "german",
        14: "greek-monotonic",
        148: "greek-polytonic",
        133: "guarani",
        69: "gujarati",
        10: "hebrew",
        21: "hindi",
        26: "hungarian",
        15: "icelandic",
        81: "indonesian",
        143: "inuktitut",
        35: "irishgaelic",
        146: "irishgaelic-dotsabove",
        3: "italian",
        11: "japanese",
        138: "javaneserom",
        73: "kannada",
        61: "kashmiri",
        48: "kazakh",
        90: "kiryarwanda",
        54: "kirghiz",
        91: "rundi",
        23: "korean",
        60: "kurdish",
        79: "lao",
        131: "latin",
        28: "latvian",
        24: "lithuanian",
        43: "macedonian",
        93: "malagasy",
        83: "malayroman-latin",
        84: "malayroman-arabic",
        72: "malayalam",
        16: "maltese",
        66: "marathi",
        53: "moldavian",
        57: "mongolian",
        58: "mongolian-cyrillic",
        64: "nepali",
        9: "norwegian",
        71: "oriya",
        87: "oromo",
        59: "pashto",
        25: "polish",
        8: "portuguese",
        70: "punjabi",
        132: "quechua",
        37: "romanian",
        32: "russian",
        29: "sami",
        65: "sanskrit",
        42: "serbian",
        62: "sindhi",
        76: "sinhalese",
        39: "slovak",
        40: "slovenian",
        88: "somali",
        6: "spanish",
        139: "sundaneserom",
        89: "swahili",
        5: "swedish",
        82: "tagalog",
        55: "tajiki",
        74: "tamil",
        135: "tatar",
        75: "telugu",
        22: "thai",
        63: "tibetan",
        86: "tigrinya",
        147: "tongan",
        17: "turkish",
        56: "turkmen",
        136: "uighur",
        45: "ukrainian",
        20: "urdu",
        47: "uzbek",
        80: "vietnamese",
        128: "welsh",
        41: "yiddish",
    }
}

COLORANTS = {
    0: {"description": "unknown", "channels": ()},
    1: {
        "description": "ITU-R BT.709",
        "channels": ((0.64, 0.33), (0.3, 0.6), (0.15, 0.06)),
    },
    2: {
        "description": "SMPTE RP145-1994",
        "channels": ((0.63, 0.34), (0.31, 0.595), (0.155, 0.07)),
    },
    3: {
        "description": "EBU Tech.3213-E",
        "channels": ((0.64, 0.33), (0.29, 0.6), (0.15, 0.06)),
    },
    4: {
        "description": "P22",
        "channels": ((0.625, 0.34), (0.28, 0.605), (0.155, 0.07)),
    },
}

GEOMETRY = {0: "unknown", 1: "0/45 or 45/0", 2: "0/d or d/0"}

ILLUMINANTS = {
    0: "unknown",
    1: "D50",
    2: "D65",
    3: "D93",
    4: "F2",
    5: "D55",
    6: "A",
    7: "E",
    8: "F8",
}

OBSERVERS = {0: "unknown", 1: "CIE 1931", 2: "CIE 1964"}

MANUFACTURERS = {
    b"ADBE": "Adobe Systems Incorporated",
    b"APPL": "Apple Computer, Inc.",
    b"agfa": "Agfa Graphics N.V.",
    b"argl": "ArgyllCMS",  # Not registered
    b"DCAL": "DisplayCAL",  # Not registered
    b"bICC": "basICColor GmbH",
    b"DL&C": "Digital Light & Color",
    b"EPSO": "Seiko Epson Corporation",
    b"HDM ": "Heidelberger Druckmaschinen AG",
    b"HP  ": "Hewlett-Packard",
    b"KODA": "Kodak",
    b"lcms": "Little CMS",
    b"MONS": "Monaco Systems Inc.",
    b"MSFT": "Microsoft Corporation",
    b"qato": "QUATOGRAPHIC Technology GmbH",
    b"XRIT": "X-Rite",
}

PLATFORM = {
    b"APPL": "Apple",
    b"MSFT": "Microsoft",
    b"SGI ": "Silicon Graphics",
    b"SUNW": "Sun Microsystems",
}

PROFILE_CLASS = {
    b"scnr": "Input device profile",
    b"mntr": "Display device profile",
    b"prtr": "Output device profile",
    b"link": "DeviceLink profile",
    b"spac": "Color space Conversion profile",
    b"abst": "Abstract profile",
    b"nmcl": "Named color profile",
}

TAGS = {
    "A2B0": "Device to PCS: Intent 0",
    "A2B1": "Device to PCS: Intent 1",
    "A2B2": "Device to PCS: Intent 2",
    "B2A0": "PCS to device: Intent 0",
    "B2A1": "PCS to device: Intent 1",
    "B2A2": "PCS to device: Intent 2",
    "CIED": "Characterization measurement values",  # Non-standard
    "DevD": "Characterization device values",  # Non-standard
    "arts": "Absolute to media relative transform",  # Non-standard (Argyll)
    "bkpt": "Media black point",
    "bTRC": "Blue tone response curve",
    "bXYZ": "Blue matrix column",
    "chad": "Chromatic adaptation transform",
    "ciis": "Colorimetric intent image state",
    "clro": "Colorant order",
    "cprt": "Copyright",
    "desc": "Description",
    "dmnd": "Device manufacturer name",
    "dmdd": "Device model name",
    "gamt": "Out of gamut tag",
    "gTRC": "Green tone response curve",
    "gXYZ": "Green matrix column",
    "kTRC": "Gray tone response curve",
    "lumi": "Luminance",
    "meas": "Measurement type",
    "mmod": "Make and model",
    "ncl2": "Named colors",
    "pseq": "Profile sequence description",
    "rTRC": "Red tone response curve",
    "rXYZ": "Red matrix column",
    "targ": "Characterization target",
    "tech": "Technology",
    "vcgt": "Video card gamma table",
    "view": "Viewing conditions",
    "vued": "Viewing conditions description",
    "wtpt": "Media white point",
}

TECH = {
    "fscn": "Film scanner",
    "dcam": "Digital camera",
    "rscn": "Reflective scanner",
    "ijet": "Ink jet printer",
    "twax": "Thermal wax printer",
    "epho": "Electrophotographic printer",
    "esta": "Electrostatic printer",
    "dsub": "Dye sublimation printer",
    "rpho": "Photographic paper printer",
    "fprn": "Film writer",
    "vidm": "Video monitor",
    "vidc": "Video camera",
    "pjtv": "Projection television",
    "CRT ": "Cathode ray tube display",
    "PMD ": "Passive matrix display",
    "AMD ": "Active matrix display",
    "KPCD": "Photo CD",
    "imgs": "Photographic image setter",
    "grav": "Gravure",
    "offs": "Offset lithography",
    "silk": "Silkscreen",
    "flex": "Flexography",
    "mpfs": "Motion picture film scanner",
    "mpfr": "Motion picture film recorder",
    "dmpc": "Digital motion picture camera",
    "dcpj": "Digital cinema projector",
}

CIIS = {
    "scoe": "Scene colorimetry estimates",
    "sape": "Scene appearance estimates",
    "fpce": "Focal plane colorimetry estimates",
    "rhoc": "Reflection hardcopy original colorimetry",
    "rpoc": "Reflection print output colorimetry",
}
