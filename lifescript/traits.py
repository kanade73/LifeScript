"""traits — DSLから文脈定義（traits）を抽出・収集するモジュール。

traitsはユーザーが自分の生活パターンや価値観をDSLの中で言語化したもの。
マシンはtraitsを読んで提案の根拠にする。

DSL例:
    traits:
      朝は弱い → notify() は 8:00 以降
      バイトの許容は週3まで
      疲れた時は美味しいものを食べに行く
"""

from __future__ import annotations

import re

from .database.client import db_client


def extract_traits(dsl_text: str) -> list[str]:
    """DSLテキストから traits ブロックの各行を抽出する。"""
    traits: list[str] = []
    in_traits = False

    for line in dsl_text.splitlines():
        stripped = line.strip()

        if stripped.lower().startswith("traits:"):
            in_traits = True
            # "traits:" の後ろに内容がある場合
            rest = stripped[7:].strip()
            if rest:
                traits.append(rest)
            continue

        if in_traits:
            # インデントされていない行 or 別のブロック開始で終了
            if stripped and not line[0].isspace():
                in_traits = False
                continue
            if stripped:
                traits.append(stripped)

    return traits


def gather_all_traits() -> list[str]:
    """全てのアクティブなスクリプトからtraitsを収集する。"""
    all_traits: list[str] = []
    try:
        scripts = db_client.get_scripts()
        for script in scripts:
            dsl = script.get("dsl_text", "")
            all_traits.extend(extract_traits(dsl))
    except Exception:
        pass
    # 重複除去（順序保持）
    seen: set[str] = set()
    unique: list[str] = []
    for t in all_traits:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def format_traits_for_prompt(traits: list[str]) -> str:
    """プロンプト埋め込み用にtraitsをフォーマットする。"""
    if not traits:
        return "（まだ定義されていません — ユーザーがDSLでtraitsを書くと蓄積されます）"
    return "\n".join(f"- {t}" for t in traits)
