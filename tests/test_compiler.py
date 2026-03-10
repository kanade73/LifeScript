"""Tests for the LifeScript compiler."""

import json
from unittest.mock import patch

import pytest

from lifescript.compiler.compiler import Compiler, _build_system_prompt
from lifescript.exceptions import CompileError, LifeScriptError


def _mock_llm_response(result_dict: dict) -> str:
    """Create a mock LLM response string."""
    return json.dumps(result_dict)


class TestCompilerParsing:
    """Test response parsing and validation."""

    def setup_method(self):
        self.compiler = Compiler(model="test-model")

    def test_parse_valid_json(self):
        content = (
            '{"title": "test", "trigger": {"type": "interval", "seconds": 60}, "code": "x = 1"}'
        )
        result = self.compiler._parse_response(content)
        assert result["title"] == "test"

    def test_parse_json_with_code_fences(self):
        content = '```json\n{"title": "test", "trigger": {"type": "interval", "seconds": 60}, "code": "x = 1"}\n```'
        result = self.compiler._parse_response(content)
        assert result["title"] == "test"

    def test_parse_invalid_json_raises(self):
        with pytest.raises(CompileError, match="無効なJSON"):
            self.compiler._parse_response("not json at all")


class TestCompilerValidation:
    """Test the _validate_result method."""

    def setup_method(self):
        self.compiler = Compiler(model="test-model")

    def test_valid_interval_result(self):
        result = {
            "title": "test rule",
            "trigger": {"type": "interval", "seconds": 60},
            "code": "x = fetch_time_now()",
        }
        validated = self.compiler._validate_result(result)
        assert validated["trigger"]["seconds"] == 60

    def test_error_in_result_raises(self):
        with pytest.raises(CompileError, match="invalid"):
            self.compiler._validate_result({"error": "invalid code"})

    def test_missing_field_raises(self):
        with pytest.raises(CompileError, match="必須フィールド"):
            self.compiler._validate_result({"title": "test"})

    def test_invalid_trigger_type_raises(self):
        with pytest.raises(CompileError, match="辞書型"):
            self.compiler._validate_result({"title": "t", "trigger": "not a dict", "code": "x = 1"})

    def test_missing_seconds_raises(self):
        with pytest.raises(CompileError, match="seconds"):
            self.compiler._validate_result(
                {"title": "t", "trigger": {"type": "interval"}, "code": "x = 1"}
            )

    def test_disallowed_code_raises(self):
        with pytest.raises(LifeScriptError):
            self.compiler._validate_result(
                {"title": "t", "trigger": {"type": "interval", "seconds": 60}, "code": "import os"}
            )


class TestCompilerCompile:
    """Test the full compile flow with mocked LLM."""

    def setup_method(self):
        self.compiler = Compiler(model="test-model")

    @patch.object(Compiler, "_call_llm")
    def test_compile_success(self, mock_llm):
        mock_llm.return_value = _mock_llm_response(
            {
                "title": "テストルール",
                "trigger": {"type": "interval", "seconds": 300},
                "code": "t = fetch_time_now()",
            }
        )
        result = self.compiler.compile("every 5m { fetch(time.now) }")
        assert result["title"] == "テストルール"
        assert result["trigger"]["seconds"] == 300

    @patch.object(Compiler, "_call_llm")
    def test_compile_caches_result(self, mock_llm):
        mock_llm.return_value = _mock_llm_response(
            {
                "title": "cached",
                "trigger": {"type": "interval", "seconds": 60},
                "code": "x = 1",
            }
        )
        code = "every 1m { let x = 1 }"
        result1 = self.compiler.compile(code)
        result2 = self.compiler.compile(code)
        assert result1 == result2
        assert mock_llm.call_count == 1  # Only called once

    @patch.object(Compiler, "_call_llm")
    def test_recompile_invalidates_cache(self, mock_llm):
        mock_llm.return_value = _mock_llm_response(
            {
                "title": "fixed",
                "trigger": {"type": "interval", "seconds": 60},
                "code": "x = 1",
            }
        )
        code = "every 1m { let x = 1 }"
        # Put something in cache first
        self.compiler.compile(code)
        # Recompile should invalidate
        self.compiler.recompile_with_error(code, "x = 1/0", "ZeroDivisionError")
        assert mock_llm.call_count == 2


class TestSystemPrompt:
    """Test dynamic system prompt generation."""

    def test_prompt_includes_plugin_functions(self):
        prompt = _build_system_prompt()
        assert "fetch_time_now" in prompt
        assert "log" in prompt

    def test_prompt_includes_descriptions(self):
        prompt = _build_system_prompt()
        assert "現在時刻" in prompt
