"""Config routes — read (masked) and update LLM/embedder config + hot-swap."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel


class ProviderBody(BaseModel):
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    dim: int | None = None


class ConfigBody(BaseModel):
    llm: ProviderBody | None = None
    embedder: ProviderBody | None = None


def _mask(d: dict) -> dict:
    out = {"model": d.get("model", ""), "base_url": d.get("base_url", ""),
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
    for k in ("model", "base_url", "api_key", "dim"):
        v = getattr(body, k, None)
        if v is not None:
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

    return router
