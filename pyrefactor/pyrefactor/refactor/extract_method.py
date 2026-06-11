from typing import List, Tuple, Set, Dict, Optional
import ast
from collections import defaultdict

from ..models import RefactoringChange


class ExtractMethodRefactor:
    def extract(
        self,
        lines: List[str],
        start_line: int,
        end_line: int,
        new_method_name: str,
        indent_level: int = 0
    ) -> RefactoringChange:
        original_text_lines = lines[start_line:end_line + 1]
        if len(original_text_lines) > 0:
            base_indent = len(original_text_lines[0]) - len(original_text_lines[0].lstrip())
            extracted_lines = []
            for line in original_text_lines:
                if len(line.strip()) > 0:
                    stripped_line = line.lstrip()
                    if len(stripped_line) < len(line):
                        line_indent = len(line) - len(stripped_line)
                        line = " " * max(0, line_indent - base_indent) + stripped_line
                extracted_lines.append(line)
        else:
            extracted_lines = original_text_lines

        original_text = "\n".join(extracted_lines)

        indent = "    " * indent_level

        tree = ast.parse(original_text)

        defined_vars, used_vars = self._analyze_variables(tree)
        defined_in_block = defined_vars - used_vars
        used_outside = self._find_used_outside(defined_vars, used_vars)
        params = list(used_outside)
        params.sort()

        if not new_method_name.strip():
            new_method_name = "extracted_method"

        param_str = ", ".join(params)
        new_call = f"{indent}{new_method_name}({param_str})"

        method_lines = [f"{indent}def {new_method_name}({param_str}):"]
        for line in extracted_lines:
            if self._is_assign_to_return_variable(line, defined_in_block):
                pass
            else:
                method_lines.append("    " + line)

        if defined_in_block:
            return_vars = ", ".join(sorted(defined_in_block))
            method_lines.append(f"{indent}    return {return_vars}")

        method_text = "\n".join(method_lines)

        new_body_lines = [new_call]
        if len(defined_in_block) == 1:
            var_name = next(iter(defined_in_block))
            new_body_lines[0] = f"{indent}{var_name} = {new_method_name}({param_str})"
        elif len(defined_in_block) > 1:
            vars_str = ", ".join(sorted(defined_in_block))
            new_body_lines[0] = f"{indent}{vars_str} = {new_method_name}({param_str})"

        new_text = "\n".join(new_body_lines)

        insert_pos = start_line - 1
        if indent_level > 0:
            pass

        change = RefactoringChange(
            original_start_line=start_line,
            original_end_line=end_line,
            original_text=original_text,
            new_text=new_text,
            description=f"Extract method {new_method_name}",
            additional_insertions=[
                (start_line, "\n" + method_text + "\n")
            ]
        )

        return change

    def _analyze_variables(self, tree: ast.AST) -> Tuple[Set[str], Set[str]]:
        defined = set()
        used = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Store):
                    defined.add(node.id)
                if isinstance(node.ctx, ast.Load):
                    used.add(node.id)

            elif isinstance(node, ast.FunctionDef):
                for arg in node.args.args:
                    defined.add(arg.arg)

        return defined, used

    def _find_used_outside(self, defined_in_block, all_used_in_block):
        return all_used_in_block - defined_in_block

    def _is_assign_to_return_variable(self, line: str, return_vars: Set[str]) -> bool:
        if not return_vars:
            return False
        line = line.strip()
        for var in return_vars:
            if line.startswith(var + " =") or line.startswith(var + ":"):
                return True
        return False