# =============================================================================
# OsdagBridge — Centralized Document & Report Styles (styles.py)
#
# Standardizes formatting across all report chapters and figures:
#   - Fonts and typography (Latin Modern, T1 encoding, line stretch)
#   - Table padding and geometry (tabcolsep, arraystretch, longtable limits)
#   - Unified color palette (Osdag green, PASS/FAIL, material take-off colors)
#   - Page geometry and margins
#   - Direct adaptation to PyLaTeX requirements (Document, Package, Command,
#     Figure, LongTable, NoEscape) with resilient string fallbacks.
# =============================================================================

from __future__ import annotations
import os
import re
from typing import Dict, Any, List, Optional, Tuple, Union

# Try importing PyLaTeX components; gracefully degrade if pylatex is absent.
try:
    import pylatex
    from pylatex import (
        Document as PyLatexDocument,
        Package as PyLatexPackage,
        Command as PyLatexCommand,
        Figure as PyLatexFigure,
        LongTable as PyLatexLongTable,
        Table as PyLatexTable,
        Tabular as PyLatexTabular,
        TextColor as PyLatexTextColor,
    )
    from pylatex.utils import NoEscape as PyLatexNoEscape, bold, italic
    PYLATEX_AVAILABLE = True
except ImportError:
    PYLATEX_AVAILABLE = False
    PyLatexDocument = None
    PyLatexPackage = None
    PyLatexCommand = None
    PyLatexFigure = None
    PyLatexLongTable = None
    PyLatexTable = None
    PyLatexTabular = None
    PyLatexTextColor = None


def NoEscape(text: str) -> Any:
    """Wrap string in PyLaTeX NoEscape if available, else return string as-is."""
    if PYLATEX_AVAILABLE:
        try:
            from pylatex.utils import NoEscape as _NoEscape
            return _NoEscape(text)
        except Exception:
            pass
    return text


# ═════════════════════════════════════════════════════════════════════════════
# 1. COLOR PALETTE (Centralized Osdag Design System)
# ═════════════════════════════════════════════════════════════════════════════

class Colors:
    """Hex color definitions and naming standard across OsdagBridge reports and charts."""
    # Osdag Branding
    OSDAG_GREEN     = "#91B014"  # Signature Osdag Olive-Green
    OSDAG_BLUE      = "#1976D2"  # Primary Blue
    NAVY_DARK       = "#1A365D"  # Deep Navy (Cover and Headings)

    # Design Check Status & Compliance
    PASS_GREEN      = "#2E7D32"  # Safe / Pass (UR <= 0.85)
    WARN_AMBER      = "#F57C00"  # Warning / Economical (0.85 < UR <= 1.0)
    FAIL_RED        = "#D32F2F"  # Over Limit / Fail (UR > 1.0)
    ALERT_RED_TEXT  = "#B71C1C"  # Dark Red for Critical Text
    NA_GREY         = "#757575"  # Non-applicable / neutral

    # Structural Materials (Take-Off / BOQ Charts)
    STEEL_GIRDER    = "#1976D2"  # Plate Girders
    STEEL_BRACING   = "#00897B"  # Cross Bracing (Intermediate)
    STEEL_DIAPHRAGM = "#43A047"  # End Diaphragms (Supports)
    STEEL_TOTAL     = "#37474F"  # Total Superstructure Steel
    CONCRETE_SLAB   = "#455A64"  # Deck Slab Concrete (M40)
    REBAR_STEEL     = "#D84315"  # Reinforcement Steel (Fe 500)
    CRASH_BARRIER   = "#795548"  # Concrete Crash Barrier
    SHEAR_STUDS     = "#6A1B9A"  # Shear Stud Connectors

    # Neutral & Layout Surfaces
    BG_WHITE        = "#FFFFFF"
    BG_LIGHT_GREY   = "#F8F9FA"
    BG_HEADER_GREY  = "#F0F0F0"
    BORDER_GREY     = "#BDBDBD"
    AXIS_GREY       = "#616161"
    TEXT_DARK       = "#212121"
    TEXT_MUTED      = "#616161"

    # LaTeX Color Name Mapping
    LATEX_COLOR_MAP = {
        "osdagGreen":     "91B014",
        "osdagBlue":      "1976D2",
        "osdagNavy":      "1A365D",
        "osdagPass":      "2E7D32",
        "osdagWarn":      "F57C00",
        "osdagFail":      "D32F2F",
        "osdagGrey":      "757575",
        "osdagHeaderBg":  "F0F0F0",
    }


def get_latex_color_definitions() -> str:
    """Generate LaTeX \\definecolor declarations for the centralized palette."""
    lines = ["% Centralized OsdagBridge Color Palette"]
    for name, hex_code in Colors.LATEX_COLOR_MAP.items():
        lines.append(f"\\definecolor{{{name}}}{{HTML}}{{{hex_code}}}")
    return "\n".join(lines)


def format_status_latex(status: Union[str, bool, None], true_label: str = "PASS", false_label: str = "FAIL") -> str:
    """
    Format a pass/fail status consistently with code-compliant colored text.
    
    Parameters
    ----------
    status : str, bool, or None
        Status string ("PASS", "FAIL"), boolean, or None.
    true_label : str
        Text label for passing state.
    false_label : str
        Text label for failing state.
    """
    if status is None:
        return "---"
    
    if isinstance(status, bool):
        is_pass = status
    else:
        s = str(status).strip().upper()
        if not s or s in ("---", "N/A", "N.A."):
            return "---"
        is_pass = ("PASS" in s or "SAFE" in s or "OK" in s) and ("FAIL" not in s)

    if is_pass:
        return f"\\textcolor{{osdagPass}}{{\\textbf{{{true_label}}}}}"
    else:
        return f"\\textcolor{{osdagFail}}{{\\textbf{{{false_label}}}}}"


def format_ur_latex(ur_value: Any) -> str:
    """Format a numerical utilization ratio with color coding for compliance."""
    try:
        f = float(ur_value)
    except (TypeError, ValueError):
        return "---"

    formatted = f"{f:.2f}"
    if f > 1.0:
        return f"\\textcolor{{osdagFail}}{{\\textbf{{{formatted}}}}}"
    elif f > 0.85:
        return f"\\textcolor{{osdagWarn}}{{\\textbf{{{formatted}}}}}"
    else:
        return formatted


# ═════════════════════════════════════════════════════════════════════════════
# 2. TABLE FORMATTING & PADDING STANDARDS
# ═════════════════════════════════════════════════════════════════════════════

class TableStyles:
    """
    Centralized table formatting constants.
    Eliminates discrepancies between different chapter modules.
    """
    # Horizontal cell padding (tabcolsep)
    TABCOLSEP_DEFAULT = "5.0pt"    # Standard balanced padding
    TABCOLSEP_COMPACT = "3.5pt"    # Wide multi-column tables (7+ columns, BOQ, slenderness)
    TABCOLSEP_COMFORT = "6.0pt"    # Relaxed padding for 2-4 column property tables

    # Vertical row spacing
    ARRAYSTRETCH_DEFAULT = 1.25     # Generous vertical stretch preventing rule collision
    EXTRAROWHEIGHT       = "2.5pt"  # Extra headroom above text baseline
    ARRAYRULEWIDTH       = "0.5pt"  # Clean boundary rule thickness

    # Longtable environment spacing
    LT_PRE_SKIP          = "8pt"    # Space before LongTable
    LT_POST_SKIP         = "10pt"   # Space after LongTable
    LT_LEFT_ALIGN        = "0pt"    # Left aligned to margin
    LT_RIGHT_ALIGN       = "\\fill" # Fill right margin

    # Orphan & footer protection
    NEEDSPACE_THRESHOLD  = "7\\baselineskip"


def table_setup_latex(preset: str = "default") -> str:
    """
    Generate LaTeX \\setlength and \\renewcommand commands for table formatting.

    Presets:
      - 'default': 5.0pt padding (balanced for most engineering tables)
      - 'compact': 3.5pt padding (for wide tables like Bill of Quantities)
      - 'comfort': 6.0pt padding (for narrow 2-4 column input tables)
    """
    tabcolsep = TableStyles.TABCOLSEP_DEFAULT
    if preset == "compact":
        tabcolsep = TableStyles.TABCOLSEP_COMPACT
    elif preset == "comfort":
        tabcolsep = TableStyles.TABCOLSEP_COMFORT

    return f"""% Centralized Table Formatting Settings ({preset})
\\setlength{{\\tabcolsep}}{{{tabcolsep}}}
\\renewcommand{{\\arraystretch}}{{{TableStyles.ARRAYSTRETCH_DEFAULT}}}
\\setlength{{\\extrarowheight}}{{{TableStyles.EXTRAROWHEIGHT}}}
\\setlength{{\\arrayrulewidth}}{{{TableStyles.ARRAYRULEWIDTH}}}
\\setlength{{\\LTpre}}{{{TableStyles.LT_PRE_SKIP}}}
\\setlength{{\\LTpost}}{{{TableStyles.LT_POST_SKIP}}}
\\setlength{{\\LTleft}}{{{TableStyles.LT_LEFT_ALIGN}}}
\\setlength{{\\LTright}}{{{TableStyles.LT_RIGHT_ALIGN}}}
"""


# ═════════════════════════════════════════════════════════════════════════════
# 3. TYPOGRAPHY & DOCUMENT GEOMETRY
# ═════════════════════════════════════════════════════════════════════════════

class Typography:
    """Typography and font standards."""
    FONT_FAMILY       = "lmodern"
    FONT_ENCODING     = "T1"
    INPUT_ENCODING    = "utf8"
    BASE_FONT_SIZE    = "12pt"
    DOCUMENT_CLASS    = "report"
    LINE_STRETCH      = 1.15

    # Column alignment types
    COL_TYPES = {
        "C": r">{\centering\arraybackslash}p",
        "L": r">{\raggedright\arraybackslash}p",
        "R": r">{\raggedleft\arraybackslash}p",
    }


# Page geometry configuration (matches PyLaTeX geometry options dict)
GEOMETRY_OPTIONS: Dict[str, Union[str, bool]] = {
    "a4paper": True,
    "top": "24mm",
    "bottom": "32mm",
    "left": "20mm",
    "right": "20mm",
    "headheight": "20pt",
    "headsep": "6mm",
    "footskip": "15mm",
}


def get_geometry_latex() -> str:
    """Generate LaTeX geometry package invocation."""
    opts = [
        "a4paper",
        f"top={GEOMETRY_OPTIONS['top']}",
        f"bottom={GEOMETRY_OPTIONS['bottom']}",
        f"left={GEOMETRY_OPTIONS['left']}",
        f"right={GEOMETRY_OPTIONS['right']}",
        f"headheight={GEOMETRY_OPTIONS['headheight']}",
        f"headsep={GEOMETRY_OPTIONS['headsep']}",
        f"footskip={GEOMETRY_OPTIONS['footskip']}",
    ]
    return "\\usepackage[\n    " + ",\n    ".join(opts) + "\n]{geometry}\n"


# ═════════════════════════════════════════════════════════════════════════════
# 4. PYLATEX INTEGRATION & ADAPTATION HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def get_pylatex_packages() -> List[Any]:
    """
    Return a list of PyLaTeX Package objects matching OsdagBridge standards.
    Returns an empty list if PyLaTeX is not installed.
    """
    if not PYLATEX_AVAILABLE:
        return []

    return [
        PyLatexPackage("geometry", options=[
            "a4paper",
            f"top={GEOMETRY_OPTIONS['top']}",
            f"bottom={GEOMETRY_OPTIONS['bottom']}",
            f"left={GEOMETRY_OPTIONS['left']}",
            f"right={GEOMETRY_OPTIONS['right']}",
            f"headheight={GEOMETRY_OPTIONS['headheight']}",
            f"headsep={GEOMETRY_OPTIONS['headsep']}",
            f"footskip={GEOMETRY_OPTIONS['footskip']}",
        ]),
        PyLatexPackage("fontenc", options=["T1"]),
        PyLatexPackage("lmodern"),
        PyLatexPackage("graphicx"),
        PyLatexPackage("amsmath"),
        PyLatexPackage("amssymb"),
        PyLatexPackage("booktabs"),
        PyLatexPackage("array"),
        PyLatexPackage("tabularx"),
        PyLatexPackage("float"),
        PyLatexPackage("fancyhdr"),
        PyLatexPackage("xcolor"),
        PyLatexPackage("setspace"),
        PyLatexPackage("enumitem"),
        PyLatexPackage("caption", options=[
            "labelfont=bf",
            "justification=raggedright",
            "singlelinecheck=false",
            "format=plain"
        ]),
        PyLatexPackage("subcaption"),
        PyLatexPackage("multirow"),
        PyLatexPackage("colortbl"),
        PyLatexPackage("longtable"),
        PyLatexPackage("titlesec"),
        PyLatexPackage("titletoc"),
        PyLatexPackage("lastpage"),
        PyLatexPackage("makecell"),
        PyLatexPackage("etoolbox"),
        PyLatexPackage("needspace"),
    ]


def apply_pylatex_styles(doc: Any) -> None:
    """
    Apply centralized Osdag styles directly to a PyLaTeX Document instance.
    Configures geometry, packages, color definitions, and table parameters.
    """
    if not PYLATEX_AVAILABLE or not isinstance(doc, PyLatexDocument):
        return

    # Add packages
    for pkg in get_pylatex_packages():
        doc.packages.append(pkg)

    # Color definitions
    for name, hex_code in Colors.LATEX_COLOR_MAP.items():
        doc.preamble.append(PyLatexCommand("definecolor", [name, "HTML", hex_code]))

    # Table layout commands
    doc.preamble.append(PyLatexCommand("setlength", [PyLatexCommand("tabcolsep"), PyLatexNoEscape(TableStyles.TABCOLSEP_DEFAULT)]))
    doc.preamble.append(PyLatexCommand("renewcommand", [PyLatexCommand("arraystretch"), PyLatexNoEscape(str(TableStyles.ARRAYSTRETCH_DEFAULT))]))
    doc.preamble.append(PyLatexCommand("setlength", [PyLatexCommand("extrarowheight"), PyLatexNoEscape(TableStyles.EXTRAROWHEIGHT)]))
    doc.preamble.append(PyLatexCommand("setlength", [PyLatexCommand("arrayrulewidth"), PyLatexNoEscape(TableStyles.ARRAYRULEWIDTH)]))
    doc.preamble.append(PyLatexCommand("setlength", [PyLatexCommand("LTpre"), PyLatexNoEscape(TableStyles.LT_PRE_SKIP)]))
    doc.preamble.append(PyLatexCommand("setlength", [PyLatexCommand("LTpost"), PyLatexNoEscape(TableStyles.LT_POST_SKIP)]))

    # Orphan protection
    doc.preamble.append(PyLatexCommand("BeforeBeginEnvironment", ["longtable", PyLatexCommand("needspace", [PyLatexNoEscape(TableStyles.NEEDSPACE_THRESHOLD)])]))

    # Custom column types
    for c_id, definition in Typography.COL_TYPES.items():
        doc.preamble.append(PyLatexCommand("newcolumntype", [c_id, 1, PyLatexNoEscape(definition + "{#1}")]))


def render_pylatex_figure(
    image_path: str,
    caption: str = "",
    label: str = "",
    width: str = r"0.92\textwidth",
    position: str = "H"
) -> str:
    """
    Render a centered, numbered figure using PyLaTeX Figure with resilient LaTeX fallback.

    Parameters
    ----------
    image_path : str
        Path to image on disk.
    caption : str
        Figure caption text (bolded per style standard).
    label : str
        LaTeX cross-reference label (e.g. 'fig:ur-overall').
    width : str
        Figure width specification.
    position : str
        Placement specifier (default 'H' for exact placement).
    """
    if not image_path or not os.path.exists(image_path):
        return ""

    clean_path = image_path.replace("\\", "/")

    if PYLATEX_AVAILABLE:
        try:
            fig = PyLatexFigure(position=position)
            fig.add_image(clean_path, width=PyLatexNoEscape(width))
            if caption:
                fig.add_caption(PyLatexNoEscape(r"\textbf{" + caption + r"}"))
            if label:
                fig.append(PyLatexCommand("label", label))
            return fig.dumps() + "\n"
        except Exception:
            pass

    # Resilient standard LaTeX fallback
    lbl_str = f"\\label{{{label}}}\n" if label else ""
    cap_str = f"\\caption{{\\textbf{{{caption}}}}}\n" if caption else ""
    return (
        r"\begin{figure}[" + position + r"]" + "\n"
        r"\centering" + "\n"
        rf"\includegraphics[width={width},keepaspectratio]{{{clean_path}}}" + "\n"
        + cap_str
        + lbl_str +
        r"\end{figure}" + "\n"
    )

