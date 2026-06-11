import re
import ast
from typing import List, Tuple, Set, Optional, Dict

from ..models import RefactoringChange

UNSAFE_NODES = (ast.Return, ast.Break, ast.Continue, ast.Yield, ast.YieldFrom)


class ExtractMethodRefactor:

    def check_safety(self, lines: List[str], start_line: int, end_line: int) -> Tuple[bool, List[str]]:
        original_text_lines = [l.rstrip("\n") for l in lines[start_line:end_line + 1]]

        base_indent = 0
        if original_text_lines:
            first = original_text_lines[0]
            base_indent = len(first) - len(first.lstrip())

        dedented_lines = []
        for line in original_text_lines:
            if line.strip():
                if len(line) >= base_indent:
                    dedented_lines.append(line[base_indent:])
                else:
                    dedented_lines.append(line.lstrip())
            else:
                dedented_lines.append("")

        dedented_text = "\n".join(dedented_lines)
        try:
            tree = ast.parse(dedented_text)
        except SyntaxError:
            return False, ["Cannot parse the selected code block."]

        warnings = []

        class UnsafeVisitor(ast.NodeVisitor):
            def __init__(self):
                self.found_return = False
                self.found_break = False
                self.found_continue = False
                self.found_yield = False
                self.conditional_assigns: Dict[str, bool] = {}
                self.unconditional_assigns: set = set()

            def visit_Return(self_detector, node):
                self_detector.found_return = True
                self_detector.generic_visit(node)

            def visit_Break(self_detector, node):
                self_detector.found_break = True
                self_detector.generic_visit(node)

            def visit_Continue(self_detector, node):
                self_detector.found_continue = True
                self_detector.generic_visit(node)

            def visit_Yield(self_detector, node):
                self_detector.found_yield = True
                self_detector.generic_visit(node)

            def visit_YieldFrom(self_detector, node):
                self_detector.found_yield = True
                self_detector.generic_visit(node)

        visitor = UnsafeVisitor()
        visitor.visit(tree)

        if visitor.found_return:
            warnings.append(
                "Contains 'return' — extracting into a nested function will change "
                "control flow: the return would only exit the nested function, "
                "not the original enclosing function."
            )
        if visitor.found_break:
            warnings.append(
                "Contains 'break' — cannot be used inside a nested function "
                "(will cause SyntaxError)."
            )
        if visitor.found_continue:
            warnings.append(
                "Contains 'continue' — cannot be used inside a nested function "
                "(will cause SyntaxError)."
            )
        if visitor.found_yield:
            warnings.append(
                "Contains 'yield' — extracting into a nested function will change "
                "the generator semantics of the enclosing function."
            )

        _def_vars, _use_vars, updated_vars = self._analyze_variables(tree)
        if updated_vars:
            updated_list = sorted(updated_vars)
            var_labels = ", ".join(f"'{v}'" for v in updated_list)
            warnings.append(
                f"Conditional variable update detected: {var_labels} — "
                f"extracting would overwrite the existing value when the "
                f"old value should be preserved. Skipping auto-refactor."
            )

        is_safe = len(warnings) == 0
        return is_safe, warnings

    def extract(
        self,
        lines: List[str],
        start_line: int,
        end_line: int,
        new_method_name: str,
        indent_level: int = 0
    ) -> RefactoringChange:
        original_text_lines = [l.rstrip("\n") for l in lines[start_line:end_line + 1]]

        base_indent = 0
        if original_text_lines:
            first = original_text_lines[0]
            base_indent = len(first) - len(first.lstrip())

        dedented_lines = []
        for line in original_text_lines:
            if line.strip():
                if len(line) >= base_indent:
                    dedented_lines.append(line[base_indent:])
                else:
                    dedented_lines.append(line.lstrip())
            else:
                dedented_lines.append("")

        dedented_text = "\n".join(dedented_lines)
        try:
            tree = ast.parse(dedented_text)
        except SyntaxError:
            tree = ast.parse("pass")

        defined_vars, used_vars, updated_vars = self._analyze_variables(tree)
        defined_in_block = defined_vars - used_vars
        used_outside = used_vars - defined_vars

        params = sorted(self._param_names(used_outside | updated_vars))

        if not new_method_name.strip():
            new_method_name = "extracted_method"

        param_str = ", ".join(params)

        call_indent = " " * base_indent
        method_indent = call_indent
        body_indent = call_indent + "    "

        method_lines = [f"{method_indent}def {new_method_name}({param_str}):"]
        if defined_in_block:
            for var in sorted(defined_in_block):
                method_lines.append(f"{body_indent}{var} = None")
        for dline in dedented_lines:
            method_lines.append(f"{body_indent}{dline}")

        return_vars_set = defined_in_block | updated_vars
        if return_vars_set:
            return_vars_str = ", ".join(sorted(return_vars_set))
            method_lines.append(f"{body_indent}return {return_vars_str}")

        method_text = "\n".join(method_lines)

        return_list = sorted(return_vars_set)
        if len(return_list) == 1:
            var_name = return_list[0]
            call_text = f"{call_indent}{var_name} = {new_method_name}({param_str})"
        elif len(return_list) > 1:
            vars_str = ", ".join(return_list)
            call_text = f"{call_indent}{vars_str} = {new_method_name}({param_str})"
        else:
            call_text = f"{call_indent}{new_method_name}({param_str})"

        original_text = "\n".join(original_text_lines)

        is_safe, safety_warnings = self.check_safety(lines, start_line, end_line)

        change = RefactoringChange(
            original_start_line=start_line,
            original_end_line=end_line,
            original_text=original_text,
            new_text=call_text,
            description=f"Extract method '{new_method_name}'",
            additional_insertions=[
                (start_line, method_text + "\n")
            ],
            safety_warnings=safety_warnings,
            is_safe=is_safe,
        )

        return change

    def _analyze_variables(self, tree: ast.AST) -> Tuple[Set[str], Set[str], Set[str]]:
        defined: Set[str] = set()
        used: Set[str] = set()
        defined_first_line: Dict[str, int] = {}
        used_first_line: Dict[str, int] = {}

        def _get_line(n) -> int:
            return getattr(n, "lineno", 0)

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                name = node.id
                if isinstance(node.ctx, ast.Store):
                    defined.add(name)
                    if name not in defined_first_line:
                        defined_first_line[name] = _get_line(node)
                elif isinstance(node.ctx, ast.Load):
                    used.add(name)
                    if name not in used_first_line:
                        used_first_line[name] = _get_line(node)
            elif isinstance(node, ast.Attribute):
                attr_name = self._get_attr_name(node)
                if attr_name:
                    if isinstance(node.ctx, ast.Store):
                        defined.add(attr_name)
                        if attr_name not in defined_first_line:
                            defined_first_line[attr_name] = _get_line(node)
                    elif isinstance(node.ctx, ast.Load):
                        used.add(attr_name)
                        if attr_name not in used_first_line:
                            used_first_line[attr_name] = _get_line(node)
            elif isinstance(node, ast.AugAssign):
                tgt = node.target
                tgt_name = None
                if isinstance(tgt, ast.Name):
                    tgt_name = tgt.id
                elif isinstance(tgt, ast.Attribute):
                    tgt_name = self._get_attr_name(tgt)
                if tgt_name:
                    used.add(tgt_name)
                    used_first_line.setdefault(tgt_name, _get_line(node))
            elif isinstance(node, ast.FunctionDef):
                for arg in node.args.args:
                    defined.add(arg.arg)
            elif isinstance(node, ast.arg):
                pass

        self_builtins = {"self", "cls", "True", "False", "None", "print", "range", "len",
                          "int", "str", "float", "list", "dict", "set", "tuple", "bool"}
        used = used - self_builtins

        raw_updated = defined & used
        updated_vars: Set[str] = set()
        for var in raw_updated:
            def_line = defined_first_line.get(var, 0)
            use_line = used_first_line.get(var, 0)
            if use_line <= def_line:
                updated_vars.add(var)

        return defined, used, updated_vars

    def _get_attr_name(self, node: ast.Attribute) -> str:
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        else:
            return ""
        return ".".join(reversed(parts))

    @staticmethod
    def _param_names(var_set: Set[str]) -> Set[str]:
        result: Set[str] = set()
        for var in var_set:
            if "." in var:
                result.add(var.split(".", 1)[0])
            else:
                result.add(var)
        return result

    def _find_used_outside(self, defined_in_block: Set[str], all_used_in_block: Set[str]) -> Set[str]:
        return all_used_in_block - defined_in_block

    def _is_assign_to_return_variable(self, line: str, return_vars: Set[str]) -> bool:
        if not return_vars:
            return False
        stripped = line.strip()
        for var in return_vars:
            if stripped.startswith(var + " =") or stripped.startswith(var + ":"):
                return True
        return False