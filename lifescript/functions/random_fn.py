"""random.*() — ランダム関数。

DSL内でランダムな選択や数値生成に使うプリミティブ。
"""

from __future__ import annotations

import random as _random


def random_pick(items: list) -> object:
    """リストからランダムに1つ選んで返す。

    例: random_pick(["頑張れ", "休もう", "水飲んだ？"])
    """
    if not items:
        return None
    return _random.choice(items)


def random_number(low: int = 0, high: int = 100) -> int:
    """low 以上 high 以下のランダムな整数を返す。"""
    return _random.randint(low, high)
