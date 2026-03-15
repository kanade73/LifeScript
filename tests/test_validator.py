"""バリデータのテスト。"""

import pytest

from lifescript.compiler.validator import validate_python
from lifescript.exceptions import ValidationError


class TestValidator:
    def test_allowed_notify(self):
        validate_python('notify("hello")')

    def test_allowed_calendar_add(self):
        validate_python('calendar_add("meeting", "2025-01-01T10:00:00")')

    def test_allowed_calendar_read(self):
        validate_python('calendar_read(keyword="バイト")')

    def test_allowed_calendar_suggest(self):
        validate_python('calendar_suggest("休み", on="tomorrow")')

    def test_blocked_import(self):
        with pytest.raises(ValidationError, match="import"):
            validate_python("import os")

    def test_blocked_exec(self):
        with pytest.raises(ValidationError, match="禁止"):
            validate_python('exec("code")')

    def test_blocked_open(self):
        with pytest.raises(ValidationError, match="禁止"):
            validate_python('open("file.txt")')

    def test_blocked_unknown_function(self):
        with pytest.raises(ValidationError, match="許可されていない"):
            validate_python("unknown_func()")

    def test_allowed_builtins(self):
        validate_python("x = len([1, 2, 3])")

    def test_blocked_global(self):
        with pytest.raises(ValidationError, match="global"):
            validate_python("global x")

    def test_syntax_error(self):
        with pytest.raises(ValidationError, match="構文エラー"):
            validate_python("def (:")
