"""widget_show() — 動的ウィジェット生成関数。

widget_show(name, content) でホーム画面にカスタムウィジェットを表示する。
スクリプトが呼ぶたびにウィジェットの内容が更新される。
"""

from __future__ import annotations

from ..database.client import db_client
from .. import log_queue


def widget_show(name: str, content: str, icon: str = "article") -> None:
    """ホーム画面にカスタムウィジェットを表示/更新する。

    Args:
        name: ウィジェット名（ホーム画面のタイトルになる）
        content: 表示内容（テキスト）
        icon: アイコン名（article, language, rss_feed, etc.）
    """
    action_type = f"widget:{name}"

    db_client.add_machine_log(
        action_type=action_type,
        content=content,
    )
    log_queue.log("widget", f"ウィジェット更新: {name}")
