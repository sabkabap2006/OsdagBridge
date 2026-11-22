import os
import re
import shutil
import tempfile
import unittest

from osdagbridge.core.reports.styles import (
    Colors,
    TableStyles,
    Typography,
    GEOMETRY_OPTIONS,
    format_status_latex,
    format_ur_latex,
    format_dim_mm,
    format_length_m,
    format_length_mm,
    get_latex_color_definitions,
    table_setup_latex,
    get_geometry_latex,
    render_pylatex_figure,
    PYLATEX_AVAILABLE,
)


class TestStyles(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_styles_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_colors_hex_validity(self):
        hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
        color_attrs = [
            "OSDAG_GREEN", "OSDAG_BLUE", "NAVY_DARK",
            "PASS_GREEN", "WARN_AMBER", "FAIL_RED",
            "STEEL_GIRDER", "STEEL_BRACING", "STEEL_DIAPHRAGM",
            "STEEL_TOTAL", "CONCRETE_SLAB", "REBAR_STEEL",
            "TEXT_DARK", "TEXT_MUTED", "BG_HEADER_GREY"
        ]
        for attr in color_attrs:
            val = getattr(Colors, attr, None)
            self.assertIsNotNone(val, f"Color {attr} missing in Colors")
            self.assertTrue(hex_pattern.match(val), f"Color {attr}={val} is not a valid 6-digit hex code")

    def test_latex_color_definitions(self):
        defs = get_latex_color_definitions()
        self.assertIn(r"\definecolor{osdagGreen}{HTML}{91B014}", defs)
        self.assertIn(r"\definecolor{osdagBlue}{HTML}{1976D2}", defs)
        self.assertIn(r"\definecolor{osdagPass}{HTML}{2E7D32}", defs)
        self.assertIn(r"\definecolor{osdagFail}{HTML}{D32F2F}", defs)

    def test_status_and_ur_formatting(self):
        # Pass tests
        self.assertEqual(format_status_latex("PASS"), r"\textcolor{osdagPass}{\textbf{PASS}}")
        self.assertEqual(format_status_latex(True), r"\textcolor{osdagPass}{\textbf{PASS}}")
        self.assertEqual(format_status_latex("OK"), r"\textcolor{osdagPass}{\textbf{PASS}}")

        # Fail tests
        self.assertEqual(format_status_latex("FAIL"), r"\textcolor{osdagFail}{\textbf{FAIL}}")
        self.assertEqual(format_status_latex(False), r"\textcolor{osdagFail}{\textbf{FAIL}}")

        # Null / empty tests
        self.assertEqual(format_status_latex(None), "---")
        self.assertEqual(format_status_latex("---"), "---")
        self.assertEqual(format_status_latex("N/A"), "---")

        # UR formatting
        self.assertEqual(format_ur_latex(0.72), "0.72")
        self.assertEqual(format_ur_latex(0.92), r"\textcolor{osdagWarn}{\textbf{0.92}}")
        self.assertEqual(format_ur_latex(1.15), r"\textcolor{osdagFail}{\textbf{1.15}}")
        self.assertEqual(format_ur_latex(None), "---")
        self.assertEqual(format_ur_latex("invalid"), "---")

    def test_table_formatting_presets(self):
        default_setup = table_setup_latex("default")
        self.assertIn(r"\setlength{\tabcolsep}{5.0pt}", default_setup)
        self.assertIn(r"\renewcommand{\arraystretch}{1.25}", default_setup)
        self.assertIn(r"\setlength{\extrarowheight}{2.5pt}", default_setup)

        compact_setup = table_setup_latex("compact")
        self.assertIn(r"\setlength{\tabcolsep}{3.5pt}", compact_compact := compact_setup)

        comfort_setup = table_setup_latex("comfort")
        self.assertIn(r"\setlength{\tabcolsep}{6.0pt}", comfort_setup)

    def test_geometry_latex(self):
        geo = get_geometry_latex()
        self.assertIn("a4paper", geo)
        self.assertIn("top=24mm", geo)
        self.assertIn("bottom=32mm", geo)
        self.assertIn("left=20mm", geo)
        self.assertIn("right=20mm", geo)
        self.assertIn("headheight=20pt", geo)
        self.assertIn("headsep=6mm", geo)
        self.assertIn("footskip=15mm", geo)

    def test_render_pylatex_figure(self):
        # Create a dummy image
        img_path = os.path.join(self.tmp_dir, "sample.png")
        with open(img_path, "wb") as f:
            # 1x1 transparent PNG bytes
            f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82")

        fig_tex = render_pylatex_figure(
            img_path,
            caption="Test Caption",
            label="fig:test-label",
            width=r"0.85\textwidth",
            position="H"
        )
        self.assertIn(r"\begin{figure}[H]", fig_tex)
        self.assertIn(r"\includegraphics[width=0.85\textwidth,keepaspectratio]", fig_tex)
        self.assertIn(r"\caption{\textbf{Test Caption}}", fig_tex)
        self.assertIn(r"\label{fig:test-label}", fig_tex)
        self.assertIn(r"\end{figure}", fig_tex)

        # Test starred caption and height options (used by report_utils)
        fig_starred = render_pylatex_figure(
            "assets/plan.png",
            caption="Overview Plan",
            width=r"0.9\textwidth",
            height="7.5cm",
            starred_caption=True
        )
        self.assertIn(r"\begin{figure}[H]", fig_starred)
        self.assertIn(r"\includegraphics[width=0.9\textwidth,height=7.5cm,keepaspectratio]{assets/plan.png}", fig_starred)
        self.assertIn(r"\caption*{\textbf{Overview Plan}}", fig_starred)

    def test_format_status_latex_custom_labels(self):
        res = format_status_latex(False, false_label="Fail (Shear, Flexure)")
        self.assertEqual(res, r"\textcolor{osdagFail}{\textbf{Fail (Shear, Flexure)}}")
        res_pass = format_status_latex(True, true_label="Pass")
        self.assertEqual(res_pass, r"\textcolor{osdagPass}{\textbf{Pass}}")

    def test_end_to_end_latex_compilation(self):
        pdflatex_bin = None
        for cand in ("/Library/TeX/texbin/pdflatex", "/usr/local/bin/pdflatex", shutil.which("pdflatex")):
            if cand and os.path.exists(cand):
                pdflatex_bin = cand
                break
        if not pdflatex_bin:
            self.skipTest("pdflatex binary not found")

        import subprocess

        # Build document using only styles.py declarations
        doc = r"""\documentclass[12pt,a4paper]{report}
""" + get_geometry_latex() + r"""
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{array}
\usepackage{longtable}
\usepackage{float}

""" + get_latex_color_definitions() + r"""
""" + table_setup_latex("compact") + r"""

\newcolumntype{C}[1]{""" + Typography.COL_TYPES["C"] + r"""{#1}}
\newcolumntype{L}[1]{""" + Typography.COL_TYPES["L"] + r"""{#1}}

\begin{document}
\chapter{Testing Centralized Styles}

Status: """ + format_status_latex("PASS") + r""" or """ + format_status_latex("FAIL") + r"""

\begin{longtable}{|C{3cm}|L{6cm}|C{3cm}|}
\hline
\textbf{Check ID} & \textbf{Limit State Description} & \textbf{Status} \\
\hline
\endfirsthead
\hline
\textbf{Check ID} & \textbf{Limit State Description} & \textbf{Status} \\
\hline
\endhead
1 & Plate Girder Flexure & """ + format_status_latex(True) + r""" \\
\hline
2 & Shear Buckling & """ + format_status_latex(False) + r""" \\
\hline
3 & Deflection UR = """ + format_ur_latex(0.68) + r""" & """ + format_status_latex("PASS") + r""" \\
\hline
\end{longtable}

\end{document}
"""
        tex_path = os.path.join(self.tmp_dir, "test_styles_doc.tex")
        with open(tex_path, "w") as f:
            f.write(doc)

        proc = subprocess.run([pdflatex_bin, "-interaction=nonstopmode", "test_styles_doc.tex"],
                              cwd=self.tmp_dir, capture_output=True)
        pdf_path = os.path.join(self.tmp_dir, "test_styles_doc.pdf")
        self.assertTrue(os.path.exists(pdf_path), f"pdflatex compilation failed: {proc.stdout.decode('utf-8', 'ignore')[-1000:]}")
        self.assertGreater(os.path.getsize(pdf_path), 5000)


    def test_vehicle_selection_dynamic(self):
        from osdagbridge.core.reports.chap3 import ch3_loads
        from osdagbridge.core.utils.common import (
            KEY_LL_IRC_CLASS_A, KEY_LL_IRC_70R_WHEELED, KEY_LL_IRC_CLASS_FATIGUE, KEY_SPAN
        )

        # Case 1: Only Class 70R Wheeled selected
        inp1 = {
            KEY_SPAN: "30.0",
            KEY_LL_IRC_CLASS_A: False,
            KEY_LL_IRC_70R_WHEELED: True,
            KEY_LL_IRC_CLASS_FATIGUE: False,
        }
        res1 = ch3_loads(inp1)
        self.assertIn("IRC Class 70R (Wheeled)", res1)
        self.assertNotIn("IRC Class Fatigue", res1)

        # Case 2: Only Fatigue vehicle selected
        inp2 = {
            KEY_SPAN: "30.0",
            KEY_LL_IRC_CLASS_A: False,
            KEY_LL_IRC_70R_WHEELED: False,
            KEY_LL_IRC_CLASS_FATIGUE: True,
        }
        res2 = ch3_loads(inp2)
        self.assertIn("IRC Class Fatigue", res2)
        self.assertNotIn("IRC Class 70R (Wheeled)", res2)

    def test_ur_charts_covers_four_components(self):
        from osdagbridge.core.reports.ur_charts import extract_design_utilization_ratios

        class MockBridge:
            input_dict = {"typical_section.deck_overhang": "1.2"}
            output_dict = {
                "design_results": {
                    "per_girder": {
                        "G1": {
                            "checks": [
                                {"check_id": 1, "demand": 1200.0, "capacity": 2000.0, "dcr": 0.60},
                                {"check_id": 2, "demand": 400.0, "capacity": 800.0, "dcr": 0.50},
                            ]
                        }
                    }
                },
                "deck_design_results": {
                    "ur_bot_uls": 0.75,
                    "ur_top_uls": 0.65,
                },
                "deck_report_values": {},
                "end_diaphragm_design_results": {
                    "G1-G2": {
                        "diagonal": {
                            "compression": {
                                "capacity_kN": 500.0,
                                "efficiency": 0.82,
                                "slenderness": 180.0
                            }
                        }
                    }
                }
            }
            def get_cb_pairs(self):
                return ["G1-G2"]
            def get_cb_capacity(self, pair, member, ft):
                return "600.0"
            def get_cb_efficiency(self, pair, member, ft):
                return "0.78"
            def get_cb_slenderness(self, pair, member):
                return "190.0"

        data = extract_design_utilization_ratios(MockBridge())
        self.assertIn("girders", data)
        self.assertIn("deck", data)
        self.assertIn("bracing", data)
        self.assertIn("end_diaphragm", data)

        components_in_overall = {item["component"] for item in data["overall"]}
        self.assertIn("Plate Girder", components_in_overall)
        self.assertIn("Deck Slab", components_in_overall)
        self.assertIn("Cross Bracing", components_in_overall)
        self.assertIn("End Diaphragm", components_in_overall)

    def test_unit_conversion_helpers(self):
        # format_dim_mm: values in metres (<= 6.0) converted to mm, mm left untouched
        self.assertEqual(format_dim_mm(1.67), "1670")
        self.assertEqual(format_dim_mm("1.67"), "1670")
        self.assertEqual(format_dim_mm(0.01), "10")
        self.assertEqual(format_dim_mm(0.51), "510")
        self.assertEqual(format_dim_mm(0.022), "22")
        self.assertEqual(format_dim_mm(1670), "1670")
        self.assertEqual(format_dim_mm(10), "10")
        self.assertEqual(format_dim_mm(510), "510")
        self.assertEqual(format_dim_mm(22), "22")
        self.assertEqual(format_dim_mm(None), "---")

        # format_length_m
        self.assertEqual(format_length_m(30.0), "30 m")
        self.assertEqual(format_length_m("30.0"), "30 m")
        self.assertEqual(format_length_m(22), "22 m")
        self.assertEqual(format_length_m(2.29), "2.29 m")
        self.assertEqual(format_length_m(None), "---")

        # format_length_mm
        self.assertEqual(format_length_mm(250.0), "250 mm")
        self.assertEqual(format_length_mm(0.25), "250 mm")
        self.assertEqual(format_length_mm(None), "---")

    def test_executive_summary_status_reconciliation(self):
        from osdagbridge.core.reports.executive_summary import executive_summary
        from osdagbridge.core.utils.common import (
            KEY_SPAN, KEY_CARRIAGEWAY_WIDTH, KEY_TS_GIRDER_SPACING, KEY_TS_DECK_THICKNESS,
            KEY_STRUCTURE_TYPE, KEY_TS_NO_OF_GIRDERS
        )

        input_dict = {
            KEY_STRUCTURE_TYPE: "Composite Plate Girder",
            KEY_SPAN: "30.0",
            KEY_CARRIAGEWAY_WIDTH: "22.0",
            KEY_TS_NO_OF_GIRDERS: "4",
            KEY_TS_GIRDER_SPACING: "2.29",
            KEY_TS_DECK_THICKNESS: "250.0",
        }
        output_dict = {
            "design_results": {
                "per_girder": {
                    "G1": {
                        "checks": [
                            {"check_id": 1, "name": "Girder Moment", "dcr": 0.85, "status": "PASS"},
                            {"check_id": 9, "name": "Fatigue Normal Stress", "dcr": 2.26, "status": "FAIL"},
                        ]
                    }
                }
            },
            "deck_design_results": {"ur_bot_uls": 0.72},
            "crossbracing_design_results": {
                "G1-G2": {
                    "diagonal": {
                        "compression": {"raw": {"efficiency": 0.65, "capacity_kN": 500.0, "status": "PASS"}},
                    }
                }
            },
            "end_diaphragm_design_results": {
                "G1-G2": {
                    "diagonal": {
                        "compression": {"raw": {"efficiency": 0.55, "capacity_kN": 600.0, "status": "PASS"}},
                    }
                }
            },
        }

        tex = executive_summary(input_dict, output_dict, {})

        # Units in project overview
        self.assertIn("30 m", tex)
        self.assertIn("22 m", tex)
        self.assertIn("2.29 m", tex)
        self.assertIn("250 mm", tex)

        # Status reconciliation
        self.assertIn("FAIL", tex)
        self.assertIn("Fatigue Normal Stress", tex)
        self.assertIn("2.26", tex)

        # Key outcomes summary: Girder fail, not hardcoded pass!
        self.assertIn("Girder design fail", tex)
        self.assertIn("Deck design pass", tex)
        self.assertIn("Cross bracing design pass", tex)
        self.assertIn("End Diaphragm design pass", tex)


if __name__ == "__main__":
    unittest.main()

