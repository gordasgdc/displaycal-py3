"""Plain-language help for the test chart editor (which keeps every ArgyllCMS option).

The editor's fields follow the options of ArgyllCMS ``targen``; this adds an
introduction and a tooltip per field that says what it changes. Source of the
meanings: https://www.argyllcms.com/doc/targen.html (read 2026-10-19).
"""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel

from DisplayCAL import localization as lang

TARGEN_DOC = "https://www.argyllcms.com/doc/targen.html"

#: widget attribute -> help id (``tc.help.<id>``)
HELP = {
    "tc_white_patches": "white",
    "tc_black_patches": "black",
    "tc_single_channel_patches": "single",
    "tc_gray_patches": "gray",
    "tc_multi_steps": "multi",
    "tc_multi_bcc_cb": "bcc",
    "tc_fullspread_patches": "fullspread",
    "tc_algo": "algo",
    "tc_adaption_slider": "adaption",
    "tc_adaption_intctrl": "adaption",
    "tc_angle_slider": "angle",
    "tc_angle_intctrl": "angle",
    "tc_gamma_floatctrl": "gamma",
    "tc_neutral_axis_emphasis_slider": "neutral",
    "tc_neutral_axis_emphasis_intctrl": "neutral",
    "tc_dark_emphasis_slider": "dark",
    "tc_dark_emphasis_intctrl": "dark",
    "tc_precond": "precond",
    "tc_precond_profile": "precond",
    "tc_filter": "sphere",
    "change_patch_order_ctrl": "order",
    "preview_btn": "create",
}


def apply_help(window, root_layout) -> None:
    """Add the introduction on top and a tooltip to every known field."""
    intro = QLabel(
        lang.getstr("tc.help.intro")
        + f' <a href="{TARGEN_DOC}">{lang.getstr("tc.help.source")}</a>'
    )
    intro.setWordWrap(True)
    intro.setTextFormat(Qt.RichText)
    intro.setOpenExternalLinks(True)
    intro.setObjectName("testchart_editor_intro")
    root_layout.insertWidget(0, intro)
    for attr, hid in HELP.items():
        widget = getattr(window, attr, None)
        if widget is not None:
            widget.setToolTip(lang.getstr(f"tc.help.{hid}"))
