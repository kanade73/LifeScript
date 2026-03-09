"""RestrictedPython sandbox for executing LLM-generated code safely."""

from RestrictedPython import compile_restricted, safe_globals, safe_builtins, PrintCollector
from RestrictedPython.Guards import guarded_iter_unpack_sequence

from ..exceptions import SandboxError
from ..plugins.time_plugin import fetch_time_now, fetch_time_today
from ..plugins.line_plugin import notify_line


def _build_globals() -> dict:
    restricted_builtins = dict(safe_builtins)
    restricted_builtins.update(
        {
            # Plugin functions (the only external calls allowed)
            "fetch_time_now": fetch_time_now,
            "fetch_time_today": fetch_time_today,
            "notify_line": notify_line,
            # Safe built-ins
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "len": len,
            "range": range,
            "list": list,
            "dict": dict,
        }
    )
    globs = dict(safe_globals)
    globs["__builtins__"] = restricted_builtins
    globs["_getiter_"] = iter
    globs["_getattr_"] = getattr
    globs["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence
    # RestrictedPython replaces print with _print_ / PrintCollector
    globs["_print_"] = PrintCollector
    return globs


def run_sandboxed(python_code: str) -> None:
    """Compile and execute Python code inside RestrictedPython."""
    try:
        byte_code = compile_restricted(python_code, filename="<lifescript>", mode="exec")
    except SyntaxError as e:
        raise SandboxError(f"Syntax error in compiled code: {e}") from e

    if byte_code is None:
        raise SandboxError("Code failed RestrictedPython compilation (returned None)")

    globs = _build_globals()
    try:
        exec(byte_code, globs)  # noqa: S102
    except Exception as e:
        raise SandboxError(f"{type(e).__name__}: {e}") from e
