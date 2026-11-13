import os
import shutil
import tempfile
import unittest

from osdagbridge.core.boq.boq_generator import calculate_material_quantities
from osdagbridge.core.reports.boq_charts import (
    extract_boq_quantities,
    plot_steel_tonnage_chart,
    plot_concrete_rebar_chart,
    generate_all_boq_charts,
)
from osdagbridge.core.reports.chap7 import ch7_quantities


class TestBOQCharts(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="test_boq_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_calculate_and_extract_boq_quantities(self):
        # 24 m span, 4 girders, 2.5 m spacing
        inputs = {
            "span": "24.0",
            "typical_section.no_of_girders": "4",
            "typical_section.girder_spacing": "2.5",
            "typical_section.overall_bridge_width": "8.5",
            "typical_section.deck_thickness": "250.0",
            "member_properties.girder_details.section_input.web_depth": "1600.0",
            "member_properties.girder_details.section_input.web_thickness": "14.0",
            "member_properties.girder_details.section_input.top_flange_width": "450.0",
            "member_properties.girder_details.section_input.top_flange_thickness": "25.0",
            "member_properties.girder_details.section_input.bottom_flange_width": "500.0",
            "member_properties.girder_details.section_input.bottom_flange_thickness": "32.0",
            "member_properties.end_diaphragm_details.type": "Cross Bracing",
        }
        outputs = {
            "transverse_member_design.cb.section_properties.bracing.G1G2.A": "25.5",  # cm²
            "crossbracing_forces_dict": {
                "geometry": {
                    "diagonal_length_m": 2.97,
                    "cb_spacing_m": 4.8,
                }
            },
            "transverse_member_design.ed.section_properties.end_diaphragm.G1G2.A": "28.0",  # cm²
            "end_diaphragm_forces_dict": {
                "geometry": {
                    "diagonal_length_m": 2.97,
                }
            }
        }

        quantities = calculate_material_quantities(inputs, outputs)
        inputs.update(quantities)

        # Check that values are calculated
        self.assertNotEqual(quantities["steel_girders_wt_total"], "N.A.")
        self.assertNotEqual(quantities["bracing_top_wt_total"], "N.A.")
        self.assertNotEqual(quantities["ed_wt_total"], "N.A.")
        self.assertNotEqual(quantities["concrete_deck_vol_total"], "N.A.")
        self.assertNotEqual(quantities["rebar_deck_wt_total"], "N.A.")

        # Extract quantities
        data = extract_boq_quantities(inputs, outputs)
        self.assertTrue(data["has_valid_steel"])
        self.assertTrue(data["has_valid_concrete_rebar"])

        steel = data["steel"]
        self.assertGreater(steel["girders"], 0.0)
        self.assertGreater(steel["cross_bracing"], 0.0)
        self.assertGreater(steel["end_diaphragm"], 0.0)
        self.assertAlmostEqual(
            steel["total"],
            steel["girders"] + steel["cross_bracing"] + steel["end_diaphragm"],
            places=2
        )

        concrete = data["concrete"]
        self.assertGreater(concrete["volume_m3"], 0.0)

        rebar = data["rebar"]
        self.assertGreater(rebar["weight_mt"], 0.0)

    def test_plot_charts(self):
        inputs = {
            "steel_girders_wt_total": "42.50",
            "bracing_top_wt_total": "1.20",
            "bracing_bot_wt_total": "1.20",
            "bracing_diag_wt_total": "2.40",
            "ed_wt_total": "2.10",
            "concrete_deck_vol_total": "51.00",
            "concrete_deck_wt_total": "127.50",
            "rebar_deck_wt_total": "6.12",
        }
        data = extract_boq_quantities(inputs, {})

        p1 = os.path.join(self.tmp_dir, "test_steel.png")
        res1 = plot_steel_tonnage_chart(data, p1)
        self.assertIsNotNone(res1)
        self.assertTrue(os.path.exists(p1))
        self.assertGreater(os.path.getsize(p1), 5000)

        p2 = os.path.join(self.tmp_dir, "test_concrete_rebar.png")
        res2 = plot_concrete_rebar_chart(data["concrete"], data["rebar"], p2)
        self.assertIsNotNone(res2)
        self.assertTrue(os.path.exists(p2))
        self.assertGreater(os.path.getsize(p2), 5000)

    def test_generate_all_boq_charts(self):
        inputs = {
            "steel_girders_wt_total": "42.50",
            "bracing_top_wt_total": "1.20",
            "bracing_bot_wt_total": "1.20",
            "bracing_diag_wt_total": "2.40",
            "ed_wt_total": "2.10",
            "concrete_deck_vol_total": "51.00",
            "concrete_deck_wt_total": "127.50",
            "rebar_deck_wt_total": "6.12",
        }
        paths = generate_all_boq_charts(inputs, {}, self.tmp_dir)
        self.assertIn("boq_chart_steel", paths)
        self.assertIn("boq_chart_concrete_rebar", paths)
        self.assertTrue(os.path.exists(paths["boq_chart_steel"]))
        self.assertTrue(os.path.exists(paths["boq_chart_concrete_rebar"]))

    def test_ch7_quantities_embedding(self):
        inputs = {
            "steel_girders_vol_formula": "Area x Length",
            "steel_girders_qty": "4",
            "steel_girders_vol_total": "5.41",
            "steel_girders_wt_single": "10.62",
            "steel_girders_wt_total": "42.50",
            "bracing_top_wt_total": "1.20",
            "bracing_bot_wt_total": "1.20",
            "bracing_diag_wt_total": "2.40",
            "ed_vol_formula": "Area x Length",
            "ed_qty": "6",
            "ed_vol_total": "0.27",
            "ed_wt_single": "0.35",
            "ed_wt_total": "2.10",
            "concrete_deck_vol_formula": "W x T x L",
            "concrete_deck_qty": "1",
            "concrete_deck_vol_total": "51.00",
            "concrete_deck_wt_single": "127.50",
            "concrete_deck_wt_total": "127.50",
            "rebar_deck_vol_formula": "Area x L",
            "rebar_deck_qty": "1",
            "rebar_deck_vol_total": "0.78",
            "rebar_deck_wt_single": "6.12",
            "rebar_deck_wt_total": "6.12",
        }
        fig_paths = generate_all_boq_charts(inputs, {}, self.tmp_dir)
        tex_output = ch7_quantities(inputs, fig_paths)

        # Verify Table 7.1 has End Diaphragms row
        self.assertIn("End Diaphragms", tex_output)
        self.assertIn("2.10", tex_output)

        # Verify Visualizations section and Figure inclusion
        self.assertIn("Material Quantity Visualizations", tex_output)
        self.assertIn("fig:boq-steel-tonnage", tex_output)
        self.assertIn("fig:boq-concrete-rebar", tex_output)
        self.assertIn("boq_chart_steel.png", tex_output)
        self.assertIn("boq_chart_concrete_rebar.png", tex_output)

    def test_empty_or_unsolved_fallback(self):
        empty_inputs = {}
        paths = generate_all_boq_charts(empty_inputs, {}, self.tmp_dir)
        self.assertEqual(len(paths), 0)

        tex_output = ch7_quantities(empty_inputs, {})
        self.assertIn("Material Quantity Visualizations", tex_output)
        self.assertIn("Note: Material quantity visualizations are generated automatically", tex_output)
        self.assertNotIn("begin{figure}", tex_output)

    def test_end_to_end_pdf_compilation(self):
        pdflatex_bin = None
        for cand in ("/Library/TeX/texbin/pdflatex", "/usr/local/bin/pdflatex", shutil.which("pdflatex")):
            if cand and os.path.exists(cand):
                pdflatex_bin = cand
                break
        if not pdflatex_bin:
            self.skipTest("pdflatex binary not found")

        import subprocess
        inputs = {
            "steel_girders_vol_formula": "Area x Length",
            "steel_girders_qty": "4",
            "steel_girders_vol_total": "5.41",
            "steel_girders_wt_single": "10.62",
            "steel_girders_wt_total": "42.50",
            "bracing_top_wt_total": "1.20",
            "bracing_bot_wt_total": "1.20",
            "bracing_diag_wt_total": "2.40",
            "ed_vol_formula": "Area x Length",
            "ed_qty": "6",
            "ed_vol_total": "0.27",
            "ed_wt_single": "0.35",
            "ed_wt_total": "2.10",
            "concrete_deck_vol_formula": "W x T x L",
            "concrete_deck_qty": "1",
            "concrete_deck_vol_total": "51.00",
            "concrete_deck_wt_single": "127.50",
            "concrete_deck_wt_total": "127.50",
            "rebar_deck_vol_formula": "Area x L",
            "rebar_deck_qty": "1",
            "rebar_deck_vol_total": "0.78",
            "rebar_deck_wt_single": "6.12",
            "rebar_deck_wt_total": "6.12",
        }
        fig_paths = generate_all_boq_charts(inputs, {}, self.tmp_dir)
        ch7_tex = ch7_quantities(inputs, fig_paths)

        doc = r"""\documentclass[12pt,a4paper]{report}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{graphicx}
\usepackage{longtable}
\usepackage{array}
\usepackage{float}
\usepackage{xcolor}
\usepackage{amsmath}
\usepackage{amssymb}
\newcolumntype{C}[1]{>{\centering\arraybackslash}p{#1}}
\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}
\begin{document}
""" + ch7_tex + r"""
\end{document}
"""
        tex_path = os.path.join(self.tmp_dir, "test_doc.tex")
        with open(tex_path, "w") as f:
            f.write(doc)

        proc = subprocess.run([pdflatex_bin, "-interaction=nonstopmode", "test_doc.tex"],
                              cwd=self.tmp_dir, capture_output=True)
        pdf_path = os.path.join(self.tmp_dir, "test_doc.pdf")
        self.assertTrue(os.path.exists(pdf_path), f"pdflatex failed: {proc.stdout.decode('utf-8', 'ignore')[-1000:]}")
        self.assertGreater(os.path.getsize(pdf_path), 10000)


if __name__ == "__main__":
    unittest.main()
