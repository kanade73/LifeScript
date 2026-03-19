"""summarize() --- 要約関数。

summarize(text, max_lines?) でLLMを使ってテキストを要約する。
"""

from __future__ import annotations

import os

from .. import llm as _llm
from .. import log_queue


def summarize(text: str, max_lines: int = 3) -> str:
    """テキストを要約する。

    Args:
        text: 要約するテキスト
        max_lines: 要約の最大行数（箇条書き、デフォルト: 3）

    Returns:
        日本語の箇条書き要約
    """
    if not text.strip():
        return ""

    model = os.getenv("LIFESCRIPT_MODEL", "gemini/gemini-2.5-flash")

    try:
        response = _llm.completion(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"あなたは要約の専門家です。入力されたテキストを日本語で{max_lines}行以内の箇条書きで要約してください。"
                        "各行は「・」で始めてください。要約のみを出力し、他の説明は不要です。"
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0.1,
        )
        result = response.choices[0].message.content.strip()
        log_queue.log("summarize", f"要約完了: {len(text)}文字 → {len(result)}文字")
        return result
    except Exception as e:
        log_queue.log("summarize", f"要約エラー: {e}", "ERROR")
        return f"[要約エラー: {e}]"
