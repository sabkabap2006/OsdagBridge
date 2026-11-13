# =============================================================================
# OsdagBridge — Material Quantity Visualizations (Chapter 7)
# Generates publication-quality Matplotlib charts for:
#   Chart 1: Structural Steel Tonnage (Girders, Cross Bracing, End Diaphragms)
#   Chart 2: Concrete and Reinforcement Quantities (Concrete m³, Rebar MT)
# Strictly uses actual quantities extracted from Chapter 7 (Material Take-off).
# Never uses sample or manually invented structural values.
# =============================================================================

import os
import logging
from typing import Dict, Any, Optional

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

logger = logging.getLogger(__name__)


def _to_float(val: Any) -> Optional[float]:
    """Safely convert a string/number value to float >= 0, returning None if invalid or placeholder."""
    if val is None:
        return None
    s = str(val).strip()
    if s in ("N.A.", "N/A", "None", "", "nan"):
        return None
    try:
        f = float(s)
        return f if f >= 0.0 else None
    except (TypeError, ValueError):
        return None


def extract_boq_quantities(input_dict: dict, output_dict: dict = None) -> dict:
    """
    Extract verified real material quantities from input_dict and output_dict.
    All values strictly correspond to the Chapter 7 Bill of Materials.
    """
    if input_dict is None:
        input_dict = {}
    if output_dict is None:
        output_dict = {}

    # 1. Structural Steel Quantities (MT)
    girders_wt = _to_float(input_dict.get("steel_girders_wt_total"))
    
    bracing_top_wt  = _to_float(input_dict.get("bracing_top_wt_total"))
    bracing_bot_wt  = _to_float(input_dict.get("bracing_bot_wt_total"))
    bracing_diag_wt = _to_float(input_dict.get("bracing_diag_wt_total"))
    
    cb_parts = [v for v in (bracing_top_wt, bracing_bot_wt, bracing_diag_wt) if v is not None]
    cross_bracing_wt = sum(cb_parts) if cb_parts else None

    ed_wt = _to_float(input_dict.get("ed_wt_total"))
    
    # Total steel check
    has_valid_steel = (girders_wt is not None and girders_wt > 0)
    total_steel_wt = 0.0
    if has_valid_steel:
        total_steel_wt += girders_wt
        if cross_bracing_wt is not None:
            total_steel_wt += cross_bracing_wt
        if ed_wt is not None:
            total_steel_wt += ed_wt
    else:
        total_steel_wt = None

    # 2. Concrete and Reinforcement Quantities
    concrete_vol = _to_float(input_dict.get("concrete_deck_vol_total"))
    concrete_wt  = _to_float(input_dict.get("concrete_deck_wt_total"))
    rebar_wt     = _to_float(input_dict.get("rebar_deck_wt_total"))
    rebar_vol    = _to_float(input_dict.get("rebar_deck_vol_total"))

    has_valid_concrete_rebar = (
        concrete_vol is not None and concrete_vol > 0 and
        rebar_wt is not None and rebar_wt > 0
    )

    return {
        "steel": {
            "girders": girders_wt,
            "cross_bracing": cross_bracing_wt,
            "end_diaphragm": ed_wt,
            "total": total_steel_wt,
        },
        "concrete": {
            "volume_m3": concrete_vol,
            "weight_mt": concrete_wt,
        },
        "rebar": {
            "weight_mt": rebar_wt,
            "volume_m3": rebar_vol,
        },
        "has_valid_steel": has_valid_steel,
        "has_valid_concrete_rebar": has_valid_concrete_rebar,
    }


def plot_steel_tonnage_chart(steel_data: dict, output_path: str) -> Optional[str]:
    """
    Generate Chart 1: Structural Steel Tonnage Breakdown
    Includes:
      - Girders
      - Cross Bracing
      - End Diaphragms
      - Total Structural Steel
    """
    if not steel_data or not steel_data.get("has_valid_steel", False):
        return None

    steel = steel_data.get("steel", {})
    g_wt  = steel.get("girders") or 0.0
    cb_wt = steel.get("cross_bracing") or 0.0
    ed_wt = steel.get("end_diaphragm") or 0.0
    tot_wt = steel.get("total") or (g_wt + cb_wt + ed_wt)

    if tot_wt <= 0.0:
        return None

    categories = [
        "Plate Girders",
        "Cross Bracing\n(Intermediate)",
        "End Diaphragms\n(Supports)",
        "Total Steel\n(Superstructure)"
    ]
    weights = [g_wt, cb_wt, ed_wt, tot_wt]
    percentages = [
        (g_wt / tot_wt * 100.0) if tot_wt > 0 else 0.0,
        (cb_wt / tot_wt * 100.0) if tot_wt > 0 else 0.0,
        (ed_wt / tot_wt * 100.0) if tot_wt > 0 else 0.0,
        100.0
    ]

    colors = ["#1976D2", "#00897B", "#43A047", "#37474F"]
    edge_styles = ["-", "-", "-", "--"]

    fig, ax = plt.subplots(figsize=(9.2, 4.5), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    x = range(len(categories))
    bars = ax.bar(
        x,
        weights,
        width=0.54,
        color=colors,
        edgecolor="#212121",
        linewidth=0.9,
        zorder=3
    )

    # Set distinct dashed boundary for the summary total bar
    bars[3].set_linestyle("--")
    bars[3].set_linewidth(1.4)

    # Add numeric labels and percentages above each bar
    for bar, wt, pct, idx in zip(bars, weights, percentages, range(len(weights))):
        h = bar.get_height()
        fontweight = "bold" if idx == 3 else "semibold"
        if idx == 3:
            label_text = f"{wt:.2f} MT\n(100%)"
        else:
            label_text = f"{wt:.2f} MT\n({pct:.1f}%)" if wt > 0 else f"{wt:.2f} MT\n(0.0%)"
        
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            h + (tot_wt * 0.02),
            label_text,
            ha="center",
            va="bottom",
            fontsize=9.0,
            color="#212121",
            fontweight=fontweight,
            zorder=6
        )

    ax.set_xticks(list(x))
    ax.set_xticklabels(categories, fontsize=9.5, fontweight="medium")

    y_max = max(tot_wt * 1.22, 1.0)
    ax.set_ylim(0.0, y_max)
    ax.set_ylabel("Structural Steel Weight (Metric Tonnes, MT)", fontsize=10, fontweight="bold")
    ax.set_title("Structural Steel Tonnage Breakdown (IS 2062)", fontsize=11, fontweight="bold", pad=12)

    ax.yaxis.grid(True, linestyle=":", alpha=0.6, color="#BDBDBD", zorder=0)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#616161")
    ax.spines["bottom"].set_color("#616161")

    # Legend indicating components
    legend_elements = [
        Patch(facecolor="#1976D2", edgecolor="#212121", label=f"Plate Girders ({g_wt:.2f} MT)"),
        Patch(facecolor="#00897B", edgecolor="#212121", label=f"Cross Bracing ({cb_wt:.2f} MT)"),
        Patch(facecolor="#43A047", edgecolor="#212121", label=f"End Diaphragms ({ed_wt:.2f} MT)"),
        Patch(facecolor="#37474F", edgecolor="#212121", linestyle="--", label=f"Total Tonnage ({tot_wt:.2f} MT)"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", framealpha=0.92, fontsize=8.5)

    plt.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def plot_concrete_rebar_chart(concrete_data: dict, rebar_data: dict, output_path: str) -> Optional[str]:
    """
    Generate Chart 2: Concrete Volume and Reinforcement Steel Quantities
    Includes:
      - Concrete volume in m³ (Deck Slab)
      - Reinforcement steel weight in MT
    Uses side-by-side subplots to cleanly respect the physical dimension differences (m³ vs MT).
    """
    c_vol = concrete_data.get("volume_m3")
    c_wt  = concrete_data.get("weight_mt")
    r_wt  = rebar_data.get("weight_mt")

    if c_vol is None or r_wt is None or c_vol <= 0 or r_wt <= 0:
        return None

    # Calculate actual rebar density (kg/m³)
    rebar_density = (r_wt * 1000.0) / c_vol if c_vol > 0 else 120.0
    concrete_wt_est = c_wt if (c_wt and c_wt > 0) else (c_vol * 2.5)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.2, 4.4), dpi=200)
    fig.patch.set_facecolor("white")

    # ── Panel 1: Concrete Volume (m³) ─────────────────────────────────────────
    ax1.set_facecolor("white")
    bar1 = ax1.bar(
        [0],
        [c_vol],
        width=0.45,
        color="#455A64",
        edgecolor="#212121",
        linewidth=0.9,
        zorder=3
    )
    ax1.text(
        0,
        c_vol + (c_vol * 0.03),
        f"{c_vol:.2f} m³",
        ha="center",
        va="bottom",
        fontsize=10.5,
        fontweight="bold",
        color="#212121",
        zorder=6
    )
    ax1.set_xticks([0])
    ax1.set_xticklabels(["Concrete Deck Slab\n(Grade M40)"], fontsize=9.5, fontweight="semibold")
    ax1.set_ylim(0.0, c_vol * 1.25)
    ax1.set_ylabel(r"Concrete Volume ($\mathrm{m}^3$)", fontsize=10, fontweight="bold")
    ax1.set_title(r"Concrete Volume ($\mathrm{m}^3$)", fontsize=11, fontweight="bold", pad=10)
    ax1.yaxis.grid(True, linestyle=":", alpha=0.6, color="#BDBDBD", zorder=0)
    ax1.set_axisbelow(True)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.spines["left"].set_color("#616161")
    ax1.spines["bottom"].set_color("#616161")

    # Informational card inside ax1
    ax1.text(
        0.5, 0.15,
        f"Design Volume: {c_vol:.2f} m³\nTotal Mass: {concrete_wt_est:.2f} MT\nUnit Weight: 25.0 kN/m³",
        transform=ax1.transAxes,
        ha="center",
        va="center",
        fontsize=8.5,
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#ECEFF1", edgecolor="#90A4AE", alpha=0.9)
    )

    # ── Panel 2: Reinforcement Steel Weight (MT) ──────────────────────────────
    ax2.set_facecolor("white")
    bar2 = ax2.bar(
        [0],
        [r_wt],
        width=0.45,
        color="#D84315",
        edgecolor="#212121",
        linewidth=0.9,
        zorder=3
    )
    ax2.text(
        0,
        r_wt + (r_wt * 0.03),
        f"{r_wt:.2f} MT",
        ha="center",
        va="bottom",
        fontsize=10.5,
        fontweight="bold",
        color="#212121",
        zorder=6
    )
    ax2.set_xticks([0])
    ax2.set_xticklabels(["Deck Reinforcement\n(Grade Fe 500)"], fontsize=9.5, fontweight="semibold")
    ax2.set_ylim(0.0, r_wt * 1.25)
    ax2.set_ylabel("Reinforcement Steel Weight (MT)", fontsize=10, fontweight="bold")
    ax2.set_title("Reinforcement Steel Weight (MT)", fontsize=11, fontweight="bold", pad=10)
    ax2.yaxis.grid(True, linestyle=":", alpha=0.6, color="#BDBDBD", zorder=0)
    ax2.set_axisbelow(True)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.spines["left"].set_color("#616161")
    ax2.spines["bottom"].set_color("#616161")

    # Informational card inside ax2
    ax2.text(
        0.5, 0.15,
        f"Rebar Mass: {r_wt:.2f} MT\nRebar Density: {rebar_density:.1f} kg/m³\nCode: IRC 112 / IS 1786",
        transform=ax2.transAxes,
        ha="center",
        va="center",
        fontsize=8.5,
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#FBE9E7", edgecolor="#FFAB91", alpha=0.9)
    )

    plt.suptitle("Superstructure Concrete and Reinforcement Quantities (Chapter 7)", fontsize=11.5, fontweight="bold", y=1.02)
    plt.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def generate_all_boq_charts(input_dict: dict, output_dict: dict, images_dir: str) -> Dict[str, str]:
    """
    Orchestrates extraction of Chapter 7 quantities and generation of BOQ charts.
    Returns a dictionary mapping figure keys to their file paths:
      - 'boq_chart_steel': path to Chart 1 (Structural Steel Tonnage)
      - 'boq_chart_concrete_rebar': path to Chart 2 (Concrete & Reinforcement)
    """
    os.makedirs(images_dir, exist_ok=True)
    quantities = extract_boq_quantities(input_dict, output_dict)

    paths: Dict[str, str] = {}

    # 1. Chart 1: Structural Steel Tonnage
    if quantities.get("has_valid_steel", False):
        p1 = os.path.join(images_dir, "boq_chart_steel.png")
        if plot_steel_tonnage_chart(quantities, p1):
            paths["boq_chart_steel"] = p1

    # 2. Chart 2: Concrete and Reinforcement
    if quantities.get("has_valid_concrete_rebar", False):
        p2 = os.path.join(images_dir, "boq_chart_concrete_rebar.png")
        if plot_concrete_rebar_chart(quantities["concrete"], quantities["rebar"], p2):
            paths["boq_chart_concrete_rebar"] = p2

    return paths

