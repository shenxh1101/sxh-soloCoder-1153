import json
from typing import List, Optional, Dict
from datetime import datetime

from .models import SmellResult, RefactoringChange, RefactorReport, SEVERITY_ORDER


class ReportGenerator:
    def __init__(self, report: RefactorReport):
        self.report = report

    def generate_text(self, smells: List[SmellResult], refactoring_changes: dict) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append("  PyRefactor - Code Smell Detection & Refactoring Report")
        lines.append("=" * 70)
        lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append(f"  Files processed:      {self.report.files_processed}")
        lines.append(f"  Files with smells:    {self.report.files_with_smells}")
        lines.append(f"  Total smells found:   {self.report.total_smells}")
        lines.append(f"  Refactorings applied: {self.report.refactored_count}")
        if self.report.skipped_unsafe > 0:
            lines.append(f"  Skipped (unsafe):     {self.report.skipped_unsafe}")
        lines.append("")

        if self.report.smells_by_type:
            lines.append("  Smells by type:")
            for smell_type, count in self.report.smells_by_type.items():
                lines.append(f"    - {smell_type.value}: {count}")
            lines.append("")

        if smells:
            lines.append("-" * 70)
            lines.append("  DETECTED CODE SMELLS")
            lines.append("-" * 70)
            lines.append("")

            current_file = None
            for smell in smells:
                file_path = smell.location.file_path
                if file_path != current_file:
                    current_file = file_path
                    lines.append(f"  [File] {file_path}")
                    lines.append("")

                lines.append(f"    [{smell.smell_type.value.upper()}] {smell.message}")
                lines.append(f"      Severity: {smell.severity}")
                lines.append(f"      Location: line {smell.location.start_line + 1}")
                if smell.location.end_line is not None:
                    lines.append(f"                to line {smell.location.end_line + 1}")
                if smell.suggestion:
                    lines.append(f"      Suggestion: {smell.suggestion}")
                if smell.refactor_suggestion:
                    lines.append(f"      Refactoring: {smell.refactor_suggestion}")
                if smell.can_auto_refactor:
                    if smell.is_safe_to_refactor:
                        lines.append(f"      [Auto-refactor available]")
                    else:
                        lines.append(f"      [Auto-refactor UNSAFE — skipped]")
                        for warn in smell.safety_warnings:
                            lines.append(f"        ! {warn}")
                lines.append("")

        if self.report.refactored_changes:
            lines.append("-" * 70)
            lines.append("  REFACTORING CHANGES")
            lines.append("-" * 70)
            lines.append("")

            for idx, change in enumerate(self.report.refactored_changes, 1):
                lines.append(f"  [{idx}] {change['file_path']}")
                lines.append(f"      Smell type:  {change['smell_type']}")
                lines.append(f"      Lines:       {change['original_lines']}")
                lines.append(f"      Description: {change['description']}")
                if change.get("safety_warnings"):
                    lines.append(f"      Safety:      WARNINGS PRESENT")
                    for w in change["safety_warnings"]:
                        lines.append(f"        ! {w}")
                lines.append(f"")
                lines.append(f"      --- Original ---")
                for orig_line in change.get("original_text", "").splitlines():
                    lines.append(f"      -{orig_line}")
                lines.append(f"      +++ New (replacement) +++")
                for new_line in change.get("new_text", "").splitlines():
                    lines.append(f"      +{new_line}")
                for insertion in change.get("insertions", []):
                    lines.append(f"      +++ New (inserted before line {insertion['position'] + 1}) +++")
                    for ins_line in insertion["text"].splitlines():
                        lines.append(f"      +{ins_line}")
                lines.append(f"      --- Diff ---")
                for diff_line in change.get("diff", "").splitlines():
                    lines.append(f"      {diff_line}")
                lines.append("")

        if self.report.errors:
            lines.append("-" * 70)
            lines.append("  ERRORS")
            lines.append("-" * 70)
            for error in self.report.errors:
                lines.append(f"  - {error}")
            lines.append("")

        lines.append("=" * 70)
        lines.append("  End of report")
        lines.append("=" * 70)

        return "\n".join(lines)

    def generate_json(self, smells: List[SmellResult], refactoring_changes: dict) -> str:
        data = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "files_processed": self.report.files_processed,
                "files_with_smells": self.report.files_with_smells,
                "total_smells": self.report.total_smells,
                "refactored_count": self.report.refactored_count,
                "skipped_unsafe": self.report.skipped_unsafe,
                "smells_by_type": {
                    st.value: count for st, count in self.report.smells_by_type.items()
                },
            },
            "smells": [s.to_dict() for s in smells],
            "refactored_changes": self.report.refactored_changes,
            "errors": self.report.errors,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def generate_patch(self, refactoring_changes: Dict[str, list]) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append("  PyRefactor — Refactoring Patch")
        lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 70)
        lines.append("")

        for file_path, changes in refactoring_changes.items():
            lines.append(f"[FILE] {file_path}")
            lines.append("-" * 70)
            lines.append("")

            with open(file_path, "r", encoding="utf-8") as f:
                original_content = f.read()
            from .models import RefactoringProposal
            proposal = RefactoringProposal(
                file_path=file_path,
                original_content=original_content,
                changes=[c for c, _ in changes],
            )

            for i, (change, smell) in enumerate(changes, 1):
                lines.append(f"  Change {i}: {change.description}")
                lines.append(f"    Smell:  {smell.smell_type.value}")
                lines.append(f"    Lines:  {change.original_start_line + 1} - {change.original_end_line + 1}")
                if not change.is_safe:
                    lines.append(f"    *** UNSAFE — skipped from auto-apply ***")
                    for w in change.safety_warnings:
                        lines.append(f"    ! {w}")
                lines.append("")

                lines.append(f"    --- Original ({change.original_start_line + 1}-{change.original_end_line + 1}) ---")
                for orig_line in change.original_text.splitlines():
                    lines.append(f"    - {orig_line}")
                lines.append("")

                lines.append(f"    +++ Replacement +++")
                for new_line in change.new_text.splitlines():
                    lines.append(f"    + {new_line}")
                lines.append("")

                for pos, text in change.additional_insertions:
                    lines.append(f"    +++ Inserted (before line {pos + 1}) +++")
                    for ins_line in text.splitlines():
                        lines.append(f"    + {ins_line}")
                    lines.append("")

            lines.append(f"  --- Unified Diff for {file_path} ---")
            for diff_line in proposal.get_diff().splitlines():
                lines.append(f"  {diff_line}")
            lines.append("")
            lines.append("=" * 70)
            lines.append("")

        return "\n".join(lines)


def filter_smells(
    smells: List[SmellResult],
    min_severity: Optional[str] = None,
    auto_refactorable_only: bool = False,
) -> List[SmellResult]:
    result = []
    for smell in smells:
        if min_severity is not None:
            sev_order = SEVERITY_ORDER.get(smell.severity, 2)
            min_order = SEVERITY_ORDER.get(min_severity, 0)
            if sev_order > min_order:
                continue
        if auto_refactorable_only and not smell.can_auto_refactor:
            continue
        result.append(smell)
    return result