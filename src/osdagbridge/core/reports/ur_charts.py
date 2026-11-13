# =============================================================================
# Utilization Ratio Charts Generator
# Extracts real demand and capacity values from structural design results,
# calculates UR = Demand / Capacity, and generates publication-quality
# Matplotlib bar charts with a red dashed reference line at UR = 1.0.
# DO NOT use sample or manually invented structural values.
# =============================================================================

import os
import logging
from typing import Dict, List, Any, Optional

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

from osdagbridge.core.utils.common import (
    KEY_DD_M_ULS_SAG, KEY_DD_MU_BOT,
    KEY_DD_M_ULS_HOG, KEY_DD_MU_TOP,
    KEY_DD_M_ULS_OH, KEY_DD_MU_OH,
    KEY_DD_PUNCH_VED, KEY_DD_VRD_C_MPA,
    KEY_DD_SHEAR_VED, KEY_DD_SHEAR_VRDC,
    KEY_DD_WK_LIMIT, KEY_MP_ED_TYPE
)
from osdagbridge.core.reports.styles import Colors

logger = logging.getLogger(__name__)


def extract_design_utilization_ratios(bridge: Any) -> Dict[str, Any]:
    """
    Extract strictly real demand and capacity values from bridge design results
    and compute UR = Demand / Capacity.
    
    Returns a dictionary structured by:
      - 'overall': list of controlling checks across all bridge components
      - 'girders': dict of per-girder checks
      - 'deck': list of deck slab checks
      - 'bracing': list of transverse bracing checks
    
    If data is not present or invalid in output_dict, no sample or invented
    values are used.
    """
    output_dict = getattr(bridge, "output_dict", {}) or {}
    input_dict = getattr(bridge, "input_dict", {}) or {}
    
    pg_results = (output_dict.get("design_results", {}) or {}).get("per_girder", {}) or {}
    dd_results = output_dict.get("deck_design_results", {}) or {}
    dk_values  = output_dict.get("deck_report_values", {}) or {}
    
    girder_checks: Dict[str, Dict[str, tuple]] = {}
    governing_girder_checks: Dict[str, tuple] = {}
    
    # ── 1. Plate Girder Checks ───────────────────────────────────────────────
    CHECK_NAMES = {
        1:  ("Girder Moment", "kN-m"),
        2:  ("Girder Shear", "kN"),
        3:  ("Web Yielding", "kN"),
        4:  ("Web Buckling", "kN"),
        5:  ("Girder LTB", "kN-m"),
        8:  ("Girder Fatigue (Shear)", "MPa"),
        9:  ("Girder Fatigue (Normal)", "MPa"),
        11: ("Girder Stress", "MPa"),
        13: ("Girder Deflection (Live)", "mm"),
        14: ("Girder Deflection (Total)", "mm"),
        16: ("Transverse Shear", "kN/m"),
    }
    
    for g, gd in pg_results.items():
        if str(g).startswith("EB"):
            continue
        g_name = str(g)
        girder_checks[g_name] = {}
        
        for chk in (gd.get("checks") or []):
            cid = chk.get("check_id")
            if cid not in CHECK_NAMES:
                continue
            lbl, def_unit = CHECK_NAMES[cid]
            dem = chk.get("demand")
            cap = chk.get("capacity")
            dcr = chk.get("dcr")
            unit = chk.get("demand_unit") or def_unit
            
            if dem is not None and cap is not None:
                try:
                    dem_f = float(dem)
                    cap_f = float(cap)
                    if cap_f > 0 and dem_f >= 0:
                        ur_f = float(dcr) if dcr is not None else (dem_f / cap_f)
                        girder_checks[g_name][lbl] = (dem_f, cap_f, round(ur_f, 3), unit)
                        if lbl not in governing_girder_checks or ur_f > governing_girder_checks[lbl][0]:
                            governing_girder_checks[lbl] = (round(ur_f, 3), dem_f, cap_f, unit, g_name)
                except (TypeError, ValueError):
                    pass

        # Fallback to per_lc for deflection
        for lc, ld in (gd.get("per_lc") or {}).items():
            if str(lc).lower().startswith("envelope"):
                continue
            for chk in (ld.get("checks") or []):
                cid = chk.get("id")
                if cid in (13, 14):
                    lbl = "Girder Deflection"
                    dem = chk.get("demand")
                    cap = chk.get("capacity")
                    dcr = chk.get("dcr")
                    if dem is not None and cap is not None:
                        try:
                            dem_f = float(dem)
                            cap_f = float(cap)
                            if cap_f > 0 and dem_f >= 0:
                                ur_f = float(dcr) if dcr is not None else (dem_f / cap_f)
                                if lbl not in girder_checks[g_name] or ur_f > girder_checks[g_name][lbl][2]:
                                    girder_checks[g_name][lbl] = (dem_f, cap_f, round(ur_f, 3), "mm")
                                if lbl not in governing_girder_checks or ur_f > governing_girder_checks[lbl][0]:
                                    governing_girder_checks[lbl] = (round(ur_f, 3), dem_f, cap_f, "mm", g_name)
                        except (TypeError, ValueError):
                            pass

    # ── 2. Deck Slab Checks ──────────────────────────────────────────────────
    deck_checks: List[Dict[str, Any]] = []

    def _add_deck_check(label, dem_key, cap_key, unit, fallback_ur_key=None):
        dem = dk_values.get(dem_key)
        cap = dk_values.get(cap_key)
        if dem is not None and cap is not None:
            try:
                dem_f = float(dem)
                cap_f = float(cap)
                if cap_f > 0 and dem_f >= 0:
                    deck_checks.append({
                        "label": label,
                        "demand": dem_f,
                        "capacity": cap_f,
                        "ur": round(dem_f / cap_f, 3),
                        "unit": unit
                    })
                    return
            except (TypeError, ValueError):
                pass
        if fallback_ur_key and fallback_ur_key in dd_results:
            try:
                ur_f = float(dd_results[fallback_ur_key])
                if ur_f >= 0:
                    deck_checks.append({
                        "label": label,
                        "demand": None,
                        "capacity": None,
                        "ur": round(ur_f, 3),
                        "unit": unit
                    })
            except (TypeError, ValueError):
                pass

    _add_deck_check("Deck Flexure (Sagging)", KEY_DD_M_ULS_SAG, KEY_DD_MU_BOT, "kN-m/m", "ur_bot_uls")
    _add_deck_check("Deck Flexure (Hogging)", KEY_DD_M_ULS_HOG, KEY_DD_MU_TOP, "kN-m/m", "ur_top_uls")
    
    overhang_m = float(input_dict.get("typical_section.deck_overhang", 0) or 0)
    if overhang_m > 0.01:
        _add_deck_check("Deck Cantilever Overhang", KEY_DD_M_ULS_OH, KEY_DD_MU_OH, "kN-m/m", "ur_oh_uls")
        
    _add_deck_check("Deck Punching Shear", KEY_DD_PUNCH_VED, KEY_DD_VRD_C_MPA, "MPa", "ur_bot_punch")
    _add_deck_check("Deck One-Way Shear", KEY_DD_SHEAR_VED, KEY_DD_SHEAR_VRDC, "kN/m", "ur_bot_shear")

    # Crack width check
    wk = None
    for k in ("KEY_DD_CRACK_WK_BOTTOM", "rebar_bottom_wk", "crack_bottom_wk"):
        v = dd_results.get(k)
        if v is not None:
            try:
                wk = float(v)
                break
            except Exception:
                pass
    wk_lim = dk_values.get(KEY_DD_WK_LIMIT) or dd_results.get("KEY_DD_CRACK_WK_LIMIT")
    if wk is not None and wk_lim is not None:
        try:
            wk_f = float(wk)
            lim_f = float(wk_lim)
            if lim_f > 0 and wk_f >= 0:
                deck_checks.append({
                    "label": "Deck Crack Width",
                    "demand": wk_f,
                    "capacity": lim_f,
                    "ur": round(wk_f / lim_f, 3),
                    "unit": "mm"
                })
        except (TypeError, ValueError):
            pass

    # ── 3. Cross Bracing Checks ──────────────────────────────────────────────
    bracing_checks: List[Dict[str, Any]] = []
    cb_pairs = getattr(bridge, "get_cb_pairs", lambda: [])()
    
    best_comp = None
    best_tens = None
    best_slend = None
    
    for pair in cb_pairs:
        for member in ("diagonal", "chord"):
            # Compression
            c_cap = bridge.get_cb_capacity(pair, member, "compression")
            c_eff = bridge.get_cb_efficiency(pair, member, "compression")
            try:
                ur_c = float(c_eff)
                cap_c = float(c_cap)
                dem_c = ur_c * cap_c
                if best_comp is None or ur_c > best_comp["ur"]:
                    best_comp = {
                        "label": f"Bracing Comp. ({pair})",
                        "demand": round(dem_c, 2),
                        "capacity": round(cap_c, 2),
                        "ur": round(ur_c, 3),
                        "unit": "kN"
                    }
            except (TypeError, ValueError):
                pass
                
            # Tension
            t_cap = bridge.get_cb_capacity(pair, member, "tension")
            t_eff = bridge.get_cb_efficiency(pair, member, "tension")
            try:
                ur_t = float(t_eff)
                cap_t = float(t_cap)
                dem_t = ur_t * cap_t
                if best_tens is None or ur_t > best_tens["ur"]:
                    best_tens = {
                        "label": f"Bracing Tens. ({pair})",
                        "demand": round(dem_t, 2),
                        "capacity": round(cap_t, 2),
                        "ur": round(ur_t, 3),
                        "unit": "kN"
                    }
            except (TypeError, ValueError):
                pass
                
            # Slenderness
            s_val = bridge.get_cb_slenderness(pair, member)
            try:
                sf = float(s_val)
                lim = 400.0 if member == "chord" else 250.0
                ur_s = sf / lim
                if best_slend is None or ur_s > best_slend["ur"]:
                    best_slend = {
                        "label": f"Bracing Slenderness ({pair})",
                        "demand": round(sf, 1),
                        "capacity": round(lim, 1),
                        "ur": round(ur_s, 3),
                        "unit": "-"
                    }
            except (TypeError, ValueError):
                pass

    if best_comp:
        bracing_checks.append(best_comp)
    if best_tens:
        bracing_checks.append(best_tens)
    if best_slend:
        bracing_checks.append(best_slend)

    # ── 4. Aggregate Overall Controlling Checks ──────────────────────────────
    overall: List[Dict[str, Any]] = []

    for lbl, (ur, dem, cap, unit, g_name) in governing_girder_checks.items():
        overall.append({
            "label": f"{lbl} ({g_name})",
            "demand": dem,
            "capacity": cap,
            "ur": ur,
            "unit": unit,
            "component": "Plate Girder"
        })

    for d in deck_checks:
        overall.append({
            "label": d["label"],
            "demand": d.get("demand"),
            "capacity": d.get("capacity"),
            "ur": d["ur"],
            "unit": d.get("unit", ""),
            "component": "Deck Slab"
        })

    for b in bracing_checks:
        overall.append({
            "label": b["label"],
            "demand": b.get("demand"),
            "capacity": b.get("capacity"),
            "ur": b["ur"],
            "unit": b.get("unit", ""),
            "component": "Cross Bracing"
        })

    return {
        "overall": overall,
        "girders": girder_checks,
        "deck": deck_checks,
        "bracing": bracing_checks
    }


def plot_overall_ur_chart(overall_checks: List[Dict[str, Any]], output_path: str) -> Optional[str]:
    """Generate overall governing utilization ratio bar chart."""
    if not overall_checks:
        return None
        
    labels = [c["label"] for c in overall_checks]
    urs = [c["ur"] for c in overall_checks]
    
    colors = []
    for u in urs:
        if u > 1.0:
            colors.append(Colors.FAIL_RED)     # Over limit (Red)
        elif u > 0.85:
            colors.append(Colors.WARN_AMBER)   # Economical (Amber)
        else:
            colors.append(Colors.PASS_GREEN)   # Safe (Green)
            
    fig, ax = plt.subplots(figsize=(10.5, 4.6), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    
    x = range(len(labels))
    bars = ax.bar(x, urs, width=0.55, color=colors, edgecolor="#212121", linewidth=0.8, zorder=3)
    
    # Red dashed reference line at UR = 1.0
    ax.axhline(1.0, color="#D32F2F", linestyle="--", linewidth=1.6, zorder=5, label="UR = 1.0 (Allowable Limit)")
    
    # Value annotations on top of bars
    for bar, u in zip(bars, urs):
        h = bar.get_height()
        txt_color = "#B71C1C" if u > 1.0 else "#212121"
        fontweight = "bold" if u > 0.90 else "normal"
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            h + 0.02,
            f"{u:.2f}",
            ha="center",
            va="bottom",
            fontsize=8.5,
            color=txt_color,
            fontweight=fontweight,
            zorder=6
        )
        
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9, fontweight="medium")
    
    y_max = max(1.20, max(urs) * 1.18)
    ax.set_ylim(0.0, y_max)
    ax.set_ylabel(r"Utilization Ratio, $UR = \frac{\mathrm{Demand}}{\mathrm{Capacity}}$", fontsize=10, fontweight="bold")
    ax.set_title("Overall Governing Utilization Ratios Across All Design Checks", fontsize=11, fontweight="bold", pad=12)
    
    ax.yaxis.grid(True, linestyle=":", alpha=0.6, color="#BDBDBD", zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#616161")
    ax.spines["bottom"].set_color("#616161")
    
    legend_elements = [
        Line2D([0], [0], color="#D32F2F", linestyle="--", linewidth=1.6, label="Allowable Limit (UR = 1.0)"),
        Patch(facecolor="#2E7D32", edgecolor="#212121", label="Safe (UR ≤ 0.85)"),
        Patch(facecolor="#F57C00", edgecolor="#212121", label="Economical (0.85 < UR ≤ 1.0)"),
    ]
    if any(u > 1.0 for u in urs):
        legend_elements.append(Patch(facecolor="#D32F2F", edgecolor="#212121", label="Exceeds Limit (UR > 1.0)"))
        
    ax.legend(handles=legend_elements, loc="upper right", framealpha=0.9, fontsize=8.5)
    
    plt.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def plot_girder_ur_chart(girder_checks: Dict[str, Dict[str, tuple]], output_path: str) -> Optional[str]:
    """Generate plate girder utilization ratios grouped by limit state and girder."""
    if not girder_checks:
        return None
        
    girders = sorted(girder_checks.keys())
    if not girders:
        return None
        
    PRIMARY_CHECKS = [
        ("Girder Moment",     "#1976D2"),
        ("Girder Shear",      "#388E3C"),
        ("Girder LTB",        "#7B1FA2"),
        ("Girder Deflection", "#F57C00"),
    ]
    
    active_checks = []
    for chk_name, col in PRIMARY_CHECKS:
        if any(chk_name in girder_checks[g] for g in girders):
            active_checks.append((chk_name, col))
            
    if not active_checks:
        return None
        
    import numpy as np
    x = np.arange(len(girders))
    n_bars = len(active_checks)
    bar_width = 0.75 / n_bars
    
    fig, ax = plt.subplots(figsize=(9.5, 4.4), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    
    all_urs = []
    for i, (chk_name, col) in enumerate(active_checks):
        offset = (i - (n_bars - 1) / 2.0) * bar_width
        check_urs = []
        for g in girders:
            val_tuple = girder_checks[g].get(chk_name)
            ur_val = val_tuple[2] if val_tuple else 0.0
            check_urs.append(ur_val)
            if ur_val > 0:
                all_urs.append(ur_val)
                
        bars = ax.bar(x + offset, check_urs, width=bar_width * 0.9, label=chk_name, color=col, edgecolor="#212121", linewidth=0.6, zorder=3)
        for b, u in zip(bars, check_urs):
            if u > 0:
                ax.text(b.get_x() + b.get_width() / 2.0, u + 0.02, f"{u:.2f}", ha="center", va="bottom", fontsize=7.5, zorder=6)
                
    # Red dashed reference line at UR = 1.0
    ax.axhline(1.0, color="#D32F2F", linestyle="--", linewidth=1.5, zorder=5, label="UR = 1.0 (Limit)")
    
    ax.set_xticks(x)
    ax.set_xticklabels(girders, fontsize=9.5, fontweight="bold")
    ax.set_xlabel("Girder Designation", fontsize=10, fontweight="bold")
    ax.set_ylabel(r"Utilization Ratio, $UR = \frac{\mathrm{Demand}}{\mathrm{Capacity}}$", fontsize=10, fontweight="bold")
    ax.set_title("Plate Girder Utilization Ratios by Limit State and Member", fontsize=11, fontweight="bold", pad=12)
    
    y_max = max(1.20, (max(all_urs) * 1.18) if all_urs else 1.20)
    ax.set_ylim(0.0, y_max)
    ax.yaxis.grid(True, linestyle=":", alpha=0.6, color="#BDBDBD", zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    ax.legend(loc="upper right", framealpha=0.9, fontsize=8.5)
    plt.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def plot_deck_bracing_ur_chart(deck_checks: List[Dict[str, Any]], bracing_checks: List[Dict[str, Any]], output_path: str) -> Optional[str]:
    """Generate concrete deck slab and transverse bracing utilization ratio chart."""
    combined = deck_checks + bracing_checks
    if not combined:
        return None
        
    labels = [c["label"] for c in combined]
    urs = [c["ur"] for c in combined]
    
    colors = []
    for u in urs:
        if u > 1.0:
            colors.append("#D32F2F")
        elif u > 0.85:
            colors.append("#F57C00")
        else:
            colors.append("#00897B")  # Teal
            
    fig, ax = plt.subplots(figsize=(9.5, 4.4), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    
    x = range(len(labels))
    bars = ax.bar(x, urs, width=0.55, color=colors, edgecolor="#212121", linewidth=0.8, zorder=3)
    
    # Red dashed reference line at UR = 1.0
    ax.axhline(1.0, color="#D32F2F", linestyle="--", linewidth=1.5, zorder=5, label="UR = 1.0 (Limit)")
    
    for bar, u in zip(bars, urs):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2.0, h + 0.02, f"{u:.2f}", ha="center", va="bottom", fontsize=8.5, zorder=6)
        
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9, fontweight="medium")
    
    y_max = max(1.20, max(urs) * 1.18)
    ax.set_ylim(0.0, y_max)
    ax.set_ylabel(r"Utilization Ratio, $UR = \frac{\mathrm{Demand}}{\mathrm{Capacity}}$", fontsize=10, fontweight="bold")
    ax.set_title("Reinforced Concrete Deck Slab and Bracing Utilization Ratios", fontsize=11, fontweight="bold", pad=12)
    
    ax.yaxis.grid(True, linestyle=":", alpha=0.6, color="#BDBDBD", zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    ax.legend(loc="upper right", framealpha=0.9, fontsize=8.5)
    plt.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def generate_all_ur_charts(bridge: Any, images_dir: str) -> Dict[str, str]:
    """
    Orchestrate extraction of design results and generation of UR bar charts.
    Returns a dict mapping chart keys to their image file paths.
    """
    os.makedirs(images_dir, exist_ok=True)
    data = extract_design_utilization_ratios(bridge)
    
    paths: Dict[str, str] = {}
    
    # 1. Overall Governing UR Chart
    if data["overall"]:
        p1 = os.path.join(images_dir, "ur_chart_overall.png")
        if plot_overall_ur_chart(data["overall"], p1):
            paths["ur_chart_overall"] = p1
            
    # 2. Girder Limit States UR Chart
    if data["girders"]:
        p2 = os.path.join(images_dir, "ur_chart_girders.png")
        if plot_girder_ur_chart(data["girders"], p2):
            paths["ur_chart_girders"] = p2
            
    # 3. Deck and Bracing UR Chart
    if data["deck"] or data["bracing"]:
        p3 = os.path.join(images_dir, "ur_chart_deck_bracing.png")
        if plot_deck_bracing_ur_chart(data["deck"], data["bracing"], p3):
            paths["ur_chart_deck_bracing"] = p3
            
    return paths

