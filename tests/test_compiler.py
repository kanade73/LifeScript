"""コンパイラのテスト。"""

import json
from datetime import datetime, timedelta, timezone
import re
from unittest.mock import MagicMock, patch

import pytest

from lifescript.compiler.compiler import Compiler
from lifescript.exceptions import CompileError, ValidationError
from lifescript.holidays import clear_cache as clear_holiday_cache


@pytest.fixture
def compiler():
    Compiler.clear_cache()
    clear_holiday_cache()
    return Compiler(model="test-model")


def _mock_llm_response(result_dict: dict) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = json.dumps(result_dict, ensure_ascii=False)
    return resp


def _mock_raw_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = text
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

    def test_compile_repeat_10min_weekday_only_uses_holidays(self, compiler):
        jst = timezone(timedelta(hours=9))
        today = datetime.now(jst).date()
        this_week_start = today - timedelta(days=today.weekday())
        holiday = this_week_start  # 平日（月曜）を祝日扱いにする

        holiday_resp = _mock_raw_response(json.dumps({
            "holidays": [{"date": holiday.isoformat(), "name": "テスト祝日"}]
        }))
        compile_resp = _mock_llm_response({
            "title": "平日展開",
            "trigger": {"type": "interval", "seconds": 3600},
            "code": 'notify("ok")',
        })

        dsl = """
repeat_10min:
  平日のみ:
    08:00: 朝リマインド
""".strip()

        def _side_effect(**kwargs):
            messages = kwargs.get("messages", [])
            text = "\n".join(str(m.get("content", "")) for m in messages if isinstance(m, dict))
            if "日本の祝日" in text:
                return holiday_resp
            return compile_resp

        with patch("lifescript.llm.completion", side_effect=_side_effect) as mock:
            compiler.compile(dsl)

        user_msg = mock.call_args.kwargs["messages"][1]["content"]
        starts = re.findall(r'start="(\d{4}-\d{2}-\d{2})T', user_msg)
        assert starts
        assert holiday.isoformat() not in starts
        assert all(datetime.fromisoformat(s).weekday() < 5 for s in starts)

    def test_compile_repeat_10min_weekend_holiday_uses_holidays(self, compiler):
        jst = timezone(timedelta(hours=9))
        today = datetime.now(jst).date()
        this_week_start = today - timedelta(days=today.weekday())
        holiday = this_week_start  # 平日（月曜）を祝日扱いにする

        holiday_resp = _mock_raw_response(json.dumps({
            "holidays": [{"date": holiday.isoformat(), "name": "テスト祝日"}]
        }))
        compile_resp = _mock_llm_response({
            "title": "土日祝展開",
            "trigger": {"type": "interval", "seconds": 3600},
            "code": 'notify("ok")',
        })

        dsl = """
repeat_10min:
  土日祝のみ:
    20:00: 夜リマインド
""".strip()

        def _side_effect(**kwargs):
            messages = kwargs.get("messages", [])
            text = "\n".join(str(m.get("content", "")) for m in messages if isinstance(m, dict))
            if "日本の祝日" in text:
                return holiday_resp
            return compile_resp

        with patch("lifescript.llm.completion", side_effect=_side_effect) as mock:
            compiler.compile(dsl)

        user_msg = mock.call_args.kwargs["messages"][1]["content"]
        starts = re.findall(r'start="(\d{4}-\d{2}-\d{2})T', user_msg)
        assert starts
        assert holiday.isoformat() in starts
        for s in starts:
            d = datetime.fromisoformat(s).date()
            assert d.weekday() >= 5 or d == holiday

    def test_compile_repeat_10min_holiday_fetch_failure_falls_back(self, compiler):
        result_dict = {
            "title": "フォールバック",
            "trigger": {"type": "interval", "seconds": 3600},
            "code": 'notify("ok")',
        }
        dsl = """
repeat_10min:
  平日のみ:
    08:00: 朝リマインド
""".strip()

        with (
            patch("lifescript.compiler.compiler.get_holiday_dates_between", side_effect=RuntimeError("boom")),
            patch("litellm.completion", return_value=_mock_llm_response(result_dict)) as mock,
        ):
            compiler.compile(dsl)

        user_msg = mock.call_args.kwargs["messages"][1]["content"]
        starts = re.findall(r'start="(\d{4}-\d{2}-\d{2})T', user_msg)
        assert starts
        assert all(datetime.fromisoformat(s).weekday() < 5 for s in starts)
