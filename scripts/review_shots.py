"""The list of screens/dialogs for the review capture (kept apart for easy editing)."""

from __future__ import annotations


def run_shots(win, g, app, save, tab, config, lang, settle, code) -> None:
    """Capture the main window tabs, with advanced options off and on."""
    # --- guided flow -----------------------------------------------------
    g.prepare.stop_motion()
    for step, name, title in (
        (0, "guide_1_monitor", "Calibrare ghidată — 1. Monitor și instrument"),
        (1, "guide_2_goal", "Calibrare ghidată — 2. Obiectivul"),
        (2, "guide_3_prepare", "Calibrare ghidată — 3. Pregătire"),
        (3, "guide_4_measure", "Calibrare ghidată — 4. Măsurare și plan"),
        (4, "guide_5_finish", "Calibrare ghidată — 5. Instalare și verificare"),
    ):
        if step == 3:
            for cb in g.prepare._boxes.values():
                cb.setChecked(True)
        win._select_tab("guide")
        g.go(step)
        g.prepare.stop_motion()
        save(win, name, title, "Pasul din fluxul ghidat.", "Monitor/instrument simulate.")
    # --- advanced tabs ---------------------------------------------------
    for key, label in (
        ("display_instrument", "Monitor și instrument"),
        ("calibration", "Calibrare"),
        ("profiling", "Profilare și patch-uri"),
        ("lut3d", "LUT 3D"),
        ("verification", "Verificare"),
    ):
        tab(key, False)
        save(win, f"adv_{key}", f"Avansat — {label} (opțiuni avansate ascunse)", "Fila așa cum apare implicit.", "Monitor/instrument simulate.")
        tab(key, True)
        save(win, f"adv_{key}_more", f"Avansat — {label} (opțiuni avansate afișate)", "Toate controalele filei, grupate pe decizii.", "Monitor/instrument simulate.")
    # --- the 'what each setting changes' disclosure, one per tab ---------
    for key, owner, section, label in (
        ("display_instrument", None, "behavior", "Monitor și instrument — Cum se comportă măsurarea"),
        ("calibration", None, "target", "Calibrare — Cum trebuie să arate ecranul"),
        ("profiling", None, "type", "Profilare — Tipul de profil"),
        ("lut3d", None, "mapping", "LUT 3D — Cum se mapează culorile"),
        ("verification", "_report_panel", "simulate", "Verificare — Simulează alt dispozitiv"),
    ):
        tab(key, True)
        open_section(win, key, owner, section)
        win.resize(1180, 1900)
        save(win, f"help_{key}_{section}", f"Explicații — {label}", "Secțiunea deschisă: ce schimbă fiecare setare, când se potrivește, unitate, valoare implicită, dependențe, motive de indisponibilitate.", "Monitor/instrument simulate.")
        open_section(win, key, owner, "none")
        win.resize(1180, 1250)
    # --- states that change the meaning of controls ------------------------
    tab("display_instrument", True)
    idx = next((i for i in range(win.comport_ctrl.count()) if "i1 Pro" in win.comport_ctrl.itemText(i)), -1)
    if idx >= 0:
        win.comport_ctrl.setCurrentIndex(idx)
        open_section(win, "display_instrument", None, "correction")
        win.resize(1180, 1500)
        save(win, "state_spectrometer", "Stare — instrument spectrometru: corecția dispare, cu motivul", "Corecția e ascunsă pentru spectrometre; secțiunea explică de ce.", "Instrumentul e simulat.")
        open_section(win, "display_instrument", None, "none")
        win.resize(1180, 1250)
        win.comport_ctrl.setCurrentIndex(0)
    tab("profiling", True)
    win._profile_type_change_is_synthetic = True  # no recommendation dialog in a capture
    for i in range(win.profile_type_ctrl.count()):
        if "XYZ" in win.profile_type_ctrl.itemText(i) and "LUT" in win.profile_type_ctrl.itemText(i).upper():
            win.profile_type_ctrl.setCurrentIndex(i)
            break
    save(win, "state_profile_lut", "Stare — profil de tip LUT (XYZ)", "Cu un tip LUT, butonul de mapare a gamutului devine disponibil și mai multe patch-uri sunt utile.", "Monitor/instrument simulate.")
    tab("lut3d", True)
    win.lut3d_create_cb.setChecked(True)
    open_section(win, "lut3d", None, "mapping")
    win.resize(1180, 1700)
    save(win, "state_lut3d_create", "Stare — se creează un LUT 3D după profilare", "Controalele LUT 3D devin active; secțiunea arată de ce unele rămân indisponibile.", "Monitor/instrument simulate.")
    open_section(win, "lut3d", None, "none")
    win.resize(1180, 1250)
    win.lut3d_create_cb.setChecked(False)
    tab("calibration", True)
    win.calibration_update_cb.setChecked(True)
    save(win, "state_calibration_update", "Stare — «Actualizează calibrarea» activat", "Țintele provin din calibrarea existentă; ajustarea interactivă este omisă.", "Monitor/instrument simulate.")
    win.calibration_update_cb.setChecked(False)


def open_section(win, tab_key, owner_attr, section):
    """Expand one section's disclosure (for the 'what each setting changes' captures)."""
    owner = getattr(win, owner_attr) if owner_attr else win
    headers = owner._section_headers
    for h in headers:
        h.body.setVisible(h.objectName() == f"section_{tab_key}_{section}")
        h._update_toggle()
        h.refresh()
    win._pin_stack_size_to_current_tab()


def dialogs(win, g, app, save, config, lang, settle, code, tmp):
    """Dialogs: recovery, diagnostic, export, lookup, correction creation, test chart editor."""
    import os
    import time

    from DisplayCAL import diagnostics, session_journal as sj
    from DisplayCAL.ui import diagnostic_dialog as dd
    from DisplayCAL.ui import display_lookup_dialog as ld
    from DisplayCAL.ui import recovery_dialog as rd

    # recovery: a session that stopped after 1 of 4 blocks (demonstration data)
    root = os.path.join(tmp, "sessions")
    d = os.path.join(root, "20261019-101010-demo01")
    os.makedirs(d, exist_ok=True)
    now = time.time()
    sj._atomic_json(
        os.path.join(d, "session.json"),
        {
            "id": "demo01", "started": now - 5400, "last_heartbeat": now - 600, "stage": "measuring",
            "progress": {"done": 2, "total": 4, "label": "blocks"}, "app_pid": 99999999,
            "info": {"display": "DELL U2723QE (demo)"}, "slept_seconds": 1200,
            "plan": {"blocks": 4, "block_size": 500, "fingerprint": win.worker.session_fingerprint()},
            "blocks_done": [1, 2], "child": {"name": "dispread"}, "samples": [{"app_rss": 4.0e8, "disk_free": 9.0e10}, {"app_rss": 4.4e8, "disk_free": 8.9e10}],
        },
    )
    found = sj.scan_incomplete(root)
    dlg = rd.RecoveryDialog(found, win.worker, win)
    dlg.resize(760, 560)
    dlg.show()
    save(dlg, "dlg_recovery", "Dialog — Recuperare după o oprire neașteptată", "Fapte din jurnal (nu cauze), opțiuni: exportă, arată folderul, continuă cu blocurile rămase.", "Sesiune demonstrativă creată pentru captură.")
    dlg.close()
    from DisplayCAL.ui.progress_dialog import ProgressDialog

    demo_msg = {
        "ro": "Se măsoară patch-ul 213 din 500 (blocul 1 din 4). Date demonstrative.",
        "en": "Measuring patch 213 of 500 (block 1 of 4). Demonstration data.",
        "es": "Midiendo el parche 213 de 500 (bloque 1 de 4). Datos de demostración.",
    }[code]
    pdlg = ProgressDialog(win, message=demo_msg, maximum=100, cancelable=True, pauseable=True)
    pdlg.set_progress(43)
    pdlg._elapsed_label.setText("00:12:41")
    if pdlg._remaining_label is not None:
        pdlg._remaining_label.setText("00:16:52")
    pdlg.show()
    save(pdlg, "dlg_progress", "Dialog — Progres, anulare, pauză", "Bară statică (nimic nu se animă în timpul măsurării), timp scurs și estimat.", "Date demonstrative.")
    pdlg.close()
    for name, dlg2, title, shows in (
        ("dlg_diagnostic", dd.DiagnosticDialog(win.worker, win), "Dialog — Diagnostic și suport", "Versiuni, folderul de loguri, ID-ul sesiunii, jurnal detaliat temporar, cum trimiți pachetul."),
        ("dlg_export", dd.ExportDialog(win.worker, win, diagnostics.plan_package(os.path.join(tmp, "nolog"), root)), "Dialog — Exportă pachetul de diagnostic", "Ce intră în pachet, înainte de salvare; opționalele sunt oprite implicit."),
        ("dlg_lookup", ld.DisplayLookupDialog(win, "DELL U2723QE @ 0, 0, 3840x2160", None, "darwin", "Mac14,9"), "Dialog — Caută modelul monitorului", "Acțiuni reale ale celor două site-uri, cele patru noțiuni, avertisment despre corecții."),
    ):
        dlg2.resize(700, 720)
        dlg2.show()
        save(dlg2, name, title, shows, "Date demonstrative.")
        dlg2.close()
    try:
        from DisplayCAL.ui.colorimeter_correction_window import CreateCorrectionWindow

        w = CreateCorrectionWindow()
        w.resize(900, 760)
        w.show()
        save(w, "dlg_create_correction", "Dialog — Creează o corecție de colorimetru", "Corecție spectrală/matriceală; tehnologia ecranului și căutarea modelului.", "Fără măsurători reale.")
        w.close()
    except Exception as exc:  # noqa: BLE001
        print("create_correction skipped:", exc)
    try:
        from DisplayCAL.ui.tools.testchart_editor import TestchartEditorWindow

        w = TestchartEditorWindow()
        w.resize(1100, 760)
        w.show()
        save(w, "dlg_testchart_editor", "Unealtă — Editor de diagrame de patch-uri", "Editarea diagramei de patch-uri (vezi Profilare).", "Fără măsurători reale.")
        w.close()
    except Exception as exc:  # noqa: BLE001
        print("testchart editor skipped:", exc)


def finish_dialog(win, save, lang):
    """The dialog offered when a profile has been built (demonstration text)."""
    try:
        from DisplayCAL.ui.profile_finish_dialog import ProfileFinishDialog

        d = ProfileFinishDialog(
            win,
            message="Profilul a fost creat (demonstrație). Alege dacă îl instalezi acum; poți să nu îl instalezi.",
            cinfo=["sRGB: 99 %", "Adobe RGB: 96 %", "DCI-P3: 98 %"],
            vinfo=["sRGB: 118 %", "Adobe RGB: 104 %", "DCI-P3: 109 %"],
            ok_label=lang.getstr("profile.install"),
            cancel_label=lang.getstr("profile.do_not_install"),
            installable=True,
            preview_enabled=True,
            show_profile_info_checked=False,
            worker=win.worker,
        )
        d.resize(720, 520)
        d.show()
        save(d, "dlg_profile_finish", "Dialog — Profil creat: instalare și previzualizare", "Instalarea este opțională (scop: utilizator sau sistem), cu previzualizarea calibrării; «nu instala» e o alegere obișnuită.", "Profil și acoperiri de gamut demonstrative.")
        d.close()
    except Exception as exc:  # noqa: BLE001
        print("profile finish dialog skipped:", exc)
