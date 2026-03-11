"""RestrictedPython サンドボックス — LLM 生成コードを安全に実行する。

セキュリティ第二層: RestrictedPython でコードをコンパイルし、
スレッドベースのタイムアウト（30秒）とレートリミット（60回/分）付きで実行する。
"""

from __future__ import annotations

import threading

from RestrictedPython import compile_restricted, safe_globals, safe_builtins, PrintCollector
from RestrictedPython.Guards import guarded_iter_unpack_sequence

from ..exceptions import SandboxError
from ..plugins import get_functions

# Default timeout for sandboxed execution (seconds)
_EXEC_TIMEOUT = 30

# Rate limiter: track execution counts per rule
_exec_counts: dict[str, int] = {}
_exec_lock = threading.Lock()
_MAX_EXECUTIONS_PER_MINUTE = 60


def _build_globals() -> dict:
    restricted_builtins = dict(safe_builtins)

    # Add all plugin functions dynamically
    restricted_builtins.update(get_functions())

    # Safe built-ins
    restricted_builtins.update(
        {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "len": len,
            "range": range,
            "list": list,
            "dict": dict,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "sorted": sorted,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "any": any,
            "all": all,
        }
    )
    globs = dict(safe_globals)
    globs["__builtins__"] = restricted_builtins
    globs["_getiter_"] = iter
    globs["_getattr_"] = getattr
    globs["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence
    globs["_print_"] = PrintCollector
    return globs


class _TimeoutError(Exception):
    pass


def _check_rate_limit(rule_id: str | None) -> None:
    """ルールが実行回数の上限を超えていないかチェックする。"""
    if rule_id is None:
        return
    with _exec_lock:
        count = _exec_counts.get(rule_id, 0)
        if count >= _MAX_EXECUTIONS_PER_MINUTE:
            raise SandboxError(
                f"実行回数の上限に達しました（{_MAX_EXECUTIONS_PER_MINUTE}回/分）。"
                "しばらく待ってから再試行してください。"
            )
        _exec_counts[rule_id] = count + 1


def reset_rate_limits() -> None:
    """全レートリミットカウンターをリセットする。スケジューラから定期的に呼ばれる。"""
    with _exec_lock:
        _exec_counts.clear()


def run_sandboxed(
    python_code: str, *, timeout: int = _EXEC_TIMEOUT, rule_id: str | None = None
) -> None:
    """Python コードを RestrictedPython 内でタイムアウト付きコンパイル・実行する。"""
    _check_rate_limit(rule_id)

    # Set rule context for log plugin
    from ..plugins.log_plugin import _set_rule_context

    _set_rule_context(rule_id)

    try:
        byte_code = compile_restricted(python_code, filename="<lifescript>", mode="exec")
    except SyntaxError as e:
        raise SandboxError(f"コンパイル済みコードに構文エラーがあります: {e}") from e

    if byte_code is None:
        raise SandboxError("RestrictedPythonのコンパイルに失敗しました（Noneが返されました）")

    globs = _build_globals()

    # Use threading-based timeout (works on all platforms)
    result: list[Exception | None] = [None]

    def _exec_target() -> None:
        try:
            exec(byte_code, globs)  # noqa: S102
        except Exception as e:
            result[0] = e

    thread = threading.Thread(target=_exec_target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        raise SandboxError(
            f"実行がタイムアウトしました（{timeout}秒）。無限ループの可能性があります。"
        )

    if result[0] is not None:
        e = result[0]
        raise SandboxError(f"{type(e).__name__}: {e}") from e
