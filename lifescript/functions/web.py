"""web_fetch() — Webページ取得・要約関数。

web_fetch(url, summary?) でURLの内容を取得する。
summary=True(デフォルト)でLLMによる要約を返す。
"""

from __future__ import annotations

import os
import re

import httpx
import litellm

from ..database.client import db_client
from .. import log_queue

_FETCH_TIMEOUT = 15
_MAX_CONTENT_LENGTH = 8000


def _extract_text(html: str) -> str:
    """HTMLからテキストを抽出する（簡易版）。"""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:_MAX_CONTENT_LENGTH]


def _summarize(text: str, url: str) -> str:
    """LLMでテキストを要約する。"""
    model = os.getenv("LIFESCRIPT_MODEL", "gemini/gemini-2.5-flash")
    try:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "以下のWebページの内容を日本語で簡潔に要約してください。"
                    "箇条書きで重要なポイントを3〜5個にまとめてください。"
                )},
                {"role": "user", "content": f"URL: {url}\n\n内容:\n{text}"},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"(要約エラー: {e})\n\n{text[:500]}"


def web_fetch(url: str, summary: bool = True) -> str:
    """URLの内容を取得し、オプションでLLM要約を返す。"""
    log_queue.log("web", f"取得中: {url}")
    try:
        resp = httpx.get(url, timeout=_FETCH_TIMEOUT, follow_redirects=True,
                         headers={"User-Agent": "LifeScript/0.2"})
        resp.raise_for_status()
    except Exception as e:
        error_msg = f"取得失敗: {url} ({e})"
        log_queue.log("web", error_msg, "ERROR")
        return error_msg

    text = _extract_text(resp.text)

    if summary:
        result = _summarize(text, url)
    else:
        result = text

    log_queue.log("web", f"取得完了: {url} ({len(result)}文字)")
    return result
