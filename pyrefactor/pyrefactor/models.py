import difflib
import ast
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum


SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


class SmellType(Enum):
    LONG_FUNCTION = "long_function"
    DUPLICATE_CODE = "duplicate_code"
    COMPLEX_CONDITION = "complex_condition"
    TEMPORARY_FIELD = "temporary_field"


@dataclass
class Location:
    file_path: str
    start_line: int
    end_line: Optional[int] = None
    column_start: Optional[int] = None
    column_end: Optional[int] = None
    entity_name: Optional[str] = None
    entity_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "column_start": self.column_start,
            "column_end": self.column_end,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
        }


@dataclass
class SmellResult:
    smell_type: SmellType
    location: Location
    message: str
    severity: str = "warning"
    suggestion: Optional[str] = None
    refactor_suggestion: Optional[str] = None
    can_auto_refactor: bool = False
    is_safe_to_refactor: bool = True
    safety_warnings: List[str] = field(default_factory=list)
    skip_reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "smell_type": self.smell_type.value,
            "location": self.location.to_dict(),
            "message": self.message,
            "severity": self.severity,
            "suggestion": self.suggestion,
            "refactor_suggestion": self.refactor_suggestion,
            "can_auto_refactor": self.can_auto_refactor,
            "is_safe_to_refactor": self.is_safe_to_refactor,
            "safety_warnings": self.safety_warnings,
            "skip_reason": self.skip_reason,
            "metadata": self.metadata,
        }


@dataclass
class RefactoringChange:
    original_start_line: int
    original_end_line: int
    original_text: str
    new_text: str
    description: str
    additional_insertions: List[Tuple[int, str]] = field(default_factory=list)
    safety_warnings: List[str] = field(default_factory=list)
    is_safe: bool = True

    def to_summary(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "original_lines": f"{self.original_start_line + 1}-{self.original_end_line + 1}",
            "original_text": self.original_text,
            "new_text": self.new_text,
            "insertions": [
                {"position": pos, "text": text}
                for pos, text in self.additional_insertions
            ],
            "safety_warnings": self.safety_warnings,
            "is_safe": self.is_safe,
        }


@dataclass
class RefactoringProposal:
    file_path: str
    original_content: str
    changes: List[RefactoringChange] = field(default_factory=list)
    description: str = ""

    def get_full_new_content(self) -> str:
        original_lines = self.original_content.splitlines()

        inserts_before: Dict[int, List[str]] = {}
        for change in self.changes:
            for pos, text in change.additional_insertions:
                if pos not in inserts_before:
                    inserts_before[pos] = []
                inserts_before[pos].append(text)

        replacements: Dict[tuple, str] = {}
        for change in self.changes:
            replacements[(change.original_start_line, change.original_end_line)] = change.new_text

        new_lines = []
        i = 0
        while i < len(original_lines):
            if i in inserts_before:
                for text in inserts_before[i]:
                    for txt_line in text.splitlines():
                        new_lines.append(txt_line)

            found_replacement = False
            for (start, end), new_text in replacements.items():
                if i == start:
                    new_lines.extend(new_text.splitlines())
                    i = end + 1
                    found_replacement = True
                    break

            if not found_replacement:
                new_lines.append(original_lines[i])
                i += 1

        return "\n".join(new_lines)

    def get_diff(self) -> str:
        original_lines = self.original_content.splitlines()
        new_content = self.get_full_new_content()
        new_lines = new_content.splitlines()
        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=self.file_path,
            tofile=self.file_path + " (refactored)",
            lineterm="",
        )
        return "\n".join(diff)

    def validate_syntax(self) -> Tuple[bool, str]:
        try:
            new_content = self.get_full_new_content()
            ast.parse(new_content)
            compile(new_content, self.file_path, "exec")
            return True, ""
        except SyntaxError as e:
            return False, f"SyntaxError at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, str(e)


@dataclass
class RefactorReport:
    files_processed: int = 0
    files_with_smells: int = 0
    total_smells: int = 0
    smells_by_type: Dict[SmellType, int] = field(default_factory=dict)
    refactored_count: int = 0
    refactored_changes: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    skipped_unsafe: int = 0
    skipped_items: List[Dict[str, Any]] = field(default_factory=list)
    syntax_validation_failures: List[Dict[str, Any]] = field(default_factory=list)

    def add_smell(self, smell: SmellResult):
        self.total_smells += 1
        if smell.smell_type not in self.smells_by_type:
            self.smells_by_type[smell.smell_type] = 0
        self.smells_by_type[smell.smell_type] += 1

    def add_refactoring(self, file_path: str, change: RefactoringChange, smell: SmellResult, diff_text: str = "", syntax_valid: bool = True):
        self.refactored_count += 1
        self.refactored_changes.append({
            "file_path": file_path,
            "description": change.description,
            "original_lines": f"{change.original_start_line + 1}-{change.original_end_line + 1}",
            "smell_type": smell.smell_type.value,
            "original_text": change.original_text,
            "new_text": change.new_text,
            "insertions": [
                {"position": pos, "text": text}
                for pos, text in change.additional_insertions
            ],
            "diff": diff_text,
            "safety_warnings": change.safety_warnings,
            "is_safe": change.is_safe,
            "syntax_valid": syntax_valid,
        })

    def add_skipped(self, smell: SmellResult):
        self.skipped_items.append({
            "file_path": smell.location.file_path,
            "smell_type": smell.smell_type.value,
            "line": smell.location.start_line + 1,
            "reason": smell.skip_reason or "; ".join(smell.safety_warnings) or "unsafe to refactor",
        })

    def add_syntax_failure(self, file_path: str, error_msg: str):
        self.syntax_validation_failures.append({
            "file_path": file_path,
            "error": error_msg,
        })