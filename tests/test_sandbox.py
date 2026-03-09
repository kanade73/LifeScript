"""Tests for the RestrictedPython sandbox runner."""

import pytest

from lifescript.sandbox.runner import run_sandboxed, reset_rate_limits, _exec_counts, _exec_lock
from lifescript.exceptions import SandboxError


class TestSandboxExecution:
    """Test basic sandboxed code execution."""

    def test_simple_assignment(self):
        run_sandboxed("x = 1 + 2")

    def test_plugin_function_available(self):
        """Plugin functions should be in scope."""
        run_sandboxed("t = fetch_time_now()")

    def test_fetch_time_today_available(self):
        run_sandboxed("d = fetch_time_today()")

    def test_safe_builtins_available(self):
        run_sandboxed("x = len([1, 2, 3])")
        run_sandboxed("x = str(42)")
        run_sandboxed("x = list(range(5))")

    def test_for_loop(self):
        run_sandboxed("total = 0\nfor i in range(10):\n    total = total + i")

    def test_if_statement(self):
        run_sandboxed("x = 1\nif x > 0:\n    x = x + 1")


class TestSandboxBlocked:
    """Test that dangerous operations are blocked."""

    def test_import_blocked(self):
        with pytest.raises(SandboxError):
            run_sandboxed("import os")

    def test_open_blocked(self):
        with pytest.raises(SandboxError):
            run_sandboxed('open("/etc/passwd")')

    def test_syntax_error(self):
        with pytest.raises(SandboxError, match="構文エラー"):
            run_sandboxed("def (broken")

    def test_runtime_error_reported(self):
        with pytest.raises(SandboxError, match="ZeroDivisionError"):
            run_sandboxed("x = 1 / 0")


class TestSandboxTimeout:
    """Test execution timeout."""

    def test_timeout_triggers(self):
        with pytest.raises(SandboxError, match="タイムアウト"):
            run_sandboxed("while True:\n    pass", timeout=1)


class TestRateLimiting:
    """Test execution rate limiting."""

    def setup_method(self):
        reset_rate_limits()

    def teardown_method(self):
        reset_rate_limits()

    def test_rate_limit_enforced(self):
        # Manually fill up the counter
        with _exec_lock:
            _exec_counts["test_rule"] = 60

        with pytest.raises(SandboxError, match="上限"):
            run_sandboxed("x = 1", rule_id="test_rule")

    def test_rate_limit_reset(self):
        with _exec_lock:
            _exec_counts["test_rule"] = 60

        reset_rate_limits()

        # Should work now
        run_sandboxed("x = 1", rule_id="test_rule")

    def test_no_rate_limit_without_rule_id(self):
        """When rule_id is None, rate limiting is skipped."""
        run_sandboxed("x = 1", rule_id=None)
