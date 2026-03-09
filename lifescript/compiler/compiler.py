"""LifeScript → Python compiler via LLM (LiteLLM)."""

from __future__ import annotations

import json
import re
from typing import Any

import litellm

from ..exceptions import CompileError
from .validator import validate_python

SYSTEM_PROMPT = """\
You are a LifeScript-to-Python compiler.

LifeScript is a DSL for life automation. Compile the given LifeScript into Python \
that uses ONLY the functions listed below. Output JSON and nothing else.

## AVAILABLE FUNCTIONS
- fetch_time_now()          → str  current time as "HH:MM"
- fetch_time_today()        → dict {"weekday": "Monday", "date": "2024-01-01"}
- notify_line(message: str) → None  sends LINE message to the connected user

## LIFESCRIPT → PYTHON TRANSLATION
| LifeScript                     | Python                        |
|--------------------------------|-------------------------------|
| fetch(time.now)                | fetch_time_now()              |
| fetch(time.today)              | fetch_time_today()            |
| notify(LINE, "msg")            | notify_line("msg")            |
| let x = expr                   | x = expr                      |
| when cond { ... }              | if cond: ...                  |
| repeat N { ... }               | for _ in range(N): ...        |
| every day { ... }              | trigger=interval(seconds=60)  |
| every Nh { ... }               | trigger=interval(seconds=N*3600) |
| every Nm { ... }               | trigger=interval(seconds=N*60) |

## RULES
- No import statements
- No file system access
- No network calls (use plugin functions only)
- No exec, eval, __import__, open, os, sys
- Only the plugin functions above may be called

## OUTPUT FORMAT (JSON only – no markdown, no explanation)
{
  "title": "brief human-readable description (Japanese OK)",
  "trigger": {"type": "interval", "seconds": <integer>},
  "code": "<Python body as a plain string, no function def>"
}

If the LifeScript is invalid or uses unsupported features:
{"error": "<explanation>"}
"""


class Compiler:
    def __init__(self, model: str, api_base: str | None = None) -> None:
        self.model = model
        self.api_base = api_base

    def _call_llm(self, messages: list[dict]) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        try:
            response = litellm.completion(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise CompileError(f"LLM call failed: {e}") from e

    def _parse_response(self, content: str) -> dict:
        # Strip markdown code fences if present
        content = re.sub(r"```(?:json)?\s*", "", content).strip().rstrip("`").strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise CompileError(f"LLM returned invalid JSON: {e}\nContent: {content[:300]}") from e

    def compile(self, lifescript_code: str) -> dict[str, Any]:
        """Compile LifeScript to Python. Returns dict with title, trigger, code."""
        content = self._call_llm(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Compile this LifeScript:\n\n{lifescript_code}"},
            ]
        )
        result = self._parse_response(content)

        if "error" in result:
            raise CompileError(result["error"])

        for field in ("title", "trigger", "code"):
            if field not in result:
                raise CompileError(f"LLM response missing field: '{field}'")

        # Validate trigger structure
        trigger = result["trigger"]
        if not isinstance(trigger, dict):
            raise CompileError(f"trigger must be a dict, got {type(trigger).__name__}")
        if "seconds" not in trigger:
            raise CompileError("trigger must contain 'seconds' key")
        try:
            result["trigger"]["seconds"] = int(trigger["seconds"])
        except (TypeError, ValueError) as e:
            raise CompileError(f"trigger['seconds'] must be a number: {e}") from e

        validate_python(result["code"])
        return result

    def recompile_with_error(
        self, lifescript_code: str, python_code: str, error: str
    ) -> dict[str, Any]:
        """Ask the LLM to fix a runtime error in previously generated Python."""
        content = self._call_llm(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"This LifeScript:\n\n{lifescript_code}\n\n"
                        f"Was compiled to:\n\n{python_code}\n\n"
                        f"But caused this error at runtime:\n\n{error}\n\n"
                        "Please return a corrected compilation."
                    ),
                },
            ]
        )
        result = self._parse_response(content)

        if "error" in result:
            raise CompileError(result["error"])

        for field in ("title", "trigger", "code"):
            if field not in result:
                raise CompileError(f"LLM response missing field: '{field}'")

        trigger = result["trigger"]
        if not isinstance(trigger, dict):
            raise CompileError(f"trigger must be a dict, got {type(trigger).__name__}")
        if "seconds" not in trigger:
            raise CompileError("trigger must contain 'seconds' key")
        try:
            result["trigger"]["seconds"] = int(trigger["seconds"])
        except (TypeError, ValueError) as e:
            raise CompileError(f"trigger['seconds'] must be a number: {e}") from e

        validate_python(result["code"])
        return result
