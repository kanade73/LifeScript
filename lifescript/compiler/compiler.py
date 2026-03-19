"""LifeScript DSL → Python コンパイラ（LiteLLM 経由で LLM を呼び出す）。

LifeScript の YAML 風 DSL を受け取り、LLM で Python コードに変換する。
コンパイル時のみ LLM を使用し、実行時は不使用 → コスト最小化。
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from .. import llm as _llm
from ..holidays import get_holiday_dates_between

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
| `machine.analyze()` | `machine_analyze()` |
| `machine.suggest("message")` | `machine_suggest("message")` |
| `machine.suggest("message", reason="理由")` | `machine_suggest("message", reason="理由")` |
| `device.cpu()` | `device_cpu()` |
| `device.memory()` | `device_memory()` |
| `device.info()` | `device_info()` |
| `weather.get()` | `weather_get()` |
| `weather.get("Osaka")` | `weather_get("Osaka")` |
| `time.now()` | `time_now()` |
| `random.pick([...])` | `random_pick([...])` |
| `random.number(1, 10)` | `random_number(1, 10)` |
| `streak.count("運動")` | `streak_count("運動")` |
| `streak.update("運動", True)` | `streak_update("運動", True)` |
| `memory.read("key")` | `memory_read("key")` |
| `memory.read("key", 0)` | `memory_read("key", 0)` |
| `memory.write("key", value)` | `memory_write("key", value)` |
| `math.calc("1+1")` | `math_calc("1+1")` |
| `math.calc("3*4+2")` | `math_calc("3*4+2")` |
| `math.round(3.14159, 2)` | `math_round(3.14159, 2)` |
| `date.diff("2026-04-01")` | `date_diff("2026-04-01")` |
| `date.diff("2026-04-01", "2026-03-01")` | `date_diff("2026-04-01", "2026-03-01")` |
| `list.join(["A","B","C"])` | `list_join(["A","B","C"])` |
| `list.join(items, "、")` | `list_join(items, "、")` |
| `list.count(items, "x")` | `list_count(items, "x")` |
| `translate("Hello", "ja")` | `translate("Hello", "ja")` |
| `translate(text, "en")` | `translate(text, "en")` |
| `summarize(text)` | `summarize(text)` |
| `summarize(text, 5)` | `summarize(text, 5)` |
| `qr.generate("https://example.com")` | `qr_generate("https://example.com")` |
| `qr.generate(data, 300)` | `qr_generate(data, 300)` |
| `sound.play()` | `sound_play()` |
| `sound.play("success")` | `sound_play("success")` |

**重要**: DSL ではドット記法（例: `calendar.add()`）を使いますが、Python ではアンダースコア記法（例: `calendar_add()`）に変換してください。

自然言語で書かれたルールも Python に変換してください。
例: 「バイトが週4以上なら回復タイムを提案」→ if calendar_read(keyword="バイト").count_this_week >= 4: calendar_suggest(...)
例: 「このサイトを毎日まとめて」→ result = web_fetch("url"); widget_show("サイト名", result)
例: 「カレンダーとメールを分析して提案して」→ machine_analyze()
例: 「今日は早く寝ようと提案して」→ machine_suggest("今日は早めに寝ましょう！", reason="明日の予定に備えて")
例: 「CPUが80%超えたら通知」→ if device_cpu() > 80: notify("CPU使用率が高いです")
例: 「雨なら傘を持っていけと通知」→ w = weather_get(); if w["condition"] == "rain": notify("傘を持って！")
例: 「朝なら挨拶を通知」→ t = time_now(); if t["is_morning"]: notify("おはよう！")
例: 「ランダムに応援メッセージ」→ msg = random_pick(["頑張れ！", "いい調子！", "水飲んだ？"]); notify(msg)
例: 「運動7日連続なら褒めて」→ if streak_count("運動") >= 7: notify("1週間継続おめでとう！")
例: 「前回の天気を記録」→ w = weather_get(); memory_write("last_weather", w["condition"])
例: 「1+2*3を計算して通知」→ result = math_calc("1+2*3"); notify(f"計算結果: {{result}}")
例: 「4月1日まであと何日か通知」→ days = date_diff("2026-04-01"); notify(f"4月1日まであと{{days}}日")
例: 「英語に翻訳して通知」→ result = translate("こんにちは", "en"); notify(result)
例: 「このページを要約して」→ text = web_fetch(url, summary=False); result = summarize(text); widget_show("要約", result)
例: 「URLのQRコードを生成」→ url = qr_generate("https://example.com"); notify(f"QRコード: {{url}}")
例: 「成功音を鳴らして」→ sound_play("success")

## トリガー（実行タイミング）

DSL 内の実行タイミング指定を trigger として抽出してください:
- `every day` → trigger: {{"type": "interval", "seconds": 86400}}
- `every Nh` → trigger: {{"type": "interval", "seconds": N*3600}}
- `every Nm` → trigger: {{"type": "interval", "seconds": N*60}}
- `after Ns` → trigger: {{"type": "after", "seconds": N}}
- `after Nm` → trigger: {{"type": "after", "seconds": N*60}}
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

{{"title": "簡潔な日本語説明", "trigger": {{"type": "interval", "seconds": <整数>}} または {{"type": "cron", "hour": <整数>, "minute": <整数>}} または {{"type": "after", "seconds": <整数>}}, "code": "<Python コード文字列>"}}

LifeScript が無効、またはサポート外の機能を使用している場合:
{{"error": "<日本語の説明>"}}
"""

# Compile cache
_cache: dict[str, dict] = {}
_MAX_CACHE = 128

_JST = timezone(timedelta(hours=9))
_DAY_MAP = {
    "月": 0,
    "火": 1,
    "水": 2,
    "木": 3,
    "金": 4,
    "土": 5,
    "日": 6,
}
_DAILY_KEYS = {"毎日", "daily", "everyday"}
_WEEKDAY_ONLY_KEYS = {"平日", "平日のみ", "weekday", "weekdays"}
_WEEKEND_HOLIDAY_KEYS = {"土日祝", "土日祝のみ", "weekend_holiday", "weekend_holidays"}


def _strip_quotes(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _parse_hhmm(text: str) -> time:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if not match:
        raise CompileError(f"時刻形式が正しくありません。: {text} (HH:MM)")
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        raise CompileError(f"時刻形式が正しくありません。: {text}")
    return time(hour=hour, minute=minute)


def _parse_time_expr(text: str) -> list[tuple[time, time]]:
    text = _strip_quotes(text)
    if "-" in text:
        start_str, end_str = [s.strip() for s in text.split("-", 1)]
        start_t = _parse_hhmm(start_str)
        end_t = _parse_hhmm(end_str)
        start_dt = datetime.combine(date.today(), start_t)
        end_dt = datetime.combine(date.today(), end_t)
        if end_dt <= start_dt:
            raise CompileError(f"時間範囲が正しくありません。: {text}")

        slots: list[tuple[time, time]] = []
        cur = start_dt
        while cur < end_dt:
            nxt = min(cur + timedelta(minutes=10), end_dt)
            slots.append((cur.time(), nxt.time()))
            cur = nxt
        return slots

    point = _parse_hhmm(text)
    start_dt = datetime.combine(date.today(), point)
    end_dt = start_dt + timedelta(minutes=10)
    return [(start_dt.time(), end_dt.time())]


def _next_dates_for_weekday(weekday: int, weeks: int = 4) -> list[date]:
    today = datetime.now(_JST).date()
    this_week_start = today - timedelta(days=today.weekday())
    dates: list[date] = []
    for week in range(weeks):
        dates.append(this_week_start + timedelta(days=weekday + 7 * week))
    return dates


def _date_window(weeks: int = 4) -> tuple[date, date]:
    today = datetime.now(_JST).date()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=weeks * 7 - 1)
    return start, end


def _dates_in_window(weeks: int = 4) -> list[date]:
    start, end = _date_window(weeks=weeks)
    result: list[date] = []
    cur = start
    while cur <= end:
        result.append(cur)
        cur += timedelta(days=1)
    return result


def _target_weekdays(day_key: str) -> list[int]:
    if day_key in _DAILY_KEYS:
        return [0, 1, 2, 3, 4, 5, 6]
    if day_key in _DAY_MAP:
        return [_DAY_MAP[day_key]]
    raise CompileError(f"repeat_10min の曜日が正しくありません。: {day_key}")


def _resolve_dates_for_key(
    day_key: str,
    *,
    weeks: int,
    model: str,
    api_base: str | None,
) -> list[date]:
    if day_key in _DAY_MAP:
        return _next_dates_for_weekday(_DAY_MAP[day_key], weeks=weeks)
    if day_key in _DAILY_KEYS:
        return _dates_in_window(weeks=weeks)

    start, end = _date_window(weeks=weeks)
    try:
        holidays = get_holiday_dates_between(start, end, model=model, api_base=api_base)
    except Exception:
        holidays = set()
    days = _dates_in_window(weeks=weeks)

    if day_key in _WEEKDAY_ONLY_KEYS:
        return [d for d in days if d.weekday() < 5 and d not in holidays]
    if day_key in _WEEKEND_HOLIDAY_KEYS:
        return [d for d in days if d.weekday() >= 5 or d in holidays]

    raise CompileError(f"repeat_10min の曜日が正しくありません。: {day_key}")


def _to_iso(d: date, t: time) -> str:
    return datetime.combine(d, t, tzinfo=_JST).isoformat()


def _expand_repeat_10min_block(
    block_lines: list[str],
    base_indent: int,
    *,
    model: str,
    api_base: str | None,
) -> list[str]:
    current_day: str | None = None
    generated: list[str] = []

    for raw_line in block_lines:
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()

        if indent == base_indent + 2 and stripped.endswith(":"):
            day = _strip_quotes(stripped[:-1].strip())
            if (
                day not in _DAY_MAP
                and day not in _DAILY_KEYS
                and day not in _WEEKDAY_ONLY_KEYS
                and day not in _WEEKEND_HOLIDAY_KEYS
            ):
                raise CompileError(f"repeat_10min の曜日が正しくありません。: {day}")
            current_day = day
            continue

        if indent >= base_indent + 4 and ":" in stripped and current_day is not None:
            pair = re.match(r"^(.+):\s*(.+)$", stripped)
            if not pair:
                raise CompileError(f"repeat_10min の行形式が正しくありません。: {stripped}")

            time_expr = pair.group(1).strip()
            title = _strip_quotes(pair.group(2).strip())
            if not title:
                raise CompileError("repeat_10min の予定名が空です")

            slots = _parse_time_expr(time_expr)
            for d in _resolve_dates_for_key(
                current_day,
                weeks=4,
                model=model,
                api_base=api_base,
            ):
                for start_t, end_t in slots:
                    title_escaped = title.replace('"', '\\"')
                    generated.append(
                        f'calendar.add("{title_escaped}", start="{_to_iso(d, start_t)}", '
                        f'end="{_to_iso(d, end_t)}", note="repeat_10min")'
                    )

    if not generated:
        raise CompileError("repeat_10min ブロックが空か、形式が正しくありません。")

    return generated


def _expand_repeat_10min(lifescript_code: str, *, model: str, api_base: str | None) -> str:
    lines = lifescript_code.splitlines()
    if not lines:
        return lifescript_code

    output: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.match(r"^(\s*)repeat_10min:\s*$", line)
        if not match:
            output.append(line)
            i += 1
            continue

        base_indent = len(match.group(1))
        i += 1
        block_lines: list[str] = []
        while i < len(lines):
            cur = lines[i]
            if not cur.strip():
                block_lines.append(cur)
                i += 1
                continue
            cur_indent = len(cur) - len(cur.lstrip(" "))
            if cur_indent <= base_indent:
                break
            block_lines.append(cur)
            i += 1

        output.extend(
            _expand_repeat_10min_block(
                block_lines,
                base_indent=base_indent,
                model=model,
                api_base=api_base,
            )
        )

    return "\n".join(output)


def _build_system_prompt() -> str:
    lines = []
    for f in FUNCTION_DESCRIPTIONS:
        lines.append(f"- `{f['signature']}`  — {f['description']}")
    functions_section = "\n".join(lines)
    return _SYSTEM_PROMPT.format(functions_section=functions_section)


def _cache_key(code: str) -> str:
    return hashlib.sha256(code.strip().encode()).hexdigest()


def _extract_after_trigger(code: str) -> tuple[str, dict[str, int] | None]:
    """先頭の `after 10s:` 形式を抽出し、本文と trigger を返す。"""
    lines = code.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        match = re.fullmatch(r"after\s+(\d+)\s*([smh])\s*:", stripped, flags=re.IGNORECASE)
        if not match:
            return code, None

        amount = int(match.group(1))
        unit = match.group(2).lower()
        unit_seconds = {"s": 1, "m": 60, "h": 3600}[unit]
        body_lines = lines[:index] + lines[index + 1 :]
        body = "\n".join(body_lines).strip("\n")
        return body, {"type": "after", "seconds": amount * unit_seconds}

    return code, None


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
            if not (0 <= trigger["hour"] <= 23):
                raise CompileError("cronトリガーの hour は0-23である必要があります")
            if not (0 <= trigger["minute"] <= 59):
                raise CompileError("cronトリガーの minute は0-59である必要があります")
        elif trigger_type == "interval":
            if "seconds" not in trigger:
                raise CompileError("intervalトリガーには 'seconds' が必要です")
            try:
                trigger["seconds"] = int(trigger["seconds"])
            except (TypeError, ValueError) as e:
                raise CompileError(f"trigger['seconds']は数値である必要があります: {e}") from e
            if trigger["seconds"] <= 0:
                raise CompileError("intervalトリガーの秒数は1以上である必要があります")
        elif trigger_type == "after":
            if "seconds" not in trigger:
                raise CompileError("afterトリガーには 'seconds' が必要です")
            try:
                trigger["seconds"] = int(trigger["seconds"])
            except (TypeError, ValueError) as e:
                raise CompileError(f"trigger['seconds']は数値である必要があります: {e}") from e
            if trigger["seconds"] <= 0:
                raise CompileError("afterトリガーの秒数は1以上である必要があります")
        else:
            raise CompileError(f"未対応のトリガータイプです: {trigger_type}")

        validate_python(result["code"])
        return result

    def compile(self, lifescript_code: str) -> dict[str, Any]:
        """LifeScript を Python にコンパイルする。"""
        expanded_code = _expand_repeat_10min(
            lifescript_code,
            model=self.model,
            api_base=self.api_base,
        )
        llm_input_code, explicit_trigger = _extract_after_trigger(expanded_code)

        key = _cache_key(expanded_code)
        if key in _cache:
            return _cache[key]

        content = self._call_llm(
            [
                {"role": "system", "content": _build_system_prompt()},
                {
                    "role": "user",
                    "content": f"以下の LifeScript をコンパイルしてください:\n\n{llm_input_code}",
                },
            ]
        )
        result = self._validate_result(self._parse_response(content))
        if explicit_trigger is not None:
            result["trigger"] = explicit_trigger

        if len(_cache) >= _MAX_CACHE:
            oldest = next(iter(_cache))
            del _cache[oldest]
        _cache[key] = result

        return result

    def recompile_with_error(
        self, lifescript_code: str, python_code: str, error: str
    ) -> dict[str, Any]:
        """実行時エラーが発生した Python を LLM に修正させる。"""
        expanded_code = _expand_repeat_10min(
            lifescript_code,
            model=self.model,
            api_base=self.api_base,
        )
        llm_input_code, explicit_trigger = _extract_after_trigger(expanded_code)

        key = _cache_key(expanded_code)
        _cache.pop(key, None)

        content = self._call_llm(
            [
                {"role": "system", "content": _build_system_prompt()},
                {
                    "role": "user",
                    "content": (
                        f"以下の LifeScript:\n\n{llm_input_code}\n\n"
                        f"は次の Python にコンパイルされました:\n\n{python_code}\n\n"
                        f"しかし実行時に以下のエラーが発生しました:\n\n{error}\n\n"
                        "修正したコンパイル結果を返してください。"
                    ),
                },
            ]
        )
        result = self._validate_result(self._parse_response(content))
        if explicit_trigger is not None:
            result["trigger"] = explicit_trigger
        return result

    @staticmethod
    def clear_cache() -> None:
        _cache.clear()
