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
    from .ui.app import LifeScriptApp

    # --- Supabase ---
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_ANON_KEY", "")
    if supabase_url and supabase_key:
        try:
            db_client.connect(supabase_url, supabase_key)
        except Exception as e:
            print(f"[WARN] Could not connect to Supabase: {e}")

    # --- LINE credentials ---
    if db_client.is_connected:
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
    model = os.getenv("LITELLM_MODEL", "gpt-4o-mini")
    api_base = os.getenv("LITELLM_API_BASE") or None
    compiler = Compiler(model=model, api_base=api_base)

    # --- Scheduler ---
    scheduler = LifeScriptScheduler(compiler=compiler)
    scheduler.start()
    if db_client.is_connected:
        scheduler.load_from_db()

    # --- Run UI ---
    app = LifeScriptApp(compiler=compiler, scheduler=scheduler)
    app.run()


if __name__ == "__main__":
    main()
