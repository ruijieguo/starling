"""Runtime supervisor — M0.0 minimum: load Adapter, run preflight, manage RuntimeHealth.

Bus / EngramStore are stubs in M0.0; M0.3 replaces with real adapters. The behavior
contract enforced here (PRECONDITION_FAILED on UNREADY, no worker start, exit code
78) is what TC-NEW-PREFLIGHT [CRITICAL] locks down for the rest of P1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

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
        # Store the list as args[0] so copy / cross-process round-trips
        # reconstruct the error correctly via the default __reduce__ path.
        # __str__ formats lazily so str(e) stays human-readable.
        super().__init__(list(missing_capabilities))
        self.missing_capabilities = list(missing_capabilities)

    def __str__(self) -> str:
        return "preflight failed: " + ", ".join(self.missing_capabilities)


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


class _SqliteBackedBus:
    """M0.2 SQLite-backed bus surface.

    Mirrors `_StubBus`'s shape so existing callers keep working when an adapter
    is supplied. The actual append-into-bus_events flow lands behind
    OutboxWriter in M0.3 (engram) + M0.4 (statement); M0.2 only needs the
    health gate and the adapter handle exposed to producers.
    """

    def __init__(self, adapter, *, health_getter: Callable[[], _core.RuntimeHealth]):
        self._adapter = adapter
        self._health_getter = health_getter
        self.written_count = 0

    def adapter(self):
        return self._adapter

    def append_evidence(self, _engram) -> str:
        if self._health_getter() != _core.RuntimeHealth.READY:
            return "PRECONDITION_FAILED"
        self.written_count += 1
        return "OK"

    def write(self, _stmt) -> str:
        if self._health_getter() != _core.RuntimeHealth.READY:
            return "PRECONDITION_FAILED"
        self.written_count += 1
        return "OK"


@dataclass
class Runtime:
    capability: _core.ProfileCapability
    on_health_change: Optional[Callable[[dict], None]] = None
    idx_statement_id_tenant_present: Callable[[], bool] = field(
        default=lambda: True
    )
    # M0.2: optional SqliteAdapter handle. When present, __post_init__ wires
    # _SqliteBackedBus instead of _StubBus. Default None preserves M0.0
    # call-site shape so TC-NEW-PREFLIGHT keeps passing unchanged.
    adapter: Optional[Any] = None

    foreground_workers_started: bool = False
    background_workers_started: bool = False
    exit_code: Optional[int] = None
    bus: Any = field(init=False)
    engram_store: _StubEngramStore = field(default_factory=_StubEngramStore)

    _state: _core.RuntimeHealth = field(default=_core.RuntimeHealth.UNREADY)

    def __post_init__(self):
        if self.adapter is None:
            # M0.0 stub path stays byte-stable.
            self.bus = _StubBus(health_getter=lambda: self._state)
        else:
            self.bus = _SqliteBackedBus(
                self.adapter, health_getter=lambda: self._state
            )

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
        # exit_code is fail-closed-only; never cleared on a later transition
        # back to READY (process-exit signal, not transient state).
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
        # Only safe to call after start()'s preflight has passed. Future
        # degraded→ready transitions must re-run preflight before calling this.
        self._state = _core.RuntimeHealth.READY
        self.foreground_workers_started = True
        self.background_workers_started = True
        if self.on_health_change:
            self.on_health_change({
                "event": "runtime.health_changed",
                "state": "READY",
                "missing_capabilities": [],
            })


def _build_local_store_sqlite_runtime(db_path: Path) -> "Runtime":
    """Construct a Runtime backed by a real SqliteAdapter at db_path.

    The adapter's declare_capability() reports `engram_per_record_key=False`
    and `testing_helper_marker=False` in M0.2 (KMS lands in M0.3, marker is
    dev-only). Acceptance tests that need to reach READY must call the
    M0.2-only relax_preflight_for_m0_2() helper from the testing subpackage
    before invoking this.
    """
    adapter = _core.SqliteAdapter.open(str(db_path))
    cap = adapter.declare_capability()

    # idx_statement_id_tenant_present: real check against sqlite_master.
    # Captures db_path (not the adapter handle) to avoid a second sqlite3
    # connection contending for the WAL writer lock with the C++ side; the
    # Python sqlite3 read is open-and-close, scoped to the call.
    def _idx_present() -> bool:
        import sqlite3
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='index' AND name='idx_statement_id_tenant'"
            ).fetchone()
            return row is not None

    return Runtime(
        capability=cap,
        adapter=adapter,
        idx_statement_id_tenant_present=_idx_present,
    )


__all__ = [
    "Runtime",
    "RuntimeUnreadyError",
    "EX_CONFIG",
    "LOCAL_STORE_REQUIRED",
    "_build_local_store_sqlite_runtime",
]
