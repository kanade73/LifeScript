"""Static analysis: ensure generated Python only calls whitelisted functions."""

import ast

from ..exceptions import ValidationError
from ..plugins import get_allowed_names

# Built-in functions that are safe to call
_SAFE_BUILTINS = {"str", "int", "float", "bool", "len", "range", "list", "dict", "print"}

# Dangerous names that must never appear
_FORBIDDEN_NAMES = {
    "exec",
    "eval",
    "compile",
    "__import__",
    "open",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
    "dir",
    "breakpoint",
    "exit",
    "quit",
    "input",
    "memoryview",
    "type",
    "super",
}


class _Visitor(ast.NodeVisitor):
    def __init__(self, allowed_calls: set[str]) -> None:
        self.errors: list[str] = []
        self._allowed = allowed_calls | _SAFE_BUILTINS

    def visit_Import(self, node: ast.Import) -> None:
        self.errors.append(f"import文は使用できません: {ast.unparse(node)}")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.errors.append(f"import文は使用できません: {ast.unparse(node)}")

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in _FORBIDDEN_NAMES:
                self.errors.append(f"禁止された関数の呼び出し: {name}()")
            elif name not in self._allowed:
                self.errors.append(f"許可されていない関数の呼び出し: {name}()")
        elif isinstance(node.func, ast.Attribute):
            # Allow safe attribute calls like str.format, dict.get, etc.
            # But block potentially dangerous ones
            attr_name = node.func.attr
            if attr_name.startswith("_"):
                self.errors.append(
                    f"プライベート属性の呼び出しは禁止されています: {ast.unparse(node.func)}()"
                )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in _FORBIDDEN_NAMES:
            self.errors.append(f"禁止された名前の参照: {node.id}")
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        self.errors.append("global文は使用できません")

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.errors.append("nonlocal文は使用できません")

    def visit_Delete(self, node: ast.Delete) -> None:
        self.errors.append("del文は使用できません")


def validate_python(code: str) -> None:
    """Raise ValidationError if code uses disallowed constructs."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValidationError(f"生成されたコードに構文エラーがあります: {e}") from e

    allowed = get_allowed_names()
    visitor = _Visitor(allowed)
    visitor.visit(tree)

    if visitor.errors:
        raise ValidationError(
            "生成されたコードに許可されていない操作が含まれています:\n"
            + "\n".join(f"  - {e}" for e in visitor.errors)
        )
