"""Runtime supervisor — M0.0 minimum: load Adapter, run preflight, manage RuntimeHealth.

Bus / EngramStore are stubs in M0.0; M0.3 replaces with real adapters. The behavior
contract enforced here (PRECONDITION_FAILED on UNREADY, no worker start, exit code
78) is what TC-NEW-PREFLIGHT [CRITICAL] locks down for the rest of P1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from starling import _core

EX_CONFIG = 78  # POSIX sysexits.h

# Required capabilities for local-store profile in M0.0. M0.1 will pull these
# from the parsed profile config.
LOCAL_STORE_REQUIRED = (
    "transactional_outbox",
    "consumer_checkpoint",
    "engram_per_record_key",
    "c_plus_plus_core",
    "cross_partition_transaction",
    "tenant_isolation_storage_enforced",
    "testing_helper_marker",
)


class RuntimeUnreadyError(RuntimeError):
    def __init__(self, missing_capabilities: list[str]):
        super().__init__(
            "preflight failed: " + ", ".join(missing_capabilities)
        )
        self.missing_capabilities = missing_capabilities


@dataclass
class _StubBus:
    health_getter: Callable[[], _core.RuntimeHealth]
    written_count: int = 0

    def append_evidence(self, _engram) -> str:
        if self.health_getter() != _core.RuntimeHealth.READY:
            return "PRECONDITION_FAILED"
        self.written_count += 1
        return "OK"

    def write(self, _stmt) -> str:
        if self.health_getter() != _core.RuntimeHealth.READY:
            return "PRECONDITION_FAILED"
        self.written_count += 1
        return "OK"


@dataclass
class _StubEngramStore:
    appended_count: int = 0


@dataclass
class Runtime:
    capability: _core.ProfileCapability
    on_health_change: Optional[Callable[[dict], None]] = None
    idx_statement_id_tenant_present: Callable[[], bool] = field(
        default=lambda: True
    )

    foreground_workers_started: bool = False
    background_workers_started: bool = False
    exit_code: Optional[int] = None
    bus: _StubBus = field(init=False)
    engram_store: _StubEngramStore = field(default_factory=_StubEngramStore)

    _state: _core.RuntimeHealth = field(default=_core.RuntimeHealth.UNREADY)

    def __post_init__(self):
        self.bus = _StubBus(health_getter=lambda: self._state)

    def health(self) -> _core.RuntimeHealth:
        return self._state

    def start(self) -> None:
        missing: list[str] = []
        # Capability-level preflight.
        result = _core.preflight(self.capability, list(LOCAL_STORE_REQUIRED))
        if result.status == _core.PreflightStatus.UNREADY:
            missing.extend(result.missing)
        # Index-level preflight (branch a).
        if not self.idx_statement_id_tenant_present():
            missing.append("idx_statement_id_tenant")

        if missing:
            self._set_unready(missing)
            raise RuntimeUnreadyError(missing)

        self._set_ready()

    def _set_unready(self, missing: list[str]) -> None:
        self._state = _core.RuntimeHealth.UNREADY
        self.exit_code = EX_CONFIG
        self.foreground_workers_started = False
        self.background_workers_started = False
        if self.on_health_change:
            self.on_health_change({
                "event": "runtime.health_changed",
                "state": "UNREADY",
                "missing_capabilities": missing,
            })

    def _set_ready(self) -> None:
        self._state = _core.RuntimeHealth.READY
        self.foreground_workers_started = True
        self.background_workers_started = True
        if self.on_health_change:
            self.on_health_change({
                "event": "runtime.health_changed",
                "state": "READY",
                "missing_capabilities": [],
            })


__all__ = ["Runtime", "RuntimeUnreadyError", "EX_CONFIG"]
