"""Convenience constructor for OpenAIAdapter.

Reads OPENAI_BASE_URL + OPENAI_API_KEY from env on the C++ side
(see Config::from_env). The api_key is never surfaced to Python — only
the Adapter object is returned. Callers cannot inspect or print the key.
"""

from __future__ import annotations

from starling import _core


def make_openai_adapter():
    """Return an OpenAIAdapter constructed from env vars.

    Raises RuntimeError if OPENAI_API_KEY is not set.
    """
    cfg = _core.OpenAIAdapterConfig.from_env()
    return _core.OpenAIAdapter(cfg)
