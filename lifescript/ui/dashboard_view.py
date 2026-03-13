"""ダッシュボード画面 — ステータスカード・ルール一覧・ライブログの開発寄りビュー。"""

from __future__ import annotations

import threading

import flet as ft

from ..database.client import db_client
from .app import COLORS


class DashboardView:
    def __init__(self, page: ft.Page, scheduler) -> None:
        self._page = page
        self._scheduler = scheduler
        self._pending_remove_rule_id: str | None = None

        self._remove_confirm_message = ft.Text(
            "このルールを削除しますか？",
            size=13,
            color=COLORS["dark_text"],
        )
        self._remove_confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("ルール削除の確認", weight=ft.FontWeight.W_700),
            content=self._remove_confirm_message,
            actions=[
                ft.TextButton("Cancel", on_click=self._close_remove_confirm),
                ft.TextButton(
                    "Delete",
                    style=ft.ButtonStyle(color=COLORS["coral"]),
                    on_click=self._confirm_remove_rule,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # ── Status cards ────────────────────────────────────────────
        self._scheduler_card = self._status_card(
            icon=ft.Icons.SCHEDULE_ROUNDED,
            label="Scheduler",
            value="—",
            accent=COLORS["green"],
        )
        self._rules_card = self._status_card(
            icon=ft.Icons.BOLT_ROUNDED,
            label="Rules",
            value="0",
            accent=COLORS["yellow"],
        )
        self._db_card = self._status_card(
            icon=ft.Icons.CLOUD_ROUNDED,
            label="Database",
            value="—",
            accent=COLORS["blue"],
        )

        status_row = ft.Row(
            [self._scheduler_card, self._rules_card, self._db_card],
            spacing=12,
        )

        # ── Rule cards grid ─────────────────────────────────────────
        self._cards_row = ft.Row(wrap=True, spacing=12, run_spacing=12)

        cards_section = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Your Rules",
                        size=16,
                        weight=ft.FontWeight.W_700,
                        color=COLORS["dark_text"],
                    ),
                    self._cards_row,
                ],
                spacing=10,
            ),
            padding=ft.padding.symmetric(vertical=4),
        )

        # ── Log panel ──────────────────────────────────────────────
        self._log_list = ft.ListView(expand=True, auto_scroll=True, spacing=1)

        log_panel = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.TERMINAL_ROUNDED,
                                size=14,
                                color=COLORS["light_text"],
                            ),
                            ft.Text(
                                "Live Logs",
                                size=12,
                                weight=ft.FontWeight.W_600,
                                color=COLORS["mid_text"],
                            ),
                        ],
                        spacing=6,
                    ),
                    ft.Container(
                        content=self._log_list,
                        expand=True,
                        bgcolor=COLORS["editor_bg"],
                        border_radius=10,
                        padding=10,
                    ),
                ],
                spacing=6,
                expand=True,
            ),
            expand=True,
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=12,
            border=ft.border.all(1, "#E8E4DC"),
        )

        self._content = ft.Column(
            [
                status_row,
                cards_section,
                log_panel,
            ],
            expand=True,
            spacing=16,
        )

        self._refresh_status()
        self._refresh_cards()
        self._start_refresh_timer()

    def build(self) -> ft.Column:
        return self._content

    # ------------------------------------------------------------------
    # Status card builder
    # ------------------------------------------------------------------
    @staticmethod
    def _status_card(icon: str, label: str, value: str, accent: str) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(icon, size=20, color=COLORS["card_bg"]),
                        width=40,
                        height=40,
                        bgcolor=accent,
                        border_radius=12,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                label,
                                size=11,
                                color=COLORS["light_text"],
                                weight=ft.FontWeight.W_500,
                            ),
                            ft.Text(
                                value,
                                size=15,
                                color=COLORS["dark_text"],
                                weight=ft.FontWeight.W_700,
                            ),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=COLORS["card_bg"],
            border_radius=16,
            padding=ft.padding.symmetric(horizontal=20, vertical=14),
            border=ft.border.all(1, "#E8E4DC"),
            expand=True,
        )

    # ------------------------------------------------------------------
    # Log receiving
    # ------------------------------------------------------------------
    def receive_logs(self, entries: list[str]) -> None:
        for entry in entries:
            if "ERROR" in entry:
                color = COLORS["coral"]
            elif "WARN" in entry:
                color = COLORS["yellow"]
            else:
                color = COLORS["green"]
            self._log_list.controls.append(
                ft.Text(
                    entry,
                    color=color,
                    size=11,
                    font_family="Courier New, monospace",
                    selectable=True,
                )
            )
        if len(self._log_list.controls) > 300:
            self._log_list.controls = self._log_list.controls[-300:]
        self._page.update()

    # ------------------------------------------------------------------
    # Status refresh
    # ------------------------------------------------------------------
    def _refresh_status(self) -> None:
        # Scheduler
        running = self._scheduler.is_running
        val_col = self._scheduler_card.content.controls[1]
        val_col.controls[1] = ft.Text(
            "Running" if running else "Stopped",
            size=15,
            color=COLORS["green"] if running else COLORS["coral"],
            weight=ft.FontWeight.W_700,
        )

        # Rules
        try:
            rules = db_client.get_rules()
            active_ids = self._scheduler.get_active_ids()
            val_col2 = self._rules_card.content.controls[1]
            val_col2.controls[1] = ft.Text(
                f"{len(rules)} total / {len(active_ids)} active",
                size=15,
                color=COLORS["dark_text"],
                weight=ft.FontWeight.W_700,
            )
        except Exception:
            pass

        # Database
        val_col3 = self._db_card.content.controls[1]
        if db_client.is_supabase:
            db_label = "Supabase"
            db_color = COLORS["green"]
        elif db_client.is_connected:
            db_label = "SQLite (local)"
            db_color = COLORS["yellow"]
        else:
            db_label = "Not connected"
            db_color = COLORS["light_text"]
        val_col3.controls[1] = ft.Text(
            db_label,
            size=15,
            color=db_color,
            weight=ft.FontWeight.W_700,
        )

    # ------------------------------------------------------------------
    # Rule cards
    # ------------------------------------------------------------------
    def _refresh_cards(self) -> None:
        self._cards_row.controls.clear()
        try:
            rules = db_client.get_rules()
            active_ids = {str(i) for i in self._scheduler.get_active_ids()}
            if not rules:
                self._cards_row.controls.append(
                    ft.Container(
                        content=ft.Text(
                            "No rules yet — head to the Editor to create one!",
                            size=13,
                            color=COLORS["light_text"],
                            italic=True,
                        ),
                        padding=12,
                    )
                )
            for rule in rules:
                self._cards_row.controls.append(self._rule_card(rule, active_ids))
        except Exception:
            pass

    def _rule_card(self, rule: dict, active_ids: set[str]) -> ft.Container:
        is_active = str(rule["id"]) in active_ids
        rule_id = str(rule["id"])
        interval_sec = rule.get("trigger_seconds", 60)
        if interval_sec >= 3600:
            interval_label = f"every {interval_sec // 3600}h"
        elif interval_sec >= 60:
            interval_label = f"every {interval_sec // 60}m"
        else:
            interval_label = f"every {interval_sec}s"

        accent = COLORS["green"] if is_active else COLORS["light_text"]

        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=10,
                                height=10,
                                border_radius=5,
                                bgcolor=accent,
                            ),
                            ft.Text(
                                rule.get("title", "untitled"),
                                size=13,
                                weight=ft.FontWeight.W_600,
                                color=COLORS["dark_text"],
                                expand=True,
                            ),
                        ],
                        spacing=8,
                    ),
                    ft.Container(
                        content=ft.Text(
                            interval_label,
                            size=11,
                            color=COLORS["card_bg"],
                        ),
                        bgcolor=accent,
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=8, vertical=2),
                    ),
                    ft.OutlinedButton(
                        "Pause",
                        icon=ft.Icons.PAUSE_ROUNDED,
                        disabled=not is_active,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            side=ft.BorderSide(1, COLORS["coral"]),
                            color=COLORS["coral"],
                            padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        ),
                        on_click=lambda e, rid=rule_id: self._on_pause_rule(rid),
                    ),
                    ft.OutlinedButton(
                        "Delete",
                        icon=ft.Icons.DELETE_ROUNDED,
                        disabled=False,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            side=ft.BorderSide(1, COLORS["red"]),
                            color=COLORS["red"],
                            padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        ),
                        on_click=lambda e, rid=rule_id, title=rule.get("title", "untitled"): self._on_remove_click(rid, title),
                    ),
                ],
                spacing=8,
            ),
            bgcolor=COLORS["card_bg"],
            border_radius=14,
            padding=14,
            width=180,
            border=ft.border.all(1, "#E8E4DC"),
        )

    # ------------------------------------------------------------------
    # Periodic refresh timer and rule actions
    # ------------------------------------------------------------------
    def _start_refresh_timer(self) -> None:
        def refresh() -> None:
            self._refresh_status()
            self._refresh_cards()
            self._page.update()
            t = threading.Timer(5.0, refresh)
            t.daemon = True
            t.start()

        t = threading.Timer(5.0, refresh)
        t.daemon = True
        t.start()
        
    def _on_pause_rule(self, rule_id: str) -> None:
        try:
            self._scheduler.pause_rule(rule_id)
            self._refresh_status()
            self._refresh_cards()
            self._page.update()
        except Exception:
            pass

    def _on_remove_click(self, rule_id: str, title: str) -> None:
        self._pending_remove_rule_id = rule_id
        self._remove_confirm_message.value = f"『{title}』を削除しますか？"
        if self._remove_confirm_dialog not in self._page.overlay:
            self._page.overlay.append(self._remove_confirm_dialog)
        self._remove_confirm_dialog.open = True
        self._page.update()

    def _close_remove_confirm(self, e) -> None:
        self._remove_confirm_dialog.open = False
        self._page.update()

    def _confirm_remove_rule(self, e) -> None:
        if not self._pending_remove_rule_id:
            self._close_remove_confirm(e)
            return

        rule_id = self._pending_remove_rule_id
        self._pending_remove_rule_id = None
        try:
            self._scheduler.remove_rule(rule_id)
            db_client.delete_rule(rule_id)
            self._refresh_status()
            self._refresh_cards()
        except Exception:
            pass
        self._remove_confirm_dialog.open = False
        self._page.update()