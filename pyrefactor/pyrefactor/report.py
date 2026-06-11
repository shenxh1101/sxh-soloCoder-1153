import json
from typing import List, Optional
from datetime import datetime

from .models import SmellResult, RefactoringChange, RefactorReport


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
                    lines.append(f"      [Auto-refactor available]")
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
                "smells_by_type": {
                    st.value: count for st, count in self.report.smells_by_type.items()
                },
            },
            "smells": [s.to_dict() for s in smells],
            "refactored_changes": self.report.refactored_changes,
            "errors": self.report.errors,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)