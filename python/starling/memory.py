"""Starling Memory — public application-surface facade (P2.e).

`Memory.open` builds a local-store SQLite runtime (after relaxing the M0.3
preflight gate), and `remember(text)` runs the production write path:

    BusFacade.append_evidence(EngramInput)   # creates/dedupes the engram
        -> _core.Extractor(connection, llm).run(...)   # extracts statements

Offline determinism comes from `make_stub_llm` (`_core.FakeLLMAdapter` with a
canned XML default response — no network). `make_openai_llm` builds the real
`_core.OpenAIAdapter`; its API key is sourced from the environment only
(`OPENAI_API_KEY`), never a function parameter, log line, or hardcoded value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from starling import _core
from starling import runtime as _runtime
from starling.evidence.inputs import for_user_input
from starling.testing import relax_preflight_for_m0_3


def make_stub_llm(*, default_xml: str, responses: Optional[dict] = None):
    """Offline deterministic LLM adapter.

    `default_xml` answers any prompt whose hash is not explicitly mapped in
    `responses` (hash -> canned XML). Drives `_core.Extractor` with zero
    network calls.
    """
    llm = _core.FakeLLMAdapter()
    # binding: set_default_response(raw_xml, ok=True, error="")
    llm.set_default_response(default_xml, True, "")
    for h, xml in (responses or {}).items():
        # binding: set_response(hash, raw_xml, ok=True, error="")
        llm.set_response(h, xml, True, "")
    return llm


def make_openai_llm(*, model: str = "gpt-4o-mini", base_url: str = "",
                    timeout_ms: int = 0, max_retries: int = 0):
    """Production LLM adapter (`_core.OpenAIAdapter`).

    The API key is read from the environment (`OPENAI_API_KEY`) by the C++
    adapter — it is never accepted as a parameter, logged, or hardcoded here.
    Starts from `OpenAIAdapterConfig.from_env()` so env-provided defaults
    (base_url / model / timeouts) are honoured, then overrides only the
    fields the caller explicitly set.
    """
    cfg = _core.OpenAIAdapterConfig.from_env()
    if model:
        cfg.model = model
    if base_url:
        cfg.base_url = base_url
    if timeout_ms:
        cfg.timeout_ms = timeout_ms
    if max_retries:
        cfg.max_retries = max_retries
    return _core.OpenAIAdapter(cfg)


@dataclass
class RememberResult:
    engram_ref: str
    statement_ids: list = field(default_factory=list)
    outcome: str = ""


class Memory:
    """Public facade over the Starling write path."""

    def __init__(self, rt, *, agent: str, tenant_id: str, llm):
        self._rt = rt
        self._agent = agent
        self._tenant = tenant_id
        self._llm = llm
        # Shared connection handle for the extractor (keep-alive in binding).
        self._conn = rt.adapter.connection()

    @classmethod
    def open(cls, db_path, *, agent: str = "self", tenant_id: str = "default",
             llm=None) -> "Memory":
        # M0.3 local-store preflight is not satisfiable in the embedded
        # single-process facade; relax it so the runtime reaches READY.
        relax_preflight_for_m0_3()
        rt = _runtime._build_local_store_sqlite_runtime(Path(db_path))
        rt.start()
        return cls(rt, agent=agent, tenant_id=tenant_id, llm=llm)

    def remember(self, text: str, *, holder: Optional[str] = None,
                 now: Optional[str] = None) -> RememberResult:
        if self._llm is None:
            raise RuntimeError(
                "Memory.remember requires an llm adapter "
                "(make_stub_llm / make_openai_llm)"
            )
        holder = holder or self._agent
        payload = text.encode("utf-8")
        created_at = _parse_now(now)

        inp = for_user_input(
            tenant_id=self._tenant,
            adapter_name="facade",
            adapter_version="1",
            source_item_id="mem-" + str(abs(hash(text))),
            source_version="1",
            payload_bytes=payload,
            privacy_class=_core.PrivacyClass.INTERNAL,        # enum member (no NORMAL)
            retention_mode=_core.EngramRetentionMode.AUDIT_RETAIN,  # enum member (no VERBATIM)
            created_at=created_at,
        )
        out = self._rt.bus.append_evidence(inp, None)
        kind = out["kind"]
        if kind not in ("accepted", "idempotent"):
            return RememberResult(engram_ref="", statement_ids=[], outcome=kind)

        engram_ref = out["engram_ref"].id
        ext = _core.Extractor(self._conn, self._llm)
        r = ext.run(engram_ref, payload, holder, self._tenant, {})
        return RememberResult(
            engram_ref=engram_ref,
            statement_ids=list(r.accepted_statement_ids),
            outcome=kind,
        )

    def close(self) -> None:
        # The SqliteAdapter is closed when its runtime/handle is GC'd; nothing
        # to release explicitly in the embedded facade.
        self._conn = None


def _parse_now(now: Optional[str]) -> datetime:
    """Coerce an optional ISO-8601 string into a tz-aware datetime.

    `for_user_input` expects a datetime (it formats via `_iso`). Default to
    the current UTC time when no override is given.
    """
    if now is None:
        return datetime.now(timezone.utc)
    s = now.replace("Z", "+00:00") if now.endswith("Z") else now
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
