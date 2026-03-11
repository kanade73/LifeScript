# 初心者向けタスク一覧

LifeScript プロジェクトでプログラミング初心者の人が取り組めるタスクをまとめました。
難易度が低い順に並んでいます。

現在は **開発モード**（Supabase 認証スキップ、SQLite フォールバック）で動作しています。
アプリは `uv run python -m lifescript` で起動できます。

---

## Lv.1 — コピペ＋少し変えるだけ

### タスク 1: サンプル LifeScript を追加する

**やること**: エディタ画面のデフォルトコードに加えて、サンプル LifeScript をいくつか作る

現在のデフォルトコード（`lifescript/ui/main_screen.py` 14行目）:

```javascript
// 例: 毎朝8時にログ記録
every day {
  when fetch(time.now) == "08:00" {
    log("おはようございます")
  }
}
```

**手順**:
1. `lifescript/ui/main_screen.py` を開く
2. エディタのサイドバー（Active Rules パネル）の上に「サンプル」セクションを追加する
3. クリックするとエディタにサンプルコードが入るボタンを 2〜3 個追加する

サンプル案:
```javascript
// 1時間ごとにログ
every 1h {
  log("1時間が経過しました")
}
```
```javascript
// 勤務時間チェック
let now = fetch(time.now)
if now >= "09:00" and now <= "18:00" {
  log("勤務時間内です")
}
```

**触るファイル**: `lifescript/ui/main_screen.py`

**学べること**: Python の文字列、Flet の UI コンポーネント（ボタン・イベント）

---

### タスク 2: 新しいプラグインを作る（テンプレをコピー）

**やること**: 既存のプラグインをコピーして新しいプラグインを作る

例: `math_plugin.py` — ランダムな数字を返す関数

```python
"""Math plugin - provides random number generation."""

from __future__ import annotations

import random

from .base import Plugin


class MathPlugin(Plugin):
    @property
    def name(self) -> str:
        return "math"

    def random_number(self, min_val: int = 1, max_val: int = 100) -> int:
        """min〜maxのランダムな整数を返す。"""
        return random.randint(min_val, max_val)


_plugin = MathPlugin()


def get_random_number(min_val: int = 1, max_val: int = 100) -> int:
    return _plugin.random_number(min_val, max_val)


# Auto-discovery registration
PLUGIN_EXPORTS = [
    {
        "name": "random_number",
        "func": get_random_number,
        "signature": "random_number(min_val: int = 1, max_val: int = 100) -> int",
        "description": "ランダムな整数を返す",
    },
]
```

**手順**:
1. `lifescript/plugins/time_plugin.py` を読んで構造を理解する
2. 上のコードを `lifescript/plugins/math_plugin.py` として保存する（既にあれば中身を確認）
3. `PLUGIN_EXPORTS` リストに登録すれば自動でコンパイラ・サンドボックスに組み込まれる

**触るファイル**: `lifescript/plugins/math_plugin.py`（新規作成 or 編集）

**学べること**: Python のクラス、import、プラグインの仕組み

---

## Lv.2 — 小さい機能を追加する

### タスク 3: プラグインのテストを書く

**やること**: タスク 2 で作ったプラグインのテストを書く

**参考にするファイル**: `tests/test_plugins.py`

```python
"""Tests for the math plugin."""

from lifescript.plugins.math_plugin import get_random_number


class TestMathPlugin:
    def test_random_number_in_range(self):
        result = get_random_number(1, 10)
        assert 1 <= result <= 10

    def test_random_number_default_range(self):
        result = get_random_number()
        assert 1 <= result <= 100

    def test_random_number_same_min_max(self):
        result = get_random_number(5, 5)
        assert result == 5
```

**手順**:
1. 上のコードを `tests/test_math_plugin.py` として保存する
2. `uv run pytest tests/test_math_plugin.py -v` で実行
3. 全部 PASSED になればOK

**触るファイル**: `tests/test_math_plugin.py`（新規作成）

**学べること**: テストの書き方、`assert` の使い方、コマンドラインの使い方

---

### タスク 4: エディタにキーワードボタンを追加する

**やること**: エディタ画面にLifeScriptのキーワードを挿入するボタンを追加する

仕様書（CLAUDE.md 5.3節）より:
> 初心者向けキーワードボタン群: `when` / `every` / `if` / `log` / `fetch` などをボタンで呼び出してエディタに挿入する

**手順**:
1. `lifescript/ui/main_screen.py` を開く
2. アクションバー（Compile & Save ボタンの並び）の近くにキーワードボタンの行を追加する
3. 各ボタンをクリックするとエディタにキーワードのテンプレートが挿入される

```python
# ボタンの例
ft.OutlinedButton(
    "every",
    on_click=lambda e: self._insert_snippet('every 1h {\n  \n}'),
    style=ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=10),
        side=ft.BorderSide(1, COLORS["blue"]),
        color=COLORS["blue"],
    ),
)
```

挿入スニペット案:
| ボタン | 挿入されるコード |
|--------|------------------|
| `every` | `every 1h {\n  \n}` |
| `when` | `when fetch(time.now) == "08:00" {\n  \n}` |
| `log` | `log("メッセージ")` |
| `fetch` | `fetch(time.now)` |
| `if` | `if 条件 {\n  \n}` |
| `let` | `let x = ` |

**触るファイル**: `lifescript/ui/main_screen.py`

**学べること**: Flet のボタン・イベント、テキストフィールドの値操作

---

## Lv.3 — 少し考えて実装する

### タスク 5: Home 画面のデザイン改善

**やること**: Home 画面（`lifescript/ui/home_view.py`）の見た目をより良くする

改善案:
- アクティビティカードにルールのタイトルも表示する（今は `rule_id` のみ）
- フィードが空の時の表示をもっとオシャレにする（イラストやアニメーション追加）
- サマリーチップに今日の実行回数を表示する

**ファイル構造の理解**:
- `HomeView.__init__()` — 画面のレイアウト構築
- `_feed_card()` — 各ログエントリのカードを生成
- `receive_logs()` — リアルタイムで届くログをフィードに追加
- `_refresh_chips()` — 上部のサマリーチップを更新

**触るファイル**: `lifescript/ui/home_view.py`

**学べること**: Flet のレイアウト、データの流れの理解

---

### タスク 6: Dashboard のルールカードに操作ボタンを追加する

**やること**: Dashboard 画面のルールカードに「一時停止」「削除」ボタンを追加する

**手順**:
1. `lifescript/ui/dashboard_view.py` の `_rule_card()` メソッドを見つける
2. カードの中にボタンを追加する
3. ボタンのクリックで `scheduler.pause_rule(rule_id)` や `db_client.delete_rule(rule_id)` を呼ぶ

**参考**: エディタ画面（`main_screen.py`）の `_delete_rule()` メソッドが同じことをやっている

**触るファイル**: `lifescript/ui/dashboard_view.py`

**学べること**: 既存コードの読み方、イベントハンドラ、スレッド処理

---

## 共通の作業手順

```bash
# 1. 最新の main を取得
git pull origin main

# 2. ブランチを切る
git checkout -b feature/タスク名

# 3. コードを書く

# 4. lint チェック
uv run ruff check .
uv run ruff format .

# 5. テストを実行
uv run pytest tests/ -v

# 6. アプリを起動して確認
uv run python -m lifescript

# 7. コミット & プッシュ
git add 変更したファイル名
git commit -m "タスクの説明"
git push origin feature/タスク名
```

## 現在の画面構成

| アイコン | 画面 | 役割 |
|----------|------|------|
| Home | ホーム | 通知フィード・アクティビティタイムライン（オシャレ） |
| Edit | エディタ | LifeScript コード編集・コンパイル・ルール管理（開発感） |
| Dashboard | ダッシュボード | ステータス・ルール一覧・ライブログ（開発寄り） |

## 主要ファイル一覧

| ファイル | 説明 |
|----------|------|
| `lifescript/ui/home_view.py` | Home 画面 |
| `lifescript/ui/main_screen.py` | エディタ画面 |
| `lifescript/ui/dashboard_view.py` | ダッシュボード画面 |
| `lifescript/ui/app.py` | アプリ全体のレイアウト・ナビゲーション |
| `lifescript/plugins/` | プラグイン（`time_plugin.py`, `log_plugin.py` など） |
| `tests/` | テストコード |
