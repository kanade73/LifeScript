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
from .app import COLORS

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
            border=ft.border.all(1, "#E8E4DC"),
        )

        # ── Machine logs ─────────────────────────────────────
        self._machine_logs_list = ft.ListView(expand=True, spacing=4, padding=4)

        machine_logs_section = ft.Container(
            content=ft.Column([
                ft.Text("マシンログ", size=14, weight=ft.FontWeight.W_700, color=COLORS["dark_text"]),
                self._machine_logs_list,
            ], spacing=8, expand=True),
            expand=True,
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=14,
            border=ft.border.all(1, "#E8E4DC"),
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
                    border_radius=10,
                    padding=10,
                ),
            ], spacing=6, expand=True),
            expand=True,
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=12,
            border=ft.border.all(1, "#E8E4DC"),
        )

        self._content = ft.Column([
            ft.Text("Dashboard", size=22, weight=ft.FontWeight.W_700, color=COLORS["dark_text"]),
            status_row,
            ft.Row([automation_section, machine_logs_section], expand=True, spacing=12),
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
                    border_radius=12, alignment=ft.Alignment(0, 0),
                ),
                ft.Column([
                    ft.Text(label, size=11, color=COLORS["light_text"], weight=ft.FontWeight.W_500),
                    ft.Text(value, size=15, color=COLORS["dark_text"], weight=ft.FontWeight.W_700),
                ], spacing=2),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            border=ft.border.all(1, "#E8E4DC"),
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
                                    f"#{script['id']}  {dsl_preview}",
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
                        border_radius=12,
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
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
                    if sec < 10:
                        raise ValueError
                except (TypeError, ValueError):
                    interval_field.error_text = "10以上の整数"
                    self._page.update()
                    return
                new_trigger = {"type": "interval", "seconds": sec}

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
                        border_radius=8,
                        padding=8,
                    )
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Periodic refresh
    # ------------------------------------------------------------------
    def _start_refresh_timer(self) -> None:
        def refresh() -> None:
            self._refresh_status()
            self._refresh_machine_logs()
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
