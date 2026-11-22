# =============================================================================
# OsdagBridge — BOQ (Bill of Quantities) Generator
# =============================================================================

import logging
import math
from typing import Any

from osdagbridge.core.utils.common import (
    KEY_SPAN,
    KEY_TS_NO_OF_GIRDERS,
    KEY_TS_DECK_THICKNESS,
    KEY_TS_GIRDER_SPACING,
    KEY_MP_GIRDER_DEPTH,
    KEY_MP_GIRDER_WEB_THICKNESS,
    KEY_MP_GIRDER_TOP_FLANGE_WIDTH,
    KEY_MP_GIRDER_TOP_FLANGE_THICKNESS,
    KEY_MP_GIRDER_BOTTOM_FLANGE_WIDTH,
    KEY_MP_GIRDER_BOTTOM_FLANGE_THICKNESS,
    KEY_CB_TYPE,
    KEY_CB_LOAD,
)

logger = logging.getLogger("osdagbridge.core.boq_generator")


def get_angle_section_properties(designation: str) -> tuple[float, float]:
    """Look up the cross-sectional area (cm²) and minimum radius of gyration (cm) of a structural angle."""
    if not designation:
        return (0.0, 0.0)
    raw = str(designation).upper().replace("ISA", "").strip()
    try:
        from osdagbridge.core.utils.common import _DB_PATH
        import sqlite3
        if _DB_PATH and _DB_PATH.exists():
            with sqlite3.connect(str(_DB_PATH)) as conn:
                cur = conn.cursor()
                norm = raw.replace(" ", "").replace("X", "*")
                cur.execute(
                    "SELECT Area, rvmin FROM Angles WHERE REPLACE(REPLACE(UPPER(Designation), ' ', ''), 'X', '*') = ?",
                    (norm,)
                )
                row = cur.fetchone()
                if row and row[0]:
                    return (float(row[0]), float(row[1]) if row[1] is not None else 0.0)
    except Exception as e:
        logger.debug(f"SQLite lookup error for {designation}: {e}")

    # Fallback to geometric approximation: (a + b - t) * t / 100 cm²
    try:
        parts = [float(p.strip()) for p in raw.replace("*", "x").replace("X", "x").split("x") if p.strip()]
        if len(parts) >= 3:
            a, b, t = parts[0], parts[1], parts[2]
            area = (a + b - t) * t / 100.0
            rv = 0.2 * min(a, b) / 10.0  # approximate rv ~ 0.2*b in cm
            return (area, rv)
    except Exception:
        pass
    return (0.0, 0.0)


def get_angle_section_area_cm2(designation: str) -> float:
    """Look up or approximate the cross-sectional area (cm²) of a structural angle."""
    return get_angle_section_properties(designation)[0]


def resolve_girder_value(source: dict, base_key: str, i: int = 0, default: Any = None) -> Any:
    """Resolve a girder property from an input/output dict, tolerating both the
    per-girder dynamic key scheme and the legacy scalar key.
    """
    candidates = [
        f"{base_key}.G{i + 1}.M1",
        base_key,
        f"{base_key}.G1.M1"
    ]
    for key in candidates:
        if key in source and source[key] is not None:
            return source[key]
    return default


def calculate_material_quantities(inputs: dict, outputs: dict) -> dict:
    """Calculate quantities (steel tonnage, concrete volume, rebar, studs)
    needed for the material take-off summary (Chapter 7).
    """
    quantities = {
        "steel_girders_vol_formula": "---",
        "steel_girders_qty": "---",
        "steel_girders_vol_total": "---",
        "steel_girders_wt_single": "---",
        "steel_girders_wt_total": "---",
        
        "steel_bracing_vol_formula": "---",
        "steel_bracing_qty": "---",
        "steel_bracing_vol_total": "---",
        "steel_bracing_wt_single": "---",
        "steel_bracing_wt_total": "---",

        "bracing_top_vol_formula": "---",
        "bracing_top_qty": "---",
        "bracing_top_vol_total": "---",
        "bracing_top_wt_single": "---",
        "bracing_top_wt_total": "---",

        "bracing_bot_vol_formula": "---",
        "bracing_bot_qty": "---",
        "bracing_bot_vol_total": "---",
        "bracing_bot_wt_single": "---",
        "bracing_bot_wt_total": "---",

        "bracing_diag_vol_formula": "---",
        "bracing_diag_qty": "---",
        "bracing_diag_vol_total": "---",
        "bracing_diag_wt_single": "---",
        "bracing_diag_wt_total": "---",

        "ed_vol_formula": "---",
        "ed_qty": "---",
        "ed_vol_total": "---",
        "ed_wt_single": "---",
        "ed_wt_total": "---",
        
        "concrete_deck_vol_formula": "---",
        "concrete_deck_qty": "---",
        "concrete_deck_vol_total": "---",
        "concrete_deck_wt_single": "---",
        "concrete_deck_wt_total": "---",
        
        "rebar_deck_vol_formula": "---",
        "rebar_deck_qty": "---",
        "rebar_deck_vol_total": "---",
        "rebar_deck_wt_single": "---",
        "rebar_deck_wt_total": "---",
        
        "shear_studs_vol_formula": "---",
        "shear_studs_qty": "---",
        "shear_studs_vol_total": "---",
        "shear_studs_wt_single": "---",
        "shear_studs_wt_total": "---",

        "crash_barrier_vol_formula": "---",
        "crash_barrier_qty": "---",
        "crash_barrier_vol_total": "---",
        "crash_barrier_wt_single": "---",
        "crash_barrier_wt_total": "---",
    }
    try:
        span_val = inputs.get(KEY_SPAN) or inputs.get("span")
        n_girders_val = inputs.get(KEY_TS_NO_OF_GIRDERS) or inputs.get("no_of_girders")
        if span_val is None or n_girders_val is None:
            return quantities
            
        try:
            span = float(span_val)
            n_girders = int(n_girders_val)
        except Exception:
            return quantities

        if span <= 0 or n_girders <= 0:
            return quantities

        # 1. Concrete deck volume (Cu.m) and Weight (MT)
        overall_width_val = inputs.get("typical_section.overall_bridge_width")
        deck_thickness_val = inputs.get(KEY_TS_DECK_THICKNESS)
        
        if overall_width_val is not None and deck_thickness_val is not None:
            try:
                overall_width = float(overall_width_val)
                deck_thickness = float(deck_thickness_val) / 1000.0  # mm to m
                if overall_width > 0 and deck_thickness > 0:
                    concrete_vol = span * overall_width * deck_thickness
                    quantities["concrete_deck_vol_formula"] = f"${overall_width:.2f}\\text{{ m}} \\times {deck_thickness:.2f}\\text{{ m}} \\times {span:.2f}\\text{{ m}} = {concrete_vol:.2f}\\text{{ m}}^3$"
                    quantities["concrete_deck_qty"] = "1"
                    quantities["concrete_deck_vol_total"] = f"{concrete_vol:.2f}"
                    quantities["concrete_deck_wt_single"] = f"{(concrete_vol * 2.5):.2f}"
                    quantities["concrete_deck_wt_total"] = f"{(concrete_vol * 2.5):.2f}"

                    # 2. Reinforcement Steel (Cu.m) and Weight (MT)
                    rebar_wt_kg = concrete_vol * 120.0
                    rebar_vol = rebar_wt_kg / 7850.0
                    rebar_area = rebar_vol / span if span > 0 else 0.0
                    quantities["rebar_deck_vol_formula"] = f"${rebar_area:.6f}\\text{{ m}}^2 \\times {span:.2f}\\text{{ m}} = {rebar_vol:.5f}\\text{{ m}}^3$"
                    quantities["rebar_deck_qty"] = "1"
                    quantities["rebar_deck_vol_total"] = f"{rebar_vol:.2f}"
                    
                    rebar_wt_mt = rebar_wt_kg / 1000.0
                    quantities["rebar_deck_wt_single"] = f"{rebar_wt_mt:.2f}"
                    quantities["rebar_deck_wt_total"] = f"{rebar_wt_mt:.2f}"
            except Exception:
                pass

        # 3. Steel Girders (Cu.m) and Weight (MT)
        girder_area = 0.0
        try:
            # Resolve representative girder sectional area
            girder_area = float(resolve_girder_value(inputs, "member_properties.girder_details.section_properties.area", 0))
        except Exception:
            pass

        # Calculate from inputs if not in properties
        if girder_area <= 0:
            try:
                dw_val = (resolve_girder_value(inputs, KEY_MP_GIRDER_DEPTH, 0) or
                          resolve_girder_value(inputs, "member_properties.girder_details.section_input.depth", 0) or
                          resolve_girder_value(inputs, "member_properties.girder_details.section_input.web_depth", 0))
                tw_val = (resolve_girder_value(inputs, KEY_MP_GIRDER_WEB_THICKNESS, 0) or
                          resolve_girder_value(inputs, "member_properties.girder_details.section_input.web_thickness", 0))
                bft_val = (resolve_girder_value(inputs, KEY_MP_GIRDER_TOP_FLANGE_WIDTH, 0) or
                           resolve_girder_value(inputs, "member_properties.girder_details.section_input.top_flange_width", 0))
                tft_val = (resolve_girder_value(inputs, KEY_MP_GIRDER_TOP_FLANGE_THICKNESS, 0) or
                           resolve_girder_value(inputs, "member_properties.girder_details.section_input.top_flange_thickness", 0))
                bfb_val = (resolve_girder_value(inputs, KEY_MP_GIRDER_BOTTOM_FLANGE_WIDTH, 0) or
                           resolve_girder_value(inputs, "member_properties.girder_details.section_input.bottom_flange_width", 0))
                tfb_val = (resolve_girder_value(inputs, KEY_MP_GIRDER_BOTTOM_FLANGE_THICKNESS, 0) or
                           resolve_girder_value(inputs, "member_properties.girder_details.section_input.bottom_flange_thickness", 0))
                
                if (dw_val is not None and tw_val is not None and 
                    bft_val is not None and tft_val is not None and 
                    bfb_val is not None and tfb_val is not None):
                    
                    dw = float(dw_val)
                    tw = float(tw_val)
                    bft = float(bft_val)
                    tft = float(tft_val)
                    bfb = float(bfb_val)
                    tfb = float(tfb_val)
                    
                    # Convert dimensions to metres if in mm (> 6.0), otherwise already in metres
                    if dw <= 6.0:
                        girder_area = (dw * tw) + (bft * tft) + (bfb * tfb)
                    else:
                        girder_area = ((dw * tw) + (bft * tft) + (bfb * tfb)) / 1e6
            except Exception:
                pass

        total_girder_mass = 0.0
        if girder_area > 0:
            girder_vol = girder_area * span
            quantities["steel_girders_vol_formula"] = f"${girder_area:.5f}\\text{{ m}}^2 \\times {span:.2f}\\text{{ m}} = {girder_vol:.5f}\\text{{ m}}^3$"
            quantities["steel_girders_qty"] = str(n_girders)
            
            # calculate tonnage / volume
            for gi in range(n_girders):
                try:
                    mass_per_m = float(resolve_girder_value(inputs, "member_properties.girder_details.section_properties.mass", gi))
                    total_girder_mass += mass_per_m * span
                except Exception:
                    total_girder_mass += girder_area * span * 7850.0
            
            girder_total_vol = n_girders * girder_vol
            quantities["steel_girders_vol_total"] = f"{girder_total_vol:.2f}"
            
            single_girder_wt = (total_girder_mass / n_girders) / 1000.0
            total_girder_wt = total_girder_mass / 1000.0
            quantities["steel_girders_wt_single"] = f"{single_girder_wt:.2f}"
            quantities["steel_girders_wt_total"] = f"{total_girder_wt:.2f}"

        # 4. Shear Stud Connectors (Cu.m) and Weight (MT)
        spacing_mm = 0.0
        studs_per_sec = 0
        stud_d = 0.0
        stud_h_mm = 0.0

        spacing_val = (
            outputs.get("steeldesign.details.shear.longitudinal_spacing")
            or outputs.get("design_results", {}).get("stud_spacing_provided_mm")
            or outputs.get("stud_spacing_provided_mm")
            or inputs.get("steeldesign.details.shear.longitudinal_spacing")
            or inputs.get("design_options.shear_studs.spacing")
            or inputs.get("stud_spacing")
            or 125.0
        )
        studs_val = (
            outputs.get("steeldesign.details.shear.studs_per_section")
            or outputs.get("shear_studs_per_section")
            or inputs.get("steeldesign.details.shear.studs_per_section")
            or inputs.get("design_options.shear_studs.count")
            or inputs.get("steeldesign.details.shear.studs_per_section")
            or 4
        )
        stud_d_val = (
            outputs.get("steeldesign.details.shear.diameter")
            or outputs.get("shear_stud_diameter")
            or inputs.get("steeldesign.details.shear.diameter")
            or inputs.get("design_options.shear_studs.diameter")
            or 25.0
        )
        stud_h_val = (
            outputs.get("steeldesign.details.shear.height")
            or outputs.get("shear_stud_height")
            or inputs.get("steeldesign.details.shear.height")
            or inputs.get("design_options.shear_studs.height")
            or 150.0
        )

        if spacing_val is not None and studs_val is not None and stud_d_val is not None and stud_h_val is not None:
            try:
                spacing_mm = float(spacing_val)
                studs_per_sec = int(studs_val)
                stud_d = float(stud_d_val)
                stud_h_mm = float(stud_h_val)
            except Exception:
                pass

        if spacing_mm > 0.0 and studs_per_sec > 0 and stud_d > 0.0 and stud_h_mm > 0.0:
            stud_h = stud_h_mm / 1000.0  # mm to m
            n_sections = int(span * 1000.0 / spacing_mm) + 1
            total_studs = n_girders * studs_per_sec * n_sections
            
            stud_area = (3.14159 * (stud_d / 1000.0) ** 2) / 4.0
            stud_vol = stud_area * stud_h
            quantities["shear_studs_vol_formula"] = f"${stud_area:.6f}\\text{{ m}}^2 \\times {stud_h:.3f}\\text{{ m}} = {stud_vol:.6f}\\text{{ m}}^3$"
            quantities["shear_studs_qty"] = str(total_studs)
            
            studs_total_vol = total_studs * stud_vol
            quantities["shear_studs_vol_total"] = f"{studs_total_vol:.2f}"
            
            # density of steel = 7850 kg/m^3 = 7.85 tonnes/m^3
            single_stud_wt = stud_vol * 7.85
            total_studs_wt = studs_total_vol * 7.85
            quantities["shear_studs_wt_single"] = f"{single_stud_wt:.6f}"
            quantities["shear_studs_wt_total"] = f"{total_studs_wt:.3f}"
        else:
            quantities["shear_studs_vol_formula"] = "---"
            quantities["shear_studs_qty"] = "---"
            quantities["shear_studs_vol_total"] = "---"
            quantities["shear_studs_wt_single"] = "---"
            quantities["shear_studs_wt_total"] = "---"

        # 5. Steel Bracings (Cu.m) and Weight (MT)
        # Find bracing section properties from outputs or skip if not present
        bracing_area = 0.0
        bracing_len = 0.0
        top_chord_enabled = True
        bot_chord_enabled = True

        bracing_area_val = outputs.get("transverse_member_design.cb.section_properties.bracing.G1G2.A")
        cb_forces = outputs.get("crossbracing_forces_dict")
        bracing_len_val = None
        if cb_forces:
            cb_geom = cb_forces.get("geometry")
            if cb_geom:
                bracing_len_val = cb_geom.get("diagonal_length_m")

        if bracing_area_val is not None:
            try:
                bracing_area = float(bracing_area_val) / 10000.0  # Convert cm² to m²
            except Exception:
                pass

        if bracing_len_val is not None:
            try:
                bracing_len = float(bracing_len_val)
            except Exception:
                pass

        # Fallback to section designation from inputs
        if bracing_area <= 0.0:
            cb_des = None
            for k, v in inputs.items():
                if "cb_bracing_section_designation" in str(k) or "bracing_section_designation" in str(k):
                    if v:
                        cb_des = str(v)
                        break
            if cb_des:
                area_cm2 = get_angle_section_area_cm2(cb_des)
                if area_cm2 > 0.0:
                    bracing_area = area_cm2 / 10000.0

        spacing_val = inputs.get(KEY_TS_GIRDER_SPACING)
        spacing = 0.0
        if spacing_val is not None:
            try:
                spacing = float(spacing_val)
            except Exception:
                pass

        # Girder depth for diagonal length calculation if needed
        girder_depth = 0.0
        try:
            d_val = resolve_girder_value(inputs, "member_properties.girder_details.section_input.web_depth", 0)
            if d_val is not None:
                girder_depth = float(d_val)
                if girder_depth > 6.0:
                    girder_depth /= 1000.0
        except Exception:
            pass
        if girder_depth <= 0.0:
            girder_depth = 1.67

        if bracing_len <= 0.0 and spacing > 0.0 and girder_depth > 0.0:
            bracing_len = math.sqrt(spacing**2 + girder_depth**2)

        # Only perform calculations if bracing is designed (area and length are positive)
        if bracing_area > 0.0 and bracing_len > 0.0 and spacing > 0.0:
            cb_forces = outputs.get("crossbracing_forces_dict", {}) or {}
            cb_geom = cb_forces.get("geometry", {}) or {}
            cb_spacing_val = cb_geom.get("cb_spacing_m")
            cb_spacing = 0.0
            if cb_spacing_val is not None:
                try:
                    cb_spacing = float(cb_spacing_val)
                except Exception:
                    pass
            if cb_spacing <= 0.0:
                for k, v in inputs.items():
                    if "cb_spacing" in str(k):
                        try:
                            cb_spacing = float(v)
                            break
                        except Exception:
                            pass
                    
            if cb_spacing > 0.0:
                n_panels = max(1, round(span / cb_spacing) - 1)
            else:
                n_panels = max(3, int(span / 5.0))

            # 5a. Top Chord
            top_chord_qty = (n_girders - 1) * n_panels if top_chord_enabled else 0
            top_chord_vol_single = bracing_area * spacing
            top_chord_vol_total = top_chord_qty * top_chord_vol_single
            top_chord_wt_single = top_chord_vol_single * 7.85
            top_chord_wt_total = top_chord_vol_total * 7.85
            
            quantities["bracing_top_vol_formula"] = f"${bracing_area:.5f}\\text{{ m}}^2 \\times {spacing:.2f}\\text{{ m}} = {top_chord_vol_single:.5f}\\text{{ m}}^3$"
            quantities["bracing_top_qty"] = str(top_chord_qty)
            quantities["bracing_top_vol_total"] = f"{top_chord_vol_total:.2f}" if top_chord_enabled else "0.00"
            quantities["bracing_top_wt_single"] = f"{top_chord_wt_single:.4f}"
            quantities["bracing_top_wt_total"] = f"{top_chord_wt_total:.2f}" if top_chord_enabled else "0.00"

            # 5b. Bottom Chord
            bot_chord_qty = (n_girders - 1) * n_panels if bot_chord_enabled else 0
            bot_chord_vol_single = bracing_area * spacing
            bot_chord_vol_total = bot_chord_qty * bot_chord_vol_single
            bot_chord_wt_single = bot_chord_vol_single * 7.85
            bot_chord_wt_total = bot_chord_vol_total * 7.85
            
            quantities["bracing_bot_vol_formula"] = f"${bracing_area:.5f}\\text{{ m}}^2 \\times {spacing:.2f}\\text{{ m}} = {bot_chord_vol_single:.5f}\\text{{ m}}^3$"
            quantities["bracing_bot_qty"] = str(bot_chord_qty)
            quantities["bracing_bot_vol_total"] = f"{bot_chord_vol_total:.2f}" if bot_chord_enabled else "0.00"
            quantities["bracing_bot_wt_single"] = f"{bot_chord_wt_single:.4f}"
            quantities["bracing_bot_wt_total"] = f"{bot_chord_wt_total:.2f}" if bot_chord_enabled else "0.00"

            # 5c. Diagonal
            diags_qty = (n_girders - 1) * n_panels * 2
            diag_vol_single = bracing_area * bracing_len
            diag_vol_total = diags_qty * diag_vol_single
            diag_wt_single = diag_vol_single * 7.85
            diag_wt_total = diag_vol_total * 7.85
            
            quantities["bracing_diag_vol_formula"] = f"${bracing_area:.5f}\\text{{ m}}^2 \\times {bracing_len:.2f}\\text{{ m}} = {diag_vol_single:.5f}\\text{{ m}}^3$"
            quantities["bracing_diag_qty"] = str(diags_qty)
            quantities["bracing_diag_vol_total"] = f"{diag_vol_total:.2f}"
            quantities["bracing_diag_wt_single"] = f"{diag_wt_single:.4f}"
            quantities["bracing_diag_wt_total"] = f"{diag_wt_total:.2f}"
        else:
            for prefix in ("bracing_top", "bracing_bot", "bracing_diag"):
                quantities[f"{prefix}_vol_formula"] = "---"
                quantities[f"{prefix}_qty"] = "---"
                quantities[f"{prefix}_vol_total"] = "---"
                quantities[f"{prefix}_wt_single"] = "---"
                quantities[f"{prefix}_wt_total"] = "---"

        # 5d. End Diaphragms (Cu.m) and Weight (MT)
        ed_type = ""
        for k, v in list(inputs.items()) + list(outputs.items()):
            if "end_diaphragm" in str(k) and "type" in str(k) and v:
                ed_type = str(v)
                break
        ed_is_beam = any(t in ed_type.lower() for t in ("beam", "rolled", "welded"))

        # Check end diaphragm area in cm²
        ed_area_cm2 = (
            outputs.get("transverse_member_design.ed.section_properties.end_diaphragm.G1G2.A")
            or outputs.get("transverse_member_design.ed.section_properties.bracing.G1G2.A")
            or outputs.get("transverse_member_design.ed.section_properties.end_diaphragm.A")
        )
        ed_area = 0.0
        if ed_area_cm2 is not None:
            try:
                ed_area = float(ed_area_cm2) / 10000.0  # cm² to m²
            except Exception:
                pass

        # Fallback to section designation from inputs
        if ed_area <= 0.0:
            ed_des = None
            for k, v in inputs.items():
                if ("end_diaphragm" in str(k) and "section_designation" in str(k)) or "ed_bracing" in str(k):
                    if v:
                        ed_des = str(v)
                        break
            if ed_des:
                area_cm2 = get_angle_section_area_cm2(ed_des)
                if area_cm2 > 0.0:
                    ed_area = area_cm2 / 10000.0

        # If cross-bracing ED and no specific ed_area, fallback to bracing_area
        if ed_area <= 0.0 and not ed_is_beam and bracing_area > 0.0:
            ed_area = bracing_area

        ed_bays = 2 * (n_girders - 1)
        if ed_bays > 0 and spacing > 0.0 and ed_area > 0.0:
            if ed_is_beam:
                # Beam diaphragm: 1 transverse beam per bay across the 2 ends
                ed_vol_single = ed_area * spacing
                ed_vol_total = ed_bays * ed_vol_single
                ed_wt_single = ed_vol_single * 7.85
                ed_wt_total = ed_vol_total * 7.85

                quantities["ed_vol_formula"] = f"${ed_area:.5f}\\text{{ m}}^2 \\times {spacing:.2f}\\text{{ m}} = {ed_vol_single:.5f}\\text{{ m}}^3$"
                quantities["ed_qty"] = str(ed_bays)
                quantities["ed_vol_total"] = f"{ed_vol_total:.2f}"
                quantities["ed_wt_single"] = f"{ed_wt_single:.4f}"
                quantities["ed_wt_total"] = f"{ed_wt_total:.2f}"
            else:
                # Cross bracing diaphragm: 2 diagonals + top chord + bottom chord per bay
                ed_geom = (outputs.get("end_diaphragm_forces_dict") or {}).get("geometry") or {}
                ed_diag_len = float(ed_geom.get("diagonal_length_m") or 0.0)
                if ed_diag_len <= 0.0:
                    ed_diag_len = bracing_len if bracing_len > 0.0 else math.sqrt(spacing**2 + girder_depth**2)

                ed_vol_single = ed_area * (2.0 * ed_diag_len + 2.0 * spacing)
                ed_vol_total = ed_bays * ed_vol_single
                ed_wt_single = ed_vol_single * 7.85
                ed_wt_total = ed_vol_total * 7.85

                quantities["ed_vol_formula"] = f"${ed_area:.5f}\\text{{ m}}^2 \\times ({2.0 * ed_diag_len + 2.0 * spacing:.2f}\\text{{ m}}) = {ed_vol_single:.5f}\\text{{ m}}^3$"
                quantities["ed_qty"] = str(ed_bays)
                quantities["ed_vol_total"] = f"{ed_vol_total:.2f}"
                quantities["ed_wt_single"] = f"{ed_wt_single:.4f}"
                quantities["ed_wt_total"] = f"{ed_wt_total:.2f}"
        else:
            quantities["ed_vol_formula"] = "---"
            quantities["ed_qty"] = "---"
            quantities["ed_vol_total"] = "---"
            quantities["ed_wt_single"] = "---"
            quantities["ed_wt_total"] = "---"

        # 6. Crash Barrier (Cu.m) and Weight (MT)
        KEY_CB_AREA = "typical_section.crash_barrier.area"
        cb_area = 0.0
        cb_area_val = inputs.get(KEY_CB_AREA)
        
        if cb_area_val is not None:
            try:
                cb_area = float(cb_area_val) / 1e6
            except Exception:
                pass

        if cb_area <= 0.0 and inputs.get("crash_barrier_wt_total") and inputs.get("crash_barrier_wt_total") not in ("N.A.", "---"):
            for k in ("crash_barrier_vol_formula", "crash_barrier_qty", "crash_barrier_vol_total", "crash_barrier_wt_single", "crash_barrier_wt_total"):
                if inputs.get(k):
                    quantities[k] = str(inputs.get(k))
        elif cb_area > 0.05:
            cb_vol = cb_area * span
            quantities["crash_barrier_vol_formula"] = f"${cb_area:.5f}\\text{{ m}}^2 \\times {span:.2f}\\text{{ m}} = {cb_vol:.5f}\\text{{ m}}^3$"
            quantities["crash_barrier_qty"] = "2"
            
            cb_total_vol = 2 * cb_vol
            quantities["crash_barrier_vol_total"] = f"{cb_total_vol:.2f}"
            
            single_cb_wt = cb_vol * 2.5
            total_cb_wt = cb_total_vol * 2.5
            quantities["crash_barrier_wt_single"] = f"{single_cb_wt:.2f}"
            quantities["crash_barrier_wt_total"] = f"{total_cb_wt:.2f}"
        elif (
            inputs.get("traffic_lane.barrier_type")
            or inputs.get("typical_section.crash_barrier.type")
            or inputs.get("crash_barrier_type")
            or inputs.get(KEY_CB_TYPE)
            or inputs.get(KEY_CB_LOAD)
            or inputs.get("components.crash_barrier.load")
        ):
            # Standard New Jersey Crash Barrier area = 0.25 m2 per barrier
            cb_area = 0.25
            cb_vol = cb_area * span
            quantities["crash_barrier_vol_formula"] = f"${cb_area:.2f}\\text{{ m}}^2 \\times {span:.2f}\\text{{ m}} = {cb_vol:.2f}\\text{{ m}}^3$"
            quantities["crash_barrier_qty"] = "2"
            cb_total_vol = 2 * cb_vol
            quantities["crash_barrier_vol_total"] = f"{cb_total_vol:.2f}"
            single_cb_wt = cb_vol * 2.5
            total_cb_wt = cb_total_vol * 2.5
            quantities["crash_barrier_wt_single"] = f"{single_cb_wt:.2f}"
            quantities["crash_barrier_wt_total"] = f"{total_cb_wt:.2f}"
        else:
            quantities["crash_barrier_vol_formula"] = "---"
            quantities["crash_barrier_qty"] = "---"
            quantities["crash_barrier_vol_total"] = "---"
            quantities["crash_barrier_wt_single"] = "---"
            quantities["crash_barrier_wt_total"] = "---"

        # 7. Total Structural Steel Summary (MT)
        try:
            total_steel_mt = 0.0
            has_steel = False
            gw = quantities.get("steel_girders_wt_total")
            if gw and gw not in ("N.A.", "---"):
                total_steel_mt += float(gw)
                has_steel = True
            for k in ("bracing_top_wt_total", "bracing_bot_wt_total", "bracing_diag_wt_total", "ed_wt_total"):
                bw = quantities.get(k)
                if bw and bw not in ("N.A.", "---"):
                    total_steel_mt += float(bw)
            if has_steel:
                quantities["total_structural_steel_wt"] = f"{total_steel_mt:.2f}"
            else:
                quantities["total_structural_steel_wt"] = "---"
        except Exception:
            quantities["total_structural_steel_wt"] = "---"

    except Exception as exc:
        logger.warning(f"Error calculating material quantities: {exc}")

    return quantities
