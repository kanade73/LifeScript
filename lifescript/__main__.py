"""Entry point: `python -m lifescript` or `lifescript` CLI command."""

from __future__ import annotations

import os

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    from .compiler.compiler import Compiler
    from .database.client import db_client
    from .plugins.line_plugin import line_plugin
    from .scheduler.scheduler import LifeScriptScheduler
    import flet as ft
    from .ui.app import create_app

    # --- Database (SQLite, auto-created) ---
    db_client.connect()

    # --- LINE credentials ---
    try:
        conn = db_client.get_connection("LINE")
        if conn:
            line_plugin.set_credentials(
                channel_token=conn["access_token"],
                user_id=conn["refresh_token"],
            )
    except Exception:
        pass

    # --- LLM compiler ---
    model = os.getenv("LITELLM_MODEL", "ollama/qwen2.5-coder:7b")
    api_base = os.getenv("LITELLM_API_BASE", "http://localhost:11434")
    compiler = Compiler(model=model, api_base=api_base)

    # --- Scheduler ---
    scheduler = LifeScriptScheduler(compiler=compiler)
    scheduler.start()
    scheduler.load_from_db()

    # --- Run UI ---
    ft.app(target=create_app(compiler=compiler, scheduler=scheduler))


if __name__ == "__main__":
    main()
