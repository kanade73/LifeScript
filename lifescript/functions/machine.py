"""machine.analyze() / machine.suggest() — マシン能動行動関数。

machine.analyze() でコンテキスト分析を実行し、提案を生成する。
machine.suggest(message) でダリーの提案を直接 machine_logs に書き込む。
"""

from __future__ import annotations

import json

from ..database.client import db_client
from .. import log_queue


def machine_analyze() -> list[dict]:
    """コンテキスト分析を実行し、提案を生成する。

    ContextAnalyzer を呼び出してカレンダー・メール・traits を分析し、
    提案を machine_logs に書き込む。

    Returns:
        生成された提案のリスト
    """
    from ..context_analyzer import ContextAnalyzer

    analyzer = ContextAnalyzer()
    # 実行間隔制御をバイパスして即時実行するため、_last_run をリセット
    analyzer._last_run = None
    suggestions = analyzer.analyze()
    log_queue.log("machine", f"analyze 完了: {len(suggestions)}件の提案を生成")
    return suggestions


def machine_suggest(message: str, reason: str = "") -> None:
    """ダリーの提案を machine_logs に直接書き込む。

    ホーム画面の「ダリーの提案」セクションに通知として表示される。

    Args:
        message: 提案メッセージ（ユーザーに見せる文）
        reason: 提案の理由（省略可）
    """
    content = message
    if reason:
        content += f"\n理由: {reason}"

    meta = json.dumps({"type": "notify"}, ensure_ascii=False)
    content += f"\n<!--meta:{meta}-->"

    db_client.add_machine_log(
        action_type="general_suggest",
        content=content,
    )
    log_queue.log("machine", f"提案: {message[:60]}")
