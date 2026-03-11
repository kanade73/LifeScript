# 🚀 Supabase セットアップ & ログイン機能を動かすロードマップ

---

## Step 1: Supabase プロジェクトを作る（5分）

1. [supabase.com](https://supabase.com) にアクセス → **Start your project**
2. GitHub アカウントでサインアップ（無料）
3. **New Project** をクリック
   - **Name**: `lifescript`（なんでもOK）
   - **Database Password**: 好きなパスワード（メモしておく）
   - **Region**: `Northeast Asia (Tokyo)` を選ぶ
4. 数分待つとプロジェクトが作成される

---

## Step 2: URL と Anon Key を取得する（1分）

1. Supabase Dashboard で作成したプロジェクトを開く
2. 左サイドバー → **⚙ Settings** → **API**
3. 以下の2つをコピー:
   - **Project URL** → `https://xxxxxx.supabase.co`
   - **anon public** キー → `eyJhbGci...`（長い文字列）

> ⚠️ **`service_role` キーは使わないこと！** `anon` の方を使う

---

## Step 3: `.env` に貼り付ける（1分）

プロジェクトの `.env` ファイルを編集:

```bash
# LifeScript/.env
SUPABASE_URL=https://xxxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

LITELLM_MODEL=ollama/qwen2.5-coder:7b
LITELLM_API_BASE=http://localhost:11434
```

---

## Step 4: データベースのテーブルを作る（2分）

1. Supabase Dashboard → 左サイドバー → **SQL Editor**
2. **New query** をクリック
3. プロジェクトの `schema.sql` の中身をコピペして **Run** を押す

```sql
CREATE TABLE IF NOT EXISTS rules (
    id              SERIAL PRIMARY KEY,
    title           TEXT    NOT NULL,
    lifescript_code TEXT    NOT NULL,
    compiled_python TEXT    NOT NULL,
    trigger_seconds INTEGER NOT NULL DEFAULT 60,
    status          TEXT    NOT NULL DEFAULT 'active',
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS logs (
    id            SERIAL PRIMARY KEY,
    rule_id       TEXT,
    message       TEXT    NOT NULL DEFAULT '',
    executed_at   TEXT    NOT NULL,
    result        TEXT    NOT NULL DEFAULT 'success',
    error_message TEXT    NOT NULL DEFAULT ''
);
```

> ⚠️ Supabase は PostgreSQL なので `AUTOINCREMENT` → `SERIAL` に変わるよ

---

## Step 5: メール認証を有効にする（1分）

1. Supabase Dashboard → 左サイドバー → **Authentication**
2. **Providers** タブをクリック
3. **Email** が **Enabled** になっていることを確認（デフォルトで有効）

### （任意）メール確認をスキップしたい場合:
1. **Authentication** → **Settings** (上のタブ)
2. **「Confirm email」をOFF** にする → 登録してすぐログイン可能

> 💡 開発中は Confirm email を OFF にしておくと楽

---

## Step 6: アプリを起動してテスト！（1分）

```bash
cd /Users/kanade/dev/LifeScript
uv run lifescript
```

1. ログイン画面が表示される
2. **「アカウントを作成」** でメール + パスワード（6文字以上）を入力
3. ログイン成功 → メイン画面に遷移！🎉

---

## まとめ（全体像）

```
Supabase Dashboard          LifeScript アプリ
┌──────────────────┐        ┌──────────────────┐
│ 1. プロジェクト作成  │        │                  │
│ 2. URL + Key 取得  │──.env→│ 3. .env に貼る     │
│ 4. SQL でテーブル作成│        │                  │
│ 5. Email Auth 有効 │        │ 6. uv run lifescript │
└──────────────────┘        │    → ログイン画面！  │
                            └──────────────────┘
```

## ❓ よくある質問

| 問題 | 解決方法 |
|---|---|
| `SUPABASE_URL と SUPABASE_ANON_KEY を設定してください` | `.env` に URL と Key が入っているか確認 |
| ログインしても「失敗しました」 | Supabase の Authentication → Email が有効か確認 |
| テーブルが見つからない | SQL Editor で `schema.sql` を実行したか確認 |
| `Confirm email` のメールが来ない | 開発中は Authentication → Settings → Confirm email を OFF に |
