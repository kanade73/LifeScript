"""数学プラグイン — ランダムな数値生成機能を提供する。"""

from __future__ import annotations
import random
from .base import Plugin


class MathPlugin(Plugin):
    @property
    def name(self) -> str:
        return "math"

    def random_number(self, min_val: int = 1, max_val: int = 100) -> int:
        """min〜maxのランダムな整数を返す。"""
        return random.randint(min_val, max_val)


_plugin = MathPlugin()


def get_random_number(min_val: int = 1, max_val: int = 100) -> int:
    return _plugin.random_number(min_val, max_val)


# Auto-discovery registration
PLUGIN_EXPORTS = [
    {
        "name": "random_number",
        "func": get_random_number,
        "signature": "random_number(min_val: int = 1, max_val: int = 100) -> int",
        "description": "ランダムな整数を返す",
    },
]
