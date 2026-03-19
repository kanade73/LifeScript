"""ダッシュボード — マシンが持っている文脈の全体像を可視化。

- オートメーション管理（一時停止・再開・削除・トリガー変更）
- スクリプト稼働状況
- 今週のカレンダー集計
- machine_logs履歴
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import flet as ft

from ..database.client import db_client
from .app import CARD_SHADOW, COLORS, SHADOW_SOFT

_JST = timezone(timedelta(hours=9))


class DashboardView:
    def __init__(self, page: ft.Page, scheduler) -> None:
        self._page = page
        self._scheduler = scheduler

        # ── Status cards ─────────────────────────────────────
        self._scheduler_card = self._status_card(
            icon=ft.Icons.SCHEDULE_ROUNDED, label="Scheduler", value="—", accent=COLORS["green"],
        )
        self._scripts_card = self._status_card(
            icon=ft.Icons.CODE_ROUNDED, label="Scripts", value="0", accent=COLORS["yellow"],
        )
        self._events_card = self._status_card(
            icon=ft.Icons.CALENDAR_MONTH, label="今週のイベント", value="0", accent=COLORS["blue"],
        )
        self._db_card = self._status_card(
            icon=ft.Icons.CLOUD_ROUNDED, label="Database", value="—", accent=COLORS["purple"],
        )

        status_row = ft.Row(
            [self._scheduler_card, self._scripts_card, self._events_card, self._db_card],
            spacing=12,
        )

        # ── Automation management ─────────────────────────────
        self._automation_list = ft.ListView(expand=True, spacing=6, padding=4)

        automation_section = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.BOLT_ROUNDED, size=18, color=COLORS["yellow"]),
                    ft.Text("オートメーション管理", size=14, weight=ft.FontWeight.W_700,
                            color=COLORS["dark_text"]),
                    ft.Container(expand=True),
                    ft.IconButton(
                        ft.Icons.REFRESH_ROUNDED, icon_size=18, icon_color=COLORS["mid_text"],
                        tooltip="更新", style=ft.ButtonStyle(padding=4),
                        on_click=lambda e: self._refresh_automations(),
                    ),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Divider(height=1, color="#E8E4DC"),
                self._automation_list,
            ], spacing=8, expand=True),
            expand=2,
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=14,
            shadow=CARD_SHADOW,
        )

        # ── Machine logs ─────────────────────────────────────
        self._machine_logs_list = ft.ListView(expand=True, spacing=4, padding=4)

        machine_logs_section = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, size=18, color=COLORS["purple"]),
                    ft.Text("ダリーログ", size=14, weight=ft.FontWeight.W_700, color=COLORS["dark_text"]),
                ], spacing=6),
                self._machine_logs_list,
            ], spacing=8, expand=True),
            expand=True,
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=14,
            shadow=CARD_SHADOW,
        )

        # ── Function Ranking ─────────────────────────────────
        self._function_ranking_list = ft.ListView(expand=True, spacing=4, padding=4)

        function_ranking_section = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.LEADERBOARD_ROUNDED, size=18, color=COLORS["orange"]),
                    ft.Text("よく使われている関数", size=14, weight=ft.FontWeight.W_700, color=COLORS["dark_text"]),
                ], spacing=6),
                self._function_ranking_list,
            ], spacing=8, expand=True),
            expand=True,
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=14,
            shadow=CARD_SHADOW,
        )

        # ── Live logs ─────────────────────────────────────────
        self._log_list = ft.ListView(expand=True, auto_scroll=True, spacing=1)

        log_panel = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.TERMINAL_ROUNDED, size=14, color=COLORS["light_text"]),
                    ft.Text("Live Logs", size=12, weight=ft.FontWeight.W_600, color=COLORS["mid_text"]),
                ], spacing=6),
                ft.Container(
                    content=self._log_list,
                    expand=True,
                    bgcolor=COLORS["editor_bg"],
                    border_radius=12,
                    padding=10,
                ),
            ], spacing=6, expand=True),
            expand=True,
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=12,
            shadow=CARD_SHADOW,
        )

        # ── 週間カレンダーグラフ + スケジューラタイムライン ──
        self._week_graph = ft.Container(
            content=ft.Column([], spacing=4),
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=14,
            shadow=CARD_SHADOW,
            expand=True,
        )
        self._scheduler_timeline = ft.Container(
            content=ft.Column([], spacing=4),
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=14,
            shadow=CARD_SHADOW,
            expand=True,
        )

        graph_row = ft.Row([self._week_graph, self._scheduler_timeline], spacing=12)

        self._content = ft.Column([
            ft.Text("Dashboard", size=22, weight=ft.FontWeight.W_700, color=COLORS["dark_text"]),
            status_row,
            graph_row,
            ft.Row([automation_section, machine_logs_section, function_ranking_section], expand=True, spacing=12),
            log_panel,
        ], expand=True, spacing=16)

        self._refresh_all()
        self._start_refresh_timer()

    def build(self) -> ft.Column:
        return self._content

    # ------------------------------------------------------------------
    # Status card builder
    # ------------------------------------------------------------------
    @staticmethod
    def _status_card(icon: str, label: str, value: str, accent: str) -> ft.Container:
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(icon, size=20, color=COLORS["card_bg"]),
                    width=40, height=40, bgcolor=accent,
                    border_radius=14, alignment=ft.Alignment(0, 0),
                ),
                ft.Column([
                    ft.Text(label, size=11, color=COLORS["light_text"], weight=ft.FontWeight.W_500),
                    ft.Text(value, size=15, color=COLORS["dark_text"], weight=ft.FontWeight.W_700),
                ], spacing=2),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=COLORS["card_bg"],
            border_radius=20,
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            shadow=CARD_SHADOW,
            expand=True,
        )

    # ------------------------------------------------------------------
    # Automation management
    # ------------------------------------------------------------------
    def _refresh_automations(self) -> None:
        self._automation_list.controls.clear()
        try:
            scripts = db_client.get_scripts()
            active_ids = self._scheduler.get_active_ids()

            if not scripts:
                self._automation_list.controls.append(
                    ft.Container(
                        content=ft.Text("登録されたスクリプトなし", size=12,
                                        color=COLORS["light_text"], italic=True),
                        padding=8,
                    )
                )
            else:
                for script in scripts:
                    sid = str(script["id"])
                    is_active = sid in active_ids
                    is_paused = self._scheduler.is_paused(sid)
                    trigger = self._scheduler.get_trigger_info(sid)
                    trigger_desc = self._scheduler.describe_trigger(trigger)
                    script_name = script.get("name", "") or ""
                    dsl_preview = (script.get("dsl_text", "") or "")[:60].replace("\n", " ")

                    # Status indicator
                    if is_paused:
                        status_color = COLORS["yellow"]
                        status_text = "一時停止"
                    elif is_active:
                        status_color = COLORS["green"]
                        status_text = "稼働中"
                    else:
                        status_color = COLORS["light_text"]
                        status_text = "未登録"

                    # Action buttons
                    actions = []
                    if is_active:
                        actions.append(ft.IconButton(
                            ft.Icons.PAUSE_ROUNDED, icon_size=16, icon_color=COLORS["yellow"],
                            tooltip="一時停止", style=ft.ButtonStyle(padding=4),
                            on_click=lambda e, s=sid: self._pause_script(s),
                        ))
                    elif is_paused:
                        actions.append(ft.IconButton(
                            ft.Icons.PLAY_ARROW_ROUNDED, icon_size=16, icon_color=COLORS["green"],
                            tooltip="再開", style=ft.ButtonStyle(padding=4),
                            on_click=lambda e, sc=script: self._resume_script(sc),
                        ))
                    else:
                        actions.append(ft.IconButton(
                            ft.Icons.PLAY_ARROW_ROUNDED, icon_size=16, icon_color=COLORS["green"],
                            tooltip="登録", style=ft.ButtonStyle(padding=4),
                            on_click=lambda e, sc=script: self._register_script(sc),
                        ))

                    actions.append(ft.IconButton(
                        ft.Icons.EDIT_ROUNDED, icon_size=16, icon_color=COLORS["blue"],
                        tooltip="トリガー変更", style=ft.ButtonStyle(padding=4),
                        on_click=lambda e, sc=script, tr=trigger: self._show_edit_trigger(sc, tr),
                    ))
                    actions.append(ft.IconButton(
                        ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=16, icon_color=COLORS["coral"],
                        tooltip="削除", style=ft.ButtonStyle(padding=4),
                        on_click=lambda e, sc=script: self._delete_script(sc),
                    ))

                    tile = ft.Container(
                        content=ft.Row([
                            ft.Container(width=8, height=8, border_radius=4, bgcolor=status_color),
                            ft.Column([
                                ft.Text(
                                    script_name if script_name else dsl_preview or f"スクリプト #{script['id']}",
                                    size=12, weight=ft.FontWeight.W_600, color=COLORS["dark_text"],
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Row([
                                    ft.Text(status_text, size=10, color=status_color,
                                            weight=ft.FontWeight.W_600),
                                    ft.Text(f"  {trigger_desc}", size=10, color=COLORS["mid_text"]),
                                ], spacing=0),
                            ], spacing=2, expand=True),
                            *actions,
                        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        bgcolor=COLORS["bg"],
                        border_radius=14,
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        shadow=SHADOW_SOFT,
                    )
                    self._automation_list.controls.append(tile)
        except Exception:
            pass
        self._page.update()

    def _pause_script(self, script_id: str) -> None:
        self._scheduler.pause_script(script_id)
        self._refresh_automations()

    def _resume_script(self, script: dict) -> None:
        self._scheduler.resume_script(str(script["id"]), script)
        self._refresh_automations()

    def _register_script(self, script: dict) -> None:
        self._scheduler.add_script(script)
        self._refresh_automations()

    def _delete_script(self, script: dict) -> None:
        sid = str(script["id"])
        self._scheduler.remove_script(sid)
        db_client.delete_script(script["id"])
        self._refresh_automations()

    def _show_edit_trigger(self, script: dict, current_trigger: dict) -> None:
        sid = str(script["id"])
        trigger_type = current_trigger.get("type", "interval")

        type_dropdown = ft.Dropdown(
            label="トリガータイプ",
            value=trigger_type,
            options=[
                ft.dropdown.Option("interval", "インターバル（定期実行）"),
                ft.dropdown.Option("cron", "時刻指定（毎日）"),
                ft.dropdown.Option("after", "遅延実行（1回だけ）"),
            ],
            width=280,
        )

        # Interval fields
        interval_val = current_trigger.get("seconds", 3600)
        interval_field = ft.TextField(
            label="間隔（秒）", value=str(interval_val), width=280,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        # Cron fields
        cron_hour = ft.TextField(
            label="時", value=str(current_trigger.get("hour", 8)), width=130,
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        cron_minute = ft.TextField(
            label="分", value=str(current_trigger.get("minute", 0)), width=130,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        # Preset buttons for interval
        def _set_preset(seconds: int) -> None:
            interval_field.value = str(seconds)
            self._page.update()

        presets = ft.Row([
            ft.TextButton("1分", on_click=lambda e: _set_preset(60),
                          style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=8))),
            ft.TextButton("10分", on_click=lambda e: _set_preset(600),
                          style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=8))),
            ft.TextButton("1時間", on_click=lambda e: _set_preset(3600),
                          style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=8))),
            ft.TextButton("1日", on_click=lambda e: _set_preset(86400),
                          style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=8))),
        ], spacing=4)

        def _save(e: ft.ControlEvent) -> None:
            ttype = type_dropdown.value
            if ttype == "cron":
                try:
                    h = int(cron_hour.value)
                    m = int(cron_minute.value)
                    if not (0 <= h <= 23 and 0 <= m <= 59):
                        raise ValueError
                except (TypeError, ValueError):
                    cron_hour.error_text = "0-23"
                    cron_minute.error_text = "0-59"
                    self._page.update()
                    return
                new_trigger = {"type": "cron", "hour": h, "minute": m}
            else:
                try:
                    sec = int(interval_field.value)
                    minimum = 1 if ttype == "after" else 10
                    if sec < minimum:
                        raise ValueError
                except (TypeError, ValueError):
                    interval_field.error_text = "1以上の整数" if ttype == "after" else "10以上の整数"
                    self._page.update()
                    return
                new_trigger = {"type": ttype, "seconds": sec}

            self._scheduler.update_trigger(sid, script, new_trigger)
            dialog.open = False
            self._refresh_automations()
            self._page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(f"トリガー変更 — Script#{sid}", size=16, weight=ft.FontWeight.W_600),
            content=ft.Column([
                type_dropdown,
                ft.Container(height=8),
                ft.Text("インターバル設定", size=12, weight=ft.FontWeight.W_600,
                        color=COLORS["dark_text"]),
                interval_field,
                presets,
                ft.Container(height=8),
                ft.Text("時刻指定設定", size=12, weight=ft.FontWeight.W_600,
                        color=COLORS["dark_text"]),
                ft.Row([cron_hour, cron_minute], spacing=12),
            ], tight=True, spacing=4),
            actions=[
                ft.TextButton("キャンセル",
                              on_click=lambda e: setattr(dialog, "open", False) or self._page.update()),
                ft.ElevatedButton("保存", bgcolor=COLORS["blue"], color=COLORS["card_bg"],
                                  on_click=_save),
            ],
        )
        self._page.overlay.append(dialog)
        dialog.open = True
        self._page.update()

    # ------------------------------------------------------------------
    # Log receiving
    # ------------------------------------------------------------------
    def receive_logs(self, entries: list) -> None:
        for entry in entries:
            if isinstance(entry, tuple):
                source, msg, level = entry
                text = f"[{source}] {msg}"
            else:
                text = str(entry)
                level = "INFO"
            color = COLORS["coral"] if level == "ERROR" else (COLORS["yellow"] if level == "WARN" else COLORS["green"])
            self._log_list.controls.append(
                ft.Text(text, color=color, size=11, font_family="Courier New, monospace", selectable=True)
            )
        if len(self._log_list.controls) > 300:
            self._log_list.controls = self._log_list.controls[-300:]
        self._page.update()

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def _refresh_all(self) -> None:
        self._refresh_status()
        self._refresh_graphs()
        self._refresh_automations()
        self._refresh_machine_logs()

    def _refresh_status(self) -> None:
        # Scheduler
        running = self._scheduler.is_running
        val = self._scheduler_card.content.controls[1]
        val.controls[1] = ft.Text(
            "Running" if running else "Stopped",
            size=15, color=COLORS["green"] if running else COLORS["coral"],
            weight=ft.FontWeight.W_700,
        )

        # Scripts
        try:
            scripts = db_client.get_scripts()
            active_ids = self._scheduler.get_active_ids()
            val2 = self._scripts_card.content.controls[1]
            val2.controls[1] = ft.Text(
                f"{len(scripts)} total / {len(active_ids)} active",
                size=15, color=COLORS["dark_text"], weight=ft.FontWeight.W_700,
            )
        except Exception:
            pass

        # Events this week
        try:
            now = datetime.now(_JST)
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
            events = db_client.get_events(start_from=start.isoformat(), start_to=end.isoformat())
            val3 = self._events_card.content.controls[1]
            val3.controls[1] = ft.Text(
                str(len(events)), size=15, color=COLORS["dark_text"], weight=ft.FontWeight.W_700,
            )
        except Exception:
            pass

        # Database
        val4 = self._db_card.content.controls[1]
        if db_client.is_supabase:
            db_label, db_color = "Supabase", COLORS["green"]
        elif db_client.is_connected:
            db_label, db_color = "SQLite (local)", COLORS["yellow"]
        else:
            db_label, db_color = "Not connected", COLORS["light_text"]
        val4.controls[1] = ft.Text(db_label, size=15, color=db_color, weight=ft.FontWeight.W_700)

    def _refresh_graphs(self) -> None:
        """週間イベントグラフ + スケジューラタイムラインを更新。"""
        # ── 週間イベント棒グラフ ──
        try:
            now = datetime.now(_JST)
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)

            day_labels = ["月", "火", "水", "木", "金", "土", "日"]
            day_counts = []
            max_count = 1

            for i in range(7):
                day_start = start + timedelta(days=i)
                day_end = day_start + timedelta(days=1)
                events = db_client.get_events(
                    start_from=day_start.isoformat(),
                    start_to=day_end.isoformat(),
                )
                count = len(events)
                day_counts.append(count)
                if count > max_count:
                    max_count = count

            today_idx = now.weekday()
            bars = []
            for i, (label, count) in enumerate(zip(day_labels, day_counts)):
                bar_height = max(4, int(60 * count / max_count)) if count > 0 else 4
                is_today = i == today_idx
                bar_color = COLORS["yellow"] if is_today else COLORS["blue"]

                bars.append(ft.Column([
                    ft.Text(str(count) if count > 0 else "", size=10, color=COLORS["mid_text"],
                            text_align=ft.TextAlign.CENTER, weight=ft.FontWeight.W_600),
                    ft.Container(
                        width=28, height=bar_height,
                        bgcolor=bar_color, border_radius=6,
                    ),
                    ft.Text(label, size=11, color=COLORS["dark_text"] if is_today else COLORS["mid_text"],
                            weight=ft.FontWeight.W_700 if is_today else ft.FontWeight.W_400),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2,
                    alignment=ft.MainAxisAlignment.END))

            self._week_graph.content = ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.BAR_CHART_ROUNDED, size=16, color=COLORS["blue"]),
                    ft.Text("今週のイベント数", size=13, weight=ft.FontWeight.W_700,
                            color=COLORS["dark_text"]),
                ], spacing=6),
                ft.Container(
                    content=ft.Row(bars, alignment=ft.MainAxisAlignment.SPACE_AROUND,
                                   vertical_alignment=ft.CrossAxisAlignment.END),
                    height=100,
                    padding=ft.padding.only(top=8),
                ),
            ], spacing=8)
        except Exception:
            self._week_graph.content = ft.Text("グラフ読み込みエラー", size=12, color=COLORS["light_text"])

        # ── スケジューラタイムライン ──
        try:
            scripts = db_client.get_scripts()
            active_ids = self._scheduler.get_active_ids()
            timeline_items = []

            for script in scripts:
                sid = str(script["id"])
                if sid not in active_ids:
                    continue
                trigger = self._scheduler.get_trigger_info(sid)
                trigger_desc = self._scheduler.describe_trigger(trigger)
                name = script.get("name", "") or (script.get("dsl_text", "") or "")[:30].replace("\n", " ")
                tt = trigger.get("type", "interval")

                if tt == "cron":
                    icon = ft.Icons.ACCESS_TIME_ROUNDED
                    color = COLORS["orange"]
                    time_text = f'{trigger.get("hour", 0):02d}:{trigger.get("minute", 0):02d}'
                elif tt == "after":
                    icon = ft.Icons.TIMER_OUTLINED
                    color = COLORS["green"]
                    secs = trigger.get("seconds", 0)
                    time_text = f"{secs}s"
                elif tt == "interval":
                    icon = ft.Icons.LOOP_ROUNDED
                    color = COLORS["blue"]
                    secs = trigger.get("seconds", 3600)
                    if secs >= 3600:
                        time_text = f"{secs // 3600}h"
                    else:
                        time_text = f"{secs // 60}m"
                else:
                    icon = ft.Icons.FLASH_ON_ROUNDED
                    color = COLORS["green"]
                    time_text = "once"

                timeline_items.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Container(
                                content=ft.Text(time_text, size=10, color=COLORS["card_bg"],
                                                weight=ft.FontWeight.W_700),
                                bgcolor=color, border_radius=6, width=40,
                                alignment=ft.Alignment(0, 0),
                                padding=ft.padding.symmetric(vertical=4),
                            ),
                            ft.Icon(icon, size=14, color=color),
                            ft.Text(name or f"#{sid}", size=11, color=COLORS["dark_text"],
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.padding.symmetric(vertical=2),
                    )
                )

            if not timeline_items:
                timeline_items.append(
                    ft.Text("稼働中のスクリプトなし", size=12, color=COLORS["light_text"], italic=True)
                )

            self._scheduler_timeline.content = ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.TIMELINE_ROUNDED, size=16, color=COLORS["green"]),
                    ft.Text("スケジューラ", size=13, weight=ft.FontWeight.W_700,
                            color=COLORS["dark_text"]),
                    ft.Container(expand=True),
                    ft.Text(f"{len([s for s in scripts if str(s['id']) in active_ids])} 件稼働",
                            size=11, color=COLORS["green"], weight=ft.FontWeight.W_600),
                ], spacing=6),
                ft.Column(timeline_items, spacing=2),
            ], spacing=8)
        except Exception:
            self._scheduler_timeline.content = ft.Text("タイムライン読み込みエラー", size=12,
                                                        color=COLORS["light_text"])

    def _refresh_machine_logs(self) -> None:
        self._machine_logs_list.controls.clear()
        try:
            logs = db_client.get_machine_logs(limit=20)
            if not logs:
                self._machine_logs_list.controls.append(
                    ft.Container(
                        content=ft.Text("ログなし", size=12, color=COLORS["light_text"], italic=True),
                        padding=8,
                    )
                )
            for log_entry in logs:
                action = log_entry.get("action_type", "")
                content = log_entry.get("content", "")
                time_str = log_entry.get("triggered_at", "")[:19].replace("T", " ")

                icon_map = {
                    "notify": (ft.Icons.NOTIFICATIONS_NONE, COLORS["green"]),
                    "notify_scheduled": (ft.Icons.SCHEDULE, COLORS["blue"]),
                    "calendar_suggest": (ft.Icons.LIGHTBULB_OUTLINE, COLORS["orange"]),
                    "script_error": (ft.Icons.ERROR_OUTLINE, COLORS["coral"]),
                    "reminder": (ft.Icons.PUSH_PIN_ROUNDED, COLORS["purple"]),
                }
                icon_name, icon_color = icon_map.get(action, (ft.Icons.INFO_OUTLINE, COLORS["mid_text"]))

                self._machine_logs_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(icon_name, size=16, color=icon_color),
                            ft.Column([
                                ft.Text(content, size=12, color=COLORS["dark_text"], max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text(time_str, size=10, color=COLORS["light_text"]),
                            ], spacing=2, expand=True),
                        ], spacing=8),
                        bgcolor=COLORS["bg"],
                        border_radius=12,
                        padding=8,
                        shadow=SHADOW_SOFT,
                    )
                )
        except Exception:
            pass

    def _refresh_function_ranking(self) -> None:
        self._function_ranking_list.controls.clear()
        try:
            # 最新のログ（最大1000件）を取得して集計
            logs = db_client.get_machine_logs(limit=1000)
            func_counts: dict[str, int] = {}

            for entry in logs:
                action = entry.get("action_type", "")
                content = entry.get("content", "")

                # action_typeからの抽出
                if action == "notify" or action == "notify_scheduled":
                    func_counts["notify()"] = func_counts.get("notify()", 0) + 1
                elif action == "calendar_suggest":
                    func_counts["calendar.suggest()"] = func_counts.get("calendar.suggest()", 0) + 1
                elif action.startswith("widget:"):
                    func_counts["widget.show()"] = func_counts.get("widget.show()", 0) + 1
                elif action == "reminder":
                    func_counts["calendar.add()"] = func_counts.get("calendar.add()", 0) + 1
                elif action == "memory":
                    func_counts["memory.write()"] = func_counts.get("memory.write()", 0) + 1
                elif action == "memory_auto":
                    func_counts["machine.analyze()"] = func_counts.get("machine.analyze()", 0) + 1

                # contentからのキーワードベース抽出（簡易的）
                import re as _re
                for func_match in _re.finditer(r"([a-z_]+(?:\.[a-z_]+)?)\(", content):
                    name = func_match.group(1) + "()"
                    # 一般的なPython組み込み関数などを除外
                    if name not in ("print()", "len()", "range()", "str()", "int()"):
                        func_counts[name] = func_counts.get(name, 0) + 1

            if not func_counts:
                self._function_ranking_list.controls.append(
                    ft.Container(
                        content=ft.Text("データ不足", size=12, color=COLORS["light_text"], italic=True),
                        padding=8,
                    )
                )
                self._page.update()
                return

            # 上位5件をソートして表示
            sorted_funcs = sorted(func_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            
            medals = ["🥇", "🥈", "🥉", "４位", "５位"]
            colors = [COLORS["yellow"], "#C0C0C0", "#CD7F32", COLORS["mid_text"], COLORS["mid_text"]]

            for i, (func_name, count) in enumerate(sorted_funcs):
                self._function_ranking_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Container(
                                content=ft.Text(medals[i] if i < 3 else f" {i+1} ", size=14 if i < 3 else 12),
                                width=24, alignment=ft.Alignment(0, 0)
                            ),
                            ft.Text(func_name, size=13, weight=ft.FontWeight.W_700,
                                    color=COLORS["blue"], font_family="monospace"),
                            ft.Container(expand=True),
                            ft.Container(
                                content=ft.Text(f"{count} 回", size=11, color=COLORS["dark_text"], weight=ft.FontWeight.W_600),
                                bgcolor=f"{colors[i]}33",
                                padding=ft.padding.symmetric(horizontal=8, vertical=2),
                                border_radius=10,
                            )
                        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        bgcolor=COLORS["bg"],
                        border_radius=12,
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        shadow=SHADOW_SOFT,
                    )
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Periodic refresh
    # ------------------------------------------------------------------
    def _refresh_all(self) -> None:
        self._refresh_status()
        self._refresh_graphs()
        self._refresh_automations()
        self._refresh_machine_logs()
        self._refresh_function_ranking()

    def _start_refresh_timer(self) -> None:
        def refresh() -> None:
            self._refresh_status()
            self._refresh_graphs()
            self._refresh_machine_logs()
            self._refresh_function_ranking()
            try:
                self._page.update()
            except Exception:
                pass
            t = threading.Timer(5.0, refresh)
            t.daemon = True
            t.start()

        t = threading.Timer(5.0, refresh)
        t.daemon = True
        t.start()
