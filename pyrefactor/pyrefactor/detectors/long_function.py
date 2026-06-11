import ast
from typing import List

from .base import BaseDetector
from ..models import SmellResult, SmellType, Location


class LongFunctionDetector(BaseDetector):
    rule_name = "long_function"

    def detect(self, tree: ast.AST, source_code: str, file_path: str) -> List[SmellResult]:
        source_lines = source_code.splitlines()
        results = []

        class FuncVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self_detector, node):
                if self._should_skip_node(node, source_lines):
                    self_detector.generic_visit(node)
                    return

                func_lines = node.end_lineno - node.lineno + 1
                max_lines = self.rule_config.get("max_lines", 30)

                if func_lines > max_lines:
                    suggestion = (
                        f"Function '{node.name}' is {func_lines} lines long "
                        f"(threshold: {max_lines}). Consider splitting it into "
                        f"smaller functions."
                    )
                    results.append(
                        SmellResult(
                            smell_type=SmellType.LONG_FUNCTION,
                            location=Location(
                                file_path=file_path,
                                start_line=node.lineno - 1,
                                end_line=node.end_lineno - 1,
                                entity_name=node.name,
                                entity_type="function",
                            ),
                            message=f"Long function '{node.name}' ({func_lines} lines)",
                            suggestion=suggestion,
                            can_auto_refactor=False,
                            metadata={
                                "function_name": node.name,
                                "lines": func_lines,
                                "threshold": max_lines,
                            },
                        )
                    )
                self_detector.generic_visit(node)

            def visit_ClassDef(self_detector, node):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        if self._should_skip_node(item, source_lines):
                            continue
                        func_lines = item.end_lineno - item.lineno + 1
                        max_lines = self.rule_config.get("max_lines", 30)

                        if func_lines > max_lines:
                            qualified_name = f"{node.name}.{item.name}"
                            suggestion = (
                                f"Method '{qualified_name}' is {func_lines} lines "
                                f"long (threshold: {max_lines}). Consider splitting "
                                f"it into smaller methods."
                            )
                            results.append(
                                SmellResult(
                                    smell_type=SmellType.LONG_FUNCTION,
                                    location=Location(
                                        file_path=file_path,
                                        start_line=item.lineno - 1,
                                        end_line=item.end_lineno - 1,
                                        entity_name=qualified_name,
                                        entity_type="method",
                                    ),
                                    message=f"Long method '{qualified_name}' ({func_lines} lines)",
                                    suggestion=suggestion,
                                    can_auto_refactor=False,
                                    metadata={
                                        "function_name": qualified_name,
                                        "class_name": node.name,
                                        "lines": func_lines,
                                        "threshold": max_lines,
                                    },
                                )
                            )

        FuncVisitor().visit(tree)
        return results