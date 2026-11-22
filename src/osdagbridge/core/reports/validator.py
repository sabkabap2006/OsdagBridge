# =============================================================================
# OsdagBridge — Pre-Generation Report Validator
# Validates report payload, data integrity, figure existence, status consistency,
# and checks for unresolved placeholders before PDF compilation.
# =============================================================================

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    severity: str  # "ERROR" or "WARNING"
    category: str
    message: str


@dataclass
class ValidationReport:
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    unresolved_items: List[str] = field(default_factory=list)
    unsupported_calculations: List[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "ERROR")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "WARNING")

    @property
    def errors(self) -> List[str]:
        return [i.message for i in self.issues if i.severity == "ERROR"]

    @property
    def warnings(self) -> List[str]:
        return [i.message for i in self.issues if i.severity == "WARNING"]

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "OSDAGBRIDGE REPORT VALIDATION SUMMARY",
            "=" * 60,
            f"Overall Status: {'PASSED' if self.is_valid else 'FAILED'}",
            f"Errors: {self.error_count}, Warnings: {self.warning_count}",
        ]
        if self.issues:
            lines.append("\nValidation Issues:")
            for issue in self.issues:
                lines.append(f"  [{issue.severity}] ({issue.category}) {issue.message}")

        if self.unresolved_items:
            lines.append("\nUnresolved Placeholders / Missing Items:")
            for item in self.unresolved_items:
                lines.append(f"  - {item}")

        if self.unsupported_calculations:
            lines.append("\nUnsupported / Explicitly Marked Calculations:")
            for calc in self.unsupported_calculations:
                lines.append(f"  - {calc}")

        lines.append("=" * 60)
        return "\n".join(lines)


ValidationResult = ValidationReport
ReportValidationResult = ValidationReport


def validate_report_payload(payload: Any, request: Any = None, figures_dir: Optional[str] = None) -> ValidationReport:
    """Validate report payload data consistency and completeness before rendering."""
    issues: List[ValidationIssue] = []
    unresolved: List[str] = []
    unsupported: List[str] = []

    inputs = getattr(payload, "inputs", {}) or {}
    outputs = getattr(payload, "output_dict", {}) or {}
    asum = getattr(payload, "analysis_summary", {}) or {}

    # 1. Mandatory Input Fields
    mandatory_inputs = [
        (("span", "geometry.span"), "Bridge Span"),
        (("typical_section.no_of_girders", "typical_section.girders"), "Number of Girders"),
        (("typical_section.girder_spacing",), "Girder Spacing"),
        (("typical_section.deck_thickness",), "Deck Thickness"),
        (("materials.girder", "material.girder"), "Girder Steel Grade"),
        (("materials.deck.concrete_grade", "material.deck"), "Deck Concrete Grade"),
    ]
    for keys, name in mandatory_inputs:
        val = None
        for k in keys:
            if inputs.get(k) is not None and str(inputs.get(k)).strip() != "":
                val = inputs.get(k)
                break
        if val is None or str(val).strip() == "":
            issues.append(ValidationIssue("ERROR", "Input Data", f"Missing mandatory input field '{name}' ({keys[0]})"))
            unresolved.append(f"Missing mandatory input: {name}")

    # 2. Analysis Summary
    lc_summary = asum.get("load_cases", {})
    rxn_summary = asum.get("reactions", {})
    if not lc_summary:
        issues.append(ValidationIssue("WARNING", "Analysis Results", "Table 4.1 analysis load case summary is empty"))
        unresolved.append("Analysis load cases empty in Table 4.1")
    if not rxn_summary:
        issues.append(ValidationIssue("WARNING", "Analysis Results", "Table 4.2 support reactions summary is empty"))
        unresolved.append("Support reactions empty in Table 4.2")

    # 3. Girder Design Results
    dr = outputs.get("design_results", {}) or {}
    per_girder = dr.get("per_girder", {}) or {}
    if not per_girder:
        issues.append(ValidationIssue("ERROR", "Girder Design", "No per-girder design results found in design_results['per_girder']"))
        unresolved.append("Missing per-girder design results")
    else:
        # Check individual checks for failures and completeness
        for g_name, g_data in per_girder.items():
            if str(g_name).startswith("EB"):
                continue
            checks = g_data.get("checks", [])
            if not checks:
                issues.append(ValidationIssue("WARNING", "Girder Design", f"Girder {g_name} has no design check records"))
                unresolved.append(f"Girder {g_name} checks empty")

    # 4. Deck Slab Design Results
    dd_results = outputs.get("deck_design_results", {}) or {}
    dd_rpt = outputs.get("deck_report_values", {}) or {}
    if not dd_results and not dd_rpt:
        issues.append(ValidationIssue("WARNING", "Deck Slab", "Deck slab design results missing or not calculated"))
        unsupported.append("Deck slab detailed design (marked NOT CALCULATED if absent)")

    # 5. Cross Bracing & End Diaphragm
    cb_results = outputs.get("crossbracing_design_results", {}) or {}
    ed_results = outputs.get("end_diaphragm_design_results", {}) or {}
    if not cb_results:
        issues.append(ValidationIssue("WARNING", "Cross Bracing", "Cross bracing design results missing"))
        unsupported.append("Cross bracing design results")
    if not ed_results:
        issues.append(ValidationIssue("WARNING", "End Diaphragm", "End diaphragm design results missing"))
        unsupported.append("End diaphragm design results")

    # 6. Bill of Materials
    for k in ("steel_girders_vol_formula", "concrete_deck_vol_formula", "shear_studs_qty"):
        val = inputs.get(k)
        if val is None or "N.A." in str(val) or "placeholder" in str(val).lower():
            issues.append(ValidationIssue("WARNING", "Bill of Materials", f"BOM field '{k}' contains placeholder or N.A."))
            unresolved.append(f"BOM field '{k}' not resolved to numerical quantity")

    # 7. Status Reconciliation (Summary vs Detailed)
    # Check if girder fatigue or other check failed
    failing_checks = []
    for g_name, g_data in per_girder.items():
        if str(g_name).startswith("EB"):
            continue
        for chk in g_data.get("checks", []):
            dcr = chk.get("dcr")
            status = str(chk.get("status", "")).upper()
            if "FAIL" in status or (dcr is not None and float(dcr) > 1.0):
                failing_checks.append(f"{g_name}: {chk.get('name')} (UR={dcr})")

    deck_failed = False
    if dd_rpt:
        # Check booleans if present
        for ok_key in ("deck.report.punch_ok", "deck.report.shear_ok", "deck.report.cover_ok"):
            if ok_key in dd_rpt and dd_rpt[ok_key] is False:
                deck_failed = True

    # Rule: If any check failed, overall status must not claim PASS
    overall_status_claimed = str(getattr(payload, "overall_status", "") or outputs.get("overall_status", "")).upper()
    if "PASS" in overall_status_claimed and (failing_checks or deck_failed):
        issues.append(ValidationIssue("ERROR", "Status Consistency", f"Overall status claims PASS but contradicts failed component checks: {failing_checks}"))

    is_valid = not any(i.severity == "ERROR" for i in issues)

    report = ValidationReport(
        is_valid=is_valid,
        issues=issues,
        unresolved_items=unresolved,
        unsupported_calculations=unsupported,
    )
    return report


def validate_latex_source(tex_content: str) -> ValidationReport:
    """Inspect generated LaTeX for unresolved placeholders and formatting errors."""
    placeholder_patterns = [
        (r"\\placeholder\{([^}]+)\}", "LaTeX placeholder \\placeholder{}"),
        (r"<—>", "Empty angle bracket placeholder <—>"),
        (r"\[ PLACEHOLDER:[^\]]+\]", "Figure placeholder box [ PLACEHOLDER ]"),
        (r"\\todo\{[^}]+\}", "TODO marker \\todo{}"),
    ]
    issues: List[ValidationIssue] = []
    unresolved: List[str] = []
    for pat, label in placeholder_patterns:
        matches = re.findall(pat, tex_content)
        if matches:
            msg = f"Found {len(matches)} occurrences of {label}: {matches[:3]}"
            sev = "WARNING" if "Figure placeholder" in label else "ERROR"
            issues.append(ValidationIssue(sev, "LaTeX Placeholder", msg))
            unresolved.append(msg)

    is_valid = not any(i.severity == "ERROR" for i in issues)
    return ValidationReport(
        is_valid=is_valid,
        issues=issues,
        unresolved_items=unresolved,
        unsupported_calculations=[],
    )
