"""Config routes — multi-model provider registry (read masked, upsert, bind, test).

The registry is `providers` (named secret-bearing configs) + `roles` (which
provider each job uses). extraction/embedding are live; chat is consumed by
converse() (2c); consolidation (#38-C) judges NORM gists in offline replay.
Hot-swap is per affected role:
rebinding/editing the extraction provider re-swaps the LLM adapter (O(1));
the embedding provider triggers a re-embed (expensive). GET never leaks keys.
"""
from __future__ import annotations

from anyio import to_thread
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel


class ProviderFields(BaseModel):
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    dim: int | None = None


class ConfigBody(BaseModel):
    # Partial registry update: upsert these providers and/or (re)bind these roles.
    providers: dict[str, ProviderFields] | None = None
    roles: dict[str, str] | None = None
    # #38-C v2 threshold surface: {min_holders, min_replay_count, min_confidence}.
    # None → unchanged; {} → reset to C++ defaults.
    gist_thresholds: dict | None = None


class TestBody(ProviderFields):
    name: str | None = None       # probe a stored provider by name (reuses its key)
    kind: str = "llm"             # "llm" | "embedder" — which live call to make


def _mask(d: dict) -> dict:
    out = {"provider": d.get("provider", "openai"),
           "model": d.get("model", ""), "base_url": d.get("base_url", ""),
           "key_set": bool(d.get("api_key"))}
    if "dim" in d:
        out["dim"] = d["dim"]
    return out


def _public(cfg) -> dict:
    return {"agent": cfg.agent, "tenant": cfg.tenant, "host": cfg.host, "port": cfg.port,
            "providers": {name: _mask(p) for name, p in cfg.providers.items()},
            "roles": dict(cfg.roles),
            "gist_thresholds": dict(cfg.gist_thresholds)}


def _merge_provider(dst: dict, body: ProviderFields) -> None:
    """Merge edits into a provider dict. Omitted/None fields are untouched, so an
    empty api_key on edit keeps the stored secret. Non-positive dim is ignored."""
    for k in ("provider", "model", "base_url", "api_key", "dim"):
        v = getattr(body, k, None)
        if v is None:
            continue
        if k == "api_key" and v == "":
            continue  # blank key on edit → keep existing secret
        if k == "dim" and (not isinstance(v, int) or v <= 0):
            continue
        dst[k] = v


def build_config_router(require_token) -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

    @router.get("/config")
    async def get_config(request: Request):
        return _public(request.app.state.config)

    @router.post("/config")
    async def post_config(body: ConfigBody, request: Request):
        cfg = request.app.state.config
        eng = request.app.state.engine
        # Upsert providers (preserve stored keys on blank-key edits).
        for name, pf in (body.providers or {}).items():
            _merge_provider(cfg.providers.setdefault(name, {}), pf)
        # Bind roles (validate target provider exists).
        for role, name in (body.roles or {}).items():
            if name and name not in cfg.providers:
                raise HTTPException(status_code=400, detail=f"unknown provider: {name}")
            cfg.roles[role] = name
        # #38-C v2 threshold surface: persist the gist knobs ({} resets to defaults).
        if body.gist_thresholds is not None:
            cfg.gist_thresholds = {
                k: body.gist_thresholds[k]
                for k in ("min_holders", "min_replay_count", "min_confidence",
                          "similarity_threshold", "entity_gist_enabled")
                if body.gist_thresholds.get(k) is not None
            }
        cfg.save()                                   # persist starling.json (0600)
        # Hot-swap only the live roles whose resolved provider changed: a role
        # was (re)bound, or its currently-bound provider was edited.
        touched_providers = set(body.providers or {})
        rebound = set(body.roles or {})
        def _affected(role: str) -> bool:
            return role in rebound or cfg.roles.get(role) in touched_providers
        warnings: list[str] = []
        if eng is not None:
            def _apply() -> None:
                if _affected("extraction"):
                    eng.set_llm(cfg.resolve_role("extraction") or {})
                # chat: rebound/edited, or unbound-and-extraction-changed (chat
                # falls back to the extraction provider).
                if _affected("chat") or (not cfg.roles.get("chat") and _affected("extraction")):
                    eng.set_chat(cfg.chat() or {})
                if _affected("embedding"):
                    # rebuild + re-embed; a rejected embedding provider returns a
                    # warning (non-fatal — the save still succeeds) instead of 500.
                    warn = eng.rebuild_embedder(cfg.embedding() or {})
                    if warn:
                        warnings.append(warn)
                if _affected("consolidation"):                    # #38-C consolidation role
                    eng.set_consolidation(cfg.resolve_role("consolidation") or {})
                if body.gist_thresholds is not None:              # #38-C v2 threshold surface
                    eng.set_gist_thresholds(cfg.gist_thresholds)
            await to_thread.run_sync(_apply)
        result = _public(cfg)
        if warnings:
            result["warnings"] = warnings
        return result

    @router.delete("/config/provider/{name}")
    async def delete_provider(name: str, request: Request):
        cfg = request.app.state.config
        eng = request.app.state.engine
        cfg.providers.pop(name, None)
        # Unbind any role pointing at the removed provider, then hot-swap it off.
        unbound = [r for r, n in cfg.roles.items() if n == name]
        for r in unbound:
            cfg.roles[r] = ""
        cfg.save()
        if eng is not None and unbound:
            def _apply() -> None:
                if "extraction" in unbound:
                    eng.set_llm({})            # → None (remember will 409 until rebound)
                if "chat" in unbound or "extraction" in unbound:
                    eng.set_chat(cfg.chat() or {})   # re-resolve (may fall back / go None)
                if "embedding" in unbound:
                    eng.rebuild_embedder({})   # → stub (recall degraded)
                if "consolidation" in unbound:
                    eng.set_consolidation({})  # → None (offline replay falls back to deterministic)
            await to_thread.run_sync(_apply)
        return _public(cfg)

    @router.post("/config/test")
    async def test_config(body: TestBody, request: Request):
        """Probe a provider config WITHOUT persisting it. Builds a transient
        adapter from (stored provider, by name, overlaid with inline fields) and
        issues one minimal live call. Never saves, never returns/logs the key.

        SECURITY: the stored key for provider `name` may only probe its own
        stored base_url. A base_url override (or a name with no stored key)
        requires a fresh api_key in the body — blocks credential exfiltration via
        a redirected probe. A caller-supplied key may go to a caller URL (their risk).
        """
        import time
        from starling.dashboard.engine import _build_chat_adapter, _build_embed_adapter
        cfg = request.app.state.config
        src = cfg.providers.get(body.name or "", {})
        probe = dict(src)
        for k in ("provider", "model", "base_url", "dim"):
            v = getattr(body, k, None)
            if v is None:
                continue
            if k == "dim" and (not isinstance(v, int) or v <= 0):
                continue
            probe[k] = v
        if body.api_key:
            probe["api_key"] = body.api_key
        else:
            overrides_endpoint = body.base_url is not None and body.base_url != src.get("base_url", "")
            if overrides_endpoint or not src.get("api_key"):
                return {"ok": False, "latency_ms": 0,
                        "detail": "需提供 api_key（改了 base_url 或未存密钥时不复用已存密钥）"}

        def _probe() -> tuple[bool, str]:
            if body.kind == "embedder":
                vec = _build_embed_adapter(probe).embed("ping")
                return True, f"dim={len(vec)}"
            r = _build_chat_adapter(probe).extract("ping", "")
            return bool(r.ok), ("ok" if r.ok else (r.error or "failed"))

        t0 = time.monotonic()
        try:
            ok, detail = await to_thread.run_sync(_probe)
            return {"ok": ok, "latency_ms": int((time.monotonic() - t0) * 1000), "detail": detail}
        except Exception as e:  # noqa: BLE001 — surface any build/probe failure as a failed test
            return {"ok": False, "latency_ms": int((time.monotonic() - t0) * 1000), "detail": str(e)}

    return router
