"""High-level Python wrapper around _core.Bus.append_evidence."""

from typing import Optional

from starling import _core


class BusFacade:
    """Thin wrapper around the C++ Bus.

    Factory-built runtimes (`_build_local_store_sqlite_runtime`) expose
    BusFacade as `rt.bus`. Runtime(capability=cap) constructed directly
    (no adapter) retains _StubBus so TC-NEW-PREFLIGHT keeps passing.
    """

    def __init__(self, adapter: "_core.SqliteAdapter") -> None:
        self._adapter = adapter
        self._bus = _core.Bus(adapter)

    def append_evidence(
        self,
        engram_input: "_core.EngramInput",
        causation_parent: Optional[str] = None,
    ) -> dict:
        return self._bus.append_evidence(engram_input, causation_parent)
