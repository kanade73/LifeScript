"""プラグインの自動検出とレジストリ。

各プラグインモジュールは PLUGIN_EXPORTS リストを定義する:

    PLUGIN_EXPORTS = [
        {
            "name": "関数名",
            "func": 呼び出し可能オブジェクト,
            "signature": "関数名(引数: 型) -> 戻り値型",
            "description": "この関数が何をするかの説明",
        },
    ]

起動時に discover() を一度呼び出すとレジストリに登録される。
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

# {function_name: callable}
_functions: dict[str, Any] = {}
# {function_name: {"signature": str, "description": str}}
_descriptions: dict[str, dict[str, str]] = {}
_discovered = False


def discover() -> None:
    """全プラグインモジュールを import し、PLUGIN_EXPORTS を収集する。"""
    global _discovered  # noqa: PLW0603
    if _discovered:
        return
    for _importer, modname, _ispkg in pkgutil.iter_modules(__path__):
        if modname == "base":
            continue
        mod = importlib.import_module(f".{modname}", __package__)
        for export in getattr(mod, "PLUGIN_EXPORTS", []):
            _functions[export["name"]] = export["func"]
            _descriptions[export["name"]] = {
                "signature": export["signature"],
                "description": export["description"],
            }
    _discovered = True


def get_functions() -> dict[str, Any]:
    """登録済みの全プラグイン関数を {名前: 関数} で返す。"""
    discover()
    return dict(_functions)


def get_descriptions() -> dict[str, dict[str, str]]:
    """システムプロンプト生成用に {名前: {signature, description}} を返す。"""
    discover()
    return dict(_descriptions)


def get_allowed_names() -> set[str]:
    """バリデータ用に許可された関数名のセットを返す。"""
    discover()
    return set(_functions.keys())
