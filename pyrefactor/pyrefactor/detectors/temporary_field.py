import ast
from typing import List, Set

from .base import BaseDetector
from ..models import SmellResult, SmellType, Location


class TemporaryFieldDetector(BaseDetector):
    rule_name = "temporary_field"

    def detect(self, tree: ast.AST, source_code: str, file_path: str) -> List[SmellResult]:
        source_lines = source_code.splitlines()
        results = []

        class ClassVisitor(ast.NodeVisitor):
            def visit_ClassDef(self_visitor, node):
                if self._should_skip_node(node, source_lines):
                    self_visitor.generic_visit(node)
                    return

                instance_attrs = self_visitor._collect_instance_assignments(node)
                used_in_methods = self_visitor._collect_attr_usage(node)

                method_attrs_map = {}
                for method in node.body:
                    if isinstance(method, ast.FunctionDef):
                        method.name = method.name
                        assigned = self_visitor._get_attrs_assigned_in(method)
                        used = self_visitor._get_attrs_used_in(method)
                        method_attrs_map[method.name] = {
                            "assigns": assigned,
                            "uses": used,
                        }

                temporary_fields = self_visitor._find_temporary_fields(
                    instance_attrs, used_in_methods, node
                )

                for field_name, info in temporary_fields.items():
                    suggestion = (
                        f"Instance attribute 'self.{field_name}' only appears as "
                        f"a data-passing variable. Consider passing it as a "
                        f"parameter directly or using local variables instead."
                    )
                    assign_method = info.get("assign_method", "unknown")
                    results.append(
                        SmellResult(
                            smell_type=SmellType.TEMPORARY_FIELD,
                            location=Location(
                                file_path=file_path,
                                start_line=node.lineno - 1,
                                end_line=node.end_lineno - 1,
                                entity_name=node.name,
                                entity_type="class",
                            ),
                            message=(
                                f"Temporary field 'self.{field_name}' in class "
                                f"'{node.name}' (used only for data passing, "
                                f"assigned in '{assign_method}')"
                            ),
                            suggestion=suggestion,
                            can_auto_refactor=False,
                            metadata={
                                "field_name": field_name,
                                "class_name": node.name,
                                "assign_method": assign_method,
                            },
                        )
                    )

                self_visitor.generic_visit(node)

            def _collect_instance_assignments(self_detector, class_node):
                attrs = {}
                for item in class_node.body:
                    if isinstance(item, ast.FunctionDef):
                        for child in ast.walk(item):
                            if isinstance(child, ast.Assign):
                                for target in child.targets:
                                    if isinstance(target, ast.Attribute):
                                        if isinstance(target.value, ast.Name) and target.value.id == "self":
                                            attr_name = target.attr
                                            if attr_name not in attrs:
                                                attrs[attr_name] = []
                                            attrs[attr_name].append({
                                                "method": item.name,
                                                "line": child.lineno,
                                            })
                            elif isinstance(child, ast.AnnAssign):
                                target = child.target
                                if isinstance(target, ast.Attribute):
                                    if isinstance(target.value, ast.Name) and target.value.id == "self":
                                        attr_name = target.attr
                                        if attr_name not in attrs:
                                            attrs[attr_name] = []
                                        attrs[attr_name].append({
                                            "method": item.name,
                                            "line": child.lineno,
                                        })
                return attrs

            def _collect_attr_usage(self_detector, class_node):
                usage = {}
                for item in class_node.body:
                    if isinstance(item, ast.FunctionDef):
                        for child in ast.walk(item):
                            if isinstance(child, ast.Attribute):
                                if isinstance(child.value, ast.Name) and child.value.id == "self":
                                    attr_name = child.attr
                                    if not isinstance(child.ctx, ast.Store):
                                        if attr_name not in usage:
                                            usage[attr_name] = []
                                        usage[attr_name].append({
                                            "method": item.name,
                                            "line": child.lineno,
                                        })
                return usage

            def _get_attrs_assigned_in(self_detector, func_node):
                attrs = set()
                for child in ast.walk(func_node):
                    if isinstance(child, ast.Assign):
                        for target in child.targets:
                            if isinstance(target, ast.Attribute):
                                if isinstance(target.value, ast.Name) and target.value.id == "self":
                                    attrs.add(target.attr)
                    elif isinstance(child, ast.AnnAssign):
                        target = child.target
                        if isinstance(target, ast.Attribute):
                            if isinstance(target.value, ast.Name) and target.value.id == "self":
                                attrs.add(target.attr)
                return attrs

            def _get_attrs_used_in(self_detector, func_node):
                attrs = set()
                for child in ast.walk(func_node):
                    if isinstance(child, ast.Attribute):
                        if isinstance(child.value, ast.Name) and child.value.id == "self":
                            if not isinstance(child.ctx, ast.Store):
                                attrs.add(child.attr)
                return attrs

            def _find_temporary_fields(self_detector, instance_attrs, usage, class_node):
                temporary = {}
                for attr_name, assignments in instance_attrs.items():
                    usage_count_total = 0
                    non_init_methods = set()
                    init_methods = set()

                    for a in assignments:
                        if a["method"] == "__init__":
                            init_methods.add(a["method"])
                        else:
                            non_init_methods.add(a["method"])

                    if attr_name in usage:
                        for u in usage[attr_name]:
                            usage_count_total += 1

                    produced_in = list(non_init_methods)
                    consumed_in = []
                    if attr_name in usage:
                        consumed_in = [u["method"] for u in usage[attr_name]]

                    if usage_count_total > 5:
                        continue

                    if produced_in and consumed_in:
                        all_methods = set(produced_in + consumed_in)
                        if len(all_methods) <= 2 and len(usage.get(attr_name, [])) <= 3:
                            temporary[attr_name] = {
                                "assign_method": produced_in[0] if produced_in else "__init__",
                                "used_methods": consumed_in,
                                "usage_count": usage_count_total,
                            }

                return temporary

        ClassVisitor().visit(tree)
        return results