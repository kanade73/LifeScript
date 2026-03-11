class LifeScriptError(Exception):
    """LifeScript の全例外の基底クラス。"""


class CompileError(LifeScriptError):
    """LifeScript から Python へのコンパイルに失敗した場合に送出される。"""


class ValidationError(LifeScriptError):
    """生成された Python が静的解析に通らなかった場合に送出される。"""


class ServiceNotConnectedError(LifeScriptError):
    """外部サービス（Discord, LINE 等）が未接続の場合に送出される。"""

    def __init__(self, service: str):
        super().__init__(
            f"LifeScriptError: {service} が接続されていません。\n"
            f"Settings から {service} アカウントを連携してください。"
        )
        self.service = service


class SandboxError(LifeScriptError):
    """サンドボックス内でのコード実行が失敗した場合に送出される。"""
