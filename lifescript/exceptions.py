class LifeScriptError(Exception):
    """Base exception for all LifeScript errors."""


class CompileError(LifeScriptError):
    """Raised when LifeScript fails to compile to Python."""


class ValidationError(LifeScriptError):
    """Raised when generated Python fails static analysis."""


class ServiceNotConnectedError(LifeScriptError):
    def __init__(self, service: str):
        super().__init__(
            f"LifeScriptError: {service} is not connected.\n"
            f"Please link your {service} account from Settings."
        )
        self.service = service


class SandboxError(LifeScriptError):
    """Raised when sandboxed execution fails."""
