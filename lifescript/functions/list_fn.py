"""list.*() --- リスト操作関数。

list_join(items, separator?) でリストを文字列に結合する。
list_count(items, value) で要素の出現回数をカウントする。
"""

from __future__ import annotations

from .. import log_queue


def list_join(items: list, separator: str = ", ") -> str:
    """リストの要素を文字列に結合する。

    Args:
        items: 結合するリスト
        separator: 区切り文字（デフォルト: ", "）

    Returns:
        結合された文字列
    """
    result = separator.join(str(item) for item in items)
    log_queue.log("list", f"結合: {len(items)}要素 → \"{result[:80]}\"")
    return result


def list_count(items: list, value: object) -> int:
    """リスト内の要素の出現回数をカウントする。

    Args:
        items: 検索対象のリスト
        value: カウントする値

    Returns:
        出現回数
    """
    count = items.count(value)
    log_queue.log("list", f"カウント: {value} → {count}回")
    return count
