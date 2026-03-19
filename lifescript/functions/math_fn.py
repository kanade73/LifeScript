"""math.*() --- 数学関数。

math_calc(expression) で安全に数式を評価する。
math_round(value, digits) で四捨五入する。
"""

from __future__ import annotations

import ast
import operator

from .. import log_queue

# 安全に許可する演算子
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.FloorDiv: operator.floordiv,
}


def _safe_eval(node: ast.AST) -> float:
    """ASTノードを再帰的に評価する。"""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _OPERATORS:
            raise ValueError(f"未対応の演算子: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        if op_type is ast.Div and right == 0:
            raise ValueError("ゼロ除算です")
        return _OPERATORS[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _OPERATORS:
            raise ValueError(f"未対応の単項演算子: {op_type.__name__}")
        return _OPERATORS[op_type](_safe_eval(node.operand))
    raise ValueError(f"未対応の式要素: {type(node).__name__}")


def math_calc(expression: str) -> float:
    """安全に数式を評価する。

    Args:
        expression: 数式文字列（例: "1+1", "3*4+2", "2**10"）

    Returns:
        計算結果（float）
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval(tree)
        log_queue.log("math", f"計算: {expression} = {result}")
        return result
    except Exception as e:
        log_queue.log("math", f"計算エラー: {expression} - {e}", "ERROR")
        raise ValueError(f"数式の評価に失敗しました: {e}") from e


def math_round(value: float, digits: int = 0) -> float:
    """値を四捨五入する。

    Args:
        value: 四捨五入する値
        digits: 小数点以下の桁数（デフォルト0）

    Returns:
        四捨五入された値
    """
    result = round(float(value), digits)
    log_queue.log("math", f"四捨五入: {value} → {result} (桁数: {digits})")
    return result
