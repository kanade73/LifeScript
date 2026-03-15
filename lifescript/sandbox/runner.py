"""RestrictedPython サンドボックス — LLM 生成コードを安全に実行する。"""

from __future__ import annotations

import threading

from RestrictedPython import compile_restricted, safe_globals, safe_builtins, PrintCollector
from RestrictedPython.Guards import guarded_iter_unpack_sequence

from ..exceptions import SandboxError
from ..functions import FUNCTION_MAP

_EXEC_TIMEOUT = 30

_exec_counts: dict[str, int] = {}
_exec_lock = threading.Lock()
_MAX_EXECUTIONS_PER_MINUTE = 60


def _build_globals() -> dict:
    restricted_builtins = dict(safe_builtins)

    # 関数ライブラリを登録
    restricted_builtins.update(FUNCTION_MAP)

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


def _check_rate_limit(rule_id: str | None) -> None:
    if rule_id is None:
        return
    with _exec_lock:
        count = _exec_counts.get(rule_id, 0)
        if count >= _MAX_EXECUTIONS_PER_MINUTE:
            raise SandboxError(
                f"実行回数の上限に達しました（{_MAX_EXECUTIONS_PER_MINUTE}回/分）。"
            )
        _exec_counts[rule_id] = count + 1


def reset_rate_limits() -> None:
    with _exec_lock:
        _exec_counts.clear()


def run_sandboxed(
    python_code: str, *, timeout: int = _EXEC_TIMEOUT, rule_id: str | None = None
) -> None:
    """Python コードを RestrictedPython 内でタイムアウト付きで実行する。"""
    _check_rate_limit(rule_id)

    try:
        byte_code = compile_restricted(python_code, filename="<lifescript>", mode="exec")
    except SyntaxError as e:
        raise SandboxError(f"コンパイル済みコードに構文エラーがあります: {e}") from e

    if byte_code is None:
        raise SandboxError("RestrictedPythonのコンパイルに失敗しました")

    globs = _build_globals()

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
        raise SandboxError(f"実行がタイムアウトしました（{timeout}秒）。")

    if result[0] is not None:
        e = result[0]
        raise SandboxError(f"{type(e).__name__}: {e}") from e
