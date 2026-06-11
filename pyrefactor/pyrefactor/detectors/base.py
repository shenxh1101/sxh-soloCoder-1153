import ast
from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import SmellResult
from ..pragma import extract_pragmas, is_smell_ignored


class BaseDetector(ABC):
    rule_name: str = ""

    def __init__(self, config: dict):
        self.config = config
        self.rule_config = config.get("rules", {}).get(self.rule_name, {})

    def is_enabled(self) -> bool:
        return self.rule_config.get("enabled", False)

    @abstractmethod
    def detect(self, tree: ast.AST, source_code: str, file_path: str) -> List[SmellResult]:
        pass

    def _should_skip_node(self, node, source_lines):
        pragmas = extract_pragmas(node, source_lines)
        return is_smell_ignored(pragmas, self.rule_name)