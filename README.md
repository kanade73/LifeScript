# LifeScript

**「暮らしをHackせよ！」**

<!-- ホーム画面のスクリーンショットをここにドラッグ&ドロップ -->
![LifeScript Home](https://github.com/user-attachments/assets/placeholder)

LifeScript は、あなたの生活文脈を理解して能動的に動く"相棒"—— **ダリー** を育てるためのDSL（ドメイン固有言語）です。

ユーザーはルールを書くのではなく、**自分の文脈**をダリーに伝えるだけ。ダリーはカレンダーや通知を通じて、ユーザーが設定していない行動まで提案・実行します。

```
リマインドアプリ   → 人間がルールを考えて、アプリが実行する
LifeScript        → 人間が「自分の文脈」を渡すと、ダリーが判断して動く
```

---

## 特徴

- **コンパイル時のみLLM使用** — 実行時はPythonを直接実行するためコストゼロ
- **2層セキュリティ** — AST静的解析 + RestrictedPython サンドボックス
- **デュアルDB** — Supabase（クラウド）/ SQLite（オフライン）を自動切替
- **関数ライブラリ拡張 = ロードマップ** — 関数が増えるほどDSLの表現力が上がる
- **iOS + PC 対応** — SwiftUI ネイティブアプリ + Flet デスクトップアプリ

---

## アーキテクチャ

```
┌──────────────┐    REST API     ┌───────────────────────────┐
│  iOS App     │ ◄─────────────► │  Python Backend           │
│  (SwiftUI)   │                 │                           │
└──────┬───────┘                 │  Compiler  (LiteLLM/Gemini)│
       │                         │  Validator (RestrictedPython)│
       │  Supabase               │  Scheduler (APScheduler)   │
       │  (直接CRUD)             │  Sandbox   (RestrictedPython)│
       ▼                         │  Gmail API (OAuth 2.0)     │
┌──────────────┐                 └────────────┬──────────────┘
│  Supabase    │ ◄────────────────────────────┘
│  (PostgreSQL) │
└──────────────┘
┌───────────────────────────┐
│  Flet Desktop App (PC)    │  ← デモ・開発用
│  同一Pythonプロセス内で動作  │
└───────────────────────────┘
```

### 処理フロー

```
DSL入力 → Gemini でPythonに変換 → AST解析で安全性検証
→ RestrictedPython サンドボックスで実行 → APScheduler でジョブ登録
→ ダリーが能動的に提案・通知
```

---

## 技術スタック

| レイヤー | 技術 |
|---|---|
| iOS フロントエンド | SwiftUI, Supabase Swift SDK |
| PC フロントエンド | Flet (Material 3) |
| DSLコンパイル | LiteLLM → Gemini 2.5 Flash / Pro |
| セキュリティ | RestrictedPython, AST解析 (validator.py) |
| ジョブ実行 | APScheduler (cron / interval / once) |
| データベース | Supabase (PostgreSQL) / SQLite (ローカルフォールバック) |
| 認証 | Supabase Auth, Google OAuth 2.0 |
| 外部連携 | Gmail API, httpx |
| 配布 | PyInstaller (.app), Xcode (iOS) |

---

## DSL の書き方

LifeScript では自然言語に近い記法で生活ルールを記述できます。LLMがPythonに変換するため、厳密な構文を覚える必要はありません。

```yaml
# 自分の特性を定義（ダリーへの文脈提供）
traits:
  朝は弱い → notify() は 8:00 以降
  バイトの許容は週3まで

# カレンダーベースの自動化
when calendar.read("バイト").count_this_week >= 4:
  calendar.suggest("回復タイム", on="next_free_morning")

# 継続の見守り
when streak.count("運動") >= 7:
  machine.suggest("1週間継続！次の目標を設定しようか？")
```

### 利用可能な関数

| 関数 | 説明 |
|---|---|
| `notify(message, at?)` | 通知を送る（時刻指定可） |
| `calendar.add(title, start, end?, note?)` | カレンダーにイベント追加 |
| `calendar.read(keyword?, range?)` | イベントを検索・取得 |
| `calendar.suggest(title, on, note?)` | イベントを提案 |
| `gmail.unread(limit?)` | 未読メールを取得 |
| `gmail.search(query, limit?)` | メールを検索 |
| `gmail.summarize(limit?)` | 未読メールをAI要約 |
| `gmail.send(to, subject, body)` | メールを送信 |
| `web.fetch(url)` | Webページを取得・要約 |

---

## セットアップ

### 必要なもの

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Supabase プロジェクト（無料枠で可）
- Gemini API キー（Google AI Studio 無料枠で可）

### インストール

```bash
git clone https://github.com/kanade73/LifeScript.git
cd LifeScript
uv sync
```

### 環境設定

```bash
cp .env.example .env
# .env を編集して各種APIキーを設定
```

```bash
# .env の主要項目
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
LIFESCRIPT_MODEL=gemini/gemini-2.5-flash
GEMINI_API_KEY=your-gemini-key
```

### 起動

```bash
uv run lifescript
```

### macOS アプリとしてビルド

```bash
pyinstaller LifeScript.spec --noconfirm
# → dist/LifeScript.app が生成される
```

---

## プロジェクト構成

```
lifescript/
├── compiler/          # DSL → Python コンパイラ（LLM使用）
│   ├── compiler.py    #   LiteLLM経由でGeminiを呼び出し
│   └── validator.py   #   AST解析によるホワイトリスト検証
├── sandbox/           # RestrictedPython 実行環境
│   └── runner.py      #   30秒タイムアウト、レート制限付き
├── scheduler/         # APScheduler ジョブ管理
│   └── scheduler.py   #   cron / interval / once トリガー
├── database/          # デュアルバックエンド DB
│   └── client.py      #   Supabase ↔ SQLite 自動切替
├── functions/         # DSLから呼べる関数ライブラリ
│   ├── calendar.py    #   カレンダー操作
│   ├── notify.py      #   通知
│   ├── gmail.py       #   Gmail連携
│   ├── web.py         #   Web取得・要約
│   └── widget.py      #   ホーム画面ウィジェット
├── ui/                # Flet デスクトップUI
│   ├── app.py         #   アプリケーションルート
│   ├── home_view.py   #   ホーム画面
│   ├── main_screen.py #   IDEエディタ
│   ├── dashboard_view.py
│   ├── concierge_view.py  # ダリーチャット
│   ├── reference_view.py  # 関数リファレンス
│   └── settings_view.py   # 設定（Google認証等）
├── auth.py            # Supabase 認証・セッション管理
├── google_auth.py     # Google OAuth 2.0
├── chat.py            # チャットエンジン（IDE / コンシェルジュ）
├── context_analyzer.py # 文脈分析・能動提案（3時間毎）
├── llm.py             # LLM呼び出しラッパー（リトライ+フォールバック）
├── traits.py          # ユーザー特性の抽出
└── api.py             # iOS向け REST API

ios/LifeScript/        # SwiftUI iOSアプリ
```

---

## 開発

```bash
uv sync --group dev
uv run ruff check .     # Lint
uv run ruff format .    # Format
uv run pytest           # Test
```

---

## Gmail 連携（オプション）

1. [Google Cloud Console](https://console.cloud.google.com/) でOAuth 2.0クライアントIDを作成
2. `credentials.json` を `~/.lifescript/google_credentials.json` に配置
3. アプリの設定画面から「Googleアカウントを連携」を実行

---

## ライセンス

MIT © 2026 kanade
