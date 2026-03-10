"""Home view - stylish notification feed and activity timeline."""

from __future__ import annotations

from datetime import datetime

import flet as ft

from ..database.client import db_client
from .app import COLORS

# ── Home-specific palette (richer, more consumer-facing) ──────────
_HOME_BG = "#F7F5F0"
_CARD_GRADIENT_START = "#FFFFFF"
_CARD_GRADIENT_END = "#FDFCFA"
_ACCENT_WARM = "#FF9F43"
_ACCENT_MINT = "#00D2D3"
_ACCENT_LAVENDER = "#A29BFE"
_ACCENT_ROSE = "#FD79A8"
_SUBTLE_BORDER = "#EDE8E0"
_TIME_COLOR = "#B8B0A4"


def _time_ago(iso_str: str) -> str:
    """Convert an ISO timestamp to a human-friendly relative time."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "たった今"
        if seconds < 3600:
            return f"{seconds // 60}分前"
        if seconds < 86400:
            return f"{seconds // 3600}時間前"
        return f"{seconds // 86400}日前"
    except Exception:
        return ""


def _pick_accent(index: int) -> str:
    """Cycle through accent colors for visual variety."""
    accents = [_ACCENT_WARM, _ACCENT_MINT, _ACCENT_LAVENDER, _ACCENT_ROSE]
    return accents[index % len(accents)]


def _pick_icon(result: str) -> tuple[str, str]:
    """Return (icon_name, color) based on log result."""
    if result == "error":
        return ft.Icons.ERROR_OUTLINE_ROUNDED, COLORS["coral"]
    if result == "warning":
        return ft.Icons.WARNING_AMBER_ROUNDED, COLORS["yellow"]
    return ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, COLORS["green"]


class HomeView:
    def __init__(self, page: ft.Page, scheduler) -> None:
        self._page = page
        self._scheduler = scheduler

        # ── Header ────────────────────────────────────────────────
        greeting = self._get_greeting()

        header = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        greeting,
                        size=28,
                        weight=ft.FontWeight.W_800,
                        color=COLORS["dark_text"],
                    ),
                    ft.Text(
                        "LifeScript が暮らしを動かしています",
                        size=14,
                        color=COLORS["mid_text"],
                        weight=ft.FontWeight.W_400,
                    ),
                ],
                spacing=4,
            ),
            padding=ft.padding.only(bottom=8),
        )

        # ── Summary chips ─────────────────────────────────────────
        self._active_chip = self._summary_chip(
            ft.Icons.BOLT_ROUNDED, "0 ルール稼働中", _ACCENT_WARM
        )
        self._db_chip = self._summary_chip(ft.Icons.CLOUD_OUTLINED, "未接続", _ACCENT_MINT)
        self._scheduler_chip = self._summary_chip(
            ft.Icons.TIMER_OUTLINED, "停止中", _ACCENT_LAVENDER
        )

        chips_row = ft.Row(
            [self._active_chip, self._db_chip, self._scheduler_chip],
            spacing=10,
        )

        # ── Activity feed ─────────────────────────────────────────
        self._feed = ft.ListView(
            expand=True,
            spacing=8,
            padding=ft.padding.only(right=4),
        )

        feed_section = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.NOTIFICATIONS_NONE_ROUNDED,
                                    size=18,
                                    color=_ACCENT_WARM,
                                ),
                                width=32,
                                height=32,
                                bgcolor="#FFF5EB",
                                border_radius=10,
                                alignment=ft.Alignment(0, 0),
                            ),
                            ft.Text(
                                "アクティビティ",
                                size=16,
                                weight=ft.FontWeight.W_700,
                                color=COLORS["dark_text"],
                            ),
                            ft.Container(expand=True),
                            ft.TextButton(
                                "すべて消去",
                                style=ft.ButtonStyle(
                                    color=COLORS["light_text"],
                                    padding=ft.padding.symmetric(horizontal=8),
                                ),
                                on_click=self._clear_feed,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(
                        content=self._feed,
                        expand=True,
                        border_radius=16,
                    ),
                ],
                spacing=12,
                expand=True,
            ),
            expand=True,
        )

        self._content = ft.Column(
            [header, chips_row, feed_section],
            expand=True,
            spacing=16,
        )

        self._refresh_chips()
        self._load_recent_logs()

    def build(self) -> ft.Column:
        return self._content

    # ------------------------------------------------------------------
    # Greeting
    # ------------------------------------------------------------------
    @staticmethod
    def _get_greeting() -> str:
        hour = datetime.now().hour
        if hour < 6:
            return "おやすみなさい"
        if hour < 12:
            return "おはようございます"
        if hour < 18:
            return "こんにちは"
        return "こんばんは"

    # ------------------------------------------------------------------
    # Summary chips
    # ------------------------------------------------------------------
    @staticmethod
    def _summary_chip(icon: str, label: str, accent: str) -> ft.Container:
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(icon, size=16, color=accent),
                        width=30,
                        height=30,
                        bgcolor=f"{accent}18",
                        border_radius=10,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(
                        label,
                        size=13,
                        weight=ft.FontWeight.W_600,
                        color=COLORS["dark_text"],
                    ),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=COLORS["card_bg"],
            border_radius=14,
            padding=ft.padding.symmetric(horizontal=14, vertical=10),
            border=ft.border.all(1, _SUBTLE_BORDER),
            expand=True,
        )

    def _refresh_chips(self) -> None:
        # Active rules
        try:
            active_ids = self._scheduler.get_active_ids()
            label_ctrl = self._active_chip.content.controls[1]
            label_ctrl.value = f"{len(active_ids)} ルール稼働中"
        except Exception:
            pass

        # Database
        label_ctrl2 = self._db_chip.content.controls[1]
        if db_client.is_supabase:
            label_ctrl2.value = "Supabase 接続中"
        elif db_client.is_connected:
            label_ctrl2.value = "SQLite (ローカル)"
        else:
            label_ctrl2.value = "未接続"

        # Scheduler
        label_ctrl3 = self._scheduler_chip.content.controls[1]
        label_ctrl3.value = "スケジューラ稼働中" if self._scheduler.is_running else "停止中"

    # ------------------------------------------------------------------
    # Feed
    # ------------------------------------------------------------------
    def _load_recent_logs(self) -> None:
        """Load recent logs from DB into the feed."""
        try:
            logs = db_client.get_logs(limit=30)
            if not logs:
                self._feed.controls.append(self._empty_state())
                return
            for i, log_entry in enumerate(logs):
                self._feed.controls.append(self._feed_card(log_entry, i))
        except Exception:
            self._feed.controls.append(self._empty_state())

    def _empty_state(self) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(
                        ft.Icons.INBOX_ROUNDED,
                        size=48,
                        color=COLORS["light_text"],
                    ),
                    ft.Text(
                        "まだ通知はありません",
                        size=14,
                        color=COLORS["light_text"],
                        weight=ft.FontWeight.W_500,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "エディタでルールを作成すると、ここに実行結果が表示されます",
                        size=12,
                        color=COLORS["light_text"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
            alignment=ft.Alignment(0, 0),
            padding=ft.padding.symmetric(vertical=60),
        )

    @staticmethod
    def _feed_card(log_entry: dict, index: int) -> ft.Container:
        result = log_entry.get("result", "success")
        icon_name, icon_color = _pick_icon(result)
        message = log_entry.get("message", "")
        time_str = log_entry.get("executed_at", "")
        error_msg = log_entry.get("error_message", "")
        relative_time = _time_ago(time_str)

        content_items = [
            ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(icon_name, size=18, color=icon_color),
                        width=34,
                        height=34,
                        bgcolor=f"{icon_color}14",
                        border_radius=10,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        [
                            ft.Text(
                                message if message else "(empty)",
                                size=14,
                                weight=ft.FontWeight.W_600,
                                color=COLORS["dark_text"],
                            ),
                            ft.Text(
                                relative_time,
                                size=11,
                                color=_TIME_COLOR,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text(
                            result,
                            size=10,
                            weight=ft.FontWeight.W_600,
                            color=icon_color,
                        ),
                        bgcolor=f"{icon_color}14",
                        border_radius=8,
                        padding=ft.padding.symmetric(horizontal=8, vertical=3),
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ]

        if error_msg:
            content_items.append(
                ft.Container(
                    content=ft.Text(
                        error_msg,
                        size=11,
                        color=COLORS["coral"],
                        selectable=True,
                    ),
                    bgcolor=f"{COLORS['coral']}0A",
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    margin=ft.margin.only(left=46),
                )
            )

        return ft.Container(
            content=ft.Column(content_items, spacing=6),
            bgcolor=COLORS["card_bg"],
            border_radius=14,
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            border=ft.border.all(1, _SUBTLE_BORDER),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    # ------------------------------------------------------------------
    # Log receiving (from poll)
    # ------------------------------------------------------------------
    def receive_logs(self, entries: list[str]) -> None:
        """Receive raw log strings from the central poller and add to feed."""
        # Remove empty state if present
        if (
            self._feed.controls
            and len(self._feed.controls) == 1
            and isinstance(self._feed.controls[0].content, ft.Column)
        ):
            first_col = self._feed.controls[0].content
            if first_col.controls and isinstance(first_col.controls[0], ft.Icon):
                self._feed.controls.clear()

        for entry in entries:
            result = "success"
            icon_color = COLORS["green"]
            icon_name = ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
            if "ERROR" in entry:
                result = "error"
                icon_color = COLORS["coral"]
                icon_name = ft.Icons.ERROR_OUTLINE_ROUNDED
            elif "WARN" in entry:
                result = "warning"
                icon_color = COLORS["yellow"]
                icon_name = ft.Icons.WARNING_AMBER_ROUNDED

            card = ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Container(
                                    content=ft.Icon(icon_name, size=18, color=icon_color),
                                    width=34,
                                    height=34,
                                    bgcolor=f"{icon_color}14",
                                    border_radius=10,
                                    alignment=ft.Alignment(0, 0),
                                ),
                                ft.Column(
                                    [
                                        ft.Text(
                                            entry,
                                            size=13,
                                            weight=ft.FontWeight.W_500,
                                            color=COLORS["dark_text"],
                                        ),
                                        ft.Text(
                                            "たった今",
                                            size=11,
                                            color=_TIME_COLOR,
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        result,
                                        size=10,
                                        weight=ft.FontWeight.W_600,
                                        color=icon_color,
                                    ),
                                    bgcolor=f"{icon_color}14",
                                    border_radius=8,
                                    padding=ft.padding.symmetric(horizontal=8, vertical=3),
                                ),
                            ],
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=6,
                ),
                bgcolor=COLORS["card_bg"],
                border_radius=14,
                padding=ft.padding.symmetric(horizontal=16, vertical=12),
                border=ft.border.all(1, _SUBTLE_BORDER),
            )
            # Insert at top (newest first)
            self._feed.controls.insert(0, card)

        # Keep feed manageable
        if len(self._feed.controls) > 200:
            self._feed.controls = self._feed.controls[:200]

        self._refresh_chips()
        self._page.update()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _clear_feed(self, e) -> None:
        self._feed.controls.clear()
        self._feed.controls.append(self._empty_state())
        self._page.update()
