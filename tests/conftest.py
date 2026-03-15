"""Shared test fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _reset_compiler_cache():
    """Clear the compile cache between tests."""
    from lifescript.compiler.compiler import _cache

    _cache.clear()
    yield
    _cache.clear()
