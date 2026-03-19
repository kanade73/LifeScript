"""オンボーディング画面 — 初回ログイン時にユーザーのパーソナリティを収集。

回答はメモリ（machine_logs action_type="memory"）に保存され、
マシンの提案やチャットの文脈として即座に使用される。
"""

from __future__ import annotations

import flet as ft

from ..database.client import db_client
from .app import (
    BG, CARD_BG, BLUE, GREEN, CORAL, YELLOW, ORANGE, PURPLE,
    DARK_TEXT, MID_TEXT, LIGHT_TEXT, CARD_SHADOW, SHADOW_SOFT, darii_image,
)

_BORDER = "#E8E4DC"

# ── 質問定義 ──────────────────────────────────────────────────
# (質問文, 選択肢リスト, メモリ変換テンプレート)
# テンプレートの {answer} が選択された値に置換される
_QUESTIONS: list[tuple[str, list[str], str]] = [
    (
        "朝と夜、どちらが得意ですか？",
        ["朝型", "夜型", "どちらでもない"],
        "{answer}",
    ),
    (
        "通知はいつ届くと嬉しいですか？",
        ["朝（7-9時）", "昼（12-14時）", "夕方（17-19時）", "夜（20-22時）", "いつでもOK"],
        "通知は{answer}に届けてほしい",
    ),
    (
        "予定が詰まると…",
        ["ストレスを感じる（余白が欲しい）", "充実感がある（忙しいのが好き）", "特に気にしない"],
        "予定が詰まると{answer}",
    ),
    (
        "疲れたときのリフレッシュ方法は？",
        ["美味しいものを食べる", "散歩・外出する", "家でゆっくり過ごす", "運動する", "寝る"],
        "疲れたときは{answer}ことが多い",
    ),
    (
        "ダリーにどこまで任せたいですか？",
        ["積極的に提案してほしい", "控えめに提案してほしい", "聞いたときだけ答えてほしい"],
        "ダリーには{answer}",
    ),
]


def build_onboarding(page: ft.Page, on_complete: callable) -> ft.Control:
    """オンボーディングUIを構築して返す。

    on_complete() はオンボーディング完了時に呼ばれる。
    """
    current_q = [0]
    answers: list[str] = []
    selected_index: list[int | None] = [None]

    # ── UIパーツ ──
    question_text = ft.Text("", size=20, weight=ft.FontWeight.W_700, color=DARK_TEXT)
    progress_text = ft.Text("", size=13, color=MID_TEXT)
    choices_column = ft.Column(spacing=8)
    next_btn = ft.Container(
        content=ft.Row([
            ft.Text("次へ", size=14, weight=ft.FontWeight.W_600, color=CARD_BG),
            ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=18, color=CARD_BG),
        ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
        bgcolor=BLUE, border_radius=12,
        padding=ft.padding.symmetric(horizontal=24, vertical=12),
        on_click=lambda e: _on_next(),
        ink=True,
        visible=False,
        opacity=0.5,
    )

    def _render_question() -> None:
        idx = current_q[0]
        q_text, choices, _ = _QUESTIONS[idx]
        selected_index[0] = None
        next_btn.visible = False

        question_text.value = q_text
        progress_text.value = f"{idx + 1} / {len(_QUESTIONS)}"

        choices_column.controls.clear()
        for i, choice in enumerate(choices):
            choice_card = ft.Container(
                content=ft.Row([
                    ft.Container(
                        width=20, height=20, border_radius=10,
                        border=ft.border.all(2, BLUE),
                        bgcolor=ft.Colors.TRANSPARENT,
                    ),
                    ft.Text(choice, size=15, color=DARK_TEXT),
                ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=CARD_BG, border_radius=16,
                padding=ft.padding.symmetric(horizontal=16, vertical=14),
                border=ft.border.all(1, _BORDER),
                on_click=lambda e, ci=i: _select(ci),
                ink=True,
            )
            choices_column.controls.append(choice_card)
        page.update()

    def _select(choice_idx: int) -> None:
        selected_index[0] = choice_idx
        _, choices, _ = _QUESTIONS[current_q[0]]

        for i, card in enumerate(choices_column.controls):
            if i == choice_idx:
                card.border = ft.border.all(2, BLUE)
                card.bgcolor = f"{BLUE}08"
                # ラジオボタンを塗りつぶし
                row = card.content
                dot = row.controls[0]
                dot.bgcolor = BLUE
            else:
                card.border = ft.border.all(1, _BORDER)
                card.bgcolor = CARD_BG
                row = card.content
                dot = row.controls[0]
                dot.bgcolor = ft.Colors.TRANSPARENT

        next_btn.visible = True
        next_btn.opacity = 1.0
        page.update()

    def _on_next() -> None:
        if selected_index[0] is None:
            return

        idx = current_q[0]
        _, choices, template = _QUESTIONS[idx]
        answer = choices[selected_index[0]]
        answers.append(template.format(answer=answer))

        if idx + 1 < len(_QUESTIONS):
            current_q[0] = idx + 1
            _render_question()
        else:
            _save_and_finish()

    def _save_and_finish() -> None:
        # 回答をメモリに保存
        for memory_text in answers:
            db_client.add_machine_log(action_type="memory", content=memory_text)

        on_complete()

    # ── プログレスバー ──
    progress_bar = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.ProgressBar(
                    value=0, bgcolor=f"{BLUE}15", color=BLUE,
                ),
                expand=True, height=6, border_radius=3,
            ),
        ]),
    )

    # プログレス更新用
    def _update_progress() -> None:
        bar = progress_bar.content.controls[0].content
        bar.value = (current_q[0] + 1) / len(_QUESTIONS)

    # _render_question を拡張してプログレスも更新
    original_render = _render_question
    def _render_with_progress() -> None:
        original_render()
        _update_progress()
        page.update()

    # 差し替え
    _render_question = _render_with_progress

    # ── レイアウト ──
    _render_question()

    return ft.Container(
        content=ft.Column([
            ft.Container(height=40),
            # ヘッダー
            ft.Row([
                ft.Container(
                    content=darii_image(44),
                    width=48, height=48, border_radius=18,
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Container(width=12),
                ft.Column([
                    ft.Text("はじめまして", size=24, weight=ft.FontWeight.W_800, color=DARK_TEXT),
                    ft.Text("あなたのことを少し教えてください", size=13, color=MID_TEXT),
                ], spacing=2),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=8),
            progress_bar,
            ft.Container(height=24),
            # 質問エリア
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        question_text,
                        ft.Container(expand=True),
                        progress_text,
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=16),
                    choices_column,
                    ft.Container(height=16),
                    ft.Row([
                        ft.Container(expand=True),
                        next_btn,
                    ]),
                ], spacing=0),
                bgcolor=CARD_BG,
                border_radius=24,
                padding=ft.padding.all(24),
                shadow=CARD_SHADOW,
                width=560,
            ),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
        expand=True, bgcolor=BG,
        alignment=ft.Alignment(0, -0.2),
    )
