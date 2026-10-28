"""Starling Memory public API."""
from starling import _core
from starling.memory import (EmbedStats, Memory, PendingEvent,
                             RecallDegradedError,
                             make_anthropic_llm, make_openai_embedder,
                             make_openai_llm, make_stub_llm, RememberResult,
                             TickStats)
from starling.extractor.config import ExtractionConfig

# `Memory.remember_event` 的同 key 异文本 / 已放弃冲突。异常类注册在 C++ 绑定层
# (bind_13_memory_ops.cpp),这里只把它抬到公开命名空间。
EventConflict = _core.EventConflict

__all__ = ["_core", "Memory", "make_stub_llm", "make_openai_llm",
           "make_anthropic_llm", "make_openai_embedder", "RememberResult",
           "TickStats", "EmbedStats", "ExtractionConfig", "RecallDegradedError",
           "PendingEvent", "EventConflict"]
__version__ = "0.0.1"
