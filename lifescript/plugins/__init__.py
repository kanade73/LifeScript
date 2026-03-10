"""Plugin auto-discovery and registry.

Each plugin module in this package should define a PLUGIN_EXPORTS list:

    PLUGIN_EXPORTS = [
        {
            "name": "function_name",
            "func": callable,
            "signature": "function_name(arg: type) -> type",
            "description": "What it does",
        },
    ]

Call discover() once at startup to populate the registry.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

# {function_name: callable}
_functions: dict[str, Any] = {}
# {function_name: {"signature": str, "description": str}}
_descriptions: dict[str, dict[str, str]] = {}
_discovered = False


def discover() -> None:
    """Import all plugin modules and collect their PLUGIN_EXPORTS."""
    global _discovered  # noqa: PLW0603
    if _discovered:
        return
    for _importer, modname, _ispkg in pkgutil.iter_modules(__path__):
        if modname == "base":
            continue
        mod = importlib.import_module(f".{modname}", __package__)
        for export in getattr(mod, "PLUGIN_EXPORTS", []):
            _functions[export["name"]] = export["func"]
            _descriptions[export["name"]] = {
                "signature": export["signature"],
                "description": export["description"],
            }
    _discovered = True


def get_functions() -> dict[str, Any]:
    """Return {name: callable} for all registered plugin functions."""
    discover()
    return dict(_functions)


def get_descriptions() -> dict[str, dict[str, str]]:
    """Return {name: {signature, description}} for system prompt generation."""
    discover()
    return dict(_descriptions)


def get_allowed_names() -> set[str]:
    """Return the set of allowed function names for the validator."""
    discover()
    return set(_functions.keys())
