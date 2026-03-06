"""Textual application entry point."""
from __future__ import annotations

from textual.app import App, ComposeResult

from ..compiler.compiler import Compiler
from ..scheduler.scheduler import LifeScriptScheduler
from .main_screen import MainScreen
from .settings_screen import SettingsScreen


class LifeScriptApp(App):
    TITLE = "LifeScript - 暮らしにコードを書け"
    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+s", "compile", "Compile & Save"),
    ]

    def __init__(self, compiler: Compiler, scheduler: LifeScriptScheduler) -> None:
        super().__init__()
        self.compiler = compiler
        self.scheduler = scheduler

    def on_mount(self) -> None:
        self.install_screen(SettingsScreen(), name="settings")
        self.push_screen(MainScreen(compiler=self.compiler, scheduler=self.scheduler))

    def action_compile(self) -> None:
        screen = self.screen
        if isinstance(screen, MainScreen):
            from textual.widgets import TextArea
            code = screen.query_one("#editor", TextArea).text.strip()
            screen._compile_and_save(code)

    def on_unmount(self) -> None:
        self.scheduler.stop()
