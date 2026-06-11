import re
import ast
from typing import List, Tuple, Dict
from difflib import SequenceMatcher

from .base import BaseDetector
from ..models import SmellResult, SmellType, Location


class DuplicateCodeDetector(BaseDetector):
    rule_name = "duplicate_code"

    def detect(self, tree: ast.AST, source_code: str, file_path: str) -> List[SmellResult]:
        results = []
        source_lines = source_code.splitlines()
        self._source_lines = source_lines
        min_block_lines = self.rule_config.get("min_block_lines", 6)
        similarity_threshold = self.rule_config.get("similarity_threshold", 0.8)

        blocks = self._extract_code_blocks(source_lines)
        pairs = self._find_similar_pairs(blocks, min_block_lines, similarity_threshold)

        for block1, block2, similarity in pairs:
            if similarity >= similarity_threshold:
                suggestion = (
                    f"Found similar code blocks with {similarity:.0%} similarity. "
                    f"Consider extracting the common logic into a shared function."
                )
                results.append(
                    SmellResult(
                        smell_type=SmellType.DUPLICATE_CODE,
                        location=Location(
                            file_path=file_path,
                            start_line=block1[0],
                            end_line=block1[1],
                            entity_name=f"Block at line {block1[0] + 1}",
                            entity_type="code_block",
                        ),
                        message=(
                            f"Duplicate code: block at lines {block1[0] + 1}-{block1[1] + 1} "
                            f"is {similarity:.0%} similar to block at lines "
                            f"{block2[0] + 1}-{block2[1] + 1}"
                        ),
                        suggestion=suggestion,
                        can_auto_refactor=False,
                        metadata={
                            "similarity": similarity,
                            "block1_start": block1[0],
                            "block1_end": block1[1],
                            "block2_start": block2[0],
                            "block2_end": block2[1],
                        },
                    )
                )
        return results

    def _extract_code_blocks(self, source_lines: List[str]) -> List[Tuple[int, int]]:
        blocks = []
        i = 0
        while i < len(source_lines):
            line = source_lines[i]
            stripped = line.strip()

            if stripped and not stripped.startswith("#"):
                if stripped.startswith("def ") or stripped.startswith("class "):
                    func_start = i
                    func_header_end = i
                    i += 1
                    while i < len(source_lines):
                        current = source_lines[i]
                        current_stripped = current.strip()
                        if current_stripped and (current_stripped.startswith("def ") or current_stripped.startswith("class ")):
                            break
                        indent = len(current) - len(current.lstrip())
                        if current_stripped and indent == 0:
                            break
                        i += 1
                    func_end = i - 1
                    if func_end > func_header_end:
                        blocks.append((func_header_end + 1, func_end))
                    continue

            if stripped and not stripped.startswith("#"):
                block_start = i
                base_indent = len(line) - len(line.lstrip())
                i += 1
                while i < len(source_lines):
                    current = source_lines[i]
                    current_stripped = current.strip()
                    if not current_stripped:
                        i += 1
                        continue
                    current_indent = len(current) - len(current.lstrip())
                    if current_indent <= base_indent and current_stripped:
                        break
                    i += 1
                block_end = i - 1
                block_lines = block_end - block_start + 1
                if block_lines >= 4:
                    blocks.append((block_start, block_end))
            else:
                i += 1

        return blocks

    def _find_similar_pairs(self, blocks, min_block_lines, similarity_threshold):
        max_comparisons = self.rule_config.get("max_comparisons", 5000)
        pairs = []
        source_lines_cache = self._source_lines

        count = 0
        for i in range(len(blocks)):
            for j in range(i + 1, len(blocks)):
                if count >= max_comparisons:
                    break
                b1 = blocks[i]
                b2 = blocks[j]
                lines_i = b1[1] - b1[0] + 1
                lines_j = b2[1] - b2[0] + 1
                if lines_i < min_block_lines or lines_j < min_block_lines:
                    continue
                similarity = self._compute_similarity(source_lines_cache, b1, b2)
                if similarity >= similarity_threshold:
                    pairs.append((b1, b2, similarity))
                count += 1

        return pairs

    def _compute_similarity(self, source_lines, block1: Tuple[int, int], block2: Tuple[int, int]) -> float:
        text1 = self._get_block_text(source_lines, block1)
        text2 = self._get_block_text(source_lines, block2)
        norm1 = self._normalize_code(text1)
        norm2 = self._normalize_code(text2)
        return SequenceMatcher(None, norm1, norm2).ratio()

    def _get_block_text(self, source_lines, block):
        return "\n".join(source_lines[block[0]:block[1] + 1])

    def _normalize_code(self, code: str) -> str:
        code = re.sub(r'"""[\s\S]*?"""', '""', code)
        code = re.sub(r"'''[\s\S]*?'''", "''", code)
        code = re.sub(r"#.*$", "", code, flags=re.MULTILINE)
        code = re.sub(r"\s+", " ", code)
        code = re.sub(
            r'"[^"]*"', '"STR"', code
        )
        code = re.sub(
            r"'[^']*'", "'STR'", code
        )
        code = re.sub(r"\b\d+\b", "N", code)
        code = re.sub(r"\b\d+\.\d+\b", "N.N", code)
        return code.strip()