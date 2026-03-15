"""スレッドセーフなログキュー — スケジューラと UI 間の通信に使用。

エントリは (source, message, level) のタプルとして格納。
"""

from collections import deque
import threading

_queue: deque[tuple[str, str, str]] = deque(maxlen=500)
_lock = threading.Lock()


def log(source: str, message: str, level: str = "INFO") -> None:
    with _lock:
        _queue.append((source, message, level))


def drain() -> list[tuple[str, str, str]]:
    """溜まっているログエントリを全て返してキューを空にする。"""
    with _lock:
        entries = list(_queue)
        _queue.clear()
        return entries
