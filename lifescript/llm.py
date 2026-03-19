"""LLM呼び出し共通ヘルパー — リトライ + フォールバック。

全モジュールがこれを経由してLLMを呼ぶことで、
503などの一時エラー時に自動でフォールバックモデルへ切り替える。
"""

from __future__ import annotations

import os
import time

import litellm

# LiteLLMのログレベルを設定（起動時の情報メッセージを抑制）
litellm.suppress_debug_info = True
litellm.set_verbose = False

# フォールバックモデルの定義（環境変数で上書き可能）
_FALLBACK_MODELS = [
    "gemini/gemini-2.0-flash",
    "gemini/gemini-2.5-flash",
]

# リトライ対象のエラー
_RETRIABLE_ERRORS = (
    litellm.ServiceUnavailableError,
    litellm.RateLimitError,
    litellm.Timeout,
    litellm.APIConnectionError,
)


def completion(
    model: str,
    messages: list[dict],
    temperature: float = 0.3,
    **kwargs,
) -> litellm.ModelResponse:
    """litellm.completion のラッパー。失敗時にリトライ+フォールバック。"""

    # 試行するモデルリスト: 指定モデル → フォールバック群
    models = [model] + [m for m in _get_fallback_models() if m != model]

    last_error = None
    for i, m in enumerate(models):
        for attempt in range(2):  # 各モデル最大2回
            try:
                return litellm.completion(
                    model=m,
                    messages=messages,
                    temperature=temperature,
                    **kwargs,
                )
            except _RETRIABLE_ERRORS as e:
                last_error = e
                if attempt == 0:
                    time.sleep(1)  # 短いウェイトで1回だけリトライ
                continue
            except Exception as e:
                last_error = e
                break  # リトライ不可能なエラーは次のモデルへ

    raise last_error  # type: ignore[misc]


def _get_fallback_models() -> list[str]:
    """フォールバックモデルのリストを返す。"""
    env = os.getenv("LIFESCRIPT_FALLBACK_MODELS", "")
    if env:
        return [m.strip() for m in env.split(",") if m.strip()]
    return _FALLBACK_MODELS
