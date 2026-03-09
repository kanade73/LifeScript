"""Settings dialog - Miro-style pop design."""

from __future__ import annotations

import os
import threading

import flet as ft
from dotenv import set_key

from ..database.client import db_client
from ..plugins.line_plugin import line_plugin
from .app import COLORS

ENV_FILE = ".env"


def _env_path() -> str:
    return os.path.join(os.getcwd(), ENV_FILE)


class SettingsDialog:
    def __init__(self, page: ft.Page, compiler) -> None:
        self._page = page
        self._compiler = compiler
        self._status = ft.Text("", size=12)

        # ── LINE fields ─────────────────────────────────────────────
        self._line_token = ft.TextField(
            label="Channel Access Token",
            password=True,
            can_reveal_password=True,
            expand=True,
            border_radius=10,
            border_color="#E8E4DC",
            focused_border_color=COLORS["blue"],
        )
        self._line_user_id = ft.TextField(
            label="LINE User ID",
            hint_text="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            expand=True,
            border_radius=10,
            border_color="#E8E4DC",
            focused_border_color=COLORS["blue"],
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
                # LINE section
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.CHAT_ROUNDED,
                                    size=16,
                                    color=COLORS["card_bg"],
                                ),
                                width=28,
                                height=28,
                                bgcolor=COLORS["green"],
                                border_radius=8,
                                alignment=ft.alignment.center,
                            ),
                            ft.Text(
                                "LINE Messaging API",
                                weight=ft.FontWeight.W_700,
                                size=14,
                                color=COLORS["dark_text"],
                            ),
                        ],
                        spacing=8,
                    ),
                ),
                self._line_token,
                self._line_user_id,
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Connect",
                            icon=ft.Icons.LINK_ROUNDED,
                            bgcolor=COLORS["green"],
                            color=COLORS["card_bg"],
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=10),
                                elevation=0,
                            ),
                            on_click=self._connect_line,
                        ),
                        ft.OutlinedButton(
                            "Disconnect",
                            icon=ft.Icons.LINK_OFF_ROUNDED,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=10),
                                side=ft.BorderSide(1, COLORS["coral"]),
                                color=COLORS["coral"],
                            ),
                            on_click=self._disconnect_line,
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
                                alignment=ft.alignment.center,
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
                        alignment=ft.alignment.center,
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
        self._refresh_line_status()
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

    def _refresh_line_status(self) -> None:
        connected = line_plugin.check_connection()
        if connected:
            self._set_status("LINE: connected", COLORS["green"])
        else:
            self._set_status("LINE: not connected", COLORS["coral"])

    # ------------------------------------------------------------------
    # LINE
    # ------------------------------------------------------------------
    def _connect_line(self, e) -> None:
        token = self._line_token.value.strip()
        user_id = self._line_user_id.value.strip()
        threading.Thread(target=self._do_connect_line, args=(token, user_id), daemon=True).start()

    def _do_connect_line(self, token: str, user_id: str) -> None:
        if not token or not user_id:
            self._set_status("Token and User ID are required.", COLORS["coral"])
            return
        try:
            line_plugin.set_credentials(channel_token=token, user_id=user_id)
            db_client.save_connection("LINE", access_token=token, refresh_token=user_id)
            self._set_status("LINE connected!", COLORS["green"])
        except Exception as ex:
            self._set_status(f"LINE error: {ex}", COLORS["coral"])

    def _disconnect_line(self, e) -> None:
        threading.Thread(target=self._do_disconnect_line, daemon=True).start()

    def _do_disconnect_line(self) -> None:
        try:
            line_plugin.clear_credentials()
            db_client.delete_connection("LINE")
            self._set_status("LINE disconnected.", COLORS["yellow"])
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
