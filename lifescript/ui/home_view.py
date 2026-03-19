"""ホーム画面 — ウィジェットボード。

現在のウィジェット:
  - 時計         （常時表示）
  - カレンダー   （calendar.* で操作）
  - 通知         （notify() による通知履歴）
  - スケジュール （直近の予定 + リマインダーの統合）
  - Machine      （マシンの提案 + サマリー + 対話への入口）
"""

from __future__ import annotations

import calendar as cal_mod
import os
import threading
from datetime import datetime, timedelta, timezone

import flet as ft

from ..database.client import db_client
from ..holidays import get_month_holidays
from ..scheduler.scheduler import LifeScriptScheduler
from ..traits import gather_all_traits
from .app import (
    CARD_BG, BLUE, GREEN, CORAL, YELLOW, DARK_TEXT, MID_TEXT, LIGHT_TEXT,
    PURPLE, ORANGE, BG, SIDEBAR_BG, EDITOR_BG, EDITOR_FG, darii_image,
)

_BORDER = "#E8E4DC"
_JST = timezone(timedelta(hours=9))
_WIDGET_ITEM_HEIGHT = 44  # 1アイテムあたりの概算高さ（ゆとりあり）
_WIDGET_MAX_HEIGHT = int(_WIDGET_ITEM_HEIGHT * 2.5)  # 2件+半分見えて「下がある」と匂わせる


class HomeView:
    # ページ定義: (ページ名, アイコン)
    _PAGES = [
        ("メイン", ft.Icons.HOME_ROUNDED),
        ("ウィジェット", ft.Icons.WIDGETS_ROUNDED),
    ]

    def __init__(self, page: ft.Page, scheduler: LifeScriptScheduler,
                 on_navigate: callable | None = None,
                 on_ask_darii: callable | None = None) -> None:
        self._page = page
        self._scheduler = scheduler
        self._on_navigate = on_navigate  # on_navigate(index) で画面遷移
        self._on_ask_darii = on_ask_darii  # on_ask_darii(message) でダリーに質問
        self._logs: list[tuple[str, str, str]] = []
        self._cal_year = datetime.now().year
        self._cal_month = datetime.now().month
        self._content_container: ft.Container | None = None
        self._refresh_timer: threading.Timer | None = None
        self._is_active = False
        self._current_page = 0

    def receive_logs(self, entries: list[tuple[str, str, str]]) -> None:
        self._logs = (entries + self._logs)[:50]
        self._refresh_content()

    def _refresh_content(self) -> None:
        """表示中のウィジェットを最新データで再構築する。"""
        if self._content_container is not None and self._is_active:
            try:
                self._content_container.content = self._build_content()
                self._page.update()
            except Exception:
                pass

    def _start_refresh_timer(self) -> None:
        """定期リフレッシュ（10秒ごと）。"""
        self._is_active = True

        def _tick() -> None:
            if not self._is_active:
                return
            self._refresh_content()
            self._refresh_timer = threading.Timer(10.0, _tick)
            self._refresh_timer.daemon = True
            self._refresh_timer.start()

        self._refresh_timer = threading.Timer(10.0, _tick)
        self._refresh_timer.daemon = True
        self._refresh_timer.start()

    def _stop_refresh_timer(self) -> None:
        self._is_active = False
        if self._refresh_timer:
            self._refresh_timer.cancel()
            self._refresh_timer = None

    def build(self) -> ft.Control:
        self._stop_refresh_timer()
        self._start_refresh_timer()
        self._content_container = ft.Container(
            content=self._build_content(),
            expand=True,
        )
        return self._content_container

    def _build_content(self) -> ft.Control:
        """ホーム画面の中身をフルリビルドする。"""
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
                ft.IconButton(
                    ft.Icons.PSYCHOLOGY_ROUNDED, icon_size=20, icon_color=LIGHT_TEXT,
                    tooltip="メモリ（パーソナリティ）",
                    style=ft.ButtonStyle(padding=6),
                    on_click=self._show_memory_dialog,
                ),
                ft.Text(
                    now.strftime("%m/%d"),
                    size=20, weight=ft.FontWeight.W_700, color=LIGHT_TEXT,
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.only(bottom=14, top=4),
        )

        # ── ページタブ ──────────────────────────────────────────
        def _switch_page(idx: int) -> None:
            self._current_page = idx
            self._refresh_content()

        page_tabs = ft.Row(
            [
                ft.Container(
                    content=ft.Row([
                        ft.Icon(icon, size=16,
                                color=DARK_TEXT if i == self._current_page else LIGHT_TEXT),
                        ft.Text(name, size=13,
                                weight=ft.FontWeight.W_600 if i == self._current_page else ft.FontWeight.W_400,
                                color=DARK_TEXT if i == self._current_page else LIGHT_TEXT),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=YELLOW if i == self._current_page else ft.Colors.TRANSPARENT,
                    border_radius=10,
                    padding=ft.padding.symmetric(horizontal=14, vertical=6),
                    on_click=lambda e, idx=i: _switch_page(idx),
                    ink=True,
                )
                for i, (name, icon) in enumerate(self._PAGES)
            ],
            spacing=4,
        )

        # ── ウィジェット群 ────────────────────────────────────
        if self._current_page == 0:
            # メインページ: 時計 + カレンダー | ダリー + スケジュール
            clock_widget = self._widget_clock()
            calendar_widget = self._widget_calendar()
            schedule_widget = self._widget_schedule()
            machine_widget = self._widget_machine()

            page_content = ft.Row([
                ft.Column([
                    clock_widget,
                    ft.Container(height=10),
                    calendar_widget,
                ], expand=6, spacing=0, scroll=ft.ScrollMode.AUTO),
                ft.Column([
                    machine_widget,
                    ft.Container(height=10),
                    schedule_widget,
                ], expand=7, spacing=0, scroll=ft.ScrollMode.AUTO),
            ], expand=True, spacing=14, vertical_alignment=ft.CrossAxisAlignment.START)
        else:
            # ウィジェットページ: 通知 + Gmail + 動的ウィジェット群
            notification_widget = self._widget_notifications()
            gmail_widget = self._widget_gmail()
            dynamic_widgets = self._build_dynamic_widgets()

            left_items: list[ft.Control] = []
            if gmail_widget:
                left_items.append(gmail_widget)
            for dw in dynamic_widgets:
                if left_items:
                    left_items.append(ft.Container(height=10))
                left_items.append(dw)
            if not left_items:
                left_items.append(ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.WIDGETS_ROUNDED, size=36, color=LIGHT_TEXT),
                        ft.Text("ウィジェットはまだありません", size=14, color=MID_TEXT,
                                text_align=ft.TextAlign.CENTER),
                        ft.Text(
                            "IDEで web.fetch() や widget.show() を実行すると\nここにウィジェットが追加されます",
                            size=12, color=LIGHT_TEXT, text_align=ft.TextAlign.CENTER,
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    padding=40, alignment=ft.Alignment(0, 0),
                    bgcolor=CARD_BG, border_radius=16, border=ft.border.all(1, _BORDER),
                ))

            right_items: list[ft.Control] = [notification_widget]

            page_content = ft.Row([
                ft.Column(left_items, expand=6, spacing=0, scroll=ft.ScrollMode.AUTO),
                ft.Column(right_items, expand=7, spacing=0, scroll=ft.ScrollMode.AUTO),
            ], expand=True, spacing=14, vertical_alignment=ft.CrossAxisAlignment.START)

        return ft.Column([
            header,
            page_tabs,
            ft.Container(height=6),
            page_content,
        ], expand=True, spacing=0)

    # ==================================================================
    # メモリダイアログ（パーソナリティ管理）
    # ==================================================================
    def _show_memory_dialog(self, e: ft.ControlEvent) -> None:
        memory_list = ft.ListView(spacing=6, height=400)
        dialog: ft.AlertDialog | None = None

        def _refresh() -> None:
            memory_list.controls.clear()

            # traits由来
            traits = gather_all_traits()
            if traits:
                memory_list.controls.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=14, color=PURPLE),
                        ft.Text("Traitsから自動取得", size=11,
                                weight=ft.FontWeight.W_600, color=PURPLE),
                    ], spacing=4),
                    padding=ft.padding.only(left=4, bottom=4),
                ))
                for trait in traits:
                    memory_list.controls.append(ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=14, color=PURPLE),
                            ft.Text(trait, size=13, color=DARK_TEXT, expand=True),
                        ], spacing=6),
                        bgcolor=CARD_BG, border_radius=10,
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        border=ft.border.all(1, _BORDER),
                    ))

            # マシンの観察 + 手動メモリ
            try:
                logs = db_client.get_machine_logs(limit=100)
                memories = [l for l in logs if l.get("action_type") == "memory"]
                auto_memories = [l for l in logs if l.get("action_type") == "memory_auto"]
            except Exception:
                memories = []
                auto_memories = []

            if auto_memories:
                memory_list.controls.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.VISIBILITY_ROUNDED, size=14, color=ORANGE),
                        ft.Text("ダリーの観察", size=11,
                                weight=ft.FontWeight.W_600, color=ORANGE),
                    ], spacing=4),
                    padding=ft.padding.only(left=4, top=12, bottom=4),
                ))
                for mem in auto_memories:
                    content = mem.get("content", "")
                    log_id = mem.get("id")
                    memory_list.controls.append(ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.VISIBILITY_ROUNDED, size=14, color=ORANGE),
                            ft.Text(content, size=13, color=DARK_TEXT, expand=True),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=14, icon_color=CORAL,
                                tooltip="削除", style=ft.ButtonStyle(padding=4),
                                on_click=lambda e, lid=log_id: _delete(lid),
                            ),
                        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.START),
                        bgcolor=CARD_BG, border_radius=10,
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        border=ft.border.all(1, _BORDER),
                    ))

            if memories:
                memory_list.controls.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, size=14, color=BLUE),
                        ft.Text("手動で追加", size=11,
                                weight=ft.FontWeight.W_600, color=BLUE),
                    ], spacing=4),
                    padding=ft.padding.only(left=4, top=12, bottom=4),
                ))
                for mem in memories:
                    content = mem.get("content", "")
                    log_id = mem.get("id")
                    memory_list.controls.append(ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.PERSON_ROUNDED, size=14, color=BLUE),
                            ft.Text(content, size=13, color=DARK_TEXT, expand=True),
                            ft.IconButton(
                                ft.Icons.EDIT_ROUNDED, icon_size=14, icon_color=MID_TEXT,
                                tooltip="編集", style=ft.ButtonStyle(padding=4),
                                on_click=lambda e, lid=log_id, t=content: _edit(lid, t),
                            ),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=14, icon_color=CORAL,
                                tooltip="削除", style=ft.ButtonStyle(padding=4),
                                on_click=lambda e, lid=log_id: _delete(lid),
                            ),
                        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.START),
                        bgcolor=CARD_BG, border_radius=10,
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        border=ft.border.all(1, _BORDER),
                    ))

            if not traits and not memories and not auto_memories:
                memory_list.controls.append(ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, size=32, color=LIGHT_TEXT),
                        ft.Text("メモリはまだありません", size=14, color=MID_TEXT,
                                text_align=ft.TextAlign.CENTER),
                        ft.Text("LifeScript に traits を書くか、\n＋ボタンで手動追加できます",
                                size=12, color=LIGHT_TEXT, text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    padding=40, alignment=ft.Alignment(0, 0),
                ))
            self._page.update()

        def _add(e: ft.ControlEvent) -> None:
            tf = ft.TextField(
                hint_text="例: 疲れた時は甘いものが食べたくなる",
                text_size=13, border_radius=8, bgcolor=CARD_BG,
                border_color=_BORDER, focused_border_color=BLUE,
                content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
                multiline=True, min_lines=2, max_lines=4,
            )
            add_dlg = ft.AlertDialog(
                title=ft.Text("メモリを追加", size=16, weight=ft.FontWeight.W_700),
                content=ft.Container(content=tf, width=400),
                actions=[
                    ft.TextButton("キャンセル",
                                  on_click=lambda e: _close_sub(add_dlg)),
                    ft.TextButton("追加", style=ft.ButtonStyle(color=BLUE),
                                  on_click=lambda e: _save_new(tf, add_dlg)),
                ],
            )
            self._page.overlay.append(add_dlg)
            add_dlg.open = True
            self._page.update()

        def _save_new(tf: ft.TextField, dlg: ft.AlertDialog) -> None:
            val = (tf.value or "").strip()
            if not val:
                return
            db_client.add_machine_log(action_type="memory", content=val)
            dlg.open = False
            _refresh()

        def _edit(log_id: int, current: str) -> None:
            tf = ft.TextField(
                value=current, text_size=13, border_radius=8, bgcolor=CARD_BG,
                border_color=_BORDER, focused_border_color=BLUE,
                content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
                multiline=True, min_lines=2, max_lines=4,
            )
            edit_dlg = ft.AlertDialog(
                title=ft.Text("メモリを編集", size=16, weight=ft.FontWeight.W_700),
                content=ft.Container(content=tf, width=400),
                actions=[
                    ft.TextButton("キャンセル",
                                  on_click=lambda e: _close_sub(edit_dlg)),
                    ft.TextButton("保存", style=ft.ButtonStyle(color=BLUE),
                                  on_click=lambda e: _save_edit(tf, log_id, edit_dlg)),
                ],
            )
            self._page.overlay.append(edit_dlg)
            edit_dlg.open = True
            self._page.update()

        def _save_edit(tf: ft.TextField, log_id: int, dlg: ft.AlertDialog) -> None:
            val = (tf.value or "").strip()
            if not val:
                return
            db_client.delete_machine_log(log_id)
            db_client.add_machine_log(action_type="memory", content=val)
            dlg.open = False
            _refresh()

        def _delete(log_id: int) -> None:
            db_client.delete_machine_log(log_id)
            _refresh()

        def _close_sub(dlg: ft.AlertDialog) -> None:
            dlg.open = False
            self._page.update()

        _refresh()

        dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.PSYCHOLOGY_ROUNDED, size=20, color=BLUE),
                ft.Text("メモリ", size=18, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                ft.Container(width=4),
                ft.Text("ダリーが把握しているあなたの情報", size=11, color=MID_TEXT),
            ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            content=ft.Container(content=memory_list, width=500),
            actions=[
                ft.TextButton("追加", icon=ft.Icons.ADD_ROUNDED,
                              style=ft.ButtonStyle(color=BLUE), on_click=_add),
                ft.TextButton("閉じる",
                              on_click=lambda e: setattr(dialog, "open", False) or self._page.update()),
            ],
        )
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()

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
        holidays_by_day: dict[int, str] = {}
        try:
            model = os.getenv("LIFESCRIPT_MODEL", "gemini/gemini-2.5-flash")
            month_holidays = get_month_holidays(year, month, model=model)
            holidays_by_day = {d.day: name for d, name in month_holidays.items()}
        except Exception:
            holidays_by_day = {}

        # イベントを取得（日 → タイトルリストのマッピング）
        events_by_day: dict[int, list[str]] = {}
        events_by_day_full: dict[int, list[dict]] = {}
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
                        events_by_day_full.setdefault(d.day, []).append(ev)
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
                    holiday_name = holidays_by_day.get(day, "")

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
                    if holiday_name:
                        ev_labels.append(ft.Container(
                            content=ft.Text(
                                holiday_name[:6], size=9, color=CARD_BG,
                                max_lines=1, overflow=ft.TextOverflow.CLIP,
                                no_wrap=True,
                            ),
                            bgcolor=CORAL,
                            border_radius=3,
                            padding=ft.padding.symmetric(horizontal=3, vertical=1),
                            clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        ))
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

                    day_full_events = events_by_day_full.get(day, [])
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
                        on_click=lambda e, d=day, evs=day_full_events: self._show_day_dialog(year, month, d, evs),
                        ink=True,
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
    # Widget: スケジュール（リマインダー + 直近の予定を統合）
    # ==================================================================
    def _widget_schedule(self) -> ft.Container:
        items: list[ft.Control] = []
        now = datetime.now(_JST)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_3days = today_start + timedelta(days=3)

        # ── 直近のイベント ──
        try:
            events = db_client.get_events(
                start_from=today_start.isoformat(), start_to=end_3days.isoformat(),
            )
            for ev in events[:6]:
                start = ev.get("start_at", "")
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
                ev_id = ev.get("id")
                source_label = "ダリー" if source == "machine" else "手動"
                accent = PURPLE if source == "machine" else BLUE
                items.append(ft.Container(
                    content=ft.Row([
                        ft.Container(width=4, height=36, bgcolor=accent, border_radius=2),
                        ft.Column([
                            ft.Text(ev_title, size=14,
                                    weight=ft.FontWeight.W_600, color=DARK_TEXT,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(f"{date_part} {time_part}", size=12, color=LIGHT_TEXT),
                        ], spacing=1, expand=True),
                    ], spacing=8),
                    padding=ft.padding.symmetric(vertical=4),
                    on_click=lambda e, t=ev_title, dp=date_part, tp=time_part,
                                    n=ev_note, s=source_label, a=accent,
                                    eid=ev_id, evt=ev: self._show_detail(
                        t, [("日付", dp), ("時刻", tp), ("メモ", n), ("ソース", s)], a,
                        on_delete=lambda eid=eid: self._delete_event(eid),
                        on_edit=lambda evt=evt: self._show_edit_event_dialog(evt)),
                    ink=True, border_radius=8,
                ))
        except Exception:
            pass

        # ── リマインダー ──
        try:
            logs = db_client.get_machine_logs(limit=30)
            for entry in logs:
                if entry.get("action_type") != "reminder":
                    continue
                content = entry.get("content", "")
                log_id = entry.get("id")
                triggered = entry.get("triggered_at", "")[:16].replace("T", " ")
                items.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.PUSH_PIN_ROUNDED, size=16, color=PURPLE),
                        ft.Text(content, size=13, color=DARK_TEXT, expand=True,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(triggered[5:] if len(triggered) > 5 else triggered,
                                size=11, color=LIGHT_TEXT),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(vertical=5),
                    on_click=lambda e, c=content, t=triggered, lid=log_id: self._show_detail(
                        "リマインダー", [("内容", c), ("登録日時", t)], PURPLE,
                        on_delete=lambda lid=lid: self._delete_log(lid)),
                    ink=True, border_radius=8,
                ))
        except Exception:
            pass

        if not items:
            items.append(ft.Container(
                content=ft.Text("予定・リマインダーなし", size=14, color=LIGHT_TEXT, italic=True),
                padding=ft.padding.symmetric(vertical=8),
            ))

        def _add_event(e: ft.ControlEvent) -> None:
            self._show_add_dialog("event")

        def _add_reminder(e: ft.ControlEvent) -> None:
            self._show_add_dialog("reminder")

        items_view = ft.ListView(controls=items, spacing=2,
                                  height=_WIDGET_MAX_HEIGHT if len(items) > 2 else None)

        schedule_legend = ft.Row([
            ft.Container(width=8, height=8, bgcolor=BLUE, border_radius=2),
            ft.Text("予定", size=10, color=MID_TEXT),
            ft.Container(width=4),
            ft.Container(width=8, height=8, bgcolor=PURPLE, border_radius=2),
            ft.Text("ダリー", size=10, color=MID_TEXT),
            ft.Container(width=4),
            ft.Icon(ft.Icons.PUSH_PIN_ROUNDED, size=12, color=PURPLE),
            ft.Text("リマインダー", size=10, color=MID_TEXT),
        ], spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.EVENT_NOTE_ROUNDED, size=20, color=BLUE),
                    ft.Text("スケジュール", size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                    ft.Container(expand=True),
                    ft.IconButton(ft.Icons.PUSH_PIN_ROUNDED, icon_size=18, icon_color=PURPLE,
                                  tooltip="リマインダー追加", style=ft.ButtonStyle(padding=4),
                                  on_click=_add_reminder),
                    ft.IconButton(ft.Icons.ADD_ROUNDED, icon_size=20, icon_color=BLUE,
                                  tooltip="予定追加", style=ft.ButtonStyle(padding=4),
                                  on_click=_add_event),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                schedule_legend,
                ft.Divider(height=1, color=_BORDER),
                items_view,
            ], spacing=4),
            bgcolor=CARD_BG,
            border_radius=16,
            padding=14,
            border=ft.border.all(1, _BORDER),
        )

    # ==================================================================
    # Widget: マシン（提案 + サマリー + 対話への入口）
    # ==================================================================
    @staticmethod
    def _strip_meta(content: str) -> str:
        """表示用にメタデータタグを除去する。"""
        import re as _re
        return _re.sub(r"\n<!--meta:.*?-->", "", content).strip()

    def _widget_machine(self) -> ft.Container:
        # ── サマリー行 ──
        now = datetime.now(_JST)
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        event_count = 0
        try:
            events = db_client.get_events(
                start_from=week_start.isoformat(), start_to=week_end.isoformat(),
            )
            event_count = len(events)
        except Exception:
            pass
        active_count = len(self._scheduler.get_active_ids())

        # ── 選択状態の管理 ──
        selected_entry: list[dict | None] = [None]

        # 「Machineに聞く」ボタン（初期非表示）
        ask_button = ft.Container(
            content=ft.Row([
                darii_image(16),
                ft.Text("この提案についてダリーに聞く", size=12, color=CARD_BG,
                        weight=ft.FontWeight.W_600),
            ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=ORANGE,
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            on_click=lambda e: self._go_machine_with_context(selected_entry[0]),
            ink=True,
            visible=False,
        )

        # ── 提案カード群 ──
        suggestion_cards: list[ft.Container] = []
        suggestion_entries: list[dict] = []
        try:
            logs = db_client.get_machine_logs(limit=20)
            for entry in logs:
                if entry.get("action_type") not in ("calendar_suggest", "general_suggest"):
                    continue
                suggestion_entries.append(entry)
                if len(suggestion_entries) >= 3:
                    break
        except Exception:
            pass

        def _select_suggestion(idx: int) -> None:
            selected_entry[0] = suggestion_entries[idx]
            for i, card in enumerate(suggestion_cards):
                if i == idx:
                    card.border = ft.border.all(2, ORANGE)
                    card.bgcolor = "#FFF8EE"
                else:
                    card.border = ft.border.all(1, "#F0E8D8")
                    card.bgcolor = "#FFFBF0"
            ask_button.visible = True
            self._page.update()

        for i, entry in enumerate(suggestion_entries):
            raw_content = entry.get("content", "")
            display = self._strip_meta(raw_content)
            log_id = entry.get("id")
            card = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Markdown(
                            display, selectable=False,
                            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                            md_style_sheet=ft.MarkdownStyleSheet(
                                p_text_style=ft.TextStyle(size=14, color=DARK_TEXT),
                                strong_text_style=ft.TextStyle(weight=ft.FontWeight.W_700, color=DARK_TEXT),
                                list_bullet_text_style=ft.TextStyle(size=14, color=DARK_TEXT),
                            ),
                        ),
                        expand=True,
                    ),
                    ft.IconButton(
                        ft.Icons.CHECK_ROUNDED, icon_size=18, icon_color=GREEN,
                        tooltip="承認", style=ft.ButtonStyle(padding=2),
                        on_click=lambda e, ent=entry: self._accept_suggestion(ent),
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED, icon_size=16, icon_color=LIGHT_TEXT,
                        tooltip="却下", style=ft.ButtonStyle(padding=2),
                        on_click=lambda e, lid=log_id: self._delete_log(lid),
                    ),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.START),
                padding=ft.padding.symmetric(vertical=4, horizontal=8),
                bgcolor="#FFFBF0",
                border=ft.border.all(1, "#F0E8D8"),
                border_radius=10,
                on_click=lambda e, idx=i: _select_suggestion(idx),
                ink=True,
            )
            suggestion_cards.append(card)

        if not suggestion_cards:
            suggestion_cards.append(ft.Container(
                content=ft.Text("ダリーからの提案はまだありません",
                                size=13, color=LIGHT_TEXT, italic=True),
                padding=ft.padding.symmetric(vertical=6),
            ))

        # ── 分析ボタン ──
        def _on_analyze(e: ft.ControlEvent) -> None:
            import threading
            def _run() -> None:
                self._scheduler.run_analysis_now()
                self._page.update()
            threading.Thread(target=_run, daemon=True).start()

        # ── ヘッダー凡例 + サマリー統合 ──
        legend = ft.Row([
            ft.Icon(ft.Icons.CHECK_ROUNDED, size=12, color=GREEN),
            ft.Text("承認", size=10, color=MID_TEXT),
            ft.Container(width=3),
            ft.Icon(ft.Icons.CLOSE_ROUNDED, size=12, color=LIGHT_TEXT),
            ft.Text("却下", size=10, color=MID_TEXT),
            ft.Container(width=3),
            ft.Icon(ft.Icons.ADS_CLICK_ROUNDED, size=12, color=ORANGE),
            ft.Text("選択で質問", size=10, color=MID_TEXT),
            ft.Container(expand=True),
            ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED, size=11, color=BLUE),
            ft.Text(f"今週{event_count}件", size=10, color=MID_TEXT),
            ft.Container(width=3),
            ft.Icon(ft.Icons.CODE_ROUNDED, size=11, color=GREEN),
            ft.Text(f"{active_count}スクリプト", size=10, color=MID_TEXT),
        ], spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    darii_image(22),
                    ft.Text("ダリー", size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                    ft.Container(expand=True),
                    ft.IconButton(ft.Icons.REFRESH_ROUNDED, icon_size=18, icon_color=ORANGE,
                                  tooltip="文脈を分析して提案を生成",
                                  style=ft.ButtonStyle(padding=4),
                                  on_click=_on_analyze),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                legend,
                ft.Divider(height=1, color=_BORDER),
                ft.Column(suggestion_cards, spacing=6),
                ask_button,
            ], spacing=4),
            bgcolor=CARD_BG,
            border_radius=16,
            padding=14,
            border=ft.border.all(1, _BORDER),
        )

    def _go_machine_with_context(self, entry: dict | None) -> None:
        """提案の文脈をダリーチャットに渡して遷移する。"""
        if not entry:
            # 提案が選択されていない場合はダリー画面に遷移だけ
            if self._on_navigate:
                self._on_navigate(4)
            return

        content = self._strip_meta(entry.get("content", ""))
        message = f"この提案について詳しく教えて: 「{content}」"

        # 先にダリー画面に遷移
        if self._on_navigate:
            self._on_navigate(4)

        # 遷移後にメッセージを送信（少し遅延させてUIの描画完了を待つ）
        if self._on_ask_darii:
            import threading
            def _send_delayed():
                import time
                time.sleep(0.3)
                self._on_ask_darii(message)
            threading.Thread(target=_send_delayed, daemon=True).start()

    # ==================================================================
    # Widget: Gmail
    # ==================================================================
    def _widget_gmail(self) -> ft.Container | None:
        """Google認証済みの場合のみGmailウィジェットを表示する。"""
        from ..google_auth import is_authenticated, get_user_email

        if not is_authenticated():
            return None

        email = get_user_email() or "Gmail"

        # 未読メール取得（UIスレッドなので軽量に）
        items: list[ft.Control] = []
        try:
            from ..google_auth import get_credentials
            creds = get_credentials()
            if creds:
                from googleapiclient.discovery import build
                service = build("gmail", "v1", credentials=creds)
                results = service.users().messages().list(
                    userId="me", q="is:unread", maxResults=5,
                ).execute()
                messages = results.get("messages", [])
                unread_count = results.get("resultSizeEstimate", 0)

                items.append(ft.Row([
                    ft.Icon(ft.Icons.MARK_EMAIL_UNREAD_ROUNDED, size=14, color="#EA4335"),
                    ft.Text(f"未読 {unread_count}件", size=12,
                            weight=ft.FontWeight.W_600, color=DARK_TEXT),
                ], spacing=6))

                for m in messages[:3]:
                    msg = service.users().messages().get(
                        userId="me", id=m["id"], format="metadata",
                        metadataHeaders=["Subject", "From"],
                    ).execute()
                    headers = {h["name"].lower(): h["value"]
                               for h in msg.get("payload", {}).get("headers", [])}
                    subject = headers.get("subject", "(件名なし)")
                    sender = headers.get("from", "")
                    # 差出人名だけ抽出
                    if "<" in sender:
                        sender = sender.split("<")[0].strip().strip('"')
                    items.append(ft.Container(
                        content=ft.Row([
                            ft.Container(width=4, height=28, bgcolor="#EA4335", border_radius=2),
                            ft.Column([
                                ft.Text(subject, size=13, weight=ft.FontWeight.W_500,
                                        color=DARK_TEXT, max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text(sender, size=11, color=LIGHT_TEXT,
                                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ], spacing=0, expand=True),
                        ], spacing=8),
                        padding=ft.padding.symmetric(vertical=2),
                    ))
                if not messages:
                    items.append(ft.Text("未読メールはありません",
                                         size=13, color=LIGHT_TEXT, italic=True))
        except Exception:
            items.append(ft.Text("メール取得に失敗しました",
                                 size=12, color=CORAL, italic=True))

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.MAIL_ROUNDED, size=20, color="#EA4335"),
                    ft.Text("Gmail", size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                    ft.Container(expand=True),
                    ft.Text(email.split("@")[0] if email else "",
                            size=11, color=LIGHT_TEXT),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=1, color=_BORDER),
                *items,
            ], spacing=6),
            bgcolor=CARD_BG,
            border_radius=16,
            padding=14,
            border=ft.border.all(1, _BORDER),
        )

    # ==================================================================
    # Widget: Gmail
    # ==================================================================
    def _widget_gmail(self) -> ft.Container | None:
        """Google認証済みの場合のみGmailウィジェットを表示する。"""
        from ..google_auth import is_authenticated, get_user_email

        if not is_authenticated():
            return None

        email = get_user_email() or "Gmail"

        # 未読メール取得（UIスレッドなので軽量に）
        items: list[ft.Control] = []
        try:
            from ..google_auth import get_credentials
            creds = get_credentials()
            if creds:
                from googleapiclient.discovery import build
                service = build("gmail", "v1", credentials=creds)
                results = service.users().messages().list(
                    userId="me", q="is:unread", maxResults=5,
                ).execute()
                messages = results.get("messages", [])
                unread_count = results.get("resultSizeEstimate", 0)

                items.append(ft.Row([
                    ft.Icon(ft.Icons.MARK_EMAIL_UNREAD_ROUNDED, size=14, color="#EA4335"),
                    ft.Text(f"未読 {unread_count}件", size=12,
                            weight=ft.FontWeight.W_600, color=DARK_TEXT),
                ], spacing=6))

                for m in messages[:3]:
                    msg = service.users().messages().get(
                        userId="me", id=m["id"], format="metadata",
                        metadataHeaders=["Subject", "From"],
                    ).execute()
                    headers = {h["name"].lower(): h["value"]
                               for h in msg.get("payload", {}).get("headers", [])}
                    subject = headers.get("subject", "(件名なし)")
                    sender = headers.get("from", "")
                    # 差出人名だけ抽出
                    if "<" in sender:
                        sender = sender.split("<")[0].strip().strip('"')
                    items.append(ft.Container(
                        content=ft.Row([
                            ft.Container(width=4, height=28, bgcolor="#EA4335", border_radius=2),
                            ft.Column([
                                ft.Text(subject, size=13, weight=ft.FontWeight.W_500,
                                        color=DARK_TEXT, max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text(sender, size=11, color=LIGHT_TEXT,
                                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ], spacing=0, expand=True),
                        ], spacing=8),
                        padding=ft.padding.symmetric(vertical=2),
                    ))
                if not messages:
                    items.append(ft.Text("未読メールはありません",
                                         size=13, color=LIGHT_TEXT, italic=True))
        except Exception:
            items.append(ft.Text("メール取得に失敗しました",
                                 size=12, color=CORAL, italic=True))

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.MAIL_ROUNDED, size=20, color="#EA4335"),
                    ft.Text("Gmail", size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                    ft.Container(expand=True),
                    ft.Text(email.split("@")[0] if email else "",
                            size=11, color=LIGHT_TEXT),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=1, color=_BORDER),
                *items,
            ], spacing=6),
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
                log_id = entry.get("id")
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
                    on_click=lambda e, c=content, ts=time_str, tl=type_label, cl=clr,
                                    lid=log_id: self._show_detail(
                        "通知", [("内容", c), ("種類", tl), ("日時", ts)], cl,
                        on_delete=lambda lid=lid: self._delete_log(lid)),
                    ink=True, border_radius=8,
                ))
        except Exception:
            pass

        if not items:
            items.append(ft.Container(
                content=ft.Text("通知なし", size=14, color=LIGHT_TEXT, italic=True),
                padding=ft.padding.symmetric(vertical=8),
            ))

        items_view = ft.ListView(controls=items, spacing=2,
                                  height=_WIDGET_MAX_HEIGHT if len(items) > 2 else None)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.NOTIFICATIONS_NONE_ROUNDED, size=20, color=GREEN),
                    ft.Text("通知", size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=1, color=_BORDER),
                items_view,
            ], spacing=4),
            bgcolor=CARD_BG,
            border_radius=16,
            padding=14,
            border=ft.border.all(1, _BORDER),
        )

    # ==================================================================
    # 動的ウィジェット（widget_show() で生成されたもの）
    # ==================================================================
    _ICON_MAP = {
        "article": ft.Icons.ARTICLE_ROUNDED,
        "language": ft.Icons.LANGUAGE_ROUNDED,
        "rss_feed": ft.Icons.RSS_FEED_ROUNDED,
        "newspaper": ft.Icons.NEWSPAPER_ROUNDED,
        "science": ft.Icons.SCIENCE_ROUNDED,
        "trending_up": ft.Icons.TRENDING_UP_ROUNDED,
        "search": ft.Icons.SEARCH_ROUNDED,
        "mail": ft.Icons.MAIL_ROUNDED,
        "bookmark": ft.Icons.BOOKMARK_ROUNDED,
        "lightbulb": ft.Icons.LIGHTBULB_ROUNDED,
    }

    def _build_dynamic_widgets(self) -> list[ft.Container]:
        """machine_logs の widget:* エントリからウィジェットを動的に生成。"""
        widgets: list[ft.Container] = []
        seen_names: dict[str, dict] = {}

        try:
            logs = db_client.get_machine_logs(limit=100)
            for entry in logs:
                at = entry.get("action_type", "")
                if not at.startswith("widget:"):
                    continue
                widget_name = at[7:]  # "widget:" を除去
                # 各ウィジェット名の最新エントリだけ取る
                if widget_name not in seen_names:
                    seen_names[widget_name] = entry
        except Exception:
            pass

        for widget_name, entry in seen_names.items():
            content = entry.get("content", "")
            log_id = entry.get("id")
            triggered = entry.get("triggered_at", "")[:16].replace("T", " ")

            # アイコン推定（content内の <!--icon:xxx--> または デフォルト）
            import re as _re
            icon_match = _re.search(r"<!--icon:(\w+)-->", content)
            if icon_match:
                icon_name = icon_match.group(1)
                content = _re.sub(r"<!--icon:\w+-->", "", content).strip()
            else:
                icon_name = "article"
            icon = self._ICON_MAP.get(icon_name, ft.Icons.ARTICLE_ROUNDED)

            widget = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(icon, size=20, color=BLUE),
                        ft.Text(widget_name, size=16, weight=ft.FontWeight.W_700,
                                color=DARK_TEXT),
                        ft.Container(expand=True),
                        ft.Text(triggered[5:] if len(triggered) > 5 else triggered,
                                size=10, color=LIGHT_TEXT),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Divider(height=1, color=_BORDER),
                    ft.Container(
                        content=ft.Markdown(
                            content, selectable=True,
                            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                            code_theme=ft.MarkdownCodeTheme.MONOKAI,
                            md_style_sheet=ft.MarkdownStyleSheet(
                                p_text_style=ft.TextStyle(size=13, color=DARK_TEXT),
                                h1_text_style=ft.TextStyle(size=18, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                                h2_text_style=ft.TextStyle(size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT),
                                h3_text_style=ft.TextStyle(size=14, weight=ft.FontWeight.W_600, color=DARK_TEXT),
                                strong_text_style=ft.TextStyle(weight=ft.FontWeight.W_700, color=DARK_TEXT),
                                list_bullet_text_style=ft.TextStyle(size=13, color=DARK_TEXT),
                            ),
                        ),
                        padding=ft.padding.only(top=4),
                    ),
                ], spacing=4),
                bgcolor=CARD_BG,
                border_radius=16,
                padding=14,
                border=ft.border.all(1, _BORDER),
                on_click=lambda e, n=widget_name, c=content, t=triggered,
                                lid=log_id: self._show_detail(
                    n, [("内容", c), ("更新日時", t)], BLUE,
                    on_delete=lambda lid=lid: self._delete_log(lid)),
                ink=True,
            )
            widgets.append(widget)

        return widgets

    # ==================================================================
    # カレンダー日付タップ → 日別イベントダイアログ
    # ==================================================================
    _WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]

    def _show_day_dialog(self, year: int, month: int, day: int,
                         day_events: list[dict]) -> None:
        """指定日のイベント一覧ダイアログを表示する。"""
        import calendar as _cal

        wdidx = _cal.weekday(year, month, day)
        header_text = f"{month}月{day}日（{self._WEEKDAY_JP[wdidx]}）"

        # --- イベント行を構築 ---
        _ev_colors = [BLUE, PURPLE, GREEN, ORANGE, CORAL]
        event_rows: list[ft.Control] = []
        for i, ev in enumerate(day_events):
            ev_id = ev.get("id")
            ev_title = ev.get("title", "")
            source = ev.get("source", "user")
            start_raw = ev.get("start_at", "")
            try:
                dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M")
            except (ValueError, AttributeError):
                time_str = start_raw[11:16] if len(start_raw) > 15 else "--:--"

            accent = _ev_colors[i % len(_ev_colors)]
            source_label = "ダリー" if source == "machine" else "手動"
            source_bg = PURPLE if source == "machine" else MID_TEXT

            row = ft.Container(
                content=ft.Row([
                    ft.Container(width=4, height=40, bgcolor=accent, border_radius=2),
                    ft.Column([
                        ft.Row([
                            ft.Text(time_str, size=12, color=LIGHT_TEXT,
                                    weight=ft.FontWeight.W_600),
                            ft.Container(
                                content=ft.Text(source_label, size=9, color=CARD_BG),
                                bgcolor=source_bg, border_radius=4,
                                padding=ft.padding.symmetric(horizontal=5, vertical=1),
                            ),
                        ], spacing=6),
                        ft.Text(ev_title, size=14, weight=ft.FontWeight.W_600,
                                color=DARK_TEXT, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=2, expand=True),
                    ft.IconButton(
                        ft.Icons.EDIT_ROUNDED, icon_size=16, icon_color=BLUE,
                        style=ft.ButtonStyle(padding=4),
                        tooltip="編集",
                        on_click=lambda e, evt=ev: self._day_edit_event(
                            evt, year, month, day, dialog),
                    ),
                    ft.IconButton(
                        ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=16, icon_color=CORAL,
                        style=ft.ButtonStyle(padding=4),
                        tooltip="削除",
                        on_click=lambda e, eid=ev_id: self._day_delete_event(
                            eid, dialog),
                    ),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(vertical=4, horizontal=4),
                border=ft.border.all(1, _BORDER),
                border_radius=10,
            )
            event_rows.append(row)

        if not event_rows:
            event_rows.append(ft.Container(
                content=ft.Text("予定なし", size=14, color=LIGHT_TEXT, italic=True),
                padding=ft.padding.symmetric(vertical=12),
                alignment=ft.Alignment(0, 0),
            ))

        def _close(e=None):
            dialog.open = False
            self._page.update()

        def _add(e):
            dialog.open = False
            self._page.update()
            self._day_add_event(year, month, day)

        content = ft.Column(
            [*event_rows],
            tight=True, spacing=6, scroll=ft.ScrollMode.AUTO,
        )

        dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED, size=20, color=BLUE),
                ft.Text(header_text, size=18, weight=ft.FontWeight.W_700,
                        color=DARK_TEXT),
            ], spacing=8),
            content=ft.Container(content=content, width=340),
            actions=[
                ft.ElevatedButton(
                    "予定を追加", icon=ft.Icons.ADD_ROUNDED,
                    bgcolor=BLUE, color=CARD_BG,
                    on_click=_add,
                ),
                ft.TextButton("閉じる", on_click=_close),
            ],
        )
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()

    def _day_delete_event(self, event_id: int, parent_dialog: ft.AlertDialog) -> None:
        """日別ダイアログからイベントを削除（確認付き）。"""

        def _confirm_delete(e):
            confirm_dlg.open = False
            self._page.update()
            try:
                db_client.delete_event(event_id)
            except Exception:
                pass
            parent_dialog.open = False
            self._page.update()
            self._refresh_content()

        def _cancel(e):
            confirm_dlg.open = False
            self._page.update()

        confirm_dlg = ft.AlertDialog(
            title=ft.Text("削除確認", size=16, weight=ft.FontWeight.W_600, color=DARK_TEXT),
            content=ft.Text("この予定を削除しますか？", size=14, color=MID_TEXT),
            actions=[
                ft.TextButton("キャンセル", on_click=_cancel),
                ft.ElevatedButton("削除", bgcolor=CORAL, color=CARD_BG,
                                  on_click=_confirm_delete),
            ],
        )
        self._page.overlay.append(confirm_dlg)
        confirm_dlg.open = True
        self._page.update()

    def _day_edit_event(self, event: dict, year: int, month: int, day: int,
                        parent_dialog: ft.AlertDialog) -> None:
        """日別ダイアログからイベントを編集。"""
        title_field = ft.TextField(
            label="タイトル", value=event.get("title", ""),
            autofocus=True, text_size=14,
        )
        start_raw = event.get("start_at", "")
        try:
            dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            date_val = dt.strftime("%Y-%m-%d")
            time_val = dt.strftime("%H:%M")
        except (ValueError, AttributeError):
            date_val = f"{year:04d}-{month:02d}-{day:02d}"
            time_val = start_raw[11:16] if len(start_raw) > 15 else "09:00"

        date_field = ft.TextField(
            label="日付 (YYYY-MM-DD)", value=date_val,
            hint_text="YYYY-MM-DD", text_size=14,
        )
        time_field = ft.TextField(
            label="時刻 (HH:MM)", value=time_val,
            hint_text="HH:MM", text_size=14,
        )

        def _save(e):
            text = title_field.value.strip()
            if not text:
                return
            d_str = date_field.value.strip()
            t_str = time_field.value.strip()
            if not d_str:
                date_field.error_text = "日付を入力してください"
                self._page.update()
                return
            if not t_str:
                time_field.error_text = "時刻を入力してください"
                self._page.update()
                return
            try:
                new_dt = datetime.strptime(f"{d_str} {t_str}", "%Y-%m-%d %H:%M")
                new_dt = new_dt.replace(tzinfo=_JST)
            except ValueError:
                date_field.error_text = "形式: YYYY-MM-DD"
                time_field.error_text = "形式: HH:MM"
                self._page.update()
                return
            try:
                db_client.update_event(
                    event["id"], title=text, start_at=new_dt.isoformat(),
                )
            except Exception:
                pass
            edit_dlg.open = False
            parent_dialog.open = False
            self._page.update()
            self._refresh_content()

        def _cancel(e):
            edit_dlg.open = False
            self._page.update()

        edit_dlg = ft.AlertDialog(
            title=ft.Text("イベント編集", size=18, weight=ft.FontWeight.W_600,
                          color=DARK_TEXT),
            content=ft.Column([title_field, date_field, time_field],
                              tight=True, spacing=12),
            actions=[
                ft.TextButton("キャンセル", on_click=_cancel),
                ft.ElevatedButton("保存", bgcolor=BLUE, color=CARD_BG, on_click=_save),
            ],
        )
        self._page.overlay.append(edit_dlg)
        edit_dlg.open = True
        self._page.update()

    def _day_add_event(self, year: int, month: int, day: int) -> None:
        """日別ダイアログから新規イベントを追加。"""
        title_field = ft.TextField(
            label="タイトル", autofocus=True, text_size=14,
        )
        date_val = f"{year:04d}-{month:02d}-{day:02d}"
        date_field = ft.TextField(
            label="日付 (YYYY-MM-DD)", value=date_val,
            hint_text="YYYY-MM-DD", text_size=14,
        )
        time_field = ft.TextField(
            label="時刻 (HH:MM)", value="09:00",
            hint_text="HH:MM", text_size=14,
        )

        def _save(e):
            text = title_field.value.strip()
            if not text:
                title_field.error_text = "タイトルを入力してください"
                self._page.update()
                return
            d_str = date_field.value.strip()
            t_str = time_field.value.strip()
            if not d_str:
                date_field.error_text = "日付を入力してください"
                self._page.update()
                return
            if not t_str:
                time_field.error_text = "時刻を入力してください"
                self._page.update()
                return
            try:
                new_dt = datetime.strptime(f"{d_str} {t_str}", "%Y-%m-%d %H:%M")
                new_dt = new_dt.replace(tzinfo=_JST)
            except ValueError:
                date_field.error_text = "形式: YYYY-MM-DD"
                time_field.error_text = "形式: HH:MM"
                self._page.update()
                return
            try:
                db_client.add_event(
                    title=text, start_at=new_dt.isoformat(), source="user",
                )
            except Exception:
                pass
            add_dlg.open = False
            self._page.update()
            self._refresh_content()

        def _cancel(e):
            add_dlg.open = False
            self._page.update()

        add_dlg = ft.AlertDialog(
            title=ft.Text("予定を追加", size=18, weight=ft.FontWeight.W_600,
                          color=DARK_TEXT),
            content=ft.Column([title_field, date_field, time_field],
                              tight=True, spacing=12),
            actions=[
                ft.TextButton("キャンセル", on_click=_cancel),
                ft.ElevatedButton("追加", bgcolor=BLUE, color=CARD_BG, on_click=_save),
            ],
        )
        self._page.overlay.append(add_dlg)
        add_dlg.open = True
        self._page.update()

    # ==================================================================
    # 詳細ダイアログ
    # ==================================================================
    def _show_detail(self, title: str, rows: list[tuple[str, str]],
                     accent: str = BLUE,
                     on_delete: callable | None = None,
                     on_edit: callable | None = None) -> None:
        """汎用の詳細表示ダイアログ。rows は (ラベル, 値) のリスト。"""
        content_items: list[ft.Control] = []
        for label, value in rows:
            content_items.append(ft.Container(
                content=ft.Column([
                    ft.Text(label, size=12, weight=ft.FontWeight.W_600, color=MID_TEXT),
                    ft.Markdown(
                        value or "—", selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        code_theme=ft.MarkdownCodeTheme.MONOKAI,
                        md_style_sheet=ft.MarkdownStyleSheet(
                            p_text_style=ft.TextStyle(size=14, color=DARK_TEXT),
                            strong_text_style=ft.TextStyle(weight=ft.FontWeight.W_700, color=DARK_TEXT),
                            list_bullet_text_style=ft.TextStyle(size=14, color=DARK_TEXT),
                        ),
                    ),
                ], spacing=2),
                padding=ft.padding.only(bottom=10),
            ))

        def _close(e=None):
            dialog.open = False
            self._page.update()

        def _do_delete(e):
            dialog.open = False
            self._page.update()
            if on_delete:
                on_delete()

        def _do_edit(e):
            dialog.open = False
            self._page.update()
            if on_edit:
                on_edit()

        actions = []
        if on_delete:
            actions.append(ft.TextButton(
                "削除", style=ft.ButtonStyle(color=CORAL),
                on_click=_do_delete,
            ))
        if on_edit:
            actions.append(ft.TextButton(
                "編集", style=ft.ButtonStyle(color=BLUE),
                on_click=_do_edit,
            ))
        actions.append(ft.TextButton("閉じる", on_click=_close))

        dialog = ft.AlertDialog(
            title=ft.Row([
                ft.Container(width=6, height=24, bgcolor=accent, border_radius=3),
                ft.Text(title, size=16, weight=ft.FontWeight.W_700, color=DARK_TEXT,
                        expand=True, max_lines=2),
            ], spacing=10),
            content=ft.Column(content_items, tight=True, spacing=4,
                              scroll=ft.ScrollMode.AUTO),
            actions=actions,
        )
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()

    # ==================================================================
    # 削除ヘルパー
    # ==================================================================
    def _delete_event(self, event_id: int) -> None:
        try:
            db_client.delete_event(event_id)
        except Exception:
            pass
        self._page.update()

    def _delete_log(self, log_id: int) -> None:
        try:
            db_client.delete_machine_log(log_id)
        except Exception:
            pass
        self._page.update()

    # ==================================================================
    # イベント編集ダイアログ
    # ==================================================================
    def _show_edit_event_dialog(self, event: dict) -> None:
        title_field = ft.TextField(
            label="タイトル", value=event.get("title", ""),
            autofocus=True, text_size=14,
        )
        start_raw = event.get("start_at", "")
        try:
            dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            date_val = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, AttributeError):
            date_val = start_raw[:16].replace("T", " ")
        date_field = ft.TextField(
            label="日時 (YYYY-MM-DD HH:MM)", value=date_val,
            hint_text="YYYY-MM-DD HH:MM", text_size=14,
        )
        note_field = ft.TextField(
            label="メモ", value=event.get("note", ""), text_size=14,
        )

        def _save(e):
            text = title_field.value.strip()
            if not text:
                return
            date_str = date_field.value.strip()
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
            db_client.update_event(
                event["id"],
                title=text,
                start_at=dt.isoformat(),
                note=note_field.value.strip(),
            )
            dialog.open = False
            self._page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("イベント編集", size=18, weight=ft.FontWeight.W_600),
            content=ft.Column([title_field, date_field, note_field], tight=True, spacing=12),
            actions=[
                ft.TextButton("キャンセル",
                              on_click=lambda e: setattr(dialog, "open", False) or self._page.update()),
                ft.ElevatedButton("保存", bgcolor=BLUE, color=CARD_BG, on_click=_save),
            ],
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
