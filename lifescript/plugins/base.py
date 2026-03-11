"""プラグインの抽象基底クラス。

すべてのプラグインはこの Plugin クラスを継承して実装する。
"""

from abc import ABC, abstractmethod


class Plugin(ABC):
    """プラグインの基底クラス。name プロパティの実装が必須。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """プラグイン名を返す（例: "time", "log"）。"""
        ...

    @property
    def requires_connection(self) -> bool:
        """外部サービスへの接続が必要かどうか。"""
        return False

    def check_connection(self) -> bool:
        """接続済みかどうかを返す。"""
        return True
