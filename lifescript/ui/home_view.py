"""ホーム画面 — ウィジェットボード。

スマホのホーム画面のように、LifeScript が操作できる「ウィジェット」が並ぶ。
関数ライブラリが増えると対応するウィジェットが追加される。

現在のウィジェット:
  - 時計         （常時表示）
  - カレンダー   （calendar.* で操作）
  - リマインダー （手動追加のタスク管理）
  - 通知         （notify() による通知履歴）
  - マシン提案   （calendar.suggest 等で自動表示）
  - 直近の予定   （カレンダーイベント）
"""

from __future__ import annotations

import calendar as cal_mod
from datetime import datetime, timedelta, timezone

import flet as ft

from ..database.client import db_client
from ..scheduler.scheduler import LifeScriptScheduler
from .app import (
    CARD_BG, BLUE, GREEN, CORAL, YELLOW, DARK_TEXT, MID_TEXT, LIGHT_TEXT,
    PURPLE, ORANGE, BG, SIDEBAR_BG, EDITOR_BG, EDITOR_FG,
)

_BORDER = "#E8E4DC"
_JST = timezone(timedelta(hours=9))


class HomeView:
    def __init__(self, page: ft.Page, scheduler: LifeScriptScheduler) -> None:
        self._page = page
        self._scheduler = scheduler
        self._logs: list[tuple[str, str, str]] = []
        self._cal_year = datetime.now().year
        self._cal_month = datetime.now().month

    def receive_logs(self, entries: list[tuple[str, str, str]]) -> None:
        self._logs = (entries + self._logs)[:50]

    def build(self) -> ft.Control:
        # ── Header ────────────────────────────────────────────
        now = datetime.now()
        hour = now.hour
        if hour < 6:
            greeting = "おやすみなさい"
            greeting_icon = ft.Icons.DARK_MODE_ROUNDED
            greeting_color = PURPLE
        elif hour < 12:
            greeting = "おはようございます"
            greeting_icon = ft.Icons.WB_SUNNY_ROUNDED
            greeting_color = ORANGE
        elif hour < 18:
            greeting = "こんにちは"
            greeting_icon = ft.Icons.LIGHT_MODE_ROUNDED
            greeting_color = YELLOW
        else:
            greeting = "こんばんは"
            greeting_icon = ft.Icons.NIGHTS_STAY_ROUNDED
            greeting_color = BLUE

        active_count = len(self._scheduler.get_active_ids())

        header = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(greeting_icon, size=28, color=CARD_BG),
                    width=48, height=48, bgcolor=greeting_color,
                    border_radius=14, alignment=ft.Alignment(0, 0),
                    shadow=ft.BoxShadow(
                        spread_radius=0, blur_radius=16,
                        color=f"{greeting_color}33", offset=ft.Offset(0, 4),
                    ),
                ),
                ft.Container(width=12),
                ft.Column([
                    ft.Text(greeting, size=26, weight=ft.FontWeight.W_800, color=DARK_TEXT),
                    ft.Row([
                        ft.Container(width=8, height=8, bgcolor=GREEN, border_radius=4),
                        ft.Text(
                            f"{active_count} 件のスクリプトが稼働中",
                            size=13, color=MID_TEXT,
                        ),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ], spacing=2),
                ft.Container(expand=True),
                ft.Text(
                    now.strftime("%m/%d"),
                    size=20, weight=ft.FontWeight.W_700, color=LIGHT_TEXT,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(bottom=14, top=4),
        )

        # ── ウィジェット群 ────────────────────────────────────
        clock_widget = self._widget_clock()
        calendar_widget = self._widget_calendar()
        reminder_widget = self._widget_reminders()
        notification_widget = self._widget_notifications()
        suggestion_widget = self._widget_suggestions()
        upcoming_widget = self._widget_upcoming()

        # ── ウィジェットグリッド配置 ──────────────────────────
        #  左列: 時計 + カレンダー + 通知
        #  右列: リマインダー + マシン提案 + 直近の予定
        return ft.Column([
            header,
            ft.Row([
                # 左列
                ft.Column([
                    clock_widget,
                    ft.Container(height=10),
                    calendar_widget,
                ], expand=2, spacing=0, scroll=ft.ScrollMode.AUTO),
                # 右列
                ft.Column([
                    notification_widget,
                    ft.Container(height=10),
                    reminder_widget,
                    ft.Container(height=10),
                    suggestion_widget,
                    ft.Container(height=10),
                    upcoming_widget,
                ], expand=3, spacing=0, scroll=ft.ScrollMode.AUTO),
            ], expand=True, spacing=14, vertical_alignment=ft.CrossAxisAlignment.START),
        ], expand=True, spacing=0)

    # ==================================================================
    # Widget: 時計
    # ==================================================================
    def _widget_clock(self) -> ft.Container:
        now = datetime.now()
        h_str = now.strftime("%H")
        m_str = now.strftime("%M")
        date_str = now.strftime("%Y年 %m月 %d日")
        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        weekday = weekday_names[now.weekday()]

        # 時間帯によってアクセントカラーを変える
        hour = now.hour
        if hour < 6:
            accent = PURPLE
        elif hour < 12:
            accent = ORANGE
        elif hour < 18:
            accent = BLUE
        else:
            accent = PURPLE

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    # 時
                    ft.Container(
                        content=ft.Text(h_str, size=52, weight=ft.FontWeight.W_300,
                                        color=DARK_TEXT, font_family="Courier New"),
                        bgcolor=CARD_BG,
                        border_radius=14,
                        padding=ft.padding.symmetric(horizontal=16, vertical=4),
                    ),
                    # コロン
                    ft.Column([
                        ft.Container(width=8, height=8, bgcolor=accent, border_radius=4),
                        ft.Container(height=8),
                        ft.Container(width=8, height=8, bgcolor=accent, border_radius=4),
                    ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    # 分
                    ft.Container(
                        content=ft.Text(m_str, size=52, weight=ft.FontWeight.W_300,
                                        color=DARK_TEXT, font_family="Courier New"),
                        bgcolor=CARD_BG,
                        border_radius=14,
                        padding=ft.padding.symmetric(horizontal=16, vertical=4),
                    ),
                ], alignment=ft.MainAxisAlignment.CENTER, spacing=12,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=8),
                ft.Container(
                    content=ft.Text(f"{date_str} ({weekday})", size=14,
                                    weight=ft.FontWeight.W_500, color=MID_TEXT),
                    bgcolor=CARD_BG,
                    border_radius=20,
                    padding=ft.padding.symmetric(horizontal=16, vertical=6),
                ),
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=f"{accent}15",
            border_radius=16,
            padding=ft.padding.symmetric(vertical=20, horizontal=20),
            alignment=ft.Alignment(0, 0),
            border=ft.border.all(1, f"{accent}30"),
        )

    # ==================================================================
    # Widget: カレンダー（月表示 + イベント一覧）
    # ==================================================================
    def _widget_calendar(self) -> ft.Container:
        year = self._cal_year
        month = self._cal_month
        today = datetime.now()

        # イベントを取得（日 → タイトルリストのマッピング）
        events_by_day: dict[int, list[str]] = {}
        month_events: list[dict] = []
        try:
            first = datetime(year, month, 1, tzinfo=_JST)
            last = datetime(year + (1 if month == 12 else 0),
                            (1 if month == 12 else month + 1), 1, tzinfo=_JST)
            month_events = db_client.get_events(
                start_from=first.isoformat(), start_to=last.isoformat(),
            )
            for ev in month_events:
                try:
                    d = datetime.fromisoformat(ev["start_at"].replace("Z", "+00:00"))
                    if d.year == year and d.month == month:
                        events_by_day.setdefault(d.day, []).append(ev.get("title", ""))
                except (ValueError, KeyError):
                    pass
        except Exception:
            pass

        # ナビ
        def _prev(e: ft.ControlEvent) -> None:
            self._cal_month = 12 if self._cal_month == 1 else self._cal_month - 1
            if self._cal_month == 12:
                self._cal_year -= 1
            self._page.update()

        def _next(e: ft.ControlEvent) -> None:
            self._cal_month = 1 if self._cal_month == 12 else self._cal_month + 1
            if self._cal_month == 1:
                self._cal_year += 1
            self._page.update()

        nav = ft.Row([
            ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_size=18, on_click=_prev,
                          style=ft.ButtonStyle(padding=4)),
            ft.Text(f"{year}/{month:02d}", size=16, weight=ft.FontWeight.W_600, color=DARK_TEXT),
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_size=18, on_click=_next,
                          style=ft.ButtonStyle(padding=4)),
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=0)

        # イベント色パレット（日ごとに循環）
        _ev_colors = [BLUE, PURPLE, GREEN, ORANGE, CORAL]

        # 曜日ヘッダー
        cell_w = 1 / 7  # 均等割
        wk = ft.Row(
            [ft.Container(
                content=ft.Text(d, size=12, color=LIGHT_TEXT, text_align=ft.TextAlign.CENTER),
                expand=True, alignment=ft.Alignment(0, 0),
            ) for d in ["月", "火", "水", "木", "金", "土", "日"]],
            spacing=2,
        )

        # 日付グリッド（セル内にイベントを表示）
        rows = []
        for week in cal_mod.monthcalendar(year, month):
            cells = []
            for day in week:
                if day == 0:
                    cells.append(ft.Container(expand=True, height=62))
                else:
                    is_today = (day == today.day and month == today.month and year == today.year)
                    day_events = events_by_day.get(day, [])

                    # 日番号
                    day_label = ft.Text(
                        str(day), size=12,
                        weight=ft.FontWeight.W_700 if is_today else ft.FontWeight.W_400,
                        color=CARD_BG if is_today else DARK_TEXT,
                    )
                    day_badge = ft.Container(
                        content=day_label,
                        width=22, height=22,
                        bgcolor=BLUE if is_today else ft.Colors.TRANSPARENT,
                        border_radius=11,
                        alignment=ft.Alignment(0, 0),
                    )

                    # イベントラベル（最大2件）
                    ev_labels: list[ft.Control] = []
                    for i, title in enumerate(day_events[:2]):
                        clr = _ev_colors[i % len(_ev_colors)]
                        ev_labels.append(ft.Container(
                            content=ft.Text(
                                title[:6], size=9, color=CARD_BG,
                                max_lines=1, overflow=ft.TextOverflow.CLIP,
                                no_wrap=True,
                            ),
                            bgcolor=clr, border_radius=3,
                            padding=ft.padding.symmetric(horizontal=3, vertical=1),
                            clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        ))
                    if len(day_events) > 2:
                        ev_labels.append(ft.Text(
                            f"+{len(day_events) - 2}", size=9, color=LIGHT_TEXT,
                        ))

                    cells.append(ft.Container(
                        content=ft.Column(
                            [day_badge, *ev_labels],
                            spacing=1,
                            horizontal_alignment=ft.CrossAxisAlignment.START,
                        ),
                        expand=True, height=62,
                        bgcolor=f"{BLUE}0A" if is_today else ft.Colors.TRANSPARENT,
                        border_radius=8,
                        padding=ft.padding.only(left=3, top=2, right=2, bottom=2),
                        border=ft.border.all(1, f"{BLUE}30" if is_today else "#F0EDE6"),
                    ))
            rows.append(ft.Row(cells, spacing=2))

        return ft.Container(
            content=ft.Column([
                nav, wk, *rows,
            ], spacing=3),
            bgcolor=CARD_BG,
            border_radius=16,
            padding=14,
            border=ft.border.all(1, _BORDER),
        )

    # ==================================================================
    # Widget: リマインダー
    # ==================================================================
    def _widget_reminders(self) -> ft.Container:
        items: list[ft.Control] = []
        try:
            logs = db_client.get_machine_logs(limit=30)
            for entry in logs:
                if entry.get("action_type") != "reminder":
                    continue
                content = entry.get("content", "")
                triggered = entry.get("triggered_at", "")[:16].replace("T", " ")
                items.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.PUSH_PIN_ROUNDED, size=18, color=PURPLE),
                        ft.Text(content, size=14, color=DARK_TEXT, expand=True,
                                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(vertical=6),
                    on_click=lambda e, c=content, t=triggered: self._show_detail(
                        "リマインダー", [("内容", c), ("登録日時", t)], PURPLE),
                    ink=True, border_radius=8,
                ))
                if len(items) >= 6:
                    break
        except Exception:
            pass

        if not items:
            items.append(ft.Container(
                content=ft.Text("リマインダーなし", size=14, color=LIGHT_TEXT, italic=True),
                padding=ft.padding.symmetric(vertical=8),
            ))

        def _add(e: ft.ControlEvent) -> None:
            self._show_add_dialog("reminder")

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.NOTIFICATIONS_NONE_ROUNDED, size=20, color=PURPLE),
                    ft.Text("リマインダー", size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                    ft.Container(expand=True),
                    ft.IconButton(ft.Icons.ADD_ROUNDED, icon_size=20, icon_color=PURPLE,
                                  tooltip="追加", style=ft.ButtonStyle(padding=4),
                                  on_click=_add),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=1, color=_BORDER),
                *items,
            ], spacing=4),
            bgcolor=CARD_BG,
            border_radius=16,
            padding=14,
            border=ft.border.all(1, _BORDER),
        )

    # ==================================================================
    # Widget: マシンの提案
    # ==================================================================
    @staticmethod
    def _strip_meta(content: str) -> str:
        """表示用にメタデータタグを除去する。"""
        import re as _re
        return _re.sub(r"\n<!--meta:.*?-->", "", content).strip()

    def _widget_suggestions(self) -> ft.Container:
        items: list[ft.Control] = []
        try:
            logs = db_client.get_machine_logs(limit=20)
            for entry in logs:
                if entry.get("action_type") != "calendar_suggest":
                    continue
                raw_content = entry.get("content", "")
                display = self._strip_meta(raw_content)
                triggered = entry.get("triggered_at", "")[:16].replace("T", " ")
                items.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.LIGHTBULB_ROUNDED, size=18, color=ORANGE),
                        ft.Text(display, size=14, color=DARK_TEXT, expand=True,
                                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.TextButton("承認", style=ft.ButtonStyle(
                            color=GREEN, padding=ft.padding.symmetric(horizontal=8, vertical=0),
                        ), on_click=lambda e, ent=entry: self._accept_suggestion(ent)),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(vertical=4),
                    on_click=lambda e, c=display, t=triggered: self._show_detail(
                        "マシンの提案", [("提案内容", c), ("提案日時", t)], ORANGE),
                    ink=True, border_radius=8,
                ))
                if len(items) >= 5:
                    break
        except Exception:
            pass

        if not items:
            items.append(ft.Container(
                content=ft.Text("提案なし — 「分析」で提案を生成できます", size=14, color=LIGHT_TEXT, italic=True),
                padding=ft.padding.symmetric(vertical=8),
            ))

        def _on_analyze(e: ft.ControlEvent) -> None:
            import threading
            def _run() -> None:
                self._scheduler.run_analysis_now()
                self._page.update()
            threading.Thread(target=_run, daemon=True).start()

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=20, color=ORANGE),
                    ft.Text("マシンの提案", size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                    ft.Container(expand=True),
                    ft.IconButton(ft.Icons.REFRESH_ROUNDED, icon_size=20, icon_color=ORANGE,
                                  tooltip="文脈を分析して提案を生成",
                                  style=ft.ButtonStyle(padding=4),
                                  on_click=_on_analyze),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=1, color=_BORDER),
                *items,
            ], spacing=4),
            bgcolor=CARD_BG,
            border_radius=16,
            padding=14,
            border=ft.border.all(1, _BORDER),
        )

    # ==================================================================
    # Widget: 直近の予定
    # ==================================================================
    def _widget_upcoming(self) -> ft.Container:
        now = datetime.now(_JST)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_3days = today_start + timedelta(days=3)

        items: list[ft.Control] = []
        try:
            events = db_client.get_events(
                start_from=today_start.isoformat(), start_to=end_3days.isoformat(),
            )
            for ev in events[:8]:
                start = ev.get("start_at", "")
                date_part = ""
                time_part = ""
                try:
                    d = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    date_part = f"{d.month}/{d.day}"
                    time_part = d.strftime("%H:%M")
                except (ValueError, KeyError):
                    parts = start[:16].split("T")
                    date_part = parts[0][5:] if parts else ""
                    time_part = parts[1] if len(parts) > 1 else ""
                source = ev.get("source", "user")
                ev_title = ev.get("title", "")
                ev_note = ev.get("note", "")
                source_label = "マシン" if source == "machine" else "手動"
                accent = PURPLE if source == "machine" else BLUE
                items.append(ft.Container(
                    content=ft.Row([
                        ft.Container(
                            width=4, height=36,
                            bgcolor=accent,
                            border_radius=2,
                        ),
                        ft.Column([
                            ft.Text(ev_title, size=14,
                                    weight=ft.FontWeight.W_600, color=DARK_TEXT,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(f"{date_part} {time_part}", size=12, color=LIGHT_TEXT),
                        ], spacing=1, expand=True),
                    ], spacing=8),
                    padding=ft.padding.symmetric(vertical=4),
                    on_click=lambda e, t=ev_title, dp=date_part, tp=time_part,
                                    n=ev_note, s=source_label, a=accent: self._show_detail(
                        t, [("日付", dp), ("時刻", tp), ("メモ", n), ("ソース", s)], a),
                    ink=True, border_radius=8,
                ))
        except Exception:
            pass

        if not items:
            items.append(ft.Container(
                content=ft.Text("直近の予定なし", size=14, color=LIGHT_TEXT, italic=True),
                padding=ft.padding.symmetric(vertical=8),
            ))

        def _add(e: ft.ControlEvent) -> None:
            self._show_add_dialog("event")

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.EVENT_ROUNDED, size=20, color=BLUE),
                    ft.Text("直近の予定", size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                    ft.Container(expand=True),
                    ft.IconButton(ft.Icons.ADD_ROUNDED, icon_size=20, icon_color=BLUE,
                                  tooltip="追加", style=ft.ButtonStyle(padding=4),
                                  on_click=_add),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=1, color=_BORDER),
                *items,
            ], spacing=4),
            bgcolor=CARD_BG,
            border_radius=16,
            padding=14,
            border=ft.border.all(1, _BORDER),
        )

    # ==================================================================
    # Widget: 通知
    # ==================================================================
    def _widget_notifications(self) -> ft.Container:
        items: list[ft.Control] = []
        try:
            logs = db_client.get_machine_logs(limit=30)
            for entry in logs:
                at = entry.get("action_type", "")
                if at not in ("notify", "notify_scheduled"):
                    continue
                content = entry.get("content", "")
                time_str = entry.get("triggered_at", "")[:16].replace("T", " ")
                icon_map = {
                    "notify": (ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED, GREEN),
                    "notify_scheduled": (ft.Icons.SCHEDULE_ROUNDED, BLUE),
                }
                ic, clr = icon_map.get(at, (ft.Icons.CIRCLE, MID_TEXT))
                type_label = "即時通知" if at == "notify" else "予約通知"
                items.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ic, size=18, color=clr),
                        ft.Column([
                            ft.Text(content, size=14, color=DARK_TEXT,
                                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(time_str, size=12, color=LIGHT_TEXT),
                        ], spacing=1, expand=True),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(vertical=4),
                    on_click=lambda e, c=content, ts=time_str, tl=type_label, cl=clr: self._show_detail(
                        "通知", [("内容", c), ("種類", tl), ("日時", ts)], cl),
                    ink=True, border_radius=8,
                ))
                if len(items) >= 6:
                    break
        except Exception:
            pass

        if not items:
            items.append(ft.Container(
                content=ft.Text("通知なし", size=14, color=LIGHT_TEXT, italic=True),
                padding=ft.padding.symmetric(vertical=8),
            ))

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.NOTIFICATIONS_NONE_ROUNDED, size=20, color=GREEN),
                    ft.Text("通知", size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=1, color=_BORDER),
                *items,
            ], spacing=4),
            bgcolor=CARD_BG,
            border_radius=16,
            padding=14,
            border=ft.border.all(1, _BORDER),
        )

    # ==================================================================
    # 詳細ダイアログ
    # ==================================================================
    def _show_detail(self, title: str, rows: list[tuple[str, str]],
                     accent: str = BLUE) -> None:
        """汎用の詳細表示ダイアログ。rows は (ラベル, 値) のリスト。"""
        content_items: list[ft.Control] = []
        for label, value in rows:
            content_items.append(ft.Container(
                content=ft.Column([
                    ft.Text(label, size=12, weight=ft.FontWeight.W_600, color=MID_TEXT),
                    ft.Text(value or "—", size=14, color=DARK_TEXT, selectable=True),
                ], spacing=2),
                padding=ft.padding.only(bottom=10),
            ))

        dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Container(width=6, height=24, bgcolor=accent, border_radius=3),
                ft.Text(title, size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT,
                        expand=True, max_lines=2),
            ], spacing=10),
            content=ft.Column(content_items, tight=True, spacing=4,
                              scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton(
                "閉じる",
                on_click=lambda e: setattr(dialog, "open", False) or self._page.update(),
            )],
        )
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()

    # ==================================================================
    # 提案の承認
    # ==================================================================
    def _accept_suggestion(self, entry: dict) -> None:
        import json as _json
        import re as _re

        content = entry.get("content", "")

        # メタデータからイベント情報を抽出
        meta_match = _re.search(r"<!--meta:(.*?)-->", content)
        if meta_match:
            try:
                meta = _json.loads(meta_match.group(1))
                title = meta.get("event_title", "承認済みイベント")
                date_str = meta.get("event_date", "")
                time_str = meta.get("event_time", "09:00")

                if date_str:
                    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                    dt = dt.replace(tzinfo=_JST)
                else:
                    now = datetime.now(_JST)
                    dt = (now + timedelta(days=1)).replace(
                        hour=9, minute=0, second=0, microsecond=0)
            except (ValueError, KeyError, _json.JSONDecodeError):
                title, dt = self._fallback_parse(content)
        else:
            title, dt = self._fallback_parse(content)

        db_client.add_event(title=title, start_at=dt.isoformat(), source="machine")
        db_client.add_machine_log(
            action_type="calendar_add",
            content=f"提案を承認: 「{title}」を {dt.strftime('%m/%d %H:%M')} に追加しました",
        )
        self._page.update()

    @staticmethod
    def _fallback_parse(content: str) -> tuple[str, datetime]:
        """メタデータがない旧形式の提案からタイトルと日時を抽出する。"""
        title = "承認済みイベント"
        if "「" in content and "」" in content:
            title = content.split("「")[1].split("」")[0]
        now = datetime.now(_JST)
        dt = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        return title, dt

    # ==================================================================
    # 追加ダイアログ
    # ==================================================================
    def _show_add_dialog(self, mode: str) -> None:
        is_reminder = mode == "reminder"
        dialog_title = "リマインダー追加" if is_reminder else "イベント追加"

        title_field = ft.TextField(
            label="内容" if is_reminder else "タイトル",
            autofocus=True,
            text_size=14,
        )
        date_field = ft.TextField(
            label="通知日時 (空欄で即時)" if is_reminder else "日時 (YYYY-MM-DD HH:MM)",
            value="" if is_reminder else datetime.now().strftime("%Y-%m-%d %H:%M"),
            hint_text="YYYY-MM-DD HH:MM",
            text_size=14,
        )

        fields: list[ft.Control] = [title_field, date_field]
        if not is_reminder:
            note_field = ft.TextField(label="メモ (任意)", text_size=14)
            fields.append(note_field)
        else:
            note_field = None

        def _save(ev: ft.ControlEvent) -> None:
            text = title_field.value.strip()
            if not text:
                return

            date_str = date_field.value.strip()

            if is_reminder:
                if date_str:
                    try:
                        datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                    except ValueError:
                        date_field.error_text = "形式: YYYY-MM-DD HH:MM"
                        self._page.update()
                        return
                    db_client.add_machine_log(action_type="reminder",
                                              content=f"[{date_str}] {text}")
                else:
                    db_client.add_machine_log(action_type="reminder", content=text)
            else:
                if not date_str:
                    date_field.error_text = "日時を入力してください"
                    self._page.update()
                    return
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                    dt = dt.replace(tzinfo=_JST)
                except ValueError:
                    date_field.error_text = "形式: YYYY-MM-DD HH:MM"
                    self._page.update()
                    return
                db_client.add_event(
                    title=text, start_at=dt.isoformat(),
                    note=(note_field.value.strip() if note_field else ""),
                    source="user",
                )

            dialog.open = False
            self._page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(dialog_title, size=18, weight=ft.FontWeight.W_600),
            content=ft.Column(fields, tight=True, spacing=12),
            actions=[
                ft.TextButton("キャンセル",
                              on_click=lambda ev: setattr(dialog, "open", False) or self._page.update()),
                ft.ElevatedButton("追加", bgcolor=PURPLE if is_reminder else BLUE,
                                  color=CARD_BG, on_click=_save),
            ],
        )
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()
