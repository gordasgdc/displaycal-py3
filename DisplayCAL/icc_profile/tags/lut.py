"""ICC LUT16Type tag."""

from __future__ import annotations

import functools
import operator
import os
import warnings
from typing import TYPE_CHECKING, BinaryIO, Callable, TextIO

from DisplayCAL import colormath, imfile
from DisplayCAL.icc_profile.codecs import (
    legacy_PCSLab_uInt16_to_dec,
    s15Fixed16Number,
    s15Fixed16Number_tohex,
    uInt8Number,
    uInt8Number_tohex,
    uInt16Number,
    uInt16Number_tohex,
)
from DisplayCAL.icc_profile.constants import DEBUG
from DisplayCAL.icc_profile.tags.base import ICCProfileTag
from DisplayCAL.util_dict import dict_sort

if TYPE_CHECKING:
    import threading

    from DisplayCAL.icc_profile import ICCProfile


class LUT16Type(ICCProfileTag):
    """ICC LUT16Type tag.

    Args:
        tagData (bytes): The raw tag data.
        tagSignature (bytes): The tag signature.
        profile (ICCProfile): The ICC profile this tag belongs to.
    """

    def __init__(
        self,
        tagData: None | bytes = None,  # noqa: N803
        tagSignature: None | str = None,  # noqa: N803
        profile: None | ICCProfile = None,
    ) -> None:
        ICCProfileTag.__init__(self, tagData, tagSignature)
        self.profile = profile
        self._matrix = None
        self._input = None
        self._clut = None
        self._output = None
        self._i = (tagData and uInt8Number(tagData[8:9])) or 0  # Input channel count
        self._o = (tagData and uInt8Number(tagData[9:10])) or 0  # Output channel count
        self._g = (tagData and uInt8Number(tagData[10:11])) or 0  # cLUT grid res
        self._n = (
            tagData and uInt16Number(tagData[48:50])
        ) or 0  # Input channel entries count
        self._m = (
            tagData and uInt16Number(tagData[50:52])
        ) or 0  # Output channel entries count

    def apply_black_offset(
        self,
        XYZbp: tuple[float, float, float],  # noqa: N803
        logfile: None | TextIO = None,
        thread_abort: None | threading.Event = None,
        abortmessage: str = "Aborted",
    ) -> None:
        """Apply black point offset to the cLUT.

        Args:
            XYZbp (tuple[float, float, float]): The black point offset values
                as a tuple of three floats (X, Y, Z).
            logfile (None | TextIO): File-like object to write progress
                messages to. Defaults to None.
            thread_abort (threading.Event): Event to signal thread abortion.
                Defaults to None.
            abortmessage (str): Message to display when the operation is
                aborted. Defaults to "Aborted".
        """
        # Apply only the black point blending portion of BT.1886 mapping
        self._apply_black(XYZbp, False, False, logfile, thread_abort, abortmessage)

    def apply_bpc(
        self,
        bp_out: tuple[float, float, float] = (0, 0, 0),
        weight: bool = False,
        logfile: None | TextIO = None,
        thread_abort: None | threading.Event = None,
        abortmessage: str = "Aborted",
    ) -> None:
        """Apply black point compensation to the cLUT.

        Args:
            bp_out (tuple, optional): The black point output values as a tuple
                of three floats (R, G, B). Defaults to (0, 0, 0).
            weight (bool, optional): Whether to apply a weighted black point
                compensation. Defaults to False.
            logfile (None | TextIO): File-like object to write the log messages
                to.
            thread_abort (threading.Event): Event to signal thread abortion.
            abortmessage (str): Message to display when the operation is aborted.
        """
        return self._apply_black(
            bp_out, True, weight, logfile, thread_abort, abortmessage
        )

    def _apply_black(
        self,
        bp_out: tuple[float, float, float],
        use_bpc: bool = False,
        weight: bool = False,
        logfile: None | TextIO = None,
        thread_abort: None | threading.Event = None,
        abortmessage: str = "Aborted",
    ) -> None:
        """Apply black point compensation or offset to the cLUT.

        Args:
            bp_out (tuple): The black point output values as a tuple of three
                floats (R, G, B).
            use_bpc (bool, optional): Whether to use black point compensation
                (BPC) or just apply a black offset. Defaults to False.
            weight (bool, optional): Whether to apply a weighted black point
                compensation. Defaults to False.
            logfile (None | TextIO): File-like object to write progress
                messages to. Defaults to None.
            thread_abort (None | threading.Event, optional): Event to signal
                thread abortion. Defaults to None.
            abortmessage (str): Message to display when the operation is
                aborted. Defaults to "Aborted".

        Raises:
            ValueError: If the PCS is not supported or if the black point
                output does not match the expected format.
        """
        pcs = self.profile and self.profile.connectionColorSpace
        bp_row = list(self.clut[0][0])
        wp_row = list(self.clut[-1][-1])
        nonzero_bp = tuple(bp_out) != (0, 0, 0)
        interp = []
        rinterp = []
        if not use_bpc or nonzero_bp:
            osize = len(self.output[0])
            omaxv = osize - 1.0
            orange = [i / omaxv * 65535 for i in range(osize)]
            for i in range(3):
                interp.append(colormath.Interp(orange, self.output[i]))
                rinterp.append(colormath.Interp(self.output[i], orange))
            for row in (bp_row, wp_row):
                for column, value in enumerate(row):
                    row[column] = interp[column](value)
        method = "apply_bpc" if use_bpc else "apply_black_offset"
        if pcs == b"Lab":
            bp = colormath.Lab2XYZ(*legacy_PCSLab_uInt16_to_dec(*bp_row))
            wp = colormath.Lab2XYZ(*legacy_PCSLab_uInt16_to_dec(*wp_row))
        elif not pcs or pcs == b"XYZ":
            if not pcs:
                warnings.warn(
                    f"LUT16Type.{method}: PCS not specified, assuming XYZ",
                    Warning,
                    stacklevel=2,
                )
            bp = [v / 32768.0 for v in bp_row]
            wp = [v / 32768.0 for v in wp_row]
        else:
            raise ValueError(f"LUT16Type.{method}: Unsupported PCS {pcs!r}")
        if [round(v * 32768) for v in bp] != [round(v * 32768) for v in bp_out]:
            D50 = colormath.get_whitepoint("D50")  # noqa: N806

            from DisplayCAL.icc_profile.tonemap import _mp_apply_black
            from DisplayCAL.multiprocess import pool_slice

            num_workers = 1 if len(self.clut[0]) < 33 else None

            # if pcs != "Lab" and nonzero_bp:
            #     bp_out_offset = bp_out
            #     bp_out = (0, 0, 0)

            if bp != bp_out:
                self.clut = functools.reduce(
                    operator.iadd,
                    pool_slice(
                        _mp_apply_black,
                        self.clut,
                        (
                            pcs,
                            bp,
                            bp_out,
                            wp,
                            use_bpc,
                            weight,
                            D50,
                            interp,
                            rinterp,
                            abortmessage,
                        ),
                        {},
                        num_workers,
                        thread_abort,
                        logfile,
                    ),
                    [],
                )

        # if pcs != "Lab" and nonzero_bp:
        # # Apply black offset to output curves
        # out = [[], [], []]
        # for i in range(2049):
        # v = i / 2048.0
        # X, Y, Z = colormath.blend_blackpoint(v, v, v, (0, 0, 0),
        # bp_out_offset)
        # out[0].append(X * 2048 / 4095.0 * 65535)
        # out[1].append(Y * 2048 / 4095.0 * 65535)
        # out[2].append(Z * 2048 / 4095.0 * 65535)
        # for i in range(2049, 4096):
        # v = i / 4095.0
        # out[0].append(v * 65535)
        # out[1].append(v * 65535)
        # out[2].append(v * 65535)
        # self.output = out

    @property
    def clut(self) -> list:
        """Return the cLUT of the LUT16Type tag.

        Returns:
            list: The cLUT of the LUT16Type tag, a nested list structure
                containing uInt16Number values.
        """
        if self._clut is not None:
            return self._clut

        # Calculate cLUT from tag data
        i, o, g, n = self._i, self._o, self._g, self._n
        tag_data = self._tagData
        self._clut = [
            [
                [
                    uInt16Number(
                        tag_data[
                            52 + n * i * 2 + o * 2 * (g * x + y) + z * 2 : 54
                            + n * i * 2
                            + o * 2 * (g * x + y)
                            + z * 2
                        ]
                    )
                    for z in range(o)
                ]
                for y in range(g)
            ]
            for x in range(int(g**i / g))
        ]
        return self._clut

    @clut.setter
    def clut(self, value: list) -> None:
        """Set the cLUT of the LUT16Type tag.

        Args:
            value (list): The cLUT to set, a nested list structure containing
                uInt16Number values.
        """
        self._clut = value

    def clut_writepng(self, stream_or_filename: str | BinaryIO) -> None:
        """Write the cLUT as a PNG image arranged in grid squares.

        Args:
            stream_or_filename (str | BinaryIO): The filename or
                file-like object to write the PNG image to.

        Raises:
            NotImplementedError: If the output channels are not RGB
                (3 channels).
        """
        if len(self.clut[0][0]) != 3:
            raise NotImplementedError("clut_writepng: output channels != 3")
        imfile.write(self.clut, stream_or_filename)

    def clut_writecgats(self, stream_or_filename: str | BinaryIO) -> None:
        """Write the cLUT as CGATS.

        Args:
            stream_or_filename (str | BinaryIO): The filename or
                file-like object to write the CGATS data to.
        """
        # TODO:
        # Need to take into account input/output curves
        # Currently only supports RGB, A2B direction, and XYZ color space
        if len(self.clut[0][0]) != 3:
            raise NotImplementedError("clut_writecgats: output channels != 3")
        if isinstance(stream_or_filename, str):
            stream = open(stream_or_filename, "wb")  # noqa: SIM115
        else:
            stream = stream_or_filename
        with stream:
            stream.write(
                b"""CTI3
DEVICE_CLASS "DISPLAY"
COLOR_REP "RGB_XYZ"
BEGIN_DATA_FORMAT
SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
BEGIN_DATA
"""
            )
            clutres = len(self.clut[0])
            block = 0
            i = 1
            if self.tagSignature and self.tagSignature.startswith("B2A"):
                interp = [
                    colormath.Interp(
                        input_value, list(range(len(input_value))), use_numpy=True
                    )
                    for input_value in self.input
                ]
            for a in range(clutres):
                for b in range(clutres):
                    for c in range(clutres):
                        R, G, B = [v / (clutres - 1.0) * 100 for v in (a, b, c)]  # noqa: N806
                        if self.tagSignature and self.tagSignature.startswith("B2A"):
                            linear_rgb = [
                                interp[i](v)
                                / (len(interp[i].xp) - 1.0)
                                * (1 + (32767 / 32768.0))
                                * 100
                                for i, v in enumerate(self.clut[block][c])
                            ]
                            X, Y, Z = self.matrix.inverted() * linear_rgb  # noqa: N806
                        else:
                            X, Y, Z = [v / 32768.0 * 100 for v in self.clut[block][c]]  # noqa: N806
                        stream.write(
                            b"%i %7.3f %7.3f %7.3f %10.6f %10.6f %10.6f\n"
                            % (i, R, G, B, X, Y, Z)
                        )
                        i += 1
                    block += 1
            stream.write(b"END_DATA\n")

    @property
    def clut_grid_steps(self) -> int:
        """Return number of grid points per dimension.

        Returns:
            int: The number of grid points per dimension of the cLUT.
        """
        return self._g or len(self.clut[0])

    @property
    def input(self) -> list:
        """Return the input table of the LUT16Type tag.

        Returns:
            list: The input table of the LUT16Type tag, a list of lists
                containing uInt16Number values.
        """
        if self._input is None:
            i, n = self._i, self._n
            tag_data = self._tagData
            self._input = [
                [
                    uInt16Number(
                        tag_data[52 + n * 2 * z + y * 2 : 54 + n * 2 * z + y * 2]
                    )
                    for y in range(n)
                ]
                for z in range(i)
            ]
        return self._input

    @input.setter
    def input(self, value: list) -> None:
        """Set the input table of the LUT16Type tag.

        Args:
            value (list): The input table to set, a list of lists containing
                uInt16Number values.
        """
        self._input = value

    @property
    def input_channels_count(self) -> int:
        """Return number of input channels.

        Returns:
            int: The number of input channels in the LUT16Type tag.
        """
        return self._i or len(self.input)

    @property
    def input_entries_count(self) -> int:
        """Return number of entries per input channel.

        Returns:
            int: The number of entries per input channel in the LUT16Type tag.
        """
        return self._n or len(self.input[0])

    def invert(self) -> None:
        """Invert input and output tables."""
        # Invert input/output 1d LUTs
        for channel in (self.input, self.output):
            for e, entries in enumerate(channel):
                lut = {}
                maxv = len(entries) - 1.0
                for i, entry in enumerate(entries):
                    lut[entry / 65535.0 * maxv] = i / maxv * 65535
                xp = list(lut.keys())
                fp = list(lut.values())
                for i in range(len(entries)):
                    if i not in lut:
                        lut[i] = colormath.interp(i, xp, fp)
                lut = dict_sort(lut)
                channel[e] = list(lut.values())

    def clut_row_apply_per_channel(
        self,
        indexes: list,
        fn: Callable,
        fnargs: None | tuple = None,
        fnkwargs: None | dict = None,
        pcs: None | str = None,
        protect_gray_axis: bool = True,
        protect_dark: bool = False,
        protect_black: bool = True,
        exclude: None | set = None,
    ) -> None:
        """Apply function to channel values of each cLUT row.

        Args:
            indexes (list): List of channel indexes to apply the function to.
            fn (callable): Function to apply to the channel values.
            fnargs (None | tuple, optional): Additional positional arguments to
                pass to the function. Defaults to an empty tuple.
            fnkwargs (None | dict, optional): Additional keyword arguments to
                pass to the function. Defaults to an empty dictionary.
            pcs (None | str, optional): The PCS (Profile Connection Space) to
                use. Defaults to None, which means the PCS will be determined
                from the profile.
            protect_gray_axis (bool, optional): Whether to protect the gray
                axis (diagonal) from modification. Defaults to True.
            protect_dark (bool, optional): Whether to protect dark values from
                modification. Defaults to False.
            protect_black (bool, optional): Whether to protect black values
                from modification. Defaults to True.
            exclude (set, optional): Set of (row_index, column_index) tuples to
                exclude from modification. Defaults to None, which means no
                exclusions will be applied.
        """
        if fnargs is None:
            fnargs = ()

        if fnkwargs is None:
            fnkwargs = {}

        clutres = len(self.clut[0])
        block = -1
        for i, row in enumerate(self.clut):
            channels = {}
            for k in indexes:
                channels[k] = []
            if protect_gray_axis or protect_dark or protect_black or exclude:
                if i % clutres == 0:
                    block += 1
                    gray_col_i = block if pcs == "XYZ" else clutres // 2  # L*a*b*
                    gray_row_i = i + gray_col_i
                fnkwargs["protect"] = []
            for j, column in enumerate(row):
                is_exclude = exclude and (i, j) in exclude
                if is_exclude or (
                    protect_gray_axis and (i == gray_row_i and j == gray_col_i)
                ):
                    if DEBUG:
                        print(
                            "protect", "exclude" if is_exclude else "gray", i, j, column
                        )
                    fnkwargs["protect"].append(j)
                elif (protect_dark and sum(column) < 65535 * 0.03125 * 3) or (
                    protect_black and min(column) == max(column) == 0
                ):
                    if DEBUG:
                        print("protect dark", i, j, column)
                    fnkwargs["protect"].append(j)
                for k in indexes:
                    channels[k].append(column[k])
            for k in channels:
                values = channels[k]
                channels[k] = fn(values, *fnargs, **fnkwargs)
            for j, column in enumerate(row):
                for k in indexes:
                    column[k] = channels[k][j]

    def clut_shift_columns(
        self,
        order: tuple[int, int, int] = (1, 2, 0),
    ) -> None:
        """Shift cLUT columns, altering slowest to fastest changing column.

        Args:
            order (tuple[int, int, int]): The order of the channels to shift.
                Default is (1, 2, 0), which means the first channel will be
                the slowest changing, the second channel will be the middle
                changing, and the third channel will be the fastest changing.

        Raises:
            NotImplementedError: If the number of input channels is not 3.
        """
        if len(self.input) != 3:
            raise NotImplementedError("input channels != 3")
        steps = len(self.clut[0])
        clut = []
        coord = [0, 0, 0]
        for a in range(steps):
            coord[order[0]] = a
            for b in range(steps):
                coord[order[1]] = b
                clut.append([])
                for c in range(steps):
                    coord[order[2]] = c
                    z, y, x = coord
                    clut[-1].append(self.clut[z * steps + y][x])
        self.clut = clut

    @property
    def matrix(self) -> colormath.Matrix3x3:
        """Return the matrix of the LUT16Type tag.

        Returns:
            colormath.Matrix3x3: The matrix of the LUT16Type tag.
        """
        if self._matrix is None:
            tag_data = self._tagData
            return colormath.Matrix3x3(
                [
                    (
                        s15Fixed16Number(tag_data[12:16]),
                        s15Fixed16Number(tag_data[16:20]),
                        s15Fixed16Number(tag_data[20:24]),
                    ),
                    (
                        s15Fixed16Number(tag_data[24:28]),
                        s15Fixed16Number(tag_data[28:32]),
                        s15Fixed16Number(tag_data[32:36]),
                    ),
                    (
                        s15Fixed16Number(tag_data[36:40]),
                        s15Fixed16Number(tag_data[40:44]),
                        s15Fixed16Number(tag_data[44:48]),
                    ),
                ]
            )
        return self._matrix

    @matrix.setter
    def matrix(self, value: colormath.Matrix3x3) -> None:
        """Set the matrix of the LUT16Type tag.

        Args:
            value (colormath.Matrix3x3): The matrix to set.
        """
        self._matrix = value

    @property
    def output(self) -> list:
        """Return the output table of the LUT16Type tag.

        Returns:
            list: The output table of the LUT16Type tag.
        """
        if self._output is None:
            i, o, g, n, m = self._i, self._o, self._g, self._n, self._m
            tag_data = self._tagData
            self._output = [
                [
                    uInt16Number(
                        tag_data[
                            52 + n * i * 2 + m * 2 * z + y * 2 + g**i * o * 2 : 54
                            + n * i * 2
                            + m * 2 * z
                            + y * 2
                            + g**i * o * 2
                        ]
                    )
                    for y in range(m)
                ]
                for z in range(o)
            ]
        return self._output

    @output.setter
    def output(self, value: list) -> None:
        """Set the output table of the LUT16Type tag.

        Args:
            value (list): The output table to set, which should be a list of
                lists containing uInt16Number values.
        """
        self._output = value

    @property
    def output_channels_count(self) -> int:
        """Return number of output channels.

        Returns:
            int: The number of output channels of the cLUT.
        """
        return self._o or len(self.output)

    @property
    def output_entries_count(self) -> int:
        """Return number of entries per output channel.

        Returns:
            int: The number of entries per output channel of the cLUT.
        """
        return self._m or len(self.output[0])

    def smooth(
        self,
        diagpng: int = 2,
        pcs: None | str = None,
        filename: None | str = None,
        logfile: None | TextIO = None,
        debug_: int = 0,
    ) -> None:
        """Apply extra smoothing to the cLUT.

        Args:
            diagpng (int, optional): If 2, generate a diagnostic PNG image of
                the cLUT. If 1, generate a diagnostic PNG image only if the
                cLUT is modified. If 0, do not generate a diagnostic image.
                Defatult is 2.
            pcs (None | str, optional): The profile connection space, either
                "XYZ" or "Lab". Default is None, which uses the profile's
                connectionColorSpace if available.
            filename (None | str, optional): The filename to save the
                diagnostic image to. Default is None, which uses the
                profile's filename if available.
            logfile (None | TextIO, optional): A file-like object to write log
                messages to. Default is None, which means no logging.
            debug_ (int, optional): Debug level, where 0 means no debug, 1
                means debug with some output, and 2 means full debug output.
                Default is 0.

        Raises:
            TypeError: If PCS is not specified and no profile is available.
        """
        if not pcs:
            if self.profile:
                pcs = self.profile.connectionColorSpace
            else:
                raise TypeError("PCS not specified")

        if not filename and self.profile:
            filename = self.profile.filename

        clutres = len(self.clut[0])

        sig = self.tagSignature or id(self)

        if diagpng and filename and len(self.output) == 3:
            # Generate diagnostic images
            fname, _ = os.path.splitext(filename)
            diag_fname = f"{fname}.{sig}.post.CLUT.png"
            if diagpng == 2 and not os.path.isfile(diag_fname):
                self.clut_writepng(diag_fname)
        else:
            diagpng = 0

        if logfile:
            logfile.write(f"Smoothing {sig}...\n")
        # Create a list of <clutres> number of 2D grids, each one with a
        # size of (width x height) <clutres> x <clutres>
        grids = []
        for i, block in enumerate(self.clut):
            if i % clutres == 0:
                grids.append([])
            grids[-1].append([])
            for RGB in block:  # noqa: N806
                grids[-1][-1].append(RGB)
        for i, grid in enumerate(grids):
            for y in range(clutres):
                for x in range(clutres):
                    is_dark = sum(grid[y][x]) < 65535 * 0.03125 * 3
                    if pcs == "XYZ":
                        is_gray = x == y == i
                    elif clutres // 2 != clutres / 2.0:
                        # For CIELab cLUT, gray will only
                        # fall on a cLUT point if uneven cLUT res
                        is_gray = x == y == clutres // 2
                    else:
                        is_gray = False
                    # print(
                    #     i, y, x,
                    #     "{:d} {:d} {:d}".format(*(int(v / 655.35 * 2.55)
                    #     for v in grid[y][x])),
                    #     is_dark,
                    #     raw_input(is_gray) if is_gray else "",
                    # )
                    if is_dark or is_gray:
                        # Don't smooth dark colors and gray axis
                        continue
                    RGB = [[v] for v in grid[y][x]]  # noqa: N806
                    # Use either "plus"-shaped or box filter depending if one
                    # channel is fully saturated
                    if clutres - 1 in (y, x) or 0 in (x, y):
                        # Filter with a "plus" (+) shape
                        # Smoothing factor for L*a*b* -> RGB cLUT above 50%
                        smooth = 0.25 if pcs == "Lab" and i > clutres / 2.0 else 0.5
                        for j, c in enumerate((x, y)):
                            # Omit corners and perpendicular axis
                            if 0 < c < clutres - 1:
                                for n in (-1, 1):
                                    yi, xi = (y, y + n)[j], (x + n, x)[j]
                                    if -1 < xi < clutres and -1 < yi < clutres:
                                        RGBn = grid[yi][xi]  # noqa: N806
                                        if debug_ == 2:
                                            if i < clutres - 1 or grid[y][x] != [
                                                16384,
                                                16384,
                                                16384,
                                            ]:
                                                grid[y][x] = [32768, 32768, 32768]
                                            if x == y == clutres - 2:
                                                RGBn[:] = [16384, 16384, 16384]
                                        for k in range(3):
                                            RGB[k].append(
                                                RGBn[k] * smooth
                                                + RGB[k][0] * (1 - smooth)
                                            )
                    else:
                        # Box filter, 3x3
                        # Center pixel weight = 1.0, surround = 2/3, corners = 1/3
                        if debug_ == 1:
                            grid[y][x] = [32768, 32768, 32768]
                        for j in (0, 1):
                            for n in (-1, 1):
                                for yi, xi in [
                                    ((y, y + n)[j], (x + n, x)[j]),
                                    (y - n, (x + n, x - n)[j]),
                                ]:
                                    if -1 < xi < clutres and -1 < yi < clutres:
                                        RGBn = grid[yi][xi]  # noqa: N806
                                        if yi != y and xi != x:
                                            smooth = 1 / 3.0
                                        else:
                                            smooth = 2 / 3.0
                                        if debug_ == 1 and x == y == clutres - 2:
                                            RGBn[:] = (v * (1 - smooth) for v in RGBn)
                                        for k in range(3):
                                            RGB[k].append(
                                                RGBn[k] * smooth
                                                + RGB[k][0] * (1 - smooth)
                                            )
                    if not debug_:
                        grid[y][x] = [sum(v) / float(len(v)) for v in RGB]
            for j, row in enumerate(grid):
                self.clut[i * clutres + j] = [
                    [min(v, 65535) for v in RGB] for RGB in row
                ]

        if diagpng and filename:
            self.clut_writepng(f"{fname}.{sig}.post.CLUT.smooth.png")

    def smooth2(
        self,
        diagpng: int = 2,
        pcs: None | str = None,
        filename: None | str = None,
        logfile: None | TextIO = None,
        window: tuple[float, float, float] = (1 / 16.0, 1, 1 / 16.0),
    ) -> None:
        """Apply extra smoothing to the cLUT.

        Args:
            diagpng (int, optional): Diagnostic PNG generation level (0, 1, 2,
                or 3). If `diagpng` is 0, no diagnostic images will be
                generated. If `diagpng` is 1, only the final smoothed cLUT will
                be saved. If `diagpng` is 2, the original and final smoothed
                cLUT will be saved. If `diagpng` is 3, intermediate steps will
                also be saved. If `diagpng` is 2 or 3, the filename will be
                used to generate diagnostic PNG files with the signature of the
                tag appended to the filename, e.g.,
                `filename.<signature>.post.CLUT.png`.
            pcs (None | str): The profile connection space (PCS) to use, e.g.,
                "Lab" or "XYZ". Default is None, which will use the PCS from
                the profile if available, or raise a TypeError if no PCS is
                specified and no profile is available.
            filename (None | str): The filename to save diagnostic images to.
                Default is None, which will use the profile filename if
                available.
            logfile (None | TextIO): A file-like object to write log messages
                to. Default is None, which means no logging will be done.
            window (tuple[float, float, float]): The smoothing window as a
                tuple of three floats, representing the weights for the R, G,
                and B channels. Default value is (1/16.0, 1, 1/16.0).

        Raises:
            TypeError: If PCS is not specified and no profile is available.
        """
        if not pcs:
            if self.profile:
                pcs = self.profile.connectionColorSpace
            else:
                raise TypeError("PCS not specified")

        if not filename and self.profile:
            filename = self.profile.filename

        clutres = len(self.clut[0])

        sig = self.tagSignature or id(self)

        if diagpng and filename and len(self.output) == 3:
            # Generate diagnostic images
            fname, ext = os.path.splitext(filename)
            diag_fname = f"{fname}.{sig}.post.CLUT.png"
            if diagpng == 2 and not os.path.isfile(diag_fname):
                self.clut_writepng(diag_fname)
        else:
            diagpng = 0

        if logfile:
            logfile.write(f"Smoothing {sig}...\n")

        for i in range(3):
            state = ("original", "pass", "final")[i]
            if diagpng != 3 and i != 1:
                continue
            for j, (order, channels) in enumerate(
                [
                    (None, "BGR"),
                    ((1, 2, 0), "RBG"),
                    ((0, 2, 1), "BRG"),
                    ((2, 1, 0), "GRB"),
                    ((0, 2, 1), "RGB"),
                    ((2, 0, 1), "GBR"),
                    ((0, 2, 1), "BGR"),
                ]
            ):
                if order:
                    if DEBUG:
                        print("Shifting order to", channels)
                    self.clut_shift_columns(order)
                if i == 1 and j != 6:
                    if DEBUG:
                        print("Smoothing")
                    exclude = None
                    protect_gray_axis = True
                    if pcs == "Lab":
                        if clutres // 2 != clutres / 2.0:
                            # For CIELab cLUT, gray will only
                            # fall on a cLUT point if uneven cLUT res
                            if channels in ("RBG", "RGB"):
                                exclude = [
                                    ((clutres // 2 + 1) * (clutres - 1), col)
                                    for col in range(clutres)
                                ]
                                protect_gray_axis = False
                            elif channels in ("BRG", "GRB"):
                                exclude = [
                                    ((clutres // 2) * clutres + y, clutres // 2)
                                    for y in range(clutres)
                                ]
                                protect_gray_axis = False
                        else:
                            protect_gray_axis = False
                    self.clut_row_apply_per_channel(
                        (0, 1, 2),
                        colormath.smooth_avg,
                        (),
                        {"window": window},
                        pcs,
                        protect_gray_axis,
                        exclude=exclude,
                    )
                if diagpng == 3 and filename and j != 6:
                    if DEBUG:
                        print("Writing diagnostic PNG for", state, channels)
                    self.clut_writepng(
                        f"{fname}.{sig}.post.CLUT.{channels}.{state}.png"
                    )

        if diagpng and filename:
            self.clut_writepng(f"{fname}.{sig}.post.CLUT.smooth.png")

    @property
    def tagData(self) -> bytes:  # noqa: N802
        """Return raw tag data.

        Returns:
            bytes: Raw tag data for the LUT16Type tag.
        """
        if (self._matrix, self._input, self._clut, self._output) == (None,) * 4:
            return self._tagData
        tag_data = [
            b"mft2",
            b"\0" * 4,
            uInt8Number_tohex(len(self.input)),
            uInt8Number_tohex(len(self.output)),
            uInt8Number_tohex(len(self.clut and self.clut[0])),
            b"\0",
            s15Fixed16Number_tohex(self.matrix[0][0]),
            s15Fixed16Number_tohex(self.matrix[0][1]),
            s15Fixed16Number_tohex(self.matrix[0][2]),
            s15Fixed16Number_tohex(self.matrix[1][0]),
            s15Fixed16Number_tohex(self.matrix[1][1]),
            s15Fixed16Number_tohex(self.matrix[1][2]),
            s15Fixed16Number_tohex(self.matrix[2][0]),
            s15Fixed16Number_tohex(self.matrix[2][1]),
            s15Fixed16Number_tohex(self.matrix[2][2]),
            uInt16Number_tohex(len(self.input and self.input[0])),
            uInt16Number_tohex(len(self.output and self.output[0])),
        ]
        for entries in self.input:
            tag_data.extend(uInt16Number_tohex(v) for v in entries)
        for block in self.clut:
            for entries in block:
                tag_data.extend(uInt16Number_tohex(v) for v in entries)
        for entries in self.output:
            tag_data.extend(uInt16Number_tohex(v) for v in entries)
        return b"".join(tag_data)

    @tagData.setter
    def tagData(self, tagData: bytes) -> None:  # noqa: N802, N803
        """Set raw tag data.

        Args:
            tagData (bytes): Raw tag data.
        """
        self._tagData = tagData
