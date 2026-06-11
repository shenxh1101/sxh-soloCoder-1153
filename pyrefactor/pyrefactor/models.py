from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


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
            "metadata": self.metadata,
        }


@dataclass
class RefactoringChange:
    original_start_line: int
    original_end_line: int
    original_text: str
    new_text: str
    description: str
    additional_insertions: List[tuple[int, str]] = field(default_factory=list)

    def get_diff(self, file_path: str, original_lines: List[str]) -> str:
        diff_lines = [f"--- {file_path}"]
        diff_lines.append(f"+++ {file_path} (after refactoring)")
        diff_lines.append(f"@@ -{self.original_start_line + 1},{self.original_end_line - self.original_start_line + 1} +...")

        for line_num in range(self.original_start_line, self.original_end_line + 1):
            if 0 <= line_num < len(original_lines):
                diff_lines.append(f"-{original_lines[line_num]}")

        new_lines = self.new_text.splitlines()
        for line in new_lines:
            diff_lines.append(f"+{line}")

        for insert_line, insert_text in self.additional_insertions:
            lines = insert_text.splitlines()
            for line in lines:
                diff_lines.append(f"+{line}")

        return "\n".join(diff_lines)


@dataclass
class RefactoringProposal:
    file_path: str
    original_content: str
    changes: List[RefactoringChange] = field(default_factory=list)
    description: str = ""

    def get_full_new_content(self) -> str:
        original_lines = self.original_content.splitlines()
        insertions = []
        for change in self.changes:
            insertions.extend(
                (pos, text) for pos, text in change.additional_insertions
            )

        insertions.sort(key=lambda x: x[0], reverse=True)

        new_lines = original_lines.copy()
        for change in sorted(self.changes, key=lambda x: x.original_start_line, reverse=True):
            del new_lines[change.original_start_line:change.original_end_line + 1]
            change_lines = change.new_text.splitlines()
            for i, line in enumerate(change_lines):
                new_lines.insert(change.original_start_line + i, line)

        for insert_pos, insert_text in insertions:
            lines = insert_text.splitlines()
            for i, line in enumerate(reversed(lines)):
                new_lines.insert(insert_pos, line)

        return "\n".join(new_lines)

    def get_diff(self) -> str:
        original_lines = self.original_content.splitlines()
        diff_parts = []
        for change in self.changes:
            diff_parts.append(change.get_diff(self.file_path, original_lines))
        return "\n\n".join(diff_parts)


@dataclass
class RefactorReport:
    files_processed: int = 0
    files_with_smells: int = 0
    total_smells: int = 0
    smells_by_type: Dict[SmellType, int] = field(default_factory=dict)
    refactored_count: int = 0
    refactored_changes: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def add_smell(self, smell: SmellResult):
        self.total_smells += 1
        if smell.smell_type not in self.smells_by_type:
            self.smells_by_type[smell.smell_type] = 0
        self.smells_by_type[smell.smell_type] += 1

    def add_refactoring(self, file_path: str, change: RefactoringChange, smell: SmellResult):
        self.refactored_count += 1
        self.refactored_changes.append({
            "file_path": file_path,
            "description": change.description,
            "original_lines": f"{change.original_start_line + 1}-{change.original_end_line + 1}",
            "smell_type": smell.smell_type.value,
        })
