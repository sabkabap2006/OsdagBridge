import unittest
import tempfile
import os
import sys

_venv_pkgs = os.path.abspath(".venv/lib/python3.9/site-packages")
if _venv_pkgs not in sys.path:
    sys.path.append(_venv_pkgs)

from osdagbridge.core.reports.validator import (
    validate_report_payload,
    validate_latex_source,
    ValidationResult,
)
from osdagbridge.core.reports.report_generator import (
    ReportPayload,
    ReportMetadata,
    ReportOptions,
    ReportDataBridge,
)
from osdagbridge.core.boq.boq_generator import (
    calculate_material_quantities,
    get_angle_section_properties,
    get_angle_section_area_cm2,
)
from osdagbridge.core.utils.common import (
    KEY_SPAN,
    KEY_CARRIAGEWAY_WIDTH,
    KEY_STRUCTURE_TYPE,
    KEY_TS_NO_OF_GIRDERS,
    KEY_TS_GIRDER_SPACING,
    KEY_TS_DECK_THICKNESS,
    KEY_TS_DECK_OVERHANG,
    KEY_TS_OVERALL_WIDTH,
    KEY_FOOTPATH,
    KEY_WC_MATERIAL,
    KEY_WC_THICKNESS,
    KEY_CB_TYPE,
    KEY_CB_LOAD,
    KEY_MP_GD_SELECT_GIRDER,
    KEY_MP_GD_MEMBER_ID,
    KEY_MP_ED_TYPE,
    KEY_SD_SECTION_DESIGNATION,
    KEY_SD_DEFL_LIVE,
    KEY_SD_DEFL_TOTAL,
    KEY_MATERIAL_GIRDER_DENSITY,
    KEY_MATERIAL_DECK_DENSITY,
)


class TestReportPipeline(unittest.TestCase):
    def setUp(self):
        self.metadata = ReportMetadata(
            project_name="Unit Test Bridge",
            project_location="Test City",
            designer="Test Engineer",
            client="Test Client",
            company="Test Company",
            job_number="TEST-001",
            report_date="2026-11-21",
        )
        self.options = ReportOptions()

    def test_angle_section_properties_resolution(self):
        # ISA 100x100x10 -> Area = 19.1 cm2, rvmin = 1.97 cm
        a1, r1 = get_angle_section_properties("ISA 100x100x10")
        self.assertAlmostEqual(a1, 19.1, places=1)
        self.assertAlmostEqual(r1, 1.97, places=1)

        # ISA 110x110x12 -> Area = 25.0 cm2, rvmin = 2.15 cm
        a2, r2 = get_angle_section_properties("ISA 110x110x12")
        self.assertAlmostEqual(a2, 25.0, places=1)
        self.assertAlmostEqual(r2, 2.15, places=1)

    def test_boq_quantities_no_placeholders(self):
        inputs = {
            KEY_SPAN: "30.0",
            KEY_TS_NO_OF_GIRDERS: "4",
            KEY_TS_GIRDER_SPACING: "2.29",
            KEY_TS_DECK_THICKNESS: "250.0",
            "typical_section.overall_bridge_width": "25.0",
            "member_properties.girder_details.section_input.web_depth": "1670.0",
            "member_properties.girder_details.section_input.web_thickness": "10.0",
            "member_properties.girder_details.section_input.top_flange_width": "510.0",
            "member_properties.girder_details.section_input.top_flange_thickness": "22.0",
            "member_properties.girder_details.section_input.bottom_flange_width": "510.0",
            "member_properties.girder_details.section_input.bottom_flange_thickness": "22.0",
            "member_properties.cross_bracing_details.bracing_section_designation": "ISA 100x100x10",
            "member_properties.end_diaphragm_details.bracing_section_designation": "ISA 110x110x12",
            "crash_barrier_wt_total": "37.50",
        }
        outputs = {
            "steeldesign.details.shear.longitudinal_spacing": 125.0,
            "steeldesign.details.shear.studs_per_section": 4,
            "steeldesign.details.shear.diameter": 25.0,
            "steeldesign.details.shear.height": 150.0,
        }
        q = calculate_material_quantities(inputs, outputs)

        # Ensure no placeholder or N.A. in calculated values
        for k, v in q.items():
            self.assertNotIn(r"\placeholder", str(v), f"Unresolved placeholder in {k}: {v}")
            self.assertNotEqual(v, "N.A.", f"N.A. value in {k}")

        self.assertGreater(float(q["steel_girders_wt_total"]), 0.0)
        self.assertGreater(float(q["bracing_top_wt_total"]), 0.0)
        self.assertGreater(float(q["ed_wt_total"]), 0.0)
        self.assertGreater(float(q["concrete_deck_vol_total"]), 0.0)
        self.assertGreater(float(q["rebar_deck_wt_total"]), 0.0)
        self.assertGreater(float(q["shear_studs_wt_total"]), 0.0)

    def test_validator_mandatory_fields(self):
        # Missing mandatory inputs
        payload = ReportPayload(
            metadata=self.metadata,
            options=self.options,
            inputs={},
            output_dict={},
        )
        res = validate_report_payload(payload)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Missing mandatory input field" in e for e in res.errors))

    def test_validator_status_reconciliation(self):
        inputs = {
            KEY_SPAN: "30.0",
            KEY_CARRIAGEWAY_WIDTH: "22.0",
            KEY_STRUCTURE_TYPE: "Composite Plate Girder",
            KEY_TS_NO_OF_GIRDERS: "4",
            KEY_TS_GIRDER_SPACING: "2.29",
            KEY_TS_DECK_THICKNESS: "250.0",
        }
        # Failed check in girder
        output_dict = {
            "design_results": {
                "per_girder": {
                    "G1": {
                        "checks": [
                            {"name": "Girder Moment", "dcr": 0.82, "status": "PASS"},
                            {"name": "Fatigue Normal Stress", "dcr": 2.26, "status": "FAIL"},
                        ]
                    }
                }
            },
            "deck_design_results": {
                "deck_design_check": "PASS",
                "ur_bot_uls": 0.75,
            },
            "crossbracing_design_results": {
                "G1-G2": {
                    "diagonal": {
                        "compression": {"raw": {"efficiency": 0.71, "capacity_kN": 450.0, "slenderness": 143.7, "status": "PASS"}},
                    }
                }
            },
            "end_diaphragm_design_results": {
                "G1-G2": {
                    "diagonal": {
                        "compression": {"efficiency": 0.71, "capacity_kN": 590.0, "slenderness": 131.6, "status": "PASS"},
                    }
                }
            },
            "overall_status": "PASS",  # CONTRADICTION: claiming PASS when girder fatigue fails
        }
        payload = ReportPayload(
            metadata=self.metadata,
            options=self.options,
            inputs=inputs,
            output_dict=output_dict,
        )
        res = validate_report_payload(payload)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("contradicts failed component checks" in e for e in res.errors))

    def test_latex_source_placeholder_detection(self):
        clean_latex = r"\chapter{Test}\section{Data} Value: 42.0 kN"
        res_clean = validate_latex_source(clean_latex)
        self.assertTrue(res_clean.is_valid)

        dirty_latex = r"\chapter{Test} Formula: \placeholder{Area \times Length} and <—>"
        res_dirty = validate_latex_source(dirty_latex)
        self.assertFalse(res_dirty.is_valid)
        self.assertTrue(any(r"\placeholder" in e for e in res_dirty.errors))
        self.assertTrue(any("<—>" in e for e in res_dirty.errors))

    def test_report_data_bridge_crossbracing_and_diaphragms(self):
        inputs = {
            "span": "30.0",
            "typical_section.girder_spacing": "2.29",
            "member_properties.cross_bracing_details.bracing_section_designation": "ISA 100x100x10",
            "member_properties.end_diaphragm_details.bracing_section_designation": "ISA 110x110x12",
        }
        outputs = {
            "crossbracing_forces_dict": {
                "geometry": {"diagonal_length_m": 2.83},
                "pairs": {
                    "G1-G2": {"P_comp_kN": 320.0, "P_tens_kN": 240.0, "connection": "Bolted (3xM20)"}
                }
            },
            "crossbracing_design_results": {
                "G1-G2": {
                    "diagonal": {
                        "compression": {"efficiency": 0.71, "capacity_kN": 450.0, "slenderness": 143.7, "status": "PASS"}
                    }
                }
            },
            "end_diaphragm_forces_dict": {
                "geometry": {"diagonal_length_m": 2.83},
                "pairs": {
                    "G1-G2": {"P_comp_kN": 420.0, "P_tens_kN": 310.0, "connection": "Bolted (4xM20)"}
                }
            },
            "end_diaphragm_design_results": {
                "G1-G2": {
                    "diagonal": {
                        "compression": {"efficiency": 0.71, "capacity_kN": 590.0, "slenderness": 131.6, "status": "PASS"}
                    }
                }
            }
        }
        bridge = ReportDataBridge(outputs, inputs)
        
        # Cross bracing
        self.assertEqual(bridge.get_cb_pairs(), ["G1-G2"])
        force, ftype = bridge.get_cb_governing_force("G1-G2", "diagonal")
        self.assertEqual(force, "320.000")
        self.assertEqual(ftype, "compression")
        self.assertEqual(bridge.get_cb_capacity("G1-G2", "diagonal", "compression"), "450.000")
        self.assertEqual(bridge.get_cb_efficiency("G1-G2", "diagonal", "compression"), "0.710")
        self.assertEqual(bridge.get_cb_slenderness("G1-G2", "diagonal"), "143.7")
        self.assertIn("PASS", bridge.get_cb_status("G1-G2", "diagonal", "compression"))

        # End diaphragm
        self.assertEqual(bridge.get_ed_pairs(), ["G1-G2"])
        ed_force, ed_ftype = bridge.get_ed_governing_force("G1-G2", "diagonal")
        self.assertEqual(ed_force, "420.000")
        self.assertEqual(ed_ftype, "compression")
        self.assertEqual(bridge.get_ed_capacity("G1-G2", "diagonal", "compression"), "590.000")
        self.assertEqual(bridge.get_ed_efficiency("G1-G2", "diagonal", "compression"), "0.710")
        self.assertEqual(bridge.get_ed_slenderness("G1-G2", "diagonal"), "131.6")
        self.assertIn("PASS", bridge.get_ed_status("G1-G2", "diagonal", "compression"))

    def test_intermediate_stiffener_and_table5_checks(self):
        from osdagbridge.core.reports.chap5 import ch5_design_checks
        from osdagbridge.core.utils.common import (
            KEY_MP_STIFFENER_INTERMEDIATE_SPACING,
            KEY_MP_STIFFENER_INTERMEDIATE_THICKNESS,
        )
        inputs = {
            KEY_SPAN: "30.0",
            KEY_TS_NO_OF_GIRDERS: "4",
            f"{KEY_MP_STIFFENER_INTERMEDIATE_SPACING}.G1.M1": "2440",
            f"{KEY_MP_STIFFENER_INTERMEDIATE_SPACING}.G2.M1": "2440",
            f"{KEY_MP_STIFFENER_INTERMEDIATE_SPACING}.G3.M1": "2440",
            f"{KEY_MP_STIFFENER_INTERMEDIATE_SPACING}.G4.M1": "2440",
            f"{KEY_MP_STIFFENER_INTERMEDIATE_THICKNESS}.G1.M1": "12",
        }
        outputs = {
            "design_results": {
                "per_girder": {
                    "G1": {
                        "checks": [
                            {"check_id": 20, "name": "Intermediate Stiffener Spacing", "demand": 250.0, "capacity": 169.03, "dcr": 1.479, "status": "FAIL"},
                            {"check_id": 9, "name": "Fatigue Normal Stress", "demand": 116.0, "capacity": 100.0, "dcr": 1.16, "status": "FAIL"},
                        ]
                    }
                }
            }
        }
        bridge = ReportDataBridge(outputs, inputs)
        tex = ch5_design_checks({}, bridge)
        # Verify 2440 mm spacing is rendered in Table 5.7
        self.assertIn("2440", tex)
        # Verify Intermediate Stiffener is in Table 5.29
        self.assertIn("Girder --- Intermediate Stiffener", tex)
        self.assertIn("1.48", tex)

    def test_girder_stress_check_separation_from_fatigue(self):
        from osdagbridge.core.reports.chap5 import ch5_design_checks
        inputs = {
            KEY_SPAN: "30.0",
            KEY_TS_NO_OF_GIRDERS: "4",
        }
        outputs = {
            "design_results": {
                "per_girder": {
                    "G1": {
                        "checks": [
                            {"check_id": 9, "name": "Fatigue Normal Stress", "demand": 116.0, "capacity": 100.0, "dcr": 1.16, "status": "FAIL"},
                            {"check_id": 11, "name": "Girder Stress", "demand": 210.0, "capacity": 280.0, "dcr": 0.75, "status": "PASS"},
                        ]
                    }
                }
            }
        }
        bridge = ReportDataBridge(outputs, inputs)
        tex = ch5_design_checks({}, bridge)
        # Table 5.11 (Girder Stress) should show 210.00 MPa demand and 280.00 MPa capacity with PASS
        self.assertIn("210.00 MPa", tex)
        self.assertIn("280.00 MPa", tex)
        # Fatigue table should report 116.00 and 100.00
        self.assertIn("116", tex)
        self.assertIn("100", tex)

    def test_table_529_all_components_and_cover_status(self):
        from osdagbridge.core.reports.chap5 import ch5_design_checks
        from osdagbridge.core.utils.common import (
            KEY_DS_TOP_CLEAR_COVER,
            KEY_DS_BOTTOM_CLEAR_COVER,
            KEY_DD_COVER_OK,
            KEY_DD_MIN_COVER,
        )
        inputs = {
            KEY_SPAN: "30.0",
            KEY_TS_NO_OF_GIRDERS: "4",
            KEY_DS_TOP_CLEAR_COVER: "40.0",
            KEY_DS_BOTTOM_CLEAR_COVER: "40.0",
        }
        outputs = {
            "deck_report_values": {
                KEY_DD_COVER_OK: False,
                KEY_DD_MIN_COVER: 50.0,
            },
            "design_results": {
                "per_girder": {
                    "G1": {
                        "checks": [
                            {"check_id": 1, "name": "Girder Moment", "demand": 4200.0, "capacity": 5100.0, "dcr": 0.82, "status": "PASS"},
                            {"check_id": 20, "name": "Intermediate Stiffener Outstand Leg ($b_s \\le 14 t_q \\varepsilon$)", "demand": 250.0, "capacity": 169.03, "dcr": 1.479, "status": "FAIL"},
                        ]
                    }
                }
            }
        }
        bridge = ReportDataBridge(outputs, inputs)
        tex = ch5_design_checks({}, bridge)
        # Verify Deck Clear Cover Detailing row is in Table 5.29
        self.assertIn("Deck --- Clear Cover Detailing", tex)
        self.assertIn("50 mm (req)", tex)
        self.assertIn("40 mm (prov)", tex)
        # Verify Intermediate Stiffener Outstand Leg row
        self.assertIn("Intermediate Stiffener Outstand Leg", tex)
        # Verify End Panel Stiffener row
        self.assertIn("Girder --- End Panel Stiffener", tex)

    def test_ur_charts_include_end_diaphragms(self):
        from osdagbridge.core.reports.ur_charts import extract_design_utilization_ratios
        outputs = {
            "end_diaphragm_design_results": {
                "G1-G2": {
                    "diagonal": {
                        "compression": {"efficiency": 0.71, "capacity_kN": 590.0, "slenderness": 131.6, "status": "PASS"},
                        "tension": {"efficiency": 0.38, "capacity_kN": 810.0, "slenderness": 131.6, "status": "PASS"},
                    }
                }
            }
        }
        bridge = ReportDataBridge(outputs, {})
        data = extract_design_utilization_ratios(bridge)
        self.assertTrue(len(data.get("end_diaphragm", [])) > 0)
        self.assertTrue(any(c.get("component") == "End Diaphragm" for c in data.get("overall", [])))

    def test_ch3_wind_seismic_and_table33_cleanliness(self):
        from osdagbridge.core.reports.chap3 import ch3_loads
        inputs = {
            KEY_SPAN: "30.0",
            KEY_CARRIAGEWAY_WIDTH: "22.0",
            "wind_speed": "44.0",
            "seismic_zone": "III",
        }
        tex = ch3_loads(inputs)
        # Verify no empty cells for wind forces or seismic forces
        self.assertIn("Applied to Substructure / Bearings per IRC 6 Cl. 209", tex)
        self.assertIn("Negligible for Superstructure per IRC 6 Cl. 209.4", tex)
        self.assertIn("Evaluated at Bearing", tex)
        self.assertIn(r"\Needspace*{16\baselineskip}", tex)
        self.assertIn("Table \\thetable\\ continued from previous page", tex)

    def test_ch4_reactions_fallback(self):
        from osdagbridge.core.reports.chap4 import ch4_analysis
        asum = {
            "load_cases": {
                "Dead Load (DL)": {"max_bm": 1500.0, "max_sf": 210.0, "bm_girder": "G1", "bm_location": 15.0, "sf_girder": "G1", "sf_location": 0.0}
            },
            "reactions": {}  # empty reactions dict
        }
        bridge = ReportDataBridge({}, {KEY_SPAN: "30.0"})
        tex = ch4_analysis(asum, {}, bridge, 30.0)
        # Verify Table 4.2 has populated values from fallback
        self.assertIn("210.000", tex)
        self.assertNotIn("--- & --- & ---", tex)

    # =========================================================================
    # Report_After(9) Automated Validation Tests (10 Categories)
    # =========================================================================

    def test_1_input_geometry_vs_optimized_geometry_separation(self):
        """Category 1: Input geometry vs optimized geometry inconsistencies."""
        from osdagbridge.core.reports.chap2 import ch2_input_parameters
        inputs = {
            KEY_SPAN: "30.0",
            KEY_CARRIAGEWAY_WIDTH: "22.0",
            KEY_FOOTPATH: "None",
            KEY_STRUCTURE_TYPE: "Composite Plate Girder",
            KEY_TS_NO_OF_GIRDERS: "10",
            KEY_TS_OVERALL_WIDTH: "22.90",
            KEY_TS_GIRDER_SPACING: "2.29",
            KEY_TS_DECK_OVERHANG: "1.145",
            KEY_TS_DECK_THICKNESS: "250.0",
        }
        tex = ch2_input_parameters(self.metadata, inputs)
        # Table 2.2 must show user input (22.0 m carriageway, None footpath)
        self.assertIn("Carriageway Width (m)} & 22.0 m", tex)
        self.assertIn("Footpath} & None", tex)
        # Section 2.2 / Table 2.3 must document 10-girder optimized arrangement
        self.assertIn("Superstructure Geometry and Optimization", tex)
        self.assertIn("10-girder", tex)
        self.assertIn("22.90", tex)
        self.assertIn("2.29 m", tex)

    def test_2_girder_count_and_member_id_consistency(self):
        """Category 2: Girder count and member-ID mismatches."""
        from osdagbridge.core.reports.report_utils import get_girder_entries
        inputs = {
            KEY_TS_NO_OF_GIRDERS: "10",
        }
        for i in range(1, 11):
            inputs[f"{KEY_MP_GD_SELECT_GIRDER}.G{i}"] = f"G{i}"
            inputs[f"{KEY_MP_GD_MEMBER_ID}.G{i}.M1"] = f"G{i}M1"
        entries = get_girder_entries(inputs)
        self.assertEqual(len(entries), 10)
        for i, (g_lbl, m_id) in enumerate(entries, start=1):
            self.assertEqual(g_lbl, f"G{i}")
            self.assertEqual(m_id, f"G{i}M1")

    def test_3_material_density_reconciliation(self):
        """Category 3: Material density inconsistencies."""
        from osdagbridge.core.reports.chap3 import ch3_loads
        from osdagbridge.core.utils.common import KEY_MATERIAL_GIRDER_DENSITY, KEY_MATERIAL_DECK_DENSITY
        # When uncalibrated values like 76.4 or 24.5 are passed, they must normalize to code values
        inputs = {
            KEY_SPAN: "30.0",
            KEY_CARRIAGEWAY_WIDTH: "22.0",
            KEY_MATERIAL_GIRDER_DENSITY: "76.4",
            KEY_MATERIAL_DECK_DENSITY: "24.5",
        }
        tex = ch3_loads(inputs)
        self.assertIn("78.5 kN/m", tex)
        self.assertIn("25.0 kN/m", tex)
        self.assertNotIn("76.4 kN/m", tex)
        self.assertNotIn("24.5 kN/m", tex)

    def test_4_wearing_course_load_labelling_and_calculation(self):
        """Category 4: Missing or incorrectly labelled load values."""
        from osdagbridge.core.reports.chap3 import ch3_loads
        inputs = {
            KEY_SPAN: "30.0",
            KEY_CARRIAGEWAY_WIDTH: "22.0",
            KEY_WC_MATERIAL: "Bituminous Concrete",
            KEY_WC_THICKNESS: "75.0",
        }
        tex = ch3_loads(inputs)
        self.assertNotIn("Concrete x 50.0", tex)
        self.assertIn("Bituminous Concrete", tex)
        self.assertIn("75.0 mm", tex)
        self.assertIn("1.800 kN/m", tex)
        self.assertIn("39.60 kN/m", tex)

    def test_5_end_diaphragm_results_presence_and_no_false_pass(self):
        """Category 5: Missing end-diaphragm results."""
        from osdagbridge.core.reports.chap5 import ch5_design_checks
        # Case A: Missing end-diaphragm results -> NOT CALCULATED, never dashes or false PASS
        bridge_empty = ReportDataBridge({}, {KEY_SPAN: "30.0", KEY_TS_NO_OF_GIRDERS: "4"})
        tex_empty = ch5_design_checks({}, bridge_empty)
        self.assertIn("NOT CALCULATED", tex_empty)
        self.assertNotIn("End Diaphragm --- Compression & --- & --- & --- & ---", tex_empty)

        # Case B: Populated end diaphragm results -> genuine checks
        outputs = {
            "end_diaphragm_forces_dict": {
                "geometry": {"diagonal_length_m": 2.83},
                "pairs": {"G1-G2": {"P_comp_kN": 420.0, "P_tens_kN": 310.0}}
            },
            "end_diaphragm_design_results": {
                "G1-G2": {
                    "diagonal": {
                        "compression": {"efficiency": 0.71, "capacity_kN": 590.0, "slenderness": 131.6, "status": "PASS"},
                        "tension": {"efficiency": 0.38, "capacity_kN": 810.0, "slenderness": 131.6, "status": "PASS"},
                    }
                }
            }
        }
        inputs_ed = {
            KEY_SPAN: "30.0",
            KEY_TS_NO_OF_GIRDERS: "4",
            f"{KEY_MP_ED_TYPE}.G1G2.E1M1": "Cross Bracing",
        }
        bridge_pop = ReportDataBridge(outputs, inputs_ed)
        tex_pop = ch5_design_checks({}, bridge_pop)
        self.assertIn("590.000 kN", tex_pop)
        self.assertIn("0.71", tex_pop)

    def test_6_deflection_consistency_and_failure_propagation(self):
        """Category 6: Summary and detailed deflection mismatches."""
        from osdagbridge.core.reports.chap4 import ch4_analysis
        from osdagbridge.core.reports.chap5 import ch5_design_checks
        outputs = {
            KEY_SD_DEFL_LIVE: 30.312,
            KEY_SD_DEFL_TOTAL: 73.826,
            "design_results": {
                "per_girder": {
                    "G1": {
                        "demand": {"delta_live_mm": 30.312, "delta_total_mm": 73.826},
                        "checks": [
                            {"check_id": 13, "name": "Girder Deflection (Live)", "demand": 30.312, "capacity": 37.5, "dcr": 0.81, "status": "PASS"},
                            {"check_id": 14, "name": "Girder Deflection (Total)", "demand": 73.826, "capacity": 50.0, "dcr": 1.48, "status": "FAIL"},
                        ]
                    }
                }
            }
        }
        bridge = ReportDataBridge(outputs, {KEY_SPAN: "30.0", KEY_TS_NO_OF_GIRDERS: "1"})
        tex_ch4 = ch4_analysis({}, {}, bridge, 30.0)
        self.assertIn("30.312 mm", tex_ch4)
        self.assertIn("73.826 mm", tex_ch4)
        self.assertIn("FAIL", tex_ch4)

        tex_ch5 = ch5_design_checks({}, bridge)
        self.assertIn("73.83 mm", tex_ch5)
        self.assertIn("50.00 mm", tex_ch5)
        self.assertIn("1.48", tex_ch5)

    def test_7_fatigue_failure_propagation_to_executive_summary(self):
        """Category 7: Fatigue failures missing from the executive summary."""
        from osdagbridge.core.reports.executive_summary import executive_summary
        outputs = {
            KEY_SD_SECTION_DESIGNATION: "Custom Welded Plate Girder (1670x510)",
            "design_results": {
                "per_girder": {
                    "G1": {
                        "checks": [
                            {"check_id": 1, "name": "Girder Moment", "dcr": 0.82, "status": "PASS"},
                            {"check_id": 9, "name": "Fatigue Normal Stress", "dcr": 2.26, "status": "FAIL"},
                        ]
                    }
                }
            }
        }
        tex_es = executive_summary({KEY_TS_NO_OF_GIRDERS: "1"}, outputs, {})
        self.assertIn("Fatigue Normal Stress", tex_es)
        self.assertIn("2.26", tex_es)
        self.assertIn("FAIL", tex_es)

    def test_8_bom_quantities_and_crash_barrier_nonzero(self):
        """Category 8: BOM quantity errors and zero-quantity components with applied loads."""
        inputs = {
            KEY_SPAN: "30.0",
            KEY_TS_NO_OF_GIRDERS: "10",
            KEY_TS_GIRDER_SPACING: "2.29",
            KEY_TS_DECK_THICKNESS: "250.0",
            "typical_section.overall_bridge_width": "22.90",
            KEY_CB_TYPE: "New Jersey",
            KEY_CB_LOAD: "5.0",
            "member_properties.girder_details.section_properties.area": 0.03914,
            "member_properties.cross_bracing_details.bracing_section_designation": "ISA 100x100x10",
            "member_properties.end_diaphragm_details.bracing_section_designation": "ISA 110x110x12",
        }
        outputs = {
            "steeldesign.details.shear.longitudinal_spacing": 125.0,
            "steeldesign.details.shear.studs_per_section": 4,
            "steeldesign.details.shear.diameter": 25.0,
            "steeldesign.details.shear.height": 150.0,
        }
        q = calculate_material_quantities(inputs, outputs)
        # Crash barrier must be non-zero
        self.assertEqual(q["crash_barrier_qty"], "2")
        self.assertAlmostEqual(float(q["crash_barrier_vol_total"]), 15.0, places=1)
        self.assertAlmostEqual(float(q["crash_barrier_wt_total"]), 37.5, places=1)
        # 10 girders
        self.assertEqual(q["steel_girders_qty"], "10")
        self.assertGreater(float(q["steel_girders_wt_total"]), 50.0)

    def test_9_chart_data_matches_corresponding_tables(self):
        """Category 9: Chart data that differs from the corresponding tables."""
        from osdagbridge.core.reports.ur_charts import extract_design_utilization_ratios
        outputs = {
            "design_results": {
                "per_girder": {
                    "G1": {
                        "checks": [
                            {"check_id": 9, "name": "Girder Fatigue (Normal)", "demand": 226.0, "capacity": 100.0, "dcr": 2.26, "status": "FAIL"},
                            {"check_id": 14, "name": "Girder Deflection (Total)", "demand": 73.826, "capacity": 50.0, "dcr": 1.48, "status": "FAIL"},
                            {"check_id": 20, "name": "Intermediate Stiffener", "demand": 250.0, "capacity": 169.03, "dcr": 1.48, "status": "FAIL"},
                        ]
                    }
                }
            },
            "end_diaphragm_design_results": {
                "G1-G2": {
                    "diagonal": {
                        "compression": {"efficiency": 0.71, "capacity_kN": 590.0, "slenderness": 131.6, "status": "PASS"},
                    }
                }
            }
        }
        bridge = ReportDataBridge(outputs, {})
        data = extract_design_utilization_ratios(bridge)
        overall = data.get("overall", [])
        fatigue_item = next((x for x in overall if "Fatigue" in x["label"]), None)
        self.assertIsNotNone(fatigue_item)
        self.assertAlmostEqual(fatigue_item["ur"], 2.26, places=2)

    def test_10_missing_units_and_malformed_formulas(self):
        """Category 10: Missing units and malformed formulas."""
        tex_file = "Report_Final.tex" if os.path.exists("Report_Final.tex") else "Report_After(9).tex"
        if not os.path.exists(tex_file):
            self.skipTest(f"{tex_file} not present on disk")
        import re
        from osdagbridge.core.reports.validator import validate_latex_source
        with open(tex_file) as f:
            tex = f.read()
        val = validate_latex_source(tex)
        self.assertTrue(val.is_valid, f"Validation failed: {val.errors}")
        placeholders = re.findall(r"\\placeholder\{([^}]+)\}", tex)
        self.assertEqual(len(placeholders), 0, f"Found unresolved placeholders: {placeholders}")
        todo_calls = re.findall(r"\\todo\{([^}]+)\}", tex)
        self.assertEqual(len(todo_calls), 0, f"Found unresolved TODO markers: {todo_calls}")
        self.assertNotIn("<—>", tex)

    def test_deck_clear_cover_contradiction_acknowledged(self):
        """Fix 1: Deck clear cover note acknowledges failure when cover check fails."""
        from osdagbridge.core.reports.chap5 import ch5_design_checks
        from osdagbridge.core.utils.common import (
            KEY_SPAN,
            KEY_TS_NO_OF_GIRDERS,
            KEY_DS_TOP_CLEAR_COVER,
            KEY_DS_BOTTOM_CLEAR_COVER,
            KEY_DD_COVER_OK,
            KEY_DD_MIN_COVER,
        )
        inputs = {
            KEY_SPAN: "30.0",
            KEY_TS_NO_OF_GIRDERS: "4",
            KEY_DS_TOP_CLEAR_COVER: "40.0",
            KEY_DS_BOTTOM_CLEAR_COVER: "40.0",
        }
        outputs_fail = {
            "deck_report_values": {
                KEY_DD_COVER_OK: False,
                KEY_DD_MIN_COVER: 50.0,
            }
        }
        bridge_fail = ReportDataBridge(outputs_fail, inputs)
        tex_fail = ch5_design_checks({}, bridge_fail)
        self.assertIn("clear-cover detailing check FAIL", tex_fail)
        self.assertNotIn("All reinforcement provisions satisfy strength and detailing requirements.", tex_fail)

        # When cover passes, note states all provisions satisfy
        outputs_pass = {
            "deck_report_values": {
                KEY_DD_COVER_OK: True,
                KEY_DD_MIN_COVER: 40.0,
            }
        }
        bridge_pass = ReportDataBridge(outputs_pass, inputs)
        tex_pass = ch5_design_checks({}, bridge_pass)
        self.assertIn("All reinforcement provisions satisfy strength and detailing requirements.", tex_pass)

    def test_self_weight_factor_in_table_31(self):
        """Fix 4: Self-weight factor in Table 3.1 is reported or falls back to NOT REPORTED."""
        from osdagbridge.core.reports.chap3 import ch3_loads
        from osdagbridge.core.utils.common import KEY_PL_SELF_WEIGHT_FACTOR
        tex_sw = ch3_loads({KEY_PL_SELF_WEIGHT_FACTOR: "1.00"})
        self.assertIn("Self-Weight Factor", tex_sw)
        self.assertIn("1.00", tex_sw)

        tex_no_sw = ch3_loads({})
        self.assertIn("Self-Weight Factor", tex_no_sw)
        self.assertIn("NOT REPORTED", tex_no_sw)

    def test_fatigue_safety_factors_reconciled(self):
        """Fix 5: Section 8.2 reports gamma_Mft = 1.25 and gamma_flt = 1.00 without 1.35."""
        from osdagbridge.core.reports.chap8 import ch8_design_log
        tex = ch8_design_log([], {})
        self.assertIn(r"Fatigue material factor ($\gamma_{Mft}$", tex)
        self.assertIn("1.25", tex)
        self.assertIn(r"Fatigue load factor ($\gamma_{flt}$", tex)
        self.assertIn("1.00", tex)
        self.assertNotIn("1.35", tex)

    def test_math_expression_in_executive_summary(self):
        """Fix 6: Math expressions like ($b_s <= 14 t_q epsilon$) are preserved in Executive Summary."""
        from osdagbridge.core.reports.executive_summary import executive_summary
        inputs = {
            KEY_SPAN: "30.0",
            KEY_TS_NO_OF_GIRDERS: "4",
        }
        outputs = {
            "design_results": {
                "per_girder": {
                    "G1": {
                        "checks": [
                            {
                                "check_id": 20,
                                "name": r"Intermediate Stiffener Outstand Leg ($b_s \le 14 t_q \varepsilon$)",
                                "demand": 250.0,
                                "capacity": 169.03,
                                "dcr": 1.479,
                                "status": "FAIL",
                            }
                        ]
                    }
                }
            }
        }
        tex = executive_summary(inputs, outputs, {})
        self.assertIn(r"Intermediate Stiffener Outstand Leg ($b_s \le 14 t_q \varepsilon$)", tex)
        self.assertNotIn(r"\textbackslash{}le", tex)
        self.assertNotIn(r"\textbackslash{}varepsilon", tex)
        self.assertNotIn(r"\{}le", tex)
        self.assertNotIn(r"\{}varepsilon", tex)

    def test_deflection_and_stiffener_in_final_tex(self):
        """Fixes 2 & 3: Deflection (73.826 mm, FAIL) and Stiffener outstand (250 mm vs 169.03 mm, FAIL)."""
        tex_file = "Report_Final.tex" if os.path.exists("Report_Final.tex") else "Report_After(9).tex"
        if not os.path.exists(tex_file):
            self.skipTest(f"{tex_file} not present on disk")
        with open(tex_file) as f:
            tex = f.read()
        self.assertIn("73.826 mm", tex)
        self.assertIn("30.312 mm", tex)
        self.assertIn("250.00 mm", tex)
        self.assertIn("169.03 mm", tex)
        self.assertIn("1.48", tex)

    def test_table1_split_for_10_girders(self):
        """Fix 7: Table 1 for 10 girders is split into Table 1(a) and Table 1(b) without right-edge overflow."""
        from osdagbridge.core.reports.executive_summary import executive_summary
        inputs = {KEY_SPAN: "30.0", KEY_TS_NO_OF_GIRDERS: "10"}
        for i in range(1, 11):
            inputs[f"{KEY_MP_GD_SELECT_GIRDER}.G{i}"] = f"G{i}"
            inputs[f"{KEY_MP_GD_MEMBER_ID}.G{i}.M1"] = f"G{i}M1"
        tex = executive_summary(inputs, {}, {})
        self.assertIn(r"Table 1(a) -- Final Girder Parameters: G1 to G5", tex)
        self.assertIn(r"Table 1(b) -- Final Girder Parameters: G6 to G10", tex)
        self.assertIn(r"\setlength{\tabcolsep}{3pt}", tex)

    def test_table_515_column_mapping_and_statuses(self):
        """Fix 8: Table 5.15 has NOT APPLICABLE for demand/capacity rows and only valid statuses."""
        from osdagbridge.core.reports.chap5 import ch5_design_checks
        from osdagbridge.core.utils.common import KEY_SD_TS_VL, KEY_SD_TS_VRD
        outputs = {
            KEY_SD_TS_VL: 185.0,
            KEY_SD_TS_VRD: 240.0,
            "design_results": {
                KEY_SD_TS_VL: 185.0,
                KEY_SD_TS_VRD: 240.0,
                "transverse_shear_ok": True,
            }
        }
        bridge = ReportDataBridge(outputs, {})
        tex = ch5_design_checks({}, bridge)
        self.assertIn(r"\textnormal{Longitudinal Shear per unit length, $V_L$} & 185.00 kN/m & \textcolor{gray}{\textbf{NOT APPLICABLE}}", tex)
        self.assertIn(r"\textnormal{Transverse Shear Capacity of Slab, $V_{Rd}$} & 240.00 kN/m & \textcolor{gray}{\textbf{NOT APPLICABLE}}", tex)
        self.assertNotIn(r"\text{Applied Shear}", tex)
        self.assertNotIn(r"\text{Slab Resistance}", tex)

    def test_section_catalog_and_preview_widget(self):
        """Fix 4: SectionCatalog and SectionPreviewWidget resolve ISA 100x100x10 and ISA 110x110x12."""
        from PySide6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication([])
        from osdagbridge.desktop.ui.widgets.section_viewer import SectionCatalog, SectionPreviewWidget
        cat = SectionCatalog()
        ang1 = cat.get_angle("ISA 100x100x10")
        self.assertIsNotNone(ang1)
        self.assertEqual(ang1.a, 100.0)
        self.assertEqual(ang1.b, 100.0)
        self.assertEqual(ang1.t, 10.0)

        ang2 = cat.get_angle("ISA 110x110x12")
        self.assertIsNotNone(ang2)
        self.assertEqual(ang2.a, 110.0)
        self.assertEqual(ang2.b, 110.0)
        self.assertEqual(ang2.t, 12.0)

        widget = SectionPreviewWidget()
        widget.set_section("angle", "ISA 100x100x10")
        self.assertIsNotNone(widget._dimension_info)
        self.assertEqual(widget._dimension_info.get("w"), 100.0)
        self.assertEqual(widget._dimension_info.get("t"), 10.0)

    def test_explanatory_notes_for_stiffener_and_precamber(self):
        """Fixes 2 & 9: Explanatory notes under Table 5.7 (stiffener outstand) and Table 4.3 (precamber)."""
        from osdagbridge.core.reports.chap5 import ch5_design_checks
        from osdagbridge.core.reports.chap4 import ch4_analysis
        tex5 = ch5_design_checks({}, ReportDataBridge({}, {}))
        self.assertIn("Intermediate transverse stiffeners are provided at 1500~mm longitudinal spacing", tex5)
        self.assertIn(r"physical stiffener outstand width is $b_s = (b_f - t_w)/2 = 250.00\text{~mm}$", tex5)
        self.assertIn(r"distinct from the longitudinal intermediate stiffener spacing ($c = 1500\text{~mm}$)", tex5)

        tex4 = ch4_analysis({}, {}, ReportDataBridge({}, {}), 30.0)
        self.assertIn("permanent dead load and superimposed dead load deflections are compensated for during steel girder fabrication by providing intentional precamber", tex4)

    def test_deflection_split_in_summary_table_529(self):
        """Issue 1: Deflection result inconsistency resolved with separate Live and Total rows."""
        from osdagbridge.core.reports.chap5 import ch5_design_checks
        outputs = {
            KEY_SD_DEFL_LIVE: 30.312,
            KEY_SD_DEFL_TOTAL: 73.826,
            "design_results": {
                "per_girder": {
                    "G1": {
                        "demand": {"delta_live_mm": 30.312, "delta_total_mm": 73.826},
                        "checks": [
                            {"check_id": 13, "name": "Girder Deflection (Live)", "demand": 30.312, "capacity": 37.5, "dcr": 0.81, "status": "PASS"},
                            {"check_id": 14, "name": "Girder Deflection (Total)", "demand": 73.826, "capacity": 50.0, "dcr": 1.48, "status": "FAIL"},
                        ]
                    }
                }
            }
        }
        inputs = {KEY_SPAN: "30.0"}
        bridge = ReportDataBridge(outputs, inputs)
        tex = ch5_design_checks(inputs, bridge)
        self.assertIn(r"Girder --- Deflection (Live Load)", tex)
        self.assertIn(r"Girder --- Deflection (Total Load)", tex)
        self.assertIn(r"30.31 mm", tex)
        self.assertIn(r"37.50 mm", tex)
        self.assertIn(r"73.83 mm", tex)
        self.assertIn(r"50.00 mm", tex)
        self.assertIn(r"FAIL", tex)

    def test_end_diaphragm_no_hardcoded_dummy_fabrication(self):
        """Issue 2: End diaphragm fallback values eliminated; reports NOT CALCULATED when uncomputed."""
        from osdagbridge.core.reports.chap5 import ch5_design_checks
        from osdagbridge.core.reports.executive_summary import executive_summary
        # Test case: NO end diaphragm design results in output_dict
        outputs = {}
        inputs = {KEY_TS_NO_OF_GIRDERS: "2", KEY_SPAN: "30.0"}
        bridge = ReportDataBridge(outputs, inputs)
        tex5 = ch5_design_checks(inputs, bridge)
        
        # Verify no fabricated values
        self.assertNotIn("520.000", tex5)
        self.assertNotIn("426.400", tex5)
        self.assertNotIn("0.820", tex5)
        self.assertIn(r"\textcolor{gray}{\textbf{NOT CALCULATED}}", tex5)

        # Executive summary Key Outcomes
        tex_exec = executive_summary(inputs, outputs, {})
        self.assertIn(r"End Diaphragm not calculated / not verified", tex_exec)
        self.assertNotIn(r"End Diaphragm design pass", tex_exec)

    def test_fatigue_normal_and_shear_split(self):
        """Issue 3: Fatigue check distinguishes Normal Stress and Shear Stress independently."""
        from osdagbridge.core.reports.chap5 import ch5_design_checks
        from osdagbridge.core.reports.executive_summary import executive_summary
        outputs = {
            "design_results": {
                "per_girder": {
                    "G1": {
                        "checks": [
                            {"check_id": 8, "name": "Fatigue Normal Stress", "demand": 226.0, "capacity": 100.0, "dcr": 2.26, "status": "FAIL"}
                        ]
                    }
                }
            }
        }
        inputs = {KEY_SPAN: "30.0"}
        bridge = ReportDataBridge(outputs, inputs)
        tex5 = ch5_design_checks(inputs, bridge)
        self.assertIn(r"Girder --- Fatigue (Normal Stress, $\Delta\sigma$)", tex5)
        self.assertIn(r"Girder --- Fatigue (Shear Stress, $\Delta\tau$)", tex5)
        # Normal stress fails
        self.assertIn("226.00 MPa", tex5)
        self.assertIn("100.00 MPa", tex5)
        self.assertIn("2.26", tex5)
        # Shear stress is NOT CALCULATED
        self.assertIn(r"Girder --- Fatigue (Shear Stress, $\Delta\tau$) & --- & --- & --- & \textcolor{gray}{\textbf{NOT CALCULATED}}", tex5)

        # Executive summary reports normal stress failure without claiming shear failure
        tex_exec = executive_summary(inputs, outputs, {})
        self.assertIn("Fatigue Normal Stress", tex_exec)
        self.assertNotIn("Fatigue Shear", tex_exec)


if __name__ == "__main__":
    unittest.main()
