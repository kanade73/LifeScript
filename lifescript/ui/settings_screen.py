"""Settings screen: Supabase, LINE, LLM configuration."""
from __future__ import annotations

import os

from dotenv import set_key
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static
from textual import work

from ..database.client import db_client
from ..plugins.line_plugin import line_plugin

ENV_FILE = ".env"


def _env_path() -> str:
    """Resolve .env path relative to the project root (cwd)."""
    return os.path.join(os.getcwd(), ENV_FILE)


class SettingsScreen(Screen):
    CSS = """
    SettingsScreen {
        layout: vertical;
        padding: 1 2;
    }

    .section-title {
        color: $accent;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }

    .section-box {
        border: solid $primary;
        padding: 1 2;
        margin-bottom: 1;
    }

    .field-label {
        margin-top: 1;
    }

    Input {
        margin-bottom: 1;
    }

    .btn-row {
        layout: horizontal;
        margin-top: 1;
    }

    .btn-row Button {
        margin-right: 1;
    }

    #status-line {
        color: $success;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # --- Supabase section ---
        yield Static("Supabase", classes="section-title")
        with Container(classes="section-box"):
            yield Label("Project URL", classes="field-label")
            yield Input(
                value=os.getenv("SUPABASE_URL", ""),
                placeholder="https://xxxx.supabase.co",
                id="supabase-url",
            )
            yield Label("Anon Key", classes="field-label")
            yield Input(
                value=os.getenv("SUPABASE_ANON_KEY", ""),
                placeholder="eyJ…",
                id="supabase-key",
                password=True,
            )
            with Container(classes="btn-row"):
                yield Button("Connect", id="btn-supabase-connect", variant="primary")

        # --- LINE section ---
        yield Static("LINE Messaging API", classes="section-title")
        with Container(classes="section-box"):
            yield Label("Channel Access Token", classes="field-label")
            yield Input(
                placeholder="Channel Access Token",
                id="line-token",
                password=True,
            )
            yield Label("Your LINE User ID  (starts with U…)", classes="field-label")
            yield Input(
                placeholder="Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                id="line-user-id",
            )
            with Container(classes="btn-row"):
                yield Button("Connect", id="btn-line-connect", variant="primary")
                yield Button("Disconnect", id="btn-line-disconnect", variant="error")

        # --- LLM section ---
        yield Static("LLM (via LiteLLM)", classes="section-title")
        with Container(classes="section-box"):
            yield Label("Model name  (e.g. gpt-4o-mini, ollama/qwen2.5-coder:7b)", classes="field-label")
            yield Input(
                value=os.getenv("LITELLM_MODEL", "gpt-4o-mini"),
                placeholder="gpt-4o-mini",
                id="llm-model",
            )
            yield Label("API Base URL  (leave blank for OpenAI default)", classes="field-label")
            yield Input(
                value=os.getenv("LITELLM_API_BASE", ""),
                placeholder="http://localhost:11434",
                id="llm-api-base",
            )
            with Container(classes="btn-row"):
                yield Button("Save LLM Settings", id="btn-llm-save", variant="primary")

        yield Static("", id="status-line")

        with Container(classes="btn-row"):
            yield Button("← Back", id="btn-back")

        yield Footer()

    def on_mount(self) -> None:
        self._refresh_line_status()

    def _set_status(self, message: str) -> None:
        self.query_one("#status-line", Static).update(message)

    def _refresh_line_status(self) -> None:
        connected = line_plugin.check_connection()
        status = "[green]LINE: connected[/green]" if connected else "[red]LINE: not connected[/red]"
        self._set_status(status)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-back":
            self.app.pop_screen()
        elif btn_id == "btn-supabase-connect":
            # Extract widget values on the main thread before handing off to a worker
            url = self.query_one("#supabase-url", Input).value.strip()
            key = self.query_one("#supabase-key", Input).value.strip()
            self._connect_supabase(url, key)
        elif btn_id == "btn-line-connect":
            token = self.query_one("#line-token", Input).value.strip()
            user_id = self.query_one("#line-user-id", Input).value.strip()
            self._connect_line(token, user_id)
        elif btn_id == "btn-line-disconnect":
            self._disconnect_line()
        elif btn_id == "btn-llm-save":
            model = self.query_one("#llm-model", Input).value.strip()
            api_base = self.query_one("#llm-api-base", Input).value.strip()
            self._save_llm(model, api_base)

    @work(thread=True)
    def _connect_supabase(self, url: str, key: str) -> None:
        if not url or not key:
            self.app.call_from_thread(self._set_status, "[red]URL and key are required.[/red]")
            return
        try:
            db_client.connect(url, key)
            env = _env_path()
            set_key(env, "SUPABASE_URL", url)
            set_key(env, "SUPABASE_ANON_KEY", key)
            self.app.call_from_thread(
                self._set_status, "[green]Supabase connected successfully![/green]"
            )
        except Exception as e:
            self.app.call_from_thread(self._set_status, f"[red]Supabase error: {e}[/red]")

    @work(thread=True)
    def _connect_line(self, token: str, user_id: str) -> None:
        if not token or not user_id:
            self.app.call_from_thread(
                self._set_status, "[red]Token and User ID are required.[/red]"
            )
            return
        try:
            line_plugin.set_credentials(channel_token=token, user_id=user_id)
            db_client.save_connection("LINE", access_token=token, refresh_token=user_id)
            self.app.call_from_thread(
                self._set_status, "[green]LINE connected successfully![/green]"
            )
        except Exception as e:
            self.app.call_from_thread(self._set_status, f"[red]LINE error: {e}[/red]")

    @work(thread=True)
    def _disconnect_line(self) -> None:
        try:
            line_plugin.clear_credentials()
            db_client.delete_connection("LINE")
            self.app.call_from_thread(self._set_status, "[yellow]LINE disconnected.[/yellow]")
        except Exception as e:
            self.app.call_from_thread(self._set_status, f"[red]Error: {e}[/red]")

    @work(thread=True)
    def _save_llm(self, model: str, api_base: str) -> None:
        try:
            env = _env_path()
            set_key(env, "LITELLM_MODEL", model)
            set_key(env, "LITELLM_API_BASE", api_base)
            self.app.compiler.model = model
            self.app.compiler.api_base = api_base or None
            self.app.call_from_thread(
                self._set_status, "[green]LLM settings saved.[/green]"
            )
        except Exception as e:
            self.app.call_from_thread(self._set_status, f"[red]Error saving LLM settings: {e}[/red]")
