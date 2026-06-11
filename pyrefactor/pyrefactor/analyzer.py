import ast
import os
from typing import List, Optional
from pathlib import Path

from .config import load_config, is_rule_enabled
from .detectors import (
    LongFunctionDetector,
    DuplicateCodeDetector,
    ComplexConditionDetector,
    TemporaryFieldDetector,
)
from .models import SmellResult, RefactoringChange, RefactoringProposal, RefactorReport, SmellType
from .pragma import extract_pragmas, is_smell_ignored
from .refactor import ExtractMethodRefactor


class Analyzer:
    def __init__(self, config_path: Optional[str] = None):
        self.config = load_config(config_path)
        self.detectors = []
        self._init_detectors()

    def _init_detectors(self):
        self.detectors.clear()
        if is_rule_enabled(self.config, "long_function"):
            self.detectors.append(LongFunctionDetector(self.config))
        if is_rule_enabled(self.config, "duplicate_code"):
            self.detectors.append(DuplicateCodeDetector(self.config))
        if is_rule_enabled(self.config, "complex_condition"):
            self.detectors.append(ComplexConditionDetector(self.config))
        if is_rule_enabled(self.config, "temporary_field"):
            self.detectors.append(TemporaryFieldDetector(self.config))

    def analyze_file(self, file_path: str) -> List[SmellResult]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()
        except (IOError, UnicodeDecodeError) as e:
            return []

        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return []

        results = []
        for detector in self.detectors:
            try:
                detector_results = detector.detect(tree, source_code, file_path)
                results.extend(detector_results)
            except Exception:
                continue

        return results

    def analyze_directory(self, directory: str) -> List[SmellResult]:
        all_results = []
        ignore_patterns = self.config.get("ignore_patterns", [])
        skip_untracked = self.config.get("vcs", {}).get("skip_untracked", True)

        untracked = set()
        if skip_untracked:
            from .vcs import get_untracked_files, is_git_repository
            if is_git_repository(directory):
                untracked = get_untracked_files(directory)

        py_files = list(Path(directory).rglob("*.py"))
        for py_file in py_files:
            file_path_str = str(py_file)

            should_skip = False
            for pattern in ignore_patterns:
                if pattern.startswith("*"):
                    if py_file.name.startswith(pattern[1:]) or py_file.match(pattern):
                        should_skip = True
                        break
                elif pattern in file_path_str.replace("\\", "/"):
                    should_skip = True
                    break

            if should_skip:
                continue

            if skip_untracked and untracked:
                norm_path = os.path.normpath(file_path_str)
                if norm_path in untracked:
                    continue

            results = self.analyze_file(file_path_str)
            all_results.extend(results)

        return all_results

    def create_refactoring(
        self, smell: SmellResult, file_path: str
    ) -> Optional[RefactoringChange]:
        if not smell.can_auto_refactor:
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_lines = f.readlines()
        except (IOError, UnicodeDecodeError):
            return None

        if smell.smell_type == SmellType.COMPLEX_CONDITION:
            return self._extract_method_for_condition(smell, source_lines)

        return None

    def _extract_method_for_condition(self, smell, source_lines):
        start = smell.location.start_line
        end = smell.location.end_line

        refactor = ExtractMethodRefactor()
        method_name = f"_extracted_condition_{start + 1}"

        change = refactor.extract(
            lines=source_lines,
            start_line=start,
            end_line=end,
            new_method_name=method_name,
        )

        change.description = (
            f"Extract complex condition from line {start + 1} to {end + 1} "
            f"into method '{method_name}'"
        )

        return change

    def _detect_indent_level(self, lines, line_num):
        if line_num < len(lines):
            line = lines[line_num]
            stripped = line.lstrip()
            if stripped != line:
                spaces = len(line) - len(stripped)
                return spaces // 4
        return 0