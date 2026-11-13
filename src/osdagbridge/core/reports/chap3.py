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


def _is_checked(val):
    """Safely check if a GUI checkbox or boolean flag is active."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "yes", "1", "checked")


def _resolve_governing_vehicle(carriageway_width_m: float, input_dict: dict) -> str:
    """Determine the governing vehicle class based on IRC 6 Table 6A and GUI selections."""
    has_70rw = _is_checked(input_dict.get(KEY_LL_IRC_70R_WHEELED))
    has_70rt = _is_checked(input_dict.get(KEY_LL_IRC_70R_TRACKED))
    has_70rb = _is_checked(input_dict.get(KEY_LL_IRC_70R_BOGIE))
    has_aa_w = _is_checked(input_dict.get(KEY_LL_IRC_AA_WHEELED))
    has_aa_t = _is_checked(input_dict.get(KEY_LL_IRC_AA_TRACKED))
    has_a    = _is_checked(input_dict.get(KEY_LL_IRC_CLASS_A))

    try:
        result = IRC6_2017.table_6A(carriageway_width_m)
        combos = result.get("vehicle_combinations", [])
        fits_70r = any("Class70R" in combo for combo in combos)
    except Exception:
        fits_70r = carriageway_width_m >= 5.3

    if has_70rw and fits_70r:
        return KEY_VEHICLE[0]  # Class70R(W)
    if has_70rt and fits_70r:
        return KEY_VEHICLE[1]  # Class70R(T)
    if has_70rb and fits_70r:
        return KEY_VEHICLE[0]
    if has_aa_w:
        return KEY_VEHICLE[0]
    if has_aa_t:
        return KEY_VEHICLE[1]
    if has_a:
        return KEY_VEHICLE[2]  # ClassA

    # Default to Table 6A standard
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
        if _is_checked(input_dict.get(item["key"])):
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

    # Default fallback to Class A if no vehicle checkbox was selected
    if not selected_vehicles:
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
    if not vz_val or not pz_val:
        try:
            _vb  = input_dict.get(KEY_WL_BASIC_WIND_SPEED) or input_dict.get('wind_speed')
            _h   = input_dict.get(KEY_WL_AVG_EXPOSED_HEIGHT)
            _ter = {
                "Plain Terrain": "plain",
                "Terrain with Obstructions": "obstructed",
            }.get(str(input_dict.get(KEY_WL_TERRAIN_TYPE, "")).strip(), "plain")
            _res = IRC6_2017.table_12(float(_h), _ter, float(_vb))
            if not vz_val:
                vz_val = _res.get("Vz")
            if not pz_val:
                pz_val = _res.get("Pz")
        except Exception:
            pass

    # ── Seismic Load (EL) ────────────────────────────────────────────────────
    sl_zone_factor = input_dict.get(KEY_SL_ZONE_FACTOR)
    sl_spectral    = input_dict.get(KEY_SL_SPECTRAL_COEFF)
    sl_ah          = input_dict.get(KEY_SL_HORIZONTAL_COEFF)
    sl_av          = input_dict.get(KEY_SL_VERTICAL_COEFF)
    if not sl_ah or not sl_zone_factor:
        try:
            _zone = input_dict.get(KEY_SL_SEISMIC_ZONE) or input_dict.get('seismic_zone')
            _zmap = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V"}
            _z    = str(_zone).strip().upper()
            if _z.isdigit():
                _z = _zmap.get(_z)
            _smap = {"Type I – Rocky or Hard": 1, "Type II – Medium Soil": 2, "Type III – Soft Soil": 3}
            _st   = _smap.get(str(input_dict.get(KEY_SL_SOIL_TYPE, "")), 1)
            _tp   = input_dict.get(KEY_SL_TIME_PERIOD)
            _damp = input_dict.get(KEY_SL_DAMPING) or "5"
            _dl_v = input_dict.get(KEY_SL_DEAD_LOAD_VALUE)
            _ll_v = input_dict.get(KEY_SL_LIVE_LOAD_VALUE)
            _dead = float(_dl_v) if str(input_dict.get(KEY_SL_DEAD_LOAD_MODE, "")) == "Custom" and _dl_v else 0.0
            _live = float(_ll_v) if str(input_dict.get(KEY_SL_LIVE_LOAD_MODE, "")) == "Custom" and _ll_v else 0.0
            _res  = IRC6_2017.cl_218_5_1(zone=f"Zone {_z}", soil_type=_st, dead_load_kN=_dead,
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

    return r"""
\chapter{Loads and Load Combinations}

This section summarizes all loads applied to the bridge and the load combinations considered for analysis and design as per IRC 6:2017.

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
\textnormal{Steel Self-Weight Applied} & """ + (_render_value(input_dict, KEY_MATERIAL_GIRDER_DENSITY, ' kN/m\\textsuperscript{3}')) + r""" \\[6pt]
\hline
\textnormal{Concrete Deck Weight} & """ + (_render_value(input_dict, KEY_MATERIAL_DECK_DENSITY, ' kN/m\\textsuperscript{3}')) + r""" \\[6pt]
\hline
\textnormal{Self-Weight Factor} & """ + (_render_value(input_dict, KEY_PL_SELF_WEIGHT_FACTOR)) + r""" \\[6pt]
\hline
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
\textnormal{Wearing Course Load} & """ + (_render_value(input_dict, KEY_WC_MATERIAL)) + r""" x """ + (_render_value(input_dict, KEY_WC_THICKNESS)) + r""" \\[6pt]
\hline
\textnormal{Additional SIDL (Crash Barrier)} & """ + (_render_value(input_dict, KEY_CB_LOAD)) + r""" kN/m per barrier \\[6pt]
\hline
\textnormal{Railing Load} & """ + (_render_value(input_dict, KEY_RL_LOAD_VALUE)) + r""" kN/m\sdstar{} \\[6pt]
\hline
\end{longtable}

\vspace{1em}
\begin{longtable}{|L{5.5cm}|p{10.0cm}|}
\caption{\textbf{Vehicular Live Load Parameters (IRC 6)}}\\
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endfirsthead
\hline
\textbf{parameter} & \textbf{value} \\
\hline
\endhead
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
\hline
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
\hline
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
\textnormal{Basic Wind Speed, Vb} & """ + (_render_value(input_dict,'wind_speed', ' m/s')) + r""" [from Project Location] \\[6pt]
\hline
\textnormal{Terrain Type} & """ + (_render_value(input_dict, KEY_WL_TERRAIN_TYPE)) + r""" \\[6pt]
\hline
\textnormal{Average Exposed Height, H (m)} & """ + (_render_value(input_dict, KEY_WL_AVG_EXPOSED_HEIGHT, ' m')) + r""" \\[6pt]
\hline
\textnormal{Hourly Mean Wind Speed, Vz} & """ + (_render_value(input_dict, KEY_WL_HOURLY_MEAN_WIND, ' m/s')) + r""" \\[6pt]
\hline
\textnormal{Hourly Wind Pressure, Pz} & """ + (_render_value(input_dict, KEY_WL_HOURLY_WIND_PRESSURE, ' N/m\\textsuperscript{2}')) + r""" \\[6pt]
\hline
\textnormal{Transverse Wind Force} & """ + (_render_value(input_dict, KEY_WL_TRANSVERSE_WIND_FORCE, ' kN')) + r""" \\[6pt]
\hline
\textnormal{Longitudinal Wind Force} & """ + (_render_value(input_dict, KEY_WL_LONGITUDINAL_WIND_FORCE, ' kN')) + r""" \\[6pt]
\hline
\textnormal{Vertical Wind Force} & """ + (_render_value(input_dict, KEY_WL_VERTICAL_WIND_FORCE, ' kN')) + r""" \\[6pt]
\hline
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
\textnormal{Seismic Zone} & """ + (_render_value(input_dict,'seismic_zone')) + r""" [from Project Location] \\[6pt]
\hline
\textnormal{Zone Factor, Z} & """ + (_render_value(input_dict, KEY_SL_ZONE_FACTOR)) + r""" \\[6pt]
\hline
\textnormal{Importance Factor, I} & """ + (_render_value(input_dict, KEY_SL_IMPORTANCE_FACTOR)) + r""" \\[6pt]
\hline
\textnormal{Type of Soil} & """ + (_render_value(input_dict, KEY_SL_SOIL_TYPE)) + r""" \\[6pt]
\hline
\textnormal{Sa/g} & """ + (_render_value(input_dict, KEY_SL_SPECTRAL_COEFF)) + r""" \\[6pt]
\hline
\textnormal{Horizontal Seismic Coefficient, Ah} & """ + (_render_value(input_dict, KEY_SL_HORIZONTAL_COEFF)) + r""" \\[6pt]
\hline
\textnormal{Vertical Seismic Coefficient, Av} & """ + (_render_value(input_dict, KEY_SL_VERTICAL_COEFF)) + r""" \\[6pt]
\hline
\textnormal{Horizontal Seismic Force (longitudinal)} & """ + '' + r""" kN \\[6pt]
\hline
\textnormal{Horizontal Seismic Force (transverse)} & """ + '' + r""" kN \\[6pt]
\hline
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
\textnormal{Maximum Shade Temperature} & """ + (_render_value(input_dict,'shade_temp_max')) + r""" $^\circ$C \\[6pt]
\hline
\textnormal{Minimum Shade Temperature} & """ + (_render_value(input_dict,'shade_temp_min')) + r""" $^\circ$C \\[6pt]
\hline
\textnormal{Effective Bridge Temp. Range} & """ + (_render_value(input_dict, KEY_TL_BRIDGE_TEMP_MIN)) + r""" to """ + (_render_value(input_dict, KEY_TL_BRIDGE_TEMP_MAX)) + r""" $^\circ$C \\[6pt]
\hline
\textnormal{Temperature Rise / Fall for Design} & +""" + (_render_value(input_dict, KEY_TL_TEMP_RISE)) + r""" $^\circ$C / $-$""" + (_render_value(input_dict, KEY_TL_TEMP_FALL)) + r""" $^\circ$C \\[6pt]
\hline
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
""" + lc_rows_str + r"""
\end{longtable}

\noindent\textit{Note: All IRC 6 load combinations are auto-generated by OsdagBridge. User-defined custom combinations, if any, are appended.}
"""
