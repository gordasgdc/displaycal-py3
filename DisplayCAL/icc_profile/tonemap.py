"""Multiprocessing workers for cLUT black point blending and HDR tonemapping."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from DisplayCAL import colormath
from DisplayCAL.icc_profile.codecs import (
    legacy_PCSLab_dec_to_uInt16,
    legacy_PCSLab_uInt16_to_dec,
)

if TYPE_CHECKING:
    import multiprocessing
    import threading


def _blend_blackpoint(
    row: tuple[float, float, float],
    bp_in: None | tuple,
    bp_out: None | tuple,
    wp: None | float | str | list | tuple = None,
    use_bpc: bool = False,
    weight: bool = False,
) -> tuple[float, float, float]:
    """Blend black point compensation or offset into XYZ values.

    Args:
        row (tuple): A tuple containing XYZ values.
        bp_in (tuple): Input black point (X, Y, Z).
        bp_out (tuple): Output black point (X, Y, Z).
        wp (None | float | str | list | tuple, optional): White point, if using
            BPC.
        use_bpc (bool, optional): Whether to use black point compensation.
        weight (bool, optional): Whether to apply weighting.

    Returns:
        tuple: Adjusted XYZ values after applying black point compensation or
            offset.
    """
    X, Y, Z = row  # noqa: N806
    if use_bpc:
        X, Y, Z = colormath.apply_bpc(X, Y, Z, bp_in, bp_out, wp, weight=weight)  # noqa: N806
    else:
        X, Y, Z = colormath.blend_blackpoint(X, Y, Z, bp_in, bp_out, wp)  # noqa: N806
    return X, Y, Z


def _mp_apply(
    blocks: list,
    thread_abort_event: threading.Event,
    progress_queue: multiprocessing.Queue,
    pcs: str,
    fn: Callable,
    args: tuple,
    D50: None | float | str | list | tuple,  # noqa: N803
    interp: list,
    rinterp: list,
    abortmessage: str = "Aborted",
) -> list:
    """Worker for applying function to cLUT.

    This should be spawned as a multiprocessing process.

    Args:
        blocks (list): List of blocks to process.
        thread_abort_event (threading.Event): Event to signal abort.
        progress_queue (multiprocessing.Queue): Queue for progress updates.
        pcs (str): PCS type, either "Lab" or "XYZ".
        fn (callable): Function to apply to each block.
        args (tuple): Arguments to pass to the function.
        D50 (None | float | str | list | tuple): D50 whitepoint.
        interp (list): Interpolation functions for each channel.
        rinterp (list): Reverse interpolation functions for each channel.
        abortmessage (str): Message to return if aborted.

    Returns:
        list: Processed blocks after applying the function.
    """
    from DisplayCAL.debughelpers import Info

    for interp_tuple in (interp, rinterp):
        if interp_tuple:
            # Use numpy for speed
            interp_list = list(interp_tuple)
            for i, ointerp in enumerate(interp_list):
                interp_list[i] = colormath.Interp(
                    ointerp.xp, ointerp.fp, use_numpy=True
                )
                interp_list[i].lookup = ointerp.lookup
            if interp_tuple is interp:
                interp = interp_list
            else:
                rinterp = interp_list
    prevperc = 0
    count = 0
    numblocks = len(blocks)
    for block in blocks:
        if thread_abort_event and thread_abort_event.is_set():
            return Info(abortmessage)
        for i, row in enumerate(block):
            if interp:
                for column, value in enumerate(row):
                    row[column] = interp[column](value)
            if pcs == "Lab":
                L, a, b = legacy_PCSLab_uInt16_to_dec(*row)  # noqa: N806
                X, Y, Z = colormath.Lab2XYZ(L, a, b, D50)  # noqa: N806
            else:
                X, Y, Z = [v / 32768.0 for v in row]  # noqa: N806
            X, Y, Z = fn((X, Y, Z), *args)  # noqa: N806
            if pcs == "Lab":
                L, a, b = colormath.XYZ2Lab(X, Y, Z, D50)  # noqa: N806
                row = [
                    min(max(0, v), 65535) for v in legacy_PCSLab_dec_to_uInt16(L, a, b)
                ]
            else:
                row = [min(max(0, v) * 32768.0, 65535) for v in (X, Y, Z)]
            if rinterp:
                for column, value in enumerate(row):
                    row[column] = rinterp[column](value)
            block[i] = row
        count += 1.0
        perc = round(count / numblocks * 100)
        if progress_queue and perc > prevperc:
            progress_queue.put(perc - prevperc)
            prevperc = perc
    return blocks


def _mp_apply_black(
    blocks: list,
    thread_abort_event: threading.Event,
    progress_queue: multiprocessing.Queue,
    pcs: str,
    bp: tuple[float, float, float],
    bp_out: tuple[float, float, float],
    wp: None | float | str | list | tuple,
    use_bpc: bool,
    weight: bool,
    D50: None | float | str | list | tuple,  # noqa: N803
    interp: list,
    rinterp: list,
    abortmessage: str = "Aborted",
) -> list:
    """Worker for applying black point compensation or offset.

    This should be spawned as a multiprocessing process.

    Args:
        blocks (list): List of blocks to process.
        thread_abort_event (threading.Event): Event to signal abort.
        progress_queue (multiprocessing.Queue): Queue for progress updates.
        pcs (str): PCS type, either "Lab" or "XYZ".
        bp (tuple): Black point to apply.
        bp_out (tuple): Black point output.
        wp (None | float | str | list | tuple): White point, if using BPC.
        use_bpc (bool): Whether to use black point compensation.
        weight (bool): Whether to apply weighting.
        D50 (None | float | str | list | tuple): D50 whitepoint.
        interp (list): Interpolation functions for each channel.
        rinterp (list): Reverse interpolation functions for each channel.
        abortmessage (str): Message to return if aborted.

    Returns:
        list: Processed blocks after applying black point compensation or
            offset.
    """
    return _mp_apply(
        blocks,
        thread_abort_event,
        progress_queue,
        pcs,
        _blend_blackpoint,
        (bp, bp_out, wp if use_bpc else None, use_bpc, weight),
        D50,
        interp,
        rinterp,
        abortmessage,
    )


def _mp_hdr_tonemap(
    HDR_XYZ: list,  # noqa: N803
    thread_abort_event: threading.Event,
    progress_queue: multiprocessing.Queue,
    rgb_space: None | str | list | tuple,
    maxv: float,
    sat: float,
    cat: str = "Bradford",
) -> list:
    """Worker for HDR tonemapping.

    This should be spawned as a multiprocessing process

    Args:
        HDR_XYZ (list): List of HDR XYZ tuples.
        thread_abort_event (threading.Event): Event to signal abort.
        progress_queue (multiprocessing.Queue): Queue for progress updates.
        rgb_space (None | str | list | tuple): The RGB space to use for
            conversion. Defaults to sRGB if not set. If a string is given, it
            must be a valid RGB space name. If a list or tuple is given, it
            must be in the format (gamma, whitepoint, red, green, blue). The
            whitepoint can be a string (e.g. "D50"), a tuple of XYZ
            coordinates, or a color temperature in degrees K (float or int).
            The gamma should be a float. The RGB primaries red, green, blue
            should be lists or tuples of xyY coordinates (only x and y will be
            used, so Y can be zero or None).
        maxv (float): Maximum value for normalization.
        sat (float): Saturation factor for ICtCp.
        cat (str): Chromatic adaptation transform to use, defaults to
            "Bradford".

    Returns:
        list: Processed HDR XYZ tuples.
    """
    prevperc = 0
    amount = len(HDR_XYZ)
    dI = 0  # noqa: N806
    dI_max = 0  # noqa: N806
    dC = 0  # noqa: N806
    dC_max = 0  # noqa: N806
    I_reduced_count = 0  # noqa: N806
    its_hi = 0  # Highest number pf iterations seen per color
    for i, (RGB_in, ICtCp_XYZ, RGB_ICtCp_XYZ) in enumerate(HDR_XYZ):  # noqa: N806
        if thread_abort_event and thread_abort_event.is_set():
            return [False]
        is_neutral = all(v == RGB_in[0] for v in RGB_in)
        for j, XYZ in enumerate((ICtCp_XYZ, RGB_ICtCp_XYZ)):  # noqa: N806
            if j == 0 and (sat == 1 or ICtCp_XYZ == RGB_ICtCp_XYZ):
                # Set ICtCp_XYZ to the same object as RGB_ICtCp_XYZ which we
                # are going to change in-place in the next iteration of the loop
                # so that at the end of this loop, both will point to the same
                # changed data
                ICtCp_XYZ = RGB_ICtCp_XYZ  # noqa: N806
                continue
            X, Y, Z = XYZ  # noqa: N806
            H = None  # noqa: N806
            its = 10000  # Remaining iterations (limit)
            while not is_neutral and its:
                X_D50, Y_D50, Z_D50 = colormath.adapt(  # noqa: N806
                    *(v / maxv for v in (X, Y, Z)),
                    whitepoint_source=rgb_space[1],
                    cat=cat,
                )
                negative_clip = min(X_D50, Y_D50, Z_D50) < 0
                positive_clip = (
                    round(X_D50, 4) > 0.9642 or Y_D50 > 1 or round(Z_D50, 4) > 0.8249
                )
                if not (negative_clip or positive_clip):
                    break
                if H is None:
                    # Record hue angle
                    H = colormath.RGB2HSV(*RGB_in)[0]  # noqa: N806
                    # This is the initial intensity, and hue + saturation
                    I, Ct, Cp = colormath.XYZ2ICtCp(X, Y, Z)  # noqa: N806
                    Io = I  # noqa: N806
                    Co = colormath.Lab2LCHab(I, Ct, Cp)[1]  # noqa: N806
                # Desaturate
                Ct *= 0.99  # noqa: N806
                Cp *= 0.99  # noqa: N806
                # Update XYZ
                X, Y, Z = colormath.ICtCp2XYZ(I, Ct, Cp)  # noqa: N806
                if Y > XYZ[1]:  # noqa: SIM300
                    # Desaturating CtCp increases Y!
                    # As we desaturate different amounts per color,
                    # restore initial Y if lower than adjusted Y
                    # to keep luminance relation
                    X, Y, Z = (v / Y * XYZ[1] for v in (X, Y, Z))  # noqa: N806
                    I, Ct, Cp = colormath.XYZ2ICtCp(X, Y, Z)  # noqa: N806
                its -= 1
            if H is not None and round(Io - I, 4):
                # Intensity was reduced by >= 0.0001, gather statistics
                C = colormath.Lab2LCHab(I, Ct, Cp)[1]  # noqa: N806
                dI += Io - I  # noqa: N806
                dI_max = max(dI_max, Io - I)  # noqa: N806
                dC += Co - C  # noqa: N806
                dC_max = max(dC_max, Co - C)  # noqa: N806
                I_reduced_count += 1  # noqa: N806
            if not its:
                # Max iterations exceeded, print diagnostics
                # XXX: This should not happen (testing OK)
                oX_D50, oY_D50, oZ_D50 = colormath.adapt(  # noqa: N806
                    *(v / maxv for v in XYZ), whitepoint_source=rgb_space[1], cat=cat
                )
                X_D50, Y_D50, Z_D50 = colormath.adapt(  # noqa: N806
                    *(v / maxv for v in (X, Y, Z)),
                    whitepoint_source=rgb_space[1],
                    cat=cat,
                )
                print(
                    "Reached iteration limit, XYZ "
                    f"{oX_D50:.4f} {oY_D50:.4f} {oZ_D50:.4f} -> "
                    f"{X_D50:.4f} {Y_D50:.4f} {Z_D50:.4f}"
                )
            its_hi = max(its_hi, 10000 - its)
            XYZ[:] = X, Y, Z
        HDR_XYZ[i] = (RGB_in, ICtCp_XYZ, RGB_ICtCp_XYZ)
        perc = round((i + 1.0) / amount * 50)
        if progress_queue and perc > prevperc:
            progress_queue.put(perc - prevperc)
            prevperc = perc
    if I_reduced_count:
        # Intensity was reduced, print informational statistics
        print(
            f"Max iterations {int(its_hi):d} "
            f"dI avg {dI / I_reduced_count:.4f} "
            f"max {dI_max:.4f} "
            f"dC avg {dC / I_reduced_count:.4f} "
            f"max {dC_max:.4f}"
        )
    elif its_hi:
        print("Max iterations", its_hi)
    return HDR_XYZ
