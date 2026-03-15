# LifeScript アーキテクチャガイド

プロジェクトの構造を理解するためのロードマップ。

---

## 全体像（データの流れ）

```
ユーザー
  │  LifeScript を書く
  ▼
┌─────────────────────────────────────────────────┐
│  UI 層 (lifescript/ui/)                          │
│  app.py → home_view / main_screen / dashboard   │
└──────────────┬──────────────────────────────────┘
               │ Compile & Save ボタン
               ▼
┌─────────────────────────────────────────────────┐
│  コンパイラ (lifescript/compiler/)                │
│  compiler.py: LLM に送信 → Python 生成           │
│  validator.py: AST で静的解析（セキュリティ第一層）│
└──────────────┬──────────────────────────────────┘
               │ 検証済み Python + trigger 情報
               ▼
┌─────────────────────────────────────────────────┐
│  データベース (lifescript/database/client.py)     │
│  rules テーブルに保存                             │
│  Supabase or SQLite                              │
└──────────────┬──────────────────────────────────┘
               │ ルール登録
               ▼
┌─────────────────────────────────────────────────┐
│  スケジューラ (lifescript/scheduler/scheduler.py) │
│  APScheduler で定期実行ジョブとして登録            │
└──────────────┬──────────────────────────────────┘
               │ trigger 発火
               ▼
┌─────────────────────────────────────────────────┐
│  サンドボックス (lifescript/sandbox/runner.py)    │
│  RestrictedPython で実行（セキュリティ第二層）      │
│  タイムアウト 30秒 / レートリミット 60回/分        │
└──────────────┬──────────────────────────────────┘
               │ プラグイン関数を呼び出す
               ▼
┌─────────────────────────────────────────────────┐
│  プラグイン (lifescript/plugins/)                 │
│  log() → DB に書き込み                            │
│  fetch_time_now() → "HH:MM"                     │
│  etc.                                            │
└──────────────┬──────────────────────────────────┘
               │ log_queue 経由
               ▼
┌─────────────────────────────────────────────────┐
│  UI に通知が表示される                            │
│  Home: オシャレなカードフィード                    │
│  Editor/Dashboard: ターミナル風ログ               │
└─────────────────────────────────────────────────┘
```

---

## 読む順番（推奨ロードマップ）

| 順番 | ファイル | なぜ先に読むか |
|------|----------|---------------|
| 1 | `CLAUDE.md` | プロダクトの全体仕様。言語仕様・アーキテクチャ・フェーズが全部書いてある |
| 2 | `lifescript/__main__.py` | アプリの起動順序がわかる（プラグイン検出 → コンパイラ → スケジューラ → UI） |
| 3 | `lifescript/plugins/base.py` → `time_plugin.py` → `log_plugin.py` | 一番シンプルなコード。プラグインの構造（Plugin 基底クラス + PLUGIN_EXPORTS）がわかる |
| 4 | `lifescript/plugins/__init__.py` | 自動検出の仕組み（pkgutil でモジュールを走査 → PLUGIN_EXPORTS を収集） |
| 5 | `lifescript/compiler/compiler.py` | LLM 呼び出しの核心。システムプロンプト → LLM → JSON パース → バリデーション |
| 6 | `lifescript/compiler/validator.py` | セキュリティ第一層。AST を歩いて禁止関数をブロック |
| 7 | `lifescript/sandbox/runner.py` | セキュリティ第二層。RestrictedPython + タイムアウト + レートリミット |
| 8 | `lifescript/database/client.py` | DB の読み書き。Supabase / SQLite 二重構造の Facade パターン |
| 9 | `lifescript/scheduler/scheduler.py` | ルールの定期実行。add_rule → APScheduler → _run_rule → サンドボックス |
| 10 | `lifescript/log_queue.py` | バックグラウンド → UI の橋渡し。たった 24 行なのですぐ読める |
| 11 | `lifescript/ui/app.py` | UI の骨格。ナビゲーション・ログポーリング・ステータスバー |
| 12 | `lifescript/ui/home_view.py` → `main_screen.py` → `dashboard_view.py` | 3 つの画面。好きな順で |

---

## ディレクトリ構造

```
lifescript/
├── __init__.py          # パッケージ宣言
├── __main__.py          # エントリポイント（python -m lifescript）
├── exceptions.py        # 全例外クラスの定義
├── log_queue.py         # スレッドセーフなログキュー（スケジューラ → UI）
│
├── auth/                # Supabase 認証（現在は開発モードでバイパス中）
│   ├── __init__.py
│   └── auth.py          # AuthClient: メール + パスワード認証
│
├── compiler/            # LifeScript → Python コンパイラ
│   ├── __init__.py
│   ├── compiler.py      # LLM 呼び出し・JSON パース・キャッシュ
│   └── validator.py     # AST ベースの静的解析（ホワイトリスト検証）
│
├── database/            # データベース層
│   ├── __init__.py
│   └── client.py        # DatabaseClient: Supabase / SQLite Facade
│
├── plugins/             # プラグイン（自動検出される）
│   ├── __init__.py      # 自動検出エンジン（discover / get_functions / get_descriptions）
│   ├── base.py          # Plugin 抽象基底クラス
│   ├── time_plugin.py   # fetch(time.now) / fetch(time.today)
│   ├── log_plugin.py    # log("message") → DB + UI
│   ├── math_plugin.py   # random_number() — サンプルプラグイン
│   ├── weather_plugin.py # fetch(weather.today) — 将来用
│   ├── discord_plugin.py # notify_discord() — 将来用
│   └── line_plugin.py   # notify_line() — 将来用
│
├── sandbox/             # サンドボックス実行環境
│   ├── __init__.py
│   └── runner.py        # RestrictedPython + タイムアウト + レートリミット
│
├── scheduler/           # ジョブスケジューラ
│   ├── __init__.py
│   └── scheduler.py     # APScheduler ベースの定期実行管理
│
└── ui/                  # Flet デスクトップ UI
    ├── __init__.py
    ├── app.py           # アプリ骨格（ナビ・ポーリング・ステータスバー）
    ├── home_view.py     # Home 画面（通知フィード — オシャレ）
    ├── main_screen.py   # Editor 画面（コード編集 — 開発感）
    ├── dashboard_view.py # Dashboard 画面（ステータス — 開発寄り）
    ├── settings_screen.py # 設定ダイアログ
    └── login_screen.py  # ログイン画面（現在バイパス中）
```

---

## 主要な設計パターン

### 1. シングルトン
`db_client`, `auth_client`, 各プラグインインスタンス — アプリ全体で1つのインスタンスを共有。

```python
# lifescript/database/client.py の末尾
db_client = DatabaseClient()  # これが全モジュールから import される
```

### 2. Facade パターン
`DatabaseClient` が `_SupabaseBackend` と `_SQLiteBackend` を隠蔽。
呼び出し側は `db_client.save_rule()` だけで、裏側がどちらの DB かを意識しない。

```python
# 呼び出し側（scheduler.py や main_screen.py）は同じコード
db_client.save_rule(title=..., lifescript_code=..., compiled_python=...)
```

### 3. プラグイン自動検出
`PLUGIN_EXPORTS` リストを定義するだけで、以下すべてに自動反映される:
- コンパイラのシステムプロンプト（LLM が使える関数として認識）
- サンドボックスの実行環境（関数がグローバルに注入）
- バリデータのホワイトリスト（静的解析で許可）

```python
# 新しいプラグインを追加する手順:
# 1. lifescript/plugins/xxx_plugin.py を作成
# 2. PLUGIN_EXPORTS を定義
# 3. 終わり（他のファイルの変更は不要）
```

### 4. ログキューによる疎結合
スケジューラ（バックグラウンドスレッド）→ `log_queue` → UI ポーリング（1秒間隔）。
直接 UI を触らないのでスレッド安全。

```
[scheduler/runner] --log()--> [log_queue] --drain()--> [app.py ポーリング] --> [各画面の receive_logs()]
```

### 5. 二重セキュリティ
LLM が生成した Python を exec() する前に二重チェック:

| 層 | ファイル | タイミング | やること |
|----|----------|-----------|---------|
| 第一層 | `validator.py` | コンパイル時 | AST を歩いて import / exec / open 等をブロック |
| 第二層 | `runner.py` | 実行時 | RestrictedPython で実行、30秒タイムアウト、60回/分レートリミット |

---

## コンパイルフロー（詳細）

```
LifeScript コード
  │
  ▼  compiler.compile()
[1] SHA256 ハッシュでキャッシュチェック → ヒットならキャッシュ返却
  │
  ▼  キャッシュミス
[2] _build_system_prompt() でプラグイン一覧を含むシステムプロンプト生成
  │
  ▼
[3] LiteLLM 経由で LLM に送信（temperature=0.1 で確定的な出力を狙う）
  │
  ▼  LLM の応答（JSON 文字列）
[4] _parse_response() で JSON パース（コードフェンス除去対応）
  │
  ▼
[5] _validate_result() で必須フィールド確認 + trigger 正規化
  │
  ▼
[6] validate_python() で AST 静的解析（第一層セキュリティ）
  │
  ▼
[7] キャッシュに保存（最大128エントリ、LRU）
  │
  ▼
結果: {"title": "...", "trigger": {"seconds": 60}, "code": "..."}
```

---

## エラー時の再コンパイルフロー

```
[サンドボックス実行] → SandboxError 発生
  │
  ▼  scheduler._try_recompile()
[1] エラー内容 + 元の LifeScript + 生成済み Python を LLM に送信
  │
  ▼
[2] LLM が修正版 Python を生成
  │
  ▼
[3] バリデーション → DB 更新 → スケジューラに再登録
  │
  ▼
[4] 次回の trigger 発火時に修正版コードで実行される
```

---

## 画面構成

| 画面 | ファイル | 役割 | デザイン方針 |
|------|----------|------|-------------|
| Home | `home_view.py` | 通知フィード・アクティビティ | オシャレ・コンシューマー向け |
| Editor | `main_screen.py` | コード編集・コンパイル・保存 | ダークエディタ・開発感 |
| Dashboard | `dashboard_view.py` | ステータス・ルール管理・ログ | 開発寄り・モニタリング |
| Settings | `settings_screen.py` | LLM モデル設定 | ダイアログ |

### UI ↔ バックエンドの接続ポイント
- **Compile & Save** ボタン → `compiler.compile()` → `db_client.save_rule()` → `scheduler.add_rule()`
- **Run All** ボタン → `scheduler.start()`
- **Stop All** ボタン → `scheduler.remove_all()`
- **ログ表示** → `log_queue.drain()` を 1 秒ごとにポーリング → `receive_logs()` で各画面に配信
