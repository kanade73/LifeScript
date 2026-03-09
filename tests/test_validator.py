"""Tests for the AST-based code validator."""

import pytest

from lifescript.compiler.validator import validate_python
from lifescript.exceptions import ValidationError


class TestValidateAllowed:
    """Allowed code should pass validation."""

    def test_plugin_function_calls(self):
        validate_python('notify_line("hello")')
        validate_python("t = fetch_time_now()")
        validate_python("d = fetch_time_today()")
        validate_python('w = fetch_weather("Tokyo")')

    def test_safe_builtins(self):
        validate_python("x = str(42)")
        validate_python("x = int('5')")
        validate_python("x = len([1, 2, 3])")
        validate_python("x = list(range(10))")

    def test_simple_logic(self):
        validate_python('if fetch_time_now() == "08:00":\n    notify_line("hi")')
        validate_python("for _ in range(3):\n    pass")
        validate_python("x = 1 + 2")

    def test_string_methods(self):
        """Attribute calls on safe types (e.g. str.upper) should be allowed."""
        validate_python('x = "hello".upper()')
        validate_python('x = "a,b,c".split(",")')

    def test_dict_methods(self):
        validate_python('d = {"a": 1}\nx = d.get("a", 0)')


class TestValidateBlocked:
    """Disallowed code should raise ValidationError."""

    def test_import_blocked(self):
        with pytest.raises(ValidationError, match="import"):
            validate_python("import os")

    def test_from_import_blocked(self):
        with pytest.raises(ValidationError, match="import"):
            validate_python("from os import path")

    def test_exec_blocked(self):
        with pytest.raises(ValidationError, match="禁止"):
            validate_python('exec("print(1)")')

    def test_eval_blocked(self):
        with pytest.raises(ValidationError, match="禁止"):
            validate_python('eval("1+1")')

    def test_dunder_import_blocked(self):
        with pytest.raises(ValidationError, match="禁止"):
            validate_python('__import__("os")')

    def test_open_blocked(self):
        with pytest.raises(ValidationError, match="禁止"):
            validate_python('open("/etc/passwd")')

    def test_unknown_function_blocked(self):
        with pytest.raises(ValidationError, match="許可されていない"):
            validate_python("unknown_func()")

    def test_global_blocked(self):
        with pytest.raises(ValidationError, match="global"):
            validate_python("global x")

    def test_nonlocal_blocked(self):
        with pytest.raises(ValidationError, match="nonlocal"):
            validate_python("def f():\n    nonlocal x")

    def test_del_blocked(self):
        with pytest.raises(ValidationError, match="del"):
            validate_python("x = 1\ndel x")

    def test_private_attribute_blocked(self):
        with pytest.raises(ValidationError, match="プライベート"):
            validate_python("x.__class__()")

    def test_syntax_error(self):
        with pytest.raises(ValidationError, match="構文エラー"):
            validate_python("def (broken")
