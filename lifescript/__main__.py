"""エントリポイント: `python -m lifescript` で起動。"""

from __future__ import annotations

import os

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    from .compiler.compiler import Compiler
    from .scheduler.scheduler import LifeScriptScheduler
    from .api import start_api_server
    import flet as ft
    from .ui.app import create_app

    # --- LLM compiler ---
    model = os.getenv("LIFESCRIPT_MODEL", os.getenv("LITELLM_MODEL", "gemini/gemini-2.5-flash"))
    api_base = os.getenv("LITELLM_API_BASE", "")
    compiler = Compiler(model=model, api_base=api_base if api_base else None)

    # --- Scheduler ---
    scheduler = LifeScriptScheduler(compiler=compiler)

    # --- REST API (iOS向け) ---
    api_port = int(os.getenv("API_PORT", "8000"))
    start_api_server(compiler, port=api_port)

    # --- Run UI ---
    ft.run(create_app(compiler=compiler, scheduler=scheduler))


if __name__ == "__main__":
    main()
