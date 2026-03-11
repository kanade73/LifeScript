"""Entry point: `python -m lifescript` or `lifescript` CLI command."""

from __future__ import annotations

import os

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    # Plugin auto-discovery (must happen before compiler/validator/runner use plugins)
    from .plugins import discover

    discover()

    from .compiler.compiler import Compiler
    from .scheduler.scheduler import LifeScriptScheduler
    import flet as ft
    from .ui.app import create_app

    # --- LLM compiler ---
    model = os.getenv("LITELLM_MODEL", "ollama/qwen2.5-coder:7b")
    api_base = os.getenv("LITELLM_API_BASE", "http://localhost:11434")
    compiler = Compiler(model=model, api_base=api_base)

    # --- Scheduler (DB connect + load is done after login in app.py) ---
    scheduler = LifeScriptScheduler(compiler=compiler)

    # --- Run UI ---
    ft.run(create_app(compiler=compiler, scheduler=scheduler))


if __name__ == "__main__":
    main()
