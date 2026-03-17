"""チャットエンジン — 2つのモード。

1. CodingChat: IDE用。DSL生成に特化。
2. ConciergeChat: コンシェルジュ用。全コンテキストを持ち、即時アクションも実行。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from . import llm

from .database.client import db_client
from .functions import FUNCTION_DESCRIPTIONS
from .functions.calendar import calendar_add, calendar_suggest
from .functions.notify import notify
from .traits import gather_all_traits, format_traits_for_prompt
from . import log_queue

_JST = timezone(timedelta(hours=9))

# ======================================================================
# IDE用: コーディングチャット
# ======================================================================
_CODING_PROMPT = """\
あなたは LifeScript のコーディングアシスタントです。
ユーザーがやりたいことを伝えてくるので、LifeScript DSL コードを生成してください。

## LifeScript とは
「ダリー」という相棒に自分の生活文脈を伝えるための DSL です。

## 使える関数
{functions_section}

## DSL の書き方

```yaml
# 条件付き実行
when calendar.read("バイト").count_this_week >= 4:
  calendar.suggest("回復タイム", on="next_free_morning")

# 時刻トリガー（毎日その時刻に実行）
when 08:00:
  notify("おはよう！今日も頑張ろう")

# 定期実行
every day:
  notify("日報を書こう")

# カレンダー操作
calendar.add("ミーティング", start="2026-03-20T14:00:00")

# 通知
notify("傘を持って", at="2026-03-20T07:00:00")
```

## 応答ルール
1. DSL コードは必ず ```lifescript ... ``` のコードブロックで囲む
2. コードの前後に簡潔な説明を添える（日本語）
3. ユーザーの意図を汲み取り、最適な関数とトリガーを選ぶ
4. 複雑な要件は複数のルールに分けて書く
5. コードの生成に集中する。予定の追加や通知の実行はしない
6. 短く簡潔に答える
"""

# ======================================================================
# コンシェルジュ用: 全コンテキスト付きチャット
# ======================================================================
_CONCIERGE_PROMPT = """\
あなたは LifeScript のコンシェルジュ「ダリー」です。
ダリーは黄色い丸いロボットのキャラクターで、ユーザーの生活に寄り添う相棒です。
ユーザーの生活文脈を全て把握しており、カレンダー管理・通知・生活全般を支援します。
話し方は親しみやすく、少しおせっかいだけど頼りになるトーンで。一人称は「ダリー」。

## 現在の日時
{now}

## ユーザーの traits（生活文脈の自己定義）
{traits}

traits はユーザーが LifeScript で自分の生活パターンや価値観を言語化したものです。
回答や提案をする際は traits を考慮し、必要に応じて「あなたの traits に基づくと〜」と根拠を示してください。

## あなたができること

### 1. 即時アクション（ユーザーの指示で直接実行）
ユーザーが「〇〇の予定入れて」「通知して」と言ったら、以下のアクションブロックで即実行します。

アクションブロックの書き方:
```action
{{"action": "calendar_add", "title": "イベント名", "start": "YYYY-MM-DDTHH:MM:SS", "note": ""}}
```
```action
{{"action": "notify", "message": "通知メッセージ", "at": "YYYY-MM-DDTHH:MM:SS"}}
```
```action
{{"action": "calendar_suggest", "title": "提案名", "on": "日付の説明"}}
```
```action
{{"action": "gmail_summarize", "limit": 5}}
```
```action
{{"action": "gmail_search", "query": "from:example.com", "limit": 5}}
```
```action
{{"action": "gmail_send", "to": "宛先@example.com", "subject": "件名", "body": "本文"}}
```

- at を省略すると即時通知
- 「明日」「来週月曜」などは具体的な日付に変換すること（現在: {now}）
- アクションブロックの前後に説明文を添えること
- Gmail系アクションはGoogle認証済みの場合のみ利用可能

### 2. LifeScript DSL（コピペ用に表示のみ）
定期実行ルールを作りたい場合は DSL コードを ```lifescript ... ``` で囲んで表示。
IDEにコピペして使ってもらう前提。

### 3. 会話・質問への回答
予定の確認、生活のアドバイスなど。

### 4. リッチなサマリー・概要
ユーザーが「今週の予定は？」「最近何があった？」「通知の状況は？」などと聞いたら、
持っている全コンテキストを使って**見やすく整理されたサマリー**を返す。

サマリーの書き方:
- 日付ごと・カテゴリごとに整理する
- 重要なものは強調する（「**バイト**」など）
- 空き時間や傾向（忙しさ、偏り）にも言及する
- 提案やアドバイスがあれば最後に添える
- 絵文字は使わない

例:
```
今週の予定（3/15〜3/21）

月曜: バイト 10:00-14:00
火曜: 予定なし（空き）
水曜: ミーティング 15:00 / バイト 18:00-22:00
...

→ 今週はバイトが3回。木曜が空いているので休息日にするのも良さそうです。
```

## 使える関数
{functions_section}

## ユーザーのカレンダー（今週〜来週）
{calendar_context}

## 最近のマシンログ
{recent_logs}

## 登録済みスクリプト
{active_scripts}

## メモリ（ユーザーのパーソナリティ）
{memory}

## 応答ルール
1. 短く簡潔に答える（日本語）
2. 予定の追加や通知は即座にアクションブロックで実行する
3. 定期ルールの場合のみ DSL コードを表示（コピペ用）
4. ユーザーの予定を把握した上で提案や回答をする
5. 日付・時刻は必ず具体的な値にする（「明日」→実際の日付）
6. ダリーとしてのキャラクターを保ちながら、フレンドリーで簡潔なトーン
7. 予定の概要やサマリーを聞かれたら、日別に整理して見やすく回答する
8. 通知やスクリプトの状況を聞かれたら、わかりやすく一覧化する
"""


def _build_functions_section() -> str:
    lines = []
    for f in FUNCTION_DESCRIPTIONS:
        lines.append(f"- `{f['signature']}`  — {f['description']}")
    return "\n".join(lines)


def _gather_calendar_context() -> str:
    try:
        now = datetime.now(_JST)
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        two_weeks = week_start + timedelta(days=14)
        events = db_client.get_events(
            start_from=week_start.isoformat(),
            start_to=two_weeks.isoformat(),
        )
        if not events:
            return "（予定なし）"
        lines = []
        for ev in events:
            start = ev.get("start_at", "")
            title = ev.get("title", "")
            note = ev.get("note", "")
            source = ev.get("source", "user")
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
        return "\n".join(lines)
    except Exception:
        return "（取得エラー）"


def _gather_recent_logs() -> str:
    try:
        logs = db_client.get_machine_logs(limit=10)
        if not logs:
            return "（なし）"
        lines = []
        for entry in logs:
            at = entry.get("action_type", "")
            content = entry.get("content", "")
            content = re.sub(r"\n<!--meta:.*?-->", "", content).strip()
            time_str = entry.get("triggered_at", "")[:16].replace("T", " ")
            lines.append(f"- [{at}] {content[:60]} ({time_str})")
        return "\n".join(lines)
    except Exception:
        return "（取得エラー）"


def _gather_memory() -> str:
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


def _gather_active_scripts() -> str:
    try:
        scripts = db_client.get_scripts()
        if not scripts:
            return "（なし）"
        lines = []
        for s in scripts:
            name = s.get("name", "") or f"Script#{s['id']}"
            dsl = (s.get("dsl_text", "") or "")[:60].replace("\n", " ")
            lines.append(f"- {name}: {dsl}")
        return "\n".join(lines)
    except Exception:
        return "（取得エラー）"


# ======================================================================
# コーディングチャット（IDE用）
# ======================================================================
class CodingChat:
    """IDE用: DSL生成に特化したチャット。"""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or os.getenv("LIFESCRIPT_MODEL", "gemini/gemini-2.5-flash")
        self._history: list[dict[str, str]] = []
        functions_section = _build_functions_section()
        self._system_prompt = _CODING_PROMPT.format(functions_section=functions_section)

    def send(self, user_message: str) -> str:
        """ユーザーメッセージを送信し、応答テキストを返す。"""
        self._history.append({"role": "user", "content": user_message})
        messages = [
            {"role": "system", "content": self._system_prompt},
            *self._history[-20:],
        ]
        response = llm.completion(
            model=self._model, messages=messages, temperature=0.3,
        )
        reply = response.choices[0].message.content.strip()
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def clear(self) -> None:
        self._history.clear()


# ======================================================================
# コンシェルジュチャット（汎用チャット画面用）
# ======================================================================
class ChatEngine:
    """全コンテキストを持つコンシェルジュチャット。"""

    def __init__(self, model: str | None = None) -> None:
        self._model = model or os.getenv("LIFESCRIPT_MODEL", "gemini/gemini-2.5-flash")
        self._history: list[dict[str, str]] = []

    def _build_system_prompt(self) -> str:
        now = datetime.now(_JST)
        traits = gather_all_traits()
        return _CONCIERGE_PROMPT.format(
            now=now.strftime("%Y-%m-%d %H:%M (%A)"),
            traits=format_traits_for_prompt(traits),
            functions_section=_build_functions_section(),
            calendar_context=_gather_calendar_context(),
            recent_logs=_gather_recent_logs(),
            active_scripts=_gather_active_scripts(),
            memory=_gather_memory(),
        )

    def send(self, user_message: str) -> tuple[str, list[dict]]:
        """ユーザーメッセージを送信し、(応答テキスト, 実行されたアクション一覧) を返す。"""
        self._history.append({"role": "user", "content": user_message})
        system_prompt = self._build_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            *self._history[-20:],
        ]
        response = llm.completion(
            model=self._model, messages=messages, temperature=0.3,
        )
        reply = response.choices[0].message.content.strip()
        executed_actions = self._execute_actions(reply)
        self._history.append({"role": "assistant", "content": reply})
        return reply, executed_actions

    def _execute_actions(self, reply: str) -> list[dict]:
        actions = []
        pattern = r"```action\s*\n?(.*?)```"
        for match in re.finditer(pattern, reply, re.DOTALL):
            raw_block = match.group(0)
            raw_json = match.group(1).strip()
            try:
                data = json.loads(raw_json)
                result = self._run_action(data)
                result["raw_block"] = raw_block
                actions.append(result)
            except json.JSONDecodeError:
                actions.append({
                    "success": False,
                    "description": "アクションのパースに失敗",
                    "raw_block": raw_block,
                })
        return actions

    def _run_action(self, data: dict) -> dict:
        action = data.get("action", "")
        try:
            if action == "calendar_add":
                title = data["title"]
                start = data["start"]
                note = data.get("note", "")
                calendar_add(title=title, start=start, note=note)
                desc = f"カレンダーに追加: {title}"
                log_queue.log("Chat", desc)
                return {"success": True, "description": desc}
            elif action == "notify":
                message = data["message"]
                at = data.get("at")
                notify(message=message, at=at)
                desc = f"通知: {message}"
                log_queue.log("Chat", desc)
                return {"success": True, "description": desc}
            elif action == "calendar_suggest":
                title = data["title"]
                on = data.get("on", "")
                calendar_suggest(title=title, on=on)
                desc = f"提案を登録: {title}"
                log_queue.log("Chat", desc)
                return {"success": True, "description": desc}
            elif action == "gmail_summarize":
                from .functions.gmail import gmail_summarize
                limit = data.get("limit", 5)
                result = gmail_summarize(limit=limit)
                log_queue.log("Chat", "メールを要約しました")
                return {"success": True, "description": f"メール要約:\n{result}"}
            elif action == "gmail_search":
                from .functions.gmail import gmail_search
                query = data["query"]
                limit = data.get("limit", 5)
                emails = gmail_search(query=query, limit=limit)
                if not emails:
                    desc = f"「{query}」に一致するメールはありません"
                else:
                    lines = [f"検索結果: {len(emails)}件"]
                    for e in emails:
                        lines.append(f"- {e['subject']} (from: {e['from'][:30]})")
                    desc = "\n".join(lines)
                log_queue.log("Chat", f"Gmail検索: {query}")
                return {"success": True, "description": desc}
            elif action == "gmail_send":
                from .functions.gmail import gmail_send
                to = data["to"]
                subject = data["subject"]
                body = data["body"]
                result = gmail_send(to=to, subject=subject, body=body)
                log_queue.log("Chat", f"メール送信: {to}")
                return {"success": True, "description": result}
            else:
                return {"success": False, "description": f"未知のアクション: {action}"}
        except Exception as e:
            return {"success": False, "description": f"実行エラー: {e}"}

    def clear(self) -> None:
        self._history.clear()
