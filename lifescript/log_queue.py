"""Thread-safe log queue for communication between the scheduler and the UI."""
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
    return "mikan"