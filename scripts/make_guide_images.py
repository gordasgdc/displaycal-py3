#!/usr/bin/env python3
"""Regenerate the guide images (PDF guides + site) in the proof-sheet look, per language.

Offscreen, 2x resolution, demonstration data (every image carries the band). Writes
``<out>/<lang>/<name>.png`` with the names the guides use. Usage:

    make_guide_images.py <out_dir> [ro,en,es] [light|dark]
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
NAMES = {
    "guide_1_monitor": "step1",
    "guide_2_goal": "step2",
    "guide_3_prepare": "step3",
    "guide_4_measure": "step4",
    "guide_5_finish": "step5",
    "adv_display_instrument_more": "monitor_instrument_full",
    "adv_calibration_more": "calibrare_full",
    "adv_profiling_more": "profilare_full",
    "adv_lut3d_more": "lut3d_full",
    "adv_verification_more": "verificare",
    "tool_synth_profile": "creeaza_profil_sintetic",
    "tool_lut3d": "creeaza_lut3d_standalone",
    "tool_profile_info": "profile_info",
    "tool_curve_viewer": "curbe",
    "tool_log": "jurnal",
    "dlg_recovery": "recuperare",
    "dlg_progress": "progres",
    "dlg_diagnostic": "diagnostic",
    "dlg_profile_finish": "profil_creat",
    "dlg_testchart_editor": "editor_diagrama",
}


def main() -> None:
    out = sys.argv[1]
    langs = (sys.argv[2] if len(sys.argv) > 2 else "ro,en,es").split(",")
    theme = sys.argv[3] if len(sys.argv) > 3 else "light"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", CAPTURE_DPR="2", DEMO_PLAN="10986:500",
               SHOT_HEIGHTS="guide_1_monitor=720,guide_2_goal=1010,guide_5_finish=900")
    for lang in langs:
        tmp = tempfile.mkdtemp(prefix=f"gi_{lang}_")
        subprocess.run(
            [sys.executable, os.path.join(HERE, "capture_review.py"), tmp, "--lang", lang, "--theme", theme,
             "--size", "1180x980", "--only", ",".join(NAMES)],
            check=True, env=env,
        )
        src = os.path.join(tmp, lang, theme)
        dst = os.path.join(out, lang)
        os.makedirs(dst, exist_ok=True)
        for f in sorted(os.listdir(src)):
            if not f.endswith(".png"):
                continue
            key = f.split("_", 1)[1][:-4]
            if key in NAMES:
                shutil.copy(os.path.join(src, f), os.path.join(dst, NAMES[key] + ".png"))
        shutil.rmtree(tmp)
        print(lang, "->", dst)


if __name__ == "__main__":
    main()
