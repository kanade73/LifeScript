"""コンテキスト分析エンジン — カレンダーやログを読み、LLMで提案を生成する。

定期実行されてユーザーの文脈を読み取り、能動的な提案を machine_logs に書き込む。
実行時に LLM を呼び出す唯一のモジュール（コンパイラ以外で）。
"""

from __future__ import annotations

import json
import re
import os
from datetime import datetime, timedelta, timezone

import litellm

from .database.client import db_client
from .traits import gather_all_traits, format_traits_for_prompt
from . import log_queue

_JST = timezone(timedelta(hours=9))

_ANALYSIS_PROMPT = """\
あなたは LifeScript の「マシン」です。ユーザーの生活文脈を読み取り、能動的に提案します。

以下のユーザーの **traits（自己定義した生活文脈）** とカレンダー情報を分析し、有用な提案を生成してください。

## あなたの役割
- ユーザーが traits で定義した文脈とメモリに記録されたパーソナリティを最優先で尊重する
- traits とメモリに基づいて、ユーザーが設定していない行動まで提案する
- 休息、運動、準備時間など、ユーザーの生活を改善する提案をする
- 同じ種類の予定が連続している場合は休息を提案する
- 空き時間を有効活用する提案をする
- 過去にした提案と重複しないこと

## ユーザーの traits（生活文脈の自己定義）
{traits}

traits はユーザーが LifeScript で自分の生活パターンや価値観を言語化したものです。
提案の根拠として traits を積極的に引用してください。

## 現在の日時
{now}

## 今週のカレンダー ({week_start} 〜 {week_end})
{calendar_summary}

## メモリ（ユーザーのパーソナリティ）
{memory}

## 最近の提案履歴（重複を避けること）
{recent_suggestions}

## 出力形式
JSON配列で提案を返してください。提案が無い場合は空配列 [] を返してください。
各提案は以下の形式です:

```json
[
  {{
    "message": "提案の説明文（ユーザーに見せる文）",
    "event_title": "追加するイベントのタイトル（承認時に使う）",
    "event_date": "YYYY-MM-DD",
    "event_time": "HH:MM",
    "reason": "この提案の根拠（どの trait や状況に基づくか明記）"
  }}
]
```

注意:
- 最大3件まで
- 具体的な日付と時刻を含めること
- 日本語で書くこと
- event_date は今日以降の日付にすること
- reason には必ず「どの trait またはメモリに基づくか」を含めること（traits やメモリがある場合）
- JSON のみ出力。説明文やマークダウンは不要
"""


class ContextAnalyzer:
    """カレンダー文脈を分析し、能動的な提案を生成する。"""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or os.getenv("LIFESCRIPT_MODEL", "gemini/gemini-2.5-flash")
        self._last_run: datetime | None = None

    def analyze(self) -> list[dict]:
        """文脈を分析して提案を生成し、machine_logs に書き込む。

        Returns:
            生成された提案のリスト
        """
        now = datetime.now(_JST)

        # 実行間隔制御（最低1時間空ける）
        if self._last_run and (now - self._last_run).total_seconds() < 3600:
            return []
        self._last_run = now

        log_queue.log("Analyzer", "文脈分析を開始します…")

        try:
            # ── コンテキスト収集 ──────────────────────────────
            calendar_summary = self._gather_calendar(now)
            recent_suggestions = self._gather_recent_suggestions()
            traits = gather_all_traits()
            traits_text = format_traits_for_prompt(traits)

            if not calendar_summary.strip():
                calendar_summary = "（今週の予定はありません）"

            log_queue.log("Analyzer", f"traits: {len(traits)}件の文脈定義を読み込み")

            # ── LLM呼び出し ───────────────────────────────────
            week_start = (now - timedelta(days=now.weekday())).strftime("%m/%d")
            week_end = (now + timedelta(days=6 - now.weekday())).strftime("%m/%d")

            # メモリ収集
            memory_text = self._gather_memory()

            prompt = _ANALYSIS_PROMPT.format(
                now=now.strftime("%Y-%m-%d %H:%M (%A)"),
                week_start=week_start,
                week_end=week_end,
                calendar_summary=calendar_summary,
                recent_suggestions=recent_suggestions or "（なし）",
                traits=traits_text,
                memory=memory_text,
            )

            response = litellm.completion(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "カレンダーを分析して提案を生成してください。"},
                ],
                temperature=0.7,
            )
            raw = response.choices[0].message.content.strip()

            # ── パース ────────────────────────────────────────
            suggestions = self._parse_suggestions(raw)

            # ── machine_logs に書き込み ───────────────────────
            for s in suggestions:
                event_title = s.get("event_title", "")
                event_date = s.get("event_date", "")
                event_time = s.get("event_time", "09:00")
                reason = s.get("reason", "")
                message = s.get("message", "")

                # 構造化コンテンツ: 「タイトル」を含めて承認時に抽出可能に
                content = f"{message}\n提案: 「{event_title}」を {event_date} {event_time} に追加しませんか？"
                if reason:
                    content += f"\n理由: {reason}"

                # メタデータをJSON埋め込み（承認時にパース）
                meta = json.dumps({
                    "event_title": event_title,
                    "event_date": event_date,
                    "event_time": event_time,
                }, ensure_ascii=False)
                content += f"\n<!--meta:{meta}-->"

                db_client.add_machine_log(
                    action_type="calendar_suggest",
                    content=content,
                )
                log_queue.log("Analyzer", f"提案: {event_title} ({event_date} {event_time})")

            if not suggestions:
                log_queue.log("Analyzer", "新しい提案はありません")

            return suggestions

        except Exception as e:
            log_queue.log("Analyzer", f"分析エラー: {e}", "ERROR")
            return []

    def _gather_calendar(self, now: datetime) -> str:
        """今週+来週のカレンダーイベントをテキストにまとめる。"""
        try:
            week_start = now - timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            two_weeks = week_start + timedelta(days=14)

            events = db_client.get_events(
                start_from=week_start.isoformat(),
                start_to=two_weeks.isoformat(),
            )

            if not events:
                return ""

            lines = []
            for ev in events:
                start = ev.get("start_at", "")
                title = ev.get("title", "")
                source = ev.get("source", "user")
                note = ev.get("note", "")

                try:
                    d = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    date_str = d.strftime("%m/%d (%a) %H:%M")
                except (ValueError, KeyError):
                    date_str = start[:16]

                line = f"- {date_str}: {title}"
                if source == "machine":
                    line += " [マシン登録]"
                if note:
                    line += f" ({note})"
                lines.append(line)

            # 同じタイトルの予定の回数を集計
            title_counts: dict[str, int] = {}
            for ev in events:
                t = ev.get("title", "")
                title_counts[t] = title_counts.get(t, 0) + 1

            summary_lines = []
            for t, c in sorted(title_counts.items(), key=lambda x: -x[1]):
                if c >= 2:
                    summary_lines.append(f"  「{t}」: {c}回")

            result = "\n".join(lines)
            if summary_lines:
                result += "\n\n### 頻度集計（2回以上）\n" + "\n".join(summary_lines)

            return result

        except Exception:
            return ""

    def _gather_memory(self) -> str:
        """手動追加されたメモリをテキストにまとめる。"""
        try:
            logs = db_client.get_machine_logs(limit=100)
            memories = [l for l in logs if l.get("action_type") == "memory"]
            if not memories:
                return "（なし）"
            lines = []
            for m in memories:
                content = m.get("content", "").strip()
                if content:
                    lines.append(f"- {content}")
            return "\n".join(lines) if lines else "（なし）"
        except Exception:
            return "（取得エラー）"

    def _gather_recent_suggestions(self) -> str:
        """最近の提案をテキストにまとめる（重複防止用）。"""
        try:
            logs = db_client.get_machine_logs(limit=30)
            lines = []
            for entry in logs:
                if entry.get("action_type") != "calendar_suggest":
                    continue
                content = entry.get("content", "")
                # メタデータ部分を除去して表示用テキストだけ取得
                content = re.sub(r"\n<!--meta:.*?-->", "", content)
                lines.append(f"- {content[:80]}")
                if len(lines) >= 10:
                    break
            return "\n".join(lines)
        except Exception:
            return ""

    def _parse_suggestions(self, raw: str) -> list[dict]:
        """LLMレスポンスから提案リストをパースする。"""
        # マークダウンコードブロックを除去
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data[:3]
            return []
        except json.JSONDecodeError:
            # JSON配列を抽出
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                    if isinstance(data, list):
                        return data[:3]
                except json.JSONDecodeError:
                    pass
            return []
