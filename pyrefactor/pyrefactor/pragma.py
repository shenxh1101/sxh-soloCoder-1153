import ast
import re


def extract_pragmas(node, source_lines):
    pragmas = {"no_smells": False, "no_smell_rules": []}
    if hasattr(node, "decorator_list"):
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name) and decorator.func.id == "no_smells":
                    pragmas["no_smells"] = True
                    for arg in decorator.args:
                        if isinstance(arg, ast.Constant):
                            pragmas["no_smell_rules"].append(arg.value)
                elif isinstance(decorator.func, ast.Attribute):
                    pass
            elif isinstance(decorator, ast.Name) and decorator.id == "no_smells":
                pragmas["no_smells"] = True

    comment_pragmas = _extract_comment_pragmas(node, source_lines)
    if comment_pragmas["no_smells"]:
        pragmas["no_smells"] = True
    pragmas["no_smell_rules"].extend(comment_pragmas["no_smell_rules"])

    return pragmas


def _extract_comment_pragmas(node, source_lines):
    pragmas = {"no_smells": False, "no_smell_rules": []}
    start_line = getattr(node, "lineno", 0)
    if start_line <= 0:
        return pragmas

    check_lines = []
    for line_num in range(max(0, start_line - 2), start_line):
        if line_num < len(source_lines):
            check_lines.append(source_lines[line_num])

    for line in check_lines:
        line = line.strip()
        if not line.startswith("#"):
            continue
        match = re.match(
            r"#\s*pyrefactor:\s*ignore\s*(.*)", line
        )
        if match:
            if not match.group(1):
                pragmas["no_smells"] = True
            else:
                rules = [r.strip() for r in match.group(1).split(",") if r.strip()]
                pragmas["no_smell_rules"].extend(rules)

    return pragmas


def is_smell_ignored(pragmas, rule_name):
    if pragmas.get("no_smells", False):
        return True
    if rule_name in pragmas.get("no_smell_rules", []):
        return True
    return False