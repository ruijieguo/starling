"""Config routes — read (masked) and update LLM/embedder config + hot-swap."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel


class ProviderBody(BaseModel):
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    dim: int | None = None


class TestBody(ProviderBody):
    kind: str = "llm"  # "llm" | "embedder"


class ConfigBody(BaseModel):
    llm: ProviderBody | None = None
    embedder: ProviderBody | None = None


def _mask(d: dict) -> dict:
    out = {"provider": d.get("provider", "openai"),
           "model": d.get("model", ""), "base_url": d.get("base_url", ""),
           "key_set": bool(d.get("api_key"))}
    if "dim" in d:
        out["dim"] = d["dim"]
    return out


def _public(cfg) -> dict:
    return {"agent": cfg.agent, "tenant": cfg.tenant, "host": cfg.host, "port": cfg.port,
            "llm": _mask(cfg.llm), "embedder": _mask(cfg.embedder)}


def _merge(dst: dict, body) -> None:
    if body is None:
        return
    for k in ("provider", "model", "base_url", "api_key", "dim"):
        v = getattr(body, k, None)
        if v is None:
            continue
        if k == "dim" and (not isinstance(v, int) or v <= 0):
            continue  # ignore non-positive dim (invalid embedding dimension)
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
        llm_changed = body.llm is not None
        emb_changed = body.embedder is not None
        _merge(cfg.llm, body.llm)
        _merge(cfg.embedder, body.embedder)
        cfg.save()                                   # persist starling.json (0600)
        if eng is not None:
            if llm_changed:
                eng.set_llm(cfg.llm)
            if emb_changed:
                eng.rebuild_embedder(cfg.embedder)   # rebuild + re-embed
        return _public(cfg)

    @router.post("/config/test")
    async def test_config(body: TestBody, request: Request):
        """Probe a candidate provider config WITHOUT persisting it.

        Builds a transient adapter from (saved config overlaid with the body)
        and issues one minimal live call. Never saves, never returns/logs the
        key; detail carries only a status/error code, never secret material.

        SECURITY: the PERSISTED api_key is never sent to a caller-supplied
        endpoint. A caller-supplied key may go to a caller-supplied base_url
        (their own risk), but the stored secret may only probe its own stored
        base_url — any base_url override (or a provider with no stored key)
        requires a fresh api_key in the body. Blocks credential exfiltration via
        a redirected probe.
        """
        import time
        from starling.dashboard.engine import _build_chat_adapter, _build_embed_adapter
        cfg = request.app.state.config
        src = cfg.embedder if body.kind == "embedder" else cfg.llm
        probe = dict(src)
        for k in ("provider", "model", "base_url", "dim"):
            v = getattr(body, k, None)
            if v is None:
                continue
            if k == "dim" and (not isinstance(v, int) or v <= 0):
                continue
            probe[k] = v
        if body.api_key:
            probe["api_key"] = body.api_key  # caller key may go to caller URL (their own risk)
        else:
            overrides_endpoint = body.base_url is not None and body.base_url != src.get("base_url", "")
            if overrides_endpoint or not src.get("api_key"):
                return {"ok": False, "latency_ms": 0,
                        "detail": "需提供 api_key（改了 base_url 时不复用已存密钥）"}
        t0 = time.monotonic()
        try:
            if body.kind == "embedder":
                vec = _build_embed_adapter(probe).embed("ping")
                ok, detail = True, f"dim={len(vec)}"
            else:
                r = _build_chat_adapter(probe).extract("ping", "")
                ok, detail = bool(r.ok), ("ok" if r.ok else (r.error or "failed"))
            return {"ok": ok, "latency_ms": int((time.monotonic() - t0) * 1000), "detail": detail}
        except Exception as e:  # noqa: BLE001 — surface any build/probe failure as a failed test
            return {"ok": False, "latency_ms": int((time.monotonic() - t0) * 1000), "detail": str(e)}

    return router
