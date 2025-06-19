import sys

import pytest

from DisplayCAL import colormath
from DisplayCAL.cgats import CGATS
from DisplayCAL.colorspace_to_vrml import (
    CAT,
    ColorSpaceToVRML,
    DIN99bToVRML,
    DIN99cToVRML,
    DIN99dToVRML,
    DIN99ToVRML,
    HSIToVRML,
    HSLToVRML,
    HSVToVRML,
    ICtCpToVRML,
    IPTToVRML,
    LabToVRML,
    LCHabToVRML,
    LCHuvToVRML,
    LptToVRML,
    LuvPrimeToVRML,
    LuvToVRML,
    RGBToVRML,
    xyYToVRML,
)


@pytest.fixture(scope="module")
def get_cgats_data(data_files):
    """Return the CGATS data from the test data files."""
    cgats_path = data_files["profile_tags_targ.ti3"]  # cgats0_simple.txt"]
    cgats = CGATS(cgats=cgats_path)
    return cgats.queryv1("DATA")


def test_color_space_to_vrml_init_data_arg_sis_skipped():
    """ColorSpaceToVRML.__init__() data is skipped raises TypeError."""
    with pytest.raises(TypeError) as cm:
        _ = ColorSpaceToVRML(
            white_point=(0.9642, 1.0, 0.8249),
            cat=CAT.Bradford,
            rgb_black_offset=40,
            normalize_rgb_white=False,
        )

    assert str(cm.value) == (
        "__init__() missing 1 required positional argument: 'data'"
    )


def test_color_space_to_vrml_init_data_arg_is_none():
    """ColorSpaceToVRML.__init__() data is None raises TypeError."""
    with pytest.raises(TypeError) as cm:
        _ = ColorSpaceToVRML(
            data=None,
            white_point=(0.9642, 1.0, 0.8249),
            cat=CAT.Bradford,
            rgb_black_offset=40,
            normalize_rgb_white=False,
        )

    assert str(cm.value) == (
        "ColorSpaceToVRML.data must be a dictionary or a CGATS instance, "
        "not NoneType: None"
    )


def test_color_space_to_vrml_data_attr_is_none(get_cgats_data):
    """ColorSpaceToVRML.data is set to None raises TypeError."""
    colorspace_to_vrml = ColorSpaceToVRML(
        data=get_cgats_data,
        white_point=(0.9642, 1.0, 0.8249),
        cat=CAT.Bradford,
        rgb_black_offset=40,
        normalize_rgb_white=False,
    )
    with pytest.raises(TypeError) as cm:
        colorspace_to_vrml.data = None

    assert str(cm.value) == (
        "ColorSpaceToVRML.data must be a dictionary or a CGATS instance, "
        "not NoneType: None"
    )


def test_color_space_to_vrml_init_data_arg_is_a_dictionary(get_cgats_data):
    """ColorSpaceToVRML.__init__() data arg can be a dictionary."""
    cgats_data_as_dict = dict(get_cgats_data)
    assert isinstance(cgats_data_as_dict, dict)
    # this should not raise an error
    _ = ColorSpaceToVRML(
        data=cgats_data_as_dict,
        white_point=(0.9642, 1.0, 0.8249),
        cat=CAT.Bradford,
        rgb_black_offset=40,
        normalize_rgb_white=False,
    )


def test_color_space_to_vrml_data_attr_is_a_dictionary(get_cgats_data):
    """ColorSpaceToVRML.data is set to a dictionary."""
    cgats_data_as_dict = dict(get_cgats_data)
    assert isinstance(cgats_data_as_dict, dict)
    # this should not raise an error
    colorspace_to_vrml = ColorSpaceToVRML(
        data={"a": 1},
        white_point=(0.9642, 1.0, 0.8249),
        cat=CAT.Bradford,
        rgb_black_offset=40,
        normalize_rgb_white=False,
    )
    colorspace_to_vrml.data = cgats_data_as_dict
    assert colorspace_to_vrml.data == cgats_data_as_dict


def test_color_space_to_vrml_init_data_arg_is_a_cgats_instance(get_cgats_data):
    """ColorSpaceToVRML.__init__() data arg can be a CGATS instance."""
    cgats_data_as_cgats = get_cgats_data
    assert isinstance(cgats_data_as_cgats, CGATS)
    # this should not raise an error
    _ = ColorSpaceToVRML(
        data=cgats_data_as_cgats,
        white_point=(0.9642, 1.0, 0.8249),
        cat=CAT.Bradford,
        rgb_black_offset=40,
        normalize_rgb_white=False,
    )


def test_color_space_to_vrml_data_attr_is_a_cgats_instance(get_cgats_data):
    """ColorSpaceToVRML.data is set to a CGATS instance."""
    cgats_data_as_cgats = get_cgats_data
    assert isinstance(cgats_data_as_cgats, CGATS)
    colorspace_to_vrml = ColorSpaceToVRML(
        data={"a": 1},
        white_point=(0.9642, 1.0, 0.8249),
        cat=CAT.Bradford,
        rgb_black_offset=40,
        normalize_rgb_white=False,
    )
    colorspace_to_vrml.data = cgats_data_as_cgats
    assert colorspace_to_vrml.data == cgats_data_as_cgats


def test_color_space_to_vrml_init_data_arg_value_is_passed_to_the_data_attr(
    get_cgats_data,
):
    """ColorSpaceToVRML.__init__() data is passed to the data attribute."""
    test_data = get_cgats_data
    colorspace_to_vrml = ColorSpaceToVRML(
        data=test_data,
        white_point=(0.9642, 1.0, 0.8249),
        cat=CAT.Bradford,
        rgb_black_offset=40,
        normalize_rgb_white=False,
    )
    assert colorspace_to_vrml.data == test_data


def test_color_space_to_vrml_name_is_read_only(get_cgats_data):
    """ColorSpaceToVRML.name is read-only."""
    colorspace_to_vrml = ColorSpaceToVRML(
        data=get_cgats_data,
        white_point=(0.9642, 1.0, 0.8249),
        cat=CAT.Bradford,
        rgb_black_offset=40,
        normalize_rgb_white=False,
    )
    with pytest.raises(AttributeError) as cm:
        colorspace_to_vrml.name = "New Name"

    py_error_message = {
        9: "can't set attribute",
        10: "can't set attribute 'name'",
        11: "property 'name' of 'ColorSpaceToVRML' object has no setter",
        12: "property 'name' of 'ColorSpaceToVRML' object has no setter",
        13: "property 'name' of 'ColorSpaceToVRML' object has no setter",
    }[sys.version_info.minor]
    assert str(cm.value) == py_error_message


# ColorSpaceToVRML.cat


def test_color_space_to_vrml_cat_is_skipped(get_cgats_data):
    """ColorSpaceToVRML.cat is skipped uses Bradford as default."""
    colorspace_to_vrml = ColorSpaceToVRML(
        data=get_cgats_data,
        white_point=(0.9642, 1.0, 0.8249),
        rgb_black_offset=40,
        normalize_rgb_white=False,
    )
    assert colorspace_to_vrml.cat == CAT.Bradford


def test_color_space_to_vrml_cat_is_str(get_cgats_data):
    """ColorSpaceToVRML.cat is a string."""
    colorspace_to_vrml = ColorSpaceToVRML(
        data=get_cgats_data,
        white_point=(0.9642, 1.0, 0.8249),
        cat="XYZ Scaling",
        rgb_black_offset=40,
        normalize_rgb_white=False,
    )
    assert colorspace_to_vrml.cat == CAT.XYZ_Scaling


# ColorSpaceToVRML.name


@pytest.mark.parametrize(
    "colorspace_class, expected_name",
    [
        (DIN99bToVRML, "DIN99b"),
        (DIN99cToVRML, "DIN99c"),
        (DIN99dToVRML, "DIN99d"),
        (DIN99ToVRML, "DIN99"),
        (HSIToVRML, "HSI"),
        (HSLToVRML, "HSL"),
        (HSVToVRML, "HSV"),
        (ICtCpToVRML, "ICtCp"),
        (IPTToVRML, "IPT"),
        (LabToVRML, "Lab"),
        (LCHabToVRML, "LCH(ab)"),
        (LCHuvToVRML, "LCH(uv)"),
        (LptToVRML, "Lpt"),
        (LuvPrimeToVRML, "Lu'v'"),
        (LuvToVRML, "Luv"),
        (RGBToVRML, "RGB"),
        (xyYToVRML, "xyY"),
    ],
)
def test_color_space_to_vrml_name_is_correct(
    colorspace_class, expected_name, get_cgats_data
):
    """ColorSpaceToVRML.name is correct."""
    obj = colorspace_class(
        data=get_cgats_data,
        white_point=(0.9642, 1.0, 0.8249),
        cat=CAT.Bradford,
        rgb_black_offset=40,
        normalize_rgb_white=False,
    )
    assert obj.name == expected_name


@pytest.mark.parametrize(
    "colorspace_class, vrml_filename",
    (
        (DIN99bToVRML, "DIN99b.vrml"),
        (DIN99cToVRML, "DIN99c.vrml"),
        (DIN99dToVRML, "DIN99d.vrml"),
        (DIN99ToVRML, "DIN99.vrml"),
        (HSIToVRML, "HSI.vrml"),
        (HSLToVRML, "HSL.vrml"),
        (HSVToVRML, "HSV.vrml"),
        (ICtCpToVRML, "ICtCp.vrml"),
        (IPTToVRML, "IPT.vrml"),
        (LabToVRML, "Lab.vrml"),
        (LCHabToVRML, "LCHab.vrml"),
        (LCHuvToVRML, "LCHuv.vrml"),
        (LptToVRML, "Lpt.vrml"),
        (LuvPrimeToVRML, "LuvPrime.vrml"),
        (LuvToVRML, "Luv.vrml"),
        (RGBToVRML, "RGB.vrml"),
        (xyYToVRML, "xyY.vrml"),
    ),
)
def test_color_space_to_vrml_generate_vrml(
    colorspace_class,
    vrml_filename,
    get_cgats_data,
    data_files,
):
    """ColorSpaceToVRML.generate_vrml() returns a VRML string."""
    vrml_file_path = data_files[vrml_filename]
    with open(vrml_file_path, "r", encoding="utf-8") as f:
        expected_vrml = f.read()
    obj = colorspace_class(
        data=get_cgats_data,
        white_point=colormath.get_whitepoint("D50"),
        cat=CAT.Bradford,
        rgb_black_offset=40,
        normalize_rgb_white=False,
    )
    assert obj.vrml == ""
    obj.generate_vrml()
    assert obj.vrml == expected_vrml
