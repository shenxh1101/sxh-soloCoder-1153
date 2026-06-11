import ast
from typing import List

from .base import BaseDetector
from ..models import SmellResult, SmellType, Location


class ComplexConditionDetector(BaseDetector):
    rule_name = "complex_condition"

    def detect(self, tree: ast.AST, source_code: str, file_path: str) -> List[SmellResult]:
        source_lines = source_code.splitlines()
        results = []

        class CondVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self_visitor, node):
                if self._should_skip_node(node, source_lines):
                    self_visitor.generic_visit(node)
                    return
                max_depth = self.rule_config.get("max_depth", 3)
                nodes_to_check = []
                for child in ast.walk(node):
                    if isinstance(child, ast.If) or isinstance(child, ast.While):
                        nodes_to_check.append(child)

                for n in nodes_to_check:
                    depth = self_visitor._compute_nesting_depth(n)
                    if depth > max_depth:
                        entity_name = self_visitor._get_function_name(n, node)
                        suggestion = (
                            f"Complex conditional nesting depth is {depth} "
                            f"(threshold: {max_depth}). Consider extracting nested "
                            f"conditions into separate functions or using early returns "
                            f"to reduce nesting."
                        )
                        results.append(
                            SmellResult(
                                smell_type=SmellType.COMPLEX_CONDITION,
                                location=Location(
                                    file_path=file_path,
                                    start_line=n.lineno - 1,
                                    end_line=getattr(n, "end_lineno", n.lineno) - 1,
                                    entity_name=entity_name,
                                    entity_type=_get_node_type(n),
                                ),
                                message=(
                                    f"Complex condition nesting depth {depth} "
                                    f"in {_get_node_type(n)} at line {n.lineno}"
                                ),
                                suggestion=suggestion,
                                can_auto_refactor=True,
                                metadata={
                                    "depth": depth,
                                    "threshold": max_depth,
                                    "function_name": entity_name,
                                    "node_type": _get_node_type(n),
                                },
                            )
                        )
                self_visitor.generic_visit(node)

            def _compute_nesting_depth(self_detector, node):
                depth = 0
                current = node
                while current is not None:
                    if isinstance(current, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                        depth += 1
                    current = getattr(current, "parent", None)
                return depth

            def _get_function_name(self_detector, node, func_node):
                if isinstance(func_node, ast.FunctionDef):
                    return func_node.name
                return "unknown"

        self._add_parent_links(tree)
        CondVisitor().visit(tree)
        return results

    @staticmethod
    def _add_parent_links(tree):
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child.parent = node


def _get_node_type(node):
    if isinstance(node, ast.If):
        return "if-statement"
    elif isinstance(node, ast.While):
        return "while-loop"
    return type(node).__name__