"""ICC video card gamma tags."""

from __future__ import annotations

import math
from typing import Callable

from DisplayCAL import colormath
from DisplayCAL.icc_profile.codecs import (
    u16Fixed16Number,
    u16Fixed16Number_tohex,
    uInt8Number,
    uInt8Number_tohex,
    uInt16Number,
    uInt16Number_tohex,
    uInt32Number,
    uInt32Number_tohex,
    uInt64Number,
    uInt64Number_tohex,
)
from DisplayCAL.icc_profile.structures import ADict, AODict, CRInterpolation
from DisplayCAL.icc_profile.tags.base import ICCProfileTag


class VideoCardGammaType(ICCProfileTag, ADict):
    """Video Card Gamma Tag.

    This tag contains the gamma correction values for the red, green and blue
    channels of the video card. The values are stored in a table or as a
    formula. The table is a 256-entry table with values ranging from 0 to
    65535. The formula is a gamma correction formula with the following
    parameters: redMin, redMax, redGamma, greenMin, greenMax, greenGamma,
    blueMin, blueMax, blueGamma.

    Private tag
    http://developer.apple.com/documentation/GraphicsImaging/Reference/ColorSync_Manager/Reference/reference.html#//apple_ref/doc/uid/TP30000259-CH3g-C001473

    Args:
        tagData (bytes): The raw tag data.
        tagSignature (str): The signature of the tag, usually "vcgt".
    """

    def __init__(self, tagData: bytes, tagSignature: str) -> None:  # noqa: N803
        ICCProfileTag.__init__(self, tagData, tagSignature)

    def is_linear(self, r: bool = True, g: bool = True, b: bool = True) -> bool:
        """Check if the gamma correction is linear for the red, green and blue channels.

        Args:
            r (bool): Whether to check the red channel.
            g (bool): Whether to check the green channel.
            b (bool): Whether to check the blue channel.

        Returns:
            bool: True if the gamma correction is linear for the specified
                channels.
        """
        r_points, g_points, b_points, linear_points = self.get_values()
        if (
            (r and g and b and r_points == g_points == b_points)
            or (r and g and r_points == g_points)
            or not (g or b)
        ):
            points = r_points
        elif (
            (r and b and r_points == b_points)
            or (g and b and g_points == b_points)
            or not (r or g)
        ):
            points = b_points
        elif g:
            points = g_points
        return points == linear_points

    def get_unique_values(
        self, r: bool = True, g: bool = True, b: bool = True
    ) -> tuple:
        """Return unique values for the red, green and blue channels.

        Args:
            r (bool): Whether to include red channel values.
            g (bool): Whether to include green channel values.
            b (bool): Whether to include blue channel values.

        Returns:
            tuple: Three sets containing the unique values for the red,
        """
        r_points, g_points, b_points, linear_points = self.get_values()
        r_unique = {round(y) for x, y in r_points}
        g_unique = {round(y) for x, y in g_points}
        b_unique = {round(y) for x, y in b_points}
        return r_unique, g_unique, b_unique

    def get_values(self, r: bool = True, g: bool = True, b: bool = True) -> tuple:
        """Return the gamma correction values for the red, green and blue channels.

        Args:
            r (bool, optional): Whether to include red channel values.
            g (bool, optional): Whether to include green channel values.
            b (bool, optional): Whether to include blue channel values.

        Returns:
            tuple: Four lists containing the red, green, blue, and linear
        """
        r_points = []
        g_points = []
        b_points = []
        linear_points = []
        vcgt = self
        if "data" in vcgt:  # table
            data = list(vcgt["data"])
            while len(data) < 3:
                data.append(data[0])
            irange = list(range(vcgt["entryCount"]))
            vmax = math.pow(256, vcgt["entrySize"]) - 1
            for i in irange:
                j = i * (255.0 / (vcgt["entryCount"] - 1))
                linear_points.append(
                    [j, round(i / float(vcgt["entryCount"] - 1) * 65535)]
                )
                if r:
                    n = round(float(data[0][i]) / vmax * 65535)
                    r_points.append([j, n])
                if g:
                    n = round(float(data[1][i]) / vmax * 65535)
                    g_points.append([j, n])
                if b:
                    n = round(float(data[2][i]) / vmax * 65535)
                    b_points.append([j, n])
        else:  # formula
            irange = list(range(256))
            step = 100.0 / 255.0
            for i in irange:
                linear_points.append([i, i / 255.0 * 65535])
                if r:
                    vmin = vcgt["redMin"] * 65535
                    v = math.pow(step * i / 100.0, vcgt["redGamma"])
                    vmax = vcgt["redMax"] * 65535
                    r_points.append([i, round(vmin + v * (vmax - vmin))])
                if g:
                    vmin = vcgt["greenMin"] * 65535
                    v = math.pow(step * i / 100.0, vcgt["greenGamma"])
                    vmax = vcgt["greenMax"] * 65535
                    g_points.append([i, round(vmin + v * (vmax - vmin))])
                if b:
                    vmin = vcgt["blueMin"] * 65535
                    v = math.pow(step * i / 100.0, vcgt["blueGamma"])
                    vmax = vcgt["blueMax"] * 65535
                    b_points.append([i, round(vmin + v * (vmax - vmin))])
        return r_points, g_points, b_points, linear_points

    def printNormalizedValues(  # noqa: N802
        self, amount: None | int = None, digits: int = 12
    ) -> None:
        """Normalize and prints all values in the vcgt (range of 0.0...1.0).

        For a 256-entry table with linear values from 0 to 65535:
        #   REF            C1             C2             C3
        001 0.000000000000 0.000000000000 0.000000000000 0.000000000000
        002 0.003921568627 0.003921568627 0.003921568627 0.003921568627
        003 0.007843137255 0.007843137255 0.007843137255 0.007843137255
        ...
        You can also specify the amount of values to print (where a value
        lesser than the entry count will leave out intermediate values)
        and the number of digits.

        Args:
            amount (None | int, optional): The number of values to print.
                If None, it defaults to the entryCount if available, otherwise
                to 256.
            digits (int, optional): The number of digits to round the values
                to. Defaults to 12.
        """
        if amount is None:
            # use entryCount if exists, otherwise use the common value
            amount = self.entryCount if hasattr(self, "entryCount") else 256
        values = self.getNormalizedValues(amount)
        entry_count = len(values)
        channels = len(values[0])
        header = ["REF"]
        header.extend(f"C{k + 1}" for k in range(channels))
        header = [title.ljust(digits + 2) for title in header]
        print("#".ljust(len(str(amount)) + 1) + " ".join(header))
        for i, value in enumerate(values):
            formatted_values = [
                str(round(channel, digits)).ljust(digits + 2, "0") for channel in value
            ]
            print(
                str(i + 1).rjust(len(str(amount)), "0"),
                str(round(i / float(entry_count - 1), digits)).ljust(digits + 2, "0"),
                " ".join(formatted_values),
            )


class VideoCardGammaFormulaType(VideoCardGammaType):
    """Video card gamma formula type class.

    Args:
        tagData (bytes): The raw tag data containing the video LUT curves.
        tagSignature (str): The signature of the tag, typically "vcgt".
    """

    def __init__(self, tagData: bytes, tagSignature: str) -> None:  # noqa: N803
        VideoCardGammaType.__init__(self, tagData, tagSignature)
        data = tagData[12:]
        self.update(
            {
                "redGamma": u16Fixed16Number(data[0:4]),
                "redMin": u16Fixed16Number(data[4:8]),
                "redMax": u16Fixed16Number(data[8:12]),
                "greenGamma": u16Fixed16Number(data[12:16]),
                "greenMin": u16Fixed16Number(data[16:20]),
                "greenMax": u16Fixed16Number(data[20:24]),
                "blueGamma": u16Fixed16Number(data[24:28]),
                "blueMin": u16Fixed16Number(data[28:32]),
                "blueMax": u16Fixed16Number(data[32:36]),
            }
        )

    def getNormalizedValues(self, amount: None | int = None) -> list:  # noqa: N802
        """Return normalized values of the video LUT curves.

        Args:
            amount (None | int, optional): The number of values to return. If
                None, it defaults to 256.

        Returns:
            list: A list of tuples, each containing normalized values for the
                red, green, and blue channels.
        """
        if amount is None:
            amount = 256  # common value
        step = 1.0 / float(amount - 1)
        rgb = AODict([("red", []), ("green", []), ("blue", [])])
        for i in range(amount):
            for key in rgb:
                rgb[key].append(
                    float(self[key + "Min"])
                    + math.pow(step * i / 1.0, float(self[key + "Gamma"]))
                    * float(self[key + "Max"] - self[key + "Min"])
                )
        return list(zip(*list(rgb.values())))

    def getTableType(  # noqa: N802
        self,
        entryCount: int = 256,  # noqa: N803
        entrySize: int = 2,  # noqa: N803
        quantizer: Callable = round,  # noqa: N803
    ) -> VideoCardGammaTableType:
        """Return gamma as table type.

        Args:
            entryCount (int, optional): The number of entries in the table.
                Defaults to 256.
            entrySize (int, optional): The size of each entry in bytes.
                Defaults to 2.
            quantizer (Callable, optional): A function to quantize the values.
                Defaults to `round`.

        Returns:
            VideoCardGammaTableType: A new instance of VideoCardGammaTableType
                containing the gamma table data.
        """
        max_value = math.pow(256, entrySize) - 1
        tag_data = [
            self.tagData[:8],
            uInt32Number_tohex(0),  # type 0 = table
            uInt16Number_tohex(3),  # channels
            uInt16Number_tohex(entryCount),
            uInt16Number_tohex(entrySize),
        ]
        int2hex = {
            1: uInt8Number_tohex,
            2: uInt16Number_tohex,
            4: uInt32Number_tohex,
            8: uInt64Number_tohex,
        }
        for key in ("red", "green", "blue"):
            for i in range(entryCount):
                vmin = float(self[key + "Min"])
                vmax = float(self[key + "Max"])
                gamma = float(self[key + "Gamma"])
                v = vmin + math.pow(1.0 / (entryCount - 1) * i, gamma) * float(
                    vmax - vmin
                )
                tag_data.append(int2hex[entrySize](quantizer(v * max_value)))
        return VideoCardGammaTableType(b"".join(tag_data), self.tagSignature)


class VideoCardGammaTableType(VideoCardGammaType):
    """Video card gamma table type class.

    Args:
        tagData (bytes): The raw tag data containing the video LUT curves.
        tagSignature (str): The signature of the tag, typically "vcgt".
    """

    def __init__(self, tagData: bytes, tagSignature: str) -> None:  # noqa: N803
        VideoCardGammaType.__init__(self, tagData, tagSignature)
        if not tagData:
            self.update({"channels": 0, "entryCount": 0, "entrySize": 0, "data": []})
            return
        data = tagData[12:]
        channels = uInt16Number(data[0:2])
        entry_count = uInt16Number(data[2:4])
        entry_size = uInt16Number(data[4:6])
        self.update(
            {
                "channels": channels,
                "entryCount": entry_count,
                "entrySize": entry_size,
                "data": [],
            }
        )
        hex2int = {1: uInt8Number, 2: uInt16Number, 4: uInt32Number, 8: uInt64Number}
        if entry_size not in hex2int:
            raise ValueError(
                f"Invalid VideoCardGammaTableType entry size {int(entry_size):d}"
            )
        i = 0
        while i < channels:
            self.data.append([])
            j = 0
            while j < entry_count:
                index = 6 + i * entry_count * entry_size + j * entry_size
                self.data[i].append(
                    hex2int[entry_size](data[index : index + entry_size])
                )
                j = j + 1
            i = i + 1

    def getNormalizedValues(self, amount: None | int = None) -> list:  # noqa: N802
        """Return normalized values of the video LUT curves.

        Args:
            amount (None | int, optional): The number of values to return. If
                None, it defaults to the entryCount of the video LUT curves.

        Returns:
            list: A list of tuples, each containing normalized values for the
                red, green, and blue channels.
        """
        if amount is None:
            amount = self.entryCount
        max_value = math.pow(256, self.entrySize) - 1
        values = list(
            zip(*[[entry / max_value for entry in channel] for channel in self.data])
        )
        if amount <= self.entryCount:
            step = self.entryCount / float(amount - 1)
            all_values = values
            values = []
            for i, value in enumerate(all_values):
                if i == 0 or (i + 1) % step < 1 or i + 1 == self.entryCount:
                    values.append(value)
        return values

    def getFormulaType(self) -> VideoCardGammaFormulaType:  # noqa: N802
        """Return formula representing gamma value at 50% input.

        Returns:
            VideoCardGammaFormulaType: A new instance of
                VideoCardGammaFormulaType with the calculated gamma values and
                min/max values for each channel.
        """
        max_value = math.pow(256, self.entrySize) - 1
        tag_data = [self.tagData[:8], uInt32Number_tohex(1)]  # type 1 = formula
        data = list(self.data)
        while len(data) < 3:
            data.append(data[0])
        for channel in data:
            channel_length = (len(channel) - 1) / 2.0
            floor = float(channel[math.floor(channel_length)])
            ceil = float(channel[math.ceil(channel_length)])
            vmin = channel[0] / max_value
            vmax = channel[-1] / max_value
            v = (vmin + ((floor + ceil) / 2.0) * (vmax - vmin)) / max_value
            gamma = math.log(v) / math.log(0.5)
            print(vmin, gamma, vmax)
            tag_data.append(u16Fixed16Number_tohex(gamma))
            tag_data.append(u16Fixed16Number_tohex(vmin))
            tag_data.append(u16Fixed16Number_tohex(vmax))
        return VideoCardGammaFormulaType(b"".join(tag_data), self.tagSignature)

    def quantize(self, bits: int = 16, quantizer: Callable = round) -> None:
        """Quantize to n bits of precision.

        Note that when the quantize bits are not 8, 16, 32 or 64, double
        quantization will occur: First from the table precision bits according
        to entrySize to the chosen quantization bits, and then back to the
        table precision bits.

        Args:
            bits (int, optional): The number of bits to quantize to. Must be
                one of 8, 16, 32, or 64. Defaults to 16.
            quantizer (callable, optional): A function to quantize the values.
                Defaults to the built-in `round` function.
        """
        oldmax = math.pow(256, self.entrySize) - 1
        if bits in (8, 16, 32, 64):
            self.entrySize = int(bits / 8)
        bitv = 2.0**bits
        newmax = math.pow(256, self.entrySize) - 1
        for _i, channel in enumerate(self.data):
            for j, value in enumerate(channel):
                channel[j] = int(quantizer(value / oldmax * bitv) / bitv * newmax)

    def resize(self, length: int = 128) -> None:
        """Resize video LUT curves to a given length.

        Args:
            length (int): The desired length of the resized LUT curves.
        """
        data = [[], [], []]
        for i, channel in enumerate(self.data):
            for j in range(length):
                j *= (len(channel) - 1) / float(length - 1)
                if int(j) != j:
                    floor = channel[math.floor(j)]
                    ceil = channel[min(math.ceil(j), len(channel) - 1)]
                    interpolated = range(floor, ceil + 1)
                    fraction = j - int(j)
                    index = round(fraction * (ceil - floor))
                    v = interpolated[index]
                else:
                    v = channel[int(j)]
                data[i].append(v)
        self.data = data
        self.entryCount = len(data[0])

    def resized(self, length: int = 128) -> VideoCardGammaTableType:
        """Return a resized version of the video LUT curves.

        Args:
            length (int): The desired length of the resized LUT curves.

        Returns:
            VideoCardGammaTableType: A new instance of VideoCardGammaTableType
                with the resized LUT curves.
        """
        resized = self.__class__(self.tagData, self.tagSignature)
        resized.resize(length)
        return resized

    def smooth_cr(self, length: int = 64) -> None:
        """Smooth video LUT curves (Catmull-Rom).

        Args:
            length (int): The desired length of the smoothed LUT curves.
                Defaults to 64.
        """
        resized = self.resized(length)
        for i in range(len(self.data)):
            step = float(length - 1) / (len(self.data[i]) - 1)
            interpolation = CRInterpolation(resized.data[i])
            for j in range(len(self.data[i])):
                self.data[i][j] = interpolation(j * step)

    def smooth_avg(self, passes: int = 1, window: None | list | tuple = None) -> None:
        """Smooth video LUT curves (moving average).

        Args:
            passes (int): Number of passes to perform. Defaults to 1.
            window (None | list | tuple , optional): Tuple or list containing
                weighting factors. Its length determines the size of the window
                to use. Defaults to (1.0, 1.0, 1.0).
        """
        for i, channel in enumerate(self.data):
            self.data[i] = colormath.smooth_avg(channel, passes, window)
        self.entryCount = len(self.data[0])

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: The raw tag data formatted as bytes.
        """
        tag_data = [
            b"vcgt",
            b"\0" * 4,
            uInt32Number_tohex(0),  # type 0 = table
            uInt16Number_tohex(len(self.data)),  # channels
            uInt16Number_tohex(self.entryCount),
            uInt16Number_tohex(self.entrySize),
        ]
        int2hex = {
            1: uInt8Number_tohex,
            2: uInt16Number_tohex,
            4: uInt32Number_tohex,
            8: uInt64Number_tohex,
        }
        tag_data.extend(
            int2hex[self.entrySize](channel[i])
            for channel in self.data
            for i in range(self.entryCount)
        )
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set the tag data.

        Does nothing in this case, as the tagData is generated
        from the internal data structure.

        Args:
            tagData (bytes): The raw tag data to set.
        """
