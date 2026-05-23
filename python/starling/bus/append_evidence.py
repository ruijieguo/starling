"""High-level Python wrapper around _core.Bus.append_evidence."""

from typing import Optional

from starling import _core


class BusFacade:
    """Thin wrapper around the C++ Bus.

    M0.3 instantiates BusFacade directly with an SqliteAdapter handle.
    Task 10 (relax_preflight_for_m0_3) integrates it into the runtime
    construction path; M0.3's runtime.bus stays as the M0.2 stub-shape
    (_StubBus / _SqliteBackedBus) so TC-NEW-PREFLIGHT keeps passing.
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
