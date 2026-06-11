import json
from typing import List, Optional, Dict, Tuple
from datetime import datetime

from .models import SmellResult, RefactoringChange, RefactorReport, SEVERITY_ORDER


class ReportGenerator:
    def __init__(self, report: RefactorReport):
        self.report = report

    def generate_text(self, smells: List[SmellResult], refactoring_changes: dict,
                      skipped_smells: Optional[List[SmellResult]] = None) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append("  PyRefactor - Code Smell Detection & Refactoring Report")
        lines.append("=" * 70)
        lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append(f"  Files processed:         {self.report.files_processed}")
        lines.append(f"  Files with smells:       {self.report.files_with_smells}")
        lines.append(f"  Total smells found:      {self.report.total_smells}")
        lines.append(f"  Refactorings applied:    {self.report.refactored_count}")
        if self.report.skipped_unsafe > 0:
            lines.append(f"  Refactorings skipped:    {self.report.skipped_unsafe}")
        if self.report.syntax_validation_failures:
            lines.append(f"  Syntax check failures:   {len(self.report.syntax_validation_failures)}")
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
                        lines.append(f"      [Auto-refactor SKIPPED — unsafe]")
                        for warn in smell.safety_warnings:
                            lines.append(f"        ! {warn}")
                lines.append("")

        if skipped_smells:
            lines.append("-" * 70)
            lines.append("  SKIPPED (unsafe or non-applicable)")
            lines.append("-" * 70)
            lines.append("")
            for smell in skipped_smells:
                lines.append(f"    [{smell.smell_type.value.upper()}] {smell.message}")
                lines.append(f"      File: {smell.location.file_path}")
                lines.append(f"      Line: {smell.location.start_line + 1}")
                reason = smell.skip_reason or "; ".join(smell.safety_warnings)
                if reason:
                    lines.append(f"      Reason: {reason}")
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
                syntax_ok = change.get("syntax_valid", True)
                lines.append(f"      Syntax:      {'PASS' if syntax_ok else 'FAIL'}")
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

        if self.report.syntax_validation_failures:
            lines.append("-" * 70)
            lines.append("  SYNTAX VALIDATION FAILURES")
            lines.append("-" * 70)
            for failure in self.report.syntax_validation_failures:
                lines.append(f"  [File] {failure['file_path']}")
                lines.append(f"    Error: {failure['error']}")
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

    def generate_json(self, smells: List[SmellResult], refactoring_changes: dict,
                      skipped_smells: Optional[List[SmellResult]] = None) -> str:
        data = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "files_processed": self.report.files_processed,
                "files_with_smells": self.report.files_with_smells,
                "total_smells": self.report.total_smells,
                "refactored_count": self.report.refactored_count,
                "skipped_unsafe": self.report.skipped_unsafe,
                "syntax_failures": len(self.report.syntax_validation_failures),
                "smells_by_type": {
                    st.value: count for st, count in self.report.smells_by_type.items()
                },
            },
            "smells": [s.to_dict() for s in smells],
            "skipped": [s.to_dict() for s in (skipped_smells or [])],
            "refactored_changes": self.report.refactored_changes,
            "syntax_validation_failures": self.report.syntax_validation_failures,
            "errors": self.report.errors,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def generate_patch(self, refactoring_changes: Dict[str, list],
                       skipped_items: Optional[List[SmellResult]] = None,
                       syntax_results: Optional[Dict[str, bool]] = None) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append("  PyRefactor — Refactoring Patch")
        lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 70)
        lines.append("")

        syntax_results = syntax_results or {}
        skipped_by_file: Dict[str, int] = {}
        if skipped_items:
            for s in skipped_items:
                f = s.location.file_path
                skipped_by_file[f] = skipped_by_file.get(f, 0) + 1

        all_files = set(refactoring_changes.keys()) | set(skipped_by_file.keys())

        lines.append("  [SUMMARY]")
        lines.append(f"  Total files with changes: {len(refactoring_changes)}")
        total_applied = sum(len(v) for v in refactoring_changes.values())
        total_skipped = sum(skipped_by_file.values())
        lines.append(f"  Total changes applied:    {total_applied}")
        lines.append(f"  Total changes skipped:    {total_skipped}")
        lines.append("")

        for file_path in sorted(all_files):
            changes = refactoring_changes.get(file_path, [])
            skip_count = skipped_by_file.get(file_path, 0)
            syntax_ok = syntax_results.get(file_path, None)

            lines.append(f"[FILE] {file_path}")
            lines.append(f"  Changes applied: {len(changes)}")
            lines.append(f"  Changes skipped: {skip_count}")
            if syntax_ok is not None:
                lines.append(f"  Syntax check:    {'PASS' if syntax_ok else 'FAIL'}")
            else:
                lines.append(f"  Syntax check:    N/A")
            lines.append("-" * 70)
            lines.append("")

            if changes:
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

            if skipped_items:
                file_skipped = [s for s in skipped_items if s.location.file_path == file_path]
                if file_skipped:
                    lines.append(f"  --- Skipped in {file_path} ---")
                    for s in file_skipped:
                        reason = s.skip_reason or "; ".join(s.safety_warnings) or "unsafe"
                        lines.append(f"  * line {s.location.start_line + 1}: {reason}")
                    lines.append("")

            lines.append("=" * 70)
            lines.append("")

        return "\n".join(lines)

    def generate_dry_run_summary(self, refactoring_changes: Dict[str, list],
                                  skipped_count: int,
                                  syntax_results: Dict[str, bool]) -> str:
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("  DRY-RUN SUMMARY")
        lines.append("=" * 70)
        lines.append(f"  Files with changes:   {len(refactoring_changes)}")
        total_changes = sum(len(v) for v in refactoring_changes.values())
        lines.append(f"  Total changes:        {total_changes}")
        lines.append(f"  Skipped (unsafe):     {skipped_count}")
        syntax_pass = sum(1 for v in syntax_results.values() if v)
        syntax_fail = sum(1 for v in syntax_results.values() if not v)
        lines.append(f"  Syntax pass:          {syntax_pass}")
        lines.append(f"  Syntax fail:          {syntax_fail}")
        lines.append("")

        if refactoring_changes:
            lines.append("  Per-file breakdown:")
            for file_path, changes in sorted(refactoring_changes.items()):
                syntax_mark = "OK" if syntax_results.get(file_path, True) else "FAIL"
                lines.append(f"    {len(changes):>3} change(s)  syntax={syntax_mark}  {file_path}")
            lines.append("")

        if syntax_fail > 0:
            lines.append("  WARNING: Some files failed syntax validation after refactoring.")
            lines.append("           Check the full patch file for details.")

        lines.append("=" * 70)
        lines.append("")

        return "\n".join(lines)


def filter_smells(
    smells: List[SmellResult],
    min_severity: Optional[str] = None,
    auto_refactorable_only: bool = False,
) -> Tuple[List[SmellResult], List[SmellResult]]:
    kept = []
    skipped = []
    for smell in smells:
        if min_severity is not None:
            sev_order = SEVERITY_ORDER.get(smell.severity, 2)
            min_order = SEVERITY_ORDER.get(min_severity, 0)
            if sev_order > min_order:
                continue

        if auto_refactorable_only:
            if smell.can_auto_refactor and smell.is_safe_to_refactor:
                kept.append(smell)
            elif smell.can_auto_refactor and not smell.is_safe_to_refactor:
                skipped.append(smell)
            else:
                pass
        else:
            kept.append(smell)

    return kept, skipped