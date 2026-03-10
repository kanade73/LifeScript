"""Settings dialog - Miro-style pop design."""

from __future__ import annotations

import os
import threading

import flet as ft
from dotenv import set_key

from ..database.client import db_client
from .app import COLORS

ENV_FILE = ".env"


def _env_path() -> str:
    return os.path.join(os.getcwd(), ENV_FILE)


class SettingsDialog:
    def __init__(self, page: ft.Page, compiler) -> None:
        self._page = page
        self._compiler = compiler
        self._status = ft.Text("", size=12)

        # ── Supabase fields ──────────────────────────────────────────
        self._supabase_url = ft.TextField(
            value=os.getenv("SUPABASE_URL", ""),
            label="Supabase URL",
            hint_text="https://xxxxx.supabase.co",
            expand=True,
            border_radius=10,
            border_color="#E8E4DC",
            focused_border_color=COLORS["blue"],
        )
        self._supabase_key = ft.TextField(
            value=os.getenv("SUPABASE_ANON_KEY", ""),
            label="Anon Key",
            hint_text="eyJhbGci...",
            expand=True,
            border_radius=10,
            border_color="#E8E4DC",
            focused_border_color=COLORS["blue"],
            password=True,
            can_reveal_password=True,
        )

        # ── LLM fields ─────────────────────────────────────────────
        self._llm_model = ft.TextField(
            value=os.getenv("LITELLM_MODEL", "ollama/qwen2.5-coder:7b"),
            label="Model",
            hint_text="ollama/qwen2.5-coder:7b  or  gpt-4o-mini",
            expand=True,
            border_radius=10,
            border_color="#E8E4DC",
            focused_border_color=COLORS["blue"],
        )
        self._llm_api_base = ft.TextField(
            value=os.getenv("LITELLM_API_BASE", "http://localhost:11434"),
            label="API Base URL",
            hint_text="http://localhost:11434  (leave blank for OpenAI)",
            expand=True,
            border_radius=10,
            border_color="#E8E4DC",
            focused_border_color=COLORS["blue"],
        )

        content = ft.Column(
            [
                # Supabase section
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.CLOUD_ROUNDED,
                                    size=16,
                                    color=COLORS["card_bg"],
                                ),
                                width=28,
                                height=28,
                                bgcolor=COLORS["green"],
                                border_radius=8,
                                alignment=ft.Alignment(0, 0),
                            ),
                            ft.Text(
                                "Supabase",
                                weight=ft.FontWeight.W_700,
                                size=14,
                                color=COLORS["dark_text"],
                            ),
                        ],
                        spacing=8,
                    ),
                ),
                self._supabase_url,
                self._supabase_key,
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Save & Connect",
                            icon=ft.Icons.LINK_ROUNDED,
                            bgcolor=COLORS["green"],
                            color=COLORS["card_bg"],
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=10),
                                elevation=0,
                            ),
                            on_click=self._save_supabase,
                        ),
                    ],
                    spacing=8,
                ),
                ft.Divider(color="#E8E4DC"),
                # LLM section
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.AUTO_AWESOME_ROUNDED,
                                    size=16,
                                    color=COLORS["card_bg"],
                                ),
                                width=28,
                                height=28,
                                bgcolor=COLORS["purple"],
                                border_radius=8,
                                alignment=ft.Alignment(0, 0),
                            ),
                            ft.Text(
                                "LLM (via LiteLLM)",
                                weight=ft.FontWeight.W_700,
                                size=14,
                                color=COLORS["dark_text"],
                            ),
                        ],
                        spacing=8,
                    ),
                ),
                self._llm_model,
                self._llm_api_base,
                ft.ElevatedButton(
                    "Save LLM Settings",
                    icon=ft.Icons.SAVE_ROUNDED,
                    bgcolor=COLORS["blue"],
                    color=COLORS["card_bg"],
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        elevation=0,
                    ),
                    on_click=self._save_llm,
                ),
                ft.Divider(color="#E8E4DC"),
                self._status,
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )

        self._dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.SETTINGS_ROUNDED,
                            size=18,
                            color=COLORS["card_bg"],
                        ),
                        width=32,
                        height=32,
                        bgcolor=COLORS["yellow"],
                        border_radius=10,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text(
                        "Settings",
                        weight=ft.FontWeight.W_700,
                        size=18,
                        color=COLORS["dark_text"],
                    ),
                ],
                spacing=10,
            ),
            content=ft.Container(content=content, width=500, height=400),
            actions=[
                ft.TextButton(
                    "Close",
                    style=ft.ButtonStyle(color=COLORS["mid_text"]),
                    on_click=self._close,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=20),
        )

    def show(self) -> None:
        self._refresh_supabase_status()
        self._page.overlay.append(self._dlg)
        self._dlg.open = True
        self._page.update()

    def _close(self, e) -> None:
        self._dlg.open = False
        self._page.update()

    def _set_status(self, msg: str, color: str) -> None:
        self._status.value = msg
        self._status.color = color
        self._page.update()

    def _refresh_supabase_status(self) -> None:
        if db_client.is_supabase:
            self._set_status("Supabase: connected", COLORS["green"])
        elif db_client.is_connected:
            self._set_status("Database: SQLite (fallback)", COLORS["yellow"])
        else:
            self._set_status("Database: not connected", COLORS["coral"])

    # ------------------------------------------------------------------
    # Supabase
    # ------------------------------------------------------------------
    def _save_supabase(self, e) -> None:
        url = self._supabase_url.value.strip()
        key = self._supabase_key.value.strip()
        threading.Thread(target=self._do_save_supabase, args=(url, key), daemon=True).start()

    def _do_save_supabase(self, url: str, key: str) -> None:
        if not url or not key:
            self._set_status("URLとAnon Keyの両方を入力してください。", COLORS["coral"])
            return
        try:
            set_key(_env_path(), "SUPABASE_URL", url)
            set_key(_env_path(), "SUPABASE_ANON_KEY", key)
            os.environ["SUPABASE_URL"] = url
            os.environ["SUPABASE_ANON_KEY"] = key
            # Reconnect with new credentials
            db_client.connect()
            if db_client.is_supabase:
                self._set_status("Supabase connected!", COLORS["green"])
            else:
                self._set_status(
                    "接続に失敗しました。URLとKeyを確認してください。", COLORS["coral"]
                )
        except Exception as ex:
            self._set_status(f"Error: {ex}", COLORS["coral"])

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------
    def _save_llm(self, e) -> None:
        model = self._llm_model.value.strip()
        api_base = self._llm_api_base.value.strip()
        threading.Thread(target=self._do_save_llm, args=(model, api_base), daemon=True).start()

    def _do_save_llm(self, model: str, api_base: str) -> None:
        try:
            set_key(_env_path(), "LITELLM_MODEL", model)
            set_key(_env_path(), "LITELLM_API_BASE", api_base)
            self._compiler.model = model
            self._compiler.api_base = api_base or None
            self._set_status("LLM settings saved.", COLORS["green"])
        except Exception as ex:
            self._set_status(f"Error: {ex}", COLORS["coral"])
