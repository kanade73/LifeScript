"""スレッドセーフなログキュー — スケジューラと UI 間の通信に使用。

バックグラウンドのスケジューラ/サンドボックスからログメッセージを受け取り、
UI のポーリングループが定期的に drain() して画面に表示する。
"""

from collections import deque
from datetime import datetime
import threading

_queue: deque[str] = deque(maxlen=500)
_lock = threading.Lock()


def log(rule_title: str, message: str, level: str = "INFO") -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] [{level}] {rule_title}: {message}"
    with _lock:
        _queue.append(entry)


def drain() -> list[str]:
    """溜まっているログエントリを全て返してキューを空にする。"""
    with _lock:
        entries = list(_queue)
        _queue.clear()
        return entries
