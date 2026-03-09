"""Static analysis: ensure generated Python only calls whitelisted functions."""

import ast
from ..exceptions import ValidationError

ALLOWED_CALLS = {
    "fetch_time_now",
    "fetch_time_today",
    "notify_line",
}


class _Visitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.errors: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        self.errors.append(f"import is not allowed: {ast.unparse(node)}")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.errors.append(f"import is not allowed: {ast.unparse(node)}")

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id not in ALLOWED_CALLS and node.func.id not in {
                "str",
                "int",
                "float",
                "bool",
                "len",
                "range",
            }:
                self.errors.append(f"function call not allowed: {node.func.id}()")
        elif isinstance(node.func, ast.Attribute):
            self.errors.append(f"attribute call not allowed: {ast.unparse(node.func)}()")
        self.generic_visit(node)

    def visit_Global(self, node: ast.Global) -> None:
        self.errors.append("global statement is not allowed")


def validate_python(code: str) -> None:
    """Raise ValidationError if code uses disallowed constructs."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValidationError(f"Syntax error in generated code: {e}") from e

    visitor = _Visitor()
    visitor.visit(tree)

    if visitor.errors:
        raise ValidationError(
            "Generated code contains disallowed operations:\n"
            + "\n".join(f"  - {e}" for e in visitor.errors)
        )
