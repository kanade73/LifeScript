"""デバイス情報関数 — PCのシステム状態を取得する。"""

from __future__ import annotations

import platform
import os


def device_cpu() -> float:
    """CPU使用率(%)を返す。psutilがなければ簡易推定。"""
    try:
        import psutil
        return psutil.cpu_percent(interval=0.5)
    except ImportError:
        load = os.getloadavg()[0]
        cores = os.cpu_count() or 1
        return min(round(load / cores * 100, 1), 100.0)


def device_memory() -> dict:
    """メモリ情報を返す。{total_gb, used_gb, percent}"""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024**3), 1),
            "used_gb": round(mem.used / (1024**3), 1),
            "percent": mem.percent,
        }
    except ImportError:
        return {"total_gb": 0, "used_gb": 0, "percent": 0}


def device_info() -> dict:
    """デバイスの基本情報を返す。"""
    return {
        "os": platform.system(),
        "os_version": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count() or 0,
    }
