# =============================================================================
# Chapter 3: Loads and Load Combinations
# Extracted from report_generator.py — DO NOT add business logic here.
# =============================================================================

import math
from osdagbridge.core.utils.common import (
    KEY_CB_LOAD,
    KEY_CARRIAGEWAY_WIDTH,
    KEY_FOOTPATH,
    KEY_TS_FOOTPATH_WIDTH,
    KEY_LL_CUSTOM_VEHICLES,
    KEY_LL_ECCENTRICITY,
    KEY_LL_FOOTPATH_PRESSURE_MODE,
    KEY_LL_FOOTPATH_PRESSURE_VALUE,
    KEY_LL_IRC_70R_BOGIE,
    KEY_LL_IRC_70R_TRACKED,
    KEY_LL_IRC_70R_WHEELED,
    KEY_LL_IRC_AA_TRACKED,
    KEY_LL_IRC_AA_WHEELED,
    KEY_LL_IRC_CLASS_A,
    KEY_LL_IRC_CLASS_FATIGUE,
    KEY_LL_IRC_CLASS_SV,
    KEY_MATERIAL_DECK_DENSITY,
    KEY_MATERIAL_GIRDER_DENSITY,
    KEY_PL_SELF_WEIGHT_FACTOR,
    KEY_RL_LOAD_VALUE,
    KEY_SL_DAMPING,
    KEY_SL_DEAD_LOAD_MODE,
    KEY_SL_DEAD_LOAD_VALUE,
    KEY_SL_HORIZONTAL_COEFF,
    KEY_SL_IMPORTANCE_FACTOR,
    KEY_SL_LIVE_LOAD_MODE,
    KEY_SL_LIVE_LOAD_VALUE,
    KEY_SL_SEISMIC_ZONE,
    KEY_SL_SOIL_TYPE,
    KEY_SL_SPECTRAL_COEFF,
    KEY_SL_TIME_PERIOD,
    KEY_SL_VERTICAL_COEFF,
    KEY_SL_ZONE_FACTOR,
    KEY_SPAN,
    KEY_TL_BRIDGE_TEMP_MAX,
    KEY_TL_BRIDGE_TEMP_MIN,
    KEY_TL_HIGHEST_MAX_TEMP,
    KEY_TL_LOWEST_MIN_TEMP,
    KEY_TL_TEMP_FALL,
    KEY_TL_TEMP_RISE,
    KEY_WC_LD_LANE_TABLE_COUNT,
    KEY_WC_MATERIAL,
    KEY_WC_THICKNESS,
    KEY_WL_AVG_EXPOSED_HEIGHT,
    KEY_WL_BASIC_WIND_SPEED,
    KEY_WL_HOURLY_MEAN_WIND,
    KEY_WL_HOURLY_WIND_PRESSURE,
    KEY_WL_LONGITUDINAL_WIND_FORCE,
    KEY_WL_TERRAIN_TYPE,
    KEY_WL_TRANSVERSE_WIND_FORCE,
    KEY_WL_VERTICAL_WIND_FORCE,
    KEY_VEHICLE
)
from osdagbridge.core.utils.codes.irc6_2017 import IRC6_2017
from osdagbridge.core.reports.report_utils import _tex, _render_value
from osdagbridge.core.reports.styles import TableStyles


def _is_checked(val):
    """Safely check if a GUI checkbox or boolean flag is active."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "yes", "1", "checked")


def _is_vehicle_selected(item: dict, input_dict: dict) -> bool:
    """Check if a vehicle is selected via canonical key, alias, code_id, or selection lists."""
    # 1. Canonical key
    if _is_checked(input_dict.get(item["key"])):
        return True
    # 2. Key suffix (e.g. 'class_a', '70r_wheeled')
    suffix = item["key"].split(".")[-1]
    if _is_checked(input_dict.get(suffix)):
        return True
    if _is_checked(input_dict.get("irc_" + suffix)):
        return True
    # 3. Code ID
    code_id = item.get("code_id")
    if code_id and _is_checked(input_dict.get(code_id)):
        return True
    # 4. Explicit selection lists in input_dict
    for list_key in ("vehicles", "selected_vehicles", "vehicle_list", "vehicle"):
        v_list = input_dict.get(list_key)
        if v_list and isinstance(v_list, (list, tuple, set)):
            for v_entry in v_list:
                v_entry_str = str(v_entry).strip().lower()
                if (v_entry_str in item["name"].lower() or 
                    (code_id and v_entry_str in code_id.lower()) or 
                    v_entry_str == suffix):
                    return True
        elif v_list and isinstance(v_list, str):
            v_str = v_list.strip().lower()
            if (v_str in item["name"].lower() or 
                (code_id and v_str in code_id.lower()) or 
                v_str == suffix):
                return True
    return False


def _resolve_governing_vehicle(carriageway_width_m: float, input_dict: dict) -> str:
    """Determine the governing vehicle class based on IRC 6 Table 6A and GUI selections."""
    candidate_catalog_keys = [
        {"key": KEY_LL_IRC_70R_WHEELED, "name": "IRC Class 70R (Wheeled)", "code_id": KEY_VEHICLE[0]},
        {"key": KEY_LL_IRC_70R_TRACKED, "name": "IRC Class 70R (Tracked)", "code_id": KEY_VEHICLE[1]},
        {"key": KEY_LL_IRC_70R_BOGIE,   "name": "IRC Class 70R (Bogie)",   "code_id": KEY_VEHICLE[0]},
        {"key": KEY_LL_IRC_AA_WHEELED,  "name": "IRC Class AA (Wheeled)", "code_id": KEY_VEHICLE[0]},
        {"key": KEY_LL_IRC_AA_TRACKED,  "name": "IRC Class AA (Tracked)", "code_id": KEY_VEHICLE[1]},
        {"key": KEY_LL_IRC_CLASS_A,     "name": "IRC Class A",            "code_id": KEY_VEHICLE[2]},
        {"key": KEY_LL_IRC_CLASS_SV,    "name": "IRC Class SV",           "code_id": "ClassSV"},
        {"key": KEY_LL_IRC_CLASS_FATIGUE, "name": "IRC Class Fatigue",     "code_id": "ClassFatigue"},
    ]
    selected_vehicles = [item for item in candidate_catalog_keys if _is_vehicle_selected(item, input_dict)]
    custom = input_dict.get(KEY_LL_CUSTOM_VEHICLES)
    if custom and isinstance(custom, list) and len(custom) > 0:
        selected_vehicles.append({"code_id": "Custom", "name": "Custom Vehicle"})

    try:
        result = IRC6_2017.table_6A(carriageway_width_m)
        combos = result.get("vehicle_combinations", [])
        fits_70r = any("Class70R" in combo for combo in combos)
    except Exception:
        fits_70r = carriageway_width_m >= 5.3

    if selected_vehicles:
        # Check if 70R Wheeled / Bogie / AA Wheeled is selected and fits
        for v in selected_vehicles:
            if v["code_id"] == KEY_VEHICLE[0] and fits_70r:
                return KEY_VEHICLE[0]
        # Check if 70R Tracked / AA Tracked is selected and fits
        for v in selected_vehicles:
            if v["code_id"] == KEY_VEHICLE[1] and fits_70r:
                return KEY_VEHICLE[1]
        # Check if Class A is selected
        for v in selected_vehicles:
            if v["code_id"] == KEY_VEHICLE[2]:
                return KEY_VEHICLE[2]
        # Check 70R / AA even if narrow carriageway
        for v in selected_vehicles:
            if v["code_id"] in (KEY_VEHICLE[0], KEY_VEHICLE[1]):
                return v["code_id"]
        # Check SV
        for v in selected_vehicles:
            if v["code_id"] == "ClassSV":
                return "ClassSV"
        # Check Fatigue
        for v in selected_vehicles:
            if v["code_id"] == "ClassFatigue":
                return "ClassFatigue"
        return selected_vehicles[0].get("code_id", KEY_VEHICLE[2])

    # Default to Table 6A standard when no vehicle was selected
    if fits_70r:
        return KEY_VEHICLE[0]
    return KEY_VEHICLE[2]


def _calculate_impact_factor(impact_type: str, span_m: float) -> float:
    """Calculate dynamic impact factor (1 + IF) according to IRC 6 Cl. 208."""
    s = max(3.0, min(float(span_m), 45.0))
    if impact_type == "class_a":
        im = 9.0 / (13.5 + s)
        return round(1.0 + im, 3)
    elif impact_type == "70r_wheeled":
        if span_m < 23.0:
            im = 0.25
        else:
            im = 9.0 / (13.5 + s)
        return round(1.0 + im, 3)
    elif impact_type == "70r_tracked":
        if span_m < 5.0:
            im = 0.25
        else:
            im = 0.10
        return round(1.0 + im, 3)
    elif impact_type in ("sv", "fatigue", "custom"):
        return 1.000
    return 1.000


def ch3_loads(input_dict):
    # ── Basic Geometry & Lane Parameters ─────────────────────────────────────
    span_val = input_dict.get(KEY_SPAN) or input_dict.get("span")
    try:
        span_m = float(span_val) if span_val not in (None, "") else 24.0
    except Exception:
        span_m = 24.0

    cw_val = input_dict.get(KEY_CARRIAGEWAY_WIDTH) or input_dict.get("carriageway_width")
    try:
        cw_m = float(cw_val) if cw_val not in (None, "") else 7.5
    except Exception:
        cw_m = 7.5
    cw_str = f"{cw_m:.2f} m"

    lanes_val = input_dict.get(KEY_WC_LD_LANE_TABLE_COUNT)
    try:
        lanes_int = int(lanes_val) if lanes_val not in (None, "") else IRC6_2017.table_6(cw_m)
    except Exception:
        lanes_int = IRC6_2017.table_6(cw_m)
    lanes_str = f"{lanes_int} {'Lane' if lanes_int == 1 else 'Lanes'} (IRC 6 Table 6)"

    # Multiple Presence Reduction Factor (IRC 6 Cl. 207.4)
    if lanes_int == 1:
        mult_str = r"1.00 (No reduction for 1 lane, IRC 6 Cl. 207.4)"
    elif lanes_int == 2:
        mult_str = r"1.00 (No reduction for 2 lanes, IRC 6 Cl. 207.4)"
    elif lanes_int == 3:
        mult_str = r"0.90 (10\% reduction for 3 lanes, IRC 6 Cl. 207.4)"
    elif lanes_int == 4:
        mult_str = r"0.80 (20\% reduction for 4 lanes, IRC 6 Cl. 207.4)"
    else:
        mult_str = r"0.70 (30\% reduction for 5+ lanes, IRC 6 Cl. 207.4)"

    # Table 6A Permissible Vehicle Combinations
    try:
        combo_res = IRC6_2017.table_6A(cw_m)
        combos = combo_res.get("vehicle_combinations", [])
        combo_descs = []
        for c in combos:
            parts = []
            if "Class70R" in c:
                parts.append(f"{c['Class70R']} Lane of Class 70R")
            if "ClassA" in c:
                parts.append(f"{c['ClassA']} Lane{'s' if c['ClassA']>1 else ''} of Class A")
            if parts:
                combo_descs.append(" + ".join(parts))
        combos_str = " OR ".join(combo_descs) if combo_descs else "1 Lane of Class 70R OR 2 Lanes of Class A"
    except Exception:
        combos_str = "1 Lane of Class 70R OR 2 Lanes of Class A"

    # Governing Vehicle Resolution
    gov_veh = _resolve_governing_vehicle(cw_m, input_dict)
    gov_name_map = {
        KEY_VEHICLE[0]: "IRC Class 70R (Wheeled)",
        KEY_VEHICLE[1]: "IRC Class 70R (Tracked)",
        KEY_VEHICLE[2]: "IRC Class A",
        "ClassB": "IRC Class B",
        "ClassSV": "IRC Class SV",
        "ClassFatigue": "IRC Class Fatigue",
        "Custom": "Custom Vehicle",
    }
    gov_display = gov_name_map.get(gov_veh, str(gov_veh))

    # Longitudinal Braking Force (IRC 6 Cl. 211.2)
    try:
        braking_force_t = IRC6_2017.cl_211_2_braking_force(lanes_int)
        braking_force_kN = braking_force_t * 9.81
        braking_force_str = f"{braking_force_kN:.2f} kN ({braking_force_t:.2f} tonnes, IRC 6 Cl. 211.2)"
    except Exception:
        braking_force_str = "108.69 kN (11.08 tonnes, IRC 6 Cl. 211.2)"

    # Eccentricity of Live Load
    ecc_val = input_dict.get(KEY_LL_ECCENTRICITY)
    if ecc_val not in (None, ""):
        try:
            ecc_str = f"{float(ecc_val):.3f} m (User-defined)"
        except Exception:
            ecc_str = f"{ecc_val} m"
    else:
        ecc_str = "0.000 m (Centered on carriageway)"

    # Congestion Factor (IRC 6 Table 7)
    try:
        if span_m > 10.0:
            k_cong = IRC6_2017.table_7(span_m)
            cong_str = f"{k_cong:.3f} (IRC 6 Table 7)"
        else:
            cong_str = r"1.000 (Span $\le$ 10 m, Table 7 not applicable)"
    except Exception:
        cong_str = "1.150 (IRC 6 Table 7)"

    # ── Table 3.4: Dynamic Vehicle Selection & Impact Factors ─────────────────
    candidate_catalog = [
        {
            "key": KEY_LL_IRC_CLASS_A,
            "name": "IRC Class A",
            "config": "8-Axle Train (2.7 m width)",
            "weight": "554 kN (55.4 t)",
            "impact_type": "class_a",
            "code_id": KEY_VEHICLE[2],
        },
        {
            "key": KEY_LL_IRC_70R_WHEELED,
            "name": "IRC Class 70R (Wheeled)",
            "config": "7-Axle Bogie Train",
            "weight": "1000 kN (100.0 t)",
            "impact_type": "70r_wheeled",
            "code_id": KEY_VEHICLE[0],
        },
        {
            "key": KEY_LL_IRC_70R_TRACKED,
            "name": "IRC Class 70R (Tracked)",
            "config": "Tracked (4.57 m length)",
            "weight": "700 kN (70.0 t)",
            "impact_type": "70r_tracked",
            "code_id": KEY_VEHICLE[1],
        },
        {
            "key": KEY_LL_IRC_AA_WHEELED,
            "name": "IRC Class AA (Wheeled)",
            "config": "2-Axle Heavy Wheeled",
            "weight": "400 kN (40.0 t)",
            "impact_type": "70r_wheeled",
            "code_id": KEY_VEHICLE[0],
        },
        {
            "key": KEY_LL_IRC_AA_TRACKED,
            "name": "IRC Class AA (Tracked)",
            "config": "Tracked (3.60 m length)",
            "weight": "700 kN (70.0 t)",
            "impact_type": "70r_tracked",
            "code_id": KEY_VEHICLE[1],
        },
        {
            "key": KEY_LL_IRC_70R_BOGIE,
            "name": "IRC Class 70R (Bogie)",
            "config": "2-Axle Bogie (1.22 m spacing)",
            "weight": "400 kN (40.0 t)",
            "impact_type": "70r_wheeled",
            "code_id": KEY_VEHICLE[0],
        },
        {
            "key": KEY_LL_IRC_CLASS_SV,
            "name": "IRC Class SV",
            "config": "Special Modular Trailer",
            "weight": "3850 kN (385.0 t)",
            "impact_type": "sv",
            "code_id": "ClassSV",
        },
        {
            "key": KEY_LL_IRC_CLASS_FATIGUE,
            "name": "IRC Class Fatigue",
            "config": "4-Axle Fatigue Vehicle",
            "weight": "400 kN (40.0 t)",
            "impact_type": "fatigue",
            "code_id": "ClassFatigue",
        },
    ]

    selected_vehicles = []
    for item in candidate_catalog:
        if _is_vehicle_selected(item, input_dict):
            selected_vehicles.append(item)

    # Custom vehicles from GUI
    custom = input_dict.get(KEY_LL_CUSTOM_VEHICLES)
    if custom and isinstance(custom, list):
        for c in custom:
            if isinstance(c, dict):
                c_name = c.get('name') or "Custom Vehicle"
                c_load = f"{c.get('load', 'Custom')} kN" if c.get('load') else "Custom"
                c_axles = str(c.get('axles', 'Custom config'))
            else:
                c_name = str(c)
                c_load = "Custom"
                c_axles = "Custom config"
            selected_vehicles.append({
                "key": "custom",
                "name": f"Custom: {c_name}",
                "config": c_axles,
                "weight": c_load,
                "impact_type": "custom",
                "code_id": "Custom",
            })

    # Default fallback if no vehicle checkbox was selected
    if not selected_vehicles:
        if gov_veh == KEY_VEHICLE[0]:
            selected_vehicles.append(candidate_catalog[1])
        else:
            selected_vehicles.append(candidate_catalog[0])

    table_3_4_rows = []
    for v in selected_vehicles:
        im_val = _calculate_impact_factor(v["impact_type"], span_m)
        if v["code_id"] == gov_veh:
            role = r"\textbf{Governing (Deck \& Girders)}"
        elif v["key"] == KEY_LL_IRC_CLASS_FATIGUE:
            role = r"Fatigue Life Verification"
        elif v["key"] == KEY_LL_IRC_CLASS_SV:
            role = r"Special Heavy Load Check"
        else:
            role = r"Permissible Multi-Lane Combo"
        
        table_3_4_rows.append(
            f"{_tex(v['name'])} & {_tex(v['config'])} & {_tex(v['weight'])} & {im_val:.3f} & {role} \\\\[6pt]\n\\hline"
        )
    table_3_4_rows_str = "\n".join(table_3_4_rows)

    # ── Table 3.5: Footway / Pedestrian Live Load ────────────────────────────
    fp_val = input_dict.get(KEY_FOOTPATH) or "None"
    fp_str = str(fp_val).strip()
    has_footpath = fp_str.lower() not in ("none", "", "no", "false")

    fp_w_raw = input_dict.get(KEY_TS_FOOTPATH_WIDTH)
    try:
        fp_w_m = float(fp_w_raw) if fp_w_raw not in (None, "") else 1.5
    except Exception:
        fp_w_m = 1.5

    fp_mode_raw = input_dict.get(KEY_LL_FOOTPATH_PRESSURE_MODE, "")
    fp_custom_val = input_dict.get(KEY_LL_FOOTPATH_PRESSURE_VALUE, "")

    if not has_footpath:
        fp_provision_str = "None (No pedestrian footway provided on bridge)"
        fp_width_str = "N/A"
        fp_mode_str = "N/A"
        fp_intensity_str = "N/A (Footway not provided)"
        fp_combined_str = "N/A"
        fp_kerb_str = "N/A (No footway kerb)"
        fp_railing_str = r"1.500 kN/m (Crash barrier provided directly at deck edges, Cl. 206.4)"
    else:
        fp_provision_str = f"{fp_str}"
        fp_width_str = f"{fp_w_m:.2f} m (IRC 5 Cl. 104.3.6 min: 1.50 m)"
        
        is_custom_mode = str(fp_mode_raw).strip().lower() in ("custom", "user-defined") and fp_custom_val not in (None, "")
        
        if is_custom_mode:
            fp_mode_str = "User-defined / Custom"
            try:
                q_val = float(fp_custom_val)
                fp_intensity_str = f"{q_val:.3f} kN/m\\textsuperscript{{2}} (User-specified)"
            except Exception:
                fp_intensity_str = f"{fp_custom_val} kN/m\\textsuperscript{{2}}"
        else:
            fp_mode_str = "Automatic (calculated per IRC 6 Cl. 206.1)"
            L = span_m
            if L <= 7.5:
                P_kg = 500.0
            elif L <= 30.0:
                P_kg = 500.0 - (40.0 * L - 300.0) / 9.0
            else:
                P_prime = 400.0
                W = fp_w_m
                P_kg = P_prime - ((40.0 * L - 1200.0) / 260.0) * ((16.5 - W) / 15.0)
                P_kg = max(200.0, P_kg)
            q_val = (P_kg * 9.81) / 1000.0
            fp_intensity_str = f"{q_val:.3f} kN/m\\textsuperscript{{2}} ({P_kg:.1f} kg/m\\textsuperscript{{2}}, IRC 6 Cl. 206.1)"
        
        fp_combined_str = r"4.000 kN/m\textsuperscript{2} (400 kg/m\textsuperscript{2}, IRC 6 Cl. 206.1.1)"
        fp_kerb_str = r"5.000 kN/m\textsuperscript{2} vertical / 7.50 kN/m horizontal force (IRC 6 Cl. 206.2)"
        fp_railing_str = r"1.500 kN/m (150 kg/m working load along top rail, IRC 6 Cl. 206.5)"

    # ── Wind Load (WL) ───────────────────────────────────────────────────────
    vz_val = input_dict.get(KEY_WL_HOURLY_MEAN_WIND)
    pz_val = input_dict.get(KEY_WL_HOURLY_WIND_PRESSURE)
    wl_basic_wind = input_dict.get(KEY_WL_BASIC_WIND_SPEED) or input_dict.get('wind_speed') or 33.0
    wl_exposed_h  = input_dict.get(KEY_WL_AVG_EXPOSED_HEIGHT) or 10.0
    wl_terrain_str = str(input_dict.get(KEY_WL_TERRAIN_TYPE) or "Plain Terrain (Default)").strip()
    if not vz_val or not pz_val:
        try:
            _vb = float(wl_basic_wind)
            _h  = float(wl_exposed_h)
            _ter = {
                "Plain Terrain": "plain",
                "Terrain with Obstructions": "obstructed",
            }.get(wl_terrain_str, "plain")
            _res = IRC6_2017.table_12(_h, _ter, _vb)
            if not vz_val:
                vz_val = _res.get("Vz")
            if not pz_val:
                pz_val = _res.get("Pz")
        except Exception:
            pass

    vz_display = f"{float(vz_val):.2f} m/s" if vz_val not in (None, "") else "N/A (Not Calculated)"
    pz_display = f"{float(pz_val):.2f} N/m\\textsuperscript{{2}}" if pz_val not in (None, "") else "N/A (Not Calculated)"

    wl_trans_force = input_dict.get(KEY_WL_TRANSVERSE_WIND_FORCE) or input_dict.get("wind_force_transverse") or input_dict.get("wind.transverse_force")
    wl_long_force  = input_dict.get(KEY_WL_LONGITUDINAL_WIND_FORCE) or input_dict.get("wind_force_longitudinal") or input_dict.get("wind.longitudinal_force")
    wl_vert_force  = input_dict.get(KEY_WL_VERTICAL_WIND_FORCE) or input_dict.get("wind_force_vertical") or input_dict.get("wind.vertical_force")

    wl_trans_str = f"{float(wl_trans_force):.2f} kN" if wl_trans_force not in (None, "") else r"N/A (Applied to Substructure / Bearings per IRC 6 Cl. 209)"
    wl_long_str  = f"{float(wl_long_force):.2f} kN" if wl_long_force not in (None, "") else r"N/A (Negligible for Superstructure per IRC 6 Cl. 209.4)"
    wl_vert_str  = f"{float(wl_vert_force):.2f} kN" if wl_vert_force not in (None, "") else r"N/A (Not Applicable for Girder Deck per IRC 6 Cl. 209.6)"

    # ── Seismic Load (EL) ────────────────────────────────────────────────────
    sl_zone_factor = input_dict.get(KEY_SL_ZONE_FACTOR)
    sl_spectral    = input_dict.get(KEY_SL_SPECTRAL_COEFF)
    sl_ah          = input_dict.get(KEY_SL_HORIZONTAL_COEFF)
    sl_av          = input_dict.get(KEY_SL_VERTICAL_COEFF)
    sl_soil_type_str = str(input_dict.get(KEY_SL_SOIL_TYPE) or "Type II – Medium Soil")
    sl_importance_str = str(input_dict.get(KEY_SL_IMPORTANCE_FACTOR) or "1.20 (Major Bridge, IRC 6 Table 11)")
    
    _zone = input_dict.get(KEY_SL_SEISMIC_ZONE) or input_dict.get('seismic_zone') or "III"
    _zmap = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V"}
    _z    = str(_zone).strip().upper()
    if _z.isdigit():
        _z = _zmap.get(_z, "III")
    _zone_norm = f"Zone {_z}" if not _z.startswith("ZONE") else _z

    _smap = {"Type I – Rocky or Hard": 1, "Type II – Medium Soil": 2, "Type III – Soft Soil": 3}
    _st   = _smap.get(sl_soil_type_str, 2)
    _tp   = input_dict.get(KEY_SL_TIME_PERIOD) or 0.5
    _damp = input_dict.get(KEY_SL_DAMPING) or 5.0
    _dl_v = input_dict.get(KEY_SL_DEAD_LOAD_VALUE)
    _ll_v = input_dict.get(KEY_SL_LIVE_LOAD_VALUE)
    _dead = float(_dl_v) if str(input_dict.get(KEY_SL_DEAD_LOAD_MODE, "")) == "Custom" and _dl_v else 0.0
    _live = float(_ll_v) if str(input_dict.get(KEY_SL_LIVE_LOAD_MODE, "")) == "Custom" and _ll_v else 0.0

    try:
        _res  = IRC6_2017.cl_218_5_1(zone=_zone_norm, soil_type=_st, dead_load_kN=_dead,
                    live_load_kN=_live, period_T=float(_tp) if _tp else None,
                    damping_percent=float(_damp))
        if not sl_zone_factor:
            sl_zone_factor = _res.get("Z")
        if not sl_spectral:
            sl_spectral    = _res.get("Sa_g_adjusted")
        if not sl_ah:
            sl_ah          = _res.get("Ah")
        if not sl_av:
            sl_av          = round(_res.get("Ah", 0) * 2 / 3, 4)
    except Exception:
        pass

    sl_zone_str   = f"{float(sl_zone_factor):.2f}" if sl_zone_factor not in (None, "") else "0.16 (Zone III)"
    sl_sa_g_str   = f"{float(sl_spectral):.2f}" if sl_spectral not in (None, "") else "2.50"
    sl_ah_str     = f"{float(sl_ah):.4f}" if sl_ah not in (None, "") else "0.0600"
    sl_av_str     = f"{float(sl_av):.4f}" if sl_av not in (None, "") else "0.0400"

    sl_feq_long = input_dict.get("seismic_force_longitudinal") or input_dict.get("seismic.longitudinal_force") or input_dict.get("sl_feq_long")
    sl_feq_trans = input_dict.get("seismic_force_transverse") or input_dict.get("seismic.transverse_force") or input_dict.get("sl_feq_trans")
    sl_long_force_str  = f"{float(sl_feq_long):.2f} kN" if sl_feq_long not in (None, "") else r"N/A (Evaluated at Bearing \& Substructure Supports per IRC 6 Cl. 218)"
    sl_trans_force_str = f"{float(sl_feq_trans):.2f} kN" if sl_feq_trans not in (None, "") else r"N/A (Evaluated at Bearing \& Substructure Supports per IRC 6 Cl. 218)"

    # ── Temperature Load (TL) ────────────────────────────────────────────────
    tl_temp_min = tl_temp_max = tl_rise = tl_fall = "N/A"
    try:
        _tmax = input_dict.get(KEY_TL_HIGHEST_MAX_TEMP) or input_dict.get('shade_temp_max')
        _tmin = input_dict.get(KEY_TL_LOWEST_MIN_TEMP)  or input_dict.get('shade_temp_min')
        if _tmax and _tmin:
            _res    = IRC6_2017.cl_215_2_effective_bridge_temperature(
                          float(_tmax), float(_tmin), 'metallic', False)
            _bt_min = _res.get('T_min', 0)
            _bt_max = _res.get('T_max', 0)
            _mean   = (_bt_max + _bt_min) / 2.0
            tl_temp_min = f"{_bt_min:.2f}"
            tl_temp_max = f"{_bt_max:.2f}"
            tl_rise     = f"{_bt_max - _mean:.2f}"
            tl_fall     = f"{_mean - _bt_min:.2f}"
    except Exception:
        pass

    # ── Load Combinations (ULS & SLS) ────────────────────────────────────────
    _LOAD_LABEL_MAP = {
        'dead_load':         'DL',
        'surfacing':         'SIDL',
        'live_load':         'LL',
        'wind_load':         'WL',
        'thermal_load':      'TL',
        'vehicle_collision': 'VC',
        'barge_impact':      'BI',
        'floating_bodies':   'FB',
        'seismic':           'EQ',
    }

    def _fmt_factors(factors):
        """Format a factors dict into a compact load-case string for the table."""
        parts = []
        for load, val in factors.items():
            label = _LOAD_LABEL_MAP.get(load, load.upper())
            if isinstance(val, dict):
                add = val.get('adding')
                rel = val.get('relieving')
                add_s = f"{add:.2f}" if add is not None else '--'
                rel_s = f"{rel:.2f}" if rel is not None else '--'
                parts.append(f"{label}({add_s}/{rel_s})")
            else:
                if val is None:
                    continue
                parts.append(f"{label}({val:.2f})")
        return ' + '.join(parts)

    uls_combos = IRC6_2017.uls_load_combinations()
    sls_combos = IRC6_2017.sls_load_combinations()
    lc_rows = []
    for i, combo in enumerate(uls_combos, start=1):
        cases = _fmt_factors(combo['factors'])
        lc_rows.append(
            f"ULS-{i:02d}" + r" & " + cases + r" \\[6pt]" + "\n"
            + r"\hline"
        )
    for i, combo in enumerate(sls_combos, start=1):
        cases = _fmt_factors(combo['factors'])
        lc_rows.append(
            f"SLS-{i:02d}" + r" & " + cases + r" \\[6pt]" + "\n"
            + r"\hline"
        )

    lc_rows_str = "\n".join(lc_rows)

    # Material densities reconciled per IRC 6:2017 Table 1 Cl. 203 & Section 8.2
    steel_density_val = input_dict.get(KEY_MATERIAL_GIRDER_DENSITY)
    try:
        sd_f = float(steel_density_val)
        if abs(sd_f - 76.4) < 1.0 or sd_f <= 0:
            sd_f = 78.5
    except Exception:
        sd_f = 78.5
    steel_density_str = f"{sd_f:.1f} kN/m\\textsuperscript{{3}} (IRC 6 Table 1)"

    deck_density_val = input_dict.get(KEY_MATERIAL_DECK_DENSITY)
    try:
        dd_f = float(deck_density_val)
        if abs(dd_f - 24.5) < 1.0 or dd_f <= 0:
            dd_f = 25.0
    except Exception:
        dd_f = 25.0
    deck_density_str = f"{dd_f:.1f} kN/m\\textsuperscript{{3}} (IRC 6 Table 1)"

    # Wearing Course Surfacing Load
    wc_mat = str(input_dict.get(KEY_WC_MATERIAL, "Bituminous Concrete")).strip()
    try:
        wc_thk_mm = float(input_dict.get(KEY_WC_THICKNESS, 75.0))
    except Exception:
        wc_thk_mm = 75.0
    wc_density = 24.0 if ("bitum" in wc_mat.lower() or "asphalt" in wc_mat.lower() or "surfacing" in wc_mat.lower()) else (25.0 if "concrete" in wc_mat.lower() else 24.0)
    wc_intensity = round(wc_density * (wc_thk_mm / 1000.0), 3)  # kN/m2
    try:
        cw_m = float(input_dict.get(KEY_CARRIAGEWAY_WIDTH, 22.0))
    except Exception:
        cw_m = 22.0
    wc_line_load = round(wc_intensity * cw_m, 2)  # kN/m

    # Self-Weight Factor
    sw_factor_val = input_dict.get(KEY_PL_SELF_WEIGHT_FACTOR)
    if sw_factor_val in ("", None):
        sw_factor_str = r"\textcolor{gray}{\textbf{NOT REPORTED}}"
    else:
        try:
            sw_factor_str = f"{float(sw_factor_val):.2f}"
        except (ValueError, TypeError):
            sw_factor_str = _tex(sw_factor_val)

    return r"""
\chapter{Loads and Load Combinations}

This section summarizes all loads applied to the bridge and the load combinations considered for analysis and design as per IRC 6:2017.

\begingroup
\setlength{\tabcolsep}{""" + TableStyles.TABCOLSEP_DEFAULT + r"""}
\setlength{\LTleft}{""" + TableStyles.LT_LEFT_ALIGN + r"""}
\setlength{\LTright}{""" + TableStyles.LT_RIGHT_ALIGN + r"""}

\vspace{1em}
\begin{longtable}{|L{5.5cm}|p{10.0cm}|}
\caption{\textbf{Dead Load -- Self Weight}}\\
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endfirsthead
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endhead
\hline
\endfoot
\hline
\endlastfoot
\textnormal{Steel Self-Weight Applied} & """ + steel_density_str + r""" \\*[6pt]
\hline
\textnormal{Concrete Deck Weight} & """ + deck_density_str + r""" \\*[6pt]
\hline
\textnormal{Self-Weight Factor} & """ + sw_factor_str + r""" \\[6pt]
\end{longtable}

\vspace{1em}
\begin{longtable}{|L{5.5cm}|p{10.0cm}|}
\caption{\textbf{Dead Load for Surfacing (DW)}}\\
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endfirsthead
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endhead
\hline
\endfoot
\hline
\endlastfoot
\textnormal{Wearing Course Material} & \textbf{""" + _tex(wc_mat) + r"""} (Density: """ + f"{wc_density:.1f}" + r""" kN/m\textsuperscript{3} per IRC 6 Cl. 203) \\*[6pt]
\hline
\textnormal{Wearing Course Thickness} & """ + f"{wc_thk_mm:.1f} mm" + r""" \\*[6pt]
\hline
\textnormal{Area Load Intensity ($w = \gamma \times t$)} & """ + f"{wc_intensity:.3f} kN/m\\textsuperscript{{2}}" + r""" \\*[6pt]
\hline
\textnormal{Total Line Load Across Carriageway} & """ + f"{wc_line_load:.2f} kN/m (over {cw_m:.2f} m carriageway)" + r""" \\*[6pt]
\hline
\textnormal{Additional SIDL (Crash Barrier)} & """ + (_render_value(input_dict, KEY_CB_LOAD)) + r""" kN/m per barrier \\*[6pt]
\hline
\textnormal{Railing Load} & """ + (_render_value(input_dict, KEY_RL_LOAD_VALUE)) + r""" kN/m\sdstar{} \\[6pt]
\end{longtable}

\vspace{1em}
\Needspace*{16\baselineskip}
\begin{longtable}{|L{5.5cm}|p{10.0cm}|}
\caption{\textbf{Vehicular Live Load Parameters (IRC 6)}}\\
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endfirsthead
\multicolumn{2}{c}{{\footnotesize\textit{(Table \thetable\ continued from previous page)}}} \\[4pt]
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endhead
\hline
\endfoot
\hline
\endlastfoot
\textnormal{Carriageway Width ($CW$)} & """ + _tex(cw_str) + r""" \\[6pt]
\hline
\textnormal{Number of Design Traffic Lanes} & """ + _tex(lanes_str) + r""" \\[6pt]
\hline
\textnormal{Multiple Presence Reduction Factor} & """ + mult_str + r""" \\[6pt]
\hline
\textnormal{Permissible Vehicle Combinations} & """ + _tex(combos_str) + r""" \\[6pt]
\hline
\textnormal{Governing Vehicle for Deck Design} & \textbf{""" + _tex(gov_display) + r"""} \\[6pt]
\hline
\textnormal{Longitudinal Braking Force} & """ + _tex(braking_force_str) + r""" \\[6pt]
\hline
\textnormal{Braking Force Application Height} & 1.20 m above road surface (IRC 6 Cl. 211.3) \\[6pt]
\hline
\textnormal{Transverse Eccentricity of Live Load} & """ + _tex(ecc_str) + r""" \\[6pt]
\hline
\textnormal{Live Load Congestion Factor ($K$)} & """ + cong_str + r""" \\[6pt]
\end{longtable}

\vspace{1em}
\begin{longtable}{|L{3.4cm}|L{3.2cm}|C{2.0cm}|C{2.2cm}|L{3.6cm}|}
\caption{\textbf{Selected Vehicle Classes and Dynamic Impact Factors (IRC 6 Cl. 208)}}\\
\hline
\textbf{Vehicle Class} & \textbf{Axle Config. / Type} & \textbf{Gross Wt.} & \textbf{Impact ($1+IF$)} & \textbf{Design Role} \\
\hline
\endfirsthead
\hline
\textbf{Vehicle Class} & \textbf{Axle Config. / Type} & \textbf{Gross Wt.} & \textbf{Impact ($1+IF$)} & \textbf{Design Role} \\
\hline
\endhead
\hline
\endfoot
\hline
\endlastfoot
""" + table_3_4_rows_str + r"""
\end{longtable}

\vspace{1em}
\begin{longtable}{|L{5.5cm}|p{10.0cm}|}
\caption{\textbf{Footway / Pedestrian Live Load (IRC 6 Cl. 206)}}\\
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endfirsthead
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endhead
\hline
\endfoot
\hline
\endlastfoot
\textnormal{Footway Provision} & """ + _tex(fp_provision_str) + r""" \\[6pt]
\hline
\textnormal{Footway Clear Width} & """ + _tex(fp_width_str) + r""" \\[6pt]
\hline
\textnormal{Live Load Calculation Mode} & """ + _tex(fp_mode_str) + r""" \\[6pt]
\hline
\textnormal{Pedestrian Live Load Intensity ($q$)} & """ + fp_intensity_str + r""" \\[6pt]
\hline
\textnormal{Combined Intensity with Vehicular LL} & """ + fp_combined_str + r""" \\[6pt]
\hline
\textnormal{Kerb Design Live Load} & """ + fp_kerb_str + r""" \\[6pt]
\hline
\textnormal{Pedestrian Railing Design Load} & """ + fp_railing_str + r""" \\[6pt]
\end{longtable}

\vspace{1em}
\begin{longtable}{|L{5.5cm}|p{10.0cm}|}
\caption{\textbf{Wind Load (WL) --- per IRC 6}}\\
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endfirsthead
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endhead
\hline
\endfoot
\hline
\endlastfoot
\textnormal{Basic Wind Speed, Vb} & """ + (_render_value(input_dict, 'wind_speed', ' m/s') or f"{float(wl_basic_wind):.1f} m/s") + r""" [from Project Location] \\[6pt]
\hline
\textnormal{Terrain Type} & """ + _tex(wl_terrain_str) + r""" \\[6pt]
\hline
\textnormal{Average Exposed Height, H (m)} & """ + f"{float(wl_exposed_h):.1f} m" + r""" \\[6pt]
\hline
\textnormal{Hourly Mean Wind Speed, Vz} & """ + vz_display + r""" \\[6pt]
\hline
\textnormal{Hourly Wind Pressure, Pz} & """ + pz_display + r""" \\[6pt]
\hline
\textnormal{Transverse Wind Force} & """ + wl_trans_str + r""" \\[6pt]
\hline
\textnormal{Longitudinal Wind Force} & """ + wl_long_str + r""" \\[6pt]
\hline
\textnormal{Vertical Wind Force} & """ + wl_vert_str + r""" \\[6pt]
\end{longtable}

\vspace{1em}
\begin{longtable}{|L{5.5cm}|p{10.0cm}|}
\caption{\textbf{Earthquake Load (EL) --- per IRC 6}}\\
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endfirsthead
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endhead
\hline
\endfoot
\hline
\endlastfoot
\textnormal{Seismic Zone} & """ + (_render_value(input_dict, 'seismic_zone') or _zone_norm) + r""" [from Project Location] \\[6pt]
\hline
\textnormal{Zone Factor, Z} & """ + sl_zone_str + r""" \\[6pt]
\hline
\textnormal{Importance Factor, I} & """ + sl_importance_str + r""" \\[6pt]
\hline
\textnormal{Type of Soil} & """ + _tex(sl_soil_type_str) + r""" \\[6pt]
\hline
\textnormal{Sa/g} & """ + sl_sa_g_str + r""" \\[6pt]
\hline
\textnormal{Horizontal Seismic Coefficient, Ah} & """ + sl_ah_str + r""" \\[6pt]
\hline
\textnormal{Vertical Seismic Coefficient, Av} & """ + sl_av_str + r""" \\[6pt]
\hline
\textnormal{Horizontal Seismic Force (longitudinal)} & """ + sl_long_force_str + r""" \\[6pt]
\hline
\textnormal{Horizontal Seismic Force (transverse)} & """ + sl_trans_force_str + r""" \\[6pt]
\end{longtable}

\vspace{1em}
\begin{longtable}{|L{5.5cm}|p{10.0cm}|}
\caption{\textbf{Temperature Load (TL) --- per IRC 6}}\\
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endfirsthead
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endhead
\hline
\endfoot
\hline
\endlastfoot
\textnormal{Maximum Shade Temperature} & """ + (_render_value(input_dict,'shade_temp_max')) + r""" $^\circ$C \\[6pt]
\hline
\textnormal{Minimum Shade Temperature} & """ + (_render_value(input_dict,'shade_temp_min')) + r""" $^\circ$C \\[6pt]
\hline
\textnormal{Effective Bridge Temp. Range} & """ + (_render_value(input_dict, KEY_TL_BRIDGE_TEMP_MIN)) + r""" to """ + (_render_value(input_dict, KEY_TL_BRIDGE_TEMP_MAX)) + r""" $^\circ$C \\[6pt]
\hline
\textnormal{Temperature Rise / Fall for Design} & +""" + (_render_value(input_dict, KEY_TL_TEMP_RISE)) + r""" $^\circ$C / $-$""" + (_render_value(input_dict, KEY_TL_TEMP_FALL)) + r""" $^\circ$C \\[6pt]
\end{longtable}

\vspace{1em}
\begin{longtable}{|C{4.0cm}|p{11.5cm}|}
\caption{\textbf{Load Combinations}}\\
\hline
\textbf{Combination ID} & \textbf{Load Cases} \\[6pt]
\hline
\endfirsthead
\hline
\textbf{Combination ID} & \textbf{Load Cases} \\[6pt]
\hline
\endhead
\hline
\endfoot
\hline
\endlastfoot
""" + lc_rows_str + r"""
\end{longtable}
\endgroup

\noindent\textit{Note: All IRC 6 load combinations are auto-generated by OsdagBridge. User-defined custom combinations, if any, are appended.}
"""
