from __future__ import annotations
import os
import tempfile
from typing import Dict, Any, Optional


def ch7_quantities(input_dict: dict, fig_paths: Optional[Dict[str, str]] = None) -> str:
    """Chapter 7 — Material Take-off & Quantity Summary.

    Parameters
    ----------
    input_dict : dict
        Contains the computed bill of quantities keys (populated from boq_generator).
    fig_paths : dict, optional
        Dictionary mapping figure names to image paths on disk.
    """
    if input_dict is None:
        input_dict = {}
    if fig_paths is None:
        fig_paths = {}

    # Attempt on-the-fly chart generation if not already in fig_paths
    if not any(k in fig_paths for k in ("boq_chart_steel", "boq_chart_concrete_rebar")):
        tmp_img_dir = os.path.join(tempfile.gettempdir(), "osdag_boq_images")
        try:
            from osdagbridge.core.reports.boq_charts import generate_all_boq_charts
            generated = generate_all_boq_charts(input_dict, {}, tmp_img_dir)
            fig_paths.update(generated)
        except Exception:
            pass

    def _render_fig(path_key: str, caption: str, label: str) -> str:
        raw_p = fig_paths.get(path_key)
        if not raw_p or not os.path.exists(raw_p):
            return ""
        clean_p = raw_p.replace("\\", "/")
        try:
            from pylatex import Figure
            from pylatex.utils import NoEscape
            fig = Figure(position="H")
            fig.add_image(clean_p, width=NoEscape(r"0.92\textwidth"))
            fig.add_caption(NoEscape(r"\textbf{" + caption + r"}"))
            return fig.dumps() + "\n"
        except Exception:
            lbl_tex = f"\\label{{{label}}}\n" if label else ""
            return (
                r"\begin{figure}[H]" + "\n"
                r"\centering" + "\n"
                rf"\includegraphics[width=0.92\textwidth,keepaspectratio]{{{clean_p}}}" + "\n"
                rf"\caption{{\textbf{{{caption}}}}}" + "\n"
                + lbl_tex +
                r"\end{figure}" + "\n"
            )

    boq_figures = []
    c1 = _render_fig(
        "boq_chart_steel",
        "Structural Steel Tonnage Distribution (Girders, Cross Bracing, and End Diaphragms)",
        "fig:boq-steel-tonnage"
    )
    c2 = _render_fig(
        "boq_chart_concrete_rebar",
        "Superstructure Concrete Volume (m³) and Reinforcement Steel Weight (MT)",
        "fig:boq-concrete-rebar"
    )

    for c in (c1, c2):
        if c:
            boq_figures.append(c)

    if boq_figures:
        boq_visual_content = r"""
\vspace{1.5em}
\section{Material Quantity Visualizations}
\label{sec:material-visualizations}

The following visualizations illustrate the distribution of structural steel tonnage across the superstructure components and summarize the concrete and reinforcement material requirements extracted from the Bill of Materials:

""" + "\n\\vspace{1em}\n".join(boq_figures)
    else:
        boq_visual_content = r"""
\vspace{1.5em}
\section{Material Quantity Visualizations}
\label{sec:material-visualizations}

\noindent\textit{Note: Material quantity visualizations are generated automatically when design analysis and quantity take-off results are available.}
"""

    return r"""
\chapter{Material Take-off \& Quantity Summary}
\label{ch:material-takeoff}

\begingroup
\setlength{\tabcolsep}{3.5pt}
\begin{longtable}{|C{1.0cm}|L{3.8cm}|C{2.6cm}|C{1.8cm}|C{1.8cm}|C{1.8cm}|C{1.8cm}|}
\caption{\textbf{Bill of Materials (Steel, Concrete, and Reinforcement Quantities)}}\\
\hline
\textbf{S.N.} & \textbf{Item Description} & \textbf{Volume} & \textbf{Quantity} & \textbf{Total Volume} & \textbf{Weight (MT)} & \textbf{Total Weight (MT)} \\
\hline
\endfirsthead
\hline
\textbf{S.N.} & \textbf{Item Description} & \textbf{Volume} & \textbf{Quantity} & \textbf{Total Volume} & \textbf{Weight (MT)} & \textbf{Total Weight (MT)} \\
\hline
\endhead
1 & Structural Steel (IS 2062) for Girders & """ + str(input_dict.get("steel_girders_vol_formula", "N.A.")) + r""" & """ + str(input_dict.get("steel_girders_qty", "N.A.")) + r""" & """ + str(input_dict.get("steel_girders_vol_total", "N.A.")) + r""" & """ + str(input_dict.get("steel_girders_wt_single", "N.A.")) + r""" & """ + str(input_dict.get("steel_girders_wt_total", "N.A.")) + r""" \\
\hline
2(a) & Cross Bracing - Top Chord & """ + str(input_dict.get("bracing_top_vol_formula", "N.A.")) + r""" & """ + str(input_dict.get("bracing_top_qty", "N.A.")) + r""" & """ + str(input_dict.get("bracing_top_vol_total", "N.A.")) + r""" & """ + str(input_dict.get("bracing_top_wt_single", "N.A.")) + r""" & """ + str(input_dict.get("bracing_top_wt_total", "N.A.")) + r""" \\
\hline
2(b) & Cross Bracing - Bottom Chord & """ + str(input_dict.get("bracing_bot_vol_formula", "N.A.")) + r""" & """ + str(input_dict.get("bracing_bot_qty", "N.A.")) + r""" & """ + str(input_dict.get("bracing_bot_vol_total", "N.A.")) + r""" & """ + str(input_dict.get("bracing_bot_wt_single", "N.A.")) + r""" & """ + str(input_dict.get("bracing_bot_wt_total", "N.A.")) + r""" \\
\hline
2(c) & Cross Bracing - Diagonal Chord & """ + str(input_dict.get("bracing_diag_vol_formula", "N.A.")) + r""" & """ + str(input_dict.get("bracing_diag_qty", "N.A.")) + r""" & """ + str(input_dict.get("bracing_diag_vol_total", "N.A.")) + r""" & """ + str(input_dict.get("bracing_diag_wt_single", "N.A.")) + r""" & """ + str(input_dict.get("bracing_diag_wt_total", "N.A.")) + r""" \\
\hline
2(d) & End Diaphragms & """ + str(input_dict.get("ed_vol_formula", "N.A.")) + r""" & """ + str(input_dict.get("ed_qty", "N.A.")) + r""" & """ + str(input_dict.get("ed_vol_total", "N.A.")) + r""" & """ + str(input_dict.get("ed_wt_single", "N.A.")) + r""" & """ + str(input_dict.get("ed_wt_total", "N.A.")) + r""" \\
\hline
3 & Concrete (M40) for Deck Slab & """ + str(input_dict.get("concrete_deck_vol_formula", "N.A.")) + r""" & """ + str(input_dict.get("concrete_deck_qty", "N.A.")) + r""" & """ + str(input_dict.get("concrete_deck_vol_total", "N.A.")) + r""" & """ + str(input_dict.get("concrete_deck_wt_single", "N.A.")) + r""" & """ + str(input_dict.get("concrete_deck_wt_total", "N.A.")) + r""" \\
\hline
4 & Reinforcement Steel (Fe 500) & """ + str(input_dict.get("rebar_deck_vol_formula", "N.A.")) + r""" & """ + str(input_dict.get("rebar_deck_qty", "N.A.")) + r""" & """ + str(input_dict.get("rebar_deck_vol_total", "N.A.")) + r""" & """ + str(input_dict.get("rebar_deck_wt_single", "N.A.")) + r""" & """ + str(input_dict.get("rebar_deck_wt_total", "N.A.")) + r""" \\
\hline
5 & Shear Stud Connectors & """ + str(input_dict.get("shear_studs_vol_formula", "N.A.")) + r""" & """ + str(input_dict.get("shear_studs_qty", "N.A.")) + r""" & """ + str(input_dict.get("shear_studs_vol_total", "N.A.")) + r""" & """ + str(input_dict.get("shear_studs_wt_single", "N.A.")) + r""" & """ + str(input_dict.get("shear_studs_wt_total", "N.A.")) + r""" \\
\hline
6 & Crash Barrier & """ + str(input_dict.get("crash_barrier_vol_formula", "N.A.")) + r""" & """ + str(input_dict.get("crash_barrier_qty", "N.A.")) + r""" & """ + str(input_dict.get("crash_barrier_vol_total", "N.A.")) + r""" & """ + str(input_dict.get("crash_barrier_wt_single", "N.A.")) + r""" & """ + str(input_dict.get("crash_barrier_wt_total", "N.A.")) + r""" \\
\hline
\end{longtable}
\endgroup
""" + boq_visual_content
