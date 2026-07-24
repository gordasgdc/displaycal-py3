#!/usr/bin/env python3

import os
import sys
from binascii import hexlify

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL import xrandr
from DisplayCAL.icc_profile import ICCProfile

for i in range(5):
    # Show ICC info for first five screens / outputs
    try:
        x_icc_c = xrandr.get_atom("_ICC_PROFILE" if i < 1 else "_ICC_PROFILE_%i" % i)
    except ValueError:
        x_icc_c = None
    if x_icc_c:
        print("Root window %s" % ("_ICC_PROFILE" if i < 1 else "_ICC_PROFILE_%i" % i))
        x_icc = ICCProfile("".join(chr(n) for n in x_icc_c))
        print("Description:", x_icc.getDescription())
        print("Checksum ID:", hexlify(x_icc.calculate_id()))
        print("")
    try:
        xrr_icc_c = xrandr.get_output_property(i, "_ICC_PROFILE")
    except ValueError:
        xrr_icc_c = None
    if xrr_icc_c:
        print("XRandR Output %i _ICC_PROFILE:" % i)
        xrr_icc = ICCProfile("".join(chr(n) for n in xrr_icc_c))
        print("Description:", xrr_icc.getDescription())
        print("Checksum ID:", hexlify(xrr_icc.calculate_id()))
        print("")
