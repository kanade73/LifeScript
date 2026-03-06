# LifeScript

**「暮らしにコードを書け」**

LifeScript is a DSL (Domain Specific Language) that sits between natural language and Python.
You describe your *intent* in LifeScript, an LLM compiles it to Python, and it acts on your life through real APIs.

```
Natural language (intent) → LifeScript (description) → Python (execution) → API (real-world effect)
```

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- A Supabase project (free tier works)
- An LLM API key (OpenAI) **or** a local Ollama instance

### 2. Install

```bash
git clone https://github.com/your-org/lifescript.git
cd lifescript
uv sync
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your Supabase URL, Anon Key, and OpenAI API key
```

### 4. Set up the database

Run `schema.sql` in the **Supabase SQL Editor** (Dashboard → SQL Editor → New query).

### 5. Run

```bash
uv run lifescript
```

Or directly:

```bash
uv run python -m lifescript
```

---

## LifeScript Syntax

```javascript
// Send a LINE message every morning at 8:00
every day {
  when fetch(time.now) == "08:00" {
    notify(LINE, "おはようございます")
  }
}

// Hourly reminder
every 1h {
  notify(LINE, "1時間が経過しました")
}

// Variable and condition
let now = fetch(time.now)
if now >= "09:00" and now <= "18:00" {
  notify(LINE, "勤務時間内です")
}

// Repeat
repeat 3 {
  notify(LINE, "ping")
}
```

### Keywords

| Keyword | Description |
|---|---|
| `every day / Nh / Nm` | Periodic trigger |
| `when <cond> { }` | Conditional block |
| `fetch(time.now)` | Current time as `"HH:MM"` |
| `fetch(time.today)` | Today's weekday and date |
| `notify(LINE, "msg")` | Send LINE message |
| `let x = expr` | Variable definition |
| `if / else` | Conditional |
| `repeat N { }` | Loop N times |

---

## Architecture

```
[Textual TUI]
  ↓ LifeScript code
[Compiler] → LiteLLM → [LLM] → Python
  ↓
[Validator] (AST whitelist check)
  ↓
[Supabase] (rule storage)
  ↓
[APScheduler] (background jobs)
  ↓
[RestrictedPython sandbox]
  ↓
[Plugins: time_plugin, line_plugin]
  ↓
[LINE Messaging API]
```

**LLM is called only at compile time and on runtime errors** — token cost is minimised.

### Project layout

```
lifescript/
├── compiler/       # LLM-based LifeScript→Python compiler + AST validator
├── database/       # Supabase client (in-memory fallback if unconfigured)
├── plugins/        # time_plugin, line_plugin (extend by adding files here)
├── sandbox/        # RestrictedPython execution environment
├── scheduler/      # APScheduler job manager
└── ui/             # Textual TUI (main_screen, settings_screen)
```

---

## Settings (in-app)

Press **⚙ Settings** in the UI to configure:

- **Supabase** — URL + Anon Key
- **LINE Messaging API** — Channel Access Token + LINE User ID
- **LLM** — model name (e.g. `gpt-4o-mini`, `ollama/qwen2.5-coder:7b`) and optional API base URL

Settings are persisted to `.env`.

---

## LINE Setup

1. Create a **Messaging API channel** at [LINE Developers](https://developers.line.biz/).
2. Issue a **Channel Access Token** (long-lived) from the channel console.
3. Get your **LINE User ID** from the channel console → Basic Settings → Your user ID.
4. Enter both in the Settings screen.

---

## Local LLM (Ollama)

```bash
ollama pull qwen2.5-coder:7b
# In .env:
LITELLM_MODEL=ollama/qwen2.5-coder:7b
LITELLM_API_BASE=http://localhost:11434
```

---

## Development

```bash
uv sync --group dev   # install dev dependencies
uv run ruff check .   # lint
uv run ruff format .  # format
uv run pytest         # tests
```

---

## Adding a Plugin

1. Create `lifescript/plugins/my_plugin.py` implementing the `Plugin` base class.
2. Expose a top-level function (e.g. `def notify_slack(message: str) -> None`).
3. Add the function name to `ALLOWED_CALLS` in `compiler/validator.py`.
4. Add the function to the sandbox globals in `sandbox/runner.py`.
5. Update the LLM system prompt in `compiler/compiler.py`.

---

## License

MIT © 2026 kanade

git add (ファイル名)
ステージング

git commit -m (何かしらのコメント)
これが変更を保存するやつ（ローカルに）

git push
これをしてようやくGitHubのサイトに反映される

git branch
今いるブランチと今あるブランチがわかる

git checkout -b (ブランチ名)
新しいブランチを作ってここに移動する(-b)

git checkout (ブランチ名)
このブランチ名のブランチに移動する

git add .