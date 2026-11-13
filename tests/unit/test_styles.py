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


if __name__ == "__main__":
    unittest.main()

