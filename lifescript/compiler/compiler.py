"""LifeScript → Python compiler via LLM (LiteLLM)."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import litellm

from ..exceptions import CompileError
from ..plugins import get_descriptions
from .validator import validate_python

_SYSTEM_PROMPT_TEMPLATE = """\
あなたは LifeScript → Python コンパイラです。

LifeScript は「暮らしの自動化」のための DSL です。
与えられた LifeScript を、以下に列挙された関数 **のみ** を使った Python に変換してください。
出力は JSON のみ。マークダウンや説明文は不要です。

## 使用可能な関数
{functions_section}

## LifeScript → Python 変換ルール
| LifeScript                     | Python                        |
|--------------------------------|-------------------------------|
| fetch(time.now)                | fetch_time_now()              |
| fetch(time.today)              | fetch_time_today()            |
| fetch(weather, "Tokyo")        | fetch_weather("Tokyo")        |
| notify(LINE, "msg")            | notify_line("msg")            |
| let x = expr                   | x = expr                      |
| when cond {{ ... }}            | if cond: ...                  |
| repeat N {{ ... }}             | for _ in range(N): ...        |
| every day {{ ... }}            | trigger=interval(seconds=86400)|
| every Nh {{ ... }}             | trigger=interval(seconds=N*3600) |
| every Nm {{ ... }}             | trigger=interval(seconds=N*60) |
| cron "0 8 * * *" {{ ... }}    | trigger=cron(minute=0,hour=8) |
| cron "30 9 * * mon" {{ ... }} | trigger=cron(minute=30,hour=9,day_of_week="mon") |

## 禁止事項
- import 文の使用禁止
- ファイルシステムへのアクセス禁止
- ネットワーク呼び出し禁止（プラグイン関数のみ使用可）
- exec, eval, __import__, open, os, sys の使用禁止
- 上記のプラグイン関数以外の関数呼び出し禁止

## 出力形式（JSON のみ — マークダウン不可、説明文不可）

interval トリガーの場合:
{{"title": "簡潔な説明", "trigger": {{"type": "interval", "seconds": <整数>}}, "code": "<Python コード文字列>"}}

cron トリガーの場合:
{{"title": "簡潔な説明", "trigger": {{"type": "cron", "minute": <int>, "hour": <int>, "day_of_week": "<str|省略可>", "day": "<str|省略可>", "month": "<str|省略可>"}}, "code": "<Python コード文字列>"}}

LifeScript が無効、またはサポート外の機能を使用している場合:
{{"error": "<日本語の説明>"}}
"""

# Compile cache: hash(lifescript_code) → result dict
_cache: dict[str, dict] = {}
_MAX_CACHE = 128


def _build_system_prompt() -> str:
    """Build the system prompt dynamically from registered plugins."""
    descs = get_descriptions()
    lines = []
    for name, info in descs.items():
        lines.append(f"- {info['signature']}  — {info['description']}")
    functions_section = "\n".join(lines) if lines else "（プラグインが登録されていません）"
    return _SYSTEM_PROMPT_TEMPLATE.format(functions_section=functions_section)


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
            response = litellm.completion(**kwargs)
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
        """Validate and normalize a compilation result dict."""
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
        result["trigger"]["type"] = trigger_type

        if trigger_type == "cron":
            # Ensure at least minute and hour are present
            for key in ("minute", "hour"):
                if key not in trigger:
                    raise CompileError(f"cronトリガーには '{key}' が必要です")
                try:
                    trigger[key] = int(trigger[key])
                except (TypeError, ValueError) as e:
                    raise CompileError(f"trigger['{key}']は数値である必要があります: {e}") from e
        else:
            # interval trigger
            if "seconds" not in trigger:
                raise CompileError("intervalトリガーには 'seconds' が必要です")
            try:
                result["trigger"]["seconds"] = int(trigger["seconds"])
            except (TypeError, ValueError) as e:
                raise CompileError(f"trigger['seconds']は数値である必要があります: {e}") from e

        validate_python(result["code"])
        return result

    def compile(self, lifescript_code: str) -> dict[str, Any]:
        """Compile LifeScript to Python. Returns dict with title, trigger, code."""
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

        # Store in cache (evict oldest if full)
        if len(_cache) >= _MAX_CACHE:
            oldest = next(iter(_cache))
            del _cache[oldest]
        _cache[key] = result

        return result

    def recompile_with_error(
        self, lifescript_code: str, python_code: str, error: str
    ) -> dict[str, Any]:
        """Ask the LLM to fix a runtime error in previously generated Python."""
        # Invalidate cache for this code
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
        """Clear the compile cache."""
        _cache.clear()
