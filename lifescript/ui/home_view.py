"""ホーム画面 — ウィジェットボード。

スマホのホーム画面のように、LifeScript が操作できる「ウィジェット」が並ぶ。
関数ライブラリが増えると対応するウィジェットが追加される。

現在のウィジェット:
  - 時計         （常時表示）
  - カレンダー   （calendar.* で操作）
  - リマインダー （notify / 手動追加）
  - マシン提案   （calendar.suggest 等で自動表示）
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
        hour = datetime.now().hour
        if hour < 6:
            greeting = "おやすみなさい"
        elif hour < 12:
            greeting = "おはようございます"
        elif hour < 18:
            greeting = "こんにちは"
        else:
            greeting = "こんばんは"

        active_count = len(self._scheduler.get_active_ids())

        header = ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(greeting, size=24, weight=ft.FontWeight.W_800, color=DARK_TEXT),
                    ft.Text(
                        f"{active_count} 件のスクリプトが稼働中",
                        size=12, color=MID_TEXT,
                    ),
                ], spacing=2),
                ft.Container(expand=True),
            ]),
            padding=ft.padding.only(bottom=12),
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
                    ft.Container(height=10),
                    notification_widget,
                ], expand=2, spacing=0),
                # 右列
                ft.Column([
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
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%Y年 %m月 %d日")
        weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
        weekday = weekday_names[now.weekday()]

        return ft.Container(
            content=ft.Column([
                ft.Text(time_str, size=48, weight=ft.FontWeight.W_200, color=CARD_BG,
                        font_family="Courier New"),
                ft.Text(f"{date_str} ({weekday})", size=13, color=f"{CARD_BG}BB"),
            ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=EDITOR_BG,
            border_radius=16,
            padding=ft.padding.symmetric(vertical=24, horizontal=20),
            alignment=ft.Alignment(0, 0),
        )

    # ==================================================================
    # Widget: カレンダー（コンパクト月表示）
    # ==================================================================
    def _widget_calendar(self) -> ft.Container:
        year = self._cal_year
        month = self._cal_month
        today = datetime.now()

        # イベントがある日を取得
        event_days: set[int] = set()
        try:
            first = datetime(year, month, 1, tzinfo=timezone.utc)
            last = datetime(year + (1 if month == 12 else 0),
                            (1 if month == 12 else month + 1), 1, tzinfo=timezone.utc)
            for ev in db_client.get_events(start_from=first.isoformat(), start_to=last.isoformat()):
                try:
                    d = datetime.fromisoformat(ev["start_at"].replace("Z", "+00:00"))
                    if d.year == year and d.month == month:
                        event_days.add(d.day)
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
            ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_size=16, on_click=_prev,
                          style=ft.ButtonStyle(padding=4)),
            ft.Text(f"{year}/{month:02d}", size=13, weight=ft.FontWeight.W_600, color=DARK_TEXT),
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_size=16, on_click=_next,
                          style=ft.ButtonStyle(padding=4)),
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=0)

        # 曜日
        wk = ft.Row(
            [ft.Container(
                content=ft.Text(d, size=10, color=LIGHT_TEXT, text_align=ft.TextAlign.CENTER),
                width=30, alignment=ft.Alignment(0, 0),
            ) for d in ["月", "火", "水", "木", "金", "土", "日"]],
            alignment=ft.MainAxisAlignment.CENTER, spacing=1,
        )

        # 日付
        rows = []
        for week in cal_mod.monthcalendar(year, month):
            cells = []
            for day in week:
                if day == 0:
                    cells.append(ft.Container(width=30, height=30))
                else:
                    is_today = (day == today.day and month == today.month and year == today.year)
                    has_ev = day in event_days
                    cells.append(ft.Container(
                        content=ft.Column([
                            ft.Text(str(day), size=11,
                                    weight=ft.FontWeight.W_600 if is_today else ft.FontWeight.W_400,
                                    color=CARD_BG if is_today else DARK_TEXT,
                                    text_align=ft.TextAlign.CENTER),
                            ft.Container(width=4, height=4,
                                         bgcolor=(CARD_BG if is_today else BLUE) if has_ev else ft.Colors.TRANSPARENT,
                                         border_radius=4),
                        ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        width=30, height=30,
                        bgcolor=BLUE if is_today else ft.Colors.TRANSPARENT,
                        border_radius=15,
                        alignment=ft.Alignment(0, 0),
                    ))
            rows.append(ft.Row(cells, alignment=ft.MainAxisAlignment.CENTER, spacing=1))

        return ft.Container(
            content=ft.Column([nav, wk, *rows], spacing=2,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=CARD_BG,
            border_radius=16,
            padding=12,
            border=ft.border.all(1, _BORDER),
        )

    # ==================================================================
    # Widget: リマインダー
    # ==================================================================
    def _widget_reminders(self) -> ft.Container:
        # machine_logs から reminder のみ取得（タスク管理用）
        items: list[ft.Control] = []
        try:
            logs = db_client.get_machine_logs(limit=30)
            for entry in logs:
                if entry.get("action_type") != "reminder":
                    continue
                content = entry.get("content", "")
                items.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.PUSH_PIN_ROUNDED, size=16, color=PURPLE),
                        ft.Text(content, size=12, color=DARK_TEXT, expand=True,
                                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(vertical=6),
                ))
                if len(items) >= 6:
                    break
        except Exception:
            pass

        if not items:
            items.append(ft.Container(
                content=ft.Text("リマインダーなし", size=12, color=LIGHT_TEXT, italic=True),
                padding=ft.padding.symmetric(vertical=8),
            ))

        def _add(e: ft.ControlEvent) -> None:
            self._show_add_dialog("reminder")

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.NOTIFICATIONS_NONE_ROUNDED, size=18, color=PURPLE),
                    ft.Text("リマインダー", size=14, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                    ft.Container(expand=True),
                    ft.IconButton(ft.Icons.ADD_ROUNDED, icon_size=18, icon_color=PURPLE,
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
    def _widget_suggestions(self) -> ft.Container:
        items: list[ft.Control] = []
        try:
            logs = db_client.get_machine_logs(limit=20)
            for entry in logs:
                if entry.get("action_type") != "calendar_suggest":
                    continue
                content = entry.get("content", "")
                items.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.LIGHTBULB_ROUNDED, size=16, color=ORANGE),
                        ft.Text(content, size=12, color=DARK_TEXT, expand=True,
                                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.TextButton("承認", style=ft.ButtonStyle(
                            color=GREEN, padding=ft.padding.symmetric(horizontal=6, vertical=0),
                        ), on_click=lambda e, ent=entry: self._accept_suggestion(ent)),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(vertical=4),
                ))
                if len(items) >= 5:
                    break
        except Exception:
            pass

        if not items:
            items.append(ft.Container(
                content=ft.Text("提案なし", size=12, color=LIGHT_TEXT, italic=True),
                padding=ft.padding.symmetric(vertical=8),
            ))

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=18, color=ORANGE),
                    ft.Text("マシンの提案", size=14, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                ], spacing=6),
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
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_3days = today_start + timedelta(days=3)

        items: list[ft.Control] = []
        try:
            events = db_client.get_events(
                start_from=today_start.isoformat(), start_to=end_3days.isoformat(),
            )
            for ev in events[:8]:
                start = ev.get("start_at", "")
                # 日付と時刻を分割
                parts = start[:16].split("T")
                date_part = parts[0][5:] if parts else ""  # MM-DD
                time_part = parts[1] if len(parts) > 1 else ""
                source = ev.get("source", "user")
                items.append(ft.Container(
                    content=ft.Row([
                        ft.Container(
                            width=4, height=32,
                            bgcolor=PURPLE if source == "machine" else BLUE,
                            border_radius=2,
                        ),
                        ft.Column([
                            ft.Text(ev.get("title", ""), size=12,
                                    weight=ft.FontWeight.W_600, color=DARK_TEXT,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(f"{date_part} {time_part}", size=10, color=LIGHT_TEXT),
                        ], spacing=1, expand=True),
                    ], spacing=8),
                    padding=ft.padding.symmetric(vertical=4),
                ))
        except Exception:
            pass

        if not items:
            items.append(ft.Container(
                content=ft.Text("直近の予定なし", size=12, color=LIGHT_TEXT, italic=True),
                padding=ft.padding.symmetric(vertical=8),
            ))

        def _add(e: ft.ControlEvent) -> None:
            self._show_add_dialog("event")

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.EVENT_ROUNDED, size=18, color=BLUE),
                    ft.Text("直近の予定", size=14, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                    ft.Container(expand=True),
                    ft.IconButton(ft.Icons.ADD_ROUNDED, icon_size=18, icon_color=BLUE,
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
                items.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ic, size=16, color=clr),
                        ft.Column([
                            ft.Text(content, size=12, color=DARK_TEXT,
                                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(time_str, size=10, color=LIGHT_TEXT),
                        ], spacing=1, expand=True),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(vertical=4),
                ))
                if len(items) >= 6:
                    break
        except Exception:
            pass

        if not items:
            items.append(ft.Container(
                content=ft.Text("通知なし", size=12, color=LIGHT_TEXT, italic=True),
                padding=ft.padding.symmetric(vertical=8),
            ))

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.NOTIFICATIONS_NONE_ROUNDED, size=18, color=GREEN),
                    ft.Text("通知", size=14, weight=ft.FontWeight.W_700, color=DARK_TEXT),
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
    # 提案の承認
    # ==================================================================
    def _accept_suggestion(self, entry: dict) -> None:
        content = entry.get("content", "")
        title = "承認済みイベント"
        if "\u300c" in content and "\u300d" in content:
            title = content.split("\u300c")[1].split("\u300d")[0]

        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

        db_client.add_event(title=title, start_at=tomorrow.isoformat(), source="machine")
        db_client.add_machine_log(
            action_type="calendar_add",
            content=f"提案を承認: \u300c{title}\u300d を追加しました",
        )
        self._page.update()

    # ==================================================================
    # 追加ダイアログ
    # ==================================================================
    def _show_add_dialog(self, mode: str) -> None:
        is_reminder = mode == "reminder"
        dialog_title = "リマインダー追加" if is_reminder else "イベント追加"

        title_field = ft.TextField(
            label="内容" if is_reminder else "タイトル",
            autofocus=True,
        )
        date_field = ft.TextField(
            label="通知日時 (空欄で即時)" if is_reminder else "日時 (YYYY-MM-DD HH:MM)",
            value="" if is_reminder else datetime.now().strftime("%Y-%m-%d %H:%M"),
            hint_text="YYYY-MM-DD HH:MM",
        )

        fields: list[ft.Control] = [title_field, date_field]
        if not is_reminder:
            note_field = ft.TextField(label="メモ (任意)")
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
                    dt = dt.replace(tzinfo=timezone.utc)
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
            title=ft.Text(dialog_title, size=16, weight=ft.FontWeight.W_600),
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
