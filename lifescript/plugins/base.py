from abc import ABC, abstractmethod


class Plugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def requires_connection(self) -> bool:
        return False

    def check_connection(self) -> bool:
        return True
