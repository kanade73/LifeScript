# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                   # install all dependencies
uv sync --group dev       # install with dev dependencies
uv run lifescript         # start the app
uv run python -m lifescript  # equivalent

uv run ruff check .       # lint
uv run ruff format .      # format
uv run pytest             # run tests
```

## Architecture

LifeScript is a desktop GUI app (Flet) that compiles a custom DSL into Python automation.

**Flow:**
```
LifeScript code (user input)
  → Compiler (LiteLLM → LLM) → Python code
  → Validator (AST whitelist check)
  → Supabase (rule storage)
  → APScheduler (background polling jobs)
  → RestrictedPython sandbox
  → Plugins (time_plugin, line_plugin)
  → LINE Messaging API
```

**LLM is called only at compile time and on runtime errors.**

### Key modules

| Module | Responsibility |
|---|---|
| `compiler/compiler.py` | Sends LifeScript + system prompt to LLM via LiteLLM; parses JSON response |
| `compiler/validator.py` | AST-based whitelist check on generated Python (no imports, no attribute calls) |
| `sandbox/runner.py` | Executes generated Python with RestrictedPython; only plugin functions are in scope |
| `scheduler/scheduler.py` | APScheduler BackgroundScheduler; registers/removes jobs; calls `_try_recompile` on errors |
| `database/client.py` | SQLite client (~/.lifescript/lifescript.db); singleton `db_client` |
| `plugins/time_plugin.py` | `fetch_time_now()`, `fetch_time_today()` — no external dependency |
| `plugins/line_plugin.py` | `notify_line(msg)` — requires LINE Channel Access Token + User ID in `connections` |
| `ui/app.py` | Flet app entry; Miro-inspired layout with activity bar + content area + status bar |
| `ui/main_screen.py` | `EditorView` — code editor (dark), rules sidebar, action toolbar, log panel |
| `ui/dashboard_view.py` | `DashboardView` — status cards, rule cards grid, live log panel |
| `ui/settings_screen.py` | LINE / LLM config dialog; persists to `.env` via `python-dotenv` |
| `log_queue.py` | Thread-safe deque; scheduler writes logs, Flet UI polls with `threading.Timer(1.0)` |

### Startup sequence (`__main__.py`)

1. Load `.env`
2. Connect to SQLite (auto-created at ~/.lifescript/lifescript.db)
3. Load LINE credentials from `connections` table
4. Create `Compiler(model, api_base)`
5. Create and `start()` `LifeScriptScheduler`; `load_from_db()`
6. Run Flet app via `ft.app(target=create_app(...))`

### Adding a plugin

1. Add `lifescript/plugins/my_plugin.py` extending `Plugin`.
2. Add the exposed function name to `ALLOWED_CALLS` in `compiler/validator.py`.
3. Add the function to `_build_globals()` in `sandbox/runner.py`.
4. Add the function to the system prompt in `compiler/compiler.py`.

## Tech stack

- **UI**: Flet (desktop GUI, Miro-inspired pop design)
- **LLM client**: LiteLLM (model-agnostic; OpenAI or Ollama)
- **Scheduler**: APScheduler 3.x BackgroundScheduler
- **Sandbox**: RestrictedPython
- **DB**: SQLite (~/.lifescript/lifescript.db)
- **Notifications**: LINE Messaging API (push)
- **Package manager**: uv

## Environment variables

See `.env.example`. Key vars: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `LITELLM_MODEL`, `LITELLM_API_BASE`, `OPENAI_API_KEY`.
