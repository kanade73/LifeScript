"""コンパイラのテスト。"""

import json
from unittest.mock import MagicMock, patch

import pytest

from lifescript.compiler.compiler import Compiler
from lifescript.exceptions import CompileError, ValidationError


@pytest.fixture
def compiler():
    return Compiler(model="test-model")


def _mock_llm_response(result_dict: dict) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = json.dumps(result_dict, ensure_ascii=False)
    return resp


class TestCompiler:
    def test_compile_success(self, compiler):
        result_dict = {
            "title": "テスト通知",
            "trigger": {"type": "interval", "seconds": 3600},
            "code": 'notify("Hello")',
        }
        with patch("litellm.completion", return_value=_mock_llm_response(result_dict)):
            result = compiler.compile('notify("Hello")')
        assert result["title"] == "テスト通知"
        assert result["code"] == 'notify("Hello")'
        assert result["trigger"]["seconds"] == 3600

    def test_compile_error_response(self, compiler):
        result_dict = {"error": "無効な構文です"}
        with patch("litellm.completion", return_value=_mock_llm_response(result_dict)):
            with pytest.raises(CompileError, match="無効な構文"):
                compiler.compile("invalid code")

    def test_compile_missing_field(self, compiler):
        result_dict = {"title": "test"}
        with patch("litellm.completion", return_value=_mock_llm_response(result_dict)):
            with pytest.raises(CompileError, match="必須フィールド"):
                compiler.compile("some code")

    def test_compile_caching(self, compiler):
        result_dict = {
            "title": "cached",
            "trigger": {"type": "interval", "seconds": 60},
            "code": 'notify("cached")',
        }
        with patch("litellm.completion", return_value=_mock_llm_response(result_dict)) as mock:
            compiler.compile("test code")
            compiler.compile("test code")
        assert mock.call_count == 1

    def test_compile_validation_failure(self, compiler):
        result_dict = {
            "title": "bad code",
            "trigger": {"type": "interval", "seconds": 60},
            "code": "import os",
        }
        with patch("litellm.completion", return_value=_mock_llm_response(result_dict)):
            with pytest.raises((CompileError, ValidationError)):
                compiler.compile("import os")

    def test_compile_repeat_10min_expansion(self, compiler):
        result_dict = {
            "title": "展開テスト",
            "trigger": {"type": "interval", "seconds": 3600},
            "code": 'notify("ok")',
        }
        dsl = """
repeat_10min:
  月:
    09:00-09:20: 英語
  火:
    10:00: ストレッチ
""".strip()

        with patch("litellm.completion", return_value=_mock_llm_response(result_dict)) as mock:
            compiler.compile(dsl)

        args = mock.call_args.kwargs
        user_msg = args["messages"][1]["content"]
        assert "calendar.add(\"英語\"" in user_msg
        assert "calendar.add(\"ストレッチ\"" in user_msg
        assert "note=\"repeat_10min\"" in user_msg

    def test_compile_repeat_10min_daily_expansion(self, compiler):
        result_dict = {
            "title": "日次展開テスト",
            "trigger": {"type": "interval", "seconds": 3600},
            "code": 'notify("ok")',
        }
        dsl = """
repeat_10min:
  毎日:
    07:00: 水やり
""".strip()

        with patch("litellm.completion", return_value=_mock_llm_response(result_dict)) as mock:
            compiler.compile(dsl)

        args = mock.call_args.kwargs
        user_msg = args["messages"][1]["content"]
        assert user_msg.count("calendar.add(\"水やり\"") == 28
        assert "note=\"repeat_10min\"" in user_msg
