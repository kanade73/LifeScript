"""sound.*() --- サウンド関数。

sound_play(sound?) でmacOSのシステムサウンドを再生する。
"""

from __future__ import annotations

import subprocess

from .. import log_queue

_SOUND_MAP = {
    "default": "/System/Library/Sounds/Ping.aiff",
    "alert": "/System/Library/Sounds/Basso.aiff",
    "success": "/System/Library/Sounds/Glass.aiff",
    "error": "/System/Library/Sounds/Sosumi.aiff",
}


def sound_play(sound: str = "default") -> None:
    """macOSのシステムサウンドを再生する（非ブロッキング）。

    Args:
        sound: サウンド名。"default"(Ping), "alert"(Basso), "success"(Glass), "error"(Sosumi)
    """
    sound_file = _SOUND_MAP.get(sound, _SOUND_MAP["default"])

    try:
        subprocess.Popen(
            ["afplay", sound_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log_queue.log("sound", f"サウンド再生: {sound} ({sound_file})")
    except Exception as e:
        log_queue.log("sound", f"サウンド再生エラー: {e}", "ERROR")
