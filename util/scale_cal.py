#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DisplayCAL.cgats import CGATS


def main(calfilename, caloutfilename, r_max, g_max, b_max):
    cal = CGATS(calfilename)
    for values in cal[0].DATA.itervalues():
        values["RGB_R"] *= float(r_max)
        values["RGB_G"] *= float(g_max)
        values["RGB_B"] *= float(b_max)

    cal.write(caloutfilename)


if __name__ == "__main__":
    if len(sys.argv[1:]) == 5:
        main(*sys.argv[1:])
    else:
        print(
            "Usage: %s CALFILENAME CALOUTFILENAME R_MAX G_MAX B_MAX"
            % os.path.basename(__file__)
        )
