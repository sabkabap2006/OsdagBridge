"""Reports package."""
from .report_generator import (
    ReportMetadata,
    ReportOptions,
    ReportRequest,
    ReportFigures,
    ReportPayload,
    ReportResult,
    build_report_payload,
    generate_report,
)
from .styles import (
    Colors,
    TableStyles,
    Typography,
    GEOMETRY_OPTIONS,
    format_status_latex,
    format_ur_latex,
    get_latex_color_definitions,
    table_setup_latex,
    render_pylatex_figure,
    apply_pylatex_styles,
)

__all__ = [
    "ReportMetadata", "ReportOptions", "ReportRequest",
    "ReportFigures", "ReportPayload", "ReportResult",
    "build_report_payload", "generate_report",
    "Colors", "TableStyles", "Typography", "GEOMETRY_OPTIONS",
    "format_status_latex", "format_ur_latex",
    "get_latex_color_definitions", "table_setup_latex",
    "render_pylatex_figure", "apply_pylatex_styles",
]
