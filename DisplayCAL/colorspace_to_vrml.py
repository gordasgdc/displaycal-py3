"""Colorspace to VRML conversion for DisplayCAL."""

from __future__ import annotations

import math
import os
from enum import Enum
from typing import TYPE_CHECKING

from DisplayCAL import colormath, x3dom
from DisplayCAL.log import safe_print
from DisplayCAL.util_io import GzipFileProper

if TYPE_CHECKING:
    from pathlib import Path

    from DisplayCAL.cgats import CGATS


class CAT(Enum):
    """Chromatic adaptation transform (CAT) enumeration."""

    Bradford = "Bradford"
    BS = "BS"
    BS_PC = "BS-PC"
    CAT02 = "CAT02"
    CAT02BS = "CAT02BS"
    CAT97s = "CAT97s"
    CIE2012_2 = "CIE2012_2"
    CMCCAT2000 = "CMCCAT2000"
    HPE_D65 = "HPE D65"
    HPE_E = "HPE E"
    IPT = "IPT"
    Sharp = "Sharp"
    XYZ_Scaling = "XYZ scaling"

    def __str__(self) -> str:
        """Get the string representation of the CAT."""
        return self.value

    @classmethod
    def to_cat(cls, cat: str | CAT) -> CAT:
        """Convert the given cat value to a CAT enum.

        Args:
            cat (str | CAT): The value to convert to a CAT.

        Raises:
            TypeError: Input value type is invalid.
            ValueError: Input value is invalid.

        Returns:
            CAT: The enum.
        """
        valid_values = sorted(set([c.name for c in cls] + [c.value for c in cls]))
        if not isinstance(cat, (str, CAT)):
            raise TypeError(
                f"cat should be a CAT enum value or one of {valid_values}, "
                f"not {cat.__class__.__name__}: '{cat}'"
            )
        if isinstance(cat, str):
            cat_name_lut = {c.name.lower(): c.name for c in cls}
            cat_name_lut.update({c.value.lower(): c.name for c in cls})
            cat_lower_case = cat.lower()
            if cat_lower_case not in cat_name_lut:
                raise ValueError(
                    f"cat should be a CAT enum value or one of {valid_values}, "
                    f"not '{cat}'"
                )

            return cls.__members__[cat_name_lut[cat_lower_case]]

        return cat


class ColorSpace(Enum):
    """Color space enumeration."""

    DIN99 = "DIN99"
    DIN99b = "DIN99b"
    DIN99c = "DIN99c"
    DIN99d = "DIN99d"
    HSI = "HSI"
    HSL = "HSL"
    HSV = "HSV"
    ICtCp = "ICtCp"
    IPT = "IPT"
    Lab = "Lab"
    LCHab = "LCH(ab)"
    LCHuv = "LCH(uv)"
    Lpt = "Lpt"
    LuvPrime = "Lu'v'"
    Luv = "Luv"
    RGB = "RGB"
    xyY = "xyY"  # noqa: N815

    def __str__(self) -> str:
        """Get the string representation of the ColorSpace."""
        return self.value

    @classmethod
    def to_colorspace(cls, colorspace: str | ColorSpace) -> ColorSpace:
        """Convert the given colorspace value to a ColorSpace enum.

        Args:
            colorspace (str | ColorSpace): The value to convert to a ColorSpace.

        Raises:
            TypeError: Input value type is invalid.
            ValueError: Input value is invalid.

        Returns:
            ColorSpace: The enum.
        """
        valid_values = sorted(set([c.name for c in cls] + [c.value for c in cls]))
        if not isinstance(colorspace, (str, ColorSpace)):
            raise TypeError(
                "colorspace should be a ColorSpace enum value or one of "
                f"{valid_values}, not {colorspace.__class__.__name__}: '{colorspace}'"
            )
        if isinstance(colorspace, str):
            colorspace_name_lut = {c.name.lower(): c.name for c in cls}
            colorspace_name_lut.update({c.value.lower(): c.name for c in cls})
            colorspace_lower_case = colorspace.lower()
            if colorspace_lower_case not in colorspace_name_lut:
                raise ValueError(
                    "colorspace should be a ColorSpace enum value or one of "
                    f"{valid_values}, not '{colorspace}'"
                )

            return cls.__members__[colorspace_name_lut[colorspace_lower_case]]

        return colorspace

    def __eq__(self, other: object) -> bool:
        """Check equality with another ColorSpace or string.

        Args:
            other (object): The object to compare with.

        Returns:
            bool: True if equal, False otherwise.
        """
        if isinstance(other, str):
            return (
                self.value.lower() == other.lower()
                or self.name.lower() == other.lower()
            )
        if isinstance(other, ColorSpace):
            return self.value == other.value
        return False


class ColorSpaceToVRML:
    """Color space class for easy VRML.

    Args:
        data (dict | CGATS): The color data to be processed, could be a
            dictionary or a CGATS instance containing color values ("DATA").
        white_point (tuple[float, float, float]): The white point for the color
            space.
        cat (str): The chromatic adaptation transform to use. Defaults to
            "Bradford".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to
            40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to
            False.
    """

    sqrt3_100 = math.sqrt(3) * 100
    sqrt3_50 = math.sqrt(3) * 50

    VALID_COLOR_SPACE_NAMES = tuple(c.value for c in ColorSpace)

    VRML_TEMPLATE = """#VRML V2.0 utf8

Transform {{
    children [

        NavigationInfo {{
            type "EXAMINE"
        }}

        DirectionalLight {{
            direction 0 0 -1
            direction 0 -1 0
        }}

        Viewpoint {{
            fieldOfView {fov}
            position 0 0 {offset_z}
        }}

        {axes}
{children}
    ]
}}
"""

    VRML_CHILD_TEMPLATE = """       # Sphere
        Transform {{
            translation {offset_x:.6f} {offset_y:.6f} {offset_z:.6f}
            children [
                Shape{{
                    geometry Sphere {{ radius {radius:.6f} }}
                    appearance Appearance {{ material Material {{ diffuseColor {R:.6f} {G:.6f} {B:.6f} }} }}
                }}
            ]
        }}
"""  # noqa: E501

    VRML_AXES_TEMPLATE = """        Transform {{
            translation {hundredth_scale:.1f} {hundredth_scale:.1f} -50.0
            children [
                Shape {{
                    geometry Text {{
                        string ["{colorspace}"]
                        fontStyle FontStyle {{ family "SANS" style "BOLD" size {tenth_scale:.1f} }}
                    }}
                    appearance Appearance {{
                        material Material {{ diffuseColor 0.7 0.7 0.7 }}
                    }}
                }}
            ]
        }}
"""  # noqa: E501

    VRML_AXES_TEMPLATE2 = """        # L* axis
        Transform {{
            translation 0.0 0.0 0.0
            children [
                Shape {{
                    geometry Box {{ size {wh:.1f} {wh:.1f} 100.0 }}
                    appearance Appearance {{
                        material Material {{ diffuseColor 0.7 0.7 0.7 }}
                    }}
                }}
            ]
        }}
        # L* axis label
        Transform {{
            translation -{Ln:.1f} -{wh:.1f} 55.0
            children [
                Shape {{
                    geometry Text {{
                        string [{pllabel}]
                        fontStyle FontStyle {{ family "SANS" style "BOLD" size {fontsize:.1f} }}
                    }}
                    appearance Appearance {{
                        material Material {{ diffuseColor 0.7 0.7 0.7}}
                    }}
                }}
            ]
        }}
        # +x axis
        Transform {{
            translation {aboffset:.1f} 0.0 -50.0
            children [
                Shape {{
                    geometry Box {{ size {ab:.1f} {wh:.1f} {wh:.1f} }}
                    appearance Appearance {{
                        material Material {{ diffuseColor {pxcolor} }}
                    }}
                }}
            ]
        }}
        # +x axis label
        Transform {{
            translation {ap:.1f} -{wh:.1f} -50.0
            children [
                Shape {{
                    geometry Text {{
                        string [{pxlabel}]
                        fontStyle FontStyle {{ family "SANS" style "BOLD" size {fontsize:.1f} }}
                    }}
                    appearance Appearance {{
                        material Material {{ diffuseColor {pxcolor} }}
                    }}
                }}
            ]
        }}
        # -x axis
        Transform {{
            translation -{aboffset:.1f} 0.0 -50.0
            children [
                Shape {{
                    geometry Box {{ size {ab:.1f} {wh:.1f} {wh:.1f} }}
                    appearance Appearance {{
                        material Material {{ diffuseColor {nxcolor} }}
                    }}
                }}
            ]
        }}
        # -x axis label
        Transform {{
            translation -{an:.1f} -{wh:.1f} -50.0
            children [
                Shape {{
                    geometry Text {{
                        string [{nxlabel}]
                        fontStyle FontStyle {{ family "SANS" style "BOLD" size {fontsize:.1f} }}
                    }}
                    appearance Appearance {{
                        material Material {{ diffuseColor {nxcolor} }}
                    }}
                }}
            ]
        }}
        # +y axis
        Transform {{
            translation 0.0 {aboffset:.1f} -50.0
            children [
                Shape {{
                    geometry Box {{ size {wh:.1f} {ab:.1f} {wh:.1f} }}
                    appearance Appearance {{
                        material Material {{ diffuseColor {pycolor} }}
                    }}
                }}
            ]
        }}
        # +y axis label
        Transform {{
            translation -{bp0:.1f} {bp1:.1f} -50.0
            children [
                Shape {{
                    geometry Text {{
                        string [{pylabel}]
                        fontStyle FontStyle {{ family "SANS" style "BOLD" size {fontsize:.1f} }}
                    }}
                    appearance Appearance {{
                        material Material {{ diffuseColor {pycolor} }}
                    }}
                }}
            ]
        }}
        # -y axis
        Transform {{
            translation 0.0 -{aboffset:.1f} -50.0
            children [
                Shape {{
                    geometry Box {{ size {wh:.1f} {ab:.1f} {wh:.1f} }}
                    appearance Appearance {{
                        material Material {{ diffuseColor {nycolor} }}
                    }}
                }}
            ]
        }}
        # -y axis label
        Transform {{
            translation -{bn0:.1f} -{bn1:.1f} -50.0
            children [
                Shape {{
                    geometry Text {{
                        string [{nylabel}]
                        fontStyle FontStyle {{ family "SANS" style "BOLD" size {fontsize:.1f} }}
                    }}
                    appearance Appearance {{
                        material Material {{ diffuseColor {nycolor} }}
                    }}
                }}
            ]
        }}
        # Zero
        Transform {{
            translation -{Ln:.1f} -{wh:.1f} -55.0
            children [
                Shape {{
                    geometry Text {{
                        string ["0"]
                        fontStyle FontStyle {{ family "SANS" style "BOLD" size {fontsize:.1f} }}
                    }}
                    appearance Appearance {{
                        material Material {{ diffuseColor 0.7 0.7 0.7}}
                    }}
                }}
            ]
        }}
"""  # noqa: E501

    def __init__(
        self,
        data: dict | CGATS,
        white_point: tuple[float, float, float],
        cat: str | CAT = CAT.Bradford,
        rgb_black_offset: float = 40,
        normalize_rgb_white: bool = False,
    ) -> None:
        self._data = None
        self._cat = None
        self.X = None
        self.Y = None
        self.Z = None
        self.L = None
        self.a = None
        self.b = None
        self.white_point = white_point
        self.cat = cat
        self.data = data
        self.extra_offset_x = 0.0
        self.extra_offset_y = 0.0
        self.scale = 1.0
        self.radius = 15.0 / (len(self.data) ** (1.0 / 3.0))
        self.max_z = 1.0
        self.max_xy = 200
        self.axes = ""
        self.vrml = ""
        self.children = []
        self.rgb_black_offset = rgb_black_offset
        self.normalize_rgb_white = normalize_rgb_white
        self.fov = 45
        self.offset_z = 340

    @property
    def colorspace(self) -> str:
        """Get the name of the color space.

        Returns:
            str: The name of the color space.
        """
        return ColorSpace.to_colorspace(self.__class__.__name__.replace("ToVRML", ""))

    @property
    def data(self) -> list:
        """Get the color data.

        Returns:
            list: The color data.
        """
        return self._data

    @data.setter
    def data(self, data: list) -> None:
        """Set the color data.

        Args:
            data (list): The color data to be set.
        """
        from DisplayCAL.cgats import CGATS

        if not isinstance(data, (dict, CGATS)):
            raise TypeError(
                f"{self.__class__.__name__}.data must be a dictionary or a "
                f"CGATS instance, not {data.__class__.__name__}: {data}"
            )
        self._data = data

    @property
    def cat(self) -> CAT:
        """Get the chromatic adaptation transform (CAT).

        Returns:
            CAT: The CAT enum.
        """
        return self._cat

    @cat.setter
    def cat(self, cat: str | CAT) -> None:
        """Set the chromatic adaptation transform (CAT).

        Args:
            cat (str | CAT): The CAT to be set.
        """
        self._cat = CAT.to_cat(cat)

    def calculate_xyz_and_lab(self, entry: dict) -> None:
        """Calculate XYZ and Lab values from the white point and CAT info.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.
        """
        self.X, self.Y, self.Z = colormath.adapt(
            entry["XYZ_X"],
            entry["XYZ_Y"],
            entry["XYZ_Z"],
            self.white_point,
            "D65" if isinstance(self, (ICtCpToVRML, IPTToVRML)) else "D50",
            cat=str(self.cat),
        )
        self.L, self.a, self.b = colormath.XYZ2Lab(self.X, self.Y, self.Z)

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        raise NotImplementedError("This method should be overridden in subclasses.")

    def generate_vrml_axes(self) -> None:
        """Get the VRML axis representation for the color space."""

    def generate_vrml_children(self) -> None:
        """Generate VRML children for the color space."""
        self.children = []
        for entry in self.data.values():
            self.calculate_xyz_and_lab(entry)
            offset_x, offset_y, offset_z = self.get_offsets(entry)

            h_ref = s_ref = 0.0
            if self.rgb_black_offset != 40:
                # Keep reference hue and saturation
                # Lab to sRGB using reference black offset of 40 like Argyll CMS
                r, g, b = colormath.Lab2RGB(
                    self.L * (100.0 - 40.0) / 100.0 + 40.0,
                    self.a,
                    self.b,
                    scale=0.7,
                    noadapt=not self.normalize_rgb_white,
                )
                h_ref, s_ref, _ = colormath.RGB2HSV(r, g, b)
                # Lab to sRGB using actual black offset
            r, g, b = colormath.Lab2RGB(
                self.L * (100.0 - self.rgb_black_offset) / 100.0
                + self.rgb_black_offset,
                self.a,
                self.b,
                scale=0.7,
                noadapt=not self.normalize_rgb_white,
            )
            if self.rgb_black_offset != 40:
                _, _, v = colormath.RGB2HSV(r, g, b)
                # Use reference H and S to go back to RGB
                r, g, b = colormath.HSV2RGB(h_ref, s_ref, v)

            child = self.VRML_CHILD_TEMPLATE.format(
                offset_x=offset_x,
                offset_y=offset_y,
                offset_z=offset_z,
                R=r + 0.05,
                G=g + 0.05,
                B=b + 0.05,
                radius=self.radius,
            )
            self.children.append(child)

    def generate_vrml(self) -> str:
        """Generate the VRML representation for the color space.

        Returns:
            str: The VRML representation of the color space.
        """
        self.generate_vrml_axes()
        self.generate_vrml_children()

        self.vrml = self.VRML_TEMPLATE.format(
            children="".join(self.children),
            axes=self.axes,
            fov=math.radians(self.fov),
            offset_z=self.offset_z,
        )

    def write_vrml(
        self, file_format: str, filename: str | Path, compress: bool = True
    ) -> None:
        """Write the VRML representation to a file.

        Args:
            file_format (str): The format of the output file, e.g., 'VRML'.
            filename (str): The name of the file to export to.
            compress (bool): Whether to compress the output file.
        """
        if file_format != "VRML":
            print("Generating", file_format)
            x3d = x3dom.vrml2x3dom(self.vrml)
            if file_format == "HTML":
                out = x3d.html(title=os.path.basename(filename))
            else:
                out = x3d.x3d()
        writer = GzipFileProper if compress else open
        safe_print("Writing", filename)
        with writer(filename, "wb") as outfile:
            outfile.write(out.encode("utf-8"))


class RGBToVRML(ColorSpaceToVRML):
    """RGB color space class.

    Args:
        data (list): The color data to be processed.
        white_point (tuple[float, float, float]): The white point for the color space.
        cat (str): The CAT for the color space. Defaults to "XYZ scaling".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to 40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to False.
    """

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        return (
            entry["RGB_G"] - 50,
            entry["RGB_B"] - 50,
            entry["RGB_R"] - 50,
        )


class HSIToVRML(ColorSpaceToVRML):
    """HSI color space class.

    Args:
        data (list): The color data to be processed.
        white_point (tuple[float, float, float]): The white point for the color space.
        cat (str): The CAT for the color space. Defaults to "XYZ scaling".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to 40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to False.
    """

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        h, s, offset_z = colormath.RGB2HSI(
            entry["RGB_R"] / 100.0,
            entry["RGB_G"] / 100.0,
            entry["RGB_B"] / 100.0,
        )
        radian = math.radians(h * 360)
        offset_x, offset_y = (
            s * offset_z * math.cos(radian),
            s * offset_z * math.sin(radian),
        )
        # Fudge device locations into Lab space
        return (
            offset_x * self.sqrt3_100,
            offset_y * self.sqrt3_100,
            offset_z * self.sqrt3_100 - self.sqrt3_50,
        )


class HSLToVRML(ColorSpaceToVRML):
    """HSL color space class.

    Args:
        data (list): The color data to be processed.
        white_point (tuple[float, float, float]): The white point for the color space.
        cat (str): The CAT for the color space. Defaults to "XYZ scaling".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to 40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to False.
    """

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        h, s, offset_z = colormath.RGB2HSL(
            entry["RGB_R"] / 100.0,
            entry["RGB_G"] / 100.0,
            entry["RGB_B"] / 100.0,
        )
        radian = math.radians(h * 360)
        s *= (1 - offset_z) if offset_z > 0.5 else (offset_z)
        offset_x, offset_y = s * math.cos(radian), s * math.sin(radian)
        # Fudge device locations into Lab space
        return (
            offset_x * self.sqrt3_100,
            offset_y * self.sqrt3_100,
            offset_z * self.sqrt3_100 - self.sqrt3_50,
        )


class HSVToVRML(ColorSpaceToVRML):
    """HSV color space class.

    Args:
        data (list): The color data to be processed.
        white_point (tuple[float, float, float]): The white point for the color space.
        cat (str): The CAT for the color space. Defaults to "XYZ scaling".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to 40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to False.
    """

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        h, s, offset_z = colormath.RGB2HSV(
            entry["RGB_R"] / 100.0,
            entry["RGB_G"] / 100.0,
            entry["RGB_B"] / 100.0,
        )
        radian = math.radians(h * 360)
        offset_x, offset_y = (
            s * offset_z * math.cos(radian),
            s * offset_z * math.sin(radian),
        )
        # Fudge device locations into Lab space
        return (
            offset_x * self.sqrt3_50,
            offset_y * self.sqrt3_50,
            offset_z * self.sqrt3_100 - self.sqrt3_50,
        )


class LabToVRML(ColorSpaceToVRML):
    """Lab color space class.

    Args:
        data (list): The color data to be processed.
        white_point (tuple[float, float, float]): The white point for the color space.
        cat (str): The CAT for the color space. Defaults to "XYZ scaling".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to 40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to False.
    """

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        l, a, b = colormath.XYZ2Lab(self.X, self.Y, self.Z)
        # Fudge device locations into Lab space
        return a, b, l - 50


class DIN99ToVRML(ColorSpaceToVRML):
    """DIN99 color space class.

    Args:
        data (list): The color data to be processed.
        white_point (tuple[float, float, float]): The white point for the color space.
        cat (str): The CAT for the color space. Defaults to "XYZ scaling".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to 40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to False.
    """

    def __init__(
        self,
        data: list,
        white_point: tuple[float, float, float],
        cat: str = "XYZ scaling",
        rgb_black_offset: float = 40,
        normalize_rgb_white: bool = False,
    ) -> None:
        super().__init__(data, white_point, cat, rgb_black_offset, normalize_rgb_white)
        self.scale = 100.0 / 40  # Scale factor for DIN99 axes
        self.radius /= self.scale
        self.fov /= self.scale

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        l, a, b = colormath.XYZ2Lab(self.X, self.Y, self.Z)
        l99, a99, b99 = colormath.Lab2DIN99(l, a, b)
        return a99, b99, l99 - 50

    def generate_vrml_axes(self) -> None:
        """Get the VRML axis representation for the color space."""
        self.axes = ""
        pxcolor = "1.0 0.0 0.0"
        nxcolor = "0.0 1.0 0.0"
        pycolor = "1.0 1.0 0.0"
        nycolor = "0.0 0.0 1.0"
        self.axes += self.VRML_AXES_TEMPLATE.format(
            hundredth_scale=100.0 / self.scale,
            tenth_scale=10.0 / self.scale,
            colorspace=str(self.colorspace),
        )
        (pxlabel, nxlabel, pylabel, nylabel, pllabel) = (
            f'"a", "+{int(100 / self.scale)}"',
            f'"a", "-{int(100 / self.scale)}"',
            f'"b +{int(100 / self.scale)}"',
            f'"b -{int(100 / self.scale)}"',
            '"L", "+100"',
        )

        self.axes += self.VRML_AXES_TEMPLATE2.format(
            wh=2.0 / self.scale,
            ab=100.0 / self.scale,
            aboffset=50.0 / self.scale,
            fontsize=10.0 / self.scale,
            ap=102.0 / self.scale,
            an=108.0 / self.scale,
            Ln=3.0,
            bp0=3.0,
            bp1=103.0 / self.scale,
            bn0=3.0,
            bn1=107.0 / self.scale,
            pxlabel=pxlabel,
            nxlabel=nxlabel,
            pylabel=pylabel,
            nylabel=nylabel,
            pllabel=pllabel,
            pxcolor=pxcolor,
            nxcolor=nxcolor,
            pycolor=pycolor,
            nycolor=nycolor,
        )


class DIN99bToVRML(DIN99ToVRML):
    """DIN99b color space class.

    Args:
        entry (dict): The color data entry containing RGB and XYZ values.
        extra_offset_x (float, optional): Extra offset in the X direction.
            Defaults to 0.0.
        extra_offset_y (float, optional): Extra offset in the Y direction.
            Defaults to 0.0.
        scale (float, optional): Scale factor for the offsets. Defaults to 1.0.
        max_z (float, optional): Maximum Z value for scaling. Defaults to 100.0.
    """

    def __init__(
        self,
        data: list,
        white_point: tuple[float, float, float],
        cat: str = "XYZ scaling",
        rgb_black_offset: float = 40,
        normalize_rgb_white: bool = False,
    ) -> None:
        super().__init__(data, white_point, cat, rgb_black_offset, normalize_rgb_white)
        self.scale = 100.0 / 50  # Scale factor for DIN99b axes
        self.radius /= self.scale

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        l, a, b = colormath.XYZ2Lab(self.X, self.Y, self.Z)
        l99, a99, b99 = colormath.Lab2DIN99b(l, a, b)
        return a99, b99, l99 - 50


class DIN99cToVRML(DIN99ToVRML):
    """DIN99c color space class.

    Args:
        entry (dict): The color data entry containing RGB and XYZ values.
        extra_offset_x (float, optional): Extra offset in the X direction.
            Defaults to 0.0.
        extra_offset_y (float, optional): Extra offset in the Y direction.
            Defaults to 0.0.
        scale (float, optional): Scale factor for the offsets. Defaults to 1.0.
        max_z (float, optional): Maximum Z value for scaling. Defaults to 100.0.
    """

    def __init__(
        self,
        data: list,
        white_point: tuple[float, float, float],
        cat: str = "XYZ scaling",
        rgb_black_offset: float = 40,
        normalize_rgb_white: bool = False,
    ) -> None:
        super().__init__(data, white_point, cat, rgb_black_offset, normalize_rgb_white)
        self.scale = 100.0 / 50  # Scale factor for DIN99c axes
        self.radius /= self.scale

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        l99, a99, b99 = colormath.XYZ2DIN99c(self.X, self.Y, self.Z)
        return a99, b99, l99 - 50


class DIN99dToVRML(DIN99ToVRML):
    """DIN99d color space class.

    Args:
        entry (dict): The color data entry containing RGB and XYZ values.
        extra_offset_x (float, optional): Extra offset in the X direction.
            Defaults to 0.0.
        extra_offset_y (float, optional): Extra offset in the Y direction.
            Defaults to 0.0.
        scale (float, optional): Scale factor for the offsets. Defaults to 1.0.
        max_z (float, optional): Maximum Z value for scaling. Defaults to 100.0.
    """

    def __init__(
        self,
        data: list,
        white_point: tuple[float, float, float],
        cat: str = "XYZ scaling",
        rgb_black_offset: float = 40,
        normalize_rgb_white: bool = False,
    ) -> None:
        super().__init__(data, white_point, cat, rgb_black_offset, normalize_rgb_white)
        self.scale = 100.0 / 50  # Scale factor for DIN99d axes
        self.radius /= self.scale

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        l99, a99, b99 = colormath.XYZ2DIN99d(self.X, self.Y, self.Z)
        return a99, b99, l99 - 50


class LCHabToVRML(ColorSpaceToVRML):
    """LCH(ab) color space class.

    Args:
        data (list): The color data to be processed.
        white_point (tuple[float, float, float]): The white point for the color space.
        cat (str): The CAT for the color space. Defaults to "XYZ scaling".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to 40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to False.
    """

    def __init__(
        self,
        data: list,
        white_point: tuple[float, float, float],
        cat: str = "XYZ scaling",
        rgb_black_offset: float = 40,
        normalize_rgb_white: bool = False,
    ) -> None:
        super().__init__(data, white_point, cat, rgb_black_offset, normalize_rgb_white)
        self.fov /= 16.0
        self.offset_z *= 16

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        l, c, h = colormath.Lab2LCHab(self.L, self.a, self.b)
        return h - 180, c - 100, l - 50

    def generate_vrml_axes(self) -> None:
        """Get the VRML axis representation for the color space."""
        self.axes = ""
        self.max_z = 1.0
        self.extra_offset_x = 0.0
        self.extra_offset_y = 0.0
        xlabel, ylabel, zlabel = "H(ab)", "C(ab)", "L*"
        self.axes = x3dom.get_vrml_axes(
            xlabel, ylabel, zlabel, -180, -100, 0, 360, 200, 100, False
        )


class LCHuvToVRML(ColorSpaceToVRML):
    """LCH(uv) color space class.

    Args:
        data (list): The color data to be processed.
        white_point (tuple[float, float, float]): The white point for the color space.
        cat (str): The CAT for the color space. Defaults to "XYZ scaling".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to 40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to False.
    """

    def __init__(
        self,
        data: list,
        white_point: tuple[float, float, float],
        cat: str = "XYZ scaling",
        rgb_black_offset: float = 40,
        normalize_rgb_white: bool = False,
    ) -> None:
        super().__init__(data, white_point, cat, rgb_black_offset, normalize_rgb_white)
        self.fov /= 16.0
        self.offset_z *= 16

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        l, c, h = colormath.Luv2LCHuv(*colormath.XYZ2Luv(self.X, self.Y, self.Z))
        return h - 180, c - 100, l - 50

    def generate_vrml_axes(self) -> None:
        """Get the VRML axis representation for the color space."""
        self.axes = ""
        self.max_z = 1.0
        self.extra_offset_x = 0.0
        self.extra_offset_y = 0.0
        xlabel, ylabel, zlabel = "H(uv)", "C(uv)", "L*"
        self.axes = x3dom.get_vrml_axes(
            xlabel, ylabel, zlabel, -180, -100, 0, 360, 200, 100, False
        )


class LuvToVRML(ColorSpaceToVRML):
    """Luv color space class.

    Args:
        data (list): The color data to be processed.
        white_point (tuple[float, float, float]): The white point for the color space.
        cat (str): The CAT for the color space. Defaults to "XYZ scaling".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to 40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to False.
    """

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        l, u, v = colormath.XYZ2Luv(self.X, self.Y, self.Z)
        return u, v, l - 50

    def generate_vrml_axes(self) -> None:
        """Get the VRML axis representation for the color space."""
        self.axes = ""
        pxcolor = "1.0 0.0 0.0"
        nxcolor = "0.0 1.0 0.0"
        pycolor = "1.0 1.0 0.0"
        nycolor = "0.0 0.0 1.0"
        x = "u"
        y = "v"
        (pxlabel, nxlabel, pylabel, nylabel, pllabel) = (
            f'"{x}*", "+100"',
            f'"{x}*", "-100"',
            f'"{y}* +100"',
            f'"{y}* -100"',
            '"L*", "+100"',
        )
        self.axes += self.VRML_AXES_TEMPLATE2.format(
            wh=2.0 / self.scale,
            ab=100.0 / self.scale,
            aboffset=50.0 / self.scale,
            fontsize=10.0 / self.scale,
            ap=102.0 / self.scale,
            an=108.0 / self.scale,
            Ln=3.0,
            bp0=3.0,
            bp1=103.0 / self.scale,
            bn0=3.0,
            bn1=107.0 / self.scale,
            pxlabel=pxlabel,
            nxlabel=nxlabel,
            pylabel=pylabel,
            nylabel=nylabel,
            pllabel=pllabel,
            pxcolor=pxcolor,
            nxcolor=nxcolor,
            pycolor=pycolor,
            nycolor=nycolor,
        )


class LuvPrimeToVRML(ColorSpaceToVRML):
    """Lu'v' color space class.

    Args:
        data (list): The color data to be processed.
        white_point (tuple[float, float, float]): The white point for the color space.
        cat (str): The CAT for the color space. Defaults to "XYZ scaling".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to 40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to False.
    """

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        l, u_, v_ = colormath.XYZ2Lu_v_(self.X, self.Y, self.Z)
        return (
            (u_ + self.extra_offset_x) * self.scale,
            (v_ + self.extra_offset_y) * self.scale,
            l / 100.0 * self.max_z - 50,
        )

    def generate_vrml_axes(self) -> None:
        """Get the VRML axis representation for the color space."""
        self.axes = ""
        self.max_z = self.scale = 100
        self.radius /= 2.0
        xlabel, ylabel, zlabel = "x 0.8", "y 0.8", "Y 100"
        self.extra_offset_x, self.extra_offset_y = -0.4, -0.4
        self.scale = self.max_xy / 0.8
        xlabel, ylabel, zlabel = "u' 0.6", "v' 0.6", "L* 100"
        self.extra_offset_x, self.extra_offset_y = -0.3, -0.3
        self.scale = self.max_xy / 0.6
        self.axes = x3dom.get_vrml_axes(
            xlabel,
            ylabel,
            zlabel,
            self.extra_offset_x * self.scale,
            self.extra_offset_y * self.scale,
            0,
            self.max_xy,
            self.max_xy,
            self.max_z,
        )


class xyYToVRML(ColorSpaceToVRML):  # noqa: N801
    """xyY color space class.

    Args:
        data (list): The color data to be processed.
        white_point (tuple[float, float, float]): The white point for the color space.
        cat (str): The CAT for the color space. Defaults to "XYZ scaling".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to 40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to False.
    """

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        offset_x, offset_y, self.Y = colormath.XYZ2xyY(self.X, self.Y, self.Z)
        return (
            (offset_x + self.extra_offset_x) * self.scale,
            (offset_y + self.extra_offset_y) * self.scale,
            self.Y / 100.0 * self.max_z - 50,
        )

    def generate_vrml_axes(self) -> None:
        """Get the VRML axis representation for the color space."""
        self.axes = ""
        self.max_z = 1.0
        self.extra_offset_x = 0.0
        self.extra_offset_y = 0.0
        self.max_z = self.scale = 100
        self.radius /= 2.0
        xlabel, ylabel, zlabel = "x 0.8", "y 0.8", "Y 100"
        self.extra_offset_x, self.extra_offset_y = -0.4, -0.4
        self.scale = self.max_xy / 0.8
        self.axes = x3dom.get_vrml_axes(
            xlabel,
            ylabel,
            zlabel,
            self.extra_offset_x * self.scale,
            self.extra_offset_y * self.scale,
            0,
            self.max_xy,
            self.max_xy,
            self.max_z,
        )


class ICtCpToVRML(ColorSpaceToVRML):
    """ICtCp color space class.

    Args:
        data (list): The color data to be processed.
        white_point (tuple[float, float, float]): The white point for the color space.
        cat (str): The CAT for the color space. Defaults to "XYZ scaling".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to 40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to False.
    """

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        i, ct, cp = colormath.XYZ2ICtCp(
            self.X / 100.0, self.Y / 100.0, self.Z / 100.0, clamp=False
        )
        return ct * 100, cp * 100, i * 100 - 50

    def generate_vrml_axes(self) -> None:
        """Get the VRML axis representation for the color space."""
        self.axes = ""
        pxcolor = "1.0 0.0 0.0"
        nxcolor = "0.0 1.0 0.0"
        pycolor = "1.0 1.0 0.0"
        nycolor = "0.0 0.0 1.0"
        self.scale = 2.0
        self.radius /= 2.0
        (pxlabel, nxlabel, pylabel, nylabel, pllabel) = (
            '"Ct", "+0.5"',
            '"Ct", "-0.5"',
            '"Cp +0.5"',
            '"Cp -0.5"',
            '"I"',
        )
        pxcolor = "0.5 0.0 1.0"
        nxcolor = "0.8 1.0 0.0"
        pycolor = "1.0 0.0 0.25"
        nycolor = "0.0 1.0 1.0"
        self.axes += self.VRML_AXES_TEMPLATE2.format(
            wh=2.0 / self.scale,
            ab=100.0 / self.scale,
            aboffset=50.0 / self.scale,
            fontsize=10.0 / self.scale,
            ap=102.0 / self.scale,
            an=108.0 / self.scale,
            Ln=3.0,
            bp0=3.0,
            bp1=103.0 / self.scale,
            bn0=3.0,
            bn1=107.0 / self.scale,
            pxlabel=pxlabel,
            nxlabel=nxlabel,
            pylabel=pylabel,
            nylabel=nylabel,
            pllabel=pllabel,
            pxcolor=pxcolor,
            nxcolor=nxcolor,
            pycolor=pycolor,
            nycolor=nycolor,
        )


class IPTToVRML(ColorSpaceToVRML):
    """IPT color space class.

    Args:
        data (list): The color data to be processed.
        white_point (tuple[float, float, float]): The white point for the color space.
        cat (str): The CAT for the color space. Defaults to "XYZ scaling".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to 40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to False.
    """

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        i, p, t = colormath.XYZ2IPT(self.X / 100.0, self.Y / 100.0, self.Z / 100.0)
        return p * 100, t * 100, i * 100 - 50

    def generate_vrml_axes(self) -> None:
        """Get the VRML axis representation for the color space."""
        self.axes = ""
        pxcolor = "1.0 0.0 0.0"
        nxcolor = "0.0 1.0 0.0"
        pycolor = "1.0 1.0 0.0"
        nycolor = "0.0 0.0 1.0"
        (pxlabel, nxlabel, pylabel, nylabel, pllabel) = (
            '"P", "+1.0',
            '"P", "-1.0"',
            '"T +1.0"',
            '"T -1.0"',
            '"I"',
        )
        self.axes += self.VRML_AXES_TEMPLATE2.format(
            wh=2.0 / self.scale,
            ab=100.0 / self.scale,
            aboffset=50.0 / self.scale,
            fontsize=10.0 / self.scale,
            ap=102.0 / self.scale,
            an=108.0 / self.scale,
            Ln=3.0,
            bp0=3.0,
            bp1=103.0 / self.scale,
            bn0=3.0,
            bn1=107.0 / self.scale,
            pxlabel=pxlabel,
            nxlabel=nxlabel,
            pylabel=pylabel,
            nylabel=nylabel,
            pllabel=pllabel,
            pxcolor=pxcolor,
            nxcolor=nxcolor,
            pycolor=pycolor,
            nycolor=nycolor,
        )


class LptToVRML(ColorSpaceToVRML):
    """Lpt color space class.

    Args:
        data (list): The color data to be processed.
        white_point (tuple[float, float, float]): The white point for the color space.
        cat (str): The CAT for the color space. Defaults to "XYZ scaling".
        rgb_black_offset (float, optional): Offset for RGB black. Defaults to 40.
        normalize_rgb_white (bool, optional): Normalize RGB white. Defaults to False.
    """

    def get_offsets(self, entry: dict) -> tuple[float, float, float]:
        """Get the offset for the color space.

        Args:
            entry (dict): The color data entry containing RGB and XYZ values.

        Returns:
            tuple[float, float, float]: Offset values for X, Y, Z.
        """
        l, p, t = colormath.XYZ2Lpt(self.X, self.Y, self.Z)
        return p, t, l - 50

    def generate_vrml_axes(self) -> None:
        """Get the VRML axis representation for the color space."""
        self.axes = ""
        pxcolor = "1.0 0.0 0.0"
        nxcolor = "0.0 1.0 0.0"
        pycolor = "1.0 1.0 0.0"
        nycolor = "0.0 0.0 1.0"
        x = "p"
        y = "t"
        (pxlabel, nxlabel, pylabel, nylabel, pllabel) = (
            f'"{x}*", "+100"',
            f'"{x}*", "-100"',
            f'"{y}* +100"',
            f'"{y}* -100"',
            '"L*", "+100"',
        )
        self.axes += self.VRML_AXES_TEMPLATE2.format(
            wh=2.0 / self.scale,
            ab=100.0 / self.scale,
            aboffset=50.0 / self.scale,
            fontsize=10.0 / self.scale,
            ap=102.0 / self.scale,
            an=108.0 / self.scale,
            Ln=3.0,
            bp0=3.0,
            bp1=103.0 / self.scale,
            bn0=3.0,
            bn1=107.0 / self.scale,
            pxlabel=pxlabel,
            nxlabel=nxlabel,
            pylabel=pylabel,
            nylabel=nylabel,
            pllabel=pllabel,
            pxcolor=pxcolor,
            nxcolor=nxcolor,
            pycolor=pycolor,
            nycolor=nycolor,
        )


COLORSPACE_NAME_TO_VRML_MAP = {
    "DIN99": DIN99ToVRML,
    "DIN99b": DIN99bToVRML,
    "DIN99c": DIN99cToVRML,
    "DIN99d": DIN99dToVRML,
    "HSI": HSIToVRML,
    "HSL": HSLToVRML,
    "HSV": HSVToVRML,
    "ICtCp": ICtCpToVRML,
    "IPT": IPTToVRML,
    "Lab": LabToVRML,
    "LCH(ab)": LCHabToVRML,
    "LCH(uv)": LCHuvToVRML,
    "Lpt": LptToVRML,
    "Lu'v'": LuvPrimeToVRML,
    "Luv": LuvToVRML,
    "RGB": RGBToVRML,
    "xyY": xyYToVRML,
}
