"""gmail_* — Gmail API 連携関数群。

Google OAuth 認証済みの場合のみ動作する。
DSLから呼び出し可能: gmail_unread(), gmail_search(), gmail_summarize()
"""

from __future__ import annotations

import base64
import os
import re
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from typing import Any

from .. import log_queue
from ..google_auth import get_credentials, is_authenticated

_JST = timezone(timedelta(hours=9))


def _get_service():
    """Gmail APIサービスを取得する。"""
    if not is_authenticated():
        raise RuntimeError("Google認証がされていません。設定画面からGoogleアカウントを連携してください。")
    creds = get_credentials()
    if creds is None:
        raise RuntimeError("Google認証の有効期限が切れています。再認証してください。")
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=creds)


def _extract_body(payload: dict) -> str:
    """メールのペイロードからテキスト本文を抽出する。"""
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    parts = payload.get("parts", [])
    for part in parts:
        mime = part.get("mimeType", "")
        if mime == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
    # multipart の再帰
    for part in parts:
        if part.get("parts"):
            result = _extract_body(part)
            if result:
                return result
    return ""


def _parse_message(msg: dict) -> dict:
    """Gmail APIのメッセージを簡易dictに変換する。"""
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body = _extract_body(msg.get("payload", {}))
    # 本文が長すぎる場合は切り詰め
    if len(body) > 2000:
        body = body[:2000] + "…（省略）"

    return {
        "id": msg.get("id", ""),
        "subject": headers.get("subject", "(件名なし)"),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "date": headers.get("date", ""),
        "snippet": msg.get("snippet", ""),
        "body": body,
        "labels": msg.get("labelIds", []),
    }


def gmail_unread(limit: int = 10) -> list[dict]:
    """未読メールを取得する。

    Args:
        limit: 最大取得件数（デフォルト10）

    Returns:
        メールのリスト。各要素は {subject, from, date, snippet, body} を持つdict。
    """
    try:
        service = _get_service()
        results = service.users().messages().list(
            userId="me", q="is:unread", maxResults=min(limit, 20),
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            log_queue.log("Gmail", "未読メールはありません")
            return []

        emails = []
        for m in messages:
            full = service.users().messages().get(
                userId="me", id=m["id"], format="full",
            ).execute()
            emails.append(_parse_message(full))

        log_queue.log("Gmail", f"未読メール {len(emails)}件を取得")
        return emails
    except Exception as e:
        log_queue.log("Gmail", f"エラー: {e}", "ERROR")
        raise


def gmail_search(query: str, limit: int = 10) -> list[dict]:
    """Gmailを検索する。

    Args:
        query: Gmail検索クエリ（例: "from:amazon.co.jp", "subject:請求書"）
        limit: 最大取得件数

    Returns:
        メールのリスト。
    """
    try:
        service = _get_service()
        results = service.users().messages().list(
            userId="me", q=query, maxResults=min(limit, 20),
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            log_queue.log("Gmail", f"検索「{query}」: 0件")
            return []

        emails = []
        for m in messages:
            full = service.users().messages().get(
                userId="me", id=m["id"], format="full",
            ).execute()
            emails.append(_parse_message(full))

        log_queue.log("Gmail", f"検索「{query}」: {len(emails)}件")
        return emails
    except Exception as e:
        log_queue.log("Gmail", f"検索エラー: {e}", "ERROR")
        raise


def gmail_summarize(limit: int = 5) -> str:
    """未読メールをLLMで要約して返す。

    Args:
        limit: 要約対象の最大件数

    Returns:
        要約テキスト。
    """
    try:
        emails = gmail_unread(limit=limit)
        if not emails:
            return "未読メールはありません。"

        # メール一覧をテキスト化
        lines = []
        for i, e in enumerate(emails, 1):
            lines.append(f"--- メール {i} ---")
            lines.append(f"件名: {e['subject']}")
            lines.append(f"差出人: {e['from']}")
            lines.append(f"日時: {e['date']}")
            lines.append(f"本文: {e['body'][:500]}")
            lines.append("")
        email_text = "\n".join(lines)

        # LLMで要約
        from .. import llm
        model = os.getenv("LIFESCRIPT_MODEL", "gemini/gemini-2.5-flash")
        response = llm.completion(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "以下のメール一覧を日本語で簡潔に要約してください。"
                    "各メールについて、差出人・件名・要点を1-2行でまとめてください。"
                    "重要度が高そうなものは先に記述してください。"
                )},
                {"role": "user", "content": email_text},
            ],
            temperature=0.2,
        )
        summary = response.choices[0].message.content.strip()
        log_queue.log("Gmail", f"未読{len(emails)}件を要約しました")
        return summary
    except Exception as e:
        log_queue.log("Gmail", f"要約エラー: {e}", "ERROR")
        return f"メール要約中にエラーが発生しました: {e}"


def gmail_send(to: str, subject: str, body: str) -> str:
    """メールを送信する。

    Args:
        to: 宛先メールアドレス
        subject: 件名
        body: 本文

    Returns:
        送信結果のメッセージ。
    """
    try:
        service = _get_service()
        message = MIMEText(body, "plain", "utf-8")
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        service.users().messages().send(
            userId="me", body={"raw": raw},
        ).execute()

        log_queue.log("Gmail", f"送信完了: {to} / {subject}")
        return f"メールを送信しました: {to}"
    except Exception as e:
        log_queue.log("Gmail", f"送信エラー: {e}", "ERROR")
        raise
