"""Serve the markdown eval reports under docs/eval/ as JSON."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends


def _repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "pyproject.toml").exists():
            return p
    return start


def build_eval_router(require_token) -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

    @router.get("/eval")
    async def eval_reports():
        root = _repo_root(Path(__file__).resolve()) / "docs" / "eval"
        reports = []
        if root.is_dir():
            for p in sorted(root.glob("*.md")):
                reports.append({"name": p.name, "markdown": p.read_text(encoding="utf-8")})
        return {"reports": reports}

    return router
