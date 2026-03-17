"""LifeScript DSL → Python コンパイラ（LiteLLM 経由で LLM を呼び出す）。

LifeScript の YAML 風 DSL を受け取り、LLM で Python コードに変換する。
コンパイル時のみ LLM を使用し、実行時は不使用 → コスト最小化。
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .. import llm as _llm

from ..exceptions import CompileError
from ..functions import FUNCTION_DESCRIPTIONS
from .validator import validate_python

_SYSTEM_PROMPT = """\
あなたは LifeScript → Python コンパイラです。

LifeScript は「ダリー」という相棒に自分の生活文脈を伝えるための DSL です。
ユーザーが書いた LifeScript を、以下の関数ライブラリのみを使った Python コードに変換してください。
出力は JSON のみ。マークダウンや説明文は不要です。

## 関数ライブラリ（使用可能な関数）
{functions_section}

## DSL → Python 変換ルール

LifeScript の DSL は YAML 風の宣言的記法です:

| DSL パターン | Python |
|---|---|
| `when <条件>:` | `if <条件>:` |
| `calendar.read("keyword")` | `calendar_read(keyword="keyword")` |
| `calendar.read("keyword").count_this_week` | `calendar_read(keyword="keyword").count_this_week` |
| `calendar.add(title, start, ...)` | `calendar_add(title, start, ...)` |
| `calendar.suggest(title, on, ...)` | `calendar_suggest(title, on, ...)` |
| `notify("message")` | `notify("message")` |
| `notify("message", at="2025-01-01T08:00:00")` | `notify("message", at="2025-01-01T08:00:00")` |
| `web.fetch(url)` | `web_fetch(url)` |
| `web.fetch(url, summary=False)` | `web_fetch(url, summary=False)` |
| `widget.show(name, content)` | `widget_show(name, content)` |
| `widget.show(name, content, icon="rss_feed")` | `widget_show(name, content, icon="rss_feed")` |

自然言語で書かれたルールも Python に変換してください。
例: 「バイトが週4以上なら回復タイムを提案」→ if calendar_read(keyword="バイト").count_this_week >= 4: calendar_suggest(...)
例: 「このサイトを毎日まとめて」→ result = web_fetch("url"); widget_show("サイト名", result)

## トリガー（実行タイミング）

DSL 内の実行タイミング指定を trigger として抽出してください:
- `every day` → trigger: {{"type": "interval", "seconds": 86400}}
- `every Nh` → trigger: {{"type": "interval", "seconds": N*3600}}
- `every Nm` → trigger: {{"type": "interval", "seconds": N*60}}
- `when HH:MM:` → trigger: {{"type": "cron", "hour": HH, "minute": MM}}（毎日その時刻に実行）
- `when morning:` → trigger: {{"type": "cron", "hour": 8, "minute": 0}}
- `when evening:` → trigger: {{"type": "cron", "hour": 18, "minute": 0}}
- 指定なし（定期実行が不要な場合） → trigger: {{"type": "once"}}（即時1回実行）
- 指定なし（定期実行が必要な場合） → trigger: {{"type": "interval", "seconds": 3600}} (デフォルト1時間)
- web_fetchやwidget_showだけの場合は通常 "once" が適切

## traits ブロックについて
DSL に `traits:` ブロックがある場合、それは文脈定義であり実行コードではありません。
traits ブロックはコンパイル対象外です。traits 以外の部分だけを Python に変換してください。
traits しかない場合は code を空文字列 "" にし、trigger を {{"type": "once"}} にしてください。

## 禁止事項
- import 文の使用禁止
- ファイルシステム・ネットワークアクセス禁止
- exec, eval, __import__, open, os, sys の使用禁止
- 上記の関数ライブラリ以外の関数呼び出し禁止

## 出力形式（JSON のみ — マークダウン不可）

{{"title": "簡潔な日本語説明", "trigger": {{"type": "interval", "seconds": <整数>}} または {{"type": "cron", "hour": <整数>, "minute": <整数>}}, "code": "<Python コード文字列>"}}

LifeScript が無効、またはサポート外の機能を使用している場合:
{{"error": "<日本語の説明>"}}
"""

# Compile cache
_cache: dict[str, dict] = {}
_MAX_CACHE = 128


def _build_system_prompt() -> str:
    lines = []
    for f in FUNCTION_DESCRIPTIONS:
        lines.append(f"- `{f['signature']}`  — {f['description']}")
    functions_section = "\n".join(lines)
    return _SYSTEM_PROMPT.format(functions_section=functions_section)


def _cache_key(code: str) -> str:
    return hashlib.sha256(code.strip().encode()).hexdigest()


class Compiler:
    def __init__(self, model: str, api_base: str | None = None) -> None:
        self.model = model
        self.api_base = api_base

    def _call_llm(self, messages: list[dict]) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        try:
            response = _llm.completion(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise CompileError(f"LLM呼び出しに失敗しました: {e}") from e

    def _parse_response(self, content: str) -> dict:
        content = re.sub(r"```(?:json)?\s*", "", content).strip().rstrip("`").strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise CompileError(f"LLMが無効なJSONを返しました: {e}\n内容: {content[:300]}") from e

    def _validate_result(self, result: dict) -> dict:
        if "error" in result:
            raise CompileError(result["error"])

        for field in ("title", "trigger", "code"):
            if field not in result:
                raise CompileError(f"LLMの応答に必須フィールドがありません: '{field}'")

        trigger = result["trigger"]
        if not isinstance(trigger, dict):
            raise CompileError(
                f"triggerは辞書型である必要があります（{type(trigger).__name__}が返されました）"
            )

        trigger_type = trigger.get("type", "interval")
        if trigger_type == "once":
            pass  # 即時1回実行 — 追加バリデーション不要
        elif trigger_type == "cron":
            for field in ("hour", "minute"):
                if field not in trigger:
                    raise CompileError(f"cronトリガーには '{field}' が必要です")
                try:
                    trigger[field] = int(trigger[field])
                except (TypeError, ValueError) as e:
                    raise CompileError(f"trigger['{field}']は数値である必要があります: {e}") from e
        elif trigger_type == "interval":
            if "seconds" not in trigger:
                raise CompileError("intervalトリガーには 'seconds' が必要です")
            try:
                trigger["seconds"] = int(trigger["seconds"])
            except (TypeError, ValueError) as e:
                raise CompileError(f"trigger['seconds']は数値である必要があります: {e}") from e
        else:
            raise CompileError(f"未対応のトリガータイプです: {trigger_type}")

        validate_python(result["code"])
        return result

    def compile(self, lifescript_code: str) -> dict[str, Any]:
        """LifeScript を Python にコンパイルする。"""
        key = _cache_key(lifescript_code)
        if key in _cache:
            return _cache[key]

        content = self._call_llm(
            [
                {"role": "system", "content": _build_system_prompt()},
                {
                    "role": "user",
                    "content": f"以下の LifeScript をコンパイルしてください:\n\n{lifescript_code}",
                },
            ]
        )
        result = self._validate_result(self._parse_response(content))

        if len(_cache) >= _MAX_CACHE:
            oldest = next(iter(_cache))
            del _cache[oldest]
        _cache[key] = result

        return result

    def recompile_with_error(
        self, lifescript_code: str, python_code: str, error: str
    ) -> dict[str, Any]:
        """実行時エラーが発生した Python を LLM に修正させる。"""
        key = _cache_key(lifescript_code)
        _cache.pop(key, None)

        content = self._call_llm(
            [
                {"role": "system", "content": _build_system_prompt()},
                {
                    "role": "user",
                    "content": (
                        f"以下の LifeScript:\n\n{lifescript_code}\n\n"
                        f"は次の Python にコンパイルされました:\n\n{python_code}\n\n"
                        f"しかし実行時に以下のエラーが発生しました:\n\n{error}\n\n"
                        "修正したコンパイル結果を返してください。"
                    ),
                },
            ]
        )
        return self._validate_result(self._parse_response(content))

    @staticmethod
    def clear_cache() -> None:
        _cache.clear()
