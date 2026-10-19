"""Section headers for the advanced tabs: the decision, and what each setting changes.

One :class:`SectionHeader` sits above the controls of a decision (for example
"What the screen should look like"). It shows the section's purpose and a
disclosure that lists, for every setting in the section: what it changes, when
it fits, unit and the application's default, what it depends on, whether it is
required / context-dependent / optional, and -- live -- *why* it is unavailable
right now. The controls themselves, their order and their configuration are
untouched, so the guided and the advanced mode keep sharing one configuration.
"""

from __future__ import annotations

from html import escape

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from DisplayCAL import config
from DisplayCAL import localization as lang
from DisplayCAL import settings_help as sh
from DisplayCAL.ui import text_scale


def _tr(key: str) -> str:
    return lang.getstr(key)


def muted_css() -> str:
    """Secondary text colour with WCAG AA contrast (see :mod:`text_scale`)."""
    return text_scale.muted_css()


def _has(key: str) -> bool:
    return lang.getstr(key) != key


# --- defaults -----------------------------------------------------------------


def default_text(item: sh.Item) -> str:
    """The application's default for this setting, as readable text ('' if none)."""
    d = config.DEFAULTS
    get = d.get

    def onoff(k: str) -> str:
        return _tr("help.val.on") if get(k) else _tr("help.val.off")

    i = item.id
    if i in ("whitelevel_drift", "blacklevel_drift", "update_cal", "interactive", "bpc", "lut3d_create", "lut3d_apply_cal"):
        return onoff(item.cfg[0])
    if i == "update_delay":
        return f"{get('measure.min_display_update_delay_ms')} ms"
    if i == "settle_mult":
        return f"{get('measure.display_settle_time_mult')} ×"
    if i == "ffp":
        return (
            f"{get('patterngenerator.ffp_insertion.interval')} s / "
            f"{get('patterngenerator.ffp_insertion.duration')} s / "
            f"{round(float(get('patterngenerator.ffp_insertion.level')) * 100)} %"
        )
    if i == "whitepoint":
        return f"{get('whitepoint.colortemp')} K"
    if i == "white_level":
        return f"{get('calibration.luminance')} cd/m²"
    if i == "tone_curve":
        kind = _tr("trc.type.absolute") if get("trc.type") == "G" else _tr("trc.type.relative")
        return f"{_tr('trc.gamma')} {get('trc')} ({kind})"
    if i == "black_offset":
        return f"{round(float(get('calibration.black_output_offset')) * 100)} %"
    if i == "black_point":
        return f"{round(float(get('calibration.black_point_correction')) * 100)} % · {get('calibration.black_point_rate')}"
    if i == "cal_quality":
        return _tr(f"help.val.quality.{get('calibration.quality')}")
    if i == "profile_quality":
        return _tr(f"help.val.quality.{get('profile.quality')}")
    if i == "testchart":
        return _tr("help.val.testchart.auto") if get("testchart.file") == "auto" else str(get("testchart.file"))
    if i == "lut3d_trc":
        return f"{get('3dlut.trc')} · {get('3dlut.trc_gamma')}"
    if i == "lut3d_format":
        return str(get("3dlut.format"))
    if i == "lut3d_size":
        s = get("3dlut.size")
        return f"{s}×{s}×{s} · {get('3dlut.bitdepth.input')} / {get('3dlut.bitdepth.output')} bit"
    if i == "lut3d_encoding":
        return _tr("help.val.range.full") if get("3dlut.encoding.input") == "n" else _tr("help.val.range.video")
    if i == "observer":
        names = {"1931_2": "CIE 1931 2°", "1964_10": "CIE 1964 10°"}
        return names.get(str(get("observer")), str(get("observer")).replace("_", " "))
    return ""


# --- why unavailable ----------------------------------------------------------


def _widget(owner: object, attr: str) -> QWidget | None:
    return getattr(owner, attr, None)


#: Items where only some of the widgets can be unavailable (the rest stay usable).
_PARTIAL = {"lut3d_gamut_mapping": ("gamut_mapping_b2a",)}
#: Items whose availability is decided by one main widget (the others are helpers
#: that stay visible, like the monitor-model search link next to the correction).
_REPRESENTATIVE = {"correction": "colorimeter_correction_matrix_ctrl"}


def unavailable_reason(
    item: sh.Item, owner: object, panel: QWidget, only: QWidget | None = None
) -> str:
    """Why this setting cannot be changed right now ('' when it can).

    ``only`` limits the answer to one widget (for tooltips).
    """
    if item.id in _PARTIAL:
        targets = [w for w in (_widget(owner, a) for a in _PARTIAL[item.id]) if w is not None]
        if only is not None and only not in targets:
            return ""
        if any(not w.isEnabled() for w in targets):
            return _tr(f"help.reason.{item.id}")
        return ""
    widgets = [w for w in (_widget(owner, a) for a in item.widgets) if w is not None]
    if not widgets:
        return ""
    if item.id in _REPRESENTATIVE:
        rep = _widget(owner, _REPRESENTATIVE[item.id])
        widgets = [rep] if rep is not None else widgets
    hidden = all(not w.isVisibleTo(panel) for w in widgets)
    disabled = all(not w.isEnabled() for w in widgets)
    if not hidden and not disabled:
        return ""
    i = item.id
    if i == "correction" and hidden:
        w = owner
        try:
            if not w.worker.instrument_can_use_ccxx(False):
                return _tr("help.reason.correction_instrument")
        except Exception:  # noqa: BLE001 - the explanation must never break the tab
            pass
        return _tr("help.reason.correction_mode")
    key = f"help.reason.{i}"
    if _has(key):
        return _tr(key)
    return _tr("help.reason.hidden" if hidden else "help.reason.generic")


# --- text ----------------------------------------------------------------------


def describe(item: sh.Item, owner: object, panel: QWidget) -> str:
    """Rich text for one setting."""
    k = sh.item_keys(item.id)
    badge = _tr(f"help.kind.{item.kind}")
    parts = [f"<b>{escape(_tr(k['name']))}</b> <span style='color:gray'>· {escape(badge)}</span>"]
    parts.append(escape(_tr(k["what"])))
    parts.append(f"<i>{escape(_tr('help.label.when'))}</i> {escape(_tr(k['when']))}")
    meta = []
    if item.unit:
        meta.append(f"{escape(_tr('help.label.unit'))} {escape(item.unit)}")
    default = default_text(item)
    if default:
        meta.append(f"{escape(_tr('help.label.default'))} {escape(default)}")
    if meta:
        parts.append(" · ".join(meta))
    if item.has_needs and _has(k["needs"]):
        parts.append(f"<i>{escape(_tr('help.label.needs'))}</i> {escape(_tr(k['needs']))}")
    reason = unavailable_reason(item, owner, panel)
    if reason:
        parts.append(f"<span style='color:#b25000'><b>{escape(_tr('help.label.unavailable'))}</b> {escape(reason)}</span>")
    return "<p style='margin:0 0 10px 0; line-height:125%'>" + "<br>".join(parts) + "</p>"


class SectionHeader(QFrame):
    """Title + purpose + 'What each setting here changes' for one decision."""

    def __init__(self, tab: str, section: str, owner: object, panel: QWidget) -> None:
        super().__init__(panel)
        self.tab, self.section, self._owner, self._panel = tab, section, owner, panel
        self.items = [sh.ITEMS[i] for s, ids in sh.SECTIONS[tab] if s == section for i in ids]
        self.setObjectName(f"section_{tab}_{section}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 10, 0, 2)
        lay.setSpacing(2)
        tkey, pkey = sh.section_keys(tab, section)
        self.title = QLabel(f"<b>{escape(_tr(tkey))}</b>")
        self.title.setTextFormat(Qt.RichText)
        text_scale.set_scaled_font(self.title, 1.1)
        lay.addWidget(self.title)
        self.purpose = QLabel(_tr(pkey))
        self.purpose.setWordWrap(True)
        self.purpose.setStyleSheet(f"color: {muted_css()};")
        text_scale.limit_reading_width(self.purpose, 96)
        lay.addWidget(self.purpose)
        self.toggle = QPushButton()
        self.toggle.setFlat(True)
        self.toggle.setCursor(Qt.PointingHandCursor)
        self.toggle.setStyleSheet("QPushButton { text-align: left; }")
        self.toggle.clicked.connect(self._toggle)
        lay.addWidget(self.toggle, 0, Qt.AlignLeft)
        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.RichText)
        self.body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.body.setContentsMargins(12, 2, 0, 6)
        text_scale.limit_reading_width(self.body, 110)
        self.body.hide()
        lay.addWidget(self.body)
        self._update_toggle()

    def _update_toggle(self) -> None:
        arrow = "▾" if not self.body.isHidden() else "▸"
        self.toggle.setText(f"{arrow} {_tr('help.sections.expand')}")

    def _toggle(self) -> None:
        self.body.setVisible(self.body.isHidden())
        self._update_toggle()
        self.refresh()
        self.updateGeometry()
        host = self._panel.layout()
        if host is not None:
            host.invalidate()
        self._repin()

    def _repin(self) -> None:
        """The tab stack is sized to the shown page: re-measure after a change."""
        from qtpy.QtCore import QTimer

        win = self.window()
        pin = getattr(win, "_pin_stack_size_to_current_tab", None)
        if pin is not None:
            QTimer.singleShot(0, pin)

    def refresh(self) -> None:
        """Re-evaluate visibility and the live 'unavailable' reasons."""
        any_visible = False
        for it in self.items:
            for a in it.widgets:
                w = _widget(self._owner, a)
                if w is not None and w.isVisibleTo(self._panel):
                    any_visible = True
        # A section whose controls are all hidden (advanced-only rows) hides too,
        # unless its disclosure is open (then the reasons are the point).
        self.setVisible(any_visible or not self.body.isHidden())
        if not self.body.isHidden():
            self.body.setText("".join(describe(it, self._owner, self._panel) for it in self.items))
        self._apply_tooltips()

    def _apply_tooltips(self) -> None:
        """Put the 'what it changes' sentence on every control that has no tooltip."""
        for it in self.items:
            what = _tr(sh.item_keys(it.id)["what"])
            for a in it.widgets:
                w = _widget(self._owner, a)
                if w is None:
                    continue
                reason = unavailable_reason(it, self._owner, self._panel, w)
                base = w.property("_base_tip")
                if base is None:
                    base = w.toolTip()
                    w.setProperty("_base_tip", base)
                text = base or what
                if reason:
                    text = f"{text}\n\n{_tr('help.label.unavailable')} {reason}"
                w.setToolTip(text)
