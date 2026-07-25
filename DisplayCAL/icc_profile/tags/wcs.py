"""ICC WCS profiles tag."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from DisplayCAL.icc_profile.codecs import (
    u16Fixed16Number_tohex,
    uInt32Number,
    uInt32Number_tohex,
)
from DisplayCAL.icc_profile.structures import ADict
from DisplayCAL.icc_profile.tags.base import ICCProfileTag
from DisplayCAL.icc_profile.tags.video_card_gamma import (
    VideoCardGammaFormulaType,
    VideoCardGammaType,
)

if TYPE_CHECKING:
    from DisplayCAL.icc_profile import ICCProfile


class WcsProfilesTagType(ICCProfileTag, ADict):
    """ICC WCS profiles tag type.

    Args:
        tagData (bytes): The raw tag data.
        tagSignature (str): The signature of the tag.
        profile (ICCProfile): The ICC profile to which this tag belongs.
    """

    def __init__(self, tagData: bytes, tagSignature: str, profile: ICCProfile) -> None:  # noqa: N803
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.profile = profile
        for i, modelname in enumerate(
            ["ColorDeviceModel", "ColorAppearanceModel", "GamutMapModel"]
        ):
            j = i * 8
            if len(tagData) < 16 + j:
                break
            offset = uInt32Number(tagData[8 + j : 12 + j])
            size = uInt32Number(tagData[12 + j : 16 + j])
            if offset and size:
                from io import StringIO

                from defusedxml import ElementTree

                it = ElementTree.iterparse(StringIO(tagData[offset : offset + size]))
                for _event, elem in it:
                    elem.tag = elem.tag.split("}", 1)[-1]  # Strip all namespaces
                self[modelname] = it.root

    def get_vcgt(
        self,
        quantize: int | bool = False,
        quantizer: Callable = round,
    ) -> None | VideoCardGammaType:
        """Return calibration information (if present) as VideoCardGammaType.

        If quantize is set, a table quantized to <quantize> bits is returned.

        Note that when the quantize bits are not 8, 16, 32 or 64, multiple
        quantizations will occur: For quantization bits below 32, first to 32
        bits, then to the chosen quantization bits, then back to 32 bits (which
        will be the final table precision bits).

        Args:
            quantize (bool | int, optional): If True, quantize to 16 bits
                (default). If an integer, quantize to that many bits.
            quantizer (Callable, optional): A quantization function, defaults to
                `round`.

        Returns:
            None | VideoCardGammaType: Returns a VideoCardGammaType object if
                calibration information is present, otherwise None.
        """
        if quantize and not isinstance(quantize, int):
            raise ValueError(f"Invalid quantization bits: {quantize!r}")

        if "ColorDeviceModel" not in self:
            return None

        # Parse calibration information to VCGT
        cal = self.ColorDeviceModel.find("Calibration")
        if cal is None:
            return None
        agammaconf = cal.find("AdapterGammaConfiguration")
        if agammaconf is None:
            return None
        pcurves = agammaconf.find("ParameterizedCurves")
        if pcurves is None:
            return None
        vcgt_data = "vcgt"
        vcgt_data += b"\0" * 4
        vcgt_data += uInt32Number_tohex(1)  # Type 1 = formula
        for color in ("Red", "Green", "Blue"):
            trc = pcurves.find(color + "TRC")
            if trc is None:
                trc = {}
            vcgt_data += u16Fixed16Number_tohex(float(trc.get("Gamma", 1)))
            vcgt_data += u16Fixed16Number_tohex(float(trc.get("Offset1", 0)))
            vcgt_data += u16Fixed16Number_tohex(float(trc.get("Gain", 1)))
        vcgt = VideoCardGammaFormulaType(vcgt_data, "vcgt")
        if quantize:
            if quantize in (8, 16, 32, 64):
                entry_size = quantize / 8
            elif quantize < 32:
                entry_size = 4
            else:
                entry_size = 8
            vcgt = vcgt.getTableType(entrySize=entry_size, quantizer=quantizer)
            if quantize not in (8, 16, 32, 64):
                vcgt.quantize(quantize, quantizer)
        return vcgt
