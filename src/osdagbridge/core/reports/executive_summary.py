# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTIVE SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

from osdagbridge.core.reports.report_utils import (
    _fig_or_placeholder,
    _format_latex_label,
    _render_value,
    _tex,
    get_girder_entries,
)
from osdagbridge.core.reports.styles import (
    format_status_latex,
    format_length_m,
    format_length_mm,
    TableStyles,
)
from osdagbridge.core.utils.common import (
    KEY_CARRIAGEWAY_WIDTH,
    KEY_SD_SECTION_DESIGNATION,
    KEY_SPAN,
    KEY_STRUCTURE_TYPE,
    KEY_TS_DECK_THICKNESS,
    KEY_TS_GIRDER_SPACING,
    KEY_TS_NO_OF_GIRDERS
)


def _max_float(values):
    """Return the largest value coercible to float, or None if there are none."""
    out = None
    for v in values:
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if out is None or f > out:
            out = f
    return out


def _max_member_efficiency(pair_designs):
    """Maximum Osdag 'efficiency' (utilization ratio) over a cross-bracing or
    end-diaphragm result dump (nested pair -> member -> force_type -> raw).
    Reads already-computed results only; nothing is recalculated here."""
    if not isinstance(pair_designs, dict) or not pair_designs:
        return None
    try:
        from osdagbridge.core.bridge_types.plate_girder.results_data import _extract_osdag_summary
    except ImportError:
        return None
    best = None
    for members in pair_designs.values():
        if not isinstance(members, dict):
            continue
        for force_types in members.values():
            if not isinstance(force_types, dict):
                continue
            for raw in force_types.values():
                try:
                    val = _extract_osdag_summary(raw or {}).get("efficiency")
                    if val is None:
                        continue
                    f = float(val)
                except (TypeError, ValueError, AttributeError):
                    continue
                if best is None or f > best:
                    best = f
    return best


def executive_summary(input_dict, output_dict, fig_paths) -> str:
    plan_fig = _fig_or_placeholder(fig_paths.get('girder_top'), 'Figure 1 -- Overall Bridge Plan')
    cs_fig = _fig_or_placeholder(fig_paths.get('cross_section'),
                                  'Figure 2 -- Typical Cross-Section (with girder, deck, barriers, footpath)')
    geom_fig = _fig_or_placeholder(fig_paths.get('final_geometry'),
                                    'Figure 3 -- 3D View of Bridge Superstructure')

    # All girders share the same section, governing check, and UR.
    # The section designation is produced by the designer pipeline, so it lives
    # in output_dict (not input_dict).
    sec = _render_value(output_dict, KEY_SD_SECTION_DESIGNATION)

    # ── Pull the stored result dicts once, then work off these locals ─────────
    # (no value is recomputed here — the pipeline already filled these in).
    design_results = output_dict.get("design_results", {}) or {}
    per_girder     = design_results.get("per_girder", {}) or {}
    deck_results   = output_dict.get("deck_design_results", {}) or {}
    cb_results     = output_dict.get("crossbracing_design_results", {}) or {}
    ed_results     = output_dict.get("end_diaphragm_design_results", {}) or {}

    # Overall Design Status — girder checks only: Pass if every check passes,
    # otherwise Fail with the names of the failing checks. Each check carries a
    # pre-computed {name, dcr, status}.
    failing = []                        # failing check names (order-preserving, deduped)
    gov_name, gov_dcr = "", None
    girder_max_ur = None
    for g, gd in per_girder.items():
        if str(g).startswith("EB"):     # skip edge-beam pseudo girders
            continue
        for chk in (gd.get("checks") or []):
            try:
                _val = chk.get("dcr")
                if _val is None:
                    dcr = None
                else:
                    dcr = float(_val)
            except (TypeError, ValueError):
                dcr = None
            name = str(chk.get("name", "")).strip()
            is_fail = ("FAIL" in str(chk.get("status", "")).upper()) or (dcr is not None and dcr > 1.0)
            if is_fail and name and name not in failing:
                failing.append(name)
            if dcr is not None:
                if gov_dcr is None or dcr > gov_dcr:
                    gov_dcr, gov_name = dcr, name
                if girder_max_ur is None or dcr > girder_max_ur:
                    girder_max_ur = dcr

    # Component Max URs
    deck_max = _max_float([v for k, v in deck_results.items() if str(k).startswith("ur_")])
    cb_max = _max_member_efficiency(cb_results)
    ed_max = _max_member_efficiency(ed_results)
    deck_rpt = output_dict.get("deck_report_values", {}) or {}

    # Derive each component's design status dynamically
    girder_verified = bool(per_girder)
    girder_pass = girder_verified and (len(failing) == 0) and (girder_max_ur is None or girder_max_ur <= 1.0)

    # Deck status: check URs, design check status, and individual detailed checks
    deck_verified = bool(deck_results or deck_rpt)
    deck_failing = []
    if deck_max is not None and deck_max > 1.0:
        deck_failing.append(f"UR = {deck_max:.2f}")
    if deck_results.get("deck_design_check") and "FAIL" in str(deck_results.get("deck_design_check")).upper():
        deck_failing.append("Detailing / Strength Check Fail")
    if deck_rpt:
        if deck_rpt.get("deck.report.cover_ok") is False:
            deck_failing.append("Clear Cover < Min Limit")
        if deck_rpt.get("deck.report.punch_ok") is False:
            deck_failing.append("Punching Shear Fail")
        if deck_rpt.get("deck.report.shear_ok") is False:
            deck_failing.append("One-way Shear Fail")

    deck_pass = deck_verified and (len(deck_failing) == 0)

    cb_verified = bool(cb_results)
    cb_pass = cb_verified and (cb_max is not None and cb_max <= 1.0)

    ed_verified = bool(ed_results)
    ed_pass = ed_verified and (ed_max is not None and ed_max <= 1.0)

    # Overall Design Status — fail if ANY verified component fails;
    # mark INCOMPLETE / NOT VERIFIED if mandatory checks are missing;
    # NEVER mark PASS if checks are failing or missing.
    failing_components = []
    unverified_components = []

    if girder_verified:
        if not girder_pass:
            if failing:
                safe_failing = [_format_latex_label(x) for x in failing]
                failing_components.append("Girder: " + ", ".join(safe_failing))
            elif girder_max_ur is not None:
                failing_components.append(f"Girder (UR={girder_max_ur:.2f})")
            else:
                failing_components.append("Girder")
    else:
        unverified_components.append("Girder")

    if deck_verified:
        if not deck_pass:
            d_msg = ", ".join(deck_failing) if deck_failing else (f"UR={deck_max:.2f}" if deck_max is not None else "Fail")
            failing_components.append(f"Deck slab ({d_msg})")
    else:
        unverified_components.append("Deck slab")

    if cb_verified:
        if not cb_pass:
            cb_val = f"UR={cb_max:.2f}" if cb_max is not None else "Fail"
            failing_components.append(f"Cross bracing ({cb_val})")
    else:
        unverified_components.append("Cross bracing")

    if ed_verified:
        if not ed_pass:
            ed_val = f"UR={ed_max:.2f}" if ed_max is not None else "Fail"
            failing_components.append(f"End diaphragm ({ed_val})")
    else:
        unverified_components.append("End diaphragm")

    if not per_girder and not deck_results and not cb_results and not ed_results:
        overall_design_status = r"\textcolor{gray}{\textbf{NOT CALCULATED}}"
    elif failing_components:
        overall_design_status = format_status_latex(False, false_label="FAIL (" + "; ".join(failing_components) + ")")
    elif unverified_components:
        overall_design_status = r"\textcolor{gray}{\textbf{INCOMPLETE / NOT VERIFIED (" + "; ".join(unverified_components) + ")}}"
    else:
        overall_design_status = format_status_latex(True, true_label="PASS")

    # Overall Utilization Ratio — the maximum UR across all bridge components,
    # tagged with the governing component (e.g. "1.05 (Deck slab)").
    component_urs = []                  # (ur_value, component_label, check_name)
    if girder_max_ur is not None:
        component_urs.append((girder_max_ur, "Girder", gov_name or "Girder Governing Check"))
    if deck_max is not None:
        component_urs.append((deck_max, "Deck slab", "Deck Slab Flexure/Shear"))
    if cb_max is not None:
        component_urs.append((cb_max, "Cross bracing", "Cross Bracing Member Capacity"))
    if ed_max is not None:
        component_urs.append((ed_max, "End diaphragm", "End Diaphragm Member Capacity"))

    if component_urs:
        max_ur, max_label, max_chk = max(component_urs, key=lambda t: t[0])
        overall_utilization_ratio = f"{max_ur:.2f} ({max_label})"
        gov_overall_name = max_chk if max_label != "Girder" else (gov_name or "Girder Check")
    else:
        overall_utilization_ratio = ""
        gov_overall_name = gov_name

    gov = _format_latex_label(gov_overall_name) if gov_overall_name not in (None, '', 'None') else ''
    ur = _tex(overall_utilization_ratio) if overall_utilization_ratio else ''

    # Dynamic Key Design Outcomes Summary
    if not girder_pass:
        girder_outcome = format_status_latex(False, false_label=f"Girder design fail (Governing: {_format_latex_label(gov_name)}, UR = {girder_max_ur:.2f})" if girder_max_ur is not None else "Girder design fail")
    else:
        girder_outcome = format_status_latex(True, true_label="Girder design pass")

    if cb_max is not None and cb_max > 1.0:
        cb_outcome = format_status_latex(False, false_label=f"Cross bracing design fail (UR = {cb_max:.2f})")
    elif not cb_verified or cb_max is None:
        cb_outcome = r"\textcolor{gray}{\textbf{Cross bracing not calculated / not verified}}"
    else:
        cb_outcome = format_status_latex(True, true_label="Cross bracing design pass")

    if ed_max is not None and ed_max > 1.0:
        ed_outcome = format_status_latex(False, false_label=f"End Diaphragm design fail (UR = {ed_max:.2f})")
    elif not ed_verified or ed_max is None:
        ed_outcome = r"\textcolor{gray}{\textbf{End Diaphragm not calculated / not verified}}"
    else:
        ed_outcome = format_status_latex(True, true_label="End Diaphragm design pass")

    if not deck_pass:
        d_fail_str = (", ".join(deck_failing)) if deck_failing else "Deck design fail"
        deck_outcome = format_status_latex(False, false_label=f"Deck design fail ({d_fail_str})")
    else:
        deck_outcome = format_status_latex(True, true_label="Deck design pass")

    # --- Dynamic Table 1: fetch backend-populated labels via exact suffix pattern ---
    # defaults.py populates: KEY_MP_GD_SELECT_GIRDER + '.G{i}' = 'G{i}'
    #                        KEY_MP_GD_MEMBER_ID     + '.G{i}.M1' = 'G{i}M1'
    labels = get_girder_entries(input_dict)
    if not labels:
        labels = [("", "")]
    n_cols = len(labels)

    def _render_table1_block(chunk_labels, chunk_start_idx, block_title):
        c_cols = len(chunk_labels)
        label_col_cm = 3.6
        girder_col_cm = round(max(2.2, (15.2 - label_col_cm) / c_cols), 2)
        c_spec = '|L{' + str(label_col_cm) + 'cm}|' + '|'.join(['C{' + str(girder_col_cm) + 'cm}'] * c_cols) + '|'

        hdr_cells = ' &\n  '.join([r'\textbf{' + _tex(lbl) + '}' for lbl, _ in chunk_labels])
        h_row = r'  \textbf{Parameter} &' + '\n  ' + hdr_cells + r' \\' + '\n'

        mid_cells = ' & '.join([_tex(mid) for _, mid in chunk_labels])
        m_row = 'Member ID & ' + mid_cells + r' \\' + '\n'

        s_cells = ' & '.join([sec] * c_cols)
        s_row = f"Section Designation & {s_cells} \\\\"

        g_cells = []
        u_cells = []
        for _offset, (lbl, _) in enumerate(chunk_labels):
            _gi = chunk_start_idx + _offset
            g_data = per_girder.get(f"G{_gi}") or per_girder.get(lbl) or {}
            g_checks = g_data.get("checks", [])
            if g_checks:
                ctrl = max(g_checks, key=lambda c: c.get("dcr") or 0.0)
                g_cells.append(_format_latex_label(str(ctrl.get("name", ""))))
                u_cells.append(f"{ctrl.get('dcr'):.2f}" if ctrl.get("dcr") is not None else "")
            else:
                g_cells.append(gov)
                u_cells.append(ur)
        g_row = "Governing Check & " + " & ".join(g_cells) + r" \\"
        u_row = "Utilization Ratio & " + " & ".join(u_cells) + r" \\"

        return (r'\noindent\textbf{' + block_title + '}' + '\n\n'
                r'\vspace{0.3em}' + '\n'
                r'\begingroup' + '\n'
                r'\setlength{\tabcolsep}{3pt}' + '\n'
                r'\noindent' + '\n'
                r'\begin{tabular}{' + c_spec + '}\n'
                r'\hline' + '\n'
                + h_row +
                r'\hline' + '\n'
                + m_row +
                r'\hline' + '\n'
                + s_row + '\n'
                r'\hline' + '\n'
                + g_row + '\n'
                r'\hline' + '\n'
                + u_row + '\n'
                r'\hline' + '\n'
                r'\end{tabular}' + '\n'
                r'\endgroup')

    if n_cols <= 5:
        table1 = _render_table1_block(labels, 1, "Table 1 -- Final Bridge Geometry (after optimization)")
    else:
        blocks = []
        chunk_size = 5
        suffixes = ["(a)", "(b)", "(c)", "(d)"]
        for b_idx in range(0, n_cols, chunk_size):
            chunk = labels[b_idx:b_idx+chunk_size]
            sfx = suffixes[len(blocks)] if len(blocks) < len(suffixes) else f"({len(blocks)+1})"
            b_title = f"Table 1{sfx} -- Final Girder Parameters: {chunk[0][0]} to {chunk[-1][0]} (after optimization)"
            blocks.append(_render_table1_block(chunk, b_idx + 1, b_title))
        table1 = '\n\n\\vspace{0.8em}\n\n'.join(blocks)

    return r"""
\newpage
{\centering\Large\bfseries Executive Summary\par}
\addcontentsline{toc}{chapter}{Executive Summary}
\vspace{0.8em}

This section provides a concise summary of the bridge design, key inputs, governing loads, and final design outcomes.

\section*{Project Overview}
\addcontentsline{toc}{section}{Project Overview}
\label{sec:project-overview}

\begingroup
\setlength{\tabcolsep}{""" + TableStyles.TABCOLSEP_DEFAULT + r"""}
\begin{tabular}{|L{5.5cm}|p{10.0cm}|}
\hline
\textbf{Bridge Type} & """ + (_render_value(input_dict, KEY_STRUCTURE_TYPE)) + r""" \\
\hline
\textbf{Design Standard} & IRC 5, IRC 6, IRC 22, IRC 24, IS 800 \\
\hline
\textbf{Span} & """ + (format_length_m(input_dict.get(KEY_SPAN))) + r""" \\
\hline
\textbf{Carriageway Width} & """ + (format_length_m(input_dict.get(KEY_CARRIAGEWAY_WIDTH))) + r""" \\
\hline
\textbf{No. of Girders} & """ + (_render_value(input_dict, KEY_TS_NO_OF_GIRDERS)) + r""" \\
\hline
\textbf{Girder Spacing} & """ + (format_length_m(input_dict.get(KEY_TS_GIRDER_SPACING))) + r""" \\
\hline
\textbf{Deck Thickness} & """ + (format_length_mm(input_dict.get(KEY_TS_DECK_THICKNESS))) + r""" \\
\hline
\textbf{Overall Design Status} & """ + (overall_design_status if overall_design_status else "") + r""" \\
\hline
\textbf{Governing Check} & """ + gov + r""" \\
\hline
\textbf{Overall Utilization Ratio (max)} & """ + ur + r""" \\
\hline
\end{tabular}
\endgroup


""" + plan_fig + r"""

\newpage

""" + cs_fig + '\n\n' + geom_fig + r"""

\newpage

""" + table1 + r"""

\vspace{0.4em}
\noindent\textit{Note: Utilization ratio (UR) = demand / capacity. A value $< 1.0$ indicates a passing check.}

\vspace{1em}

\section*{Key Design Outcomes Summary}
\addcontentsline{toc}{section}{Key Design Outcomes Summary}
\label{sec:key-outcomes}

\noindent """ + girder_outcome + r""" \\
""" + cb_outcome + r""" \\
""" + ed_outcome + r""" \\
""" + deck_outcome + r"""

\section*{Design Assumptions and Limitations}
\addcontentsline{toc}{section}{Design Assumptions and Limitations}
\label{sec:assumptions}

\begin{itemize}
\item Additional inputs not provided by the user were assumed by software per IRC/IS code defaults or practical consideration.
\item Grillage analysis was performed using OSPGrillage assuming simply supported I-girders.
\item Substructure and foundation design are not included in this report.
\item Splice connections and bearings are not designed in this version.
\end{itemize}

% Restore numbered chapter format
\titleformat{\chapter}[block]{\normalfont\Large\bfseries\centering}{\thechapter}{1em}{}
\titlespacing*{\chapter}{0pt}{-30pt}{10pt}
"""
