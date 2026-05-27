"""
starling.tom — public API for 09_tom Theory-of-Mind subsystem.

Re-exports C++ bindings from starling._core and Pythonic wrappers
from starling.tom.primitives.
"""
from starling._core import (
    # Data types
    FactKey,
    KnowsResult,
    Misalignment,
    SharedFact,
    CommonGroundEntry,
    Context,
    TickStats,
    # Engine class
    ToMEngine,
    # Exceptions
    NestingDepthOverflow,
    # Low-level free functions (direct C++ bindings)
    belief_tracker_tick,
)
from starling.tom.primitives import (
    what_does_X_believe,
    does_X_know,
    find_misalignment,
    shared_with,
)

__all__ = [
    # Data types
    "FactKey",
    "KnowsResult",
    "Misalignment",
    "SharedFact",
    "CommonGroundEntry",
    "Context",
    "TickStats",
    # Engine
    "ToMEngine",
    # Exceptions
    "NestingDepthOverflow",
    # Primitives (Pythonic wrappers)
    "what_does_X_believe",
    "does_X_know",
    "find_misalignment",
    "shared_with",
    # Direct C++ binding
    "belief_tracker_tick",
]
