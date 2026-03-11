# 🔰 初心者向けタスク一覧

LifeScript プロジェクトでプログラミング初心者の人が取り組めるタスクをまとめました。
難易度が低い順に並んでいます。

---

## ⭐ Lv.1 — コピペ＋少し変えるだけ

### タスク 1: README の更新

**やること**: `README.md` の内容を最新状態に合わせて更新する

- [ ] Settings セクション（138行目〜）から「Supabase — URL + Anon Key」の記述を削除
- [ ] 「ログインしてから使う」という説明に書き換える
- [ ] Project layout にある `auth/` フォルダの説明を追加する

**触るファイル**: `README.md` のみ

**学べること**: Markdown の書き方、Git の基本操作（add / commit / push）

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
1. `lifescript/plugins/weather_plugin.py` を読んで構造を理解する
2. 上のコードを `lifescript/plugins/math_plugin.py` として保存する
3. テストを書く（下記参照）

**触るファイル**: `lifescript/plugins/math_plugin.py`（新規作成）

**学べること**: Python のクラス、import、既存コードの読み方

---

## ⭐⭐ Lv.2 — 小さい機能を追加する

### タスク 3: テストを書く

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
3. 全部 PASSED になればOK ✅

**触るファイル**: `tests/test_math_plugin.py`（新規作成）

**学べること**: テストの書き方、`assert` の使い方、コマンドラインの使い方

---

### タスク 4: ログイン画面に「パスワードを忘れた」リンクを追加

**やること**: ログイン画面にパスワードリセット用のボタンを追加する

**手順**:
1. `lifescript/ui/login_screen.py` を開く
2. 「アカウントを作成」ボタンの下に新しいボタンを追加:
   ```python
   ft.TextButton(
       "パスワードを忘れた",
       style=ft.ButtonStyle(color=MID_TEXT),
       on_click=self._do_reset_click,
   ),
   ```
3. `_do_reset_click` メソッドを追加（メールに入力された値を使って Supabase のパスワードリセットを呼ぶ）

**ヒント**: `auth_client._client.auth.reset_password_email(email)` が Supabase のリセット API

**触るファイル**: `lifescript/ui/login_screen.py`

**学べること**: UI コンポーネントの追加、イベントハンドラの書き方

---

## ⭐⭐⭐ Lv.3 — 少し考えて実装する

### タスク 5: ログイン画面に「ログイン中...」のスケルトンアニメーション追加

**やること**: ログインボタン押下後、ローディング中にボタンを無効化する

**手順**:
1. `login_screen.py` のログインボタンに `ref` か変数を持たせる
2. `_set_loading(True)` の時にボタンの `disabled = True` にする
3. `_set_loading(False)` で `disabled = False` に戻す

**触るファイル**: `lifescript/ui/login_screen.py`

**学べること**: UI の状態管理、ユーザー体験の改善

---

### タスク 6: Home 画面の挨拶メッセージに名前を表示する

**やること**: ログインユーザーのメールアドレスから名前を取得して「おはよう、〇〇さん」と表示する

**手順**:
1. `lifescript/ui/home_view.py` の `_get_greeting()` メソッドを見つける
2. `auth_client.session.email` からメールの `@` より前の部分を取得する
3. 挨拶メッセージに組み込む

**触るファイル**: `lifescript/ui/home_view.py`

**学べること**: 文字列操作、モジュール間のデータの渡し方

---

## 📝 共通の作業手順

```bash
# 1. ブランチを切る
git checkout -b feature/タスク名

# 2. コードを書く・テストする
uv run pytest tests/ -v

# 3. コミット & プッシュ
git add .
git commit -m "タスクの説明"
git push origin feature/タスク名
```
