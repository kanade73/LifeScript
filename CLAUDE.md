# LifeScript 仕様書

> HackU Frontier 向け実装仕様  
> 最終更新: 2026-03-19

---

## 目次

1. [共通仕様](#共通仕様)
   - [コンセプト](#コンセプト)
   - [関数ライブラリ（DSLで呼べる関数）](#関数ライブラリdslで呼べる関数)
   - [DSL仕様例](#dsl仕様例)
   - [LLMコンパイルフロー](#llmコンパイルフロー)
   - [データモデル（Supabase）](#データモデルsupabase)
   - [LLM・インフラ](#llmインフラ)
2. [スマホ仕様（iOS / SwiftUI）](#スマホ仕様ios--swiftui)
   - [技術スタック](#技術スタック-ios)
   - [画面構成](#画面構成-ios)
   - [オンボーディングフロー](#オンボーディングフロー)
   - [機能一覧](#機能一覧-ios)
   - [バックエンドとの通信](#バックエンドとの通信)
3. [PC仕様（Python / Flet）](#pc仕様python--flet)
   - [技術スタック](#技術スタック-pc)
   - [画面構成](#画面構成-pc)
   - [バックエンド処理フロー](#バックエンド処理フロー)
   - [モジュール構成](#モジュール構成)
   - [LiteLLM設定](#litellm設定)
   - [機能一覧](#機能一覧-pc)

---

## 共通仕様

### コンセプト

**LifeScriptとは**

「マシン」という相棒に自分の生活文脈を伝えるためのDSL。ユーザーはルールを書くのではなく、マシンへの文脈を定義する。マシンはその文脈を読み、カレンダーや通知を通じて能動的に動く。関数ライブラリの拡充がそのままプロダクトのロードマップとなる。

**リマインドアプリとの差**

リマインドアプリは人間がルールを考えて設定する。LifeScriptはカレンダーや初回オンボーディングで得た文脈をLLMが解釈し、ユーザーが設定していない行動まで提案・実行する。「毎回話しかけなくていいChatGPT」に近い。

```
リマインドアプリ   → 人間がルールを考えて、アプリが実行する
IFTTTなどの自動化  → 人間がトリガーと行動を設定する

LifeScriptの本質  → 人間が「自分の文脈」を渡すと、
                    LLMが構造化して意味を読み取り、
                    何をすべきかを判断して動く
```

---

### 関数ライブラリ（DSLで呼べる関数）

**関数ライブラリの拡充 = LifeScriptのロードマップそのもの。**  
関数が増えるほどDSLの表現力が上がり、マシンが「世界の変化に反応する」領域へ広がっていく。

#### Phase 1 — 今週実装（ハッカソン最低限）

| 関数 | シグネチャ | 説明 |
|---|---|---|
| `notify()` | `notify(message: str, at?: datetime)` | 指定時刻にアプリ内通知を送る。atを省略した場合は即時実行。traitsのnotify制約（朝8時以降など）を自動適用。 |
| `calendar.add()` | `calendar.add(title: str, start: datetime, end?: datetime, note?: str)` | Supabaseのcalendar_eventsに新しいイベントを追加。sourceは"machine"または"user"で区別。iOSのカレンダーUIに即時反映。 |
| `calendar.read()` | `calendar.read(keyword?: str, range?: str) -> list[Event]` | Supabaseからイベントを取得。keyword="バイト"でタイトル絞り込み、range="this_week"で期間指定。count_this_week属性でカウント可。 |
| `calendar.suggest()` | `calendar.suggest(title: str, on: str, note?: str)` | イベントの提案をmachine_logsに書き込み、iOSのホーム画面に提案カードとして表示。ユーザーが承認するとcalendar.add()が実行される。 |

#### Phase 2 — ハッカソン当日向け（実装済み）

| 関数 | シグネチャ | 説明 |
|---|---|---|
| `machine.analyze()` | `machine.analyze() -> list[dict]` | コンテキスト分析を実行。カレンダー・メール・traitsをLLMで分析し、提案（notify 1件 + calendar 2件）をmachine_logsに自動生成。 |
| `machine.suggest()` | `machine.suggest(message: str, reason?: str)` | ダリーの提案をmachine_logsに直接書き込む。ホーム画面の提案セクションに通知として表示される。reasonで理由を付与可能。 |
| `web.fetch()` | `web.fetch(url: str, summary?: bool) -> str` | URLの内容を取得しLLMで要約して返す。summary=Falseで生テキスト。widget_showと組み合わせ可。 |
| `widget.show()` | `widget.show(name: str, content: str, icon?: str)` | ホーム画面にカスタムウィジェットを表示/更新する。スクリプト実行のたびに内容が最新化される。 |
| `gmail.unread()` | `gmail.unread(limit?: int) -> list[dict]` | 未読メールを取得。各要素は {subject, from, date, snippet, body}。Google認証が必要。 |
| `gmail.search()` | `gmail.search(query: str, limit?: int) -> list[dict]` | Gmailを検索。Gmail検索構文が使える。Google認証が必要。 |
| `gmail.summarize()` | `gmail.summarize(limit?: int) -> str` | 未読メールをLLMで要約して返す。widget_showと組み合わせ可。Google認証が必要。 |
| `gmail.send()` | `gmail.send(to: str, subject: str, body: str) -> str` | メールを送信する。Google認証が必要。 |

#### 将来実装

| 関数 | シグネチャ | 説明 |
|---|---|---|
| `weather.get()` | `weather.get(location?: str) -> WeatherInfo` | OpenWeatherMap APIから現在の天気・気温を取得。locationを省略するとuser.context("location")を使用。condition属性でrain/sunny等を判定。 |
| `location.pattern()` | `location.pattern(label: str, radius_m?: int) -> PatternInfo` | 位置情報の滞在パターンを分析。label="バイト先"のような名前付き場所へのアクセス頻度をSupabaseのログから集計。 |
| `machine.decide()` | `machine.decide(context: dict) -> Action` | 収集した全文脈をLLMに渡し、次の行動を自律判断させる。実行時にLLMを呼び出す唯一の関数。コスト注意。 |
| `habit.track()` | `habit.track(name: str, done: bool)` | 習慣の完了状況をstreaksテーブルに記録。done=Trueでstreak+1、done=Falseでリセット。streak.count()と組み合わせて使う。 |

---

### DSL仕様例

```yaml
# 初回オンボーディングで定義されるベース文脈
traits:
  朝は弱い → notify() は 8:00 以降
  バイトの許容は週3まで

# Phase 1: カレンダーベースの自動化
when calendar.read("バイト").count_this_week >= 4:
  calendar.suggest("回復タイム", on="next_free_morning")

# Phase 2: 文脈分析 + 能動的提案（実装済み）
every day:
  machine.analyze()   # カレンダー・メール・traitsを分析して提案生成

when calendar.read("バイト").count_this_week >= 4:
  machine.suggest("今週はバイトが多いので休息日を作りましょう",
                  reason="バイトが週4回以上")

# メール要約をウィジェットに表示
when morning:
  summary = gmail.summarize()
  widget.show("メール要約", summary, icon="mail")

# 将来: 外部状態トリガー
when weather.get().condition == "rain" and time == "morning":
  notify("傘を持って")
```

**設計の核心**

```
浅い記述  → マシンが基本的に動く
深い記述  → マシンがより文脈を理解して動く
```

書けば書くほどマシンが賢くなる正のフィードバックループを設計する。
ユーザーは関数名を正確に覚えなくてもよい。LLMがコンパイル時に自然言語から変換する。

---

### LLMコンパイルフロー

```
DSL文字列
  ↓
LiteLLM（gemini-2.5-flash）
  ↓
Pythonコード生成
  ↓
RestrictedPython（検証・サンドボックス）
  ↓
APScheduler（ジョブ登録）
```

> **重要**: 基本的にcompile時のみLLM呼び出し → コスト最小化。例外: `machine.analyze()` と `gmail.summarize()` は実行時にもLLMを使用する。

---

### データモデル（Supabase）

| テーブル | 主なカラム | 用途 |
|---|---|---|
| `users` | id, email, personality_json | ユーザー情報・オンボーディング結果 |
| `scripts` | id, user_id, dsl_text, compiled_python, active | LifeScriptのルール管理 |
| `calendar_events` | id, user_id, title, start_at, end_at, source | イベント蓄積（自前カレンダーのソース） |
| `machine_logs` | id, user_id, action_type, content, triggered_at | マシンの行動履歴・提案ログ |
| `streaks` | id, user_id, habit_name, count, last_date | 継続カウント管理 |

---

### LLM・インフラ

| 項目 | 内容 |
|---|---|
| LLMモデル（開発） | `gemini/gemini-2.5-flash`（Google AI Studio無料枠） |
| LLMモデル（当日） | `gemini/gemini-2.5-pro`（GCP $300クレジット） |
| LLM呼び出しタイミング | DSLコンパイル時のみ・実行時は不使用 |
| フォールバック | `openrouter/google/gemini-2.0-flash-exp:free` |
| DB | Supabase（開発用共有アカウント） |
| APIキー管理 | `.env` / `.gitignore`（publicリポジトリ注意） |

---

## スマホ仕様（iOS / SwiftUI）

### 技術スタック (iOS)

- **SwiftUI** — UI全体
- **Supabase Swift SDK** — DB・認証
- EventKit **不使用** — カレンダーはSupabaseから取得する自前実装
- CoreLocation — Phase 2以降で検討
- 認証 — Supabase Email/Password または匿名認証

**設計方針**: カレンダーはSupabaseから取得する自前実装。外部カレンダー連携（EventKit）は行わず、LifeScript内のカレンダーが唯一の真実。これによりOS側との同期問題を排除し、マシンが管理するカレンダーがソースとなる。

---

### 画面構成 (iOS)

#### ホーム画面
今日・今週の文脈を可視化。マシンの提案を表示。

- 自前カレンダーUI（月/週表示）
- イベント追加ボタン
- マシンからの提案カード
- 今日のイベント一覧
- streak表示（習慣継続日数）

#### ダッシュボード
マシンが読み取っている文脈の透明性を確保。

- 今週のカレンダー集計
- マシンの認識サマリ
- 過去の提案・行動ログ
- personality設定の確認

#### IDE画面
DSLを書く・編集する場所。書くほどマシンが賢くなる体験。

- DSLテキストエディタ
- コンパイルボタン（LLM呼び出し）
- コンパイル結果表示
- 関数リファレンス一覧
- エラー表示

---

### オンボーディングフロー

```
初回起動
  ↓
マシンの紹介画面（キャラクター説明）
  ↓
パーソナリティ入力（一度だけ）
  ↓
ホーム画面
```

**パーソナリティ入力（一度だけ）**

朝型/夜型・バイトや授業の大まかな頻度・集中できる時間帯・苦手なことなどを入力。  
これがSupabaseの `users.personality_json` に保存され、マシンの文脈の起点になる。  
毎日入力させる日記とは全く異なる体験——最初に少しだけ自分を教えたら、あとは勝手に育つ。

---

### 機能一覧 (iOS)

| 機能 | 優先度 | 備考 |
|---|---|---|
| 自前カレンダーUI（月表示） | **必須** | ホーム画面の中核 |
| イベントCRUD | **必須** | Supabase calendar_eventsと同期 |
| マシン提案カード表示 | **必須** | machine_logsから取得 |
| DSLエディタ + コンパイル | **必須** | バックエンドAPIを叩く |
| オンボーディング画面 | **必須** | personality_json保存 |
| ダッシュボード（集計） | 欲しい | 文脈の透明性 |
| 週表示カレンダー | 欲しい | 月表示が完成後 |
| streak表示 | 欲しい | streaksテーブルから |
| 関数リファレンス | 将来 | IDE画面内 |

---

### バックエンドとの通信

SwiftUIからSupabaseへの直接アクセス（CRUD）と、コンパイル・スケジューラ登録はPythonバックエンドへのREST呼び出しで分離する。

```
コンパイルエンドポイント:
  POST /compile
  Body: { dsl_text: string }
  Response: { compiled_python: string, error?: string }
```

---

## PC仕様（Python / Flet）

### 技術スタック (PC)

- **Python** — バックエンド全体
- **Flet** — デモ・開発用PCのUI
- **APScheduler** — コンパイル済みPythonのスケジュール実行
- **LiteLLM** — LLM呼び出しの抽象化
- **RestrictedPython** — サンドボックス実行
- **Supabase Python SDK** — DB操作

**設計方針**: Flet UIはデモ・開発用のPC画面として機能。APSchedulerがコンパイル済みPythonをスケジュール実行。実行時はLLMを呼ばずPythonを直接実行。RestrictedPythonでサンドボックス化。

---

### 画面構成 (PC)

#### ホーム画面
カレンダーとマシンの状態をPC上で確認。

- カレンダー表示（Supabaseから）
- マシンの最新提案
- 現在稼働中のルール一覧
- ジョブ実行ログ

#### IDE画面
DSL記述・コンパイル・スケジューラ登録の中核。

- DSLテキストエディタ
- コンパイルボタン
- 生成Pythonコードのプレビュー
- スケジューラへの登録ボタン
- エラー・警告表示

#### ダッシュボード
マシンが持っている文脈の全体像を可視化。

- personality_json表示
- 今週のカレンダー集計
- streak一覧
- machine_logs履歴
- LLMコスト概算

---

### バックエンド処理フロー

**コンパイルフロー**
```
DSL入力
  ↓
compiler.py（LiteLLM呼び出し）
  ↓
compiled_python
  ↓
validator.py（RestrictedPython）
  ↓
scheduler.py（APScheduler登録）
```

**実行フロー**
```
トリガー発火
  ↓
関数ライブラリ呼び出し
  ↓
Supabase更新
  ↓
iOSへ通知（DB経由ポーリング または プッシュ）
```

---

### モジュール構成

| ファイル | 責務 | 優先度 |
|---|---|---|
| `compiler.py` | DSL文字列 → Python変換（LiteLLM呼び出し） | **必須** |
| `validator.py` | RestrictedPythonによるサンドボックス検証 | **必須** |
| `scheduler.py` | APSchedulerジョブ管理・登録・削除 | **必須** |
| `functions/notify.py` | `notify()` の実装 | **必須** |
| `functions/calendar.py` | `calendar.*` の実装（Supabase CRUD） | **必須** |
| `api.py` | iOSから叩くREST APIエンドポイント | **必須** |
| `functions/machine.py` | `machine.analyze()` / `machine.suggest()` — 能動的提案 | **実装済み** |
| `functions/gmail.py` | `gmail.*` の実装（Gmail API連携） | **実装済み** |
| `functions/web.py` | `web.fetch()` — URL取得・要約 | **実装済み** |
| `functions/widget.py` | `widget.show()` — ホーム画面ウィジェット | **実装済み** |
| `context_analyzer.py` | カレンダー・メール・traits分析 → 提案生成（LLM使用） | **実装済み** |
| `functions/streak.py` | `streak.count()` の実装 | 欲しい |
| `functions/weather.py` | `weather.get()`（OpenWeatherMap） | 将来 |

---

### LiteLLM設定

```yaml
# litellm_config.yaml
model_list:
  - model_name: lifescript-compiler
    litellm_params:
      model: gemini/gemini-2.5-flash  # 開発中
      api_key: os.environ/GEMINI_API_KEY

  - model_name: lifescript-compiler   # フォールバック
    litellm_params:
      model: openrouter/google/gemini-2.0-flash-exp:free
      api_key: os.environ/OPENROUTER_API_KEY

router_settings:
  routing_strategy: "fallback"
  num_retries: 2
```

**.env構成**

```bash
# 開発中
LIFESCRIPT_MODEL=gemini/gemini-2.5-flash
GEMINI_API_KEY=your_free_key

# ハッカソン当日（前日に切替）
LIFESCRIPT_MODEL=gemini/gemini-2.5-pro
GEMINI_API_KEY=your_paid_key

# フォールバック
OPENROUTER_API_KEY=your_openrouter_key
```

> **注意**: `kanade73/LifeScript` はpublicリポジトリのため `.env` を必ず `.gitignore` に追加すること。

---

### 機能一覧 (PC)

| 機能 | 優先度 | 備考 |
|---|---|---|
| DSLコンパイル（LLM） | **必須** | compiler.py中核機能 |
| RestrictedPython検証 | **必須** | セキュリティ必須 |
| APSchedulerジョブ登録 | **必須** | scheduler.py |
| `calendar.*` 関数群 | **必須** | Supabase連携 |
| REST APIエンドポイント | **必須** | iOS向け `/compile` |
| IDE画面（Flet） | **必須** | デモ用 |
| `context_builder` | 欲しい | マシンの能動提案に必要 |
| `machine.suggest()` | 欲しい | デモの見栄え |
| ダッシュボード（Flet） | 欲しい | 文脈の可視化 |
| `weather.get()` | 将来 | 外部状態トリガー |

---

## ロードマップ

### Phase 1（今週）— カレンダー中心設計

- [ ] カレンダーUIをホーム画面に実装（自前）
- [ ] イベントをSupabaseに蓄積
- [ ] リマインドはカレンダーイベントから生成に変更
- [ ] `calendar.add()` / `calendar.read()` / `calendar.suggest()` 実装
- [ ] REST API `/compile` エンドポイント

> **成功条件**: 「バイトが週4入ってるね」という提案がmachine_logsに書き込まれ、iOSに表示されること。

### Phase 2（ハッカソン当日向け）— マシンとの対話

- [ ] 初回オンボーディング（パーソナリティ入力）
- [ ] マシンキャラクター設定
- [ ] `user.context()` / `streak.count()` / `machine.suggest()` 実装
- [ ] `context_builder.py` — 文脈をLLMに渡す仕組み
- [ ] 能動的な提案デモシーン（「休息を追加しようか？」）

> **成功条件**: ユーザーが何も設定していないのに、マシンが文脈を読んで能動的に提案してくること。

### 将来ロードマップ — 関数ライブラリの拡充

- [ ] `weather.get()` — 外部状態トリガー
- [ ] `location.pattern()` — 位置情報パターン認識
- [ ] `machine.decide()` — マシンへの完全委譲
- [ ] `habit.track()` — 習慣トラッキング