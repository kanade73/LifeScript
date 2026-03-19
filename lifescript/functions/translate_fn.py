"""translate() --- 翻訳関数。

translate(text, to_lang?) でLLMを使ってテキストを翻訳する。
"""

from __future__ import annotations

import os

from .. import llm as _llm
from .. import log_queue

_LANG_NAMES = {
    "ja": "日本語",
    "en": "英語",
    "zh": "中国語",
    "ko": "韓国語",
    "fr": "フランス語",
    "de": "ドイツ語",
    "es": "スペイン語",
    "pt": "ポルトガル語",
    "it": "イタリア語",
    "ru": "ロシア語",
}


def translate(text: str, to_lang: str = "ja") -> str:
    """テキストを翻訳する。

    Args:
        text: 翻訳するテキスト
        to_lang: 翻訳先言語コード（デフォルト: "ja"）

    Returns:
        翻訳されたテキスト
    """
    if not text.strip():
        return ""

    lang_name = _LANG_NAMES.get(to_lang, to_lang)
    model = os.getenv("LIFESCRIPT_MODEL", "gemini/gemini-2.5-flash")

    try:
        response = _llm.completion(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": f"あなたは翻訳者です。入力されたテキストを{lang_name}に翻訳してください。翻訳結果のみを出力し、説明は不要です。",
                },
                {"role": "user", "content": text},
            ],
            temperature=0.1,
        )
        result = response.choices[0].message.content.strip()
        log_queue.log("translate", f"翻訳 ({to_lang}): \"{text[:40]}\" → \"{result[:40]}\"")
        return result
    except Exception as e:
        log_queue.log("translate", f"翻訳エラー: {e}", "ERROR")
        return f"[翻訳エラー: {e}]"
