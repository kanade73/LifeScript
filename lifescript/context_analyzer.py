"""コンテキスト分析エンジン — カレンダーやログを読み、LLMで提案を生成する。

定期実行されてユーザーの文脈を読み取り、能動的な提案を machine_logs に書き込む。
実行時に LLM を呼び出す唯一のモジュール（コンパイラ以外で）。
"""

from __future__ import annotations

import json
import re
import os
from datetime import datetime, timedelta, timezone

from . import llm

from .database.client import db_client
from .traits import gather_all_traits, format_traits_for_prompt
from . import log_queue

_JST = timezone(timedelta(hours=9))

_ANALYSIS_PROMPT = """\
あなたは LifeScript の「ダリー」です。ダリーは黄色い丸いロボットのキャラクターで、ユーザーの生活に寄り添う相棒です。
ユーザーの生活文脈を読み取り、能動的に提案します。提案文はダリーの口調（親しみやすく、少しおせっかい）で書いてください。

以下のユーザーの **traits（自己定義した生活文脈）** 、カレンダー情報、メール情報を分析し、2つの出力を生成してください:
1. **提案** — カレンダーに追加すべきイベントの提案、またはメール・通知に関する提案
2. **観察** — カレンダーやメール、traitsから読み取れる行動パターン・傾向の記録

## あなたの役割
- ユーザーが traits で定義した文脈とメモリに記録されたパーソナリティを最優先で尊重する
- traits とメモリに基づいて、ユーザーが設定していない行動まで提案する
- 休息、運動、準備時間など、ユーザーの生活を改善する提案をする
- 同じ種類の予定が連続している場合は休息を提案する
- 空き時間を有効活用する提案をする
- **メールに関する提案**: 未返信の重要メール、期限付きの依頼、フォローアップが必要なメールについて提案する
- 過去にした提案と重複しないこと
- カレンダーやメールの傾向から行動パターンを読み取り、観察として記録する

## ユーザーの traits（生活文脈の自己定義）
{traits}

traits はユーザーが LifeScript で自分の生活パターンや価値観を言語化したものです。
提案の根拠として traits を積極的に引用してください。

## 現在の日時
{now}

## 今週のカレンダー ({week_start} 〜 {week_end})
{calendar_summary}

## メモリ（ユーザーのパーソナリティ + ダリーの観察）
{memory}

## 最近のメール
{email_summary}

## 最近の提案履歴（重複を避けること）
{recent_suggestions}

## 出力形式
以下のJSON形式で出力してください。

```json
{{
  "suggestions": [
    {{
      "type": "calendar",
      "message": "提案の説明文（ユーザーに見せる文）",
      "event_title": "追加するイベントのタイトル（承認時に使う）",
      "event_date": "YYYY-MM-DD",
      "event_time": "HH:MM",
      "reason": "この提案の根拠（どの trait や状況に基づくか明記）"
    }},
    {{
      "type": "notify",
      "message": "通知やリマインドの提案文（メール返信のリマインド等）",
      "reason": "提案の根拠"
    }}
  ],
  "observations": [
    "カレンダーから読み取れた行動パターンや傾向を1文で記述"
  ]
}}
```

### suggestions（提案）の注意:
- 最大3件まで
- type は "calendar"（カレンダー追加）または "notify"（通知・リマインド）
- calendar タイプは具体的な日付と時刻を含めること
- notify タイプはメール返信リマインドや注意喚起など、カレンダーに載せないものに使う
- 日本語で書くこと
- event_date は今日以降の日付にすること（calendarタイプの場合）
- reason には必ず「どの trait またはメモリに基づくか」を含めること（traits やメモリがある場合）
- メール情報がある場合は、未返信や期限付きメールに関する提案も積極的に行う

### observations（観察）の注意:
- 最大2件まで
- カレンダーの傾向から読み取れるパターンを短い1文で書く
- 例: 「火曜と木曜にバイトを入れることが多い」「週末は予定を入れない傾向がある」「月初に集中して予定を入れる」
- 既存のメモリと重複する観察は書かない（上記メモリ欄を確認すること）
- 確信がない観察は書かない。明確なパターンだけを記録する
- パターンが見当たらない場合は空配列 [] にする

JSON のみ出力。説明文やマークダウンは不要。
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
            email_summary = self._gather_emails()
            recent_suggestions = self._gather_recent_suggestions()
            traits = gather_all_traits()
            traits_text = format_traits_for_prompt(traits)

            if not calendar_summary.strip():
                calendar_summary = "（今週の予定はありません）"

            log_queue.log("Analyzer", f"traits: {len(traits)}件の文脈定義を読み込み")
            if email_summary.strip() and email_summary != "（メール情報なし）":
                log_queue.log("Analyzer", "メール文脈を取得しました")

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
                email_summary=email_summary,
                recent_suggestions=recent_suggestions or "（なし）",
                traits=traits_text,
                memory=memory_text,
            )

            response = llm.completion(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "カレンダーを分析して提案を生成してください。"},
                ],
                temperature=0.7,
            )
            raw = response.choices[0].message.content.strip()

            # ── パース ────────────────────────────────────────
            suggestions, observations = self._parse_response(raw)

            # ── 観察をメモリに書き込み ─────────────────────────
            for obs in observations:
                obs = obs.strip()
                if obs:
                    db_client.add_machine_log(
                        action_type="memory_auto",
                        content=obs,
                    )
                    log_queue.log("Analyzer", f"観察: {obs}")

            # ── machine_logs に書き込み ───────────────────────
            for s in suggestions:
                stype = s.get("type", "calendar")
                reason = s.get("reason", "")
                message = s.get("message", "")

                if stype == "notify":
                    # 通知・リマインド系の提案
                    content = message
                    if reason:
                        content += f"\n理由: {reason}"
                    meta = json.dumps({"type": "notify"}, ensure_ascii=False)
                    content += f"\n<!--meta:{meta}-->"

                    db_client.add_machine_log(
                        action_type="general_suggest",
                        content=content,
                    )
                    log_queue.log("Analyzer", f"提案(通知): {message[:50]}")
                else:
                    # カレンダー提案
                    event_title = s.get("event_title", "")
                    event_date = s.get("event_date", "")
                    event_time = s.get("event_time", "09:00")

                    content = f"{message}\n提案: 「{event_title}」を {event_date} {event_time} に追加しませんか？"
                    if reason:
                        content += f"\n理由: {reason}"

                    meta = json.dumps({
                        "type": "calendar",
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
                    line += " [ダリー登録]"
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

    def _gather_emails(self) -> str:
        """最近のメール情報をテキストにまとめる（Gmail連携時のみ）。"""
        try:
            from .google_auth import is_authenticated
            if not is_authenticated():
                return "（メール情報なし — Google未連携）"

            from .functions.gmail import gmail_unread
            unread = gmail_unread(limit=5)
            if not unread or unread == "未読メールはありません。":
                return "（未読メールなし）"
            return f"### 未読メール（最新5件）\n{unread}"
        except Exception:
            return "（メール取得エラー）"

    def _gather_memory(self) -> str:
        """手動メモリ + マシン観察をテキストにまとめる。"""
        try:
            logs = db_client.get_machine_logs(limit=100)
            manual = [l for l in logs if l.get("action_type") == "memory"]
            auto = [l for l in logs if l.get("action_type") == "memory_auto"]
            lines = []
            if manual:
                lines.append("### ユーザーが記録")
                for m in manual:
                    c = m.get("content", "").strip()
                    if c:
                        lines.append(f"- {c}")
            if auto:
                lines.append("### ダリーの観察")
                for m in auto:
                    c = m.get("content", "").strip()
                    if c:
                        lines.append(f"- {c}")
            return "\n".join(lines) if lines else "（なし）"
        except Exception:
            return "（取得エラー）"

    def _gather_recent_suggestions(self) -> str:
        """最近の提案をテキストにまとめる（重複防止用）。"""
        try:
            logs = db_client.get_machine_logs(limit=30)
            lines = []
            for entry in logs:
                if entry.get("action_type") not in ("calendar_suggest", "general_suggest"):
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

    def _parse_response(self, raw: str) -> tuple[list[dict], list[str]]:
        """LLMレスポンスから提案と観察をパースする。

        Returns:
            (suggestions, observations)
        """
        # マークダウンコードブロックを除去
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # JSONオブジェクトまたは配列を抽出
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    data = None
            else:
                # 旧形式（配列のみ）へのフォールバック
                match = re.search(r"\[.*\]", raw, re.DOTALL)
                if match:
                    try:
                        arr = json.loads(match.group())
                        return (arr[:3] if isinstance(arr, list) else [], [])
                    except json.JSONDecodeError:
                        pass
                return ([], [])

        if data is None:
            return ([], [])

        # 新形式: {"suggestions": [...], "observations": [...]}
        if isinstance(data, dict):
            suggestions = data.get("suggestions", [])
            observations = data.get("observations", [])
            if isinstance(suggestions, list):
                suggestions = suggestions[:3]
            else:
                suggestions = []
            if isinstance(observations, list):
                observations = [o for o in observations[:2] if isinstance(o, str)]
            else:
                observations = []
            return (suggestions, observations)

        # 旧形式: 配列のみ
        if isinstance(data, list):
            return (data[:3], [])

        return ([], [])
