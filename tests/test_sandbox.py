"""サンドボックスのテスト。"""

import pytest

from lifescript.sandbox.runner import run_sandboxed, reset_rate_limits
from lifescript.exceptions import SandboxError


class TestSandbox:
    def setup_method(self):
        reset_rate_limits()

    def test_simple_execution(self):
        run_sandboxed("x = 1 + 1")

    def test_syntax_error(self):
        with pytest.raises(SandboxError, match="構文エラー"):
            run_sandboxed("def (:")

    def test_timeout(self):
        with pytest.raises(SandboxError, match="タイムアウト"):
            run_sandboxed("while True: pass", timeout=1)

    def test_rate_limit(self):
        for i in range(60):
            run_sandboxed("x = 1", rule_id="test_rule")
        with pytest.raises(SandboxError, match="上限"):
            run_sandboxed("x = 1", rule_id="test_rule")

    def test_builtin_operations(self):
        run_sandboxed("x = len([1, 2, 3])")
        run_sandboxed("x = str(42)")
