"""Main editor screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    RichLog,
    Static,
    TextArea,
)
from textual import work

from ..compiler.compiler import Compiler
from ..database.client import db_client
from ..exceptions import CompileError
from .. import log_queue


class RuleItem(ListItem):
    def __init__(self, rule: dict) -> None:
        super().__init__()
        self.rule = rule

    def compose(self) -> ComposeResult:
        title = self.rule.get("title", "untitled")
        yield Label(f"● {title}", classes="rule-title")
        yield Button("✕", id=f"del_{self.rule['id']}", classes="rule-delete", variant="error")


class MainScreen(Screen):
    CSS = """
    MainScreen {
        layout: vertical;
    }

    #main-content {
        layout: horizontal;
        height: 1fr;
    }

    #editor-container {
        width: 2fr;
        border: solid $primary;
        padding: 0 1;
    }

    #editor-label {
        color: $accent;
        text-style: bold;
        padding: 0 0 1 0;
    }

    #editor {
        height: 1fr;
    }

    #rules-panel {
        width: 1fr;
        border: solid $accent;
        padding: 0 1;
    }

    #rules-label {
        color: $accent;
        text-style: bold;
        padding: 0 0 1 0;
    }

    #rules-list {
        height: 1fr;
    }

    RuleItem {
        layout: horizontal;
        height: 3;
        padding: 0 1;
    }

    .rule-title {
        width: 1fr;
        content-align: left middle;
        height: 100%;
    }

    .rule-delete {
        width: 5;
        min-width: 5;
    }

    #action-bar {
        height: 5;
        layout: horizontal;
        align: center middle;
        padding: 0 1;
        border-top: solid $primary;
    }

    #action-bar Button {
        margin: 0 1;
    }

    #log-panel {
        height: 10;
        border-top: solid $success;
    }

    #log-label {
        color: $success;
        text-style: bold;
        padding: 0 1;
    }
    """

    def __init__(self, compiler: Compiler, scheduler) -> None:
        super().__init__()
        self._compiler = compiler
        self._scheduler = scheduler
        self._loaded_rule_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-content"):
            with Vertical(id="editor-container"):
                yield Label("LifeScript Editor", id="editor-label")
                yield TextArea(
                    text=self._default_code(),
                    id="editor",
                    language="javascript",
                    show_line_numbers=True,
                )
            with Vertical(id="rules-panel"):
                yield Label("Active Rules", id="rules-label")
                yield ListView(id="rules-list")
        with Horizontal(id="action-bar"):
            yield Button("⚡ Compile & Save", id="btn-compile", variant="primary")
            yield Button("▶ Run All", id="btn-run", variant="success")
            yield Button("■ Stop All", id="btn-stop", variant="warning")
            yield Button("⚙ Settings", id="btn-settings")
        with Vertical():
            yield Label("Logs", id="log-label")
            yield RichLog(id="log-panel", highlight=True, markup=True)
        yield Footer()

    def _default_code(self) -> str:
        return (
            "// 例: 毎朝8時にLINE通知\n"
            "every day {\n"
            '  when fetch(time.now) == "08:00" {\n'
            '    notify(LINE, "おはようございます")\n'
            "  }\n"
            "}\n"
        )

    def on_mount(self) -> None:
        self._load_rules_list()
        self.set_interval(1.0, self._poll_logs)

    def _load_rules_list(self) -> None:
        rules_list = self.query_one("#rules-list", ListView)
        rules_list.clear()
        try:
            rules = db_client.get_rules()
            for rule in rules:
                rules_list.append(RuleItem(rule))
        except Exception as e:
            self._write_log(f"[red]Failed to load rules: {e}[/red]")

    def _poll_logs(self) -> None:
        entries = log_queue.drain()
        if entries:
            log_panel = self.query_one("#log-panel", RichLog)
            for entry in entries:
                color = "red" if "ERROR" in entry else "yellow" if "WARN" in entry else "green"
                log_panel.write(f"[{color}]{entry}[/{color}]")

    def _write_log(self, message: str) -> None:
        log_panel = self.query_one("#log-panel", RichLog)
        log_panel.write(message)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        if btn_id == "btn-compile":
            # Extract widget value on the main thread before handing off to a worker
            code = self.query_one("#editor", TextArea).text.strip()
            self._compile_and_save(code)
        elif btn_id == "btn-run":
            self._run_all()
        elif btn_id == "btn-stop":
            self._stop_all()
        elif btn_id == "btn-settings":
            self.app.push_screen("settings")
        elif btn_id and btn_id.startswith("del_"):
            rule_id = btn_id[4:]
            self._delete_rule(rule_id)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, RuleItem):
            rule = event.item.rule
            editor = self.query_one("#editor", TextArea)
            editor.load_text(rule.get("lifescript_code", ""))
            self._loaded_rule_id = str(rule["id"])
            self._write_log(f"[cyan]Loaded rule: {rule.get('title')}[/cyan]")

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------
    @work(thread=True)
    def _compile_and_save(self, code: str) -> None:
        if not code:
            self.app.call_from_thread(self._write_log, "[yellow]Editor is empty.[/yellow]")
            return

        self.app.call_from_thread(self._write_log, "[cyan]Compiling…[/cyan]")
        try:
            result = self._compiler.compile(code)
        except CompileError as e:
            self.app.call_from_thread(self._write_log, f"[red]Compile error: {e}[/red]")
            return

        try:
            rule = db_client.save_rule(
                title=result["title"],
                lifescript_code=code,
                compiled_python=result["code"],
                trigger_seconds=int(result["trigger"]["seconds"]),
            )
            self._scheduler.add_rule(rule)
            self.app.call_from_thread(
                self._write_log,
                f'[green]Compiled & saved: "{result["title"]}"[/green]',
            )
            self.app.call_from_thread(self._load_rules_list)
        except Exception as e:
            self.app.call_from_thread(self._write_log, f"[red]Save error: {e}[/red]")

    def _run_all(self) -> None:
        if not self._scheduler.is_running:
            self._scheduler.start()
            self._write_log("[green]Scheduler started.[/green]")
        else:
            self._write_log("[yellow]Scheduler is already running.[/yellow]")

    def _stop_all(self) -> None:
        self._scheduler.remove_all()
        self._write_log("[yellow]All jobs stopped.[/yellow]")

    @work(thread=True)
    def _delete_rule(self, rule_id: str) -> None:
        try:
            self._scheduler.remove_rule(rule_id)
            db_client.delete_rule(rule_id)
            self.app.call_from_thread(self._load_rules_list)
            self.app.call_from_thread(self._write_log, "[yellow]Rule deleted.[/yellow]")
        except Exception as e:
            self.app.call_from_thread(self._write_log, f"[red]Delete error: {e}[/red]")
