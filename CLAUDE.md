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
  → Compiler (LiteLLM → LLM, cached) → Python code
  → Validator (AST whitelist, auto-discovered from plugins)
  → SQLite (rule storage)
  → APScheduler (interval + cron triggers)
  → RestrictedPython sandbox (timeout + rate limit)
  → Plugins (auto-discovered: time, line, weather)
  → LINE Messaging API / wttr.in
```

**LLM is called only at compile time and on runtime errors.**

### Key modules

| Module | Responsibility |
|---|---|
| `compiler/compiler.py` | LLM compilation with dynamic system prompt, compile cache, Japanese errors |
| `compiler/validator.py` | AST whitelist auto-populated from plugin registry; blocks dangerous builtins |
| `sandbox/runner.py` | RestrictedPython with timeout (30s) and per-rule rate limiting (60/min) |
| `scheduler/scheduler.py` | APScheduler with interval + cron triggers; pause/resume per rule |
| `database/client.py` | SQLite client with cron fields, rule status toggle, execution logs |
| `plugins/__init__.py` | Auto-discovery: scans plugin modules for `PLUGIN_EXPORTS` at startup |
| `plugins/time_plugin.py` | `fetch_time_now()`, `fetch_time_today()` |
| `plugins/line_plugin.py` | `notify_line(msg)` — requires LINE credentials |
| `plugins/weather_plugin.py` | `fetch_weather(city)` — uses wttr.in (no API key) |
| `ui/app.py` | Flet app entry; Miro-inspired layout with activity bar + content area + status bar |
| `ui/main_screen.py` | `EditorView` — code editor (dark), rules sidebar, action toolbar, log panel |
| `ui/dashboard_view.py` | `DashboardView` — status cards, rule cards grid, live log panel |
| `ui/settings_screen.py` | LINE / LLM config dialog; persists to `.env` via `python-dotenv` |
| `log_queue.py` | Thread-safe deque; scheduler writes logs, Flet UI polls with `threading.Timer(1.0)` |

### Startup sequence (`__main__.py`)

1. Load `.env`
2. Auto-discover plugins (`plugins.discover()`)
3. Connect to SQLite (auto-created at ~/.lifescript/lifescript.db)
4. Load LINE credentials from `connections` table
4. Create `Compiler(model, api_base)`
5. Create and `start()` `LifeScriptScheduler`; `load_from_db()`
6. Run Flet app via `ft.app(target=create_app(...))`

### Adding a plugin

1. Create `lifescript/plugins/my_plugin.py`.
2. Define `PLUGIN_EXPORTS` list with `name`, `func`, `signature`, `description` for each function.
3. That's it — auto-discovery registers everything at startup (validator, sandbox, compiler prompt).

## Tech stack

- **UI**: Flet (desktop GUI, Miro-inspired pop design)
- **LLM client**: LiteLLM (model-agnostic; OpenAI or Ollama)
- **Scheduler**: APScheduler 3.x BackgroundScheduler
- **Sandbox**: RestrictedPython
- **DB**: SQLite (~/.lifescript/lifescript.db)
- **Notifications**: LINE Messaging API (push)
- **Package manager**: uv

## Environment variables

See `.env.example`. Key vars: `LITELLM_MODEL`, `LITELLM_API_BASE`, `OPENAI_API_KEY`.
